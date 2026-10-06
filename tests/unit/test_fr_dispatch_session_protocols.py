"""SessionStatus, SessionInspector and SessionFocuser (spec 2026-10-05 §A)."""

from __future__ import annotations

from typing import Any, get_args

import pytest
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
    # `__protocol_attrs__` exists from Python 3.12; without it the check would be vacuous.
    if not hasattr(Runner, "__protocol_attrs__"):
        pytest.skip("typing.Protocol exposes no __protocol_attrs__ before Python 3.12")
    members = set(Runner.__protocol_attrs__)
    assert "dispatch" in members  # the check reads real members
    assert not {"session_statuses", "focus"} & members
