#!/bin/bash

# Launch MCP servers via proxy
# Usage: ./launch_servers.sh [port]

PORT=${1:-18456}
HOST="127.0.0.1"
CONFIG_FILE="servers_config.json"

echo "Starting MCP proxy server on ${HOST}:${PORT}"
echo "Configuration: ${CONFIG_FILE}"
echo ""
echo "Available endpoints will be:"
echo "  Status: http://${HOST}:${PORT}/status"
echo "  Fetch:  http://${HOST}:${PORT}/servers/fetch/sse"
echo "  Memory: http://${HOST}:${PORT}/servers/memory/sse"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================="
echo "TODO: also launch invariantlabs-ai/mcp-streamable-http/python-example/server --> python weather.py --port 8123"

python -m mcp_proxy \
    --port="${PORT}" \
    --host="${HOST}" \
    --named-server-config="${CONFIG_FILE}" \
    --pass-environment \
    --allow-origin="*" \
    --debug
