"""
Agent Harness

Core logic for creating and running LangGraph agents with MCP tools.
"""

import logging
from typing import Any, Dict, List

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from .config import AgentConfig
from .mcp_bridge import create_mcp_tools

logger = logging.getLogger(__name__)


class AgentHarness:
    """Harness for creating and running configured agents."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm: ChatAnthropic | None = None
        self.agent = None
        self.tools: List[BaseTool] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the agent with LLM and tools."""
        if self._initialized:
            return

        logger.info(f"Initializing agent: {self.config.name}")

        # Initialize LLM
        api_key = self.config.get_api_key("anthropic")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.llm = ChatAnthropic(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            api_key=api_key,
        )

        # Load MCP tools
        self.tools = await self._load_mcp_tools()

        # Create agent based on type
        if self.config.agent_type == "react":
            self.agent = create_react_agent(
                model=self.llm,
                tools=self.tools,
                system_message=self.config.system_prompt,
            )
        else:
            # TODO: Implement supervisor agent pattern
            raise NotImplementedError(f"Agent type '{self.config.agent_type}' not yet implemented")

        self._initialized = True
        logger.info(f"Agent initialized with {len(self.tools)} tools")

    async def _load_mcp_tools(self) -> List[BaseTool]:
        """Load and initialize MCP tools."""
        if not self.config.mcp_tools:
            return []

        try:
            logger.info(f"Loading {len(self.config.mcp_tools)} MCP tool configurations")
            tools = await create_mcp_tools(self.config.mcp_tools)
            logger.info(f"Successfully loaded {len(tools)} MCP tools")
            return tools
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")
            return []

    async def invoke(self, message: str, **kwargs) -> Dict[str, Any]:
        """Invoke the agent with a message."""
        if not self._initialized:
            await self.initialize()

        if not self.agent:
            raise RuntimeError("Agent not properly initialized")

        # Prepare input for LangGraph agent
        input_data = {"messages": [{"role": "user", "content": message}], **kwargs}

        # Invoke agent
        result = await self.agent.ainvoke(input_data)

        return result

    async def stream(self, message: str, **kwargs):
        """Stream agent responses."""
        if not self._initialized:
            await self.initialize()

        if not self.agent:
            raise RuntimeError("Agent not properly initialized")

        input_data = {"messages": [{"role": "user", "content": message}], **kwargs}

        async for chunk in self.agent.astream(input_data):
            yield chunk

    def get_tool_names(self) -> List[str]:
        """Get list of available tool names."""
        return [tool.name for tool in self.tools]

    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of the agent configuration."""
        return {
            "name": self.config.name,
            "description": self.config.description,
            "model": self.config.model,
            "agent_type": self.config.agent_type,
            "tools": self.get_tool_names(),
            "initialized": self._initialized,
        }