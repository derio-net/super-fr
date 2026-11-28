"""The cursor's read status (spec 2026-11-24-batch-merge-readiness §A, R1).

`read_cursor` folds every run cursor at an open batch PR's head that names its branch:
delivered only when every one is, and it tells "read, none found" from "could not read".
`collect` stores the fold and the status on the PR; facts move to schema 19.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.triage.collect import collect_facts
from fr.triage.cursor import RUNS_DIR, read_cursor
from fr.triage.errors import TriageError
from fr.triage.model import (
    FACTS_READS,
    FACTS_SCHEMA,
    CursorAnswer,
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
        # a str value is the file's raw text (a corrupt cursor), anything else is dumped
        self.files = {n: d if isinstance(d, str) else yaml.safe_dump(d) for n, d in files.items()}
        self.reach, self.raises = reach, raises

    def reach_failure(self, sha: str, branch: str) -> str:
        ok = self.reach and sha == HEAD and branch == BRANCH
        return "" if ok else f"fetch of {branch} failed: network down"

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
    assert read_cursor(FakeCheckout(files), _pr()) == (DONE, "read", "")  # type: ignore[arg-type]


def test_one_cursor_still_delivering_is_not_delivered() -> None:
    """R1 fail-closed (s-r10): one of two cursors at `deliver: running`."""
    files = {"r1.yaml": _doc("r1", "deliver", deliver="done"),
             "r2.yaml": _doc("r2", "deliver", deliver="running")}  # fmt: skip
    got = read_cursor(FakeCheckout(files), _pr())  # type: ignore[arg-type]
    assert got == (CursorPosition(run="r2", step="deliver", kind="none"), "read", "")


def test_no_cursor_naming_the_branch_reads_none() -> None:
    files = {"other.yaml": _doc("o", "deliver", branch="feat/other", deliver="done")}
    assert read_cursor(FakeCheckout(files), _pr()) == (None, "read", "")  # type: ignore[arg-type]


def test_an_unreachable_head_or_a_failed_read_is_unread_with_its_cause() -> None:
    """l-errors-r2: the cause of a failed read is carried, never swallowed."""
    files = {"r1.yaml": _doc("r1", "deliver", deliver="done")}
    got = read_cursor(FakeCheckout(files, reach=False), _pr())  # type: ignore[arg-type]
    assert (got.position, got.read) == (None, "unread")
    assert got.detail == f"head {HEAD[:12]} not reached: fetch of {BRANCH} failed: network down"
    got = read_cursor(FakeCheckout(files, raises=True), _pr())  # type: ignore[arg-type]
    assert (got.position, got.read) == (None, "unread")
    assert got.detail == f"reading {RUNS_DIR} at {HEAD[:12]} failed: git failed"


def test_a_corrupt_cursor_beside_a_delivered_one_is_unread() -> None:
    """l-security-r3 / l-errors-r1 (R1 fail closed): a file under the runs dir that is not
    YAML is unknown, never skipped, so the delivered cursor beside it does not deliver."""
    files = {"r1.yaml": _doc("r1", "deliver", deliver="done"), "r2.yaml": "run: [unclosed"}
    got = read_cursor(FakeCheckout(files), _pr())  # type: ignore[arg-type]
    assert (got.position, got.read) == (None, "unread")
    assert got.detail.startswith(f"{RUNS_DIR}/r2.yaml at {HEAD[:12]} is not YAML: ")


def test_a_lone_corrupt_cursor_is_unread_never_no_cursor() -> None:
    """A lone corrupt file is not "no cursor names the branch" (which would advise R12's
    merge by hand): it is a read that failed."""
    got = read_cursor(FakeCheckout({"r1.yaml": "{{"}), _pr())  # type: ignore[arg-type]
    assert got.read == "unread" and "r1.yaml" in got.detail


@pytest.mark.parametrize(
    ("doc", "why"),
    [
        ({"branch": BRANCH}, "names no run"),
        ({"branch": BRANCH, "run": "r1"}, "names no cursor step"),
        ({"branch": BRANCH, "run": "r1", "cursor": "deliver", "steps": ["x"]},
         "steps is not a mapping"),
        ({"branch": BRANCH, "run": "r1", "cursor": "deliver", "steps": {"deliver": "done"}},
         "step deliver is not a mapping"),
        (["not", "a", "mapping"], "is not a mapping"),
        ({"run": "r1", "cursor": "deliver"}, "names no branch"),
    ],
)  # fmt: skip
def test_a_cursor_not_shaped_like_a_run_is_unread(doc: Any, why: str) -> None:
    """Mirrors `fr.isolation.preserve.branch_runs`: a file that is no run (no mapping, no
    branch) or names this branch with no usable run, cursor or steps is unreadable."""
    files = {"r1.yaml": _doc("r1", "deliver", deliver="done"), "r2.yaml": doc}
    got = read_cursor(FakeCheckout(files), _pr())  # type: ignore[arg-type]
    assert (got.position, got.read) == (None, "unread")
    assert got.detail == f"{RUNS_DIR}/r2.yaml at {HEAD[:12]} {why}"


# ------------------------------------------------------------------ collect

AT = datetime(2026, 9, 25, 0, 0, tzinfo=UTC)


def _open_pr() -> dict[str, Any]:
    return {"number": 41, "title": "PR", "state": "OPEN", "isDraft": True,
            "createdAt": "2026-09-25T06:00:00Z", "mergedAt": None,
            "url": f"https://github.com/{REPO}/pull/41", "headRefName": BRANCH,
            "headRefOid": HEAD, "closingIssuesReferences": [],
            "author": {"login": "operator"}, "isCrossRepository": False}  # fmt: skip


def _collect(answer: CursorAnswer) -> PullRequest:
    forge = FakeForge(issues={REPO: []}, prs={REPO: []}, head_prs={(REPO, BRANCH): [_open_pr()]})
    facts = collect_facts(
        forge, Scope(kind="repo", target=REPO), now=NOW,
        batch_branches=[("alpha", BRANCH, AT)], ledger_branches=[("alpha", BRANCH, AT)],
        cursor_at=lambda pr: answer,
    )  # fmt: skip
    (pr,) = facts.batch_prs
    return pr


def test_collect_stores_the_fold_its_read_status_and_its_cause() -> None:
    pr = _collect(CursorAnswer(DONE, "read"))
    assert (pr.cursor, pr.cursor_read, pr.cursor_detail) == (DONE, "read", None)
    pr = _collect(CursorAnswer(None, "unread", "fetch of x failed: boom"))
    assert (pr.cursor, pr.cursor_read, pr.cursor_detail) == (
        None,
        "unread",
        "fetch of x failed: boom",
    )
    pr = _collect(CursorAnswer(None, "no-clone"))
    assert (pr.cursor, pr.cursor_read, pr.cursor_detail) == (None, "no-clone", None)


def test_cursor_read_arrived_at_19_and_facts_still_read_3_to_18(tmp_path: Path) -> None:
    # The one pin of the stamp is test_triage_model.py (gh#1300); a later field may move it.
    assert FACTS_SCHEMA >= 19 and 19 in FACTS_READS
    assert set(range(3, 19)) <= set(FACTS_READS)
    old = {"schema": 18, "scope": REPO, "kind": "repo", "collected_at": "2026-09-25T06:00:00Z",
           "repos": [REPO], "issues": []}  # fmt: skip
    (tmp_path / "facts.json").write_text(json.dumps(old))
    assert load_facts(tmp_path / "facts.json").schema_ == 18
    pr = _pr()
    assert pr.cursor_read is None  # never asked


def _driver(tmp_path: Path) -> Any:
    from fr.commands import triage_batch_cmd

    return triage_batch_cmd._Driver(
        triage_batch_cmd._scope(REPO, None), tmp_path, named=None, checkouts={},
        max_inflight=4, yes=False,
    )  # fmt: skip


def test_the_drivers_reader_says_no_clone_and_caches_by_head(tmp_path: Path) -> None:
    driver = _driver(tmp_path)
    assert driver.cursor_at(_pr()) == (None, "no-clone", f"no clone of {REPO}")
    driver.checkout_paths = {REPO: tmp_path}
    calls: list[str] = []
    files = {"r1.yaml": _doc("r1", "deliver", deliver="done")}
    driver._reader = lambda repo: calls.append(repo) or FakeCheckout(files)  # type: ignore[method-assign]
    assert driver.cursor_at(_pr()) == (DONE, "read", "")
    assert driver.cursor_at(_pr()) == (DONE, "read", "")
    assert calls == [REPO]


def test_the_drivers_reader_never_caches_an_unread_head_and_says_its_cause_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """l-tests-r2 / l-errors-r2: an `unread` result is read again on the next call (a fetch
    that failed may succeed), and its cause is reported once per head, not once per pass."""
    driver = _driver(tmp_path)
    driver.checkout_paths = {REPO: tmp_path}
    calls: list[str] = []
    answers = [FakeCheckout({}, reach=False), FakeCheckout({}, reach=False),
               FakeCheckout({"r1.yaml": _doc("r1", "deliver", deliver="done")})]  # fmt: skip
    driver._reader = lambda repo: calls.append(repo) or answers[len(calls) - 1]  # type: ignore[method-assign]
    first = driver.cursor_at(_pr())
    assert first.read == "unread" and "network down" in first.detail
    assert driver.cursor_at(_pr()).read == "unread"
    assert driver.cursor_at(_pr()) == (DONE, "read", "")
    assert calls == [REPO, REPO, REPO]
    err = capsys.readouterr().err
    assert err.count("network down") == 1 and f"{REPO}#41" in err


def test_the_drivers_reader_carries_a_failed_clone_open(tmp_path: Path) -> None:
    """A clone that cannot be opened is unread with the error, never a bare `unread`."""
    driver = _driver(tmp_path)
    driver.checkout_paths = {REPO: tmp_path}

    def boom(repo: str) -> Any:
        raise TriageError("not a git repository")

    driver._reader = boom  # type: ignore[method-assign]
    got = driver.cursor_at(_pr())
    assert (
        got.read == "unread"
        and got.detail == f"the clone of {REPO} could not be read: not a git repository"
    )


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


def test_a_schema_18_facts_files_delivered_cursor_is_not_admitted(tmp_path: Path) -> None:
    """p1-r6, R1: a schema-18 facts file (the last before 19) carries a batch PR's `cursor`
    but no `cursor_read`; its deliver-done cursor was never asked at this head, so the
    queue does not admit it."""
    from fr.triage.batch import QueueEntry
    from fr.triage.readiness import batch_readiness, fact_cursors

    from tests.unit.test_triage_readiness import HEAD as R_HEAD
    from tests.unit.test_triage_readiness import B, _qs

    pr = {"repo": REPO, "number": 101, "title": "b1", "state": "OPEN", "is_draft": True,
          "url": f"https://github.com/{REPO}/pull/101", "head_ref": BRANCH, "head_oid": R_HEAD,
          "cursor": {"run": "r1", "step": "deliver", "kind": "deliver-done"}}  # fmt: skip
    old = {"schema": 18, "scope": REPO, "kind": "repo", "collected_at": "2026-09-25T06:00:00Z",
           "repos": [REPO], "issues": [], "batch_prs": [pr]}  # fmt: skip
    (tmp_path / "facts.json").write_text(json.dumps(old))
    facts = load_facts(tmp_path / "facts.json")
    (loaded,) = facts.batch_prs
    assert loaded.cursor == DONE and loaded.cursor_read is None
    cursors = fact_cursors([QueueEntry(batch=B, pr=loaded)])
    got = batch_readiness(B, _qs(B, cursor=cursors["b1"]))
    assert not got.admits
    assert got.kind == "approved-not-delivered" and got.reason == "the run cursor was not read"
