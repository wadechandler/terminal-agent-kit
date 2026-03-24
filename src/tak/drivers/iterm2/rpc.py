"""iTerm2 RPC functions for tak.

These functions are registered with iTerm2 and can be bound to
keybindings via Preferences > Keys > Invoke Script Function.

Each RPC function communicates with the daemon's AgentManager and
SessionRegistry to perform agent management operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tak.core.agent_manager import AgentManager
    from tak.core.session_registry import SessionRegistry

logger = logging.getLogger(__name__)


async def _register_tak_list_agents(
    connection: Any,
    app_getter: Any,
    agent_manager: AgentManager,
) -> None:
    import iterm2

    @iterm2.RPC
    async def tak_list_agents(
        session_id: str = iterm2.Reference("id"),  # type: ignore[arg-type]
    ) -> None:
        """List all managed agents. Injects output into the calling session."""
        app = await app_getter()
        session = app.get_session_by_id(session_id)
        if session is None:
            return

        agents = agent_manager.list_agents()
        if not agents:
            await session.async_inject(b"\r\n[tak] No agents running.\r\n")
            return

        lines = ["\r\n[tak] Agents:\r\n"]
        for handle in agents:
            model_str = f" [{handle.model}]" if handle.model else ""
            tabs_str = f" tabs={handle.associated_tabs}" if handle.associated_tabs else ""
            lines.append(
                f"  {handle.name}  {handle.provider_name}{model_str}  "
                f"{handle.status.value}{tabs_str}\r\n"
            )
        await session.async_inject("".join(lines).encode())

    await tak_list_agents.async_register(connection)  # type: ignore[attr-defined]
    logger.info("Registered RPC: tak_list_agents")


async def _register_tak_switch_to_agent(
    connection: Any,
    app_getter: Any,
    session_registry: SessionRegistry,
) -> None:
    import iterm2

    @iterm2.RPC
    async def tak_switch_to_agent(
        agent_name: str,
        session_id: str = iterm2.Reference("id"),  # type: ignore[arg-type]
    ) -> None:
        """Activate the tab associated with the named agent."""
        sessions = session_registry.get_sessions(agent_name)
        if not sessions:
            app = await app_getter()
            session = app.get_session_by_id(session_id)
            if session:
                await session.async_inject(
                    f"\r\n[tak] No tabs for agent '{agent_name}'.\r\n".encode()
                )
            return

        app = await app_getter()
        target = app.get_session_by_id(sessions[0])
        if target is not None:
            await target.async_activate(select_tab=True, order_window_front=True)

    await tak_switch_to_agent.async_register(connection)  # type: ignore[attr-defined]
    logger.info("Registered RPC: tak_switch_to_agent")


async def _register_tak_stop_agent(
    connection: Any,
    app_getter: Any,
    agent_manager: AgentManager,
) -> None:
    import iterm2

    @iterm2.RPC
    async def tak_stop_agent(
        agent_name: str,
        session_id: str = iterm2.Reference("id"),  # type: ignore[arg-type]
    ) -> None:
        """Stop the named agent."""
        app = await app_getter()
        session = app.get_session_by_id(session_id)

        try:
            await agent_manager.stop(agent_name)
            if session:
                await session.async_inject(
                    f"\r\n[tak] Stopped agent '{agent_name}'.\r\n".encode()
                )
        except ValueError as exc:
            if session:
                await session.async_inject(
                    f"\r\n[tak] Error: {exc}\r\n".encode()
                )

    await tak_stop_agent.async_register(connection)  # type: ignore[attr-defined]
    logger.info("Registered RPC: tak_stop_agent")


async def _register_tak_agent_menu(
    connection: Any,
    app_getter: Any,
) -> None:
    import iterm2

    @iterm2.RPC
    async def tak_agent_menu(
        session_id: str = iterm2.Reference("id"),  # type: ignore[arg-type]
    ) -> None:
        """Open the tak TUI dashboard in a horizontal split pane."""
        app = await app_getter()
        session = app.get_session_by_id(session_id)
        if session is None:
            return

        try:
            new_session = await session.async_split_pane(vertical=False)
            await new_session.async_send_text("tak menu\n")
        except Exception as exc:
            logger.warning("tak_agent_menu: could not split pane: %s", exc)
            await session.async_inject(
                b"\r\n[tak] Could not open TUI pane -- run `tak menu` manually.\r\n"
            )

    await tak_agent_menu.async_register(connection)  # type: ignore[attr-defined]
    logger.info("Registered RPC: tak_agent_menu")


async def register_rpcs(
    connection: Any,
    agent_manager: AgentManager,
    session_registry: SessionRegistry,
    app_getter: Any,
) -> None:
    """Register all tak RPC functions with iTerm2.

    Users bind these to keybindings in Preferences > Keys.

    Args:
        connection: An ``iterm2.Connection`` instance.
        agent_manager: The daemon's agent manager.
        session_registry: The daemon's session registry.
        app_getter: Callable that returns the ``iterm2.App`` instance.
    """
    await _register_tak_list_agents(connection, app_getter, agent_manager)
    await _register_tak_switch_to_agent(connection, app_getter, session_registry)
    await _register_tak_stop_agent(connection, app_getter, agent_manager)
    await _register_tak_agent_menu(connection, app_getter)
