//! MCP Client Session
//!
//! Manages communication with an MCP server, providing methods for
//! all MCP protocol operations.

use serde_json::Value;
use std::collections::HashMap;
use std::sync::atomic::{AtomicI64, Ordering};
use std::sync::Arc;
use tokio::sync::{mpsc, oneshot, Mutex};
use tracing::{debug, warn};

use super::types::*;
use crate::error::{Error, Result};

/// A pending request awaiting a response
struct PendingRequest {
    response_tx: oneshot::Sender<JsonRpcResponse>,
}

/// MCP Client Session for communicating with an MCP server
pub struct ClientSession {
    /// Channel for sending requests to the transport
    request_tx: mpsc::Sender<String>,
    /// Pending requests awaiting responses
    pending_requests: Arc<Mutex<HashMap<RequestId, PendingRequest>>>,
    /// Request ID counter
    next_id: AtomicI64,
    /// Server capabilities (after initialization)
    capabilities: Arc<Mutex<Option<ServerCapabilities>>>,
    /// Server info (after initialization)
    server_info: Arc<Mutex<Option<ServerInfo>>>,
}

impl ClientSession {
    /// Create a new client session with a transport channel
    pub fn new(request_tx: mpsc::Sender<String>) -> Self {
        Self {
            request_tx,
            pending_requests: Arc::new(Mutex::new(HashMap::new())),
            next_id: AtomicI64::new(1),
            capabilities: Arc::new(Mutex::new(None)),
            server_info: Arc::new(Mutex::new(None)),
        }
    }

    /// Generate the next request ID
    fn next_request_id(&self) -> RequestId {
        RequestId::Number(self.next_id.fetch_add(1, Ordering::SeqCst))
    }

    /// Send a request and wait for a response
    async fn send_request(&self, method: &str, params: Option<Value>) -> Result<Value> {
        let id = self.next_request_id();
        let request = JsonRpcRequest::new(id.clone(), method, params);
        let request_json = serde_json::to_string(&request)?;

        let (response_tx, response_rx) = oneshot::channel();

        {
            let mut pending = self.pending_requests.lock().await;
            pending.insert(id.clone(), PendingRequest { response_tx });
        }

        debug!("Sending request: {} (id={:?})", method, id);
        self.request_tx.send(request_json).await
            .map_err(|e| Error::ChannelError(e.to_string()))?;

        let response = response_rx.await
            .map_err(|_| Error::ChannelError("Response channel closed".to_string()))?;

        if let Some(error) = response.error {
            return Err(Error::McpError(format!("{}: {}", error.code, error.message)));
        }

        response.result.ok_or_else(|| Error::McpError("Empty response".to_string()))
    }

    /// Send a notification (no response expected)
    async fn send_notification(&self, method: &str, params: Option<Value>) -> Result<()> {
        let notification = JsonRpcNotification::new(method, params);
        let notification_json = serde_json::to_string(&notification)?;

        debug!("Sending notification: {}", method);
        self.request_tx.send(notification_json).await
            .map_err(|e| Error::ChannelError(e.to_string()))?;

        Ok(())
    }

    /// Handle an incoming response
    pub async fn handle_response(&self, response: JsonRpcResponse) {
        let mut pending = self.pending_requests.lock().await;
        if let Some(pending_request) = pending.remove(&response.id) {
            if pending_request.response_tx.send(response).is_err() {
                warn!("Failed to send response - receiver dropped");
            }
        } else {
            warn!("Received response for unknown request ID: {:?}", response.id);
        }
    }

    /// Initialize the session with the server
    pub async fn initialize(&self) -> Result<InitializeResult> {
        let params = InitializeParams {
            protocol_version: MCP_VERSION.to_string(),
            capabilities: ClientCapabilities::default(),
            client_info: ClientInfo {
                name: "mcp-proxy".to_string(),
                version: env!("CARGO_PKG_VERSION").to_string(),
            },
        };

        let result_value = self.send_request(methods::INITIALIZE, Some(serde_json::to_value(params)?)).await?;
        let result: InitializeResult = serde_json::from_value(result_value)?;

        // Store capabilities and server info
        {
            let mut caps = self.capabilities.lock().await;
            *caps = Some(result.capabilities.clone());
        }
        {
            let mut info = self.server_info.lock().await;
            *info = Some(result.server_info.clone());
        }

        // Send initialized notification
        self.send_notification(methods::INITIALIZED, None).await?;

        debug!("Session initialized with server: {}", result.server_info.name);
        Ok(result)
    }

    /// Get the server capabilities
    pub async fn capabilities(&self) -> Option<ServerCapabilities> {
        self.capabilities.lock().await.clone()
    }

    /// Get the server info
    pub async fn server_info(&self) -> Option<ServerInfo> {
        self.server_info.lock().await.clone()
    }

    /// List available tools
    pub async fn list_tools(&self) -> Result<ListToolsResult> {
        let result = self.send_request(methods::LIST_TOOLS, None).await?;
        Ok(serde_json::from_value(result)?)
    }

    /// Call a tool
    pub async fn call_tool(&self, name: &str, arguments: HashMap<String, Value>) -> Result<CallToolResult> {
        let params = CallToolParams {
            name: name.to_string(),
            arguments: if arguments.is_empty() { None } else { Some(arguments) },
        };
        let result = self.send_request(methods::CALL_TOOL, Some(serde_json::to_value(params)?)).await?;
        Ok(serde_json::from_value(result)?)
    }

    /// List available prompts
    pub async fn list_prompts(&self) -> Result<ListPromptsResult> {
        let result = self.send_request(methods::LIST_PROMPTS, None).await?;
        Ok(serde_json::from_value(result)?)
    }

    /// Get a prompt
    pub async fn get_prompt(&self, name: &str, arguments: Option<HashMap<String, String>>) -> Result<GetPromptResult> {
        let mut params = serde_json::json!({ "name": name });
        if let Some(args) = arguments {
            params["arguments"] = serde_json::to_value(args)?;
        }
        let result = self.send_request(methods::GET_PROMPT, Some(params)).await?;
        Ok(serde_json::from_value(result)?)
    }

    /// List available resources
    pub async fn list_resources(&self) -> Result<ListResourcesResult> {
        let result = self.send_request(methods::LIST_RESOURCES, None).await?;
        Ok(serde_json::from_value(result)?)
    }

    /// Read a resource
    pub async fn read_resource(&self, uri: &str) -> Result<ReadResourceResult> {
        let params = serde_json::json!({ "uri": uri });
        let result = self.send_request(methods::READ_RESOURCE, Some(params)).await?;
        Ok(serde_json::from_value(result)?)
    }

    /// List resource templates
    pub async fn list_resource_templates(&self) -> Result<ListResourceTemplatesResult> {
        let result = self.send_request(methods::LIST_RESOURCE_TEMPLATES, None).await?;
        Ok(serde_json::from_value(result)?)
    }

    /// Subscribe to a resource
    pub async fn subscribe_resource(&self, uri: &str) -> Result<()> {
        let params = serde_json::json!({ "uri": uri });
        self.send_request(methods::SUBSCRIBE_RESOURCE, Some(params)).await?;
        Ok(())
    }

    /// Unsubscribe from a resource
    pub async fn unsubscribe_resource(&self, uri: &str) -> Result<()> {
        let params = serde_json::json!({ "uri": uri });
        self.send_request(methods::UNSUBSCRIBE_RESOURCE, Some(params)).await?;
        Ok(())
    }

    /// Set the logging level
    pub async fn set_logging_level(&self, level: McpLogLevel) -> Result<()> {
        let params = SetLevelParams { level };
        self.send_request(methods::SET_LEVEL, Some(serde_json::to_value(params)?)).await?;
        Ok(())
    }

    /// Request completions
    pub async fn complete(&self, reference: CompletionRef, argument: CompletionArgument) -> Result<CompleteResult> {
        let params = CompleteParams { reference, argument };
        let result = self.send_request(methods::COMPLETE, Some(serde_json::to_value(params)?)).await?;
        Ok(serde_json::from_value(result)?)
    }

    /// Send a progress notification
    pub async fn send_progress_notification(&self, token: Value, progress: f64, total: Option<f64>) -> Result<()> {
        let params = ProgressParams {
            progress_token: token,
            progress,
            total,
        };
        self.send_notification(methods::PROGRESS, Some(serde_json::to_value(params)?)).await
    }

    /// Send a ping
    pub async fn ping(&self) -> Result<()> {
        self.send_request(methods::PING, None).await?;
        Ok(())
    }
}
