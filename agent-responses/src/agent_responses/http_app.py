"""
Simplified FastAPI application for agent responses.
"""

import json
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .runner import Runner
from .config import AgentConfiguration

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    stream: bool = False


def create_app(config: AgentConfiguration) -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title=config.card.name,
        description=config.card.description,
        version=getattr(config.card, 'version', '1.0.0')
    )
    
    runner = Runner(config)
    
    @app.get("/.well-known/agent.json")
    async def agent_json():
        """Serve agent card as JSON."""
        return config.card.model_dump()
    
    @app.post("/chat")
    async def chat(request: ChatRequest):
        """Chat with the agent."""
        try:
            if request.stream:
                # Streaming response
                async def generate():
                    async for chunk in runner.stream(request.message):
                        yield f"data: {json.dumps(chunk)}\n\n"
                
                return StreamingResponse(
                    generate(),
                    media_type="text/event-stream"
                )
            else:
                # Non-streaming response
                result = await runner.invoke(request.message)
                
                # Extract response content from OpenAI Responses API structure
                response_text = ""
                
                if "output" in result and len(result["output"]) > 0:
                    # OpenAI Responses API structure
                    output = result["output"][0]
                    if "content" in output and len(output["content"]) > 0:
                        content = output["content"][0]
                        if content.get("type") == "output_text":
                            response_text = content.get("text", "")
                
                # If no response found, show debug info
                if not response_text:
                    response_text = f"No response found in: {json.dumps(result, indent=2)}"
                
                return {
                    "response": response_text,
                    "conversation_id": runner.conversation_id,
                    "usage": result.get("usage")
                }
                
        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    return app 