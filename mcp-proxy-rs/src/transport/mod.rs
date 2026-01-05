//! Transport layer implementations for MCP
//!
//! This module provides different transport mechanisms for MCP communication:
//! - stdio: Standard input/output transport
//! - SSE: Server-Sent Events transport
//! - StreamableHTTP: HTTP-based streaming transport

pub mod stdio;
pub mod sse;
pub mod streamable_http;

pub use stdio::{StdioTransport, StdioServerParams};
pub use sse::{SseClient, SseServer};
pub use streamable_http::StreamableHttpClient;
