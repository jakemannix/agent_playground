# MCP Proxy Modal Deployment

This directory contains a Modal deployment configuration for the MCP proxy servers.

## Prerequisites

1. Install Modal CLI:
   ```bash
   pip install modal
   ```

2. Authenticate with Modal:
   ```bash
   modal setup
   ```

## Configuration

The deployment uses `servers_config.json` which configures three MCP servers:
- **fetch**: Web fetching capabilities via `mcp-server-fetch`
- **memory**: Persistent memory via `@modelcontextprotocol/server-memory`
- **search**: DuckDuckGo search via `duckduckgo-mcp-server`

## Local Development

Test the deployment locally:

```bash
modal run tools/modal_deploy.py
```

This will:
1. Test all dependencies (mcp-proxy, Node.js/npm, uv/uvx)
2. Start the MCP proxy server
3. Expose endpoints on port 18456

## Production Deployment

Deploy to Modal cloud:

```bash
modal serve tools/modal_deploy.py
```

This will deploy the MCP proxy as a persistent service with:
- Automatic scaling
- Health monitoring
- Public endpoints

## Available Endpoints

Once deployed, the following endpoints will be available:

- **Status**: `https://[your-modal-url]/status`
- **Fetch Server**: `https://[your-modal-url]/servers/fetch/sse`
- **Memory Server**: `https://[your-modal-url]/servers/memory/sse`
- **Search Server**: `https://[your-modal-url]/servers/search/sse`

## Web Interface

A simple web interface is available at the root URL to monitor the proxy status and view available endpoints.

## Configuration Options

You can modify the deployment by editing `modal_deploy.py`:

- **Resources**: Adjust CPU, memory, and timeout in the `@app.function` decorator
- **Port**: Change the default port (18456) in the `run_mcp_proxy` function
- **Servers**: Modify `servers_config.json` to add/remove MCP servers

## Troubleshooting

1. **Dependency Issues**: Run `modal run tools/modal_deploy.py` locally first to test dependencies
2. **Configuration Errors**: Check that `servers_config.json` is valid JSON
3. **Port Conflicts**: Ensure port 18456 is available or change the port in the deployment

## Integration

To use the deployed proxy in your applications:

```python
# Example: Connect to the deployed MCP proxy
mcp_proxy_url = "https://[your-modal-url]"
fetch_endpoint = f"{mcp_proxy_url}/servers/fetch/sse"
memory_endpoint = f"{mcp_proxy_url}/servers/memory/sse"
search_endpoint = f"{mcp_proxy_url}/servers/search/sse"
``` 