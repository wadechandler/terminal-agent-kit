"""Cursor CLI provider via Agent Client Protocol (ACP).

Thin backwards-compatibility wrapper around :class:`~tak.providers.acp.ACPProvider`.
The Cursor-specific spawn command ``cursor agent acp`` and ``cursor_login``
authentication are pre-configured.  New code should use :class:`ACPProvider`
directly with an explicit ``command`` list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tak.providers.acp import ACPProvider

if TYPE_CHECKING:
    from tak.providers.acp_session import AskQuestionCallback, PermissionCallback


class CursorACPProvider(ACPProvider):
    """Cursor CLI integration via the Agent Client Protocol.

    Convenience subclass of :class:`ACPProvider` with Cursor-specific
    defaults pre-configured.  Kept for backwards compatibility.
    """

    def __init__(
        self,
        command: str = "cursor",
        *,
        permission_callback: PermissionCallback | None = None,
        ask_question_callback: AskQuestionCallback | None = None,
    ) -> None:
        """Create a Cursor ACP provider.

        Args:
            command: The Cursor CLI executable name or path.
            permission_callback: Called when the agent requests tool permission.
            ask_question_callback: Called when the agent asks a multiple-choice question.
        """
        super().__init__(
            name="Cursor (ACP)",
            command=[command, "agent", "acp"],
            auth_method="login",
            list_models_command=[command, "agent", "models"],
            permission_callback=permission_callback,
            ask_question_callback=ask_question_callback,
        )
