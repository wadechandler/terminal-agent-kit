"""Tests for IPC server dispatch logic."""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tak.core.agent_manager import PermissionPolicy
from tak.ipc.server import IPCServer

if TYPE_CHECKING:
    from conftest import MockProvider

    from tak.core.agent_manager import AgentManager
    from tak.core.session_registry import SessionRegistry


@pytest.fixture
def short_tmp() -> Iterator[Path]:
    # Unix domain sockets have a 104-byte path limit on macOS.
    # pytest's tmp_path can exceed this, so use /tmp directly.
    d = Path(tempfile.mkdtemp(prefix="tak_", dir="/tmp"))
    yield d
    for f in d.iterdir():
        f.unlink()
    d.rmdir()


@pytest.fixture
def ipc_server(agent_manager: AgentManager, short_tmp: Path) -> IPCServer:
    socket_path = short_tmp / "t.sock"
    return IPCServer(agent_manager=agent_manager, socket_path=socket_path)


@pytest.fixture
def ipc_server_with_provider(
    agent_manager: AgentManager,
    mock_provider: MockProvider,
    short_tmp: Path,
) -> IPCServer:
    socket_path = short_tmp / "tp.sock"
    return IPCServer(
        agent_manager=agent_manager,
        socket_path=socket_path,
        providers={"mock": mock_provider},
    )


@pytest.fixture
def ipc_server_with_registry(
    agent_manager: AgentManager,
    session_registry: SessionRegistry,
    mock_provider: MockProvider,
    short_tmp: Path,
) -> IPCServer:
    socket_path = short_tmp / "tr.sock"
    return IPCServer(
        agent_manager=agent_manager,
        socket_path=socket_path,
        providers={"mock": mock_provider},
        session_registry=session_registry,
    )


@pytest.fixture
def ipc_server_with_adhoc(
    agent_manager: AgentManager,
    mock_provider: MockProvider,
    short_tmp: Path,
) -> IPCServer:
    from tak.core.adhoc import AdHocManager

    adhoc = AdHocManager(agent_manager=agent_manager, provider_name="mock")
    socket_path = short_tmp / "ta.sock"
    return IPCServer(
        agent_manager=agent_manager,
        socket_path=socket_path,
        providers={"mock": mock_provider},
        adhoc_manager=adhoc,
    )


class TestIPCServerStartStop:
    async def test_start_creates_socket(
        self, ipc_server: IPCServer, tmp_path: Path
    ) -> None:
        await ipc_server.start()
        try:
            assert ipc_server.socket_path.exists()
        finally:
            await ipc_server.stop()

    async def test_stop_removes_socket(
        self, ipc_server: IPCServer, tmp_path: Path
    ) -> None:
        await ipc_server.start()
        await ipc_server.stop()
        assert not ipc_server.socket_path.exists()


class TestIPCServerIntegration:
    async def test_list_agents_via_socket(
        self, ipc_server: IPCServer, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("test-agent", "mock")
        await ipc_server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "list_agents",
                socket_path=ipc_server.socket_path,
            )
            assert resp.success
            assert len(resp.data) == 1
            assert resp.data[0]["name"] == "test-agent"
        finally:
            await ipc_server.stop()

    async def test_spawn_via_socket(
        self, ipc_server: IPCServer, agent_manager: AgentManager
    ) -> None:
        await ipc_server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "spawn",
                params={"name": "new-agent", "provider": "mock"},
                socket_path=ipc_server.socket_path,
            )
            assert resp.success
            assert resp.data["name"] == "new-agent"
            assert agent_manager.get("new-agent") is not None
        finally:
            await ipc_server.stop()

    async def test_stop_via_socket(
        self, ipc_server: IPCServer, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("to-stop", "mock")
        await ipc_server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "stop",
                params={"name": "to-stop"},
                socket_path=ipc_server.socket_path,
            )
            assert resp.success
            handle = agent_manager.get("to-stop")
            assert handle is not None
            assert handle.status.value == "stopped"
        finally:
            await ipc_server.stop()

    async def test_unknown_method(self, ipc_server: IPCServer) -> None:
        await ipc_server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "nonexistent",
                socket_path=ipc_server.socket_path,
            )
            assert not resp.success
            assert "Unknown method" in (resp.error or "")
        finally:
            await ipc_server.stop()


class TestIPCServerRename:
    async def test_rename_agent(
        self, ipc_server: IPCServer, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("old-agent", "mock")
        await ipc_server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "rename_agent",
                params={"old_name": "old-agent", "new_name": "new-agent"},
                socket_path=ipc_server.socket_path,
            )
            assert resp.success
            assert resp.data["new_name"] == "new-agent"
            assert agent_manager.get("new-agent") is not None
            assert agent_manager.get("old-agent") is None
        finally:
            await ipc_server.stop()

    async def test_rename_nonexistent_agent_returns_error(
        self, ipc_server: IPCServer
    ) -> None:
        await ipc_server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "rename_agent",
                params={"old_name": "ghost", "new_name": "new-name"},
                socket_path=ipc_server.socket_path,
            )
            assert not resp.success
            assert "ghost" in (resp.error or "")
        finally:
            await ipc_server.stop()


class TestIPCServerListAgentsFilter:
    async def test_list_agents_filter_by_provider(
        self, ipc_server: IPCServer, agent_manager: AgentManager, mock_provider: MockProvider
    ) -> None:
        second = type(mock_provider)()
        agent_manager.register_provider("second", second)
        await agent_manager.spawn("mock-agent", "mock")
        await agent_manager.spawn("second-agent", "second")

        await ipc_server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "list_agents",
                params={"provider": "mock"},
                socket_path=ipc_server.socket_path,
            )
            assert resp.success
            names = [a["name"] for a in resp.data]
            assert "mock-agent" in names
            assert "second-agent" not in names
        finally:
            await ipc_server.stop()

    async def test_list_agents_filter_running_only(
        self, ipc_server: IPCServer, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("running-agent", "mock")
        await agent_manager.spawn("to-stop", "mock")
        await agent_manager.stop("to-stop")

        await ipc_server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "list_agents",
                params={"running": True},
                socket_path=ipc_server.socket_path,
            )
            assert resp.success
            names = [a["name"] for a in resp.data]
            assert "running-agent" in names
            assert "to-stop" not in names
        finally:
            await ipc_server.stop()

    async def test_list_agents_no_filter_returns_all(
        self, ipc_server: IPCServer, agent_manager: AgentManager
    ) -> None:
        await agent_manager.spawn("agent-a", "mock")
        await agent_manager.spawn("agent-b", "mock")
        await agent_manager.stop("agent-b")

        await ipc_server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "list_agents",
                socket_path=ipc_server.socket_path,
            )
            assert resp.success
            assert len(resp.data) == 2
        finally:
            await ipc_server.stop()


class TestIPCServerAsk:
    async def test_ask_sends_prompt_to_agent(
        self,
        ipc_server_with_provider: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        await agent_manager.spawn("ask-agent", "mock")
        await ipc_server_with_provider.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "ask",
                params={"agent": "ask-agent", "message": "hello world"},
                socket_path=ipc_server_with_provider.socket_path,
            )
            assert resp.success
            assert resp.data["agent"] == "ask-agent"
            assert resp.data["response"] == "mock response"
        finally:
            await ipc_server_with_provider.stop()

    async def test_ask_uses_first_running_agent_if_none_specified(
        self,
        ipc_server_with_provider: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        await agent_manager.spawn("default-agent", "mock")
        await ipc_server_with_provider.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "ask",
                params={"message": "hi"},
                socket_path=ipc_server_with_provider.socket_path,
            )
            assert resp.success
            assert resp.data["agent"] == "default-agent"
        finally:
            await ipc_server_with_provider.stop()

    async def test_ask_no_running_agents_returns_error(
        self,
        ipc_server_with_provider: IPCServer,
    ) -> None:
        await ipc_server_with_provider.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "ask",
                params={"message": "hi"},
                socket_path=ipc_server_with_provider.socket_path,
            )
            assert not resp.success
            assert "No running agents" in (resp.error or "")
        finally:
            await ipc_server_with_provider.stop()

    async def test_ask_resolves_agent_from_session_id(
        self,
        ipc_server_with_registry: IPCServer,
        agent_manager: AgentManager,
        session_registry: SessionRegistry,
    ) -> None:
        await agent_manager.spawn("tab-agent", "mock")
        session_registry.associate("sess-lookup", "tab-agent")
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "ask",
                params={"message": "hi", "session_id": "sess-lookup"},
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert resp.success
            assert resp.data["agent"] == "tab-agent"
            assert resp.data["response"] == "mock response"
        finally:
            await ipc_server_with_registry.stop()

    async def test_ask_resolves_agent_from_handle_tabs_fallback(
        self,
        ipc_server_with_registry: IPCServer,
        agent_manager: AgentManager,
        session_registry: SessionRegistry,
    ) -> None:
        """Registry doesn't have the mapping but handle.associated_tabs does."""
        handle = await agent_manager.spawn("orphan-tab-agent", "mock")
        handle.associated_tabs.append("sess-orphan")
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "ask",
                params={"message": "hi", "session_id": "sess-orphan"},
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert resp.success
            assert resp.data["agent"] == "orphan-tab-agent"

            assert session_registry.get_agent("sess-orphan") == "orphan-tab-agent"
        finally:
            await ipc_server_with_registry.stop()

    async def test_prompt_passes_cwd_and_mode_to_provider(
        self,
        ipc_server_with_provider: IPCServer,
        agent_manager: AgentManager,
        mock_provider: MockProvider,
    ) -> None:
        await agent_manager.spawn("ipc-test-agent", "mock")
        await ipc_server_with_provider.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "prompt",
                params={
                    "agent": "ipc-test-agent",
                    "message": "hi",
                    "cwd": "/workspace",
                    "mode": "plan",
                },
                socket_path=ipc_server_with_provider.socket_path,
            )
            assert resp.success
            assert mock_provider.send_calls[-1]["cwd"] == "/workspace"
            assert mock_provider.send_calls[-1]["mode"] == "plan"
        finally:
            await ipc_server_with_provider.stop()


class TestIPCServerSessionEnd:
    async def test_session_end_clears_acp_session_id(
        self,
        ipc_server_with_provider: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        handle = await agent_manager.spawn("ipc-test-agent", "mock")
        handle.acp_session_id = "persisted-sess"
        await ipc_server_with_provider.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "session_end",
                params={"agent": "ipc-test-agent"},
                socket_path=ipc_server_with_provider.socket_path,
            )
            assert resp.success
            renewed = agent_manager.get("ipc-test-agent")
            assert renewed is not None
            assert renewed.acp_session_id is None
        finally:
            await ipc_server_with_provider.stop()


class TestIPCServerAdHocAsk:
    async def test_ask_adhoc_spawns_and_responds(
        self,
        ipc_server_with_adhoc: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        await ipc_server_with_adhoc.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "ask",
                params={"message": "quick question", "use_adhoc": True},
                socket_path=ipc_server_with_adhoc.socket_path,
            )
            assert resp.success
            assert resp.data["agent"] == "_adhoc"
            assert resp.data["response"] == "mock response"
        finally:
            await ipc_server_with_adhoc.stop()

    async def test_ask_adhoc_without_manager_returns_error(
        self,
        ipc_server: IPCServer,
    ) -> None:
        await ipc_server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "ask",
                params={"message": "hi", "use_adhoc": True},
                socket_path=ipc_server.socket_path,
            )
            assert not resp.success
            assert "Ad-hoc" in (resp.error or "")
        finally:
            await ipc_server.stop()


class TestIPCServerAssociate:
    async def test_associate_links_session_to_agent(
        self,
        ipc_server_with_registry: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        await agent_manager.spawn("assoc-agent", "mock")
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "associate",
                params={"agent": "assoc-agent", "session_id": "sess-abc"},
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert resp.success
            assert resp.data["agent"] == "assoc-agent"
            assert resp.data["session_id"] == "sess-abc"

            handle = agent_manager.get("assoc-agent")
            assert handle is not None
            assert "sess-abc" in handle.associated_tabs
        finally:
            await ipc_server_with_registry.stop()

    async def test_associate_missing_agent_returns_error(
        self,
        ipc_server_with_registry: IPCServer,
    ) -> None:
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "associate",
                params={"agent": "ghost", "session_id": "sess-abc"},
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert not resp.success
            assert "ghost" in (resp.error or "")
        finally:
            await ipc_server_with_registry.stop()

    async def test_associate_missing_session_id_returns_error(
        self,
        ipc_server_with_registry: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        await agent_manager.spawn("assoc-agent", "mock")
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "associate",
                params={"agent": "assoc-agent"},
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert not resp.success
            assert "session_id" in (resp.error or "")
        finally:
            await ipc_server_with_registry.stop()


class TestIPCServerSetPermissions:
    async def test_set_permissions_updates_policy(
        self,
        ipc_server_with_registry: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        await agent_manager.spawn("perm-agent", "mock")
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "set_permissions",
                params={"agent": "perm-agent", "policy": "auto-allow"},
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert resp.success
            assert resp.data["policy"] == "auto-allow"

            handle = agent_manager.get("perm-agent")
            assert handle is not None
            assert handle.permission_policy == PermissionPolicy.AUTO_ALLOW
        finally:
            await ipc_server_with_registry.stop()

    async def test_set_permissions_yolo(
        self,
        ipc_server_with_registry: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        await agent_manager.spawn("yolo-agent", "mock")
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "set_permissions",
                params={"agent": "yolo-agent", "policy": "yolo"},
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert resp.success
            assert resp.data["policy"] == "yolo"

            handle = agent_manager.get("yolo-agent")
            assert handle is not None
            assert handle.permission_policy == PermissionPolicy.YOLO
        finally:
            await ipc_server_with_registry.stop()

    async def test_set_permissions_invalid_policy_returns_error(
        self,
        ipc_server_with_registry: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        await agent_manager.spawn("perm-agent", "mock")
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "set_permissions",
                params={"agent": "perm-agent", "policy": "invalid"},
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert not resp.success
            assert "Invalid policy" in (resp.error or "")
        finally:
            await ipc_server_with_registry.stop()

    async def test_set_permissions_missing_agent_returns_error(
        self,
        ipc_server_with_registry: IPCServer,
    ) -> None:
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "set_permissions",
                params={"agent": "ghost", "policy": "reject"},
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert not resp.success
            assert "ghost" in (resp.error or "")
        finally:
            await ipc_server_with_registry.stop()


class TestIPCServerSwitch:
    async def test_switch_activates_tab(
        self,
        agent_manager: AgentManager,
        mock_provider: MockProvider,
        short_tmp: Path,
    ) -> None:
        activated: list[str] = []

        async def fake_activate(session_id: str) -> None:
            await asyncio.sleep(0)
            activated.append(session_id)

        server = IPCServer(
            agent_manager=agent_manager,
            socket_path=short_tmp / "sw.sock",
            providers={"mock": mock_provider},
            activate_tab=fake_activate,
        )
        handle = await agent_manager.spawn("sw-agent", "mock")
        handle.associated_tabs.append("sess-tab-1")
        await server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "switch",
                params={"name": "sw-agent"},
                socket_path=server.socket_path,
            )
            assert resp.success
            assert resp.data["agent"] == "sw-agent"
            assert resp.data["session_id"] == "sess-tab-1"
            assert activated == ["sess-tab-1"]
        finally:
            await server.stop()

    async def test_switch_uses_most_recent_tab(
        self,
        agent_manager: AgentManager,
        mock_provider: MockProvider,
        short_tmp: Path,
    ) -> None:
        activated: list[str] = []

        async def fake_activate(session_id: str) -> None:
            await asyncio.sleep(0)
            activated.append(session_id)

        server = IPCServer(
            agent_manager=agent_manager,
            socket_path=short_tmp / "sw2.sock",
            providers={"mock": mock_provider},
            activate_tab=fake_activate,
        )
        handle = await agent_manager.spawn("multi-tab", "mock")
        handle.associated_tabs.extend(["sess-old", "sess-new"])
        await server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "switch",
                params={"name": "multi-tab"},
                socket_path=server.socket_path,
            )
            assert resp.success
            assert resp.data["session_id"] == "sess-new"
            assert activated == ["sess-new"]
        finally:
            await server.stop()

    async def test_switch_no_tabs_returns_error(
        self,
        agent_manager: AgentManager,
        mock_provider: MockProvider,
        short_tmp: Path,
    ) -> None:
        async def fake_activate(_session_id: str) -> None:
            """Unused when the agent has no associated tabs."""
            await asyncio.sleep(0)

        server = IPCServer(
            agent_manager=agent_manager,
            socket_path=short_tmp / "sw3.sock",
            providers={"mock": mock_provider},
            activate_tab=fake_activate,
        )
        await agent_manager.spawn("no-tabs", "mock")
        await server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "switch",
                params={"name": "no-tabs"},
                socket_path=server.socket_path,
            )
            assert not resp.success
            assert "no associated tabs" in (resp.error or "")
        finally:
            await server.stop()

    async def test_switch_nonexistent_agent_returns_error(
        self,
        ipc_server: IPCServer,
    ) -> None:
        await ipc_server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "switch",
                params={"name": "ghost"},
                socket_path=ipc_server.socket_path,
            )
            assert not resp.success
            assert "ghost" in (resp.error or "")
        finally:
            await ipc_server.stop()

    async def test_switch_without_callback_returns_error(
        self,
        agent_manager: AgentManager,
        mock_provider: MockProvider,
        short_tmp: Path,
    ) -> None:
        server = IPCServer(
            agent_manager=agent_manager,
            socket_path=short_tmp / "sw4.sock",
            providers={"mock": mock_provider},
        )
        handle = await agent_manager.spawn("no-driver", "mock")
        handle.associated_tabs.append("sess-123")
        await server.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "switch",
                params={"name": "no-driver"},
                socket_path=server.socket_path,
            )
            assert not resp.success
            assert "not available" in (resp.error or "")
        finally:
            await server.stop()


class TestIPCServerSpawnWithAssociation:
    async def test_spawn_with_session_id_auto_associates(
        self,
        ipc_server_with_registry: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "spawn",
                params={
                    "name": "auto-agent",
                    "provider": "mock",
                    "session_id": "sess-xyz",
                    "permission_policy": "auto-allow",
                },
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert resp.success

            handle = agent_manager.get("auto-agent")
            assert handle is not None
            assert "sess-xyz" in handle.associated_tabs
            assert handle.permission_policy == PermissionPolicy.AUTO_ALLOW
        finally:
            await ipc_server_with_registry.stop()

    async def test_spawn_without_session_id_no_association(
        self,
        ipc_server_with_registry: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "spawn",
                params={"name": "plain-agent", "provider": "mock"},
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert resp.success

            handle = agent_manager.get("plain-agent")
            assert handle is not None
            assert handle.associated_tabs == []
            assert handle.permission_policy == PermissionPolicy.PROMPT
        finally:
            await ipc_server_with_registry.stop()

    async def test_spawn_with_yolo_policy(
        self,
        ipc_server_with_registry: IPCServer,
        agent_manager: AgentManager,
    ) -> None:
        await ipc_server_with_registry.start()
        try:
            from tak.ipc.client import send_request

            resp = await send_request(
                "spawn",
                params={
                    "name": "yolo-spawn",
                    "provider": "mock",
                    "permission_policy": "yolo",
                },
                socket_path=ipc_server_with_registry.socket_path,
            )
            assert resp.success

            handle = agent_manager.get("yolo-spawn")
            assert handle is not None
            assert handle.permission_policy == PermissionPolicy.YOLO
        finally:
            await ipc_server_with_registry.stop()
