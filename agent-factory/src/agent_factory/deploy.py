"""
Modal Deployment

Deploy agents to Modal serverless infrastructure.
"""

import logging
import os
from typing import Any, Dict

import modal
from fastapi import FastAPI
from pydantic import BaseModel

from .config import AgentConfig
from .harness import AgentHarness

logger = logging.getLogger(__name__)

# Modal app for agent deployment
app = modal.App("agent-factory")

# Base image with dependencies
image = (
    modal.Image.debian_slim()
    .pip_install([
        "langgraph>=0.2.0",
        "langchain-anthropic>=0.1.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "mcp>=1.0.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.20.0",
    ])
    .env({"PYTHONPATH": "/root"})
)


class MessageRequest(BaseModel):
    """Request model for agent invocation."""

    message: str
    kwargs: Dict[str, Any] = {}


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-api-key")],
    timeout=300,
)
async def create_agent_function(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Create and initialize an agent from configuration."""
    config = AgentConfig(**config_dict)
    harness = AgentHarness(config)
    await harness.initialize()
    return harness.get_config_summary()


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("anthropic-api-key")],
    keep_warm=1,
    timeout=60,
)
async def agent_invoke(config_dict: Dict[str, Any], message: str, **kwargs) -> Dict[str, Any]:
    """Invoke an agent with a message."""
    config = AgentConfig(**config_dict)
    harness = AgentHarness(config)
    await harness.initialize()

    result = await harness.invoke(message, **kwargs)
    return result


def create_agent_api(config_dict: Dict[str, Any]) -> FastAPI:
    """Create a FastAPI app for the agent."""
    api = FastAPI(
        title=f"Agent: {config_dict.get('name', 'Unknown')}",
        description=config_dict.get("description", "AI Agent API"),
    )

    @api.post("/invoke")
    async def invoke_agent(request: MessageRequest) -> Dict[str, Any]:
        """Invoke the agent with a message."""
        try:
            result = await agent_invoke.remote.aio(config_dict, request.message, **request.kwargs)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Agent invocation failed: {e}")
            return {"success": False, "error": str(e)}

    @api.get("/health")
    async def health() -> Dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy"}

    @api.get("/config")
    async def get_config() -> Dict[str, Any]:
        """Get agent configuration summary."""
        try:
            summary = await create_agent_function.remote.aio(config_dict)
            return {"success": True, "config": summary}
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            return {"success": False, "error": str(e)}

    @api.get("/.well-known/agent.json")
    async def get_agent_card() -> Dict[str, Any]:
        """Get A2A-compatible agent card for discovery."""
        try:
            config = AgentConfig(**config_dict)
            agent_card = config.to_agent_card()
            return agent_card.model_dump()
        except Exception as e:
            logger.error(f"Failed to generate agent card: {e}")
            return {"error": "Failed to generate agent card"}

    return api


async def deploy_agent(config: AgentConfig, name: str | None = None) -> str:
    """Deploy an agent to Modal and return the endpoint URL."""

    if not name:
        name = config.name.lower().replace(" ", "-").replace("_", "-")

    logger.info(f"Deploying agent '{config.name}' as '{name}'")

    # Validate Modal secrets exist
    required_secrets = config.modal_config.secrets
    for secret in required_secrets:
        if not _check_modal_secret(secret):
            logger.warning(f"Modal secret '{secret}' may not exist")

    # Create the FastAPI app with the specific config
    agent_api = create_agent_api(config.model_dump())

    # Deploy using Modal's ASGI decorator
    @app.function(
        image=image,
        secrets=[modal.Secret.from_name(secret) for secret in required_secrets],
        keep_warm=config.modal_config.keep_warm,
        timeout=config.modal_config.timeout,
        cpu=config.modal_config.cpu,
        memory=config.modal_config.memory,
    )
    @modal.asgi_app()
    def deployed_agent():
        return agent_api

    # Deploy and get URL
    with app.run():
        url = deployed_agent.web_url
        logger.info(f"Agent '{config.name}' deployed to: {url}")
        return url


def deploy_from_config_file(config_path: str, name: str | None = None) -> str:
    """Deploy an agent from a configuration file."""
    config = AgentConfig.from_file(config_path)
    return deploy_agent(config, name)


def _check_modal_secret(secret_name: str) -> bool:
    """Check if a Modal secret exists (basic validation)."""
    try:
        # This is a simplified check - in practice you'd use Modal's API
        return True
    except Exception:
        return False


# CLI deployment function
def main() -> None:
    """CLI entry point for deployment."""
    import argparse

    parser = argparse.ArgumentParser(description="Deploy an agent to Modal")
    parser.add_argument("config", help="Path to agent configuration file")
    parser.add_argument("--name", help="Deployment name (optional)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    try:
        url = deploy_from_config_file(args.config, args.name)
        print(f"✅ Agent deployed successfully!")
        print(f"🌐 URL: {url}")
        print(f"📋 Health check: {url}/health")
        print(f"⚙️  Config: {url}/config")
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()