"""`red_decision` and `red_brief` (spec 2026-10-11-merge-train-safety §C, R10, R11).

R9's `reupdate` rule is gone: the wave merge queue never updates a PR branch (spec
2026-11-19-wave-merge-queue R13, R22).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fr.triage.batch_dispatch import NO_APPROVAL_LINE, red_brief
from fr.triage.batch_drive import RED_HANDBACKS_PER_DISPATCH, red_decision
from fr.triage.model import Batch, DispatchEvent, RedHandbackEvent, UpdateEvent

AT = datetime(2026, 10, 11, tzinfo=UTC)
PR, HEAD, BASE = 7, "h2", "b1"


def _update(before: str = "h1", after: str = HEAD, base: str = BASE) -> UpdateEvent:
    return UpdateEvent(kind="update", at=AT, pr=PR, head_before=before, head_after=after, base=base)


def _red(head: str = "h0", delivered: str = "session") -> RedHandbackEvent:
    return RedHandbackEvent(
        kind="red_handback",
        at=AT,
        pr=PR,
        head=head,
        checks=["test"],
        delivered=delivered,  # type: ignore[arg-type]
    )


def _dispatch() -> DispatchEvent:
    return DispatchEvent(kind="dispatch", at=AT, runner="r", handle="h", branch="b")


def _decide(events: list, *, status: str = "idle", head: str = HEAD) -> str:
    return red_decision(events, PR, head, ("test",), status)


def test_the_cap_is_two_per_dispatch() -> None:
    assert RED_HANDBACKS_PER_DISPATCH == 2


def test_rule_1_a_hand_back_at_this_head_is_skipped_whatever_else_holds() -> None:
    events = [_update(), _red(HEAD)]
    assert _decide(events) == "skip"
    assert _decide([_red(HEAD, "none")]) == "skip"


def test_a_red_head_fr_made_is_handed_back_like_any_other_never_updated_again() -> None:
    assert _decide([_update()]) == "handback"
    assert _decide([_dispatch(), _update(), _red("a"), _red("b")]) == "needs_you"


def test_rule_2_two_delivered_since_the_dispatch_is_needs_you() -> None:
    assert _decide([_dispatch(), _red("a"), _red("b")]) == "needs_you"


def test_rule_2_counts_since_the_last_dispatch_only() -> None:
    assert _decide([_red("a"), _red("b"), _dispatch(), _red("c")]) == "handback"


def test_rule_2_does_not_count_undelivered_ones() -> None:
    assert _decide([_dispatch(), _red("a", "none"), _red("b", "none")]) == "handback"


def test_rule_2_does_not_count_conflict_hand_backs() -> None:
    from fr.triage.model import ConflictEvent

    conflicts = [
        ConflictEvent(kind="conflict", at=AT, head=h, paths=["x"], delivered="session")
        for h in ("c1", "c2")
    ]
    assert _decide([_dispatch(), *conflicts]) == "handback"


@pytest.mark.parametrize(
    ("status", "want"),
    [
        ("idle", "handback"),
        ("absent", "needs_you"),
        ("done", "needs_you"),
        ("working", "wait"),
        ("blocked", "wait"),
        ("unknown", "wait"),
    ],
)
def test_rule_3_the_session_status_decides(status: str, want: str) -> None:
    assert _decide([], status=status) == want


def test_the_brief_names_the_pr_sha_checks_and_the_rules() -> None:
    batch = Batch(id="b", title="T", ids=["super-fr#1"])
    text = red_brief(
        batch, pr_url="https://github.com/derio-net/super-fr/pull/7", head="abc123",
        checks=["lint", "test"],
    )  # fmt: skip
    assert "https://github.com/derio-net/super-fr/pull/7" in text
    assert "abc123" in text and "lint" in text and "test" in text
    assert "force" in text  # no force-push
    assert "draft" in text and "label" in text  # leave both alone
    assert text.rstrip().endswith(NO_APPROVAL_LINE)
