"""The cursor's read status (spec 2026-11-24-batch-merge-readiness §A, R1).

`read_cursor` folds every run cursor at an open batch PR's head that names its branch:
delivered only when every one is, and it tells "read, none found" from "could not read".
`collect` stores the fold and the status on the PR; facts move to schema 17.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fr.triage.collect import collect_facts
from fr.triage.cursor import RUNS_DIR, read_cursor
from fr.triage.errors import TriageError
from fr.triage.model import (
    FACTS_READS,
    FACTS_SCHEMA,
    CursorPosition,
    PullRequest,
    Scope,
    load_facts,
)

from tests.unit.triage_fixtures import NOW, FakeForge

REPO = "example-org/alpha"
BRANCH = "feat/batch-x"
HEAD = "a" * 40


class FakeCheckout:
    """A `Checkout` holding *files* (name -> cursor document) at HEAD."""

    def __init__(
        self, files: Mapping[str, Any], *, reach: bool = True, raises: bool = False
    ) -> None:
        self.files = {n: yaml.safe_dump(d) for n, d in files.items()}
        self.reach, self.raises = reach, raises

    def reach_commit(self, sha: str, branch: str) -> bool:
        return self.reach and sha == HEAD and branch == BRANCH

    def list_dir(self, ref: str, directory: str) -> list[str]:
        if self.raises:
            raise TriageError("git failed")
        assert ref == HEAD and directory == RUNS_DIR
        return list(self.files)

    def show(self, ref: str, file: str) -> str | None:
        return self.files.get(file.rsplit("/", 1)[-1])


def _doc(run: str, cursor: str, branch: str = BRANCH, **steps: str) -> dict[str, Any]:
    return {"run": run, "branch": branch, "cursor": cursor,
            "steps": {k: {"state": v} for k, v in steps.items()}}  # fmt: skip


def _pr() -> PullRequest:
    return PullRequest(repo=REPO, number=41, title="t", state="OPEN", is_draft=False, url="u",
                       head_ref=BRANCH, head_oid=HEAD)  # fmt: skip


DONE = CursorPosition(run="r1", step="deliver", kind="deliver-done")


def test_every_cursor_delivered_reads_delivered() -> None:
    files = {"r1.yaml": _doc("r1", "deliver", deliver="done"),
             "r2.yaml": _doc("r2", "deliver", deliver="done")}  # fmt: skip
    assert read_cursor(FakeCheckout(files), _pr()) == (DONE, "read")  # type: ignore[arg-type]


def test_one_cursor_still_delivering_is_not_delivered() -> None:
    """R1 fail-closed (s-r10): one of two cursors at `deliver: running`."""
    files = {"r1.yaml": _doc("r1", "deliver", deliver="done"),
             "r2.yaml": _doc("r2", "deliver", deliver="running")}  # fmt: skip
    got = read_cursor(FakeCheckout(files), _pr())  # type: ignore[arg-type]
    assert got == (CursorPosition(run="r2", step="deliver", kind="none"), "read")


def test_no_cursor_naming_the_branch_reads_none() -> None:
    files = {"other.yaml": _doc("o", "deliver", branch="feat/other", deliver="done")}
    assert read_cursor(FakeCheckout(files), _pr()) == (None, "read")  # type: ignore[arg-type]


def test_an_unreachable_head_or_a_failed_read_is_unread() -> None:
    files = {"r1.yaml": _doc("r1", "deliver", deliver="done")}
    assert read_cursor(FakeCheckout(files, reach=False), _pr()) == (None, "unread")  # type: ignore[arg-type]
    assert read_cursor(FakeCheckout(files, raises=True), _pr()) == (None, "unread")  # type: ignore[arg-type]


# ------------------------------------------------------------------ collect

AT = datetime(2026, 9, 25, 0, 0, tzinfo=UTC)


def _open_pr() -> dict[str, Any]:
    return {"number": 41, "title": "PR", "state": "OPEN", "isDraft": True,
            "createdAt": "2026-09-25T06:00:00Z", "mergedAt": None,
            "url": f"https://github.com/{REPO}/pull/41", "headRefName": BRANCH,
            "headRefOid": HEAD, "closingIssuesReferences": [],
            "author": {"login": "operator"}, "isCrossRepository": False}  # fmt: skip


def _collect(answer: tuple[CursorPosition | None, str]) -> PullRequest:
    forge = FakeForge(issues={REPO: []}, prs={REPO: []}, head_prs={(REPO, BRANCH): [_open_pr()]})
    facts = collect_facts(
        forge, Scope(kind="repo", target=REPO), now=NOW,
        batch_branches=[("alpha", BRANCH, AT)], ledger_branches=[("alpha", BRANCH, AT)],
        cursor_at=lambda pr: answer,  # type: ignore[arg-type,return-value]
    )  # fmt: skip
    (pr,) = facts.batch_prs
    return pr


def test_collect_stores_the_fold_and_its_read_status() -> None:
    pr = _collect((DONE, "read"))
    assert (pr.cursor, pr.cursor_read) == (DONE, "read")
    pr = _collect((None, "unread"))
    assert (pr.cursor, pr.cursor_read) == (None, "unread")
    pr = _collect((None, "no-clone"))
    assert (pr.cursor, pr.cursor_read) == (None, "no-clone")


def test_facts_are_schema_17_and_still_read_3_to_16(tmp_path: Path) -> None:
    assert FACTS_SCHEMA == 17
    assert set(range(3, 17)) <= set(FACTS_READS)
    old = {"schema": 16, "scope": REPO, "kind": "repo", "collected_at": "2026-09-25T06:00:00Z",
           "repos": [REPO], "issues": []}  # fmt: skip
    (tmp_path / "facts.json").write_text(json.dumps(old))
    assert load_facts(tmp_path / "facts.json").schema_ == 16
    pr = _pr()
    assert pr.cursor_read is None  # never asked


def test_the_drivers_reader_says_no_clone_and_caches_by_head(tmp_path: Path) -> None:
    from fr.commands import triage_batch_cmd

    driver = triage_batch_cmd._Driver(
        triage_batch_cmd._scope(REPO, None), tmp_path, named=None, checkouts={},
        max_inflight=4, yes=False,
    )  # fmt: skip
    assert driver.cursor_at(_pr()) == (None, "no-clone")
    driver.checkout_paths = {REPO: tmp_path}
    calls: list[str] = []
    files = {"r1.yaml": _doc("r1", "deliver", deliver="done")}
    driver._reader = lambda repo: calls.append(repo) or FakeCheckout(files)  # type: ignore[method-assign]
    assert driver.cursor_at(_pr()) == (DONE, "read")
    assert driver.cursor_at(_pr()) == (DONE, "read")
    assert calls == [REPO]


def test_a_cursor_with_no_read_status_is_never_delivered() -> None:
    """p1-r6: a cursor at the PR's head whose read status is None (never asked) reads as not
    read, whatever its position."""
    from fr.triage.readiness import _LINES, batch_readiness

    from tests.unit.test_triage_readiness import DONE as R_DONE
    from tests.unit.test_triage_readiness import HEAD as R_HEAD
    from tests.unit.test_triage_readiness import B, _qs

    got = batch_readiness(B, _qs(B, approved=None, cursor=(R_HEAD, R_DONE, None)))
    assert got.verdict == _LINES["not-delivered"].format(r="the run cursor was not read")
    assert got.verdict == "Not ready: not delivered: the run cursor was not read"
    assert not got.admits


def test_a_schema_16_facts_files_delivered_cursor_is_not_admitted(tmp_path: Path) -> None:
    """p1-r6, R1: a schema-16 facts file carries a batch PR's `cursor` but no `cursor_read`;
    its deliver-done cursor was never asked at this head, so the queue does not admit it."""
    from fr.triage.batch import QueueEntry
    from fr.triage.readiness import batch_readiness, fact_cursors

    from tests.unit.test_triage_readiness import HEAD as R_HEAD
    from tests.unit.test_triage_readiness import B, _qs

    pr = {"repo": REPO, "number": 101, "title": "b1", "state": "OPEN", "is_draft": True,
          "url": f"https://github.com/{REPO}/pull/101", "head_ref": BRANCH, "head_oid": R_HEAD,
          "cursor": {"run": "r1", "step": "deliver", "kind": "deliver-done"}}  # fmt: skip
    old = {"schema": 16, "scope": REPO, "kind": "repo", "collected_at": "2026-09-25T06:00:00Z",
           "repos": [REPO], "issues": [], "batch_prs": [pr]}  # fmt: skip
    (tmp_path / "facts.json").write_text(json.dumps(old))
    facts = load_facts(tmp_path / "facts.json")
    (loaded,) = facts.batch_prs
    assert loaded.cursor == DONE and loaded.cursor_read is None
    cursors = fact_cursors([QueueEntry(batch=B, pr=loaded)])
    got = batch_readiness(B, _qs(B, cursor=cursors["b1"]))
    assert not got.admits
    assert got.kind == "approved-not-delivered" and got.reason == "the run cursor was not read"
