"""iTerm2 AutoLaunch daemon for tak.

This module is the entry point for the iTerm2 daemon that runs inside
iTerm2's Python API runtime. It manages agent lifecycles, hosts the
IPC server for CLI communication, and registers UI elements.

Deployment:
    Symlink or copy to ``~/Library/Application Support/iTerm2/Scripts/AutoLaunch/``
    and it will start automatically when iTerm2 launches.

Usage as a module:
    ``python -m tak.drivers.iterm2.daemon`` (requires iTerm2 to be running
    with the Python API enabled).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import signal
import sys
from typing import TYPE_CHECKING, Any

def _ensure_tak_importable() -> None:
    """Add the project ``src/`` directory to ``sys.path`` when running inside iTerm2's Python.

    iTerm2 AutoLaunch scripts run under iTerm2's bundled Python (``iterm2env``),
    which doesn't have ``tak`` installed.  Since the daemon is symlinked from
    ``~/Library/Application Support/iTerm2/Scripts/AutoLaunch/tak_daemon.py``
    back to the project tree, we resolve the symlink and derive the ``src/``
    directory to make all ``tak.*`` imports work.
    """
    try:
        import tak  # noqa: F401 — already importable, nothing to do
        return
    except ImportError:
        pass

    real_path = os.path.realpath(__file__)
    # daemon.py lives at <project>/src/tak/drivers/iterm2/daemon.py
    src_dir = os.path.normpath(
        os.path.join(os.path.dirname(real_path), os.pardir, os.pardir, os.pardir)
    )
    if os.path.isdir(os.path.join(src_dir, "tak")) and src_dir not in sys.path:
        sys.path.insert(0, src_dir)

_ensure_tak_importable()

if TYPE_CHECKING:
    from tak.core.agent_manager import AgentManager
    from tak.core.session_registry import SessionRegistry
    from tak.core.state import StateManager
    from tak.providers.acp import ACPProvider
    from tak.providers.acp_session import PermissionRequest
    from tak.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_ITERM_SESSION_PREFIX_RE = re.compile(r"^w\d+t\d+p\d+:")

_PERMISSION_TIMEOUT = 120.0
_PERIODIC_SAVE_INTERVAL = 30.0
_DECISION_MAP: dict[str, str] = {
    "y": "allow-once",
    "n": "reject-once",
    "a": "allow-always",
}


async def main(connection: Any) -> None:
    """Daemon entry point, called by ``iterm2.run_forever(main)``.

    Sets up:
    - AgentManager with providers loaded from ``agents.yaml``
    - SessionRegistry for tab-agent associations
    - StateManager for persistence
    - IPC server for CLI communication
    - AdHocManager for quick questions
    - Permission relay for headless ACP agents
    - Status bar component
    - RPC functions for keybindings
    - Periodic state save (every 30 s)

    Args:
        connection: An ``iterm2.Connection`` from iTerm2.
    """
    import shutil

    import iterm2

    from tak.core.adhoc import AdHocManager
    from tak.core.agent_manager import AgentManager
    from tak.core.config import load_agents_config, load_config
    from tak.core.session_registry import SessionRegistry
    from tak.core.state import StateManager
    from tak.drivers.iterm2.rpc import register_rpcs
    from tak.drivers.iterm2.status_bar import register_status_bar
    from tak.ipc.server import IPCServer
    from tak.providers.acp import ACPProvider

    logger.info("tak daemon starting")
    logger.info(
        "Environment: python=%s, version=%s, pid=%d",
        sys.executable,
        sys.version.split()[0],
        os.getpid(),
    )
    logger.info("PATH: %s", os.environ.get("PATH", "(unset)"))
    for name in ("cursor", "claude", "goose"):
        loc = shutil.which(name)
        if loc:
            logger.info("Found CLI: %s -> %s", name, loc)

    registry = SessionRegistry()

    agents_config = load_agents_config()
    default_config = load_config()
    providers = _build_providers_from_config(agents_config)

    manager = AgentManager()
    for provider_name, provider in providers.items():
        manager.register_provider(provider_name, provider)

    if not providers:
        logger.warning(
            "No providers loaded from config; falling back to cursor-acp default"
        )
        from tak.providers.cursor_acp import CursorACPProvider

        fallback = CursorACPProvider()
        manager.register_provider("cursor-acp", fallback)
        providers = {"cursor-acp": fallback}

    for _provider_name, provider in providers.items():
        if isinstance(provider, ACPProvider):
            _wire_permission_relay(provider, registry, connection, manager)

    state_mgr = StateManager()
    manager.set_state_manager(state_mgr, registry)

    app = await iterm2.async_get_app(connection)
    available_sessions = {
        session.session_id
        for window in app.windows
        for tab in window.tabs
        for session in tab.sessions
    }
    logger.info(
        "iTerm2 app: %d window(s), %d session(s)",
        len(app.windows),
        len(available_sessions),
    )
    await _restore_full_state(manager, registry, state_mgr, available_sessions)

    adhoc_config = default_config.get("adhoc", {})
    adhoc_provider = adhoc_config.get("provider", "cursor-acp")
    adhoc_model: str | None = adhoc_config.get("model")
    adhoc_auto_stop: float = float(adhoc_config.get("auto_stop_after", 300))
    adhoc_mgr = AdHocManager(
        agent_manager=manager,
        provider_name=adhoc_provider,
        model=adhoc_model,
        auto_stop_after=adhoc_auto_stop,
    )

    async def _activate_tab(session_id: str) -> None:
        app = await iterm2.async_get_app(connection)
        target = app.get_session_by_id(session_id)
        if target is None:
            raise ValueError(f"Tab session {session_id} no longer exists")
        await target.async_activate(select_tab=True, order_window_front=True)

    ipc = IPCServer(
        agent_manager=manager,
        providers=providers,
        adhoc_manager=adhoc_mgr,
        session_registry=registry,
        activate_tab=_activate_tab,
    )
    await ipc.start()

    await register_status_bar(connection)

    async def get_app() -> Any:
        return await iterm2.async_get_app(connection)

    await register_rpcs(connection, manager, registry, get_app)

    periodic_task = asyncio.create_task(
        _periodic_save(state_mgr, manager, registry)
    )

    logger.info(
        "tak daemon ready -- IPC on %s, %d provider(s), status bar + RPCs registered",
        ipc.socket_path,
        len(providers),
    )

    shutdown_event = asyncio.Event()

    def _request_shutdown(sig: int) -> None:
        logger.info("Received %s, initiating graceful shutdown", signal.Signals(sig).name)
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _request_shutdown, sig)

    try:
        await shutdown_event.wait()
    finally:
        periodic_task.cancel()
        await _graceful_shutdown(manager, ipc)
        state_mgr.save(manager.list_agents(), registry.all_associations())
        logger.info("tak daemon stopped")


async def _periodic_save(
    state_mgr: StateManager,
    manager: AgentManager,
    registry: SessionRegistry,
) -> None:
    """Save state every ``_PERIODIC_SAVE_INTERVAL`` seconds as a safety net.

    Args:
        state_mgr: The ``StateManager`` to save to.
        manager: The ``AgentManager`` to snapshot.
        registry: The session registry for associations.
    """
    while True:
        await asyncio.sleep(_PERIODIC_SAVE_INTERVAL)
        try:
            state_mgr.save(manager.list_agents(), registry.all_associations())
            logger.debug("Periodic state save complete")
        except Exception as exc:
            logger.warning("Periodic state save failed: %s", exc)


async def _graceful_shutdown(
    manager: AgentManager,
    ipc: Any,
) -> None:
    """Stop all running agents and shut down the IPC server.

    Called during graceful shutdown (SIGTERM/SIGINT). Each agent is stopped
    with a short timeout so the daemon doesn't hang indefinitely.

    Args:
        manager: The ``AgentManager`` with running agents to stop.
        ipc: The ``IPCServer`` to shut down.
    """
    for handle in list(manager.running_agents()):
        try:
            await asyncio.wait_for(manager.stop(handle.name), timeout=5.0)
            logger.info("Stopped agent %r", handle.name)
        except TimeoutError:
            logger.warning("Timed out stopping agent %r; abandoning", handle.name)
        except Exception:
            logger.exception("Error stopping agent %r", handle.name)

    try:
        await ipc.stop()
    except Exception:
        logger.debug("Error stopping IPC server", exc_info=True)


def _build_providers_from_config(
    agents_config: dict[str, Any],
) -> dict[str, BaseProvider]:
    """Build provider instances from the agents configuration dict.

    Reads the ``providers`` section of ``agents.yaml``.  Each entry must
    have a ``type`` field of ``"acp"`` or ``"terminal"``.  Unknown types
    are skipped with a warning.

    Args:
        agents_config: Parsed YAML dict (typically from ``load_agents_config()``).

    Returns:
        Mapping of provider name → provider instance.
    """
    from tak.providers.acp import ACPProvider
    from tak.providers.terminal_session import TerminalSessionProvider

    providers: dict[str, BaseProvider] = {}

    for pname, pdef in agents_config.get("providers", {}).items():
        provider_type = pdef.get("type", "acp")
        display_name: str = pdef.get("name", pname)
        command: list[str] = pdef.get("command", [])

        if provider_type == "acp":
            providers[pname] = ACPProvider(
                name=display_name,
                command=command,
                auth_method=pdef.get("auth_method", "env"),
                list_models_command=pdef.get("list_models_command"),
            )
        elif provider_type == "terminal":
            providers[pname] = TerminalSessionProvider(
                name=display_name,
                command=command,
            )
        else:
            logger.warning(
                "Unknown provider type %r for %r in agents.yaml; skipping",
                provider_type,
                pname,
            )

    return providers


def _wire_permission_relay(
    provider: ACPProvider,
    registry: SessionRegistry,
    connection: Any,
    agent_manager: AgentManager,
) -> None:
    """Set up callbacks so headless ACP permission requests use per-agent policy.

    The callback consults the agent's ``permission_policy`` to decide how to
    respond.  Only the ``PROMPT`` policy actually relays to the terminal tab;
    the others respond automatically with appropriate logging.

    Args:
        provider: An :class:`~tak.providers.acp.ACPProvider` instance.
        registry: The session registry for tab-agent lookups.
        connection: The ``iterm2.Connection`` for keystroke monitoring.
        agent_manager: The ``AgentManager`` for looking up agent handles.
    """
    from tak.core.agent_manager import PermissionPolicy

    async def handle_permission(request: PermissionRequest) -> str:
        import iterm2

        description = request.description or request.tool_name
        agent_name = request.agent_name
        handle = agent_manager.get(agent_name) if agent_name else None
        policy = handle.permission_policy if handle else PermissionPolicy.REJECT

        logger.info(
            "Permission request from %s: %s (tool=%s, policy=%s)",
            agent_name or "unknown",
            description,
            request.tool_name,
            policy.value,
        )

        if policy == PermissionPolicy.YOLO:
            logger.warning(
                "yolo: granting allow-always for %s on agent %s "
                "(irrevocable this session)",
                request.tool_name,
                agent_name,
            )
            return "allow-always"

        if policy == PermissionPolicy.AUTO_ALLOW:
            logger.info(
                "auto-allow: granting %s on agent %s",
                request.tool_name,
                agent_name,
            )
            return "allow-once"

        if policy == PermissionPolicy.REJECT:
            logger.info(
                "reject: denying %s on agent %s",
                request.tool_name,
                agent_name,
            )
            return "reject-once"

        session_id = _find_session_for_agent(registry, agent_name)
        if session_id is None and handle is not None and handle.associated_tabs:
            session_id = handle.associated_tabs[0]
            logger.debug(
                "Registry miss for %s; using handle.associated_tabs[0]=%s",
                agent_name, session_id,
            )
        if session_id is None:
            logger.warning(
                "No tab for agent %s (policy=prompt); rejecting",
                agent_name,
            )
            return "reject-once"

        app = await iterm2.async_get_app(connection)
        session = app.get_session_by_id(session_id)
        if session is None:
            logger.warning(
                "Session %s not found for agent %s; rejecting",
                session_id,
                agent_name,
            )
            return "reject-once"

        prompt_text = (
            f"\r\n[tak] {agent_name or 'agent'} wants to: {description}\r\n"
            f"  Allow? [y]es / [n]o / [a]lways: "
        )
        await session.async_inject(prompt_text.encode())

        decision = await _read_keystroke_decision(connection, session_id)

        echo = {"allow-once": "yes", "reject-once": "no", "allow-always": "always"}
        await session.async_inject(f"{echo.get(decision, '?')}\r\n".encode())

        return decision

    async def handle_ask_question(question: str, choices: list[str]) -> str:
        import iterm2

        logger.info("Agent asks: %s (choices=%s)", question, choices)
        if not choices:
            return ""

        all_assoc = registry.all_associations()
        session_id = next(iter(all_assoc), None) if all_assoc else None
        if session_id is None:
            logger.warning("No session for ask_question; using first choice")
            return choices[0]

        app = await iterm2.async_get_app(connection)
        session = app.get_session_by_id(session_id)
        if session is None:
            return choices[0]

        lines = [f"\r\n[tak] {question}\r\n"]
        for i, choice in enumerate(choices, 1):
            lines.append(f"  {i}) {choice}\r\n")
        lines.append("  Choice: ")
        await session.async_inject("".join(lines).encode())

        try:
            async with iterm2.KeystrokeMonitor(connection, session=session_id) as mon:
                keystroke = await asyncio.wait_for(mon.async_get(), timeout=60.0)
                char = keystroke.characters
                if char.isdigit():
                    idx = int(char) - 1
                    if 0 <= idx < len(choices):
                        await session.async_inject(f"{choices[idx]}\r\n".encode())
                        return choices[idx]
        except (TimeoutError, Exception):
            logger.warning("ask_question timed out or failed; using first choice")

        await session.async_inject(f"{choices[0]}\r\n".encode())
        return choices[0]

    provider.set_permission_callback(handle_permission)
    provider.set_ask_question_callback(handle_ask_question)


def _find_session_for_agent(
    registry: SessionRegistry,
    agent_name: str | None,
) -> str | None:
    """Find the terminal session associated with the given agent.

    Falls back to the first associated session if no direct match.

    Args:
        registry: The session registry.
        agent_name: The agent's user-assigned name.

    Returns:
        A session ID, or ``None`` if no sessions are associated.
    """
    if agent_name:
        sessions = registry.get_sessions(agent_name)
        if sessions:
            return sessions[0]

    all_assoc = registry.all_associations()
    return next(iter(all_assoc), None) if all_assoc else None


async def _read_keystroke_decision(connection: Any, session_id: str) -> str:
    """Read a single y/n/a keystroke from the user via ``iterm2.KeystrokeMonitor``.

    Waits up to ``_PERMISSION_TIMEOUT`` seconds. Ignores unrecognized keys
    and keeps waiting. Returns ``reject-once`` on timeout.

    Args:
        connection: The ``iterm2.Connection``.
        session_id: The terminal session to monitor.

    Returns:
        One of ``allow-once``, ``reject-once``, or ``allow-always``.
    """
    import iterm2

    try:
        async with iterm2.KeystrokeMonitor(connection, session=session_id) as mon:
            deadline = asyncio.get_event_loop().time() + _PERMISSION_TIMEOUT
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                keystroke = await asyncio.wait_for(mon.async_get(), timeout=remaining)
                char = keystroke.characters.lower()
                decision = _DECISION_MAP.get(char)
                if decision is not None:
                    return decision
    except TimeoutError:
        logger.info("Permission prompt timed out; rejecting")
    except Exception:
        logger.exception("Keystroke monitor error; rejecting")

    return "reject-once"


def _strip_session_prefix(session_id: str) -> str:
    """Strip the ``w0t0p0:`` prefix from an iTerm2 session ID.

    ``$ITERM_SESSION_ID`` uses the form ``w<W>t<T>p<P>:<UUID>`` but the
    iTerm2 Python API's ``session.session_id`` returns just the UUID.
    This helper normalises both forms to the bare UUID so they can be
    compared reliably.
    """
    return _ITERM_SESSION_PREFIX_RE.sub("", session_id)


def _session_exists(session_id: str, available_uuids: set[str]) -> bool:
    """Check whether *session_id* (possibly prefixed) exists in iTerm2."""
    return _strip_session_prefix(session_id) in available_uuids


async def _restore_full_state(
    manager: AgentManager,
    registry: SessionRegistry,
    state_mgr: StateManager,
    available_sessions: set[str],
) -> None:
    """Restore agents and session associations from persisted state.

    For each saved agent the corresponding provider is looked up and
    ``provider.spawn()`` is called with the original parameters.  Tab
    associations are restored only for sessions that still exist in the
    current iTerm2 app.  Missing sessions are logged as warnings.

    Session IDs from ``$ITERM_SESSION_ID`` include a ``w0t0p0:`` prefix
    while the Python API returns bare UUIDs.  Comparisons are normalised
    via :func:`_session_exists` so both forms match.

    After recovery ``StateManager.save()`` is called to update the state
    file to reflect any changes (e.g. disappeared tabs).

    Args:
        manager: The ``AgentManager`` to populate.
        registry: The session registry to restore associations into.
        state_mgr: The ``StateManager`` for loading and saving state.
        available_sessions: Set of currently active iTerm2 session IDs
            (bare UUIDs as returned by the Python API).
    """
    state = state_mgr.load()
    agents_state: dict[str, Any] = state.get("agents", {})
    associations: dict[str, str] = state.get("associations", {})

    logger.info(
        "State file: %d agent(s), %d association(s)",
        len(agents_state),
        len(associations),
    )
    for sid, aname in associations.items():
        logger.info("  association: session=%s -> agent=%s", sid, aname)
    for aname, adata in agents_state.items():
        logger.info(
            "  agent state: %s, tabs=%s",
            aname, adata.get("tabs", []),
        )

    available_uuids = {_strip_session_prefix(s) for s in available_sessions}

    await manager.restore(agents_state)

    for session_id, agent_name in associations.items():
        if _session_exists(session_id, available_uuids):
            registry.associate(session_id, agent_name)
            handle = manager.get(agent_name)
            if handle is not None and session_id not in handle.associated_tabs:
                handle.associated_tabs.append(session_id)
        else:
            logger.warning(
                "Session %s no longer exists; skipping re-association for agent %s",
                session_id,
                agent_name,
            )

    for handle in manager.running_agents():
        before = len(handle.associated_tabs)
        handle.associated_tabs = [
            t for t in handle.associated_tabs
            if _session_exists(t, available_uuids)
        ]
        pruned = before - len(handle.associated_tabs)
        if pruned:
            logger.info(
                "Pruned %d stale tab(s) from agent %r", pruned, handle.name
            )

    state_mgr.save(manager.list_agents(), registry.all_associations())
    logger.info(
        "Restart recovery: %d agent(s) restored, %d association(s) active",
        len(manager.running_agents()),
        len(registry.all_associations()),
    )


def run_daemon() -> None:
    """Launch the daemon using ``iterm2.run_forever``."""
    import iterm2

    logging.basicConfig(
        level=logging.INFO,
        format="[tak-daemon] %(levelname)s %(name)s: %(message)s",
    )
    iterm2.run_forever(main)


if __name__ == "__main__":
    run_daemon()
