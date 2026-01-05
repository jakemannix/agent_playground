//! Proxy server implementation
//!
//! Creates an MCP server that proxies requests to a remote MCP client session.

pub mod server;

pub use server::{create_proxy_server, run_proxy_bridge, ProxyServer};
