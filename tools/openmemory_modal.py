# py ≥3.10
from __future__ import annotations

import modal
import subprocess
import time
from typing import Final

app = modal.App("openmemory-stack")

# ---------- Persistent Qdrant store ----------
QDRANT_PORT: Final[int] = 6333
qdrant_data = modal.Volume.from_name(
    "openmemory-qdrant-data", create_if_missing=True
)

qdrant_image = (
    modal.Image.from_registry("qdrant/qdrant:latest", add_python="3.11")  # has cli tools
    .entrypoint("[]")
)


@app.function(
    image=qdrant_image,
    volumes={"/qdrant/storage": qdrant_data},
    i6pn=True,
    timeout=0,
)
@modal.web_server(QDRANT_PORT)
def qdrant_server() -> None:
    """Launch Qdrant and keep container alive."""
    subprocess.Popen(
        f"qdrant --storage-path /qdrant/storage "
        f"--port {QDRANT_PORT} --host 0.0.0.0",
        shell=True,
    )
    # Keep the Python process alive so Modal doesn’t exit.
    while True:
        time.sleep(3600)


# ---------- OpenMemory MCP API ----------
MCP_PORT: Final[int] = 8765

mcp_image = (
    modal.Image.from_registry(
        "mem0/openmemory-mcp:latest", add_python="3.11"
    )
    .env({"QDRANT_URL": f"http://{qdrant_server.internal_ip}:{QDRANT_PORT}"})
)  # internal_ip available because both funcs have i6pn=True


@app.function(image=mcp_image, i6pn=True, timeout=0)
@modal.web_server(MCP_PORT)
def openmemory_mcp() -> None:
    cmd = (
        "uvicorn main:app --host 0.0.0.0 "
        f"--port {MCP_PORT} --workers 4 --reload"
    )
    subprocess.Popen(cmd, shell=True)
    while True:
        time.sleep(3600)


# ---------- Next.js UI ----------
UI_PORT: Final[int] = 3000
import os
ui_image = (
    modal.from_registry("mem0/openmemory-ui:latest")
    .env(
        {
            "NEXT_PUBLIC_API_URL": openmemory_mcp.web_url,  # Modal resolves at deploy
            "NEXT_PUBLIC_USER_ID": os.environ['USER']
        }
    )
)

@app.function(image=ui_image, timeout=0)
@modal.web_server(UI_PORT)
def openmemory_ui() -> None:
    subprocess.Popen("node server.js", shell=True)  # whatever start-cmd your Dockerfile uses
    while True:
        time.sleep(3600)

