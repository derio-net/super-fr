"""SessionStatus, SessionInspector and SessionFocuser (spec 2026-10-05 §A)."""

from __future__ import annotations

from typing import Any, get_args

from fr_dispatch.protocols import (
    Runner,
    SessionFocuser,
    SessionInspector,
    SessionStatus,
)


def test_session_status_is_exactly_the_six_values() -> None:
    assert get_args(SessionStatus) == (
        "working",
        "blocked",
        "idle",
        "done",
        "unknown",
        "absent",
    )


class _Inspects:
    def session_statuses(self, items: Any) -> dict[str, str]:
        return {}


class _Focuses:
    def focus(self, item: Any) -> bool:
        return True


class _Neither:
    pass


def test_session_inspector_is_structural() -> None:
    assert isinstance(_Inspects(), SessionInspector)
    assert not isinstance(_Neither(), SessionInspector)
    assert not isinstance(_Focuses(), SessionInspector)


def test_session_focuser_is_structural() -> None:
    assert isinstance(_Focuses(), SessionFocuser)
    assert not isinstance(_Neither(), SessionFocuser)
    assert not isinstance(_Inspects(), SessionFocuser)


def test_neither_is_a_member_of_runner() -> None:
    members = set(getattr(Runner, "__protocol_attrs__", set()))
    assert not {"session_statuses", "focus"} & members
