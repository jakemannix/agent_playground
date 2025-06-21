"""Test agent harness."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_factory.config import AgentConfig
from agent_factory.harness import AgentHarness


class TestAgentHarness:
    """Test agent harness functionality."""

    @pytest.fixture
    def sample_config(self):
        """Create a sample agent configuration."""
        return AgentConfig(
            name="Test Agent",
            description="A test agent",
            url="https://example.com/agent",
            system_prompt="You are a helpful test agent.",
            model="claude-3-5-sonnet-20241022",
            temperature=0.7
        )

    def test_harness_initialization(self, sample_config):
        """Test basic harness initialization."""
        harness = AgentHarness(sample_config)
        
        assert harness.config == sample_config
        assert harness.llm is None
        assert harness.agent is None
        assert harness.tools == []
        assert not harness._initialized

    def test_get_config_summary(self, sample_config):
        """Test getting configuration summary."""
        harness = AgentHarness(sample_config)
        
        summary = harness.get_config_summary()
        
        assert summary["name"] == "Test Agent"
        assert summary["description"] == "A test agent"
        assert summary["model"] == "claude-3-5-sonnet-20241022"
        assert summary["agent_type"] == "react"
        assert summary["tools"] == []
        assert summary["initialized"] is False

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
            max_tokens=None,
            api_key="test-key"
        )
        
        # Verify create_react_agent was called
        mock_create_react_agent.assert_called_once_with(
            model=mock_llm,
            tools=mock_tools,
            system_message="You are a helpful test agent."
        )

    @pytest.mark.asyncio
    async def test_initialize_without_api_key(self, sample_config):
        """Test initialization failure without API key."""
        harness = AgentHarness(sample_config)
        
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not found"):
            await harness.initialize()

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
            "messages": [{"role": "user", "content": "test message"}]
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
        """Test getting tool names when no tools are loaded."""
        harness = AgentHarness(sample_config)
        
        tool_names = harness.get_tool_names()
        assert tool_names == []

    def test_get_tool_names_with_tools(self, sample_config):
        """Test getting tool names with loaded tools."""
        harness = AgentHarness(sample_config)
        
        # Mock some tools
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"
        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"
        
        harness.tools = [mock_tool1, mock_tool2]
        
        tool_names = harness.get_tool_names()
        assert tool_names == ["tool1", "tool2"]

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