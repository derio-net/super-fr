"""Each caller of a shared timestamp reader keeps its own rule for an awkward stamp.

`collect._created_since` counts an unknown creation as yes, `triage_batch_cmd._pr_time`
gives None for one, and `backfill._worth_reading` reads a naive `captured_at` as UTC and
an unreadable one as worth reading (spec 2026-11-27-arch-shared-helpers R7, R8).
"""

from __future__ import annotations

import datetime as _dt

import pytest
from fr.commands.triage_batch_cmd import _pr_time
from fr.triage.collect import _created_since
from fr.triage.model import PullRequest

AT = _dt.datetime(2026, 11, 1, 12, 0, tzinfo=_dt.UTC)


def _pr(created_at: str | None) -> PullRequest:
    return PullRequest(
        author="operator",
        cross_repo=False,
        repo="example-org/widgets",
        number=7,
        title="t",
        state="OPEN",
        is_draft=False,
        url="https://github.com/example-org/widgets/pull/7",
        created_at=created_at,
    )


@pytest.mark.parametrize(
    ("created_at", "since"),
    [
        (None, True),
        ("", True),
        ("not a time", True),
        ("2026-10-01T12:00:00", True),  # naive: unknown, so yes (never read as UTC)
        ("2026-10-01T12:00:00Z", False),
        ("2026-11-01T12:00:00+00:00", True),
        ("2026-11-01T13:00:00+02:00", False),  # 11:00 UTC, an hour before AT
    ],
)
def test_created_since_counts_an_unknown_creation_as_yes(
    created_at: str | None, since: bool
) -> None:
    assert _created_since(_pr(created_at), AT) is since


@pytest.mark.parametrize(
    "record",
    [
        None,
        {},
        {"createdAt": None},
        {"createdAt": ""},
        {"createdAt": "garbage"},
        {"createdAt": "2026-11-01T12:00:00"},
    ],
)
def test_pr_time_is_none_for_an_unknown_or_naive_stamp(record: dict | None) -> None:
    assert _pr_time(record) is None


def test_pr_time_reads_an_aware_stamp() -> None:
    assert _pr_time({"createdAt": "2026-11-01T12:00:00Z"}) == AT
