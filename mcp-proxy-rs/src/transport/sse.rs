//! Server-Sent Events (SSE) transport for MCP
//!
//! Provides both client and server implementations for SSE-based MCP communication.

use axum::{
    extract::State,
    response::{
        sse::{Event, KeepAlive, Sse},
        IntoResponse, Response,
    },
    routing::{get, post},
    Json, Router,
};
use futures::stream::Stream;
use reqwest::Client;
use reqwest_eventsource::{Event as EsEvent, EventSource};
use serde_json::Value;
use std::collections::HashMap;
use std::convert::Infallible;
use std::sync::Arc;
use tokio::sync::{broadcast, mpsc, Mutex};
use tracing::{debug, error, info, warn};
use uuid::Uuid;

use crate::error::{Error, Result};

/// SSE Client for connecting to remote MCP servers over SSE
#[allow(dead_code)]
pub struct SseClient {
    url: String,
    headers: HashMap<String, String>,
    client: Client,
    /// Channel for receiving messages from the server
    pub read_rx: mpsc::Receiver<String>,
    /// Channel for sending messages to the server
    pub write_tx: mpsc::Sender<String>,
}

impl SseClient {
    /// Create a new SSE client connection
    pub async fn connect(
        url: &str,
        headers: HashMap<String, String>,
        client: Client,
    ) -> Result<Self> {
        info!("Connecting to SSE endpoint: {}", url);

        let (write_tx, mut write_rx) = mpsc::channel::<String>(100);
        let (read_tx, read_rx) = mpsc::channel::<String>(100);

        // Build the SSE request
        let mut request_builder = client.get(url);
        for (key, value) in &headers {
            request_builder = request_builder.header(key, value);
        }

        let event_source = EventSource::new(request_builder)
            .map_err(|e| Error::SseError(format!("Failed to create event source: {}", e)))?;

        let messages_url = Arc::new(Mutex::new(None::<String>));
        let messages_url_clone = Arc::clone(&messages_url);
        let client_clone = client.clone();
        let headers_clone = headers.clone();

        // Spawn task to receive SSE events
        tokio::spawn(async move {
            use futures::StreamExt;
            let mut es = event_source;

            while let Some(event) = es.next().await {
                match event {
                    Ok(EsEvent::Open) => {
                        debug!("SSE connection opened");
                    }
                    Ok(EsEvent::Message(msg)) => {
                        debug!("SSE event: {} - {}", msg.event, msg.data);

                        // Handle endpoint event to get the messages URL
                        if msg.event == "endpoint" {
                            let mut url_lock = messages_url_clone.lock().await;
                            *url_lock = Some(msg.data.clone());
                            debug!("Got messages endpoint: {}", msg.data);
                            continue;
                        }

                        // Handle message events
                        if msg.event == "message" {
                            if read_tx.send(msg.data).await.is_err() {
                                warn!("Read channel closed");
                                break;
                            }
                        }
                    }
                    Err(e) => {
                        error!("SSE error: {}", e);
                        break;
                    }
                }
            }
            debug!("SSE event reader task ended");
        });

        // Spawn task to send messages via POST
        let url_for_post = url.to_string();
        tokio::spawn(async move {
            while let Some(message) = write_rx.recv().await {
                // Get the messages URL
                let post_url = {
                    let url_lock = messages_url.lock().await;
                    match &*url_lock {
                        Some(endpoint) => {
                            // Resolve relative URL against base
                            if endpoint.starts_with("http") {
                                endpoint.clone()
                            } else {
                                // Parse base URL and join
                                if let Ok(base) = url::Url::parse(&url_for_post) {
                                    base.join(endpoint)
                                        .map(|u| u.to_string())
                                        .unwrap_or_else(|_| endpoint.clone())
                                } else {
                                    endpoint.clone()
                                }
                            }
                        }
                        None => {
                            // Default to /messages endpoint
                            if let Ok(base) = url::Url::parse(&url_for_post) {
                                base.join("/messages/")
                                    .map(|u| u.to_string())
                                    .unwrap_or_else(|_| format!("{}/messages/", url_for_post.trim_end_matches('/')))
                            } else {
                                format!("{}/messages/", url_for_post.trim_end_matches('/'))
                            }
                        }
                    }
                };

                debug!("Sending message to: {}", post_url);

                let mut request = client_clone.post(&post_url)
                    .header("Content-Type", "application/json")
                    .body(message.clone());

                for (key, value) in &headers_clone {
                    request = request.header(key, value);
                }

                match request.send().await {
                    Ok(response) => {
                        if !response.status().is_success() {
                            error!("POST request failed with status: {}", response.status());
                        }
                    }
                    Err(e) => {
                        error!("Failed to send POST request: {}", e);
                    }
                }
            }
            debug!("SSE message sender task ended");
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

/// Shared state for SSE server
#[derive(Clone)]
pub struct SseServerState {
    /// Sender for broadcasting messages to SSE clients
    pub message_tx: broadcast::Sender<String>,
    /// Receiver for incoming messages from clients
    pub incoming_tx: mpsc::Sender<String>,
    /// Session ID for this connection
    pub session_id: String,
}

/// SSE Server for exposing MCP servers over SSE
pub struct SseServer {
    state: SseServerState,
    /// Receiver for messages to be sent to clients
    pub incoming_rx: mpsc::Receiver<String>,
}

impl SseServer {
    /// Create a new SSE server
    pub fn new() -> Self {
        let (message_tx, _) = broadcast::channel(100);
        let (incoming_tx, incoming_rx) = mpsc::channel(100);
        let session_id = Uuid::new_v4().to_string();

        Self {
            state: SseServerState {
                message_tx,
                incoming_tx,
                session_id,
            },
            incoming_rx,
        }
    }

    /// Get the shared state for use in routes
    pub fn state(&self) -> SseServerState {
        self.state.clone()
    }

    /// Send a message to all connected SSE clients
    pub fn send(&self, message: String) -> Result<()> {
        self.state.message_tx.send(message).map_err(|e| {
            Error::ChannelError(format!("Failed to broadcast message: {}", e))
        })?;
        Ok(())
    }

    /// Create router routes for SSE endpoints
    pub fn routes(state: SseServerState) -> Router {
        Router::new()
            .route("/sse", get(sse_handler))
            .route("/messages/", post(post_message_handler))
            .route("/messages", post(post_message_handler))
            .with_state(state)
    }
}

impl Default for SseServer {
    fn default() -> Self {
        Self::new()
    }
}

/// Handler for SSE connections
async fn sse_handler(
    State(state): State<SseServerState>,
) -> Sse<impl Stream<Item = std::result::Result<Event, Infallible>>> {
    info!("New SSE client connected");

    let mut rx = state.message_tx.subscribe();
    let session_id = state.session_id.clone();

    let stream = async_stream::stream! {
        // Send endpoint event first
        yield Ok(Event::default()
            .event("endpoint")
            .data(format!("/messages/?session_id={}", session_id)));

        // Then stream messages
        while let Ok(msg) = rx.recv().await {
            debug!("Sending SSE message: {}", msg);
            yield Ok(Event::default().event("message").data(msg));
        }
    };

    Sse::new(stream).keep_alive(KeepAlive::default())
}

/// Handler for POST messages from SSE clients
async fn post_message_handler(
    State(state): State<SseServerState>,
    Json(body): Json<Value>,
) -> impl IntoResponse {
    debug!("Received POST message: {}", body);

    let message = serde_json::to_string(&body).unwrap_or_default();
    if let Err(e) = state.incoming_tx.send(message).await {
        error!("Failed to forward message: {}", e);
        return Response::builder()
            .status(500)
            .body("Failed to process message".to_string())
            .unwrap();
    }

    Response::builder()
        .status(202)
        .body("Accepted".to_string())
        .unwrap()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sse_server_creation() {
        let server = SseServer::new();
        let state = server.state();

        // Verify session ID is a valid UUID
        assert!(!state.session_id.is_empty());
        assert!(uuid::Uuid::parse_str(&state.session_id).is_ok());
    }

    #[test]
    fn test_sse_server_state_clone() {
        let server = SseServer::new();
        let state1 = server.state();
        let state2 = state1.clone();

        assert_eq!(state1.session_id, state2.session_id);
    }

    #[tokio::test]
    async fn test_broadcast_channel_subscription() {
        let (tx, _rx) = broadcast::channel::<String>(100);

        // Subscribe multiple receivers
        let mut rx1 = tx.subscribe();
        let mut rx2 = tx.subscribe();

        // Send a message
        tx.send("test message".to_string()).unwrap();

        // Both receivers should get the message
        assert_eq!(rx1.recv().await.unwrap(), "test message");
        assert_eq!(rx2.recv().await.unwrap(), "test message");
    }

    #[tokio::test]
    async fn test_broadcast_multiple_messages() {
        let (tx, _rx) = broadcast::channel::<String>(100);
        let mut rx = tx.subscribe();

        tx.send("message1".to_string()).unwrap();
        tx.send("message2".to_string()).unwrap();
        tx.send("message3".to_string()).unwrap();

        assert_eq!(rx.recv().await.unwrap(), "message1");
        assert_eq!(rx.recv().await.unwrap(), "message2");
        assert_eq!(rx.recv().await.unwrap(), "message3");
    }

    #[tokio::test]
    async fn test_sse_server_send() {
        let server = SseServer::new();
        let state = server.state();
        let mut rx = state.message_tx.subscribe();

        // Send through the server
        server.send("test".to_string()).unwrap();

        // Should receive on subscriber
        assert_eq!(rx.recv().await.unwrap(), "test");
    }

    #[tokio::test]
    async fn test_sse_incoming_messages() {
        let mut server = SseServer::new();
        let state = server.state();

        // Send an incoming message
        state.incoming_tx.send("incoming test".to_string()).await.unwrap();

        // Should be received on server's incoming_rx
        let msg = server.incoming_rx.recv().await.unwrap();
        assert_eq!(msg, "incoming test");
    }

    #[tokio::test]
    async fn test_sse_bidirectional_flow() {
        let mut server = SseServer::new();
        let state = server.state();
        let mut broadcast_rx = state.message_tx.subscribe();

        // Simulate client sending a message (POST)
        state.incoming_tx.send(r#"{"jsonrpc":"2.0","id":1,"method":"ping"}"#.to_string()).await.unwrap();

        // Server receives it
        let request = server.incoming_rx.recv().await.unwrap();
        assert!(request.contains("ping"));

        // Server broadcasts response
        server.send(r#"{"jsonrpc":"2.0","id":1,"result":{}}"#.to_string()).unwrap();

        // Client (via SSE) receives response
        let response = broadcast_rx.recv().await.unwrap();
        assert!(response.contains("result"));
    }

    #[tokio::test]
    async fn test_multiple_sse_clients() {
        let server = SseServer::new();
        let state = server.state();

        // Multiple clients subscribe
        let mut client1 = state.message_tx.subscribe();
        let mut client2 = state.message_tx.subscribe();
        let mut client3 = state.message_tx.subscribe();

        // Server broadcasts a message
        server.send("broadcast to all".to_string()).unwrap();

        // All clients receive it
        assert_eq!(client1.recv().await.unwrap(), "broadcast to all");
        assert_eq!(client2.recv().await.unwrap(), "broadcast to all");
        assert_eq!(client3.recv().await.unwrap(), "broadcast to all");
    }

    #[tokio::test]
    async fn test_sse_stream_json_messages() {
        let server = SseServer::new();
        let state = server.state();
        let mut rx = state.message_tx.subscribe();

        // Send various JSON-RPC messages
        let messages = vec![
            r#"{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}"#,
            r#"{"jsonrpc":"2.0","id":2,"method":"tools/list"}"#,
            r#"{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"test"}}"#,
        ];

        for msg in &messages {
            server.send(msg.to_string()).unwrap();
        }

        for expected in messages {
            let received = rx.recv().await.unwrap();
            assert_eq!(received, expected);
        }
    }

    #[tokio::test]
    async fn test_late_subscriber() {
        let server = SseServer::new();
        let state = server.state();

        // Send message before subscriber exists - this fails because broadcast
        // channels require at least one subscriber
        let result = server.send("early message".to_string());
        assert!(result.is_err()); // No subscribers, so send fails

        // Subscribe after the failed message
        let mut rx = state.message_tx.subscribe();

        // Send another message - now it succeeds
        server.send("late message".to_string()).unwrap();

        // Late subscriber only sees the new message
        assert_eq!(rx.recv().await.unwrap(), "late message");
    }

    #[tokio::test]
    async fn test_concurrent_sends() {
        let server = SseServer::new();
        let state = server.state();
        let mut rx = state.message_tx.subscribe();

        // Spawn multiple concurrent senders
        let server1 = SseServer {
            state: state.clone(),
            incoming_rx: mpsc::channel(1).1,
        };
        let server2 = SseServer {
            state: state.clone(),
            incoming_rx: mpsc::channel(1).1,
        };

        let h1 = tokio::spawn(async move {
            for i in 0..5 {
                server1.send(format!("s1-{}", i)).unwrap();
            }
        });

        let h2 = tokio::spawn(async move {
            for i in 0..5 {
                server2.send(format!("s2-{}", i)).unwrap();
            }
        });

        h1.await.unwrap();
        h2.await.unwrap();

        // Should receive all 10 messages (plus our original server's messages if any)
        let mut count = 0;
        while count < 10 {
            let _ = rx.recv().await.unwrap();
            count += 1;
        }
        assert_eq!(count, 10);
    }

    #[test]
    fn test_sse_server_routes_creation() {
        let server = SseServer::new();
        let state = server.state();

        // Just verify routes can be created without panicking
        let _routes = SseServer::routes(state);
    }

    #[tokio::test]
    async fn test_channel_backpressure() {
        // Test with a small channel to simulate backpressure
        let (tx, mut rx) = mpsc::channel::<String>(2);

        // Fill the channel
        tx.send("msg1".to_string()).await.unwrap();
        tx.send("msg2".to_string()).await.unwrap();

        // Channel is now full, send would block
        // Use try_send to test
        let result = tx.try_send("msg3".to_string());
        assert!(result.is_err()); // Channel full

        // Drain one message
        let _ = rx.recv().await;

        // Now we can send again
        tx.send("msg3".to_string()).await.unwrap();
    }

    #[test]
    fn test_session_id_uniqueness() {
        let server1 = SseServer::new();
        let server2 = SseServer::new();

        assert_ne!(server1.state().session_id, server2.state().session_id);
    }
}
