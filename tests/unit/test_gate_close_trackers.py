"""P3.T1: close_gate_trackers (spec gate-backfill §H, R12)."""

from __future__ import annotations

from pathlib import Path

from fr.gatebackfill import trackers as t
from fr.verification.labels import close_gate_trackers

from tests.unit.fakes import FakeGhClient, FakeGhError
from tests.unit.gatebackfill_fixtures import ME, REPO, STRANGER

KEY = "row:r-live"


def _fake() -> FakeGhClient:
    fake = FakeGhClient()
    fake.comment_author = ME
    return fake


def _tracker(
    fake: FakeGhClient, n: int, key: str = KEY, gate: str = "tester", pr: int = 41
) -> None:
    fake.add_issue(REPO, n, labels={"fr:owed"}, body=t.tracker_body(key, "t", gate, pr))


def _closes(fake: FakeGhClient) -> list[int]:
    return [c[1]["number"] for c in fake.calls if c[0] == "close_issue"]


def test_it_closes_only_the_trackers_naming_this_pr_and_gate() -> None:
    fake = _fake()
    _tracker(fake, 1)
    _tracker(fake, 2, pr=42)
    _tracker(fake, 3, gate="devops")
    fake.add_issue(REPO, 4, labels={"fr:owed"}, body=t.tracker_body(KEY, "t", "tester", 41))
    fake.issue_authors[(REPO, 4)] = STRANGER  # foreign: marker is only text
    fake.add_issue(REPO, 5, labels=set(), body=t.tracker_body(KEY, "t", "tester", 41))

    rep = close_gate_trackers(fake, REPO, 41, "tester", "walked live", root=Path("/nonexistent"))

    assert _closes(fake) == [1] and rep.closed == [1]
    (close,) = [c[1] for c in fake.calls if c[0] == "close_issue"]
    assert close["comment"] == "Gate tester passed on #41: walked live"
    assert rep.discharge and "set-status --id r-live" in rep.discharge[0]
    assert not [c for c in fake.calls if c[0] == "list_issue_comments" and c[1]["number"] != 4]


def test_an_adopted_issue_is_listed_never_closed() -> None:
    fake = _fake()
    fake.add_issue(REPO, 9, labels={"fr:owed"}, body="a human's issue")
    fake.issue_authors[(REPO, 9)] = STRANGER
    fake.comment_issue(REPO, 9, t.adopt_comment(KEY, "tester", 41))
    fake.add_issue(REPO, 10, labels={"fr:owed"}, body="another")
    fake.issue_authors[(REPO, 10)] = STRANGER
    fake.comment_issue(REPO, 10, t.adopt_comment(KEY, "tester", 99))

    rep = close_gate_trackers(fake, REPO, 41, "tester", "ok", root=Path("/nonexistent"))

    assert _closes(fake) == []
    (cmd,) = rep.adopt_commands
    assert cmd.startswith(f"gh issue close 9 --repo {REPO} --comment ")
    assert "Gate tester passed on #41: ok" in cmd and rep.discharge


def test_a_dry_run_lists_without_closing() -> None:
    fake = _fake()
    _tracker(fake, 1)

    rep = close_gate_trackers(fake, REPO, 41, "tester", "ok", dry_run=True)

    assert rep.closed == [1] and _closes(fake) == []
    assert any("would close tracker #1" in line for line in rep.lines())


def test_a_list_failure_is_reported_not_raised() -> None:
    fake = _fake()
    _tracker(fake, 1)

    def boom(*a: object, **k: object) -> list[dict[str, object]]:
        raise FakeGhError("rate limited")

    fake.list_issues = boom  # type: ignore[method-assign]
    rep = close_gate_trackers(fake, REPO, 41, "tester", "ok")
    assert rep.closed == [] and "rate limited" in rep.errors[0]


def test_a_close_failure_is_reported_and_the_rest_still_close() -> None:
    fake = _fake()
    _tracker(fake, 1)
    _tracker(fake, 2, key="row:r-two")
    real = fake.close_issue

    def flaky(repo: str, number: int, comment: str) -> None:
        if number == 1:
            raise FakeGhError("boom")
        real(repo, number, comment)

    fake.close_issue = flaky  # type: ignore[method-assign]
    rep = close_gate_trackers(fake, REPO, 41, "tester", "ok")
    assert rep.closed == [2] and "#1" in rep.errors[0]


def test_an_empty_viewer_login_closes_and_adopts_nothing() -> None:
    """p3-r4: a ghost (author-less) issue or comment must not match an unknown viewer."""
    fake = FakeGhClient()
    fake.comment_author = ""  # viewer_login() is empty
    _tracker(fake, 1)
    fake.add_issue(REPO, 2, labels={"fr:owed"}, body="a human's issue")
    fake.comment_issue(REPO, 2, t.adopt_comment(KEY, "tester", 41))

    rep = close_gate_trackers(fake, REPO, 41, "tester", "ok", root=Path("/nonexistent"))

    assert _closes(fake) == [] and rep.closed == [] and rep.adopt_commands == []
    assert len(rep.errors) == 1 and "viewer" in rep.errors[0]


def test_it_lists_only_the_owed_labelled_issues() -> None:
    """p3-r5: the open-issue read is narrowed on the forge by `fr:owed`."""
    fake = _fake()
    _tracker(fake, 1)

    close_gate_trackers(fake, REPO, 41, "tester", "ok")

    (listing,) = [c[1] for c in fake.calls if c[0] == "list_issues"]
    assert listing["labels"] == ["fr:owed"] and listing["state"] == "open"
