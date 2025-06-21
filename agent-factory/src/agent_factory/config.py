"""
Agent Configuration

Defines the schema and validation for agent configuration, extending A2A AgentCard.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from a2a.types import AgentCard, AgentCapabilities, AgentProvider, AgentSkill
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator

# Load environment variables
load_dotenv()


class MCPToolConfig(BaseModel):
    """Configuration for an MCP tool/server."""

    name: str = Field(description="Tool name")
    server_path: str = Field(description="Path to MCP server module")
    config: Dict[str, Any] = Field(default_factory=dict, description="Tool-specific configuration")


class ModalConfig(BaseModel):
    """Modal deployment configuration."""

    cpu: Optional[float] = Field(default=1.0, description="CPU allocation")
    memory: Optional[int] = Field(default=2048, description="Memory allocation in MB")
    timeout: Optional[int] = Field(default=300, description="Function timeout in seconds")
    keep_warm: Optional[int] = Field(default=0, description="Number of containers to keep warm")
    secrets: List[str] = Field(
        default_factory=lambda: ["anthropic-api-key"], description="Modal secrets to attach"
    )


class AgentConfig(AgentCard):
    """
    Complete agent configuration extending A2A AgentCard.
    
    Combines A2A standard fields with deployment-specific configuration.
    """

    # LLM Configuration (extends A2A)
    model: str = Field(default="claude-3-5-sonnet-20241022", description="LLM model to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, gt=0, description="Maximum tokens per response")
    system_prompt: str = Field(description="System prompt defining agent behavior")

    # Agent Behavior
    agent_type: str = Field(default="react", description="Agent type: 'react' or 'supervisor'")

    # Tools (extends A2A skills)
    mcp_tools: List[MCPToolConfig] = Field(default_factory=list, description="MCP tools available to agent")

    # Deployment Configuration
    modal_config: ModalConfig = Field(default_factory=ModalConfig, description="Modal deployment configuration")

    # UI Configuration (optional)
    ui_config: Optional[Dict[str, Any]] = Field(default=None, description="FastHTML UI configuration")

    def __init__(self, **data):
        # Set default A2A fields if not provided
        if "capabilities" not in data:
            data["capabilities"] = AgentCapabilities(
                streaming=True,
                pushNotifications=False,
                stateTransitionHistory=True,
            )

        if "defaultInputModes" not in data:
            data["defaultInputModes"] = ["text/plain"]

        if "defaultOutputModes" not in data:
            data["defaultOutputModes"] = ["text/plain", "application/json"]

        if "skills" not in data:
            # Auto-generate skills from MCP tools
            mcp_tools = data.get("mcp_tools", [])
            data["skills"] = [
                AgentSkill(
                    id=f"mcp_{tool['name']}",
                    name=tool["name"],
                    description=f"MCP tool: {tool['name']}",
                    tags=["mcp", "tool"],
                    examples=[f"Use {tool['name']} to perform tasks"],
                )
                for tool in mcp_tools
            ]

        if "version" not in data:
            data["version"] = "1.0.0"

        super().__init__(**data)

    @validator("agent_type")
    def validate_agent_type(cls, v: str) -> str:
        """Validate agent type."""
        if v not in ["react", "supervisor"]:
            raise ValueError("agent_type must be 'react' or 'supervisor'")
        return v

    @classmethod
    def from_file(cls, filepath: str) -> "AgentConfig":
        """Load configuration from JSON file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {filepath}")

        with open(path) as f:
            data = json.load(f)

        # Expand environment variables in string values
        data = cls._expand_env_vars(data)

        return cls(**data)

    def to_file(self, filepath: str) -> None:
        """Save configuration to JSON file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)

    def to_agent_card(self) -> AgentCard:
        """Convert to standard A2A AgentCard (without deployment fields)."""
        agent_card_data = self.model_dump()
        
        # Remove deployment-specific fields
        deployment_fields = [
            "model", "temperature", "max_tokens", "system_prompt", 
            "agent_type", "mcp_tools", "modal_config", "ui_config"
        ]
        
        for field in deployment_fields:
            agent_card_data.pop(field, None)
        
        return AgentCard(**agent_card_data)

    def get_well_known_url(self, base_url: str) -> str:
        """Get the .well-known/agent.json URL for this agent."""
        return urljoin(base_url, "/.well-known/agent.json")

    @staticmethod
    def _expand_env_vars(obj: Any) -> Any:
        """Recursively expand environment variables in configuration."""
        if isinstance(obj, dict):
            return {k: AgentConfig._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [AgentConfig._expand_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            return os.path.expandvars(obj)
        else:
            return obj

    def get_api_key(self, provider: str = "anthropic") -> Optional[str]:
        """Get API key from environment variables."""
        key_mapping = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }

        env_var = key_mapping.get(provider.lower())
        if not env_var:
            raise ValueError(f"Unknown provider: {provider}")

        return os.getenv(env_var)

    def get_provider_info(self) -> AgentProvider:
        """Get provider information for A2A compatibility."""
        if self.provider:
            return self.provider
        
        # Default provider info
        return AgentProvider(
            organization="Agent Factory",
            url="https://github.com/agent-factory"
        )

    def update_skills_from_mcp_tools(self) -> None:
        """Update A2A skills based on MCP tools configuration."""
        self.skills = [
            AgentSkill(
                id=f"mcp_{tool.name}",
                name=tool.name,
                description=f"MCP tool: {tool.name}",
                tags=["mcp", "tool"],
                examples=[f"Use {tool.name} to perform tasks"],
            )
            for tool in self.mcp_tools
        ]