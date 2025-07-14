"""
Simplified runner for OpenAI Responses API integration.
"""

import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

import httpx
from openai import AsyncOpenAI, OpenAI

from .config import AgentConfiguration, MCPSkill

logger = logging.getLogger(__name__)


class Runner:
    """Simplified agent runner using OpenAI Responses API."""
    
    def __init__(self, config: AgentConfiguration):
        """Initialize runner with configuration."""
        self.config = config
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.sync_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._conversation_id: Optional[str] = None
        self._previous_response_id: Optional[str] = None
        
    @property
    def conversation_id(self) -> str:
        """Get or create conversation ID."""
        if not self._conversation_id:
            self._conversation_id = str(uuid4())
        return self._conversation_id
    
    def reset_conversation(self) -> None:
        """Reset conversation state."""
        self._conversation_id = None
        self._previous_response_id = None
    
    async def invoke(self, message: str, approve_all: bool = False) -> Dict[str, Any]:
        """Send message and get response."""
        payload = self._build_payload(message, approve_all)
        
        headers = {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"}
        headers.update(self._get_mcp_headers())
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                json=payload,
                headers=headers,
                timeout=300.0
            )
            # response.raise_for_status()
            result = response.json()
            
            # Update conversation state
            if result.get("id"):
                self._previous_response_id = result["id"]
                
            return result
    
    async def stream(self, message: str, approve_all: bool = False) -> AsyncIterator[Dict[str, Any]]:
        """Stream response from agent."""
        payload = self._build_payload(message, approve_all)
        payload["stream"] = True
        
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Accept": "text/event-stream"
        }
        headers.update(self._get_mcp_headers())
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/responses",
                json=payload,
                headers=headers,
                timeout=300.0
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            yield chunk
                            
                            # Update state from final chunk
                            if chunk.get("event") == "response.done":
                                response_data = chunk.get("data", {})
                                if response_data.get("id"):
                                    self._previous_response_id = response_data["id"]
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse SSE data: {data}")
    
    def invoke_sync(self, message: str, approve_all: bool = False) -> Dict[str, Any]:
        """Synchronous version of invoke."""
        return asyncio.run(self.invoke(message, approve_all))
    
    def _build_payload(self, message: str, approve_all: bool = False) -> Dict[str, Any]:
        """Build request payload for Responses API."""
        payload = {
            "model": self.config.deployment.model,
            "temperature": self.config.deployment.temperature,
            "store": True,
            "max_output_tokens": self.config.deployment.max_output_tokens,
            "tools": self._build_tools(approve_all)
        }
        
        # Build input based on conversation state
        if self._previous_response_id:
            # Continue existing conversation
            payload["previous_response_id"] = self._previous_response_id
            payload["input"] = message
        else:
            # New conversation with system prompt
            payload["input"] = [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self.config.deployment.system_prompt
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": message
                        }
                    ]
                }
            ]
        
        return payload
    
    def _build_tools(self, approve_all: bool = False) -> List[Dict[str, Any]]:
        """Build tools list from MCP skills."""
        tools = []
        
        for skill in self.config.card.skills:
            tool = {
                "type": "mcp",
                "server_label": skill.server_label,
                "server_url": os.path.expandvars(skill.server_url),
                "require_approval": "never" if approve_all else skill.require_approval
            }
            
            if skill.allowed_tools:
                tool["allowed_tools"] = skill.allowed_tools
                
            tools.append(tool)
        
        return tools
    
    def _get_mcp_headers(self) -> Dict[str, str]:
        """Get MCP server headers."""
        headers = {}
        
        for skill in self.config.card.skills:
            if isinstance(skill, MCPSkill) and skill.headers:
                for key, value in skill.headers.items():
                    # Prefix headers with server label to avoid conflicts
                    header_key = f"X-MCP-{skill.server_label}-{key}"
                    headers[header_key] = os.path.expandvars(value)
        
        return headers 