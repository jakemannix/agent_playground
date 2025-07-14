"""
Agent Factory - Build and deploy AI agents with MCP tools.

A modern framework for building and deploying AI agents with MCP tool integration.
"""

from .config import AgentConfiguration
from .deploy import deploy_agent, deploy_from_config_file
from .harness import AgentHarness

__version__ = "0.1.0"
__all__ = ["AgentConfiguration", "deploy_agent", "deploy_from_config_file", "AgentHarness"]