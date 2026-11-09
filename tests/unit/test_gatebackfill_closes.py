"""`fr gate backfill` closes the trackers whose key is discharged (spec 2026-11-08-sweep-fixes
R13, R15): the CLI over a real checkout with a fetched default ref, and a fake forge."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.commands import gate_cmd
from fr.gatebackfill import trackers as t
from fr.gatebackfill.close import holders_by_key, list_closes
from fr.gatebackfill.model import PlanEntry, PlanFile, PrHit, dropped_decisions, merge_plan
from fr.journal.model import JournalEntry, append_journal_entry, journal_path, owed_body
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.gatebackfill_fixtures import (
    ME,
    REPO,
    STRANGER,
    FakeForge,
    commit_at,
    git,
    issue,
    row,
    write_matrix,
)

DONE = "row:r-done"  # walked
OWED = "row:r-owed"  # walk-owed
WRITES = {
    "ensure_labels", "edit_pr_labels", "edit_issue_labels", "create_issue", "comment_issue",
    "edit_issue_body", "close_issue", "edit_issue_state", "comment_pr", "edit_issue",
}  # fmt: skip


class Env:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp = tmp_path
        self.plan_file = tmp_path / "home/.cache/fr/gate-backfill/example-org--widgets/plan.yaml"
        root = tmp_path / "widgets"
        root.mkdir()
        bare = tmp_path / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
        git(root, "init", "-q", "-b", "main")
        git(root, "remote", "add", "origin", f"https://github.com/{REPO}.git")
        git(root, "config", f"url.{bare}.insteadOf", f"https://github.com/{REPO}.git")
        write_matrix(root, [row("r-done", "walked"), row("r-owed", "walk-owed")])
        self.root = root
        self.publish("seed")
        self.fake = FakeGhClient()
        self.fake.comment_author = ME
        self.fake.add_pr(REPO, 41, state="MERGED", head_ref="feat/x", labels=["gate:tester-passed"])
        monkeypatch.setattr(gate_cmd, "client_for_url", lambda url: self.fake)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        monkeypatch.chdir(root)

    def publish(self, msg: str = "work") -> None:
        commit_at(self.root, msg, "2026-10-30T00:00:00+00:00")
        git(self.root, "push", "-q", "origin", "HEAD:refs/heads/main")
        git(self.root, "fetch", "-q", "origin")
        git(self.root, "remote", "set-head", "origin", "main")

    def tracked_only(self, n: int, key: str = DONE, pr: int = 41) -> None:
        body = t.passed_tracker_body(key, "t", "tester", pr, repo_root=self.root)
        self.fake.add_issue(REPO, n, labels={"fr:owed"}, body=body)

    def adopted(self, n: int, key: str = DONE, *, author: str = ME) -> None:
        self.fake.add_issue(REPO, n, labels={"fr:owed"}, body="a human's issue")
        self.fake.issue_authors[(REPO, n)] = STRANGER
        text = t.adopt_passed_comment(key, "tester", 41, repo_root=self.root)
        self.fake.issue_comments.setdefault((REPO, n), []).append({"author": author, "body": text})

    def dry(self, *args: str, ok: bool = True) -> str:
        before = self.fake.attempted_mutations
        result = CliRunner().invoke(app, ["gate", "backfill", *args])
        assert self.fake.attempted_mutations == before, "a dry run wrote to the forge"
        if ok:
            assert result.exit_code == 0, result.output
        return result.output

    def yes(self, *args: str) -> Any:
        return CliRunner().invoke(app, ["gate", "backfill", *args, "--yes"])

    def plan(self) -> dict[str, Any]:
        return yaml.safe_load(self.plan_file.read_text())

    def closes(self) -> list[int]:
        return [c[1]["number"] for c in self.fake.calls if c[0] == "close_issue"]

    def writes(self) -> list[str]:
        return [c[0] for c in self.fake.calls if c[0] in WRITES]


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    return Env(tmp_path, monkeypatch)


# --- the dry run ----------------------------------------------------------------------------


def test_a_dry_run_lists_a_discharged_tracked_only_tracker_and_records_it(env: Env) -> None:
    env.tracked_only(5)

    out = env.dry()

    assert "Trackers to close (1)" in out and f"{DONE}  {REPO}#5" in out
    assert env.plan()["closes"] == [
        {"key": DONE, "ref": f"{REPO}#5", "adopted": False, "evidence": "row r-done is walked"}
    ]


def test_the_key_leaves_the_entries_and_a_recorded_decision_is_dropped_with_a_note(
    env: Env,
) -> None:
    env.tracked_only(5)
    env.tracked_only(6, OWED)
    env.dry()
    data = env.plan()
    data["entries"] = [
        {**e, "decision": "park"} if e["key"] == OWED else e for e in data["entries"]
    ]
    data["entries"].append(PlanEntry(key=DONE, decision="park").model_dump(mode="json"))
    env.plan_file.write_text(yaml.safe_dump(data))

    out = env.dry()

    keys = [e["key"] for e in env.plan()["entries"]]
    assert DONE not in keys and OWED in keys
    assert f"{DONE}: discharged, so your decision `park` was dropped" in out
    parked = [e for e in env.plan()["entries"] if e["key"] == OWED]
    assert parked[0]["decision"] == "park"  # a key still owed keeps its decision


def test_merge_plan_drops_a_closing_key_and_its_adopt() -> None:
    pr = PrHit(number=41, basis="commit")
    old = PlanFile(
        repo=REPO,
        entries=[PlanEntry(key=DONE, pr=pr, decision=f"adopt {REPO}#8", default_decision="owed")],
    )
    closing = frozenset({DONE})
    assert merge_plan(old, [PlanEntry(key=DONE, pr=pr)], closing=closing) == []
    assert merge_plan(None, [PlanEntry(key=DONE, pr=pr)], closing=closing) == []
    (note,) = dropped_decisions(old, closing)
    assert f"adopt {REPO}#8" in note


def test_a_computed_default_is_dropped_without_a_note() -> None:
    old = PlanFile(repo=REPO, entries=[PlanEntry(key=DONE)])
    assert dropped_decisions(old, frozenset({DONE})) == []


@pytest.mark.parametrize(
    "how",
    ["held", "undischarged", "issue-key", "foreign-body", "foreign-comment", "unlabelled"],
)
def test_what_a_dry_run_never_lists(env: Env, how: str) -> None:
    if how == "held":  # a `fr-gate:` held tracker is the pass's, not the backfill's
        env.fake.add_issue(
            REPO, 5, labels={"fr:owed"}, body=t.tracker_body(DONE, "t", "tester", 41)
        )
    elif how == "undischarged":
        env.tracked_only(5, OWED)
    elif how == "issue-key":
        env.tracked_only(5, f"issue:{REPO}#3")
    elif how == "foreign-body":  # a marker on a stranger's issue is only text
        env.tracked_only(5)
        env.fake.issue_authors[(REPO, 5)] = STRANGER
    elif how == "foreign-comment":  # markers count only from this account
        env.adopted(5, author=STRANGER)
    elif how == "unlabelled":
        env.tracked_only(5)
        env.fake.issues[(REPO, 5)].labels = set()
    env.dry(ok=False)
    assert env.plan()["closes"] == []


def test_a_manifest_only_key_is_untouched(env: Env, tmp_path: Path) -> None:
    key = "row:r-manifest"
    env.tracked_only(5, key)
    manifest = tmp_path / "m.yaml"
    manifest.write_text(yaml.safe_dump({"schema": 1, "items": [
        {"key": key, "kind": "walk", "title": "a walk", "pr": 41, "gate": "tester"},
    ]}))  # fmt: skip
    env.dry("--from", str(manifest))
    assert env.plan()["closes"] == []
    # no row, no evidence: without the manifest as well
    env.dry()
    assert env.plan()["closes"] == []
    assert env.yes().exit_code == 0 and env.closes() == []


def test_a_manifest_new_item_with_evidence_stays_the_manifests_claim(
    env: Env, tmp_path: Path
) -> None:
    env.tracked_only(5)
    manifest = tmp_path / "m.yaml"
    manifest.write_text(yaml.safe_dump({"schema": 1, "items": [
        {"key": DONE, "kind": "walk", "title": "a walk", "pr": 41, "gate": "tester"},
    ]}))  # fmt: skip
    env.dry("--from", str(manifest))
    assert env.plan()["closes"] == []
    assert DONE in [e["key"] for e in env.plan()["entries"]]


def test_a_key_resolved_in_its_journal_is_listed_though_it_left_the_fold(env: Env) -> None:
    """Why the listing is built from the issues: once resolved, the fold drops the tracker."""
    key = "row:not-a-row"
    path = journal_path(env.root, "spec", "some-slug")
    for entry in (
        JournalEntry(
            kind="owed", scope="spec", id="o1", created="2026-10-11T10:00:00+00:00", title="o",
            body=owed_body(what="w", why="y", how="h", key=key),
        ),
        JournalEntry(
            kind="finding", scope="spec", id="o1-r", created="2026-10-11T10:00:00+00:00",
            title="r", resolves="o1", state="fixed",
        ),
    ):  # fmt: skip
        append_journal_entry(path, "some-slug", entry)
    env.publish()
    env.tracked_only(5, key)
    assert "Trackers to close (1)" in env.dry()
    assert env.yes().exit_code == 0 and env.closes() == [5]


def test_a_discharged_key_with_another_holders_marker_is_not_listed(env: Env) -> None:
    env.tracked_only(5)
    env.fake.add_issue(REPO, 6, labels={"fr:owed"}, body=f"text\n<!-- fr-owed:{DONE} -->")
    env.fake.issue_authors[(REPO, 6)] = STRANGER
    out = env.dry(ok=False)
    assert env.plan()["closes"] == [] and "#6 also carries its marker" in out


# --- --yes ----------------------------------------------------------------------------------


def test_yes_closes_with_the_evidence_and_a_second_run_writes_nothing(env: Env) -> None:
    env.tracked_only(5)
    env.dry()

    result = env.yes()

    assert result.exit_code == 0, result.output
    (close,) = [c[1] for c in env.fake.calls if c[0] == "close_issue"]
    assert close["number"] == 5 and "row r-done is walked" in close["comment"]
    assert f"closed tracker {REPO}#5" in result.output
    assert "new candidate" not in result.output
    before = env.fake.attempted_mutations
    again = env.yes()
    assert again.exit_code == 0, again.output
    assert env.fake.attempted_mutations == before and "0 change(s), 0 failed" in again.output


def test_a_dry_run_after_the_close_lists_nothing(env: Env) -> None:
    env.tracked_only(5)
    env.dry()
    env.yes()
    assert "Trackers to close" not in env.dry() and env.plan()["closes"] == []


def test_a_key_discharged_after_the_dry_run_waits_for_the_next_one(env: Env) -> None:
    env.tracked_only(5, OWED)
    env.dry(ok=False)
    write_matrix(env.root, [row("r-done", "walked"), row("r-owed", "walked")])
    env.publish()

    result = env.yes()

    assert env.closes() == [] and "closed tracker" not in result.output
    env.dry()
    assert env.yes().exit_code == 0 and env.closes() == [5]


def test_a_key_no_longer_discharged_at_yes_is_not_closed(env: Env) -> None:
    env.tracked_only(5)
    env.dry()
    write_matrix(env.root, [row("r-done", "walk-owed"), row("r-owed", "walk-owed")])
    env.publish()

    result = env.yes()

    assert env.closes() == [] and "no longer discharged" in result.output


def test_a_tracker_rewritten_to_held_after_the_dry_run_is_not_closed(env: Env) -> None:
    env.tracked_only(5)
    env.dry()
    env.fake.issues[(REPO, 5)].body = t.tracker_body(DONE, "t", "tester", 41)
    result = env.yes()
    assert env.closes() == [] and "not an fr-owned tracked-only tracker" in result.output


@pytest.mark.parametrize("adopted", [False, True])
def test_a_hand_edited_plan_cannot_close_someone_elses_issue(env: Env, adopted: bool) -> None:
    """The plan file only names what to look at; the forge's facts decide."""
    env.fake.add_issue(REPO, 7, labels={"fr:owed"}, body=f"x\n<!-- fr-owed:{DONE} -->")
    env.fake.issue_authors[(REPO, 7)] = STRANGER
    env.dry(ok=False)
    data = env.plan()
    data["closes"] = [{"key": DONE, "ref": f"{REPO}#7", "adopted": adopted, "evidence": "trust me"}]
    env.plan_file.write_text(yaml.safe_dump(data))
    result = env.yes()
    assert env.closes() == [] and not [c for c in env.fake.calls if c[0] == "comment_issue"]
    assert "skipped" in result.output


def test_a_plan_close_naming_another_repo_is_skipped(env: Env) -> None:
    env.tracked_only(5)
    env.dry()
    data = env.plan()
    data["closes"][0]["ref"] = "other-org/other#5"
    env.plan_file.write_text(yaml.safe_dump(data))
    result = env.yes()
    assert env.closes() == [] and "is not in" in result.output


def test_one_forge_error_leaves_the_rest_going_on(env: Env) -> None:
    write_matrix(env.root, [row("r-done", "walked"), row("r-two", "walked")])
    env.publish()
    env.tracked_only(5)
    env.tracked_only(6, "row:r-two")
    env.dry()
    real = env.fake.close_issue

    def flaky(repo: str, number: int, comment: str) -> None:
        if number == 5:
            from tests.unit.fakes import FakeGhError

            raise FakeGhError("boom")
        real(repo, number, comment)

    env.fake.close_issue = flaky  # type: ignore[method-assign]
    result = env.yes()
    assert result.exit_code == 1 and "FAILED: boom" in result.output
    assert env.closes() == [6]


def test_tracking_none_closes_nothing(env: Env) -> None:
    env.tracked_only(5)
    env.dry()
    profiles = env.root / ".devcontainer" / "fr-profiles.yaml"
    profiles.parent.mkdir()
    profiles.write_text("schema_version: 2\ntracking: {type: none}\n")
    result = env.yes()
    assert result.exit_code == 0, result.output
    assert env.closes() == [] and "tracking none" in result.output


# --- R15: the checkout ----------------------------------------------------------------------


def _head_behind(env: Env) -> None:
    (env.root / "later.txt").write_text("x\n")
    env.publish()
    git(env.root, "reset", "-q", "--hard", "HEAD~1")


def _head_ahead(env: Env) -> None:
    (env.root / "later.txt").write_text("x\n")
    commit_at(env.root, "local", "2026-10-30T00:00:00+00:00")


def _dirty_acceptance(env: Env) -> None:
    (env.root / "docs/acceptance/scratch.txt").write_text("x\n")


def _dirty_superpowers(env: Env) -> None:
    d = env.root / "docs/superpowers"
    d.mkdir(parents=True, exist_ok=True)
    (d / "scratch.txt").write_text("x\n")


def _hidden_untracked(env: Env) -> None:
    """p4-r9: the operator's config must not hide uncommitted evidence."""
    git(env.root, "config", "status.showUntrackedFiles", "no")
    (env.root / "docs/acceptance/scratch.txt").write_text("x\n")


def _no_default_ref(env: Env) -> None:
    git(env.root, "remote", "remove", "origin")
    git(env.root, "remote", "add", "origin", f"https://github.com/{REPO}.git")


BLOCKERS = {
    "behind": (_head_behind, "HEAD is not"),
    "ahead": (_head_ahead, "HEAD is not"),
    "acceptance": (_dirty_acceptance, "uncommitted"),
    "superpowers": (_dirty_superpowers, "uncommitted"),
    "hidden-untracked": (_hidden_untracked, "uncommitted"),
    "no-ref": (_no_default_ref, "no default ref"),
}


@pytest.mark.parametrize("case", sorted(BLOCKERS))
def test_a_dry_run_on_a_checkout_r15_refuses_lists_nothing_and_says_so(env: Env, case: str) -> None:
    make, says = BLOCKERS[case]
    env.tracked_only(5)
    make(env)
    out = env.dry()
    assert env.plan()["closes"] == [] and "no tracker closes" in out and says in out


@pytest.mark.parametrize("case", sorted(BLOCKERS))
def test_yes_on_a_checkout_r15_refuses_closes_nothing_and_says_so(env: Env, case: str) -> None:
    make, says = BLOCKERS[case]
    env.tracked_only(5)
    env.dry()
    make(env)
    result = env.yes()
    assert env.closes() == [] and "no tracker closes" in result.output and says in result.output


def test_a_stale_evidence_tree_outside_the_two_is_not_a_blocker(env: Env) -> None:
    env.tracked_only(5)
    (env.root / "scratch.txt").write_text("x\n")
    env.dry()
    assert env.yes().exit_code == 0 and env.closes() == [5]


# --- an adopted issue ------------------------------------------------------------------------


def test_an_adopted_issue_gets_one_evidence_comment_and_a_printed_close_and_is_never_closed(
    env: Env,
) -> None:
    env.adopted(8)
    out = env.dry()
    assert "Trackers to close (1)" in out and f"{REPO}#8 (adopted" in out
    assert env.plan()["closes"][0]["adopted"] is True

    result = env.yes()

    assert result.exit_code == 0, result.output
    assert env.closes() == [] and env.fake.issues[(REPO, 8)].state == "OPEN"
    (comment,) = [c[1] for c in env.fake.calls if c[0] == "comment_issue"]
    assert comment["number"] == 8 and "row r-done is walked" in comment["body"]
    assert t.fr_adopt_discharged_marker(comment["body"]) == (DONE, 41)
    assert f"gh issue close 8 --repo {REPO} --comment " in result.output
    assert "edit_issue_body" not in env.writes()

    before = env.fake.attempted_mutations
    again = env.yes()
    assert again.exit_code == 0 and env.fake.attempted_mutations == before
    assert "gh issue close 8" in again.output  # still printed: closing it is the operator's


def test_after_the_evidence_comment_a_dry_run_records_nothing_and_still_prints_the_close(
    env: Env,
) -> None:
    env.adopted(8)
    env.dry()
    env.yes()
    out = env.dry()
    assert env.plan()["closes"] == [] and f"gh issue close 8 --repo {REPO}" in out
    # the issue is not offered back as a candidate of its own
    assert f"issue:{REPO}#8" not in [e["key"] for e in env.plan()["entries"]]
    env.dry()


def test_a_foreign_evidence_marker_does_not_silence_the_comment(env: Env) -> None:
    env.adopted(8)
    env.fake.issue_comments[(REPO, 8)].append(
        {"author": STRANGER, "body": t.adopt_discharged_comment(DONE, 41, "forged")}
    )
    env.dry()
    assert env.yes().exit_code == 0
    assert len([c for c in env.fake.calls if c[0] == "comment_issue"]) == 1


def test_a_failed_evidence_comment_is_the_entrys_error_and_a_retry_posts_it(env: Env) -> None:
    env.adopted(8)
    env.dry()
    env.fake.fail_on_mutation = env.fake.attempted_mutations
    failed = env.yes()
    assert failed.exit_code == 1 and "gh issue close" not in failed.output
    env.fake.fail_on_mutation = None
    assert env.yes().exit_code == 0
    assert len([c for c in env.fake.calls if c[0] == "comment_issue"]) == 1


def test_an_adopted_key_still_owed_is_not_listed(env: Env) -> None:
    env.adopted(8, OWED)
    env.dry(ok=False)
    assert env.plan()["closes"] == []


# --- the listing over the port ---------------------------------------------------------------


def test_the_listing_reads_comments_once_per_foreign_owed_issue_only(env: Env) -> None:
    from fr.archive import merge_evidence

    forge = FakeForge()
    forge.issues = [
        issue(1, body=t.passed_tracker_body(DONE, "t", "tester", 41, repo_root=env.root)),
        issue(2, body="mine, no marker"),
        issue(3, body="not owed", labels=(), author=STRANGER),
        issue(4, body="foreign owed", author=STRANGER),
    ]
    listing = list_closes(env.root, forge, evidence=merge_evidence(env.root, fetch=False))
    assert [c for c in forge.calls if c[0] == "issue_comments"] == [
        ("issue_comments", 2),
        ("issue_comments", 4),
    ]
    assert [c.ref for c in listing.closes] == [f"{REPO}#1"]


def test_a_failed_read_lists_nothing_and_says_so(env: Env) -> None:
    from fr.archive import merge_evidence

    forge = FakeForge()

    def boom() -> list[dict[str, Any]]:
        raise OSError("rate limited")

    forge.open_issues = boom  # type: ignore[method-assign]
    listing = list_closes(env.root, forge, evidence=merge_evidence(env.root, fetch=False))
    assert listing.closes == [] and "rate limited" in listing.notes[0]


# --- the phase 4 review -----------------------------------------------------------------------


def _same_account_adopted(env: Env, n: int, key: str = DONE) -> None:
    env.fake.add_issue(REPO, n, labels={"fr:owed"}, body="the operator's own issue")
    text = t.adopt_passed_comment(key, "tester", 41, repo_root=env.root)
    env.fake.issue_comments.setdefault((REPO, n), []).append({"author": ME, "body": text})


def test_p4_r3_a_same_account_adopted_issue_gets_the_evidence_comment_never_a_close(
    env: Env,
) -> None:
    _same_account_adopted(env, 8)
    out = env.dry()
    assert f"{REPO}#8 (adopted" in out
    assert env.plan()["closes"][0]["adopted"] is True
    result = env.yes()
    assert result.exit_code == 0, result.output
    assert env.closes() == [] and f"gh issue close 8 --repo {REPO}" in result.output
    (comment,) = [c[1] for c in env.fake.calls if c[0] == "comment_issue"]
    assert t.fr_adopt_discharged_marker(comment["body"]) == (DONE, 41)
    before = env.fake.attempted_mutations
    assert env.yes().exit_code == 0 and env.fake.attempted_mutations == before


def test_p4_r3_a_same_account_adopted_issue_is_no_candidate_of_its_own(env: Env) -> None:
    _same_account_adopted(env, 8, OWED)  # not yet discharged
    env.dry(ok=False)
    keys = [e["key"] for e in env.plan()["entries"]]
    assert f"issue:{REPO}#8" not in keys
    _same_account_adopted(env, 9)  # discharged
    env.dry(ok=False)
    env.yes()
    env.dry(ok=False)
    keys = [e["key"] for e in env.plan()["entries"]]
    assert f"issue:{REPO}#8" not in keys and f"issue:{REPO}#9" not in keys


def test_p4_r3_a_stray_marker_comment_on_a_same_account_issue_is_only_text(env: Env) -> None:
    _same_account_adopted(env, 8)
    env.fake.issue_comments[(REPO, 8)][0]["author"] = STRANGER
    env.dry(ok=False)
    assert env.plan()["closes"] == []


def test_p4_r7_yes_from_a_manifest_honours_its_claim_on_a_recorded_close(
    env: Env, tmp_path: Path
) -> None:
    env.tracked_only(5)
    env.dry()
    assert env.plan()["closes"]
    manifest = tmp_path / "m.yaml"
    manifest.write_text(yaml.safe_dump({"schema": 1, "items": [
        {"key": DONE, "kind": "walk", "title": "a walk", "pr": 41, "gate": "tester"},
    ]}))  # fmt: skip
    result = env.yes("--from", str(manifest))
    assert result.exit_code == 0, result.output
    assert env.closes() == []
    assert f"{DONE}: the manifest names it as owed, so its recorded close was dropped" in (
        result.output
    )


def test_p4_r8_a_key_held_by_a_strangers_marker_is_refused_with_the_working_route(
    env: Env,
) -> None:
    env.fake.add_issue(REPO, 6, labels={"fr:owed"}, body=f"text\n<!-- fr-owed:{OWED} -->")
    env.fake.issue_authors[(REPO, 6)] = STRANGER
    write_matrix(env.root, [row("r-done", "walked"), row("r-owed", "manual")])
    env.publish()
    out = env.dry(ok=False)
    assert f"{OWED}: owed refused" in out and f"decision: adopt {REPO}#6" in out


def test_p4_r8_a_key_held_by_frs_own_tracker_is_not_refused(env: Env) -> None:
    env.tracked_only(5, "row:r-gone")  # no row: the fold holds it through this tracker alone
    env.dry()
    assert "row:r-gone" in [e["key"] for e in env.plan()["entries"]]


def test_p4_r10_two_tracked_only_comments_for_one_key_list_one_close(env: Env) -> None:
    env.adopted(8)
    env.fake.issue_comments[(REPO, 8)].append(
        {"author": ME, "body": t.adopt_passed_comment(DONE, "devops", 41, repo_root=env.root)}
    )
    env.fake.issue_comments[(REPO, 8)].append(
        {"author": ME, "body": t.adopt_passed_comment(DONE, "tester", 42, repo_root=env.root)}
    )
    assert "Trackers to close (1)" in env.dry()
    assert len(env.plan()["closes"]) == 1
    assert env.yes().exit_code == 0
    assert len([c for c in env.fake.calls if c[0] == "comment_issue"]) == 1
    before = env.fake.attempted_mutations
    assert env.yes().exit_code == 0 and env.fake.attempted_mutations == before
    env.dry()
    assert env.plan()["closes"] == []


def test_p4_r11_the_holder_index_names_only_foreign_owed_markers() -> None:
    marker = f"x\n<!-- fr-owed:{DONE} -->"
    issues = [
        issue(1, body=marker),  # fr's own tracker: not another holder
        issue(2, body=marker, author=STRANGER),
        issue(3, body=marker, labels=(), author=STRANGER),  # no owed label: the fold ignores it
        issue(4, body=marker, labels=("fr:awaiting-live",), author=STRANGER),
        issue(5, body="no marker", author=STRANGER),
    ]
    assert holders_by_key(issues, ME) == {DONE: {2, 4}}


def test_p4_r11_an_adopted_issues_own_marker_does_not_block_itself(env: Env) -> None:
    env.adopted(8)
    env.fake.issues[(REPO, 8)].body = f"x\n<!-- fr-owed:{DONE} -->"
    env.dry()
    assert env.plan()["closes"][0]["ref"] == f"{REPO}#8"
