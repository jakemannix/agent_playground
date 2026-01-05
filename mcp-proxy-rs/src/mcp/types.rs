//! MCP Protocol type definitions
//!
//! These types are based on the MCP specification and are used for
//! JSON-RPC communication between MCP clients and servers.

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;

/// JSON-RPC version string
pub const JSONRPC_VERSION: &str = "2.0";

/// MCP protocol version
pub const MCP_VERSION: &str = "2024-11-05";

/// JSON-RPC request ID
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(untagged)]
pub enum RequestId {
    String(String),
    Number(i64),
}

impl From<String> for RequestId {
    fn from(s: String) -> Self {
        RequestId::String(s)
    }
}

impl From<i64> for RequestId {
    fn from(n: i64) -> Self {
        RequestId::Number(n)
    }
}

/// Base JSON-RPC request structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcRequest {
    pub jsonrpc: String,
    pub id: RequestId,
    pub method: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub params: Option<Value>,
}

impl JsonRpcRequest {
    pub fn new(id: impl Into<RequestId>, method: impl Into<String>, params: Option<Value>) -> Self {
        Self {
            jsonrpc: JSONRPC_VERSION.to_string(),
            id: id.into(),
            method: method.into(),
            params,
        }
    }
}

/// Base JSON-RPC response structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcResponse {
    pub jsonrpc: String,
    pub id: RequestId,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<JsonRpcError>,
}

impl JsonRpcResponse {
    pub fn success(id: RequestId, result: Value) -> Self {
        Self {
            jsonrpc: JSONRPC_VERSION.to_string(),
            id,
            result: Some(result),
            error: None,
        }
    }

    pub fn error(id: RequestId, error: JsonRpcError) -> Self {
        Self {
            jsonrpc: JSONRPC_VERSION.to_string(),
            id,
            result: None,
            error: Some(error),
        }
    }
}

/// JSON-RPC error object
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcError {
    pub code: i32,
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<Value>,
}

impl JsonRpcError {
    pub fn new(code: i32, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            data: None,
        }
    }

    /// Standard JSON-RPC error codes
    pub fn parse_error() -> Self {
        Self::new(-32700, "Parse error")
    }

    pub fn invalid_request() -> Self {
        Self::new(-32600, "Invalid Request")
    }

    pub fn method_not_found() -> Self {
        Self::new(-32601, "Method not found")
    }

    pub fn invalid_params() -> Self {
        Self::new(-32602, "Invalid params")
    }

    pub fn internal_error() -> Self {
        Self::new(-32603, "Internal error")
    }
}

/// JSON-RPC notification (no response expected)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JsonRpcNotification {
    pub jsonrpc: String,
    pub method: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub params: Option<Value>,
}

impl JsonRpcNotification {
    pub fn new(method: impl Into<String>, params: Option<Value>) -> Self {
        Self {
            jsonrpc: JSONRPC_VERSION.to_string(),
            method: method.into(),
            params,
        }
    }
}

/// MCP server capabilities
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ServerCapabilities {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prompts: Option<PromptsCapability>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub resources: Option<ResourcesCapability>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tools: Option<ToolsCapability>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub logging: Option<LoggingCapability>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub experimental: Option<Value>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PromptsCapability {
    #[serde(default, rename = "listChanged")]
    pub list_changed: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ResourcesCapability {
    #[serde(default)]
    pub subscribe: bool,
    #[serde(default, rename = "listChanged")]
    pub list_changed: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ToolsCapability {
    #[serde(default, rename = "listChanged")]
    pub list_changed: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct LoggingCapability {}

/// MCP server information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerInfo {
    pub name: String,
    pub version: String,
}

/// Initialize request parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InitializeParams {
    #[serde(rename = "protocolVersion")]
    pub protocol_version: String,
    pub capabilities: ClientCapabilities,
    #[serde(rename = "clientInfo")]
    pub client_info: ClientInfo,
}

/// Client capabilities
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ClientCapabilities {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub roots: Option<RootsCapability>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sampling: Option<SamplingCapability>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub experimental: Option<Value>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct RootsCapability {
    #[serde(default, rename = "listChanged")]
    pub list_changed: bool,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct SamplingCapability {}

/// Client information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClientInfo {
    pub name: String,
    pub version: String,
}

/// Initialize response result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InitializeResult {
    #[serde(rename = "protocolVersion")]
    pub protocol_version: String,
    pub capabilities: ServerCapabilities,
    #[serde(rename = "serverInfo")]
    pub server_info: ServerInfo,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub instructions: Option<String>,
}

/// Tool definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Tool {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(rename = "inputSchema")]
    pub input_schema: Value,
}

/// List tools response
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListToolsResult {
    pub tools: Vec<Tool>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "nextCursor")]
    pub next_cursor: Option<String>,
}

/// Call tool request parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CallToolParams {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arguments: Option<HashMap<String, Value>>,
}

/// Tool call result content
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum ToolContent {
    #[serde(rename = "text")]
    Text { text: String },
    #[serde(rename = "image")]
    #[allow(non_snake_case)]
    Image { data: String, mimeType: String },
    #[serde(rename = "resource")]
    Resource { resource: ResourceContent },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceContent {
    pub uri: String,
    #[serde(skip_serializing_if = "Option::is_none", rename = "mimeType")]
    pub mime_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub text: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub blob: Option<String>,
}

/// Call tool result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CallToolResult {
    pub content: Vec<ToolContent>,
    #[serde(default, rename = "isError")]
    pub is_error: bool,
}

/// Prompt definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Prompt {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arguments: Option<Vec<PromptArgument>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PromptArgument {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(default)]
    pub required: bool,
}

/// List prompts result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListPromptsResult {
    pub prompts: Vec<Prompt>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "nextCursor")]
    pub next_cursor: Option<String>,
}

/// Get prompt result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GetPromptResult {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    pub messages: Vec<PromptMessage>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PromptMessage {
    pub role: String,
    pub content: PromptContent,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum PromptContent {
    Text(TextContent),
    Image(ImageContent),
    Resource(EmbeddedResource),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TextContent {
    #[serde(rename = "type")]
    pub content_type: String,
    pub text: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImageContent {
    #[serde(rename = "type")]
    pub content_type: String,
    pub data: String,
    #[serde(rename = "mimeType")]
    pub mime_type: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmbeddedResource {
    #[serde(rename = "type")]
    pub content_type: String,
    pub resource: ResourceContent,
}

/// Resource definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Resource {
    pub uri: String,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "mimeType")]
    pub mime_type: Option<String>,
}

/// List resources result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListResourcesResult {
    pub resources: Vec<Resource>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "nextCursor")]
    pub next_cursor: Option<String>,
}

/// Resource template
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceTemplate {
    #[serde(rename = "uriTemplate")]
    pub uri_template: String,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "mimeType")]
    pub mime_type: Option<String>,
}

/// List resource templates result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListResourceTemplatesResult {
    #[serde(rename = "resourceTemplates")]
    pub resource_templates: Vec<ResourceTemplate>,
    #[serde(skip_serializing_if = "Option::is_none", rename = "nextCursor")]
    pub next_cursor: Option<String>,
}

/// Read resource result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReadResourceResult {
    pub contents: Vec<ResourceContent>,
}

/// Logging level
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum McpLogLevel {
    Debug,
    Info,
    Notice,
    Warning,
    Error,
    Critical,
    Alert,
    Emergency,
}

/// Set logging level params
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SetLevelParams {
    pub level: McpLogLevel,
}

/// Progress notification params
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProgressParams {
    #[serde(rename = "progressToken")]
    pub progress_token: Value,
    pub progress: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total: Option<f64>,
}

/// Completion request params
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompleteParams {
    #[serde(rename = "ref")]
    pub reference: CompletionRef,
    pub argument: CompletionArgument,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompletionRef {
    #[serde(rename = "type")]
    pub ref_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub uri: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompletionArgument {
    pub name: String,
    pub value: String,
}

/// Completion result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompleteResult {
    pub completion: Completion,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Completion {
    pub values: Vec<String>,
    #[serde(default)]
    pub total: Option<i32>,
    #[serde(default, rename = "hasMore")]
    pub has_more: bool,
}

/// MCP method names
pub mod methods {
    pub const INITIALIZE: &str = "initialize";
    pub const INITIALIZED: &str = "notifications/initialized";
    pub const PING: &str = "ping";
    pub const LIST_TOOLS: &str = "tools/list";
    pub const CALL_TOOL: &str = "tools/call";
    pub const LIST_PROMPTS: &str = "prompts/list";
    pub const GET_PROMPT: &str = "prompts/get";
    pub const LIST_RESOURCES: &str = "resources/list";
    pub const READ_RESOURCE: &str = "resources/read";
    pub const LIST_RESOURCE_TEMPLATES: &str = "resources/templates/list";
    pub const SUBSCRIBE_RESOURCE: &str = "resources/subscribe";
    pub const UNSUBSCRIBE_RESOURCE: &str = "resources/unsubscribe";
    pub const SET_LEVEL: &str = "logging/setLevel";
    pub const COMPLETE: &str = "completion/complete";
    pub const PROGRESS: &str = "notifications/progress";
    pub const CANCELLED: &str = "notifications/cancelled";
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_request_id_string() {
        let id = RequestId::String("test-123".to_string());
        let json = serde_json::to_string(&id).unwrap();
        assert_eq!(json, "\"test-123\"");

        let parsed: RequestId = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed, id);
    }

    #[test]
    fn test_request_id_number() {
        let id = RequestId::Number(42);
        let json = serde_json::to_string(&id).unwrap();
        assert_eq!(json, "42");

        let parsed: RequestId = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed, id);
    }

    #[test]
    fn test_jsonrpc_request_serialization() {
        let request = JsonRpcRequest::new(
            1i64,
            "tools/list",
            None,
        );

        let json = serde_json::to_value(&request).unwrap();
        assert_eq!(json["jsonrpc"], "2.0");
        assert_eq!(json["id"], 1);
        assert_eq!(json["method"], "tools/list");
        assert!(json.get("params").is_none());
    }

    #[test]
    fn test_jsonrpc_request_with_params() {
        let request = JsonRpcRequest::new(
            "req-1".to_string(),
            "tools/call",
            Some(json!({"name": "get_weather", "arguments": {"city": "Seattle"}})),
        );

        let json = serde_json::to_value(&request).unwrap();
        assert_eq!(json["jsonrpc"], "2.0");
        assert_eq!(json["id"], "req-1");
        assert_eq!(json["method"], "tools/call");
        assert_eq!(json["params"]["name"], "get_weather");
        assert_eq!(json["params"]["arguments"]["city"], "Seattle");
    }

    #[test]
    fn test_jsonrpc_response_success() {
        let response = JsonRpcResponse::success(
            RequestId::Number(1),
            json!({"tools": []}),
        );

        let json = serde_json::to_value(&response).unwrap();
        assert_eq!(json["jsonrpc"], "2.0");
        assert_eq!(json["id"], 1);
        assert!(json.get("result").is_some());
        assert!(json.get("error").is_none());
    }

    #[test]
    fn test_jsonrpc_response_error() {
        let response = JsonRpcResponse::error(
            RequestId::Number(1),
            JsonRpcError::method_not_found(),
        );

        let json = serde_json::to_value(&response).unwrap();
        assert_eq!(json["jsonrpc"], "2.0");
        assert_eq!(json["id"], 1);
        assert!(json.get("result").is_none());
        assert_eq!(json["error"]["code"], -32601);
        assert_eq!(json["error"]["message"], "Method not found");
    }

    #[test]
    fn test_jsonrpc_error_codes() {
        assert_eq!(JsonRpcError::parse_error().code, -32700);
        assert_eq!(JsonRpcError::invalid_request().code, -32600);
        assert_eq!(JsonRpcError::method_not_found().code, -32601);
        assert_eq!(JsonRpcError::invalid_params().code, -32602);
        assert_eq!(JsonRpcError::internal_error().code, -32603);
    }

    #[test]
    fn test_jsonrpc_notification() {
        let notification = JsonRpcNotification::new(
            "notifications/initialized",
            None,
        );

        let json = serde_json::to_value(&notification).unwrap();
        assert_eq!(json["jsonrpc"], "2.0");
        assert_eq!(json["method"], "notifications/initialized");
        assert!(json.get("id").is_none());
    }

    #[test]
    fn test_initialize_params_serialization() {
        let params = InitializeParams {
            protocol_version: MCP_VERSION.to_string(),
            capabilities: ClientCapabilities::default(),
            client_info: ClientInfo {
                name: "test-client".to_string(),
                version: "1.0.0".to_string(),
            },
        };

        let json = serde_json::to_value(&params).unwrap();
        assert_eq!(json["protocolVersion"], MCP_VERSION);
        assert_eq!(json["clientInfo"]["name"], "test-client");
        assert_eq!(json["clientInfo"]["version"], "1.0.0");
    }

    #[test]
    fn test_initialize_result_deserialization() {
        let json = json!({
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": true},
                "prompts": {"listChanged": false}
            },
            "serverInfo": {
                "name": "test-server",
                "version": "0.1.0"
            }
        });

        let result: InitializeResult = serde_json::from_value(json).unwrap();
        assert_eq!(result.protocol_version, "2024-11-05");
        assert_eq!(result.server_info.name, "test-server");
        assert!(result.capabilities.tools.is_some());
        assert!(result.capabilities.prompts.is_some());
    }

    #[test]
    fn test_tool_serialization() {
        let tool = Tool {
            name: "get_weather".to_string(),
            description: Some("Get weather for a city".to_string()),
            input_schema: json!({
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                },
                "required": ["city"]
            }),
        };

        let json = serde_json::to_value(&tool).unwrap();
        assert_eq!(json["name"], "get_weather");
        assert_eq!(json["description"], "Get weather for a city");
        assert_eq!(json["inputSchema"]["type"], "object");
    }

    #[test]
    fn test_list_tools_result_deserialization() {
        let json = json!({
            "tools": [
                {
                    "name": "tool1",
                    "description": "First tool",
                    "inputSchema": {"type": "object"}
                },
                {
                    "name": "tool2",
                    "inputSchema": {"type": "object"}
                }
            ]
        });

        let result: ListToolsResult = serde_json::from_value(json).unwrap();
        assert_eq!(result.tools.len(), 2);
        assert_eq!(result.tools[0].name, "tool1");
        assert!(result.tools[0].description.is_some());
        assert!(result.tools[1].description.is_none());
    }

    #[test]
    fn test_call_tool_params() {
        let params = CallToolParams {
            name: "get_weather".to_string(),
            arguments: Some([("city".to_string(), json!("Seattle"))].into_iter().collect()),
        };

        let json = serde_json::to_value(&params).unwrap();
        assert_eq!(json["name"], "get_weather");
        assert_eq!(json["arguments"]["city"], "Seattle");
    }

    #[test]
    fn test_call_tool_result_success() {
        let json = json!({
            "content": [
                {"type": "text", "text": "The weather is sunny"}
            ],
            "isError": false
        });

        let result: CallToolResult = serde_json::from_value(json).unwrap();
        assert_eq!(result.content.len(), 1);
        assert!(!result.is_error);

        match &result.content[0] {
            ToolContent::Text { text } => assert_eq!(text, "The weather is sunny"),
            _ => panic!("Expected text content"),
        }
    }

    #[test]
    fn test_call_tool_result_error() {
        let json = json!({
            "content": [
                {"type": "text", "text": "City not found"}
            ],
            "isError": true
        });

        let result: CallToolResult = serde_json::from_value(json).unwrap();
        assert!(result.is_error);
    }

    #[test]
    fn test_tool_content_text() {
        let content = ToolContent::Text { text: "Hello".to_string() };
        let json = serde_json::to_value(&content).unwrap();
        assert_eq!(json["type"], "text");
        assert_eq!(json["text"], "Hello");
    }

    #[test]
    fn test_resource_serialization() {
        let resource = Resource {
            uri: "file:///path/to/file.txt".to_string(),
            name: "file.txt".to_string(),
            description: Some("A text file".to_string()),
            mime_type: Some("text/plain".to_string()),
        };

        let json = serde_json::to_value(&resource).unwrap();
        assert_eq!(json["uri"], "file:///path/to/file.txt");
        assert_eq!(json["name"], "file.txt");
        assert_eq!(json["mimeType"], "text/plain");
    }

    #[test]
    fn test_prompt_serialization() {
        let prompt = Prompt {
            name: "summarize".to_string(),
            description: Some("Summarize text".to_string()),
            arguments: Some(vec![
                PromptArgument {
                    name: "text".to_string(),
                    description: Some("Text to summarize".to_string()),
                    required: true,
                },
            ]),
        };

        let json = serde_json::to_value(&prompt).unwrap();
        assert_eq!(json["name"], "summarize");
        assert_eq!(json["arguments"][0]["name"], "text");
        assert_eq!(json["arguments"][0]["required"], true);
    }

    #[test]
    fn test_mcp_log_level_serialization() {
        let level = McpLogLevel::Warning;
        let json = serde_json::to_string(&level).unwrap();
        assert_eq!(json, "\"warning\"");

        let parsed: McpLogLevel = serde_json::from_str(&json).unwrap();
        assert_eq!(parsed, McpLogLevel::Warning);
    }

    #[test]
    fn test_progress_params() {
        let params = ProgressParams {
            progress_token: json!("token-123"),
            progress: 50.0,
            total: Some(100.0),
        };

        let json = serde_json::to_value(&params).unwrap();
        assert_eq!(json["progressToken"], "token-123");
        assert_eq!(json["progress"], 50.0);
        assert_eq!(json["total"], 100.0);
    }

    #[test]
    fn test_server_capabilities_deserialization() {
        let json = json!({
            "tools": {"listChanged": true},
            "prompts": {"listChanged": false},
            "resources": {"subscribe": true, "listChanged": true},
            "logging": {}
        });

        let caps: ServerCapabilities = serde_json::from_value(json).unwrap();
        assert!(caps.tools.is_some());
        assert!(caps.prompts.is_some());
        assert!(caps.resources.is_some());
        assert!(caps.logging.is_some());

        let resources = caps.resources.unwrap();
        assert!(resources.subscribe);
        assert!(resources.list_changed);
    }

    #[test]
    fn test_complete_result() {
        let json = json!({
            "completion": {
                "values": ["option1", "option2", "option3"],
                "total": 10,
                "hasMore": true
            }
        });

        let result: CompleteResult = serde_json::from_value(json).unwrap();
        assert_eq!(result.completion.values.len(), 3);
        assert_eq!(result.completion.total, Some(10));
        assert!(result.completion.has_more);
    }

    #[test]
    fn test_roundtrip_request() {
        let original = JsonRpcRequest::new(
            42i64,
            "tools/call",
            Some(json!({"name": "test", "arguments": {"key": "value"}})),
        );

        let json_str = serde_json::to_string(&original).unwrap();
        let parsed: JsonRpcRequest = serde_json::from_str(&json_str).unwrap();

        assert_eq!(parsed.id, original.id);
        assert_eq!(parsed.method, original.method);
        assert_eq!(parsed.params, original.params);
    }

    #[test]
    fn test_method_constants() {
        assert_eq!(methods::INITIALIZE, "initialize");
        assert_eq!(methods::LIST_TOOLS, "tools/list");
        assert_eq!(methods::CALL_TOOL, "tools/call");
        assert_eq!(methods::LIST_PROMPTS, "prompts/list");
        assert_eq!(methods::LIST_RESOURCES, "resources/list");
    }
}
