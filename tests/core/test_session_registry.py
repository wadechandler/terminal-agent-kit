"""Tests for SessionRegistry tab-agent associations."""

from __future__ import annotations

from tak.core.session_registry import SessionRegistry


class TestSessionRegistryAssociation:
    def test_associate_and_get(self, session_registry: SessionRegistry) -> None:
        session_registry.associate("sess-1", "cursor-myapp")
        assert session_registry.get_agent("sess-1") == "cursor-myapp"

    def test_get_unassociated_returns_none(
        self, session_registry: SessionRegistry
    ) -> None:
        assert session_registry.get_agent("unknown") is None

    def test_reassociate_overwrites(self, session_registry: SessionRegistry) -> None:
        session_registry.associate("sess-1", "cursor-myapp")
        session_registry.associate("sess-1", "claude-docs")
        assert session_registry.get_agent("sess-1") == "claude-docs"

    def test_disassociate(self, session_registry: SessionRegistry) -> None:
        session_registry.associate("sess-1", "cursor-myapp")
        session_registry.disassociate("sess-1")
        assert session_registry.get_agent("sess-1") is None

    def test_disassociate_unknown_is_noop(
        self, session_registry: SessionRegistry
    ) -> None:
        session_registry.disassociate("unknown")


class TestSessionRegistryQueries:
    def test_get_sessions_for_agent(
        self, session_registry: SessionRegistry
    ) -> None:
        session_registry.associate("sess-1", "cursor-myapp")
        session_registry.associate("sess-2", "cursor-myapp")
        session_registry.associate("sess-3", "claude-docs")
        sessions = session_registry.get_sessions("cursor-myapp")
        assert sorted(sessions) == ["sess-1", "sess-2"]

    def test_get_sessions_empty(self, session_registry: SessionRegistry) -> None:
        assert session_registry.get_sessions("nonexistent") == []

    def test_all_associations(self, session_registry: SessionRegistry) -> None:
        session_registry.associate("sess-1", "cursor-myapp")
        session_registry.associate("sess-2", "claude-docs")
        assoc = session_registry.all_associations()
        assert assoc == {"sess-1": "cursor-myapp", "sess-2": "claude-docs"}
