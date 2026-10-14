"""The driver's gate routing (spec 2026-10-14-exit-gates R13, R14, §D `drive_pass` step 2).

A landed batch whose merged PR carries an unpassed `gate:tester` / `gate:devops` label
is gated: the driver never closes it out. The first pass that sees it labels the issues
its gated rows cite `fr:awaiting-live`, and once every row a gate gates reads `walked`
in the default branch's matrix it plans the gate pass (label swap + comment). The pass
is pure (`drive_pass` over a hand-built `Snapshot`); the executor's forge writes are
pinned against the in-memory forge of `test_triage_batch_drive_cmd`.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.commands import triage_batch_cmd
from fr.labels import held_gates
from fr.triage.batch_drive import (
    GatedRow,
    GateLedger,
    action_line,
    drive_pass,
    is_gated,
    summary_line,
)
from fr.triage.views import drive_snapshot

from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive import NOW, _dispatched, _kinds, _snap
from tests.unit.test_triage_batch_drive_cmd import (
    REPO,
    DriveCheckout,
    World,
    _batch,
    _dispatch_event,
    _drive,
    _lines,
    _state,
)

ISSUE = f"{REPO}#7"
DUE = {"merged_at": {"b1": NOW - timedelta(hours=1)}}  # past the close-out fallback


def _ledger(*labels: str, rows: tuple[GatedRow, ...] | None = None) -> dict[str, GateLedger]:
    return {"b1": GateLedger(pr=101, labels=frozenset(labels), rows=rows)}


def _landed(**kw: Any) -> Any:
    b1 = _dispatched("b1", 7)
    return _snap([b1], {"b1": "merged"}, **DUE, **kw)


# ----------------------------------------------------------------- the predicate


def test_held_gates_are_the_unpassed_post_merge_gates() -> None:
    assert held_gates({"gate:tester", "gate:devops-passed", "gate:devops"}) == {"tester"}
    assert held_gates({"gate:tester", "gate:tester-passed"}) == frozenset()
    assert held_gates({"gate:owner", "verification:live"}) == frozenset()  # not post-merge


def test_is_gated_reads_the_ledger_of_a_landed_batch_only() -> None:
    snap = _landed(ledgers=_ledger("gate:tester"))
    assert is_gated(snap.batches[0], snap)
    assert not is_gated(snap.batches[0], _landed(ledgers=_ledger("gate:tester-passed")))
    assert not is_gated(snap.batches[0], _landed())  # labels never read: no evidence


# ------------------------------------------------------------------ step 2 (R13)


def test_a_gated_landed_batch_is_never_closed_out() -> None:
    plan = drive_pass(_landed(ledgers=_ledger("gate:tester")))

    assert "closeout" not in [k for k, _ in _kinds(plan.actions)]
    assert plan.summary.gated == 1 and plan.summary.closing == 0
    assert plan.summary.done  # a gate waits on a person: it never keeps a drive alive
    assert summary_line(plan.summary).endswith("gated 1")


def test_a_passed_gate_closes_out_normally() -> None:
    plan = drive_pass(_landed(ledgers=_ledger("gate:tester", "gate:tester-passed")))
    assert ("closeout", "b1") in _kinds(plan.actions)
    assert plan.summary.gated == 0


def test_the_first_gated_pass_labels_the_issues_its_gated_rows_cite() -> None:
    rows = (GatedRow("row-a", "tester", walked=False, issues=(ISSUE, f"{REPO}#8")),)
    plan = drive_pass(
        _landed(ledgers=_ledger("gate:tester", rows=rows), awaiting_unlabelled=frozenset({ISSUE}))
    )

    awaiting = [a for a in plan.actions if a.kind == "awaiting-live"]
    assert [(a.batch, a.key, a.pr) for a in awaiting] == [("b1", ISSUE, 101)]  # #8 has it
    assert action_line(awaiting[0]).startswith(f"awaiting-live b1: label {ISSUE}")


def test_every_gated_row_walked_plans_the_gate_pass() -> None:
    rows = (
        GatedRow("row-a", "tester", walked=True, issues=(ISSUE,)),
        GatedRow("row-b", "tester", walked=True),
        GatedRow("row-c", "devops", walked=False),
    )
    plan = drive_pass(_landed(ledgers=_ledger("gate:tester", "gate:devops", rows=rows)))

    (passing,) = [a for a in plan.actions if a.kind == "gate-pass"]
    assert (passing.batch, passing.gate, passing.pr) == ("b1", "tester", 101)
    assert "row-a, row-b" in passing.detail
    assert "closeout" not in [k for k, _ in _kinds(plan.actions)]  # devops still holds


def test_a_gate_with_no_row_passes_only_explicitly() -> None:
    """R14: a run-level `gate: devops` has no row to walk: `fr gate pass` is its route."""
    plan = drive_pass(_landed(ledgers=_ledger("gate:devops", rows=())))
    assert [a for a in plan.actions if a.kind == "gate-pass"] == []


def test_unread_rows_plan_no_label_and_no_pass() -> None:
    plan = drive_pass(
        _landed(ledgers=_ledger("gate:tester"), awaiting_unlabelled=frozenset({ISSUE}))
    )
    assert [a for a in plan.actions if a.kind in ("awaiting-live", "gate-pass")] == []


# ---------------------------------------------------------- the board shares it


def test_the_boards_snapshot_reads_the_ledger_from_facts() -> None:
    """`views` builds its snapshot from facts alone; a merged PR's labels are there."""
    world = World()
    world.issues[7] = "open"
    world.pr(101, "feat/batch-b1", [7], state="MERGED", labels=["gate:tester"],
             merged_at=(NOW - timedelta(hours=1)).isoformat())  # fmt: skip
    facts = _ledger_facts(world)
    judgements = _judgements()

    snap = drive_snapshot(facts, judgements)

    assert snap.ledgers["b1"] == GateLedger(pr=101, labels=frozenset({"gate:tester"}))
    assert is_gated(next(b for b in snap.batches if b.id == "b1"), snap)


def _ledger_facts(world: World) -> Any:
    facts = world.facts()
    issues = [
        i.model_copy(update={"prs": [p.model_copy(update={"labels": world.prs[p.number]["labels"]})
                                     for p in i.prs]})
        for i in facts.issues
    ]  # fmt: skip
    return facts.model_copy(update={"issues": issues})


def _judgements() -> Any:
    from fr.triage.model import Judgements

    return Judgements.model_validate(
        {"schema": 3, "tiers": [{"n": 1, "title": "Now"}], "issues": {"super-fr#7": {"tier": 1}},
         "batches": [{"id": "b1", "title": "b1", "ids": ["super-fr#7"], "wave": 1,
                      "events": [{"kind": "dispatch", "at": "2026-10-01T10:00:00Z",
                                  "runner": "fake", "handle": "h",
                                  "branch": "feat/batch-b1"}]}]}
    )  # fmt: skip


# ------------------------------------------------------------- the executor


class GatedWorld(World):
    """The in-memory forge, with a merged PR's labels in facts and the two PR writes."""

    def _pr(self, n: int) -> Any:
        pr = super()._pr(n)
        return pr.model_copy(update={"labels": list(self.prs[n]["labels"])})

    def edit_pr_labels(
        self, repo: str, pr: int, *, add: frozenset[str], remove: frozenset[str]
    ) -> None:
        self.calls.append(f"pr labels {pr} +{sorted(add)} -{sorted(remove)}")
        kept = [x for x in self.prs[pr]["labels"] if x not in remove]
        self.prs[pr]["labels"] = kept + sorted(add - set(kept))

    def comment_pr(self, repo: str, pr: int, body: str) -> None:
        self.calls.append(f"pr comment {pr}: {body}")

    def edit_issue_labels(self, repo: str, number: int, **kw: Any) -> None:
        self.calls.append(f"issue labels {number} +{sorted(kw.get('add', ()))}")


@pytest.fixture(name="gworld")
def gworld_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> GatedWorld:
    import json

    w = GatedWorld()

    def _recollect(scope: Any, target: Path, **_: Any) -> None:
        (target / "facts.json").write_text(json.dumps(w.facts().to_json()), "utf-8")

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    monkeypatch.setattr(triage_batch_cmd, "ci_is_none", lambda path: False)
    monkeypatch.setattr(triage_batch_cmd, "recollect", _recollect)
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: w)
    fake = DriveCheckout(tmp_path / "clone", w)
    fake.path.mkdir()
    fake.released = True
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: fake)
    runner = FakeRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: runner)
    w.runner = runner  # type: ignore[attr-defined]
    return w


def _gated(world: GatedWorld, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
           rows: tuple[GatedRow, ...]) -> None:  # fmt: skip
    world.issues[7] = "open"
    world.pr(101, "feat/batch-b1", [7], state="MERGED", labels=["gate:tester"],
             merged_at=(NOW - timedelta(hours=1)).isoformat())  # fmt: skip
    _state(tmp_path, world, _batch("b1", 7, events=_dispatch_event("b1")))
    seen: list[tuple[str, str]] = []

    def _rows(checkout: Any, ref: str, branch: str) -> tuple[GatedRow, ...]:
        seen.append((ref, branch))
        return rows

    monkeypatch.setattr(triage_batch_cmd, "gated_rows_at", _rows)
    world.rows_read = seen  # type: ignore[attr-defined]


def test_without_yes_the_gate_actions_are_planned_and_nothing_is_written(
    tmp_path: Path, gworld: GatedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gated(gworld, tmp_path, monkeypatch, (GatedRow("row-a", "tester", True, (ISSUE,)),))

    code, out = _drive(tmp_path)

    assert code == 0, out
    assert _lines(out, "awaiting-live") == [f"awaiting-live b1: label {ISSUE} fr:awaiting-live"]
    assert _lines(out, "gate-pass")[0].startswith("gate-pass b1: PR #101")
    assert not [
        c for c in gworld.calls if c.startswith(("pr labels", "pr comment", "issue labels"))
    ]
    assert gworld.rows_read == [("origin/main", "feat/batch-b1")]  # type: ignore[attr-defined]
    assert _lines(out, "closeout") == []


def test_with_yes_the_driver_labels_the_issue_and_swaps_the_gate(
    tmp_path: Path, gworld: GatedWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    _gated(gworld, tmp_path, monkeypatch, (GatedRow("row-a", "tester", True, (ISSUE,)),))

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code == 0, out
    assert "issue labels 7 +['fr:awaiting-live']" in gworld.calls
    assert "pr labels 101 +['gate:tester-passed'] -['gate:tester']" in gworld.calls
    (comment,) = [c for c in gworld.calls if c.startswith("pr comment 101")]
    assert "tester" in comment and "row-a" in comment
    assert gworld.prs[101]["labels"] == ["gate:tester-passed"]
    assert gworld.runner.dispatched == []  # type: ignore[attr-defined]  # no close-out yet


# ------------------------------------------- the default branch's rows (gitseam)


def _git(cwd: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _ledger_repo(tmp_path: Path, *, walked: bool) -> Any:
    """A clone whose `origin/main` holds a run on feat/batch-b1, its spec and the matrix."""
    from fr.run.model import RunState, StepRecord, dump_run_state, run_path
    from fr.triage.gitseam import Checkout

    from tests.unit.requirements_support import row, write_matrix

    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
    clone = tmp_path / "clone"
    _git(tmp_path, "clone", "--quiet", str(origin), str(clone))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(clone, "config", k, v)
    spec = "docs/superpowers/specs/s.md"
    (clone / spec).parent.mkdir(parents=True)
    (clone / spec).write_text(
        "# Spec\n\n## Requirements\n\nR1. x\n\n## Verification\n\nstrategy: candidate\n"
        "- r-live: live — needs the merged build\n"
    )
    live = {**row(spec, rid="r-live"), "issues": [ISSUE],
            "status": "walked" if walked else "walk-owed"}  # fmt: skip
    if walked:
        live["walks"] = [{"strategy": "live", "harness": "claude-code", "model": "m",
                          "outcome": "pass", "at": "2026-10-02", "evidence": "log"}]  # fmt: skip
    write_matrix(clone, [live, row(spec, rid="r-other")])
    brainstorm = StepRecord(state="done", emitted={"spec": spec})
    state = RunState(run="r1", workflow="fr-goal@1", branch="feat/batch-b1",
                     started="2026-10-01T00:00:00Z", cursor="deliver",
                     steps={"brainstorm": brainstorm})  # fmt: skip
    path = run_path(clone, "r1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_run_state(state))
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "merged")
    _git(clone, "push", "--quiet", "origin", "HEAD:main")
    _git(clone, "fetch", "--quiet", "origin")
    # The working tree moves on: the read is the default branch's, never the checkout's.
    (clone / "docs/acceptance/matrix.yaml").write_text("not: a matrix\n")
    return Checkout(clone)


@pytest.mark.parametrize("walked", [False, True])
def test_the_gated_rows_are_read_on_the_default_branch_through_gitseam(
    tmp_path: Path, walked: bool
) -> None:
    from fr.triage.ledger import gated_rows_at

    checkout = _ledger_repo(tmp_path, walked=walked)

    rows = gated_rows_at(checkout, "origin/main", "feat/batch-b1")

    assert rows == (GatedRow("r-live", "tester", walked=walked, issues=(ISSUE,)),)
    assert _git(checkout.path, "worktree", "list").count("\n") == 0  # the scratch tree is gone


def test_a_branch_no_run_names_has_no_gated_row(tmp_path: Path) -> None:
    from fr.triage.ledger import gated_rows_at

    assert gated_rows_at(_ledger_repo(tmp_path, walked=False), "origin/main", "fix/x") == ()


def test_the_board_owes_no_post_merge_for_a_gated_batch() -> None:
    """A gated batch is never closed out, so its post_merge is not owed yet (R13): the
    board's needs read the same `is_gated` the driver's step 2 does."""
    from fr.triage.views import needs_you

    world = World()
    world.config = {"post_merge": ["./scripts/install.sh"]}
    world.issues[7] = "open"
    world.pr(101, "feat/batch-b1", [7], state="MERGED", labels=["gate:tester"],
             merged_at=(NOW - timedelta(hours=1)).isoformat())  # fmt: skip
    gated = [n for n in needs_you(_ledger_facts(world), _judgements()) if n.kind == "post-merge"]
    world.prs[101]["labels"] = ["gate:tester-passed"]
    passed = [n for n in needs_you(_ledger_facts(world), _judgements()) if n.kind == "post-merge"]

    assert gated == [] and [n.ref for n in passed] == ["b1"]
