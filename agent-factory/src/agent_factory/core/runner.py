from __future__ import annotations

from typing import Any, Dict, Optional

from ..config import AgentConfiguration
from ..harness import AgentHarness


class AgentRunner:
    """Lightweight wrapper that lazily instantiates and caches an AgentHarness.

    This class contains *no* FastAPI or Modal imports so it can be safely unit-
    tested without heavy external dependencies.  All higher-level surfaces
    (HTTP, CLI, Modal) should depend on `AgentRunner` rather than directly on
    `AgentHarness` so we keep a clean separation between *business logic* and
    *framework* code.
    """

    def __init__(self, cfg: AgentConfiguration):
        self.cfg: AgentConfiguration = cfg
        self._harness: Optional[AgentHarness] = None

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    async def _ensure_ready(self) -> None:
        """Create & initialise the underlying harness exactly once."""
        if self._harness is None:
            self._harness = AgentHarness(self.cfg)
            await self._harness.initialize()

    # ------------------------------------------------------------------
    # Public API – these are the only methods higher layers should call
    # ------------------------------------------------------------------
    async def invoke(self, message: str, **kwargs: Any) -> Dict[str, Any]:
        """Invoke the agent and return the result.

        Parameters
        ----------
        message
            The user message / prompt.
        **kwargs
            Additional keyword arguments forwarded to the underlying harness.
        """
        await self._ensure_ready()
        assert self._harness  # for type checkers
        return await self._harness.invoke(message, **kwargs)

    async def get_agent(self):
        """Get the initialized LangGraph agent."""
        await self._ensure_ready()
        assert self._harness  # for type checkers
        return self._harness.agent
    
    async def get_harness(self) -> AgentHarness:
        """Get the initialized agent harness."""
        await self._ensure_ready()
        assert self._harness  # for type checkers
        return self._harness
    
    def get_config(self) -> AgentConfiguration:
        """Get the agent configuration."""
        return self.cfg
    
    async def get_agent_card(self) -> Dict[str, Any]:
        """Get the agent card with updated schemas."""
        harness = await self.get_harness()
        return harness.get_agent_card()
    
    async def get_tool_count(self) -> int:
        """Get the number of loaded tools."""
        harness = await self.get_harness()
        return len(harness.tools) 