"""Test agent configuration."""

import json
import tempfile
from pathlib import Path

import pytest
from a2a.types import AgentCard, AgentCapabilities, AgentProvider, AgentSkill

from agent_factory.config import AgentConfig, MCPToolConfig, ModalConfig


class TestMCPToolConfig:
    """Test MCP tool configuration."""

    def test_create_mcp_tool_config(self):
        """Test creating MCP tool configuration."""
        config = MCPToolConfig(
            name="test_tool",
            server_path="path/to/server.py",
            config={"key": "value"}
        )
        
        assert config.name == "test_tool"
        assert config.server_path == "path/to/server.py"
        assert config.config == {"key": "value"}


class TestModalConfig:
    """Test Modal deployment configuration."""

    def test_default_modal_config(self):
        """Test default Modal configuration."""
        config = ModalConfig()
        
        assert config.cpu == 1.0
        assert config.memory == 2048
        assert config.timeout == 300
        assert config.keep_warm == 0
        assert config.secrets == ["anthropic-api-key"]

    def test_custom_modal_config(self):
        """Test custom Modal configuration."""
        config = ModalConfig(
            cpu=2.0,
            memory=4096,
            timeout=600,
            keep_warm=2,
            secrets=["custom-secret"]
        )
        
        assert config.cpu == 2.0
        assert config.memory == 4096
        assert config.timeout == 600
        assert config.keep_warm == 2
        assert config.secrets == ["custom-secret"]


class TestAgentConfig:
    """Test agent configuration."""

    def test_minimal_agent_config(self):
        """Test creating minimal agent configuration."""
        config = AgentConfig(
            name="Test Agent",
            description="A test agent",
            url="https://example.com/agent",
            system_prompt="You are a test agent."
        )
        
        assert config.name == "Test Agent"
        assert config.description == "A test agent"
        assert config.url == "https://example.com/agent"
        assert config.system_prompt == "You are a test agent."
        assert config.model == "claude-3-5-sonnet-20241022"
        assert config.temperature == 0.7
        assert config.agent_type == "react"
        assert config.version == "1.0.0"

    def test_agent_config_with_a2a_fields(self):
        """Test agent configuration with A2A fields."""
        skills = [
            AgentSkill(
                id="test_skill",
                name="Test Skill",
                description="A test skill",
                tags=["test"],
                examples=["Test example"]
            )
        ]
        
        capabilities = AgentCapabilities(
            streaming=True,
            pushNotifications=False
        )
        
        provider = AgentProvider(
            organization="Test Org",
            url="https://test.com"
        )
        
        config = AgentConfig(
            name="Test Agent",
            description="A test agent", 
            url="https://example.com/agent",
            system_prompt="You are a test agent.",
            skills=skills,
            capabilities=capabilities,
            provider=provider,
            defaultInputModes=["text/plain"],
            defaultOutputModes=["text/plain"]
        )
        
        assert config.skills == skills
        assert config.capabilities == capabilities
        assert config.provider == provider
        assert config.defaultInputModes == ["text/plain"]
        assert config.defaultOutputModes == ["text/plain"]

    def test_agent_config_with_mcp_tools(self):
        """Test agent configuration with MCP tools."""
        mcp_tools = [
            MCPToolConfig(
                name="test_tool",
                server_path="path/to/server.py",
                config={"key": "value"}
            )
        ]
        
        config = AgentConfig(
            name="Test Agent",
            description="A test agent",
            url="https://example.com/agent", 
            system_prompt="You are a test agent.",
            mcp_tools=mcp_tools
        )
        
        assert len(config.mcp_tools) == 1
        assert config.mcp_tools[0].name == "test_tool"
        
        # Check that skills were auto-generated from MCP tools
        assert len(config.skills) == 1
        assert config.skills[0].id == "mcp_test_tool"
        assert config.skills[0].name == "test_tool"

    def test_agent_type_validation(self):
        """Test agent type validation."""
        with pytest.raises(ValueError, match="agent_type must be 'react' or 'supervisor'"):
            AgentConfig(
                name="Test Agent",
                description="A test agent",
                url="https://example.com/agent",
                system_prompt="You are a test agent.",
                agent_type="invalid"
            )

    def test_to_agent_card(self):
        """Test converting to A2A agent card."""
        config = AgentConfig(
            name="Test Agent",
            description="A test agent",
            url="https://example.com/agent",
            system_prompt="You are a test agent.",
            model="gpt-4",
            temperature=0.8
        )
        
        agent_card = config.to_agent_card()
        
        # Should have A2A fields
        assert isinstance(agent_card, AgentCard)
        assert agent_card.name == "Test Agent"
        assert agent_card.description == "A test agent"
        assert agent_card.url == "https://example.com/agent"
        
        # Should not have deployment-specific fields
        assert not hasattr(agent_card, 'model')
        assert not hasattr(agent_card, 'temperature')
        assert not hasattr(agent_card, 'system_prompt')

    def test_file_operations(self):
        """Test saving and loading configuration files."""
        config = AgentConfig(
            name="Test Agent",
            description="A test agent",
            url="https://example.com/agent",
            system_prompt="You are a test agent."
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_agent.json"
            
            # Save configuration
            config.to_file(str(config_path))
            assert config_path.exists()
            
            # Load configuration
            loaded_config = AgentConfig.from_file(str(config_path))
            assert loaded_config.name == config.name
            assert loaded_config.description == config.description
            assert loaded_config.url == config.url
            assert loaded_config.system_prompt == config.system_prompt

    def test_env_var_expansion(self):
        """Test environment variable expansion."""
        import os
        os.environ['TEST_VAR'] = 'test_value'
        
        config_data = {
            "name": "Test Agent",
            "description": "A test agent",
            "url": "https://example.com/agent",
            "system_prompt": "You are ${TEST_VAR}."
        }
        
        expanded = AgentConfig._expand_env_vars(config_data)
        assert expanded['system_prompt'] == "You are test_value."
        
        # Clean up
        del os.environ['TEST_VAR']

    def test_get_well_known_url(self):
        """Test getting .well-known URL."""
        config = AgentConfig(
            name="Test Agent",
            description="A test agent",
            url="https://example.com/agent",
            system_prompt="You are a test agent."
        )
        
        well_known_url = config.get_well_known_url("https://example.com")
        assert well_known_url == "https://example.com/.well-known/agent.json"