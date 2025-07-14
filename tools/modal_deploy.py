"""
Modal deployment for MCP proxy servers.
Surgical fix: runs mcp-proxy as-is, but properly exposes it via ASGI.

Deploy with:
    modal serve tools/modal_deploy.py

Connect to:
    https://[your-modal-url]/status
    https://[your-modal-url]/servers/fetch/sse
"""

import os
import sys
import threading
import time
import subprocess
from pathlib import Path

import modal

# Create the Modal app
app = modal.App("mcp-proxy")

# Build image with all necessary dependencies
image = (
    modal.Image.debian_slim()
    .pip_install(["uv", "fastapi[standard]", "httpx"])
    .run_commands("uv venv /opt/venv")
    .run_commands("uv pip install --python /opt/venv/bin/python mcp-proxy")
    .apt_install(["nodejs", "npm", "curl"])
    .add_local_file("servers_config.json", "/app/servers_config.json")
)

# No volume mounting needed - config file is copied into image


@app.function(
    image=image,
    timeout=3600,  # 1 hour timeout for long-running server
    cpu=1.0,
    memory=1024,
    allow_concurrent_inputs=100,
)
@modal.asgi_app()
def mcp_proxy_asgi():
    """
    Run mcp-proxy in background and expose it via ASGI.
    This is the surgical fix that keeps mcp-proxy unchanged.
    """
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse, Response
    import httpx
    
    # Configuration
    mcp_port = 18456
    mcp_host = "127.0.0.1"  # Local only, we proxy through ASGI
    config_file = "/app/servers_config.json"
    
    print(f"🚀 Starting MCP proxy on {mcp_host}:{mcp_port}")
    print(f"📋 Config: {config_file}")
    
    # Start mcp-proxy in background thread - exactly as before
    def start_mcp_proxy():
        cmd = [
            "/opt/venv/bin/python", "-m", "mcp_proxy",
            f"--port={mcp_port}",
            f"--host={mcp_host}",
            f"--named-server-config={config_file}",
            "--pass-environment",
            "--allow-origin=*",
            "--debug"
        ]
        
        print(f"🔧 Command: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=False)
        except Exception as e:
            print(f"❌ MCP proxy failed: {e}")
    
    # Start mcp-proxy in daemon thread
    proxy_thread = threading.Thread(target=start_mcp_proxy, daemon=True)
    proxy_thread.start()
    
    # Wait for mcp-proxy to start
    print("⏳ Waiting for mcp-proxy to start...")
    time.sleep(5)
    
    # Create FastAPI app to proxy requests
    app = FastAPI(title="MCP Proxy Gateway")
    
    @app.get("/")
    async def root():
        return {
            "service": "MCP Proxy Gateway",
            "status": "running",
            "endpoints": {
                "status": "/status",
                "fetch": "/servers/fetch/sse",
                "memory": "/servers/memory/sse",
                "search": "/servers/search/sse"
            }
        }
    
    # Universal proxy handler for all paths
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
    async def proxy_to_mcp(path: str, request: Request):
        """Proxy all requests to mcp-proxy, preserving SSE streams."""
        target_url = f"http://{mcp_host}:{mcp_port}/{path}"
        
        # Forward query parameters
        if request.url.query:
            target_url += f"?{request.url.query}"
        
        # Get request body
        body = await request.body()
        
        # Forward headers (exclude host)
        headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body
                )
                
                # Check if this is a Server-Sent Events response
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    # Stream SSE responses using Modal's streaming support
                    async def stream_sse():
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            yield chunk
                    
                    return StreamingResponse(
                        stream_sse(),
                        media_type="text/event-stream",
                        headers={k: v for k, v in response.headers.items() 
                                if k.lower() not in ["content-length", "transfer-encoding"]}
                    )
                
                # Handle regular responses
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers={k: v for k, v in response.headers.items() 
                            if k.lower() not in ["content-length", "transfer-encoding"]}
                )
                
            except httpx.TimeoutException:
                return Response("Gateway timeout", status_code=504)
            except httpx.ConnectError:
                return Response("MCP proxy not available", status_code=502)
            except Exception as e:
                print(f"❌ Proxy error: {e}")
                return Response(f"Proxy error: {str(e)}", status_code=502)
    
    return app


@app.function(image=image)
def test_dependencies():
    """Test that all required dependencies are available."""
    import subprocess
    import sys
    
    print("🧪 Testing dependencies...")
    
    # Test Python dependencies
    try:
        result = subprocess.run(["/opt/venv/bin/python", "-c", "import mcp_proxy"], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ mcp-proxy is available in venv")
        else:
            print("❌ mcp-proxy not found in venv")
            return False
    except FileNotFoundError:
        print("❌ venv python not found")
        return False
    
    # Test Node.js and npm
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        print(f"✅ Node.js: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ Node.js not found")
        return False
    
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        print(f"✅ npm: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ npm not found")
        return False
    
    # Test uv
    try:
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        print(f"✅ uv: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ uv not found")
        return False
    
    # Test config file
    if os.path.exists("/app/servers_config.json"):
        print("✅ servers_config.json found")
    else:
        print("❌ servers_config.json not found")
        return False
    
    print("🎉 All dependencies are available!")
    return True


@app.local_entrypoint()
def main():
    """Local entrypoint for testing and development."""
    print("🔧 MCP Proxy Surgical Fix - Modal Deployment")
    print("=" * 50)
    
    print("🧪 Testing dependencies first...")
    if test_dependencies.remote():
        print("\n" + "✅" + " Dependencies OK!")
        print("\n📋 Deployment Instructions:")
        print("1. Deploy: modal serve tools/modal_deploy.py")
        print("2. Your MCP proxy will be available at: https://[your-modal-url]")
        print("\n🌐 Available endpoints:")
        print("  Root:   https://[your-modal-url]/")
        print("  Status: https://[your-modal-url]/status")
        print("  Fetch:  https://[your-modal-url]/servers/fetch/sse")
        print("  Memory: https://[your-modal-url]/servers/memory/sse")
        print("  Search: https://[your-modal-url]/servers/search/sse")
        print("\n🎯 What this does:")
        print("  • Runs your existing mcp-proxy unchanged")
        print("  • Exposes it properly via Modal ASGI")
        print("  • Preserves SSE streaming for MCP protocol")
        print("  • Surgical fix - minimal changes!")
    else:
        print("❌ Dependency test failed!")


if __name__ == "__main__":
    main() 