"""
Interactive CLI client for agent responses.
"""

import argparse
import asyncio
import json
import logging
import sys
from typing import Optional

import httpx

from .utils import setup_logging

logger = logging.getLogger(__name__)


class AgentClient:
    """HTTP client for agent responses."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
    
    async def get_agent_info(self) -> dict:
        """Get agent card information."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/.well-known/agent.json", timeout=5.0)
            response.raise_for_status()
            return response.json()
    
    async def send_message(self, message: str) -> dict:
        """Send a message to the agent."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat",
                json={"message": message},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()


def _format_usage(usage: dict, verbose: bool) -> str:
    """Format usage info based on verbosity."""
    if verbose:
        return f"Usage: {json.dumps(usage, indent=2)}"
    else:
        total = usage.get('total_tokens', 0)
        input_tokens = usage.get('input_tokens', 0) 
        output_tokens = usage.get('output_tokens', 0)
        return f"Tokens: {total} total ({input_tokens} in, {output_tokens} out)"


async def single_message_mode(client: AgentClient, message: str, verbose: bool) -> None:
    """Send a single message and exit."""
    try:
        logger.info(f"Sending message: {message}")
        result = await client.send_message(message)
        
        print(result['response'])
        
        if result.get('usage') and verbose:
            print(f"\n{_format_usage(result['usage'], verbose)}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


async def interactive_mode(client: AgentClient, verbose: bool) -> None:
    """Run interactive chat mode."""
    logger.info("Starting interactive mode")
    print("Type 'quit' or 'exit' to leave")
    print("=" * 40)
    
    while True:
        try:
            message = input("You: ").strip()
            
            if message.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
                
            if not message:
                continue
                
            result = await client.send_message(message)
            print(f"Agent: {result['response']}")
            
            if result.get('usage') and verbose:
                print(f"  {_format_usage(result['usage'], verbose)}")
            
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"Error: {e}")


async def main_async(args) -> None:
    """Main async function."""
    client = AgentClient(f"http://localhost:{args.port}")
    
    # Get agent info to verify connection
    try:
        agent_info = await client.get_agent_info()
        agent_name = agent_info.get('name', 'Unknown Agent')
        
        if args.verbose:
            logger.info(f"Connected to: {agent_name}")
            logger.debug(f"Agent info: {json.dumps(agent_info, indent=2)}")
        else:
            logger.info(f"Connected to: {agent_name}")
        
    except Exception as e:
        logger.error(f"Failed to connect to server at http://localhost:{args.port}: {e}")
        logger.info("Make sure the server is running with: agent-responses <config-file>")
        sys.exit(1)
    
    if args.message:
        await single_message_mode(client, args.message, args.verbose)
    else:
        await interactive_mode(client, args.verbose)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Agent Responses Client - Interactive chat with AI agents",
        prog="agent-responses-chat"
    )
    
    parser.add_argument("--port", "-p", type=int, default=8000,
                       help="Port of the agent server (default: 8000)")
    parser.add_argument("--message", "-m", help="Send single message and exit")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main() 