"""Unix domain socket IPC server for the tak daemon.

The server listens on ``~/.tak/daemon.sock`` and handles CLI requests
by dispatching them to the ``AgentManager`` and provider sessions.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tak.core.agent_manager import AgentStatus, PermissionPolicy
from tak.ipc.protocol import IPCRequest, IPCResponse, read_message

if TYPE_CHECKING:
    from tak.core.adhoc import AdHocManager
    from tak.core.agent_manager import AgentManager
    from tak.core.session_registry import SessionRegistry
    from tak.providers.base import BaseProvider

logger = logging.getLogger(__name__)

DEFAULT_SOCKET_PATH = Path.home() / ".tak" / "daemon.sock"


class IPCServer:
    """Async Unix socket server that dispatches CLI commands to the daemon."""

    def __init__(
        self,
        agent_manager: AgentManager,
        socket_path: Path | None = None,
        providers: dict[str, BaseProvider] | None = None,
        adhoc_manager: AdHocManager | None = None,
        session_registry: SessionRegistry | None = None,
    ) -> None:
        """Create an IPC server.

        Args:
            agent_manager: The daemon's agent manager instance.
            socket_path: Path for the Unix socket. Defaults to ``~/.tak/daemon.sock``.
            providers: Optional map of provider name to instance, used for
                the ``ask`` method to send prompts directly to a provider session.
            adhoc_manager: Optional ``AdHocManager`` for ad-hoc ask requests.
            session_registry: Optional session registry for tab-agent associations.
        """
        self._manager = agent_manager
        self._socket_path = socket_path or DEFAULT_SOCKET_PATH
        self._server: asyncio.Server | None = None
        self._providers = providers or {}
        self._adhoc_manager = adhoc_manager
        self._registry = session_registry

    @property
    def socket_path(self) -> Path:
        """Return the socket file path."""
        return self._socket_path

    async def start(self) -> None:
        """Start listening for connections on the Unix socket."""
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self._socket_path.exists():
            self._socket_path.unlink()

        self._server = await asyncio.start_unix_server(
            self._handle_connection, path=str(self._socket_path)
        )
        logger.info("IPC server listening on %s", self._socket_path)

    async def stop(self) -> None:
        """Stop the IPC server and clean up the socket file."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        if self._socket_path.exists():
            self._socket_path.unlink()
        logger.info("IPC server stopped")

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a single CLI connection."""
        try:
            raw = await read_message(reader)
            request = IPCRequest.decode(raw)
            logger.debug("IPC request: %s", request.method)

            response = await self._dispatch(request)

            payload = response.encode()
            writer.write(payload)
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            logger.debug("IPC client disconnected")
        except Exception:
            logger.exception("IPC handler error")
            error_resp = IPCResponse(success=False, error="internal error")
            writer.write(error_resp.encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def _dispatch(self, request: IPCRequest) -> IPCResponse:
        """Route a request to the appropriate handler."""
        handlers: dict[str, Any] = {
            "list_agents": self._handle_list_agents,
            "spawn": self._handle_spawn,
            "stop": self._handle_stop,
            "status": self._handle_status,
            "ask": self._handle_ask,
            "rename_agent": self._handle_rename_agent,
            "associate": self._handle_associate,
            "set_permissions": self._handle_set_permissions,
        }

        handler = handlers.get(request.method)
        if handler is None:
            return IPCResponse(
                success=False,
                error=f"Unknown method: {request.method}",
                request_id=request.request_id,
            )

        try:
            data = await handler(request.params)
            return IPCResponse(
                success=True, data=data, request_id=request.request_id
            )
        except Exception as exc:
            return IPCResponse(
                success=False,
                error=str(exc),
                request_id=request.request_id,
            )

    async def _handle_list_agents(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Return a filtered list of managed agents.

        Params:
            provider: Optional provider name to filter by.
            running: If truthy, return only running agents.
        """
        provider_filter: str | None = params.get("provider")
        running_only: bool = bool(params.get("running", False))

        if provider_filter is not None:
            agents = self._manager.get_by_provider(provider_filter)
        else:
            agents = self._manager.list_agents()

        if running_only:
            agents = [a for a in agents if a.status == AgentStatus.RUNNING]

        return [
            {
                "name": h.name,
                "provider": h.provider_name,
                "model": h.model,
                "status": h.status.value,
                "tabs": h.associated_tabs,
            }
            for h in agents
        ]

    async def _handle_spawn(self, params: dict[str, Any]) -> dict[str, str]:
        """Spawn a new agent.

        Params:
            name: Agent name.
            provider: Provider name.
            project_path: Optional project directory.
            model: Optional model name.
            session_id: Optional terminal session ID for auto-association.
            permission_policy: Optional policy string (prompt/reject/auto-allow/yolo).
        """
        name = params["name"]
        provider = params["provider"]
        project_path = params.get("project_path")
        model = params.get("model")
        session_id: str | None = params.get("session_id")
        policy_str: str = params.get("permission_policy", "prompt")

        try:
            policy = PermissionPolicy(policy_str)
        except ValueError:
            policy = PermissionPolicy.PROMPT

        path_obj = Path(project_path) if project_path else None
        handle = await self._manager.spawn(
            name, provider, project_path=path_obj, model=model,
            permission_policy=policy,
        )

        if session_id:
            if self._registry is not None:
                self._registry.associate(session_id, name)
            if session_id not in handle.associated_tabs:
                handle.associated_tabs.append(session_id)
            logger.info("Auto-associated session %s with agent %s", session_id, name)

        self._manager._auto_save()
        return {"name": handle.name, "status": handle.status.value}

    async def _handle_stop(self, params: dict[str, Any]) -> dict[str, str]:
        """Stop a running agent."""
        name = params["name"]
        await self._manager.stop(name)
        handle = self._manager.get(name)
        status = handle.status.value if handle else "unknown"
        return {"name": name, "status": status}

    async def _handle_status(self, params: dict[str, Any]) -> dict[str, Any] | None:
        """Get status of a specific agent."""
        name = params.get("name", "")
        handle = self._manager.get(name)
        if handle is None:
            return None
        return {
            "name": handle.name,
            "provider": handle.provider_name,
            "model": handle.model,
            "status": handle.status.value,
            "tabs": handle.associated_tabs,
        }

    async def _handle_rename_agent(self, params: dict[str, Any]) -> dict[str, str]:
        """Rename an agent.

        Params:
            old_name: Current agent name.
            new_name: Desired new name.
        """
        old_name = params["old_name"]
        new_name = params["new_name"]
        handle = await self._manager.rename(old_name, new_name)
        return {"old_name": old_name, "new_name": handle.name}

    async def _handle_ask(self, params: dict[str, Any]) -> dict[str, str]:
        """Send a prompt to a running agent and return the response.

        Params:
            agent: The agent name to send the prompt to.
            message: The prompt text.
            session_id: Optional terminal session ID; used to resolve the
                associated agent when *agent* is not specified.
            use_adhoc: If truthy and no agent can be resolved, use the
                ad-hoc agent (spawning it if needed).
        """
        agent_name = params.get("agent", "")
        message = params.get("message", "")
        session_id: str | None = params.get("session_id")
        use_adhoc = bool(params.get("use_adhoc", False))

        if not agent_name and session_id:
            agent_name = self._resolve_agent_for_session(session_id)

        if not agent_name and use_adhoc:
            if self._adhoc_manager is None:
                raise ValueError("Ad-hoc mode not configured on this server")
            response_text = await self._adhoc_manager.ask(message)
            return {"agent": "_adhoc", "response": response_text}

        if not agent_name:
            if self._adhoc_manager is not None:
                response_text = await self._adhoc_manager.ask(message)
                return {"agent": "_adhoc", "response": response_text}
            running = self._manager.running_agents()
            if not running:
                raise ValueError("No running agents")
            agent_name = running[0].name

        handle = self._manager.get(agent_name)
        if handle is None:
            raise ValueError(f"No agent named '{agent_name}'")

        provider = self._providers.get(handle.provider_name)
        if provider is None:
            raise ValueError(f"No provider '{handle.provider_name}' registered with IPC server")

        response_text = await provider.send(handle, message)
        return {"agent": agent_name, "response": response_text}

    def _resolve_agent_for_session(self, session_id: str) -> str:
        """Find the agent associated with a terminal session.

        Checks the session registry first, then falls back to scanning
        agent handles' ``associated_tabs`` lists (covers cases where the
        registry lost the mapping on restart but the handle retained it).

        Args:
            session_id: The terminal session ID to look up.

        Returns:
            The agent name, or empty string if no association found.
        """
        if self._registry is not None:
            resolved = self._registry.get_agent(session_id)
            if resolved:
                return resolved

        for handle in self._manager.running_agents():
            if session_id in handle.associated_tabs:
                if self._registry is not None:
                    self._registry.associate(session_id, handle.name)
                return handle.name

        return ""

    async def _handle_associate(self, params: dict[str, Any]) -> dict[str, str]:
        """Associate a terminal session (tab) with an agent.

        Params:
            agent: The agent name to associate.
            session_id: The iTerm2 session ID (from ``$ITERM_SESSION_ID``).
        """
        agent_name = params.get("agent", "")
        session_id = params.get("session_id", "")

        if not agent_name:
            raise ValueError("agent name is required")
        if not session_id:
            raise ValueError("session_id is required (set $ITERM_SESSION_ID)")

        handle = self._manager.get(agent_name)
        if handle is None:
            raise ValueError(f"No agent named '{agent_name}'")

        if self._registry is not None:
            self._registry.associate(session_id, agent_name)

        if session_id not in handle.associated_tabs:
            handle.associated_tabs.append(session_id)

        logger.info("Associated session %s with agent %s", session_id, agent_name)
        return {"agent": agent_name, "session_id": session_id}

    async def _handle_set_permissions(self, params: dict[str, Any]) -> dict[str, str]:
        """Update the permission policy for a running agent.

        Params:
            agent: The agent name.
            policy: One of ``prompt``, ``reject``, ``auto-allow``, ``yolo``.
        """
        agent_name = params.get("agent", "")
        policy_str = params.get("policy", "")

        if not agent_name:
            raise ValueError("agent name is required")

        handle = self._manager.get(agent_name)
        if handle is None:
            raise ValueError(f"No agent named '{agent_name}'")

        try:
            policy = PermissionPolicy(policy_str)
        except ValueError:
            raise ValueError(
                f"Invalid policy {policy_str!r}; "
                f"must be one of: prompt, reject, auto-allow, yolo"
            ) from None

        handle.permission_policy = policy
        self._manager._auto_save()
        logger.info("Set permission policy for %s to %s", agent_name, policy.value)
        return {"agent": agent_name, "policy": policy.value}
