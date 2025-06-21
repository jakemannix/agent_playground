"""
CLI interface for agent-factory.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from .config import AgentConfig
from .deploy import deploy_from_config_file
from .harness import AgentHarness


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(name)s - %(levelname)s - %(message)s" if verbose else "%(levelname)s - %(message)s",
    )


async def test_agent(config_path: str, message: str, local: bool = True, verbose: bool = False) -> None:
    """Test an agent locally or on Modal."""
    try:
        print(f"🔧 Loading config from: {config_path}")
        config = AgentConfig.from_file(config_path)
        
        print(f"🤖 Testing agent: {config.name}")
        print(f"📝 Message: {message}")
        print(f"🏠 Running {'locally' if local else 'on Modal'}")
        
        if verbose:
            print(f"🔍 Agent config summary:")
            print(f"  - Model: {config.model}")
            print(f"  - Temperature: {config.temperature}")
            print(f"  - Max tokens: {config.max_tokens}")
            print(f"  - MCP tools: {len(config.mcp_tools)}")
            for tool in config.mcp_tools:
                print(f"    - {tool.name}: {tool.config}")
        
        if local:
            # Run locally using AgentHarness
            harness = AgentHarness(config)
            print("⏳ Initializing locally...")
            
            if verbose:
                print("🔍 Starting agent initialization...")
                
            await harness.initialize()
            
            if verbose:
                print(f"🔍 Agent initialized with {len(harness.tools)} tools:")
                for tool in harness.tools:
                    print(f"    - {tool.name}: {tool.description}")
            
            print("🔄 Processing...")
            result = await harness.invoke(message)
        else:
            # Run on Modal using deploy functions
            print("⏳ Invoking on Modal...")
            from .deploy import agent_invoke
            result = await agent_invoke.remote.aio(config.model_dump(), message)
        
        print("✅ Response:")
        # Handle LangGraph response which may contain non-JSON serializable objects
        if isinstance(result, dict) and 'messages' in result:
            # Extract just the text content from messages
            messages = result.get('messages', [])
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, 'content'):
                    print(last_message.content)
                else:
                    print(str(last_message))
            else:
                print("No messages in response")
        else:
            try:
                print(json.dumps(result, indent=2))
            except TypeError:
                # Fallback to string representation
                print(str(result))
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def validate_config(config_path: str) -> None:
    """Validate an agent configuration file."""
    try:
        config = AgentConfig.from_file(config_path)
        print(f"✅ Configuration is valid!")
        print(f"📋 Agent: {config.name}")
        print(f"🧠 Model: {config.model}")
        print(f"🔧 Tools: {len(config.mcp_tools)}")
        print(f"🚀 Type: {config.agent_type}")
        
    except Exception as e:
        print(f"❌ Configuration invalid: {e}")
        sys.exit(1)


def create_example_config(output_path: str) -> None:
    """Create an example configuration file."""
    example_config = {
        "name": "Example Agent",
        "description": "An example AI agent for demonstration",
        "url": "https://your-domain.com/example-agent",
        "system_prompt": "You are a helpful AI assistant. Use the available tools to help users with their requests.",
        "model": "claude-3-5-sonnet-20241022",
        "temperature": 0.7,
        "agent_type": "react",
        "version": "1.0.0",
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": False
        },
        "skills": [
            {
                "id": "example_skill",
                "name": "Example Skill", 
                "description": "An example skill for demonstration",
                "tags": ["example", "demo"],
                "examples": ["Help me with something"]
            }
        ],
        "mcp_tools": [
            {
                "name": "example_tool",
                "server_path": "tools/example_mcp_server.py",
                "config": {
                    "timeout": 30
                }
            }
        ],
        "modal_config": {
            "cpu": 1.0,
            "memory": 2048,
            "timeout": 300,
            "keep_warm": 0
        }
    }
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(example_config, f, indent=2)
    
    print(f"✅ Example configuration created: {output_path}")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Agent Factory - Deploy and manage AI agents",
        prog="agent-factory"
    )
    
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Deploy command
    deploy_parser = subparsers.add_parser("deploy", help="Deploy an agent to Modal")
    deploy_parser.add_argument("config", help="Path to agent configuration file")
    deploy_parser.add_argument("--name", help="Deployment name (optional)")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test an agent locally or on Modal")
    test_parser.add_argument("config", help="Path to agent configuration file")
    test_parser.add_argument("message", help="Test message to send to agent")
    test_parser.add_argument("--modal", action="store_true", 
                           help="Run test on Modal instead of locally (default is local)")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate agent configuration")
    validate_parser.add_argument("config", help="Path to agent configuration file")
    
    # Example command
    example_parser = subparsers.add_parser("example", help="Create example configuration")
    example_parser.add_argument("--output", "-o", default="example_agent.json", 
                              help="Output path for example config")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "deploy":
            url = deploy_from_config_file(args.config, args.name)
            print(f"✅ Agent deployed successfully!")
            print(f"🌐 URL: {url}")
            print(f"📋 Health check: {url}/health")
            print(f"⚙️  Config: {url}/config")
            
        elif args.command == "test":
            # Determine if running locally or on Modal
            local = not args.modal  # Default to local unless --modal is specified
            asyncio.run(test_agent(args.config, args.message, local, args.verbose))
            
        elif args.command == "validate":
            validate_config(args.config)
            
        elif args.command == "example":
            create_example_config(args.output)
            
    except KeyboardInterrupt:
        print("\n👋 Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()