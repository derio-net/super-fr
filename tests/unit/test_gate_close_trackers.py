"""P3.T1: close_gate_trackers (spec gate-backfill §H, R12)."""

from __future__ import annotations

import shlex
from pathlib import Path

from fr.gatebackfill import trackers as t
from fr.gatebackfill.close import CloseReport, held_keys
from fr.verification.labels import close_gate_trackers

from tests.unit.fakes import FakeGhClient, FakeGhError
from tests.unit.gatebackfill_fixtures import ME, REPO, STRANGER, row, write_matrix

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
    assert close["comment"].startswith("Gate tester passed on #41: walked live; ")
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


# --- R12: a closing comment states the key's real position -----------------------------------


def _checkout(tmp_path: Path, status: str = "walk-owed") -> Path:
    write_matrix(tmp_path, [row("r-live", status)])
    return tmp_path


def _comment_of_close(fake: FakeGhClient) -> str:
    (close,) = [c[1] for c in fake.calls if c[0] == "close_issue"]
    return str(close["comment"])


def test_r12_the_comment_names_the_command_when_the_key_is_still_owed(tmp_path: Path) -> None:
    fake = _fake()
    _tracker(fake, 1)
    rep = close_gate_trackers(fake, REPO, 41, "tester", "ok", root=_checkout(tmp_path))
    text = _comment_of_close(fake)
    assert text.startswith("Gate tester passed on #41: ok; `row:r-live` is still owed")
    assert "fr acceptance set-status --id r-live" in text
    assert rep.discharge


def test_r12_the_comment_names_the_evidence_when_the_key_is_discharged(tmp_path: Path) -> None:
    fake = _fake()
    _tracker(fake, 1)
    rep = close_gate_trackers(fake, REPO, 41, "tester", "ok", root=_checkout(tmp_path, "walked"))
    text = _comment_of_close(fake)
    assert "`row:r-live` is already discharged: row r-live is walked" in text
    assert "still owed" not in text and "set-status" not in text
    assert rep.discharge == []  # nothing is still owed, so no discharge line either


def test_r12_with_no_checkout_the_comment_says_neither() -> None:
    fake = _fake()
    _tracker(fake, 1)
    close_gate_trackers(fake, REPO, 41, "tester", "ok")
    assert _comment_of_close(fake) == "Gate tester passed on #41: ok"


def test_r12_a_multi_line_discharge_keeps_the_adopted_close_command_on_one_line(
    tmp_path: Path,
) -> None:
    fake = _fake()
    _adopted(fake, 9)
    rep = close_gate_trackers(fake, REPO, 41, "tester", "ok", root=_checkout(tmp_path))
    (cmd,) = rep.adopt_commands
    assert "\n" not in cmd and "is still owed" in cmd
    assert shlex.split(cmd)[:3] == ["gh", "issue", "close"]


# --- R10: --keep -----------------------------------------------------------------------------


def _adopted(
    fake: FakeGhClient, n: int, key: str = KEY, *, gate: str = "tester", pr: int = 41
) -> None:
    fake.add_issue(REPO, n, labels={"fr:owed"}, body="a human's issue")
    fake.issue_authors[(REPO, n)] = STRANGER
    fake.comment_issue(REPO, n, t.adopt_comment(key, gate, pr))


def _keep(fake: FakeGhClient, root: Path | None, *keys: str, dry_run: bool = False) -> CloseReport:
    return close_gate_trackers(
        fake, REPO, 41, "tester", "partial", root=root, keep=frozenset(keys), dry_run=dry_run
    )


def test_r10_keep_converts_a_tracker_comment_first_then_body_and_never_closes(
    tmp_path: Path,
) -> None:
    fake = _fake()
    _tracker(fake, 1)
    fake.issue_titles[(REPO, 1)] = "Owed: walk the widget"

    rep = _keep(fake, _checkout(tmp_path), KEY)

    names = [c[0] for c in fake.calls]
    assert names.index("comment_issue") < names.index("edit_issue_body")
    assert _closes(fake) == [] and rep.kept == [1] and rep.closed == []
    body = fake.issues[(REPO, 1)].body
    assert t.fr_gate_marker(body) is None and t.fr_passed_marker(body) == ("tester", 41)
    assert body.startswith("Owed: walk the widget\n")
    (comment,) = fake.issue_comments[(REPO, 1)]
    assert "still owed" in comment["body"] and "set-status --id r-live" in comment["body"]
    assert rep.discharge and "kept #1" in "\n".join(rep.lines())


def test_r10_a_kept_tracker_is_not_closed_by_a_later_pass(tmp_path: Path) -> None:
    fake = _fake()
    _tracker(fake, 1)
    root = _checkout(tmp_path)
    _keep(fake, root, KEY)
    before = fake.attempted_mutations

    rep = close_gate_trackers(fake, REPO, 41, "tester", "again", root=root)

    assert _closes(fake) == [] and rep.closed == [] and fake.attempted_mutations == before


def test_r10_only_the_named_key_is_kept(tmp_path: Path) -> None:
    fake = _fake()
    _tracker(fake, 1)
    _tracker(fake, 2, key="row:r-two")
    rep = _keep(fake, _checkout(tmp_path), KEY)
    assert rep.kept == [1] and rep.closed == [2] and _closes(fake) == [2]


def test_r10_a_keep_dry_run_lists_and_writes_nothing(tmp_path: Path) -> None:
    fake = _fake()
    _tracker(fake, 1)
    _adopted(fake, 9, "row:r-nine")
    before = fake.attempted_mutations
    rep = _keep(fake, _checkout(tmp_path), KEY, "row:r-nine", dry_run=True)
    assert rep.kept == [1, 9] and fake.attempted_mutations == before
    assert "would keep #1" in "\n".join(rep.lines()) and rep.adopt_commands == []


def test_r10_a_failed_rewrite_leaves_the_tracker_held_and_a_retry_finishes(tmp_path: Path) -> None:
    fake = _fake()
    _tracker(fake, 1)
    root = _checkout(tmp_path)
    fake.fail_on_mutation = fake.attempted_mutations + 1  # the comment lands, the rewrite fails
    rep = _keep(fake, root, KEY)
    assert rep.errors and rep.kept == [] and _closes(fake) == []
    assert t.fr_gate_marker(fake.issues[(REPO, 1)].body) == ("tester", 41)
    fake.fail_on_mutation = None
    assert _keep(fake, root, KEY).kept == [1]
    assert t.fr_passed_marker(fake.issues[(REPO, 1)].body) == ("tester", 41)


def test_r10_keep_with_no_checkout_never_closes_the_tracker() -> None:
    """`fr gate pass` refuses this first; the helper must still not lose the key."""
    fake = _fake()
    _tracker(fake, 1)
    rep = _keep(fake, None, KEY)
    assert _closes(fake) == [] and rep.errors and rep.kept == []


def test_r10_an_adopted_issue_gets_the_tracked_only_comment_once_and_no_close_command(
    tmp_path: Path,
) -> None:
    fake = _fake()
    _adopted(fake, 9)
    root = _checkout(tmp_path)

    rep = _keep(fake, root, KEY)

    assert rep.adopt_commands == [] and rep.kept == [9] and _closes(fake) == []
    comments = fake.issue_comments[(REPO, 9)]
    assert len(comments) == 2 and t.fr_adopt_passed_marker(comments[1]["body"]) == (
        KEY, "tester", 41,
    )  # fmt: skip
    # a retry with --keep writes nothing and prints no close command
    before = fake.attempted_mutations
    again = _keep(fake, root, KEY)
    assert again.adopt_commands == [] and again.kept == [] and fake.attempted_mutations == before
    # a later pass without --keep prints no close command either
    later = close_gate_trackers(fake, REPO, 41, "tester", "ok", root=root)
    assert later.adopt_commands == [] and fake.attempted_mutations == before


def test_r10_a_tracked_only_comment_by_someone_else_does_not_override(tmp_path: Path) -> None:
    fake = _fake()
    _adopted(fake, 9)
    fake.issue_comments[(REPO, 9)].append(
        {"author": STRANGER, "body": t.adopt_passed_comment(KEY, "tester", 41, repo_root=tmp_path)}
    )
    rep = close_gate_trackers(fake, REPO, 41, "tester", "ok", root=_checkout(tmp_path))
    assert len(rep.adopt_commands) == 1


def test_r10_a_tracked_only_comment_for_another_gate_or_pr_does_not_override(
    tmp_path: Path,
) -> None:
    fake = _fake()
    _adopted(fake, 9)
    root = _checkout(tmp_path)
    fake.comment_issue(REPO, 9, t.adopt_passed_comment(KEY, "devops", 41, repo_root=root))
    fake.comment_issue(REPO, 9, t.adopt_passed_comment(KEY, "tester", 99, repo_root=root))
    assert len(close_gate_trackers(fake, REPO, 41, "tester", "ok", root=root).adopt_commands) == 1


def test_r10_a_newer_adopt_comment_is_not_overridden_by_an_older_tracked_only_one(
    tmp_path: Path,
) -> None:
    """The override is of its OLDER `fr-gate-adopt:` comment."""
    fake = _fake()
    root = _checkout(tmp_path)
    fake.add_issue(REPO, 9, labels={"fr:owed"}, body="a human's issue")
    fake.issue_authors[(REPO, 9)] = STRANGER
    fake.comment_issue(REPO, 9, t.adopt_passed_comment(KEY, "tester", 41, repo_root=root))
    fake.comment_issue(REPO, 9, t.adopt_comment(KEY, "tester", 41))
    assert len(close_gate_trackers(fake, REPO, 41, "tester", "ok", root=root).adopt_commands) == 1


def test_r10_keeping_one_of_two_keys_on_an_adopted_issue_prints_no_close_command(
    tmp_path: Path,
) -> None:
    fake = _fake()
    _adopted(fake, 9)
    fake.comment_issue(REPO, 9, t.adopt_comment("row:r-two", "tester", 41))
    rep = _keep(fake, _checkout(tmp_path), "row:r-two")
    assert rep.adopt_commands == [] and rep.kept == [9]


# --- R11: what holds a key --------------------------------------------------------------------


def test_r11_held_keys_counts_held_and_tracked_only_for_this_pr_and_gate(tmp_path: Path) -> None:
    fake = _fake()
    root = _checkout(tmp_path)
    _tracker(fake, 1)
    fake.add_issue(
        REPO, 2, labels={"fr:owed"},
        body=t.passed_tracker_body("row:tracked", "t", "tester", 41, repo_root=root),
    )  # fmt: skip
    _tracker(fake, 3, key="row:other-pr", pr=42)
    _tracker(fake, 4, key="row:other-gate", gate="devops")
    _adopted(fake, 5, "row:adopted")
    fake.add_issue(REPO, 6, labels={"fr:owed"}, body="x")
    fake.issue_authors[(REPO, 6)] = STRANGER
    fake.comment_issue(REPO, 6, t.adopt_passed_comment("row:adopted-kept", "tester", 41,
                                                       repo_root=root))  # fmt: skip
    fake.add_issue(
        REPO, 7, labels={"fr:owed"}, body=t.tracker_body("row:foreign", "t", "tester", 41)
    )
    fake.issue_authors[(REPO, 7)] = STRANGER  # a marker on a foreign issue is only text

    assert held_keys(fake, REPO, 41, "tester") == {
        KEY, "row:tracked", "row:adopted", "row:adopted-kept",
    }  # fmt: skip


def test_the_driver_call_shape_still_closes() -> None:
    """`triage_batch_cmd` passes no `keep`, and is not edited."""
    fake = _fake()
    _tracker(fake, 1)
    rep = close_gate_trackers(fake, REPO, 41, "tester", "rows walked", root=Path("/nonexistent"))
    assert rep.closed == [1] and rep.kept == []
