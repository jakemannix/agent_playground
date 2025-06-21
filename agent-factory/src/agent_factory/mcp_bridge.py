"""
MCP Bridge

Converts MCP servers into LangChain tools using langchain-mcp-adapters.
"""

import logging
from typing import List

from langchain_core.tools import BaseTool
from langchain_mcp_adapters import MCPToolkit

from .config import MCPToolConfig

logger = logging.getLogger(__name__)


async def create_mcp_tools(tool_configs: List[MCPToolConfig]) -> List[BaseTool]:
    """Create LangChain tools from MCP tool configurations."""
    tools = []
    
    for tool_config in tool_configs:
        try:
            logger.info(f"Loading MCP tool: {tool_config.name}")
            
            # Use langchain-mcp-adapters to create toolkit
            toolkit = MCPToolkit(
                server_path=tool_config.server_path,
                server_config=tool_config.config
            )
            
            # Initialize the toolkit
            await toolkit.initialize()
            
            # Get tools from toolkit
            mcp_tools = toolkit.get_tools()
            tools.extend(mcp_tools)
            
            logger.info(f"Loaded {len(mcp_tools)} tools from {tool_config.name}")
            
        except Exception as e:
            logger.error(f"Failed to load MCP tool {tool_config.name}: {e}")
            # Continue with other tools instead of failing completely
            continue
    
    return tools


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