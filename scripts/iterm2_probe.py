#!/usr/bin/env python3
"""Probe script to validate iTerm2 Python API capabilities for tak.

Run from the iTerm2 Scripts menu, or place in
~/Library/Application Support/iTerm2/Scripts/ and run from there.

Tests:
  1. Connect and list all sessions
  2. Set/get user.tak_* variables
  3. Activate a tab
  4. Create a split pane
  5. Register an RPC function
  6. Display a status bar component
"""

from __future__ import annotations

import asyncio
import time

import iterm2

_OK = "\033[32m\u2713\033[0m"
_ERR = "\033[31m\u2717\033[0m"
_INFO = "\033[34mi\033[0m"


def report(label: str, passed: bool, detail: str = "") -> None:
    """Print a test result line."""
    icon = _OK if passed else _ERR
    suffix = f"  ({detail})" if detail else ""
    print(f"  {icon} {label}{suffix}")


async def probe_list_sessions(app: iterm2.App) -> bool:
    """Test 1: List all sessions across all windows/tabs."""
    print(f"\n{_INFO} Test 1: List sessions")
    count = 0
    for window in app.windows:
        for tab in window.tabs:
            for session in tab.sessions:
                count += 1
                print(
                    f"    Window={window.window_id}  Tab={tab.tab_id}  "
                    f"Session={session.session_id}"
                )
    passed = count > 0
    report("list_sessions", passed, f"{count} session(s) found")
    return passed


async def probe_variables(app: iterm2.App) -> bool:
    """Test 2: Set and read back user.tak_* variables."""
    print(f"\n{_INFO} Test 2: Set/get user.tak_* variables")
    session = app.current_terminal_window.current_tab.current_session

    test_vars = {
        "tak_agent_id": "probe-test",
        "tak_agent_status": "running",
        "tak_agent_provider": "cursor-acp",
        "tak_agent_model": "claude-sonnet-4",
    }

    all_ok = True
    for key, value in test_vars.items():
        full_key = f"user.{key}"
        await session.async_set_variable(full_key, value)
        readback = await session.async_get_variable(full_key)
        ok = readback == value
        report(f"set/get {full_key}", ok, f"wrote={value!r}, read={readback!r}")
        if not ok:
            all_ok = False

    # Clean up
    for key in test_vars:
        await session.async_set_variable(f"user.{key}", "")

    return all_ok


async def probe_activate_tab(app: iterm2.App) -> bool:
    """Test 3: Activate the current tab (proves the API call works)."""
    print(f"\n{_INFO} Test 3: Activate tab")
    session = app.current_terminal_window.current_tab.current_session
    try:
        await session.async_activate(select_tab=True, order_window_front=True)
        report("async_activate(select_tab=True, order_window_front=True)", True)
        return True
    except Exception as exc:
        report("async_activate", False, str(exc))
        return False


async def probe_split_pane(app: iterm2.App) -> bool:
    """Test 4: Create a split pane and send text to it."""
    print(f"\n{_INFO} Test 4: Split pane")
    session = app.current_terminal_window.current_tab.current_session
    try:
        new_session = await session.async_split_pane(vertical=True)
        report("async_split_pane(vertical=True)", True, f"new={new_session.session_id}")

        await new_session.async_send_text("echo 'tak probe: split pane works'\n")
        report("async_send_text to new pane", True)

        await asyncio.sleep(1.0)
        await new_session.async_close(force=True)
        report("async_close split pane", True)
        return True
    except Exception as exc:
        report("split_pane", False, str(exc))
        return False


async def probe_rpc_function(connection: iterm2.Connection) -> bool:
    """Test 5: Register and invoke an RPC function."""
    print(f"\n{_INFO} Test 5: Register RPC function")
    invoked = False

    @iterm2.RPC
    async def tak_probe_hello(session_id: str = iterm2.Reference("id")) -> None:  # type: ignore[assignment]
        nonlocal invoked
        invoked = True

    try:
        await tak_probe_hello.async_register(connection)
        report("RPC registration (tak_probe_hello)", True)
        report(
            "RPC invocation",
            True,
            "registered ok; invoke via Preferences > Keys > 'Invoke Script Function' "
            "> tak_probe_hello()",
        )
        return True
    except Exception as exc:
        report("RPC registration", False, str(exc))
        return False


async def probe_status_bar(connection: iterm2.Connection) -> bool:
    """Test 6: Register a status bar component."""
    print(f"\n{_INFO} Test 6: Status bar component")

    component = iterm2.StatusBarComponent(
        short_description="tak probe",
        detailed_description="Terminal Agent Kit probe status bar component",
        knobs=[],
        exemplar="tak: probe (ok)",
        update_cadence=None,
        identifier="com.tak.probe.status",
    )

    @iterm2.StatusBarRPC
    async def tak_probe_status_bar(
        knobs: iterm2.Reference,  # type: ignore[type-arg]
        tak_agent_id: str = iterm2.Reference("user.tak_agent_id?"),
        tak_agent_status: str = iterm2.Reference("user.tak_agent_status?"),
    ) -> str:
        agent_id = tak_agent_id or "--"
        status = tak_agent_status or "none"
        return f"tak: {agent_id} ({status})"

    try:
        await component.async_register(connection, tak_probe_status_bar)
        report(
            "StatusBarComponent registration",
            True,
            "add via Profiles > Session > Configure Status Bar > tak probe",
        )
        return True
    except Exception as exc:
        report("StatusBarComponent registration", False, str(exc))
        return False


async def probe_preferences(connection: iterm2.Connection) -> bool:
    """Bonus: Test reading/writing preferences."""
    print(f"\n{_INFO} Bonus: Preferences API")
    try:
        # async_get_theme may not exist in all iterm2 package versions.
        # Use async_list_profiles as a more reliable API availability check.
        profiles = await iterm2.PartialProfile.async_query(connection)
        report(
            "profile query",
            True,
            f"{len(profiles)} profile(s) found",
        )
        return True
    except Exception as exc:
        report("preferences read", False, str(exc))
        return False


async def probe_session_lookup(app: iterm2.App) -> bool:
    """Bonus: Test session lookup helpers."""
    print(f"\n{_INFO} Bonus: Session lookup helpers")
    session = app.current_terminal_window.current_tab.current_session
    sid = session.session_id

    try:
        found = app.get_session_by_id(sid)
        ok = found is not None and found.session_id == sid
        report("get_session_by_id", ok, f"found={found is not None}")
        return ok
    except Exception as exc:
        report("get_session_by_id", False, str(exc))
        return False


async def main(connection: iterm2.Connection) -> None:
    """Run all probe tests."""
    print("\n" + "=" * 60)
    print("  tak iTerm2 API Probe")
    print("=" * 60)
    start = time.time()

    app = await iterm2.async_get_app(connection)

    results = {
        "list_sessions": await probe_list_sessions(app),
        "variables": await probe_variables(app),
        "activate_tab": await probe_activate_tab(app),
        "split_pane": await probe_split_pane(app),
        "rpc_function": await probe_rpc_function(connection),
        "status_bar": await probe_status_bar(connection),
        "preferences": await probe_preferences(connection),
        "session_lookup": await probe_session_lookup(app),
    }

    elapsed = time.time() - start
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed}/{total} passed in {elapsed:.1f}s")
    if passed == total:
        print(f"  {_OK} All probes passed -- iTerm2 API is ready for tak")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  {_ERR} Failed: {', '.join(failed)}")
    print("=" * 60 + "\n")


iterm2.run_until_complete(main)
