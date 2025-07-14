"""Test agent configuration."""

import json
import tempfile
from pathlib import Path

import pytest
from a2a.types import AgentCard, AgentCapabilities, AgentProvider, AgentSkill, AgentExtension

from agent_factory.config import (
    AgentConfiguration, 
    MCPAgentCard, 
    MCPSkill, 
    ModalConfig,
    LLMConfig,
    DeploymentConfig
)


class TestMCPSkill:
    """Test MCP skill configuration."""

    def test_create_mcp_skill(self):
        """Test creating MCP skill."""
        skill = MCPSkill(
            id="mcp_test",
            name="Test Tool",
            description="A test MCP tool",
            tags=["mcp", "test"],
            examples=["Use test tool"],
            mcp_config={"transport": "stdio", "command": "test"},
            input_schema={"type": "object"},
            output_schema={"type": "object"}
        )
        
        assert skill.id == "mcp_test"
        assert skill.name == "Test Tool"
        assert skill.mcp_config == {"transport": "stdio", "command": "test"}
        assert skill.input_schema == {"type": "object"}
        assert skill.output_schema == {"type": "object"}


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


class TestLLMConfig:
    """Test LLM configuration."""

    def test_llm_config(self):
        """Test LLM configuration."""
        config = LLMConfig(
            model="claude-3-5-sonnet-20241022",
            temperature=0.7,
            max_tokens=1000,
            system_prompt="You are a helpful assistant."
        )
        
        assert config.model == "claude-3-5-sonnet-20241022"
        assert config.temperature == 0.7
        assert config.max_tokens == 1000
        assert config.system_prompt == "You are a helpful assistant."


class TestMCPAgentCard:
    """Test MCP agent card."""

    def test_mcp_agent_card_with_extension(self):
        """Test MCP agent card includes MCP extension."""
        skills = [
            MCPSkill(
                id="mcp_test",
                name="Test Tool",
                description="A test MCP tool",
                tags=["mcp", "test"],
                mcp_config={"transport": "stdio"}
            )
        ]
        
        card = MCPAgentCard(
            name="Test Agent",
            description="A test agent",
            url="https://example.com/agent",
            version="1.0.0",
            skills=skills,
            defaultInputModes=["text/plain"],
            defaultOutputModes=["text/plain"]
        )
        
        # Check MCP extension is present
        assert card.capabilities.extensions
        mcp_ext = next(e for e in card.capabilities.extensions if "modelcontextprotocol.io" in e.uri)
        assert mcp_ext.params["version"] == "2025-06-18"


class TestAgentConfiguration:
    """Test complete agent configuration."""

    def test_create_agent_configuration(self):
        """Test creating agent configuration."""
        skills = [
            MCPSkill(
                id="mcp_test",
                name="Test Tool",
                description="A test MCP tool",
                tags=["mcp", "test"],
                mcp_config={"transport": "stdio"}
            )
        ]
        
        agent_card = MCPAgentCard(
            name="Test Agent",
            description="A test agent",
            url="https://example.com/agent",
            version="1.0.0",
            skills=skills,
            agent_type="react",
            ui_modes=["chat"],
            defaultInputModes=["text/plain"],
            defaultOutputModes=["text/plain"]
        )
        
        deployment = DeploymentConfig(
            llm=LLMConfig(
                model="claude-3-5-sonnet-20241022",
                temperature=0.7,
                system_prompt="You are a test agent."
            ),
            modal=ModalConfig(),
            ui_config={"theme": "light"}
        )
        
        config = AgentConfiguration(
            agent_card=agent_card,
            deployment=deployment
        )
        
        assert config.agent_card.name == "Test Agent"
        assert config.deployment.llm.model == "claude-3-5-sonnet-20241022"
        assert config.deployment.modal.cpu == 1.0

    def test_file_operations(self):
        """Test saving and loading configuration from files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.json"
            
            config = AgentConfiguration(
                agent_card=MCPAgentCard(
                    name="Test Agent",
                    description="Test description",
                    url="https://example.com",
                    version="1.0.0",
                    defaultInputModes=["textMessage"],
                    defaultOutputModes=["textMessage"],
                    skills=[],
                    agent_type="react"
                ),
                deployment=DeploymentConfig(
                    llm=LLMConfig(
                        model="claude-3-5-sonnet-20241022",
                        system_prompt="Test prompt"
                    )
                )
            )
            
            # Save to file
            config.to_file(str(config_path))
            assert config_path.exists()
            
            # Load from file
            loaded_config = AgentConfiguration.from_file(str(config_path))
            assert loaded_config.agent_card.name == "Test Agent"
            assert loaded_config.deployment.llm.model == "claude-3-5-sonnet-20241022"

    def test_get_well_known_url(self):
        """Test getting well-known URL."""
        config = AgentConfiguration(
            agent_card=MCPAgentCard(
                name="Test Agent",
                description="A test agent",
                url="https://example.com/agent",
                version="1.0.0",
                skills=[],
                defaultInputModes=["text/plain"],
                defaultOutputModes=["text/plain"]
            ),
            deployment=DeploymentConfig(
                llm=LLMConfig(system_prompt="Test")
            )
        )
        
        well_known_url = config.get_well_known_url("https://example.com")
        assert well_known_url == "https://example.com/.well-known/agent.json"