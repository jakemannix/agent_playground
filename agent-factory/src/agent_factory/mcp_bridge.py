"""
MCP Bridge

Converts MCP servers into LangChain tools using langchain-mcp-adapters.
"""

import logging
from typing import List

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from .config import MCPToolConfig

logger = logging.getLogger(__name__)


async def create_mcp_tools(tool_configs: List[MCPToolConfig]) -> List[BaseTool]:
    """Create LangChain tools from MCP tool configurations."""
    if not tool_configs:
        return []
    
    # Build server configuration for MultiServerMCPClient
    # Each tool_config becomes a server in the client configuration
    servers_config = {}
    
    for tool_config in tool_configs:
        # Use the config directly as the server configuration
        # This allows flexible configuration like:
        # { "transport": "streamable_http", "url": "http://localhost:8123" }
        # or
        # { "command": "python", "args": ["server.py"], "transport": "stdio" }
        servers_config[tool_config.name] = tool_config.config
        logger.info(f"Added MCP server '{tool_config.name}' with config: {tool_config.config}")
    
    if not servers_config:
        logger.warning("No MCP server configurations found")
        return []
    
    try:
        logger.info(f"Creating MultiServerMCPClient with config: {servers_config}")
        client = MultiServerMCPClient(servers_config)
        
        # Get all tools from all configured servers
        tools = await client.get_tools()
        
        logger.info(f"Successfully loaded {len(tools)} tools from MCP servers")
        return tools
        
    except Exception as e:
        logger.error(f"Failed to create MCP client or load tools: {e}")
        return []


async def create_mcp_tool(tool_config: MCPToolConfig) -> List[BaseTool]:
    """Create LangChain tools from a single MCP tool configuration."""
    return await create_mcp_tools([tool_config])


# Legacy compatibility - single tool creation
async def create_single_mcp_tool(tool_config: MCPToolConfig) -> BaseTool:
    """
    Create a single LangChain tool from MCP configuration.
    
    Note: This is for backward compatibility. MCP servers typically
    provide multiple tools, so prefer create_mcp_tools().
    """
    tools = await create_mcp_tool(tool_config)
    
    if not tools:
        raise ValueError(f"No tools found in MCP server: {tool_config.name}")
    
    if len(tools) > 1:
        logger.warning(
            f"MCP server {tool_config.name} provides {len(tools)} tools, "
            f"returning only the first one. Consider using create_mcp_tools()."
        )
    
    return tools[0]