"""
Pytest fixtures for MCP proxy integration tests.
"""
import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator, AsyncGenerator

import pytest
import pytest_asyncio


# Path to the Rust binaries
REPO_ROOT = Path(__file__).parent.parent.parent
RELEASE_BIN = REPO_ROOT / "target" / "release"
MCP_PROXY_BIN = RELEASE_BIN / "mcp-proxy"
MCP_REVERSE_PROXY_BIN = RELEASE_BIN / "mcp-reverse-proxy"

# Path to the echo server
ECHO_SERVER = Path(__file__).parent / "echo_server.py"


def find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 10.0) -> bool:
    """Wait for a port to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except (socket.error, ConnectionRefusedError):
            time.sleep(0.1)
    return False


class ProxyServer:
    """Manages a running proxy server process."""

    def __init__(self, process: subprocess.Popen, port: int, host: str = "127.0.0.1"):
        self.process = process
        self.port = port
        self.host = host

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def sse_url(self) -> str:
        return f"{self.base_url}/sse"

    @property
    def messages_url(self) -> str:
        return f"{self.base_url}/messages"

    def stop(self):
        """Stop the server process."""
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


@pytest.fixture(scope="session")
def rust_binaries_built() -> bool:
    """Ensure Rust binaries are built."""
    if not MCP_PROXY_BIN.exists():
        pytest.skip(f"mcp-proxy binary not found at {MCP_PROXY_BIN}. Run 'cargo build --release' first.")
    return True


@pytest.fixture
def free_port() -> int:
    """Get a free port for testing."""
    return find_free_port()


@pytest.fixture
def echo_server_command() -> list[str]:
    """Command to run the echo server."""
    return [sys.executable, str(ECHO_SERVER), "--mode", "stdio"]


@pytest.fixture
def proxy_server(rust_binaries_built, free_port, echo_server_command) -> Generator[ProxyServer, None, None]:
    """
    Launch the Rust proxy server in reverse proxy mode (SSE->stdio).
    This exposes the echo server over HTTP/SSE.
    """
    port = free_port

    # Build the command - reverse proxy mode exposes a stdio server over HTTP
    # Use --command for the executable and --args=value for its arguments
    cmd = [
        str(MCP_REVERSE_PROXY_BIN),
        "--port", str(port),
        "--host", "127.0.0.1",
        "--command", echo_server_command[0],
        "--pass-environment",
    ]
    # Add each argument using --args=value format to avoid parsing issues
    for arg in echo_server_command[1:]:
        cmd.append(f"--args={arg}")

    env = os.environ.copy()
    env["RUST_LOG"] = "debug"

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    # Wait for the server to start
    if not wait_for_port(port, timeout=10.0):
        stdout, stderr = process.communicate(timeout=1)
        process.kill()
        pytest.fail(f"Proxy server failed to start on port {port}.\nstdout: {stdout}\nstderr: {stderr}")

    server = ProxyServer(process, port)
    yield server
    server.stop()


@pytest_asyncio.fixture
async def async_proxy_server(rust_binaries_built, echo_server_command) -> AsyncGenerator[ProxyServer, None]:
    """
    Async version of proxy_server fixture.
    """
    port = find_free_port()

    # Build the command with --command and --args=value format
    cmd = [
        str(MCP_REVERSE_PROXY_BIN),
        "--port", str(port),
        "--host", "127.0.0.1",
        "--command", echo_server_command[0],
        "--pass-environment",
    ]
    for arg in echo_server_command[1:]:
        cmd.append(f"--args={arg}")

    env = os.environ.copy()
    env["RUST_LOG"] = "debug"

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    # Wait for server to start
    for _ in range(100):  # 10 seconds max
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port),
                timeout=0.1
            )
            writer.close()
            await writer.wait_closed()
            break
        except (ConnectionRefusedError, asyncio.TimeoutError):
            await asyncio.sleep(0.1)
    else:
        process.kill()
        await process.wait()
        pytest.fail(f"Proxy server failed to start on port {port}")

    server = ProxyServer(process, port)
    yield server

    if process.returncode is None:
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()


@pytest.fixture
def stdio_proxy_server(rust_binaries_built, free_port) -> Generator[tuple[ProxyServer, subprocess.Popen], None, None]:
    """
    Launch the Rust proxy in client mode (stdio->SSE).
    First starts an SSE server, then connects to it via stdio proxy.
    """
    # This is more complex - we need:
    # 1. An SSE server running (we'll use the reverse proxy with echo server)
    # 2. The stdio proxy connecting to it

    sse_port = free_port
    echo_cmd = [sys.executable, str(ECHO_SERVER), "--mode", "stdio"]

    # Start the SSE server (reverse proxy mode)
    sse_cmd = [
        str(MCP_REVERSE_PROXY_BIN),
        "--port", str(sse_port),
        "--host", "127.0.0.1",
        "--command", echo_cmd[0],
        "--pass-environment",
    ]
    for arg in echo_cmd[1:]:
        sse_cmd.append(f"--args={arg}")

    env = os.environ.copy()
    env["RUST_LOG"] = "debug"

    sse_process = subprocess.Popen(
        sse_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    if not wait_for_port(sse_port, timeout=10.0):
        sse_process.kill()
        pytest.fail(f"SSE server failed to start on port {sse_port}")

    sse_server = ProxyServer(sse_process, sse_port)

    # Now start the stdio proxy that connects to the SSE server
    # URL is a positional argument, not a flag
    stdio_cmd = [
        str(MCP_PROXY_BIN),
        sse_server.sse_url,  # Positional URL argument
    ]

    stdio_process = subprocess.Popen(
        stdio_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    # Give it time to connect to SSE and receive endpoint event
    time.sleep(2.0)

    yield sse_server, stdio_process

    # Cleanup
    if stdio_process.poll() is None:
        stdio_process.terminate()
        try:
            stdio_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            stdio_process.kill()
            stdio_process.wait()

    sse_server.stop()
