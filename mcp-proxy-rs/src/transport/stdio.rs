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
