//! Error types for MCP Proxy

use thiserror::Error;

/// Result type alias using the crate's Error type
pub type Result<T> = std::result::Result<T, Error>;

/// Main error type for MCP Proxy operations
#[derive(Error, Debug)]
pub enum Error {
    /// Configuration file not found
    #[error("Configuration file not found: {0}")]
    ConfigNotFound(String),

    /// Invalid configuration format
    #[error("Invalid configuration: {0}")]
    InvalidConfig(String),

    /// JSON parsing error
    #[error("JSON parsing error: {0}")]
    JsonError(#[from] serde_json::Error),

    /// IO error
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    /// HTTP client error
    #[error("HTTP error: {0}")]
    HttpError(#[from] reqwest::Error),

    /// URL parsing error
    #[error("Invalid URL: {0}")]
    UrlError(#[from] url::ParseError),

    /// Server startup error
    #[error("Server error: {0}")]
    ServerError(String),

    /// MCP protocol error
    #[error("MCP protocol error: {0}")]
    McpError(String),

    /// Transport error
    #[error("Transport error: {0}")]
    TransportError(String),

    /// Process spawn error
    #[error("Failed to spawn process: {0}")]
    ProcessError(String),

    /// SSE connection error
    #[error("SSE connection error: {0}")]
    SseError(String),

    /// Authentication error
    #[error("Authentication error: {0}")]
    AuthError(String),

    /// Channel communication error
    #[error("Channel error: {0}")]
    ChannelError(String),

    /// Timeout error
    #[error("Operation timed out: {0}")]
    Timeout(String),
}

impl From<tokio::sync::mpsc::error::SendError<String>> for Error {
    fn from(err: tokio::sync::mpsc::error::SendError<String>) -> Self {
        Error::ChannelError(err.to_string())
    }
}
