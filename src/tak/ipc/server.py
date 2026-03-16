"""Unix domain socket IPC server for the tak daemon.

The server listens on ``~/.tak/daemon.sock`` and handles CLI requests
by dispatching them to the ``AgentManager`` and provider sessions.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tak.core.agent_manager import AgentStatus
from tak.ipc.protocol import IPCRequest, IPCResponse, read_message

if TYPE_CHECKING:
    from tak.core.adhoc import AdHocManager
    from tak.core.agent_manager import AgentManager
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
    ) -> None:
        """Create an IPC server.

        Args:
            agent_manager: The daemon's agent manager instance.
            socket_path: Path for the Unix socket. Defaults to ``~/.tak/daemon.sock``.
            providers: Optional map of provider name to instance, used for
                the ``ask`` method to send prompts directly to a provider session.
            adhoc_manager: Optional ``AdHocManager`` for ad-hoc ask requests.
        """
        self._manager = agent_manager
        self._socket_path = socket_path or DEFAULT_SOCKET_PATH
        self._server: asyncio.Server | None = None
        self._providers = providers or {}
        self._adhoc_manager = adhoc_manager

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
        """Spawn a new agent."""
        name = params["name"]
        provider = params["provider"]
        project_path = params.get("project_path")
        model = params.get("model")

        path_obj = Path(project_path) if project_path else None
        handle = await self._manager.spawn(
            name, provider, project_path=path_obj, model=model
        )
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
            use_adhoc: If truthy and *agent* is not specified, use the
                ad-hoc agent (spawning it if needed).
        """
        agent_name = params.get("agent", "")
        message = params.get("message", "")
        use_adhoc = bool(params.get("use_adhoc", False))

        if use_adhoc and not agent_name:
            if self._adhoc_manager is None:
                raise ValueError("Ad-hoc mode not configured on this server")
            response_text = await self._adhoc_manager.ask(message)
            return {"agent": "_adhoc", "response": response_text}

        if not agent_name:
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
