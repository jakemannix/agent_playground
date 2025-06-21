"""
Agent Factory

Modal deployment harness for config-driven AI agents using LangGraph
and MCP tools. Provides serverless deployment and orchestration.
"""

from .config import AgentConfig, MCPToolConfig
from .deploy import deploy_agent, deploy_from_config_file
from .harness import AgentHarness

__version__ = "0.1.0"
__all__ = ["AgentConfig", "MCPToolConfig", "deploy_agent", "deploy_from_config_file", "AgentHarness"]