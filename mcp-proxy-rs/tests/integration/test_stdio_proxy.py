"""
Integration tests for stdio proxy mode.
Tests the client mode where stdio is bridged to an SSE server.
"""
import asyncio
import json
import pytest
import subprocess
import sys
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).parent.parent.parent
MCP_PROXY_BIN = REPO_ROOT / "target" / "release" / "mcp-proxy"


pytestmark = pytest.mark.asyncio


class TestStdioToSSEBridge:
    """Tests for the stdio-to-SSE bridge mode."""

    async def test_stdio_proxy_initializes(self, stdio_proxy_server):
        """Test that the stdio proxy can initialize a connection."""
        sse_server, stdio_process = stdio_proxy_server

        # Send initialize request via stdin
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "stdio-test-client",
                    "version": "1.0.0"
                }
            }
        }

        request_line = json.dumps(init_request) + "\n"
        stdio_process.stdin.write(request_line.encode())
        stdio_process.stdin.flush()

        # Read response from stdout
        response_line = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, stdio_process.stdout.readline),
            timeout=10.0
        )

        response = json.loads(response_line.decode().strip())
        assert "result" in response
        assert response["id"] == 1
        assert response["result"]["protocolVersion"] == "2024-11-05"

    async def test_stdio_proxy_lists_tools(self, stdio_proxy_server):
        """Test listing tools through the stdio proxy."""
        sse_server, stdio_process = stdio_proxy_server

        # Initialize first
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        }
        stdio_process.stdin.write((json.dumps(init_request) + "\n").encode())
        stdio_process.stdin.flush()

        # Read init response
        await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, stdio_process.stdout.readline),
            timeout=10.0
        )

        # Send initialized notification
        stdio_process.stdin.write((json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }) + "\n").encode())
        stdio_process.stdin.flush()

        # List tools
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        stdio_process.stdin.write((json.dumps(tools_request) + "\n").encode())
        stdio_process.stdin.flush()

        # Read tools response
        response_line = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, stdio_process.stdout.readline),
            timeout=10.0
        )

        response = json.loads(response_line.decode().strip())
        assert "result" in response
        assert response["id"] == 2
        assert "tools" in response["result"]

        tool_names = [t["name"] for t in response["result"]["tools"]]
        assert "echo" in tool_names
        assert "add" in tool_names

    async def test_stdio_proxy_calls_tool(self, stdio_proxy_server):
        """Test calling a tool through the stdio proxy."""
        sse_server, stdio_process = stdio_proxy_server

        # Initialize
        stdio_process.stdin.write((json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        }) + "\n").encode())
        stdio_process.stdin.flush()

        await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, stdio_process.stdout.readline),
            timeout=10.0
        )

        # Call echo tool
        echo_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "echo",
                "arguments": {"message": "Hello from stdio!"}
            }
        }
        stdio_process.stdin.write((json.dumps(echo_request) + "\n").encode())
        stdio_process.stdin.flush()

        # Read response
        response_line = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, stdio_process.stdout.readline),
            timeout=10.0
        )

        response = json.loads(response_line.decode().strip())
        assert "result" in response
        assert response["id"] == 2
        content = response["result"]["content"]
        assert "Hello from stdio!" in content[0]["text"]


class TestStdioProxyErrorHandling:
    """Tests for error handling in stdio proxy mode."""

    async def test_stdio_proxy_handles_unknown_method(self, stdio_proxy_server):
        """Test that unknown methods return errors."""
        sse_server, stdio_process = stdio_proxy_server

        # Initialize first
        stdio_process.stdin.write((json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        }) + "\n").encode())
        stdio_process.stdin.flush()

        await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, stdio_process.stdout.readline),
            timeout=10.0
        )

        # Send unknown method
        unknown_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "unknown/method"
        }
        stdio_process.stdin.write((json.dumps(unknown_request) + "\n").encode())
        stdio_process.stdin.flush()

        # Read error response
        response_line = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, stdio_process.stdout.readline),
            timeout=10.0
        )

        response = json.loads(response_line.decode().strip())
        assert "error" in response
        assert response["id"] == 2
        assert response["error"]["code"] == -32601


class TestDirectStdioServer:
    """Tests for direct communication with the echo server (no proxy)."""

    async def test_echo_server_directly(self, echo_server_command):
        """Test the echo server works directly over stdio."""
        process = await asyncio.create_subprocess_exec(
            *echo_server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            # Send initialize
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                }
            }
            process.stdin.write((json.dumps(init_request) + "\n").encode())
            await process.stdin.drain()

            # Read response
            response_line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
            response = json.loads(response_line.decode().strip())

            assert "result" in response
            assert response["result"]["serverInfo"]["name"] == "echo-test-server"

        finally:
            process.terminate()
            await process.wait()

    async def test_echo_server_tool_call(self, echo_server_command):
        """Test calling tools on the echo server directly."""
        process = await asyncio.create_subprocess_exec(
            *echo_server_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            # Initialize
            process.stdin.write((json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                }
            }) + "\n").encode())
            await process.stdin.drain()
            await asyncio.wait_for(process.stdout.readline(), timeout=5.0)

            # Call add tool
            process.stdin.write((json.dumps({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "add",
                    "arguments": {"a": 100, "b": 23}
                }
            }) + "\n").encode())
            await process.stdin.drain()

            response_line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
            response = json.loads(response_line.decode().strip())

            assert response["result"]["content"][0]["text"] == "123"

        finally:
            process.terminate()
            await process.wait()
