//! Streamable HTTP transport for MCP
//!
//! Provides HTTP-based streaming transport as an alternative to SSE.

use reqwest::Client;
use std::collections::HashMap;
use tokio::sync::mpsc;
use tracing::{debug, error, info, warn};

use crate::error::Result;

/// StreamableHTTP Client for connecting to remote MCP servers
#[allow(dead_code)]
pub struct StreamableHttpClient {
    url: String,
    headers: HashMap<String, String>,
    client: Client,
    /// Channel for receiving messages from the server
    pub read_rx: mpsc::Receiver<String>,
    /// Channel for sending messages to the server
    pub write_tx: mpsc::Sender<String>,
}

impl StreamableHttpClient {
    /// Create a new StreamableHTTP client connection
    pub async fn connect(
        url: &str,
        headers: HashMap<String, String>,
        client: Client,
    ) -> Result<Self> {
        info!("Connecting to StreamableHTTP endpoint: {}", url);

        let (write_tx, mut write_rx) = mpsc::channel::<String>(100);
        let (read_tx, read_rx) = mpsc::channel::<String>(100);

        let client_clone = client.clone();
        let url_clone = url.to_string();
        let headers_clone = headers.clone();

        // Spawn task to send messages and receive responses
        tokio::spawn(async move {
            while let Some(message) = write_rx.recv().await {
                debug!("Sending StreamableHTTP request: {}", message);

                let mut request = client_clone
                    .post(&url_clone)
                    .header("Content-Type", "application/json")
                    .header("Accept", "application/json, text/event-stream")
                    .body(message.clone());

                for (key, value) in &headers_clone {
                    request = request.header(key, value);
                }

                match request.send().await {
                    Ok(response) => {
                        let status = response.status();
                        let content_type = response
                            .headers()
                            .get("content-type")
                            .and_then(|v| v.to_str().ok())
                            .unwrap_or("")
                            .to_string();

                        debug!("Response status: {}, content-type: {}", status, content_type);

                        if !status.is_success() {
                            error!("StreamableHTTP request failed with status: {}", status);
                            continue;
                        }

                        // Handle SSE response
                        if content_type.contains("text/event-stream") {
                            match response.text().await {
                                Ok(body) => {
                                    // Parse SSE events
                                    for line in body.lines() {
                                        if line.starts_with("data: ") {
                                            let data = &line[6..];
                                            debug!("Received SSE data: {}", data);
                                            if read_tx.send(data.to_string()).await.is_err() {
                                                warn!("Read channel closed");
                                                return;
                                            }
                                        }
                                    }
                                }
                                Err(e) => {
                                    error!("Failed to read response body: {}", e);
                                }
                            }
                        }
                        // Handle JSON response
                        else if content_type.contains("application/json") {
                            match response.text().await {
                                Ok(body) => {
                                    debug!("Received JSON response: {}", body);
                                    if read_tx.send(body).await.is_err() {
                                        warn!("Read channel closed");
                                        return;
                                    }
                                }
                                Err(e) => {
                                    error!("Failed to read response body: {}", e);
                                }
                            }
                        }
                    }
                    Err(e) => {
                        error!("Failed to send StreamableHTTP request: {}", e);
                    }
                }
            }
            debug!("StreamableHTTP sender task ended");
        });

        Ok(Self {
            url: url.to_string(),
            headers,
            client,
            read_rx,
            write_tx,
        })
    }
}

/// StreamableHTTP server handler for Axum
pub mod server {
    use axum::{
        extract::State,
        http::{header, StatusCode},
        response::{IntoResponse, Response},
        routing::post,
        Router,
    };
    use serde_json::Value;
    
    use tokio::sync::mpsc;
    use tracing::{debug, error};

    /// Shared state for StreamableHTTP server
    #[derive(Clone)]
    pub struct StreamableHttpState {
        /// Channel for sending incoming requests
        pub request_tx: mpsc::Sender<(Value, mpsc::Sender<String>)>,
    }

    /// Create StreamableHTTP server routes
    pub fn routes(state: StreamableHttpState) -> Router {
        Router::new()
            .route("/mcp", post(mcp_handler))
            .route("/mcp/", post(mcp_handler))
            .with_state(state)
    }

    /// Handler for MCP requests over StreamableHTTP
    async fn mcp_handler(
        State(state): State<StreamableHttpState>,
        body: String,
    ) -> impl IntoResponse {
        debug!("Received StreamableHTTP request: {}", body);

        let request: Value = match serde_json::from_str(&body) {
            Ok(v) => v,
            Err(e) => {
                error!("Failed to parse request: {}", e);
                return Response::builder()
                    .status(StatusCode::BAD_REQUEST)
                    .body(format!("Invalid JSON: {}", e))
                    .unwrap();
            }
        };

        // Create a channel for the response
        let (response_tx, mut response_rx) = mpsc::channel::<String>(1);

        // Send request to handler
        if let Err(e) = state.request_tx.send((request, response_tx)).await {
            error!("Failed to forward request: {}", e);
            return Response::builder()
                .status(StatusCode::INTERNAL_SERVER_ERROR)
                .body("Failed to process request".to_string())
                .unwrap();
        }

        // Wait for response
        match response_rx.recv().await {
            Some(response) => Response::builder()
                .status(StatusCode::OK)
                .header(header::CONTENT_TYPE, "application/json")
                .body(response)
                .unwrap(),
            None => Response::builder()
                .status(StatusCode::INTERNAL_SERVER_ERROR)
                .body("No response".to_string())
                .unwrap(),
        }
    }
}
