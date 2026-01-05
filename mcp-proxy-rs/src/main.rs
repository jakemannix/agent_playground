//! MCP Proxy - Transport bridge for MCP servers
//!
//! This is the main entry point for the mcp-proxy application, which operates
//! in two modes:
//!
//! 1. **Mode 1 (Default)**: SSE/StreamableHTTP to stdio - Connect to a remote
//!    SSE or StreamableHTTP server and expose it via stdio
//!
//! 2. **Mode 2**: stdio to SSE - Expose local stdio servers via SSE endpoints
//!    (use mcp-reverse-proxy binary or --server mode)

use clap::{Parser, ValueEnum};
use mcp_proxy::config::{load_named_server_configs_from_file, LogLevel};
use mcp_proxy::http_client::{create_http_client, HttpClientConfig};
use mcp_proxy::proxy::run_proxy_bridge;
use mcp_proxy::transport::stdio::{StdioServer, StdioServerParams, StdioTransport};
use mcp_proxy::transport::sse::SseClient;
use mcp_proxy::transport::streamable_http::StreamableHttpClient;
use reqwest::header::{HeaderMap, HeaderName, HeaderValue};
use std::collections::HashMap;
use std::path::PathBuf;
use std::str::FromStr;
use tracing::{error, info, Level};
use tracing_subscriber::EnvFilter;

/// Transport type for client connections
#[derive(Debug, Clone, Copy, ValueEnum, Default)]
enum TransportType {
    #[default]
    Sse,
    StreamableHttp,
}

/// MCP Proxy - A transport bridge for MCP servers
#[derive(Parser, Debug)]
#[command(name = "mcp-proxy")]
#[command(author, version, about, long_about = None)]
struct Args {
    /// URL of the remote MCP server (SSE or StreamableHTTP endpoint)
    /// If provided, operates in client mode (Mode 1)
    #[arg(index = 1)]
    url: Option<String>,

    /// Transport type to use for connecting to remote server
    #[arg(short, long, value_enum, default_value = "sse")]
    transport: TransportType,

    /// HTTP header to pass to the remote server (can be specified multiple times)
    /// Format: "Header-Name: Header-Value"
    #[arg(short = 'H', long = "header")]
    headers: Vec<String>,

    /// API access token (can also be set via API_ACCESS_TOKEN env var)
    #[arg(long, env = "API_ACCESS_TOKEN")]
    token: Option<String>,

    /// Disable SSL certificate verification
    #[arg(long)]
    insecure: bool,

    /// Path to custom CA certificate bundle
    #[arg(long)]
    ca_cert: Option<PathBuf>,

    /// Enable debug logging
    #[arg(short, long)]
    debug: bool,

    /// Log level
    #[arg(long, default_value = "info")]
    log_level: String,

    // --- Server mode options (Mode 2) ---
    /// Port to listen on (enables server mode)
    #[arg(short, long)]
    port: Option<u16>,

    /// Host to bind to
    #[arg(long, default_value = "127.0.0.1")]
    host: String,

    /// Run in stateless mode
    #[arg(long)]
    stateless: bool,

    /// Allowed CORS origins (can be specified multiple times)
    #[arg(long)]
    allow_origin: Vec<String>,

    /// Command to spawn for default stdio server
    #[arg(long)]
    command: Option<String>,

    /// Arguments for the default command
    #[arg(long)]
    args: Vec<String>,

    /// Named server configuration (format: name=command args...)
    #[arg(long = "named-server")]
    named_servers: Vec<String>,

    /// Path to JSON configuration file for named servers
    #[arg(long = "named-server-config")]
    named_server_config: Option<PathBuf>,

    /// Pass current environment variables to spawned processes
    #[arg(long)]
    pass_environment: bool,
}

fn setup_logging(debug: bool, log_level: &str) {
    let level = if debug {
        Level::DEBUG
    } else {
        log_level
            .parse::<LogLevel>()
            .map(|l| match l {
                LogLevel::Debug => Level::DEBUG,
                LogLevel::Info => Level::INFO,
                LogLevel::Warning => Level::WARN,
                LogLevel::Error | LogLevel::Critical => Level::ERROR,
            })
            .unwrap_or(Level::INFO)
    };

    let filter = EnvFilter::from_default_env()
        .add_directive(level.into());

    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(false)
        .with_writer(std::io::stderr)
        .init();
}

fn parse_headers(header_strings: &[String], token: Option<&str>) -> HashMap<String, String> {
    let mut headers = HashMap::new();

    for header in header_strings {
        if let Some((name, value)) = header.split_once(':') {
            headers.insert(name.trim().to_string(), value.trim().to_string());
        }
    }

    // Add authorization header if token is provided
    if let Some(token) = token {
        headers.insert("Authorization".to_string(), format!("Bearer {}", token));
    }

    headers
}

fn parse_named_server_cli(arg: &str) -> Option<(String, StdioServerParams)> {
    // Format: name=command arg1 arg2 ...
    let (name, rest) = arg.split_once('=')?;
    let parts: Vec<&str> = rest.split_whitespace().collect();
    if parts.is_empty() {
        return None;
    }

    let command = parts[0].to_string();
    let args = parts[1..].iter().map(|s| s.to_string()).collect();

    Some((
        name.to_string(),
        StdioServerParams::new(command).with_args(args),
    ))
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    setup_logging(args.debug, &args.log_level);

    // Determine operating mode based on arguments
    let is_client_mode = args.url.is_some();
    let is_server_mode = args.port.is_some();

    if is_client_mode {
        run_client_mode(&args).await
    } else if is_server_mode {
        run_server_mode(&args).await
    } else {
        // Default: client mode requires URL
        error!("No URL provided. Please provide a remote MCP server URL or use --port for server mode.");
        error!("\nUsage:");
        error!("  Client mode: mcp-proxy <URL>");
        error!("  Server mode: mcp-proxy --port <PORT> --command <CMD>");
        std::process::exit(1);
    }
}

/// Run in client mode: connect to remote SSE/StreamableHTTP and expose via stdio
async fn run_client_mode(args: &Args) -> anyhow::Result<()> {
    let url = args.url.as_ref().unwrap();
    info!("Starting client mode, connecting to: {}", url);

    // Parse headers
    let headers = parse_headers(&args.headers, args.token.as_deref());

    // Create HTTP client
    let http_config = HttpClientConfig {
        headers: if headers.is_empty() {
            None
        } else {
            let mut header_map = HeaderMap::new();
            for (k, v) in &headers {
                if let (Ok(name), Ok(value)) = (
                    HeaderName::from_str(k),
                    HeaderValue::from_str(v),
                ) {
                    header_map.insert(name, value);
                }
            }
            Some(header_map)
        },
        timeout_secs: 30,
        verify_ssl: !args.insecure,
        ca_cert_path: args.ca_cert.as_ref().map(|p| p.to_string_lossy().to_string()),
    };

    let http_client = create_http_client(&http_config)?;

    // Connect to remote server
    match args.transport {
        TransportType::Sse => {
            info!("Using SSE transport");
            let sse_client = SseClient::connect(url, headers, http_client).await?;

            // Create stdio server for local communication
            let stdio_server = StdioServer::new();

            // Run the proxy bridge
            // - client_rx: read from stdin (local client sends requests)
            // - client_tx: write to stdout (send responses to local client)
            // - server_rx: read from SSE (remote server sends responses)
            // - server_tx: write to SSE via POST (send requests to remote server)
            run_proxy_bridge(
                stdio_server.read_rx,    // client_rx
                stdio_server.write_tx,   // client_tx
                sse_client.read_rx,      // server_rx
                sse_client.write_tx,     // server_tx
            )
            .await?;
        }
        TransportType::StreamableHttp => {
            info!("Using StreamableHTTP transport");
            let http_client_conn =
                StreamableHttpClient::connect(url, headers, http_client).await?;

            // Create stdio server for local communication
            let stdio_server = StdioServer::new();

            // Run the proxy bridge
            // - client_rx: read from stdin (local client sends requests)
            // - client_tx: write to stdout (send responses to local client)
            // - server_rx: read from HTTP (remote server sends responses)
            // - server_tx: write to HTTP (send requests to remote server)
            run_proxy_bridge(
                stdio_server.read_rx,       // client_rx
                stdio_server.write_tx,      // client_tx
                http_client_conn.read_rx,   // server_rx
                http_client_conn.write_tx,  // server_tx
            )
            .await?;
        }
    }

    Ok(())
}

/// Run in server mode: expose stdio servers via SSE/HTTP endpoints
async fn run_server_mode(args: &Args) -> anyhow::Result<()> {
    use axum::Router;
    use mcp_proxy::transport::sse::SseServer;
    use std::net::SocketAddr;
    use tower_http::cors::{Any, CorsLayer};

    let port = args.port.unwrap();
    info!("Starting server mode on {}:{}", args.host, port);

    // Collect named servers
    let mut named_servers: HashMap<String, StdioServerParams> = HashMap::new();

    // Get base environment if requested
    let base_env: HashMap<String, String> = if args.pass_environment {
        std::env::vars().collect()
    } else {
        HashMap::new()
    };

    // Load from config file if provided
    if let Some(ref config_path) = args.named_server_config {
        let configs = load_named_server_configs_from_file(config_path, &base_env)?;
        for (name, config) in configs {
            named_servers.insert(
                name,
                StdioServerParams {
                    command: config.command,
                    args: config.args,
                    env: config.env,
                    cwd: config.cwd,
                },
            );
        }
    }

    // Add servers from CLI
    for server_arg in &args.named_servers {
        if let Some((name, params)) = parse_named_server_cli(server_arg) {
            let params = if args.pass_environment {
                params.with_env(base_env.clone())
            } else {
                params
            };
            named_servers.insert(name, params);
        }
    }

    // Add default server if command is provided
    let default_server = if let Some(ref cmd) = args.command {
        let params = StdioServerParams::new(cmd.clone())
            .with_args(args.args.clone());
        let params = if args.pass_environment {
            params.with_env(base_env.clone())
        } else {
            params
        };
        Some(params)
    } else {
        None
    };

    if default_server.is_none() && named_servers.is_empty() {
        error!("No servers configured. Use --command for a default server or --named-server for named servers.");
        std::process::exit(1);
    }

    // Build router with all server endpoints
    let mut app = Router::new();

    // Add CORS if origins specified
    if !args.allow_origin.is_empty() {
        let cors = CorsLayer::new()
            .allow_origin(Any)
            .allow_methods(Any)
            .allow_headers(Any);
        app = app.layer(cors);
    }

    // Add status endpoint
    app = app.route("/status", axum::routing::get(|| async {
        axum::Json(serde_json::json!({
            "status": "ok",
            "version": env!("CARGO_PKG_VERSION")
        }))
    }));

    // Spawn default server if configured
    if let Some(params) = default_server {
        info!("Starting default server: {} {}", params.command, params.args.join(" "));

        let mut transport = StdioTransport::spawn(&params).await?;
        let sse_server = SseServer::new();
        let state = sse_server.state();

        // Add default SSE routes
        let sse_routes = SseServer::routes(state.clone());
        app = app.merge(sse_routes);

        // Take ownership of the channels
        let (mut read_rx, write_tx) = transport.take_channels()
            .ok_or_else(|| anyhow::anyhow!("Failed to get transport channels"))?;
        let message_tx = state.message_tx.clone();
        let mut incoming_rx = sse_server.incoming_rx;

        // Spawn bridge for default server
        // IMPORTANT: Move transport into the task to keep the child process alive
        tokio::spawn(async move {
            // Keep transport alive to prevent the child process from being killed
            let _transport = transport;

            loop {
                tokio::select! {
                    Some(msg) = read_rx.recv() => {
                        let _ = message_tx.send(msg);
                    }
                    Some(msg) = incoming_rx.recv() => {
                        if write_tx.send(msg).await.is_err() {
                            break;
                        }
                    }
                    else => break,
                }
            }
        });
    }

    // Spawn named servers
    for (name, params) in named_servers {
        info!("Starting named server '{}': {} {}", name, params.command, params.args.join(" "));

        let mut transport = StdioTransport::spawn(&params).await?;
        let sse_server = SseServer::new();
        let state = sse_server.state();

        // Add named server routes under /servers/{name}/
        let sse_routes = SseServer::routes(state.clone());
        app = app.nest(&format!("/servers/{}", name), sse_routes);

        // Take ownership of the channels
        let (mut read_rx, write_tx) = transport.take_channels()
            .ok_or_else(|| anyhow::anyhow!("Failed to get transport channels"))?;
        let message_tx = state.message_tx.clone();
        let mut incoming_rx = sse_server.incoming_rx;

        // Spawn bridge for named server
        // IMPORTANT: Move transport into the task to keep the child process alive
        tokio::spawn(async move {
            // Keep transport alive to prevent the child process from being killed
            let _transport = transport;

            loop {
                tokio::select! {
                    Some(msg) = read_rx.recv() => {
                        let _ = message_tx.send(msg);
                    }
                    Some(msg) = incoming_rx.recv() => {
                        if write_tx.send(msg).await.is_err() {
                            break;
                        }
                    }
                    else => break,
                }
            }
        });
    }

    // Start the server
    let addr: SocketAddr = format!("{}:{}", args.host, port).parse()?;
    info!("Server listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
