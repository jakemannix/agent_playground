"""
Tests for agent harness functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os

from agent_factory.harness import AgentHarness
from agent_factory.config import AgentConfiguration, MCPAgentCard, DeploymentConfig, LLMConfig, MCPSkill


class TestAgentHarness:
    """Test cases for AgentHarness."""

    @pytest.fixture
    def sample_config(self):
        """Create a sample agent configuration."""
        return AgentConfiguration(
            agent_card=MCPAgentCard(
                name="Test Agent",
                description="A test agent",
                url="https://example.com/agent",
                agent_type="react",
                skills=[
                    MCPSkill(
                        id="mcp_filesystem",
                        name="filesystem",
                        description="File system operations",
                        tags=["file", "io"],
                        examples=["Read file", "Write file"],
                        mcp_config={
                            "command": "python",
                            "args": ["-m", "mcp.server.filesystem"],
                            "env": {"FILESYSTEM_ROOT": "/tmp"}
                        }
                    ),
                    MCPSkill(
                        id="mcp_sqlite",
                        name="sqlite",
                        description="SQLite database operations",
                        tags=["database", "sql"],
                        examples=["Query database", "Insert data"],
                        mcp_config={
                            "command": "python",
                            "args": ["-m", "mcp.server.sqlite"],
                            "env": {"DATABASE_PATH": "/tmp/test.db"}
                        }
                    )
                ],
                version="1.0.0",
                defaultInputModes=["textMessage"],
                defaultOutputModes=["textMessage"]
            ),
            deployment=DeploymentConfig(
                llm=LLMConfig(
                    model="claude-3-5-sonnet-20241022",
                    temperature=0.7,
                    system_prompt="You are a helpful test agent."
                )
            )
        )

    def test_harness_initialization(self, sample_config):
        """Test basic harness initialization."""
        harness = AgentHarness(sample_config)
        
        assert harness.config == sample_config
        assert harness.llm is None
        assert harness.agent is None
        assert harness.tools == []
        assert not harness._initialized

    def test_get_agent_card(self, sample_config):
        """Test getting agent card."""
        harness = AgentHarness(sample_config)
        
        agent_card = harness.get_agent_card()
        
        assert agent_card["name"] == "Test Agent"
        assert agent_card["description"] == "A test agent"
        assert agent_card["agent_type"] == "react"
        assert "skills" in agent_card
        assert len(agent_card["skills"]) == 2
        # Check that both skills are present
        skill_ids = [skill["id"] for skill in agent_card["skills"]]
        assert "mcp_filesystem" in skill_ids
        assert "mcp_sqlite" in skill_ids

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('agent_factory.harness.ChatAnthropic')
    @patch('agent_factory.harness.create_react_agent')
    @patch('agent_factory.harness.create_mcp_tools')
    async def test_initialize_agent(self, mock_create_mcp_tools, mock_create_react_agent, 
                                  mock_chat_anthropic, sample_config):
        """Test agent initialization."""
        # Mock dependencies
        mock_llm = MagicMock()
        mock_chat_anthropic.return_value = mock_llm
        
        mock_agent = MagicMock()
        mock_create_react_agent.return_value = mock_agent
        
        mock_tools = [MagicMock(), MagicMock()]
        mock_create_mcp_tools.return_value = mock_tools
        
        harness = AgentHarness(sample_config)
        await harness.initialize()
        
        # Verify initialization
        assert harness._initialized is True
        assert harness.llm == mock_llm
        assert harness.agent == mock_agent
        assert harness.tools == mock_tools
        
        # Verify ChatAnthropic was called with correct parameters
        mock_chat_anthropic.assert_called_once_with(
            model="claude-3-5-sonnet-20241022",
            temperature=0.7,
            api_key="test-key"
        )
        
        # Verify create_react_agent was called
        mock_create_react_agent.assert_called_once_with(
            model=mock_llm,
            tools=mock_tools,
        )

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('agent_factory.harness.ChatAnthropic')
    @patch('agent_factory.harness.create_react_agent')
    @patch('agent_factory.harness.create_mcp_tools')
    async def test_invoke_agent(self, mock_create_mcp_tools, mock_create_react_agent, 
                               mock_chat_anthropic, sample_config):
        """Test agent invocation."""
        # Mock dependencies
        mock_llm = MagicMock()
        mock_chat_anthropic.return_value = mock_llm
        
        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {"response": "test response"}
        mock_create_react_agent.return_value = mock_agent
        
        mock_create_mcp_tools.return_value = []
        
        harness = AgentHarness(sample_config)
        
        # Test invocation
        result = await harness.invoke("test message")
        
        assert result == {"response": "test response"}
        assert harness._initialized is True
        
        # Verify agent was called with correct input
        expected_input = {
            "messages": [
                {"role": "system", "content": "You are a helpful test agent."},
                {"role": "user", "content": "test message"}
            ]
        }
        mock_agent.ainvoke.assert_called_once_with(expected_input)

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('agent_factory.harness.ChatAnthropic')
    @patch('agent_factory.harness.create_react_agent')
    @patch('agent_factory.harness.create_mcp_tools')
    async def test_stream_agent(self, mock_create_mcp_tools, mock_create_react_agent, 
                               mock_chat_anthropic, sample_config):
        """Test agent streaming."""
        # Mock dependencies
        mock_llm = MagicMock()
        mock_chat_anthropic.return_value = mock_llm
        
        mock_agent = AsyncMock()
        
        async def mock_astream(input_data):
            yield {"chunk": 1}
            yield {"chunk": 2}
        
        mock_agent.astream = mock_astream
        mock_create_react_agent.return_value = mock_agent
        
        mock_create_mcp_tools.return_value = []
        
        harness = AgentHarness(sample_config)
        
        # Test streaming
        chunks = []
        async for chunk in harness.stream("test message"):
            chunks.append(chunk)
        
        assert len(chunks) == 2
        assert chunks[0] == {"chunk": 1}
        assert chunks[1] == {"chunk": 2}

    def test_get_tool_names_empty(self, sample_config):
        """Test that tools information is available via agent card when no tools are loaded."""
        harness = AgentHarness(sample_config)
        
        agent_card = harness.get_agent_card()
        # Skills are configured but no actual tools loaded yet
        assert "skills" in agent_card
        assert len(agent_card["skills"]) == 2

    def test_get_tool_names_with_tools(self, sample_config):
        """Test that tools information is available via agent card."""
        harness = AgentHarness(sample_config)
        
        # Mock some tools
        mock_tool1 = MagicMock()
        mock_tool1.name = "filesystem"
        mock_tool2 = MagicMock()
        mock_tool2.name = "sqlite"
        
        harness.tools = [mock_tool1, mock_tool2]
        
        agent_card = harness.get_agent_card()
        assert "skills" in agent_card
        assert len(agent_card["skills"]) == 2
        # Verify skills contain the expected information
        skill_names = [skill["name"] for skill in agent_card["skills"]]
        assert "filesystem" in skill_names
        assert "sqlite" in skill_names

    @pytest.mark.asyncio
    async def test_invoke_without_initialization_fails(self, sample_config):
        """Test that invoke fails if agent is not properly initialized."""
        harness = AgentHarness(sample_config)
        harness._initialized = True  # Pretend initialized
        harness.agent = None  # But agent is None
        
        with pytest.raises(RuntimeError, match="Agent not properly initialized"):
            await harness.invoke("test message")

    @pytest.mark.asyncio
    async def test_stream_without_initialization_fails(self, sample_config):
        """Test that stream fails if agent is not properly initialized."""
        harness = AgentHarness(sample_config)
        harness._initialized = True  # Pretend initialized
        harness.agent = None  # But agent is None
        
        with pytest.raises(RuntimeError, match="Agent not properly initialized"):
            async for _ in harness.stream("test message"):
                pass

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('agent_factory.harness.ChatAnthropic')
    @patch('langgraph.prebuilt.create_react_agent')
    @patch('agent_factory.harness.create_mcp_tools')
    async def test_required_skill_failure(self, mock_create_mcp_tools, mock_create_react_agent,
                                         mock_chat_anthropic, sample_config):
        """Test that initialization fails when required skills fail to load."""
        # Mock ChatAnthropic
        mock_llm = MagicMock()
        mock_chat_anthropic.return_value = mock_llm
        
        # Configure mock to simulate skill failure
        mock_create_mcp_tools.side_effect = RuntimeError("Failed to load required skill 'filesystem': Connection refused")
        mock_create_react_agent.return_value = MagicMock()
        
        harness = AgentHarness(sample_config)
        
        # Should raise RuntimeError for required skill failure
        with pytest.raises(RuntimeError) as exc_info:
            await harness.initialize()
        
        assert "Failed to load required skill 'filesystem'" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('agent_factory.harness.ChatAnthropic')
    @patch('langgraph.prebuilt.create_react_agent')
    @patch('agent_factory.harness.create_mcp_tools')
    async def test_optional_skill_failure(self, mock_create_mcp_tools, mock_create_react_agent,
                                         mock_chat_anthropic, sample_config):
        """Test that initialization succeeds when only optional skills fail."""
        # Mock ChatAnthropic
        mock_llm = MagicMock()
        mock_chat_anthropic.return_value = mock_llm
        
        # Make the first skill optional
        sample_config.agent_card.skills[0].optional = True
        
        # Mock the create_mcp_tools function to return empty list (simulates optional skill failure)
        mock_create_mcp_tools.return_value = []
        mock_create_react_agent.return_value = MagicMock()
        
        harness = AgentHarness(sample_config)
        
        # Should not raise for optional skill failure
        await harness.initialize()
        assert harness._initialized
        assert harness.tools == []