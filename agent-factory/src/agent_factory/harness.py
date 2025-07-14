"""
Agent Harness

Core logic for creating and running LangGraph agents with MCP tools.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from .config import AgentConfiguration, MCPSkill

logger = logging.getLogger(__name__)


async def create_mcp_tools(skills: List[MCPSkill]) -> List[BaseTool]:
    """Create LangChain tools from MCP skills."""
    if not skills:
        return []
    
    tools = []
    
    for skill in skills:
        try:
            servers_config = {skill.id: skill.mcp_config}
            logger.info(f"Creating MCP client for skill '{skill.name}' (id: {skill.id})")
            client = MultiServerMCPClient(servers_config)
            skill_tools = await client.get_tools()
            tools.extend(skill_tools)
            logger.info(f"Successfully loaded {len(skill_tools)} tools for skill '{skill.name}'")
        except Exception as e:
            if skill.optional:
                logger.warning(f"Failed to load optional skill '{skill.name}': {e}")
                continue
            else:
                # Fail fast for required skills with full stack trace
                raise RuntimeError(f"Failed to load required skill '{skill.name}': {e}") from e
    
    return tools


class AgentHarness:
    """Harness for creating and running configured agents."""

    def __init__(self, config: AgentConfiguration):
        self.config = config
        self.llm: ChatAnthropic | None = None
        self.agent = None
        self.tools: List[BaseTool] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the agent with LLM and tools."""
        if self._initialized:
            return

        logger.info(f"Initializing agent: {self.config.agent_card.name}")

        # Initialize LLM
        api_key = self.config.get_api_key("anthropic")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        # Build ChatAnthropic kwargs from deployment config
        llm_config = self.config.deployment.llm
        llm_kwargs = {
            "model": llm_config.model,
            "temperature": llm_config.temperature,
            "api_key": api_key,
        }
        
        # Only add max_tokens if it's not None
        if llm_config.max_tokens is not None:
            llm_kwargs["max_tokens"] = llm_config.max_tokens
            
        logger.info(f"Initializing ChatAnthropic with: {llm_kwargs}")
        self.llm = ChatAnthropic(**llm_kwargs)

        # Create MCP tools from skills
        if self.config.agent_card.skills:
            logger.info(f"Loading {len(self.config.agent_card.skills)} MCP skills")
            self.tools = await create_mcp_tools(self.config.agent_card.skills)
            logger.info(f"Successfully loaded {len(self.tools)} MCP tools")
            
            # Extract schemas from the tools we just created and update skills
            self._update_skills_with_schemas()

        # Create agent based on type
        agent_type = self.config.agent_card.agent_type
        if agent_type == "react":
            # Create react agent with system prompt
            # Note: For ChatAnthropic, system prompt is passed as a separate message
            self.agent = create_react_agent(
                model=self.llm,
                tools=self.tools,
            )
        else:
            raise NotImplementedError(f"Agent type '{agent_type}' not yet implemented")

        self._initialized = True
        logger.info(f"Agent initialized with {len(self.tools)} tools")

    def _update_skills_with_schemas(self) -> None:
        """Update MCPSkills with schemas extracted from the created tools."""
        if not self.tools:
            return
            
        # Create a mapping of tool names to tools
        tool_map = {tool.name: tool for tool in self.tools}
        
        # Update each skill with schema information from its corresponding tool
        for skill in self.config.agent_card.skills:
            # Try to find the corresponding tool
            # Tools might have different naming patterns
            tool = None
            for tool_name, t in tool_map.items():
                if (skill.id == f"mcp_{tool_name}" or 
                    skill.name == tool_name or
                    tool_name.startswith(f"{skill.name}_")):
                    tool = t
                    break
            
            if tool:
                try:
                    # Extract schemas from the tool - these are guaranteed properties
                    skill.input_schema = tool.input_schema.model_json_schema()
                    skill.output_schema = tool.output_schema.model_json_schema()
                    logger.debug(f"Updated skill {skill.id} with schemas from tool {tool.name}")
                except Exception as e:
                    logger.warning(f"Could not extract schemas from tool {tool.name}: {e}")

    async def invoke(self, message: str, **kwargs) -> Dict[str, Any]:
        """Invoke the agent with a message."""
        if not self._initialized:
            await self.initialize()

        if not self.agent:
            raise RuntimeError("Agent not properly initialized")

        # Prepare input for LangGraph agent
        # Include system prompt as first message if present
        messages = []
        if self.config.deployment.llm.system_prompt:
            messages.append({
                "role": "system",
                "content": self.config.deployment.llm.system_prompt
            })
        messages.append({"role": "user", "content": message})
        
        input_data = {"messages": messages, **kwargs}

        # Invoke agent
        result = await self.agent.ainvoke(input_data)

        return result

    async def stream(self, message: str, **kwargs):
        """Stream agent responses."""
        if not self._initialized:
            await self.initialize()

        if not self.agent:
            raise RuntimeError("Agent not properly initialized")

        # Include system prompt as in invoke
        messages = []
        if self.config.deployment.llm.system_prompt:
            messages.append({
                "role": "system",
                "content": self.config.deployment.llm.system_prompt
            })
        messages.append({"role": "user", "content": message})
        
        input_data = {"messages": messages, **kwargs}

        async for chunk in self.agent.astream(input_data):
            yield chunk

    def get_agent_card(self) -> Dict[str, Any]:
        """Get the agent card with updated schemas."""
        return self.config.agent_card.model_dump()