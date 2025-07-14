"""
Modal deployment for agent responses.
"""

import os
from pathlib import Path

import modal

from ..config import AgentConfiguration
from ..http_app import create_app

# Define Modal image with dependencies
image = modal.Image.debian_slim().pip_install([
    "agent-responses",
    "a2a-sdk>=0.4.0",
    "openai>=1.14.0",
    "fastapi>=0.110.0",
    "httpx>=0.27.0",
])

# Create Modal app
app = modal.App("agent-responses", image=image)

# Load configuration (this would be updated for actual deployment)
config_path = os.getenv("AGENT_CONFIG", "agent.json")
if Path(config_path).exists():
    config = AgentConfiguration.from_file(config_path)
else:
    # Fallback minimal config for demo
    from ..config import MCPAgentCard, DeploymentConfig
    config = AgentConfiguration(
        card=MCPAgentCard(
            name="Demo Agent",
            description="Demo agent for Modal deployment"
        ),
        deployment=DeploymentConfig()
    )

# Create FastAPI app
fastapi_app = create_app(config)

# Deploy to Modal
@app.function()
@modal.asgi_app()
def web():
    """Modal ASGI app wrapper."""
    return fastapi_app


if __name__ == "__main__":
    # For local testing
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000) 