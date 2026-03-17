"""Tests for driver session ID detection."""

from __future__ import annotations

from unittest.mock import patch

from tak.drivers.base import BaseDriver
from tak.drivers.iterm2.driver import ITerm2Driver


class TestBaseDriverDetectSessionId:
    def test_base_returns_none(self) -> None:
        assert BaseDriver.detect_session_id() is None


class TestITerm2DriverDetectSessionId:
    def test_returns_env_var_when_set(self) -> None:
        with patch.dict("os.environ", {"ITERM_SESSION_ID": "w0t1p0:DEADBEEF"}):
            assert ITerm2Driver.detect_session_id() == "w0t1p0:DEADBEEF"

    def test_returns_none_when_unset(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            assert ITerm2Driver.detect_session_id() is None

    def test_returns_none_when_empty(self) -> None:
        with patch.dict("os.environ", {"ITERM_SESSION_ID": ""}):
            result = ITerm2Driver.detect_session_id()
            assert result == ""
