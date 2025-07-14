"""
Simplified configuration models leveraging a2a-sdk types.
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from a2a.types import AgentCard, AgentSkill
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables once at module import
load_dotenv()


class MCPSkill(AgentSkill):
    """MCP-specific skill configuration extending a2a AgentSkill."""
    server_label: str
    server_url: str
    require_approval: str = "auto"
    allowed_tools: Optional[List[str]] = None
    headers: Optional[Dict[str, str]] = None


class MCPAgentCard(AgentCard):
    """Agent card with MCP skills extending a2a AgentCard."""
    skills: List[MCPSkill] = []


class DeploymentConfig(BaseModel):
    """Simple deployment configuration."""
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_output_tokens: Optional[int] = 2048
    system_prompt: str = "You are a helpful AI assistant."
    
    # Modal-specific settings
    modal_cpu: float = 1.0
    modal_memory: int = 1024
    modal_timeout: int = 300


class AgentConfiguration(BaseModel):
    """Complete agent configuration."""
    card: MCPAgentCard
    deployment: DeploymentConfig = DeploymentConfig()
    
    @classmethod
    def from_file(cls, filepath: str) -> "AgentConfiguration":
        """Load configuration from JSON file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {filepath}")
        
        with open(path) as f:
            data = json.load(f)
        
        return cls(**data)
    
    def save_to_file(self, filepath: str) -> None:
        """Save configuration to JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            json.dump(self.model_dump(), f, indent=2) 