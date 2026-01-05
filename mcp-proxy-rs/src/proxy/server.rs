//! Proxy server that forwards MCP requests to a remote server
//!
//! This module creates an MCP server that proxies all requests through
//! an MCP client session, enabling transport bridging.

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::{mpsc, Mutex};
use tracing::{debug, info, warn};

use crate::error::{Error, Result};
use crate::mcp::types::*;

/// A proxy server that forwards MCP requests to a remote session
#[allow(dead_code)]
pub struct ProxyServer {
    /// Server name (from remote server)
    pub name: String,
    /// Server capabilities (from remote server)
    pub capabilities: ServerCapabilities,
    /// Channel for sending requests to the remote server
    request_tx: mpsc::Sender<String>,
    /// Pending requests awaiting responses
    pending_requests: Arc<Mutex<HashMap<RequestId, mpsc::Sender<JsonRpcResponse>>>>,
}

impl ProxyServer {
    /// Create a new proxy server
    pub fn new(
        name: String,
        capabilities: ServerCapabilities,
        request_tx: mpsc::Sender<String>,
    ) -> Self {
        Self {
            name,
            capabilities,
            request_tx,
            pending_requests: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Handle an incoming JSON-RPC message and return a response
    pub async fn handle_message(&self, message: &str) -> Result<Option<String>> {
        // Try to parse as request first
        if let Ok(request) = serde_json::from_str::<JsonRpcRequest>(message) {
            return self.handle_request(request).await;
        }

        // Try to parse as notification
        if let Ok(notification) = serde_json::from_str::<JsonRpcNotification>(message) {
            return self.handle_notification(notification).await;
        }

        // Try to parse as response (for forwarding)
        if let Ok(response) = serde_json::from_str::<JsonRpcResponse>(message) {
            return self.handle_response(response).await;
        }

        Err(Error::McpError("Failed to parse message".to_string()))
    }

    /// Handle an incoming request
    async fn handle_request(&self, request: JsonRpcRequest) -> Result<Option<String>> {
        debug!("Proxying request: {} (id={:?})", request.method, request.id);

        // Forward the request to the remote server
        let request_json = serde_json::to_string(&request)?;
        self.request_tx.send(request_json).await
            .map_err(|e| Error::ChannelError(e.to_string()))?;

        // For now, we don't wait for the response here - it will come back
        // through the response handler
        Ok(None)
    }

    /// Handle an incoming notification
    async fn handle_notification(&self, notification: JsonRpcNotification) -> Result<Option<String>> {
        debug!("Proxying notification: {}", notification.method);

        // Forward the notification to the remote server
        let notification_json = serde_json::to_string(&notification)?;
        self.request_tx.send(notification_json).await
            .map_err(|e| Error::ChannelError(e.to_string()))?;

        Ok(None)
    }

    /// Handle an incoming response (forward it)
    async fn handle_response(&self, response: JsonRpcResponse) -> Result<Option<String>> {
        debug!("Received response for id={:?}", response.id);

        // Forward the response
        let response_json = serde_json::to_string(&response)?;
        Ok(Some(response_json))
    }

    /// Get initialization options for the server
    pub fn create_initialization_options(&self) -> InitializeResult {
        InitializeResult {
            protocol_version: MCP_VERSION.to_string(),
            capabilities: self.capabilities.clone(),
            server_info: ServerInfo {
                name: self.name.clone(),
                version: env!("CARGO_PKG_VERSION").to_string(),
            },
            instructions: None,
        }
    }
}

/// Create a proxy server from a remote client session
///
/// This function initializes a connection to the remote server and creates
/// a proxy server that forwards all requests to it.
pub async fn create_proxy_server(
    request_tx: mpsc::Sender<String>,
    mut response_rx: mpsc::Receiver<String>,
) -> Result<(ProxyServer, mpsc::Receiver<String>)> {
    info!("Creating proxy server...");

    // Send initialize request
    let init_request = JsonRpcRequest::new(
        1i64,
        methods::INITIALIZE,
        Some(serde_json::to_value(InitializeParams {
            protocol_version: MCP_VERSION.to_string(),
            capabilities: ClientCapabilities::default(),
            client_info: ClientInfo {
                name: "mcp-proxy".to_string(),
                version: env!("CARGO_PKG_VERSION").to_string(),
            },
        })?),
    );

    let init_json = serde_json::to_string(&init_request)?;
    request_tx.send(init_json).await
        .map_err(|e| Error::ChannelError(e.to_string()))?;

    debug!("Sent initialization request, waiting for response...");

    // Wait for initialize response
    let response_text = response_rx.recv().await
        .ok_or_else(|| Error::McpError("No initialization response received".to_string()))?;

    let response: JsonRpcResponse = serde_json::from_str(&response_text)?;
    let result = response.result
        .ok_or_else(|| Error::McpError("Empty initialization response".to_string()))?;

    let init_result: InitializeResult = serde_json::from_value(result)?;

    info!("Connected to remote server: {}", init_result.server_info.name);
    debug!("Server capabilities: {:?}", init_result.capabilities);

    // Send initialized notification
    let initialized = JsonRpcNotification::new(methods::INITIALIZED, None);
    let initialized_json = serde_json::to_string(&initialized)?;
    request_tx.send(initialized_json).await
        .map_err(|e| Error::ChannelError(e.to_string()))?;

    let proxy = ProxyServer::new(
        init_result.server_info.name,
        init_result.capabilities,
        request_tx,
    );

    Ok((proxy, response_rx))
}

/// Run a bidirectional proxy between two transports
pub async fn run_proxy_bridge(
    mut client_rx: mpsc::Receiver<String>,
    client_tx: mpsc::Sender<String>,
    mut server_rx: mpsc::Receiver<String>,
    server_tx: mpsc::Sender<String>,
) -> Result<()> {
    info!("Starting proxy bridge...");

    loop {
        tokio::select! {
            // Forward messages from client to server
            Some(msg) = client_rx.recv() => {
                debug!("Client -> Server: {}", msg);
                if server_tx.send(msg).await.is_err() {
                    warn!("Server channel closed");
                    break;
                }
            }
            // Forward messages from server to client
            Some(msg) = server_rx.recv() => {
                debug!("Server -> Client: {}", msg);
                if client_tx.send(msg).await.is_err() {
                    warn!("Client channel closed");
                    break;
                }
            }
            else => {
                info!("Both channels closed, stopping bridge");
                break;
            }
        }
    }

    Ok(())
}
