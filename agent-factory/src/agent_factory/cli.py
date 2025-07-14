"""
Command-line interface for Agent Factory.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from . import __version__
from .config import AgentConfiguration
from .deploy import deploy_from_config_file
from .core.runner import AgentRunner
from .harness import AgentHarness

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(name)s - %(levelname)s - %(message)s" if verbose else "%(levelname)s - %(message)s",
    )


def has_existing_schemas(config: AgentConfiguration) -> bool:
    """Check if config already has extracted schemas."""
    return any(skill.input_schema or skill.output_schema 
               for skill in config.agent_card.skills)


def validate_schema_consistency(original: AgentConfiguration, 
                               current: AgentConfiguration) -> None:
    """Validate that MCP schemas haven't changed."""
    # Create skill maps by ID for comparison
    orig_skills = {skill.id: skill for skill in original.agent_card.skills}
    curr_skills = {skill.id: skill for skill in current.agent_card.skills}
    
    # Check for missing/added skills
    if set(orig_skills.keys()) != set(curr_skills.keys()):
        raise ValueError(
            f"Skill mismatch. Original: {set(orig_skills.keys())}, "
            f"Current: {set(curr_skills.keys())}"
        )
    
    # Check each skill's schemas
    for skill_id, orig_skill in orig_skills.items():
        curr_skill = curr_skills[skill_id]
        
        if orig_skill.input_schema != curr_skill.input_schema:
            raise ValueError(f"Input schema changed for skill '{skill_id}'")
        
        if orig_skill.output_schema != curr_skill.output_schema:
            raise ValueError(f"Output schema changed for skill '{skill_id}'")


def save_agent_card(agent_card: Dict[str, Any], output_path: str) -> None:
    """Save agent card to file."""
    with open(output_path, 'w') as f:
        json.dump(agent_card, f, indent=2)
    print(f"✅ Saved agent card with schemas to: {output_path}")


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            # For lists, replace entirely (don't append)
            result[key] = value
        else:
            result[key] = value
    return result


def parse_value(value_str: str) -> Any:
    """Parse string value to appropriate type."""
    # Try to parse as JSON first (handles arrays, objects, booleans, numbers)
    try:
        return json.loads(value_str)
    except json.JSONDecodeError:
        # Return as string
        return value_str


def set_nested_value(obj: Dict[str, Any], path: str, value: Any) -> None:
    """Set a nested value using dot notation path."""
    parts = path.split('.')
    current = obj
    
    # Navigate to the parent of the target
    for part in parts[:-1]:
        # Handle array indices
        if '[' in part:
            key, index = part.split('[')
            index = int(index.rstrip(']'))
            if key not in current:
                current[key] = []
            while len(current[key]) <= index:
                current[key].append({})
            current = current[key][index]
        else:
            if part not in current:
                current[part] = {}
            current = current[part]
    
    # Set the final value
    final_key = parts[-1]
    if '[' in final_key:
        key, index = final_key.split('[')
        index = int(index.rstrip(']'))
        if key not in current:
            current[key] = []
        while len(current[key]) <= index:
            current[key].append(None)
        current[key][index] = value
    else:
        current[final_key] = value


def apply_overrides(base_config: AgentConfiguration, 
                   overrides: Dict[str, Any]) -> AgentConfiguration:
    """Apply overrides to base configuration."""
    # Get base as dict
    base_dict = base_config.model_dump()
    
    # Deep merge overrides
    merged = deep_merge(base_dict, overrides)
    
    # Validate and return
    return AgentConfiguration(**merged)



def start_app(config_path: str, port: int = 8000, output_path: str = None,
              strict: bool = False, verbose: bool = False, single_message: str = None) -> None:
    """Start the agent app (local or deployed), optionally run single message and exit."""
    try:
        print(f"🔧 Loading config from: {config_path}")
        config = AgentConfiguration.from_file(config_path)
        
        # Check if we have existing schemas
        had_schemas = has_existing_schemas(config)
        if had_schemas and verbose:
            print("📋 Using configuration with pre-extracted schemas")
        
        print(f"🤖 Starting agent: {config.agent_card.name}")
        
        # We need to run the schema extraction before starting the server
        async def init_and_start():
            runner = AgentRunner(config)
            agent = await runner.get_agent()
            
            # Check for schema conflicts if strict mode
            if had_schemas and strict:
                try:
                    validate_schema_consistency(config, runner.get_config())
                    print("✅ Schema validation passed")
                except ValueError as e:
                    print(f"❌ Schema validation failed: {e}")
                    sys.exit(1)
            
            # Save updated agent card if requested
            if output_path:
                agent_card = await runner.get_agent_card()
                save_agent_card(agent_card, output_path)
            
            # If single message mode, send message and exit
            if single_message:
                print(f"📝 Message: {single_message}")
                print("🔄 Processing...")
                
                try:
                    result = await runner.invoke(single_message)
                    print("✅ Response:")
                    print(result["messages"][-1].content)
                    return  # Exit without starting server
                    
                except Exception as e:
                    print(f"❌ Error: {str(e)}")
                    if verbose:
                        import traceback
                        traceback.print_exc()
                    raise
            
            # Otherwise start the server
            import uvicorn
            from .http.api import build_app
            app = build_app(runner)
            await uvicorn.Server(
                uvicorn.Config(app, host="0.0.0.0", port=port, reload=False)
            ).serve()
        
        # Run the async initialization and server
        asyncio.run(init_and_start())
            
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def create_from_overrides(config_path: str, apply_path: str = None, 
                         set_values: list = None, output_path: str = None,
                         verbose: bool = False) -> None:
    """Create configuration from base with overrides."""
    try:
        print(f"🔧 Loading base config from: {config_path}")
        config = AgentConfiguration.from_file(config_path)
        
        # Apply file overrides
        if apply_path:
            print(f"📝 Applying overrides from: {apply_path}")
            with open(apply_path) as f:
                if apply_path.endswith('.yaml') or apply_path.endswith('.yml'):
                    overrides = yaml.safe_load(f)
                else:
                    overrides = json.load(f)
            config = apply_overrides(config, overrides)
            print(f"✅ Applied overrides from {apply_path}")
        
        # Apply inline overrides
        if set_values:
            config_dict = config.model_dump()
            for override in set_values:
                if '=' not in override:
                    print(f"❌ Invalid override format: {override} (expected path=value)")
                    sys.exit(1)
                path, value = override.split('=', 1)
                parsed_value = parse_value(value)
                set_nested_value(config_dict, path, parsed_value)
                print(f"✅ Set {path} = {parsed_value}")
            
            # Recreate config from modified dict
            config = AgentConfiguration(**config_dict)
        
        # Save result
        if output_path:
            config.save_to_file(output_path)
            print(f"✅ Saved configuration to: {output_path}")
        else:
            # Print to stdout
            print("\n📋 Generated configuration:")
            print(json.dumps(config.model_dump(), indent=2))
            
    except Exception as e:
        print(f"❌ Failed to create configuration: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Agent Factory - Run AI agents",
        prog="agent-factory"
    )
    
    parser.add_argument("config", help="Path to agent configuration file")
    parser.add_argument("--message", "-m", help="Run single message and exit")
    parser.add_argument("--port", "-p", type=int, default=8000, 
                       help="Port for local server (default: 8000)")
    parser.add_argument("--deploy", action="store_true", 
                       help="Deploy to Modal cloud instead of running locally")
    parser.add_argument("--output", "-o", help="Save agent card with extracted schemas")
    parser.add_argument("--strict", action="store_true",
                       help="Fail if MCP schemas differ from saved config")
    parser.add_argument("--apply", help="Apply overrides from YAML/JSON file")
    parser.add_argument("--set", action="append", help="Set individual values (path=value)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    try:
        # Handle override mode
        if args.apply or args.set:
            create_from_overrides(
                args.config, 
                args.apply, 
                args.set, 
                args.output,
                args.verbose
            )
            
        elif args.deploy:
            # Deploy to Modal
            url = deploy_from_config_file(args.config)
            print(f"✅ Agent deployed successfully!")
            print(f"🌐 URL: {url}")
            print(f"📋 Health check: {url}/health")
            print(f"⚙️  Config: {url}/config")
            print(f"🤖 Agent Card: {url}/.well-known/agent.json")
            
        else:
            # Start app (either interactive server or single message mode)
            start_app(
                args.config, 
                args.port, 
                args.output,
                args.strict,
                args.verbose,
                args.message  # Pass message for single-message mode, or None for server mode
            )
            
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