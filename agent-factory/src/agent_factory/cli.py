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
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def test_agent(config_path: str, message: str) -> None:
    """Test an agent locally."""
    try:
        config = AgentConfig.from_file(config_path)
        harness = AgentHarness(config)
        
        print(f"🤖 Testing agent: {config.name}")
        print(f"📝 Message: {message}")
        print("⏳ Initializing...")
        
        await harness.initialize()
        
        print("🔄 Processing...")
        result = await harness.invoke(message)
        
        print("✅ Response:")
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
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
        "model": "claude-3-5-sonnet-20241022",
        "temperature": 0.7,
        "system_prompt": "You are a helpful AI assistant. Use the available tools to help users with their requests.",
        "agent_type": "react",
        "mcp_tools": [
            {
                "name": "calculator",
                "server_path": "tools/calculator_server.py",
                "config": {
                    "precision": 10
                }
            }
        ],
        "modal_config": {
            "cpu": 1.0,
            "memory": 2048,
            "timeout": 300,
            "keep_warm": 1
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
    test_parser = subparsers.add_parser("test", help="Test an agent locally")
    test_parser.add_argument("config", help="Path to agent configuration file")
    test_parser.add_argument("message", help="Test message to send to agent")
    
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
            asyncio.run(test_agent(args.config, args.message))
            
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