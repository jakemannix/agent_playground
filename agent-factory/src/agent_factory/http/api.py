from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..config import AgentConfiguration
from ..core.runner import AgentRunner

import logging
from contextlib import asynccontextmanager

__all__ = ["build_app", "MessageRequest", "ChatRequest"]

logger = logging.getLogger(__name__)


class MessageRequest(BaseModel):
    """Schema for /invoke body."""

    message: str
    kwargs: Dict[str, Any] = {}


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


def build_app(runner: AgentRunner) -> FastAPI:
    """Build FastAPI app with the given runner."""
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage app lifecycle."""
        try:
            # Initialize agent on startup
            agent = await runner.get_agent()
            config = runner.get_config()
            logger.info(f"Agent '{config.agent_card.name}' initialized successfully")
            
            # Check for degraded functionality
            expected_skills = len(config.agent_card.skills)
            actual_tools = await runner.get_tool_count()
            
            if expected_skills > actual_tools:
                logger.warning(
                    f"Agent running with degraded functionality: "
                    f"{actual_tools}/{expected_skills} skills available"
                )
            
            yield
        except RuntimeError as e:
            # Tool initialization failed
            logger.error(f"Failed to initialize agent: {e}")
            raise RuntimeError(f"Agent initialization failed: {e}")
        finally:
            logger.info("Agent shutdown")
    
    config = runner.get_config()
    app = FastAPI(
        title=f"Agent: {config.agent_card.name}",
        description=config.agent_card.description,
        lifespan=lifespan
    )

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.post("/invoke")
    async def invoke(req: MessageRequest):
        result = await runner.invoke(req.message, **req.kwargs)
        return {"success": True, "result": result}

    @app.get("/config")
    async def config():
        """Get the full agent configuration."""
        return runner.get_config().model_dump()

    @app.get("/.well-known/agent.json")
    async def agent_card():
        """Get A2A-compatible agent card with updated schemas."""
        return await runner.get_agent_card()

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        try:
            config = runner.get_config()
            tool_count = await runner.get_tool_count()
            skill_count = len(config.agent_card.skills)
            
            health_status = {
                "status": "healthy" if tool_count == skill_count else "degraded",
                "agent_name": config.agent_card.name,
                "tools_available": tool_count,
                "skills_configured": skill_count
            }
            
            if tool_count < skill_count:
                health_status["warning"] = f"Only {tool_count} of {skill_count} configured skills are available"
            
            return health_status
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "error": str(e)}
            )

    @app.post("/chat")
    async def chat(request: ChatRequest):
        """Chat endpoint."""
        result = await runner.invoke(request.message, thread_id=request.thread_id)
        return {"response": result["messages"][-1].content}

    return app 