"""Test CLI functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agent_factory.cli import create_example_config, validate_config
from agent_factory.config import AgentConfig


class TestCLI:
    """Test CLI functions."""

    def test_create_example_config(self):
        """Test creating example configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "example.json"
            
            create_example_config(str(config_path))
            
            assert config_path.exists()
            
            # Verify the config is valid
            with open(config_path) as f:
                config_data = json.load(f)
            
            assert config_data["name"] == "Example Agent"
            assert config_data["agent_type"] == "react"
            assert "mcp_tools" in config_data
            assert "modal_config" in config_data

    def test_validate_config_valid(self, capsys):
        """Test validating a valid configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "valid.json"
            
            config_data = {
                "name": "Test Agent",
                "description": "A test agent",
                "url": "https://example.com/agent",
                "system_prompt": "You are a test agent.",
                "version": "1.0.0"
            }
            
            with open(config_path, 'w') as f:
                json.dump(config_data, f)
            
            validate_config(str(config_path))
            
            captured = capsys.readouterr()
            assert "✅ Configuration is valid!" in captured.out
            assert "Test Agent" in captured.out

    def test_validate_config_invalid(self):
        """Test validating an invalid configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "invalid.json"
            
            # Missing required fields
            config_data = {
                "name": "Test Agent"
                # Missing description, url, system_prompt
            }
            
            with open(config_path, 'w') as f:
                json.dump(config_data, f)
            
            with pytest.raises(SystemExit):
                validate_config(str(config_path))

    def test_validate_config_file_not_found(self):
        """Test validating non-existent configuration file."""
        with pytest.raises(SystemExit):
            validate_config("nonexistent.json")

    @pytest.mark.asyncio
    @patch('agent_factory.cli.AgentHarness')
    async def test_test_agent_success(self, mock_harness_class, capsys):
        """Test successful agent testing."""
        from agent_factory.cli import test_agent
        
        # Mock harness
        mock_harness = AsyncMock()
        mock_harness.invoke.return_value = {"response": "test response"}
        mock_harness_class.return_value = mock_harness
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.json"
            
            config_data = {
                "name": "Test Agent",
                "description": "A test agent", 
                "url": "https://example.com/agent",
                "system_prompt": "You are a test agent.",
                "version": "1.0.0"
            }
            
            with open(config_path, 'w') as f:
                json.dump(config_data, f)
            
            await test_agent(str(config_path), "test message")
            
            captured = capsys.readouterr()
            assert "🤖 Testing agent: Test Agent" in captured.out
            assert "✅ Response:" in captured.out
            
            # Verify harness was called correctly
            mock_harness.initialize.assert_called_once()
            mock_harness.invoke.assert_called_once_with("test message")

    @pytest.mark.asyncio
    async def test_test_agent_failure(self):
        """Test agent testing failure."""
        from agent_factory.cli import test_agent
        
        with pytest.raises(SystemExit):
            await test_agent("nonexistent.json", "test message")