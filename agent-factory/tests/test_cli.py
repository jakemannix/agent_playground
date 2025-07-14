"""
Tests for CLI functionality.
"""

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from agent_factory.cli import run_single_message, setup_logging
from agent_factory.config import AgentConfiguration


class TestCLI:
    """Test CLI functions."""

    def test_setup_logging_default(self):
        """Test default logging setup."""
        setup_logging()
        # Just verify it doesn't crash
        assert True

    def test_setup_logging_verbose(self):
        """Test verbose logging setup."""
        setup_logging(verbose=True)
        # Just verify it doesn't crash
        assert True

    @pytest.mark.asyncio
    @patch('agent_factory.cli.AgentHarness')
    async def test_run_single_message_success(self, mock_harness_class, capsys):
        """Test successful single message run."""
        # Mock harness
        mock_harness = AsyncMock()
        mock_harness.tools = []
        mock_harness.invoke.return_value = {"messages": [type('Message', (), {'content': 'test response'})()]}
        mock_harness_class.return_value = mock_harness
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.json"
            
            config_data = {
                "agent_card": {
                    "name": "Test Agent",
                    "description": "A test agent",
                    "url": "https://example.com/agent",
                    "version": "1.0.0",
                    "defaultInputModes": ["textMessage"],
                    "defaultOutputModes": ["textMessage"],
                    "agent_type": "react",
                    "skills": []
                },
                "deployment": {
                    "llm": {
                        "model": "claude-3-5-sonnet-20241022",
                        "temperature": 0.7,
                        "system_prompt": "You are a test agent."
                    }
                }
            }
            
            with open(config_path, 'w') as f:
                json.dump(config_data, f)
            
            config = AgentConfiguration.from_file(str(config_path))
            args = argparse.Namespace(verbose=False)
            
            await run_single_message(config, "test message", args)
            
            captured = capsys.readouterr()
            assert "🤖 Running agent: Test Agent" in captured.out
            assert "✅ Response:" in captured.out
            
            # Verify harness was called correctly
            mock_harness.initialize.assert_called_once()
            mock_harness.invoke.assert_called_once_with("test message")

    @pytest.mark.asyncio
    @patch('agent_factory.cli.AgentHarness')
    async def test_run_single_message_failure(self, mock_harness_class):
        """Test single message run failure."""
        # Mock harness to raise an error during initialization
        mock_harness = AsyncMock()
        mock_harness.initialize.side_effect = ValueError("ANTHROPIC_API_KEY not found in environment")
        mock_harness_class.return_value = mock_harness
        
        config_data = {
            "agent_card": {
                "name": "Test Agent",
                "description": "A test agent",
                "url": "https://example.com/agent",
                "version": "1.0.0",
                "defaultInputModes": ["textMessage"],
                "defaultOutputModes": ["textMessage"],
                "agent_type": "react",
                "skills": []
            },
            "deployment": {
                "llm": {
                    "model": "claude-3-5-sonnet-20241022",
                    "temperature": 0.7,
                    "system_prompt": "You are a test agent."
                }
            }
        }
        
        config = AgentConfiguration(**config_data)
        args = argparse.Namespace(verbose=False)
        
        # This should fail because the harness raises an error
        with pytest.raises(ValueError):
            await run_single_message(config, "test message", args)

    @pytest.mark.asyncio
    @patch('agent_factory.cli.AgentHarness')
    async def test_run_single_message_verbose(self, mock_harness_class, capsys):
        """Test single message run with verbose output."""
        # Mock harness
        mock_harness = AsyncMock()
        mock_harness.tools = []
        mock_harness.invoke.return_value = {"messages": [type('Message', (), {'content': 'test response'})()]}
        mock_harness_class.return_value = mock_harness
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test.json"
            
            config_data = {
                "agent_card": {
                    "name": "Test Agent",
                    "description": "A test agent",
                    "url": "https://example.com/agent",
                    "version": "1.0.0",
                    "defaultInputModes": ["textMessage"],
                    "defaultOutputModes": ["textMessage"],
                    "agent_type": "react",
                    "skills": [
                        {
                            "id": "test_skill",
                            "name": "Test Skill",
                            "description": "A test skill",
                            "tags": ["test"],
                            "optional": True,
                            "mcp_config": {
                                "transport": "stdio",
                                "command": "python",
                                "args": ["test.py"]
                            }
                        }
                    ]
                },
                "deployment": {
                    "llm": {
                        "model": "claude-3-5-sonnet-20241022",
                        "temperature": 0.7,
                        "system_prompt": "You are a test agent."
                    }
                }
            }
            
            with open(config_path, 'w') as f:
                json.dump(config_data, f)
            
            config = AgentConfiguration.from_file(str(config_path))
            args = argparse.Namespace(verbose=True)
            
            await run_single_message(config, "test message", args)
            
            captured = capsys.readouterr()
            assert "🔍 Agent config summary:" in captured.out
            assert "Model: claude-3-5-sonnet-20241022" in captured.out
            assert "Skills: 1" in captured.out
            assert "Test Skill: A test skill" in captured.out