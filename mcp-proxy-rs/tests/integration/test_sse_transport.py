"""
Integration tests for SSE transport.
Tests the reverse proxy mode where a stdio MCP server is exposed over HTTP/SSE.
"""
import asyncio
import json
import pytest
import httpx
from httpx_sse import aconnect_sse


pytestmark = pytest.mark.asyncio


class TestSSEConnection:
    """Tests for basic SSE connection and message flow."""

    async def test_sse_endpoint_connects(self, async_proxy_server):
        """Test that we can connect to the SSE endpoint."""
        async with httpx.AsyncClient() as client:
            async with aconnect_sse(client, "GET", async_proxy_server.sse_url) as event_source:
                async for event in event_source.aiter_sse():
                    assert event.event == "endpoint"
                    assert event.data.startswith("/messages")
                    break  # Just check first event

    async def test_sse_returns_message_endpoint(self, async_proxy_server):
        """Test that SSE connection returns the message endpoint URI."""
        async with httpx.AsyncClient() as client:
            async with aconnect_sse(client, "GET", async_proxy_server.sse_url) as event_source:
                async for event in event_source.aiter_sse():
                    assert event.data.startswith("/messages")
                    assert "session_id=" in event.data
                    break


class TestMCPProtocol:
    """Tests for MCP protocol messages over SSE."""

    async def test_initialize_request(self, async_proxy_server):
        """Test sending an initialize request and receiving a response."""
        async with httpx.AsyncClient(base_url=async_proxy_server.base_url, timeout=30.0) as client:
            async with aconnect_sse(client, "GET", "/sse") as event_source:
                message_uri = None
                init_response_received = False

                async for event in event_source.aiter_sse():
                    if event.event == "endpoint":
                        message_uri = event.data
                        # Send initialize request
                        init_request = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {
                                    "name": "test-client",
                                    "version": "1.0.0"
                                }
                            }
                        }
                        response = await client.post(message_uri, json=init_request)
                        assert response.status_code in (200, 202)

                    elif event.event == "message":
                        message = json.loads(event.data)
                        if message.get("id") == 1:
                            assert "result" in message
                            assert message["result"]["protocolVersion"] == "2024-11-05"
                            assert "serverInfo" in message["result"]
                            init_response_received = True
                            break

                assert init_response_received, "Did not receive initialize response"

    async def test_tools_list(self, async_proxy_server):
        """Test listing available tools."""
        async with httpx.AsyncClient(base_url=async_proxy_server.base_url, timeout=30.0) as client:
            async with aconnect_sse(client, "GET", "/sse") as event_source:
                message_uri = None
                initialized = False
                tools_received = False

                async for event in event_source.aiter_sse():
                    if event.event == "endpoint":
                        message_uri = event.data
                        # Initialize
                        await client.post(message_uri, json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {"name": "test", "version": "1.0"}
                            }
                        })

                    elif event.event == "message":
                        msg = json.loads(event.data)
                        if msg.get("id") == 1 and not initialized:
                            initialized = True
                            # Send initialized notification
                            await client.post(message_uri, json={
                                "jsonrpc": "2.0",
                                "method": "notifications/initialized"
                            })
                            # List tools
                            await client.post(message_uri, json={
                                "jsonrpc": "2.0",
                                "id": 2,
                                "method": "tools/list"
                            })

                        elif msg.get("id") == 2:
                            assert "result" in msg
                            assert "tools" in msg["result"]
                            tools = msg["result"]["tools"]
                            tool_names = [t["name"] for t in tools]
                            assert "echo" in tool_names
                            assert "add" in tool_names
                            tools_received = True
                            break

                assert tools_received, "Did not receive tools/list response"

    async def test_tool_call_echo(self, async_proxy_server):
        """Test calling the echo tool."""
        async with httpx.AsyncClient(base_url=async_proxy_server.base_url, timeout=30.0) as client:
            async with aconnect_sse(client, "GET", "/sse") as event_source:
                message_uri = None
                initialized = False
                echo_received = False

                async for event in event_source.aiter_sse():
                    if event.event == "endpoint":
                        message_uri = event.data
                        await client.post(message_uri, json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {"name": "test", "version": "1.0"}
                            }
                        })

                    elif event.event == "message":
                        msg = json.loads(event.data)
                        if msg.get("id") == 1 and not initialized:
                            initialized = True
                            # Call echo tool
                            await client.post(message_uri, json={
                                "jsonrpc": "2.0",
                                "id": 2,
                                "method": "tools/call",
                                "params": {
                                    "name": "echo",
                                    "arguments": {"message": "Hello, MCP!"}
                                }
                            })

                        elif msg.get("id") == 2:
                            assert "result" in msg
                            content = msg["result"]["content"]
                            assert len(content) > 0
                            assert content[0]["type"] == "text"
                            assert "Hello, MCP!" in content[0]["text"]
                            echo_received = True
                            break

                assert echo_received, "Did not receive echo tool response"

    async def test_tool_call_add(self, async_proxy_server):
        """Test calling the add tool."""
        async with httpx.AsyncClient(base_url=async_proxy_server.base_url, timeout=30.0) as client:
            async with aconnect_sse(client, "GET", "/sse") as event_source:
                message_uri = None
                initialized = False
                add_received = False

                async for event in event_source.aiter_sse():
                    if event.event == "endpoint":
                        message_uri = event.data
                        await client.post(message_uri, json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {"name": "test", "version": "1.0"}
                            }
                        })

                    elif event.event == "message":
                        msg = json.loads(event.data)
                        if msg.get("id") == 1 and not initialized:
                            initialized = True
                            await client.post(message_uri, json={
                                "jsonrpc": "2.0",
                                "id": 2,
                                "method": "tools/call",
                                "params": {
                                    "name": "add",
                                    "arguments": {"a": 17, "b": 25}
                                }
                            })

                        elif msg.get("id") == 2:
                            assert "result" in msg
                            content = msg["result"]["content"]
                            assert content[0]["text"] == "42"
                            add_received = True
                            break

                assert add_received, "Did not receive add tool response"


class TestErrorHandling:
    """Tests for error handling."""

    async def test_invalid_json_returns_error(self, async_proxy_server):
        """Test that invalid JSON returns an appropriate error."""
        async with httpx.AsyncClient(base_url=async_proxy_server.base_url, timeout=30.0) as client:
            async with aconnect_sse(client, "GET", "/sse") as event_source:
                async for event in event_source.aiter_sse():
                    if event.event == "endpoint":
                        message_uri = event.data
                        response = await client.post(
                            message_uri,
                            content="not valid json",
                            headers={"Content-Type": "application/json"}
                        )
                        # Should get an error response
                        assert response.status_code in (200, 400, 422)
                        break

    async def test_unknown_method_returns_error(self, async_proxy_server):
        """Test that an unknown method returns an error."""
        async with httpx.AsyncClient(base_url=async_proxy_server.base_url, timeout=30.0) as client:
            async with aconnect_sse(client, "GET", "/sse") as event_source:
                message_uri = None
                initialized = False
                error_received = False

                async for event in event_source.aiter_sse():
                    if event.event == "endpoint":
                        message_uri = event.data
                        await client.post(message_uri, json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {"name": "test", "version": "1.0"}
                            }
                        })

                    elif event.event == "message":
                        msg = json.loads(event.data)
                        if msg.get("id") == 1 and not initialized:
                            initialized = True
                            await client.post(message_uri, json={
                                "jsonrpc": "2.0",
                                "id": 2,
                                "method": "unknown/method"
                            })

                        elif msg.get("id") == 2:
                            assert "error" in msg
                            assert msg["error"]["code"] == -32601
                            error_received = True
                            break

                assert error_received, "Did not receive error response"
