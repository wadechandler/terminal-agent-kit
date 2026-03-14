"""Tests for configuration loading and merging."""

from __future__ import annotations

from tak.core.config import _deep_merge


class TestDeepMerge:
    def test_simple_override(self) -> None:
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        assert _deep_merge(base, override) == {"a": 1, "b": 3}

    def test_nested_override(self) -> None:
        base = {"prefixes": {"agent_query": "@ai", "quick_query": "??"}}
        override = {"prefixes": {"quick_query": "!!"}}
        result = _deep_merge(base, override)
        assert result["prefixes"]["agent_query"] == "@ai"
        assert result["prefixes"]["quick_query"] == "!!"

    def test_new_keys_added(self) -> None:
        base = {"a": 1}
        override = {"b": 2}
        assert _deep_merge(base, override) == {"a": 1, "b": 2}

    def test_base_not_mutated(self) -> None:
        base = {"a": {"nested": 1}}
        override = {"a": {"nested": 2}}
        _deep_merge(base, override)
        assert base["a"]["nested"] == 1

    def test_override_replaces_non_dict_with_dict(self) -> None:
        base = {"a": "string"}
        override = {"a": {"nested": True}}
        result = _deep_merge(base, override)
        assert result["a"] == {"nested": True}
