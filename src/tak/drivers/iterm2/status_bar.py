"""iTerm2 status bar component for tak.

Displays the current tab's agent info by reading ``user.tak_*`` session
variables. Auto-updates when variables change.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

COMPONENT_IDENTIFIER = "com.tak.agent.status"


async def register_status_bar(connection: Any) -> None:
    """Register the tak status bar component with iTerm2.

    The component reads ``user.tak_agent_id`` and ``user.tak_agent_status``
    from the current session and displays them as ``tak: <name> (<status>)``.
    When no agent is associated, shows ``tak: --``.

    Args:
        connection: An ``iterm2.Connection`` instance.
    """
    import iterm2

    component = iterm2.StatusBarComponent(
        short_description="tak agent",
        detailed_description="Shows the agent associated with this terminal tab",
        knobs=[],
        exemplar="tak: my-agent (running)",
        update_cadence=None,
        identifier=COMPONENT_IDENTIFIER,
    )

    @iterm2.StatusBarRPC
    async def _status_bar_callback(
        knobs: iterm2.Reference,  # type: ignore[type-arg]
        tak_agent_id: str = iterm2.Reference("user.tak_agent_id?"),
        tak_agent_status: str = iterm2.Reference("user.tak_agent_status?"),
        tak_agent_model: str = iterm2.Reference("user.tak_agent_model?"),
    ) -> str:
        agent_id = tak_agent_id or "--"
        if not tak_agent_id:
            return "tak: --"
        status = tak_agent_status or "?"
        model_suffix = f" [{tak_agent_model}]" if tak_agent_model else ""
        return f"tak: {agent_id} ({status}){model_suffix}"

    await component.async_register(connection, _status_bar_callback)
    logger.info("Registered tak status bar component (%s)", COMPONENT_IDENTIFIER)
