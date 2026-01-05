//! Standard I/O transport for MCP
//!
//! Provides communication with MCP servers via stdin/stdout.

use std::collections::HashMap;
use std::process::Stdio;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::mpsc;
use tracing::{debug, error, info, warn};

use crate::error::{Error, Result};

/// Parameters for spawning a stdio-based MCP server
#[derive(Debug, Clone)]
pub struct StdioServerParams {
    /// Command to execute
    pub command: String,
    /// Arguments to pass to the command
    pub args: Vec<String>,
    /// Environment variables
    pub env: HashMap<String, String>,
    /// Working directory
    pub cwd: Option<String>,
}

impl StdioServerParams {
    pub fn new(command: impl Into<String>) -> Self {
        Self {
            command: command.into(),
            args: Vec::new(),
            env: HashMap::new(),
            cwd: None,
        }
    }

    pub fn with_args(mut self, args: Vec<String>) -> Self {
        self.args = args;
        self
    }

    pub fn with_env(mut self, env: HashMap<String, String>) -> Self {
        self.env = env;
        self
    }

    pub fn with_cwd(mut self, cwd: impl Into<String>) -> Self {
        self.cwd = Some(cwd.into());
        self
    }
}

/// Transport for communicating with stdio-based MCP servers
#[derive(Debug)]
pub struct StdioTransport {
    child: Child,
    /// Channel for receiving messages from the child process
    pub read_rx: Option<mpsc::Receiver<String>>,
    /// Channel for sending messages to the child process
    pub write_tx: Option<mpsc::Sender<String>>,
}

impl StdioTransport {
    /// Spawn a new stdio transport with the given parameters
    pub async fn spawn(params: &StdioServerParams) -> Result<Self> {
        info!("Spawning stdio server: {} {}", params.command, params.args.join(" "));

        let mut cmd = Command::new(&params.command);
        cmd.args(&params.args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());

        // Set environment variables
        for (key, value) in &params.env {
            cmd.env(key, value);
        }

        // Set working directory if specified
        if let Some(ref cwd) = params.cwd {
            cmd.current_dir(cwd);
        }

        let mut child = cmd.spawn().map_err(|e| {
            Error::ProcessError(format!("Failed to spawn '{}': {}", params.command, e))
        })?;

        let stdin = child.stdin.take().ok_or_else(|| {
            Error::ProcessError("Failed to capture stdin".to_string())
        })?;

        let stdout = child.stdout.take().ok_or_else(|| {
            Error::ProcessError("Failed to capture stdout".to_string())
        })?;

        // Create channels for bidirectional communication
        let (write_tx, mut write_rx) = mpsc::channel::<String>(100);
        let (read_tx, read_rx) = mpsc::channel::<String>(100);

        // Spawn task to write to stdin
        tokio::spawn(async move {
            let mut stdin = stdin;
            while let Some(message) = write_rx.recv().await {
                debug!("Writing to stdio: {}", message.trim());
                if let Err(e) = stdin.write_all(message.as_bytes()).await {
                    error!("Failed to write to stdin: {}", e);
                    break;
                }
                if let Err(e) = stdin.write_all(b"\n").await {
                    error!("Failed to write newline: {}", e);
                    break;
                }
                if let Err(e) = stdin.flush().await {
                    error!("Failed to flush stdin: {}", e);
                    break;
                }
            }
            debug!("Stdin writer task ended");
        });

        // Spawn task to read from stdout
        tokio::spawn(async move {
            let reader = BufReader::new(stdout);
            let mut lines = reader.lines();

            while let Ok(Some(line)) = lines.next_line().await {
                debug!("Read from stdio: {}", line);
                if read_tx.send(line).await.is_err() {
                    warn!("Read channel closed");
                    break;
                }
            }
            debug!("Stdout reader task ended");
        });

        Ok(Self {
            child,
            read_rx: Some(read_rx),
            write_tx: Some(write_tx),
        })
    }

    /// Take ownership of the channels, leaving None in their place
    /// This allows moving the channels out of the struct while keeping
    /// the child process alive for cleanup purposes.
    pub fn take_channels(&mut self) -> Option<(mpsc::Receiver<String>, mpsc::Sender<String>)> {
        let read_rx = self.read_rx.take()?;
        let write_tx = self.write_tx.take()?;
        Some((read_rx, write_tx))
    }

    /// Check if the child process is still running
    pub fn is_running(&mut self) -> bool {
        match self.child.try_wait() {
            Ok(Some(_)) => false,
            Ok(None) => true,
            Err(_) => false,
        }
    }

    /// Kill the child process
    pub async fn kill(&mut self) -> Result<()> {
        self.child.kill().await.map_err(|e| {
            Error::ProcessError(format!("Failed to kill process: {}", e))
        })
    }
}

impl Drop for StdioTransport {
    fn drop(&mut self) {
        // Try to kill the child process when the transport is dropped
        let _ = self.child.start_kill();
    }
}

/// Run a stdio server that reads from stdin and writes to stdout
/// This is used when the proxy itself acts as a stdio server
pub struct StdioServer {
    /// Channel for receiving messages from stdin
    pub read_rx: mpsc::Receiver<String>,
    /// Channel for sending messages to stdout
    pub write_tx: mpsc::Sender<String>,
}

impl StdioServer {
    /// Create a new stdio server using the current process's stdin/stdout
    pub fn new() -> Self {
        let (write_tx, mut write_rx) = mpsc::channel::<String>(100);
        let (read_tx, read_rx) = mpsc::channel::<String>(100);

        // Spawn task to read from stdin
        tokio::spawn(async move {
            let stdin = tokio::io::stdin();
            let reader = BufReader::new(stdin);
            let mut lines = reader.lines();

            while let Ok(Some(line)) = lines.next_line().await {
                debug!("Read from stdin: {}", line);
                if read_tx.send(line).await.is_err() {
                    break;
                }
            }
            debug!("Stdin reader task ended");
        });

        // Spawn task to write to stdout
        tokio::spawn(async move {
            let mut stdout = tokio::io::stdout();
            while let Some(message) = write_rx.recv().await {
                debug!("Writing to stdout: {}", message.trim());
                if let Err(e) = stdout.write_all(message.as_bytes()).await {
                    error!("Failed to write to stdout: {}", e);
                    break;
                }
                if let Err(e) = stdout.write_all(b"\n").await {
                    error!("Failed to write newline: {}", e);
                    break;
                }
                if let Err(e) = stdout.flush().await {
                    error!("Failed to flush stdout: {}", e);
                    break;
                }
            }
            debug!("Stdout writer task ended");
        });

        Self { read_rx, write_tx }
    }
}

impl Default for StdioServer {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_stdio_server_params_new() {
        let params = StdioServerParams::new("python");
        assert_eq!(params.command, "python");
        assert!(params.args.is_empty());
        assert!(params.env.is_empty());
        assert!(params.cwd.is_none());
    }

    #[test]
    fn test_stdio_server_params_builder() {
        let mut env = HashMap::new();
        env.insert("API_KEY".to_string(), "secret".to_string());

        let params = StdioServerParams::new("node")
            .with_args(vec!["server.js".to_string(), "--port".to_string(), "8080".to_string()])
            .with_env(env)
            .with_cwd("/app");

        assert_eq!(params.command, "node");
        assert_eq!(params.args, vec!["server.js", "--port", "8080"]);
        assert_eq!(params.env.get("API_KEY"), Some(&"secret".to_string()));
        assert_eq!(params.cwd, Some("/app".to_string()));
    }

    #[test]
    fn test_stdio_server_params_clone() {
        let params = StdioServerParams::new("python")
            .with_args(vec!["script.py".to_string()]);

        let cloned = params.clone();
        assert_eq!(params.command, cloned.command);
        assert_eq!(params.args, cloned.args);
    }

    #[tokio::test]
    async fn test_channel_communication() {
        // Test that mpsc channels work correctly for message passing
        let (tx, mut rx) = mpsc::channel::<String>(10);

        tx.send("message1".to_string()).await.unwrap();
        tx.send("message2".to_string()).await.unwrap();

        assert_eq!(rx.recv().await, Some("message1".to_string()));
        assert_eq!(rx.recv().await, Some("message2".to_string()));
    }

    #[tokio::test]
    async fn test_channel_close_detection() {
        let (tx, mut rx) = mpsc::channel::<String>(10);

        tx.send("test".to_string()).await.unwrap();
        drop(tx); // Close the sender

        assert_eq!(rx.recv().await, Some("test".to_string()));
        assert_eq!(rx.recv().await, None); // Channel closed
    }

    #[tokio::test]
    async fn test_bidirectional_channels() {
        // Simulate bidirectional communication like in a proxy
        let (client_tx, mut server_rx) = mpsc::channel::<String>(10);
        let (server_tx, mut client_rx) = mpsc::channel::<String>(10);

        // Client sends request
        client_tx.send(r#"{"jsonrpc":"2.0","id":1,"method":"ping"}"#.to_string()).await.unwrap();

        // Server receives and responds
        let request = server_rx.recv().await.unwrap();
        assert!(request.contains("ping"));

        server_tx.send(r#"{"jsonrpc":"2.0","id":1,"result":{}}"#.to_string()).await.unwrap();

        // Client receives response
        let response = client_rx.recv().await.unwrap();
        assert!(response.contains("result"));
    }

    #[tokio::test]
    async fn test_concurrent_message_handling() {
        let (tx, mut rx) = mpsc::channel::<String>(100);

        // Spawn multiple senders
        let tx1 = tx.clone();
        let tx2 = tx.clone();

        let h1 = tokio::spawn(async move {
            for i in 0..10 {
                tx1.send(format!("sender1-{}", i)).await.unwrap();
            }
        });

        let h2 = tokio::spawn(async move {
            for i in 0..10 {
                tx2.send(format!("sender2-{}", i)).await.unwrap();
            }
        });

        h1.await.unwrap();
        h2.await.unwrap();
        drop(tx);

        let mut count = 0;
        while let Some(_msg) = rx.recv().await {
            count += 1;
        }

        assert_eq!(count, 20);
    }

    #[tokio::test]
    async fn test_spawn_nonexistent_command() {
        let params = StdioServerParams::new("nonexistent_command_12345");
        let result = StdioTransport::spawn(&params).await;

        assert!(result.is_err());
        let err = result.unwrap_err();
        assert!(matches!(err, crate::error::Error::ProcessError(_)));
    }

    #[tokio::test]
    async fn test_spawn_echo_command() {
        // Test spawning a simple command that exits immediately
        let params = StdioServerParams::new("echo")
            .with_args(vec!["hello".to_string()]);

        let result = StdioTransport::spawn(&params).await;
        assert!(result.is_ok());

        let mut transport = result.unwrap();

        // The echo command outputs and exits quickly
        // Give it a moment to complete
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;

        // Check that we can take channels
        let channels = transport.take_channels();
        assert!(channels.is_some());

        // Second take should return None
        let channels2 = transport.take_channels();
        assert!(channels2.is_none());
    }

    #[tokio::test]
    async fn test_transport_take_channels_once() {
        let params = StdioServerParams::new("cat");

        let result = StdioTransport::spawn(&params).await;
        // cat might not be available on all systems
        if let Ok(mut transport) = result {
            // First take succeeds
            let channels = transport.take_channels();
            assert!(channels.is_some());

            // Second take returns None
            let channels2 = transport.take_channels();
            assert!(channels2.is_none());
        }
    }
}
