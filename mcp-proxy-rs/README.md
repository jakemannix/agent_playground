# mcp-proxy-rs

A Rust port of [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) - a transport bridge for MCP (Model Context Protocol) servers.

## Overview

`mcp-proxy` enables communication between different MCP server transports. It operates in two modes:

1. **Mode 1: stdio → SSE/StreamableHTTP** (Client Mode)
   - Acts as a proxy allowing clients like Claude Desktop to communicate with remote SSE/StreamableHTTP servers
   - Reads from stdin, forwards to remote server, and writes responses to stdout

2. **Mode 2: SSE → stdio** (Server Mode)
   - Exposes local stdio-based MCP servers via SSE endpoints
   - Enables remote access to local MCP services

## Installation

### From Source

```bash
cd mcp-proxy-rs
cargo build --release

# Binaries will be in target/release/
# - mcp-proxy
# - mcp-reverse-proxy
```

## Usage

### Client Mode (Mode 1)

Connect to a remote MCP server and expose via stdio:

```bash
# Connect to SSE endpoint
mcp-proxy http://localhost:8080/sse

# Connect to StreamableHTTP endpoint
mcp-proxy http://localhost:8080/mcp --transport streamable-http

# With authentication
mcp-proxy http://localhost:8080/sse --token "your-api-token"
# Or use environment variable
API_ACCESS_TOKEN="your-token" mcp-proxy http://localhost:8080/sse

# With custom headers
mcp-proxy http://localhost:8080/sse -H "X-Custom-Header: value"

# Disable SSL verification (not recommended for production)
mcp-proxy https://server.example.com/sse --insecure
```

### Server Mode (Mode 2)

Expose stdio MCP servers via SSE:

```bash
# Expose a single server
mcp-proxy --port 8080 --command python --args "weather.py --port 8123"

# Or use the dedicated reverse-proxy binary
mcp-reverse-proxy --port 8080 --command python --args "weather.py"

# Multiple named servers
mcp-proxy --port 8080 \
  --named-server "weather=python weather.py" \
  --named-server "files=node file-server.js"

# From configuration file
mcp-proxy --port 8080 --named-server-config servers.json

# With CORS and debug logging
mcp-proxy --port 8080 \
  --command python --args "server.py" \
  --allow-origin "*" \
  --debug
```

### Configuration File Format

Create a `servers.json` file:

```json
{
  "mcpServers": {
    "weather": {
      "command": "python",
      "args": ["weather.py", "--port", "8123"],
      "env": {
        "API_KEY": "your-api-key"
      },
      "enabled": true
    },
    "filesystem": {
      "command": "node",
      "args": ["fs-server.js"],
      "enabled": true
    },
    "disabled-server": {
      "command": "python",
      "args": ["other.py"],
      "enabled": false
    }
  }
}
```

## CLI Reference

### mcp-proxy

```
Usage: mcp-proxy [OPTIONS] [URL]

Arguments:
  [URL]  URL of the remote MCP server (enables client mode)

Options:
  -t, --transport <TRANSPORT>    Transport type [default: sse] [values: sse, streamable-http]
  -H, --header <HEADERS>         HTTP headers (format: "Name: Value")
      --token <TOKEN>            API access token [env: API_ACCESS_TOKEN]
      --insecure                 Disable SSL verification
      --ca-cert <CA_CERT>        Custom CA certificate path
  -d, --debug                    Enable debug logging
      --log-level <LOG_LEVEL>    Log level [default: info]
  -p, --port <PORT>              Port (enables server mode)
      --host <HOST>              Bind host [default: 127.0.0.1]
      --stateless                Run in stateless mode
      --allow-origin <ORIGINS>   CORS allowed origins
      --command <COMMAND>        Default server command
      --args <ARGS>              Default server arguments
      --named-server <SERVERS>   Named servers (name=command args...)
      --named-server-config <PATH>  JSON config file path
      --pass-environment         Pass env vars to child processes
  -h, --help                     Print help
  -V, --version                  Print version
```

### mcp-reverse-proxy

Simplified entry point for server mode:

```
Usage: mcp-reverse-proxy [OPTIONS] --port <PORT>

Options:
  -p, --port <PORT>              Port to listen on (required)
      --host <HOST>              Bind host [default: 127.0.0.1]
      --command <COMMAND>        Default server command
      --args <ARGS>              Default server arguments
      --named-server <SERVERS>   Named servers
      --named-server-config <PATH>  JSON config file
      --stateless                Run in stateless mode
      --allow-origin <ORIGINS>   CORS allowed origins
      --pass-environment         Pass env vars to child processes
  -d, --debug                    Enable debug logging
  -h, --help                     Print help
  -V, --version                  Print version
```

## Endpoints

When running in server mode, the following endpoints are available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Health check and server info |
| `/sse` | GET | SSE connection for default server |
| `/messages/` | POST | Send messages to default server |
| `/servers/{name}/sse` | GET | SSE connection for named server |
| `/servers/{name}/messages/` | POST | Send messages to named server |
| `/mcp` | POST | StreamableHTTP endpoint (if enabled) |

## Integration with Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "remote-weather": {
      "command": "mcp-proxy",
      "args": ["http://remote-server.example.com:8080/sse"]
    }
  }
}
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        mcp-proxy                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐ │
│  │   Transport  │     │    Proxy     │     │   Transport  │ │
│  │    Layer     │◄───►│    Server    │◄───►│    Layer     │ │
│  │              │     │              │     │              │ │
│  │  - stdio     │     │  - Message   │     │  - SSE       │ │
│  │  - SSE       │     │    routing   │     │  - HTTP      │ │
│  │  - HTTP      │     │  - Protocol  │     │  - stdio     │ │
│  └──────────────┘     └──────────────┘     └──────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Comparison with Python Version

This Rust implementation provides:

- **Performance**: Native code execution, lower memory footprint
- **Single Binary**: No Python runtime required
- **Type Safety**: Compile-time guarantees for protocol handling
- **Cross-platform**: Easy cross-compilation for different targets

## License

MIT License - see the original [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) repository.

## Credits

This is a Rust port of [sparfenyuk/mcp-proxy](https://github.com/sparfenyuk/mcp-proxy).
