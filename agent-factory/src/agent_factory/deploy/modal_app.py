from __future__ import annotations

"""Modal deployment entry-point.

Run locally with:
    modal run agent_factory/deploy/modal_app.py --env AGENT_CFG_PATH=examples/configs/basic-example.json

Deploy with:
    modal serve agent_factory/deploy/modal_app.py --env AGENT_CFG_PATH=/path/in/container/config.json
"""

import os
from typing import Any, Dict

import modal
from fastapi import FastAPI

app = modal.App("agent-factory")

# ---------------------------------------------------------------------------
# Base image (identical dependency list to existing deploy.py for now)
# ---------------------------------------------------------------------------
image = (
    modal.Image.debian_slim()
    .pip_install(
        [
            "langgraph>=0.2.0",
            "langchain-anthropic>=0.1.0",
            "langchain-mcp-adapters>=0.1.0",
            "pydantic>=2.0.0",
            "python-dotenv>=1.0.0",
            "a2a>=0.2.0",
            "fastapi>=0.100.0",
            "uvicorn>=0.20.0",
        ]
    )
    .env({"PYTHONPATH": "/root"})
)


# ----------------------------------------------------------------------------
# Remote helpers – thin wrappers around AgentRunner
# ----------------------------------------------------------------------------

@app.function(image=image, secrets=[modal.Secret.from_name("anthropic-api-key")], timeout=300)
async def remote_invoke(cfg_dict: Dict[str, Any], message: str, **kwargs):
    from agent_factory.config import AgentConfiguration
    from agent_factory.core.runner import AgentRunner
    
    cfg = AgentConfiguration(**cfg_dict)
    runner = AgentRunner(cfg)
    return await runner.invoke(message, **kwargs)


@app.function(image=image, secrets=[modal.Secret.from_name("anthropic-api-key")], timeout=300)
async def remote_cfg_summary(cfg_dict: Dict[str, Any]):
    from agent_factory.config import AgentConfiguration
    from agent_factory.core.runner import AgentRunner
    
    cfg = AgentConfiguration(**cfg_dict)
    runner = AgentRunner(cfg)
    agent = await runner.get_agent()
    return {
        "name": cfg.agent_card.name,
        "skills": len(cfg.agent_card.skills),
        "tools_loaded": len(agent.harness.get_tool_names())
    }


# ----------------------------------------------------------------------------
# ASGI application – created once per container
# ----------------------------------------------------------------------------

# Load configuration at module level to determine Modal settings
if "AGENT_CFG_PATH" in os.environ:
    from agent_factory.config import AgentConfiguration
    _config = AgentConfiguration.from_file(os.environ["AGENT_CFG_PATH"])
    config_info = _config.deployment.modal.model_dump()
    modal_secrets = [modal.Secret.from_name(s) for s in config_info.get("secrets", [])]
else:
    # Default settings when no config is available
    config_info = {"cpu": 1.0, "memory": 2048, "timeout": 300, "keep_warm": 0}
    modal_secrets = [modal.Secret.from_name("anthropic-api-key")]


@app.function(
    image=image,
    gpu=config_info.get("gpu", None),
    cpu=config_info.get("cpu", 1.0),
    memory=config_info.get("memory", 2048),
    timeout=config_info.get("timeout", 300),
    keep_warm=config_info.get("keep_warm", 0),
    secrets=modal_secrets,
)
@modal.asgi_app()
def fastapi_app():
    """Create the FastAPI app instance."""
    from agent_factory.config import AgentConfiguration
    from agent_factory.core.runner import AgentRunner
    from agent_factory.http.api import build_app
    
    # Load configuration
    config = AgentConfiguration.from_file(os.environ["AGENT_CFG_PATH"])
    
    # Create runner
    runner = AgentRunner(config)
    
    # Build and return app
    return build_app(runner)


# ----------------------------------------------------------------------------
# Local dev entry-point – hot-reloaded FastAPI on localhost:8000
# ----------------------------------------------------------------------------

@app.local_entrypoint()
def dev():
    import uvicorn
    from agent_factory.config import AgentConfiguration
    from agent_factory.core.runner import AgentRunner
    from agent_factory.http.api import build_app

    cfg_path = os.environ.get("AGENT_CFG_PATH")
    if not cfg_path:
        raise RuntimeError("AGENT_CFG_PATH must be set to a configuration JSON file")

    cfg = AgentConfiguration.from_file(cfg_path)
    runner = AgentRunner(cfg)

    # If running via `modal run` we can detect local mode
    if modal.is_local():
        print("🔄 Running in local mode (Modal stub)")
    else:
        print("☁️  Running in remote Modal container – forwarding port 8000")

    uvicorn.run(build_app(runner), host="0.0.0.0", port=8000, reload=True) 