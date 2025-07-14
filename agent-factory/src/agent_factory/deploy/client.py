"""Deployment client for Modal cloud."""

import logging
from typing import Optional

from ..config import AgentConfiguration

logger = logging.getLogger(__name__)


def deploy_from_config_file(config_path: str, name: Optional[str] = None) -> str:
    """Deploy an agent from a configuration file.
    
    Note: This is a placeholder. Actual deployment uses the Modal CLI:
    modal run agent_factory/deploy/modal_app.py --env AGENT_CFG_PATH=your_config.json
    """
    config = AgentConfiguration.from_file(config_path)
    return deploy_agent(config, name)


def deploy_agent(config: AgentConfiguration, name: Optional[str] = None) -> str:
    """Deploy an agent to Modal cloud.
    
    Note: This is a placeholder function. Actual deployment to Modal should be done
    using the Modal CLI directly:
    
    1. Install modal: pip install modal
    2. Set up Modal token: modal setup
    3. Deploy: modal run agent_factory/deploy/modal_app.py --env AGENT_CFG_PATH=config.json
    
    For local development, use the regular CLI:
    agent-factory config.json
    
    This function exists for API compatibility but does not perform actual deployment.
    """
    
    if not name:
        name = config.agent_card.name.lower().replace(" ", "-").replace("_", "-")

    logger.warning(
        f"deploy_agent() is a placeholder. To deploy '{config.agent_card.name}':\n"
        f"  modal run agent_factory/deploy/modal_app.py --env AGENT_CFG_PATH=<config_file>"
    )
    
    # Return a mock URL for compatibility
    url = f"https://{name}--agent-factory.modal.run"
    logger.info(f"Mock deployment URL: {url}")
    
    return url 