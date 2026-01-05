//! MCP Reverse Proxy - Expose stdio servers via SSE/HTTP
//!
//! This is an alternative entry point that focuses on server mode,
//! making it easier to expose local stdio-based MCP servers via SSE.

use clap::Parser;
use mcp_proxy::config::load_named_server_configs_from_file;
use mcp_proxy::transport::sse::SseServer;
use mcp_proxy::transport::stdio::{StdioServerParams, StdioTransport};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::path::PathBuf;
use tracing::{error, info, Level};
use tracing_subscriber::EnvFilter;

/// MCP Reverse Proxy - Expose stdio MCP servers via SSE/HTTP
#[derive(Parser, Debug)]
#[command(name = "mcp-reverse-proxy")]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Port to listen on (required)
    #[arg(short, long)]
    port: u16,

    /// Host to bind to
    #[arg(long, default_value = "127.0.0.1")]
    host: String,

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

    /// Run in stateless mode
    #[arg(long)]
    stateless: bool,

    /// Allowed CORS origins (can be specified multiple times)
    #[arg(long)]
    allow_origin: Vec<String>,

    /// Pass current environment variables to spawned processes
    #[arg(long)]
    pass_environment: bool,

    /// Enable debug logging
    #[arg(short, long)]
    debug: bool,
}

fn setup_logging(debug: bool) {
    let level = if debug { Level::DEBUG } else { Level::INFO };
    let filter = EnvFilter::from_default_env().add_directive(level.into());

    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(false)
        .with_writer(std::io::stderr)
        .init();
}

fn parse_named_server_cli(arg: &str) -> Option<(String, StdioServerParams)> {
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
    use axum::Router;
    use tower_http::cors::{Any, CorsLayer};

    let args = Args::parse();
    setup_logging(args.debug);

    info!("Starting MCP Reverse Proxy on {}:{}", args.host, args.port);

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
        let params = StdioServerParams::new(cmd.clone()).with_args(args.args.clone());
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

    // Build router
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
    app = app.route(
        "/status",
        axum::routing::get(|| async {
            axum::Json(serde_json::json!({
                "status": "ok",
                "version": env!("CARGO_PKG_VERSION")
            }))
        }),
    );

    // Spawn default server if configured
    if let Some(params) = default_server {
        info!(
            "Starting default server: {} {}",
            params.command,
            params.args.join(" ")
        );

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
        info!(
            "Starting named server '{}': {} {}",
            name,
            params.command,
            params.args.join(" ")
        );

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
    let addr: SocketAddr = format!("{}:{}", args.host, args.port).parse()?;
    info!("Server listening on http://{}", addr);

    // Print available endpoints
    info!("Available endpoints:");
    info!("  GET  /status - Health check");
    if args.command.is_some() {
        info!("  GET  /sse - Default server SSE endpoint");
        info!("  POST /messages/ - Default server message endpoint");
    }

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
