"""
Agent Configuration

Defines the schema and validation for agent configuration, extending A2A AgentCard.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from a2a.types import AgentCard, AgentCapabilities, AgentProvider, AgentSkill, AgentExtension
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

# Load environment variables
load_dotenv()


class MCPSkill(AgentSkill):
    """
    AgentSkill extended with MCP configuration.
    
    Includes MCP-specific fields like server configuration and schema information.
    """
    mcp_config: Dict[str, Any] = Field(
        ..., 
        description="MCP server configuration (transport, command, args, etc.)"
    )
    
    # MCP protocol 2025-06-18 compatibility fields
    # These are populated by introspecting the BaseTool objects created by langchain-mcp-adapters
    input_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="Tool input schema extracted from MCP server"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        None,
        description="Tool output schema extracted from MCP server"
    )
    optional: bool = Field(
        default=False,
        description="Whether this skill is optional. If false (default), agent initialization will fail if the MCP server is unavailable."
    )


class ModalConfig(BaseModel):
    """Modal deployment configuration."""
    cpu: float = Field(default=1.0, description="Number of CPUs")
    memory: int = Field(default=2048, description="Memory in MB")
    timeout: int = Field(default=300, description="Timeout in seconds")
    keep_warm: int = Field(default=0, description="Number of warm containers")
    secrets: List[str] = Field(default_factory=lambda: ["anthropic-api-key"])


class LLMConfig(BaseModel):
    """LLM-specific configuration."""
    model: str = Field(default="claude-3-5-sonnet-20241022", description="Model identifier")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1)
    system_prompt: str = Field(default="You are a helpful AI assistant.")


class UIConfig(BaseModel):
    """UI configuration settings."""
    theme: str = Field(default="light", description="UI theme")
    supported_modes: List[str] = Field(default_factory=lambda: ["chat"])


class DeploymentConfig(BaseModel):
    """Private deployment configuration (not exposed in public agent card)."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    modal: ModalConfig = Field(default_factory=ModalConfig)
    ui_config: Optional[UIConfig] = None


class MCPAgentCard(AgentCard):
    """
    A2A AgentCard extended for MCP-enabled agents.
    
    This is the public-facing agent description that gets served at .well-known/agent.json
    """
    capabilities: AgentCapabilities = Field(
        default_factory=lambda: AgentCapabilities(
            extensions=[
                AgentExtension(
                    uri="https://modelcontextprotocol.io/mcp/1.0",
                    description="Agent supports MCP tool integration with input/output schemas",
                    required=False,
                    params={"version": "2025-06-18"}
                )
            ]
        )
    )
    agent_type: str = Field(default="react", description="Agent type: 'react' only")
    skills: List[MCPSkill] = Field(default_factory=list, description="MCP skills")
    ui_modes: List[str] = Field(default_factory=lambda: ["chat"], description="Supported UI modes")
    
    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, v: str) -> str:
        """Validate agent type."""
        if v not in ["react"]:
            raise ValueError("agent_type must be 'react'")
        return v


class AgentConfiguration(BaseModel):
    """
    Complete agent configuration combining public and private parts.
    
    This is the full configuration used internally. Only the agent_card
    portion is exposed publicly via .well-known/agent.json
    """
    agent_card: MCPAgentCard = Field(description="Public agent card (A2A compliant)")
    deployment: DeploymentConfig = Field(description="Private deployment configuration")
    
    @classmethod
    def from_file(cls, filepath: str) -> "AgentConfiguration":
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
    
    def get_well_known_url(self, base_url: str) -> str:
        """Get the .well-known/agent.json URL for this agent."""
        return urljoin(base_url, "/.well-known/agent.json")
    
    @staticmethod
    def _expand_env_vars(obj: Any) -> Any:
        """Recursively expand environment variables in configuration."""
        if isinstance(obj, dict):
            return {k: AgentConfiguration._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [AgentConfiguration._expand_env_vars(item) for item in obj]
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