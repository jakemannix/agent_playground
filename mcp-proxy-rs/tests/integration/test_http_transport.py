"""
Integration tests for HTTP transport (non-SSE endpoints).
Tests the REST-like HTTP endpoints of the proxy.
"""
import json
import pytest
import httpx


pytestmark = pytest.mark.asyncio


class TestHealthEndpoints:
    """Tests for health check and status endpoints."""

    async def test_root_endpoint(self, async_proxy_server):
        """Test that the root endpoint returns something."""
        async with httpx.AsyncClient() as client:
            response = await client.get(async_proxy_server.base_url)
            # Could be 200, 404, or redirect - just shouldn't error
            assert response.status_code in (200, 301, 302, 404)

    async def test_messages_endpoint_requires_session(self, async_proxy_server):
        """Test that POST to messages without a session is handled."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{async_proxy_server.base_url}/messages",
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"}
            )
            # Proxy accepts messages (202) or may require session (400/404/422)
            assert response.status_code in (200, 202, 400, 404, 422)


class TestHTTPMessageFlow:
    """Tests for HTTP message request/response flow."""

    async def test_post_message_returns_response(self, async_proxy_server):
        """Test that POST messages return responses (if supported)."""
        async with httpx.AsyncClient(base_url=async_proxy_server.base_url) as client:
            # First establish SSE connection to get session
            from httpx_sse import aconnect_sse
            import asyncio

            async with aconnect_sse(client, "GET", "/sse") as event_source:
                event = await asyncio.wait_for(event_source.aiter_sse().__anext__(), timeout=5.0)
                message_uri = event.data

                # Test that we can POST and get acknowledgment
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

                response = await client.post(message_uri, json=init_request)
                # Should accept the message
                assert response.status_code in (200, 202, 204)


class TestConcurrentRequests:
    """Tests for handling concurrent HTTP requests."""

    async def test_multiple_concurrent_posts(self, async_proxy_server):
        """Test handling multiple concurrent POST requests."""
        import asyncio
        from httpx_sse import aconnect_sse

        async with httpx.AsyncClient(base_url=async_proxy_server.base_url) as client:
            async with aconnect_sse(client, "GET", "/sse") as event_source:
                # Create a single iterator and reuse it (SSE streams can only be consumed once)
                sse_iter = event_source.aiter_sse()

                event = await asyncio.wait_for(sse_iter.__anext__(), timeout=5.0)
                message_uri = event.data

                # Initialize first
                await client.post(message_uri, json={
                    "jsonrpc": "2.0",
                    "id": 0,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1.0"}
                    }
                })

                # Wait for init response (reuse same iterator)
                async for sse_event in sse_iter:
                    if sse_event.event == "message":
                        msg = json.loads(sse_event.data)
                        if msg.get("id") == 0:
                            break

                # Send multiple tool calls concurrently
                async def send_add_request(req_id: int, a: int, b: int):
                    return await client.post(message_uri, json={
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "method": "tools/call",
                        "params": {
                            "name": "add",
                            "arguments": {"a": a, "b": b}
                        }
                    })

                # Send 5 concurrent requests
                tasks = [
                    send_add_request(i, i * 10, i)
                    for i in range(1, 6)
                ]
                responses = await asyncio.gather(*tasks)

                # All should be accepted
                for resp in responses:
                    assert resp.status_code in (200, 202, 204)

                # Collect all responses from SSE (reuse same iterator)
                received_ids = set()
                expected_ids = {1, 2, 3, 4, 5}

                async for sse_event in sse_iter:
                    if sse_event.event == "message":
                        msg = json.loads(sse_event.data)
                        msg_id = msg.get("id")
                        if msg_id in expected_ids:
                            received_ids.add(msg_id)
                            assert "result" in msg
                            if received_ids == expected_ids:
                                break

                assert received_ids == expected_ids


class TestContentTypes:
    """Tests for different content type handling."""

    async def test_json_content_type(self, async_proxy_server):
        """Test that application/json content type is accepted."""
        from httpx_sse import aconnect_sse
        import asyncio

        async with httpx.AsyncClient(base_url=async_proxy_server.base_url) as client:
            async with aconnect_sse(client, "GET", "/sse") as event_source:
                event = await asyncio.wait_for(event_source.aiter_sse().__anext__(), timeout=5.0)
                message_uri = event.data

                response = await client.post(
                    message_uri,
                    content=json.dumps({
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1.0"}
                        }
                    }),
                    headers={"Content-Type": "application/json"}
                )
                assert response.status_code in (200, 202, 204)

    async def test_wrong_content_type_handled(self, async_proxy_server):
        """Test that wrong content types are handled gracefully."""
        from httpx_sse import aconnect_sse
        import asyncio

        async with httpx.AsyncClient(base_url=async_proxy_server.base_url) as client:
            async with aconnect_sse(client, "GET", "/sse") as event_source:
                event = await asyncio.wait_for(event_source.aiter_sse().__anext__(), timeout=5.0)
                message_uri = event.data

                response = await client.post(
                    message_uri,
                    content="plain text content",
                    headers={"Content-Type": "text/plain"}
                )
                # Should either reject or handle gracefully
                assert response.status_code in (200, 400, 415, 422)
