"""
Simplified CLI for agent responses - Server only.
"""

import argparse
import logging
import sys
from pathlib import Path

from .config import AgentConfiguration
from .http_app import create_app
from .utils import setup_logging

logger = logging.getLogger(__name__)


def run_server(config_path: str, port: int = 8000, verbose: bool = False) -> None:
    """Run the server."""
    try:
        logger.info(f"Loading config from: {config_path}")
        config = AgentConfiguration.from_file(config_path)
        
        logger.info(f"Starting agent: {config.card.name}")
        logger.debug(f"Description: {config.card.description}")
        logger.info(f"Server starting on port {port}")
        logger.debug(f"Agent card: http://localhost:{port}/.well-known/agent.json")
        logger.debug(f"Agent card details:\n{config.card.model_dump_json(indent=2)}")
        logger.debug(f"Chat endpoint: http://localhost:{port}/chat")
        
        app = create_app(config)
        
        import uvicorn
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=port, 
            log_level="info" if verbose else "warning"
        )
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        if verbose:
            logger.exception("Full traceback:")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Agent Responses - AI agent HTTP server using OpenAI Responses API",
        prog="agent-responses"
    )
    
    parser.add_argument("config", help="Path to agent configuration file")
    parser.add_argument("--port", "-p", type=int, default=8000,
                       help="Port for server (default: 8000)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    run_server(args.config, args.port, args.verbose)


if __name__ == "__main__":
    main() 