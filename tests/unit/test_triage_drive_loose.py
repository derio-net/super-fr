"""The wave driver passes a walked gate on a merged PR outside every batch (spec
2026-11-28-tester-gate-auto-pass R4, R6, R7): the whole-scope drive reads its rows through
the run cursor that delivered it and writes what a batch's gate pass writes."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.commands import triage_batch_cmd, triage_drive_loose
from fr.hostclient import FORGE_ERRORS
from fr.triage.batch_drive_types import GatedRow
from fr.triage.errors import TriageError
from fr.triage.ledger import LedgerRead
from fr.triage.model import Facts, PullRequest

from tests.unit.test_triage_batch_drive import NOW
from tests.unit.test_triage_batch_drive_cmd import (
    REPO,
    _batch,
    _dispatch_event,
    _drive,
    _lines,
    _state,
)
from tests.unit.test_triage_exit_gates_drive import (  # noqa: F401 - the gworld fixture
    ISSUE,
    GatedWorld,
    gworld_fixture,
)

LOOSE = 55
BRANCH = "feat/solo"


class LooseWorld(GatedWorld):
    """Every merged PR holding a gate label is also in `facts.gated_prs`, as collect lists it."""

    def facts(self) -> Facts:
        facts = super().facts()
        gated = [
            PullRequest(
                repo=REPO,
                number=n,
                title=p["head_ref"],
                state="MERGED",
                is_draft=False,
                merged_at=p["merged_at"],
                head_ref=p["head_ref"],
                url=f"https://github.com/{REPO}/pull/{n}",
                labels=list(p["labels"]),
            )
            for n, p in self.prs.items()
            if p["state"] == "MERGED" and not p["closes"]
        ]
        return facts.model_copy(update={"gated_prs": gated})


@pytest.fixture(name="lworld")
def lworld_fixture(gworld: GatedWorld, monkeypatch: pytest.MonkeyPatch) -> GatedWorld:
    gworld.__class__ = LooseWorld  # the fixture already wired this very object in
    return gworld


def _loose(
    world: GatedWorld,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rows: tuple[GatedRow, ...] | Exception,
    *,
    batch: bool = False,
) -> list[Any]:
    """A merged gated PR no batch delivered (and, with *batch*, an unrelated one in flight)."""
    world.issues[7] = "open"
    world.issues[9] = "open"
    world.pr(LOOSE, BRANCH, [], state="MERGED", labels=["gate:tester"],
             merged_at=(NOW - timedelta(hours=1)).isoformat())  # fmt: skip
    _state(tmp_path, world, *([_batch("b9", 9, events=_dispatch_event("b9"))] if batch else []))
    seen: list[Any] = []

    def _rows(
        checkout: Any, ref: str, branch: str, *, pr: int | None = None, **_: Any
    ) -> LedgerRead:
        seen.append((ref, branch, pr))
        if isinstance(rows, Exception):
            raise rows
        return LedgerRead(rows, run_gate="none", run_gate_inherited=False)

    monkeypatch.setattr(triage_drive_loose, "gated_rows_at", _rows)
    monkeypatch.setattr(triage_drive_loose, "read_cursors", lambda checkout, ref: [])
    return seen


WALKED = (GatedRow("row-a", "tester", True, (ISSUE,)),)


def test_a_whole_scope_drive_passes_a_loose_prs_walked_gate(
    tmp_path: Path, lworld: GatedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _loose(lworld, tmp_path, monkeypatch, WALKED)

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    assert seen == [("origin/main", BRANCH, LOOSE)]
    assert f"pr labels {LOOSE} +['gate:tester-passed'] -['gate:tester']" in lworld.calls
    (comment,) = [c for c in lworld.calls if c.startswith(f"pr comment {LOOSE}")]
    assert "row-a" in comment
    assert "issue labels 7 +['fr:awaiting-live']" in lworld.calls
    assert lworld.prs[LOOSE]["labels"] == ["gate:tester-passed"]


def test_a_drive_narrowed_with_batch_writes_nothing_for_a_loose_pr(
    tmp_path: Path, lworld: GatedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _loose(lworld, tmp_path, monkeypatch, WALKED, batch=True)

    _drive(tmp_path, "b9", "--once", "--yes")

    assert seen == []
    assert not [c for c in lworld.calls if c.startswith(("pr labels", "pr comment"))]


def test_rows_unreadable_for_a_loose_pr_are_reported_once_and_plan_nothing(
    tmp_path: Path, lworld: GatedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    _loose(lworld, tmp_path, monkeypatch, TriageError("more than one run cursor"))

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    assert out.count(f"PR #{LOOSE}") == 1 and "more than one run cursor" in out
    assert not [c for c in lworld.calls if c.startswith(("pr labels", "pr comment"))]


def test_the_same_unreadable_read_is_not_reported_again_on_a_later_pass(
    tmp_path: Path, lworld: GatedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    _loose(lworld, tmp_path, monkeypatch, TriageError("more than one run cursor"), batch=True)
    sleeps: list[float] = []

    def _sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise RuntimeError("stop after the third pass")

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _sleep)
    code, out = _drive(tmp_path, "--yes", "--interval", "5")

    assert len(sleeps) >= 2, out  # at least two passes ran
    assert out.count(f"PR #{LOOSE}") == 1, out


def test_a_failed_label_write_for_a_loose_pr_is_reported_and_exits_one(
    tmp_path: Path, lworld: GatedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    _loose(lworld, tmp_path, monkeypatch, WALKED)

    def _refuse(*a: Any, **k: Any) -> None:
        raise FORGE_ERRORS[0]("HTTP 502")

    monkeypatch.setattr(lworld, "edit_pr_labels", _refuse)

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 1, out
    assert "gate pass failed, retried next pass" in out
    assert _lines(out, "gate-pass")


def test_a_cursor_naming_another_pr_means_no_rows_and_nothing_is_written(
    tmp_path: Path, lworld: GatedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage.ledger import NO_RUN

    _loose(lworld, tmp_path, monkeypatch, WALKED)
    monkeypatch.setattr(triage_drive_loose, "gated_rows_at", lambda *a, **k: NO_RUN)

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    assert not [c for c in lworld.calls if c.startswith(("pr labels", "pr comment", "issue"))]


def test_a_failed_gate_pass_for_a_loose_pr_is_planned_again_on_the_next_pass(
    tmp_path: Path, lworld: GatedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    _loose(lworld, tmp_path, monkeypatch, WALKED, batch=True)  # b9 keeps the loop going

    def _refuse(*a: Any, **k: Any) -> None:
        raise FORGE_ERRORS[0]("HTTP 502")

    monkeypatch.setattr(lworld, "edit_pr_labels", _refuse)
    sleeps: list[float] = []

    def _sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise RuntimeError("stop after the second pass")

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _sleep)
    _code, out = _drive(tmp_path, "--yes", "--interval", "5")

    assert len(sleeps) == 2, out  # two passes ran
    assert out.count("gate pass failed, retried next pass") == 2, out


def test_two_loose_prs_of_one_repo_read_its_cursors_once_per_pass(
    tmp_path: Path, lworld: GatedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = _loose(lworld, tmp_path, monkeypatch, WALKED)
    lworld.pr(LOOSE + 1, "feat/solo-2", [], state="MERGED", labels=["gate:tester"],
              merged_at=(NOW - timedelta(hours=1)).isoformat())  # fmt: skip
    reads: list[str] = []
    monkeypatch.setattr(
        triage_drive_loose, "read_cursors", lambda checkout, ref: reads.append(ref) or []
    )

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    assert sorted(p for _, _, p in seen) == [LOOSE, LOOSE + 1]
    assert reads == ["origin/main"]


class _NoCloneWorld(LooseWorld):
    """A gated PR in a repo the driver has no clone of, beside the clone's own."""

    def facts(self) -> Facts:
        facts = super().facts()
        other = facts.gated_prs[0].model_copy(update={"repo": "acme/other", "number": 77})
        return facts.model_copy(update={"gated_prs": [*facts.gated_prs, other]})


def test_a_loose_pr_in_a_repo_with_no_clone_is_reported_and_the_pass_goes_on(
    tmp_path: Path, lworld: GatedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    _loose(lworld, tmp_path, monkeypatch, WALKED)
    lworld.__class__ = _NoCloneWorld

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    assert out.count("PR #77") == 1 and "no clone of acme/other" in out, out
    assert f"pr labels {LOOSE} +['gate:tester-passed'] -['gate:tester']" in lworld.calls


# ----------------------------------------- loose_ledgers over a real default branch (R5)


class _Driver:
    """The driver surface `loose_ledgers` reads, over a real clone."""

    named = False

    def __init__(self, checkout: Any) -> None:
        self.checkout_ = checkout
        self.reported: list[str] = []

    def path_of(self, repo: str) -> Path:
        return self.checkout_.path

    def _fetched_reader(self, repo: str) -> Any:
        return self.checkout_

    def _report_once(self, key: str, message: str) -> bool:
        self.reported.append(message)
        return True


def _real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **cursor: Any) -> Any:
    from fr.triage.batch_drive_types import GateLedger, LooseLedger

    from tests.unit.test_triage_exit_gates_drive import _ledger_repo
    from tests.unit.test_triage_pr_gates import _cursor_pr

    monkeypatch.setattr(triage_batch_cmd, "_checkout_refusal", lambda path, repo: None)
    checkout = _ledger_repo(tmp_path, walked=True)
    _cursor_pr(checkout, **cursor)
    loose = LooseLedger(
        REPO, 9, "feat/batch-b1", GateLedger(pr=9, labels=frozenset({"gate:tester"}))
    )
    monkeypatch.setattr(triage_drive_loose.pr_gates, "loose_prs", lambda facts, batches: [loose])
    driver = _Driver(checkout)
    got = triage_drive_loose.loose_ledgers(driver, None, _Judgements(), ())  # type: ignore[arg-type]
    (only,) = got
    return only.ledger.rows, driver.reported


class _Judgements:
    batches: list[Any] = []


def test_loose_ledgers_reads_the_rows_of_the_cursor_naming_this_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows, reported = _real(tmp_path, monkeypatch, pr=f"https://github.com/{REPO}/pull/9")
    assert [r.id for r in rows] == ["r-live"] and reported == []


def test_loose_ledgers_reads_no_rows_when_the_cursor_names_another_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows, reported = _real(tmp_path, monkeypatch, pr=f"https://github.com/{REPO}/pull/19")
    assert rows == () and reported == []


def test_loose_ledgers_reports_two_runs_naming_the_branch_and_reads_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows, reported = _real(tmp_path, monkeypatch, pr=None, extra="r2")
    assert rows is None
    assert len(reported) == 1 and "more than one run cursor" in reported[0]
