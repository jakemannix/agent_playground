"""
Tests for configuration management features.
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from agent_factory.cli import (
    has_existing_schemas,
    validate_schema_consistency,
    deep_merge,
    parse_value,
    set_nested_value,
    apply_overrides,
)
from agent_factory.config import AgentConfiguration, MCPAgentCard, MCPSkill, DeploymentConfig, LLMConfig


class TestConfigManagement:
    """Test configuration management utilities."""

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
                        id="mcp_tool1",
                        name="tool1",
                        description="Tool 1",
                        tags=["test"],
                        mcp_config={"transport": "stdio", "command": "tool1"}
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
                    system_prompt="You are a test agent."
                )
            )
        )

    @pytest.fixture
    def config_with_schemas(self, sample_config):
        """Create a config with extracted schemas."""
        config = sample_config.model_copy(deep=True)
        config.agent_card.skills[0].input_schema = {"type": "object", "properties": {"query": {"type": "string"}}}
        config.agent_card.skills[0].output_schema = {"type": "object", "properties": {"result": {"type": "string"}}}
        return config

    def test_has_existing_schemas_false(self, sample_config):
        """Test detection when no schemas exist."""
        assert not has_existing_schemas(sample_config)

    def test_has_existing_schemas_true(self, config_with_schemas):
        """Test detection when schemas exist."""
        assert has_existing_schemas(config_with_schemas)

    def test_validate_schema_consistency_matching(self, config_with_schemas):
        """Test validation when schemas match."""
        # Should not raise
        validate_schema_consistency(config_with_schemas, config_with_schemas)

    def test_validate_schema_consistency_different_skills(self, config_with_schemas, sample_config):
        """Test validation when skills differ."""
        # Add a new skill to one config
        new_skill = MCPSkill(
            id="mcp_tool2",
            name="tool2",
            description="Tool 2",
            tags=["test"],
            mcp_config={"transport": "stdio", "command": "tool2"}
        )
        modified_config = config_with_schemas.model_copy(deep=True)
        modified_config.agent_card.skills.append(new_skill)
        
        with pytest.raises(ValueError, match="Skill mismatch"):
            validate_schema_consistency(config_with_schemas, modified_config)

    def test_validate_schema_consistency_different_input_schema(self, config_with_schemas):
        """Test validation when input schema changes."""
        modified_config = config_with_schemas.model_copy(deep=True)
        modified_config.agent_card.skills[0].input_schema = {"type": "object", "properties": {"different": {"type": "string"}}}
        
        with pytest.raises(ValueError, match="Input schema changed"):
            validate_schema_consistency(config_with_schemas, modified_config)

    def test_validate_schema_consistency_different_output_schema(self, config_with_schemas):
        """Test validation when output schema changes."""
        modified_config = config_with_schemas.model_copy(deep=True)
        modified_config.agent_card.skills[0].output_schema = {"type": "object", "properties": {"different": {"type": "string"}}}
        
        with pytest.raises(ValueError, match="Output schema changed"):
            validate_schema_consistency(config_with_schemas, modified_config)

    def test_deep_merge_simple(self):
        """Test deep merge with simple values."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested(self):
        """Test deep merge with nested dicts."""
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 3, "z": 4}, "c": 5}
        result = deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 3, "z": 4}, "b": 3, "c": 5}

    def test_deep_merge_lists(self):
        """Test deep merge with lists (replace behavior)."""
        base = {"a": [1, 2, 3], "b": 2}
        override = {"a": [4, 5], "c": 3}
        result = deep_merge(base, override)
        assert result == {"a": [4, 5], "b": 2, "c": 3}

    def test_parse_value_string(self):
        """Test parsing string values."""
        assert parse_value("hello") == "hello"

    def test_parse_value_number(self):
        """Test parsing numeric values."""
        assert parse_value("123") == 123
        assert parse_value("123.45") == 123.45

    def test_parse_value_boolean(self):
        """Test parsing boolean values."""
        assert parse_value("true") is True
        assert parse_value("false") is False

    def test_parse_value_array(self):
        """Test parsing array values."""
        assert parse_value('["a", "b", "c"]') == ["a", "b", "c"]

    def test_parse_value_object(self):
        """Test parsing object values."""
        assert parse_value('{"key": "value"}') == {"key": "value"}

    def test_set_nested_value_simple(self):
        """Test setting simple nested value."""
        obj = {"a": {"b": 1}}
        set_nested_value(obj, "a.b", 2)
        assert obj == {"a": {"b": 2}}

    def test_set_nested_value_create_path(self):
        """Test creating path when setting value."""
        obj = {"a": {}}
        set_nested_value(obj, "a.b.c", 3)
        assert obj == {"a": {"b": {"c": 3}}}

    def test_set_nested_value_array_index(self):
        """Test setting value in array by index."""
        obj = {"items": [{"name": "a"}, {"name": "b"}]}
        set_nested_value(obj, "items[1].name", "c")
        assert obj == {"items": [{"name": "a"}, {"name": "c"}]}

    def test_set_nested_value_create_array(self):
        """Test creating array when setting indexed value."""
        obj = {}
        set_nested_value(obj, "items[0].name", "test")
        assert obj == {"items": [{"name": "test"}]}

    def test_apply_overrides(self, sample_config):
        """Test applying overrides to configuration."""
        overrides = {
            "agent_card": {
                "name": "Modified Agent",
                "skills": [
                    {
                        "id": "mcp_new_tool",
                        "name": "new_tool",
                        "description": "New tool",
                        "tags": ["new"],
                        "mcp_config": {"transport": "http", "url": "http://localhost:8000"}
                    }
                ]
            },
            "deployment": {
                "llm": {
                    "temperature": 0.5
                }
            }
        }
        
        result = apply_overrides(sample_config, overrides)
        
        assert result.agent_card.name == "Modified Agent"
        assert len(result.agent_card.skills) == 1
        assert result.agent_card.skills[0].id == "mcp_new_tool"
        assert result.deployment.llm.temperature == 0.5
        assert result.deployment.llm.model == "claude-3-5-sonnet-20241022"  # Preserved

    def test_apply_overrides_from_yaml_file(self, sample_config):
        """Test applying overrides from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = """
agent_card:
  name: YAML Agent
  description: Updated from YAML
deployment:
  llm:
    temperature: 0.3
"""
            f.write(yaml_content)
            f.flush()
            
            with open(f.name) as yaml_file:
                overrides = yaml.safe_load(yaml_file)
            
            result = apply_overrides(sample_config, overrides)
            
            assert result.agent_card.name == "YAML Agent"
            assert result.agent_card.description == "Updated from YAML"
            assert result.deployment.llm.temperature == 0.3
            
            # Clean up
            Path(f.name).unlink() 