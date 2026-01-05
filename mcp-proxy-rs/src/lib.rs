//! MCP Proxy - A transport bridge for MCP (Model Context Protocol) servers
//!
//! This crate provides a proxy that enables communication between different
//! MCP server transports. It operates in two modes:
//!
//! 1. **stdio to SSE/StreamableHTTP Client**: Acts as a proxy allowing clients like
//!    Claude Desktop to communicate with remote SSE servers.
//!
//! 2. **SSE to stdio Server**: Exposes an SSE server endpoint while connecting
//!    to local stdio-based MCP servers.

pub mod config;
pub mod error;
pub mod http_client;
pub mod mcp;
pub mod proxy;
pub mod transport;

pub use config::{McpServerSettings, NamedServerConfig, ServerConfig};
pub use error::{Error, Result};
