"""`fr triage batch closeout [<id>...] [--yes]` (spec 2026-10-14-exit-gates R15, §E).

The verb over the drive tests' in-memory forge (`World`) and clone (`DriveCheckout`):
the default branch's read (`closeout_read`) and the scratch worktree are faked, so no
git, `fr` process or network is reached.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.triage.ledger import CloseoutRead
from fr.triage.model import load_judgements
from typer.testing import CliRunner

from tests.unit.test_triage_batch_closeout import FakeTree
from tests.unit.test_triage_batch_drive_cmd import (
    NOW,
    REPO,
    DriveCheckout,
    World,
    _batch,
    _dispatch_event,
    _sandbox,  # noqa: F401 - the drive tests' autouse sandbox
    _state,
    checkout_fixture,  # noqa: F401 - registered as `checkout`
    world_fixture,  # noqa: F401 - registered as `world`
)

BRANCH = "chore/closeout-2026-10-02-1"


@pytest.fixture(name="tree")
def tree_fixture(monkeypatch: pytest.MonkeyPatch, checkout: DriveCheckout) -> FakeTree:
    tree = FakeTree()
    monkeypatch.setattr(checkout, "add_worktree", lambda where, ref: tree, raising=False)
    tree.start_branch = lambda branch: None  # type: ignore[attr-defined]
    return tree


def _reads(monkeypatch: pytest.MonkeyPatch, by_branch: dict[str, CloseoutRead]) -> None:
    monkeypatch.setattr(
        triage_batch_cmd, "closeout_read",
        lambda checkout, ref, branch, repo: by_branch.get(branch, CloseoutRead(f"r-{branch}")),
    )  # fmt: skip


def _landed(world: World, tmp_path: Path, *bids: str) -> Path:
    batches = []
    for i, bid in enumerate(bids, 1):
        world.issues[i] = "closed"
        world.pr(100 + i, f"feat/batch-{bid}", [i], state="MERGED",
                 merged_at=(NOW - timedelta(hours=1)).isoformat())  # fmt: skip
        batches.append(_batch(bid, i, events=_dispatch_event(bid)))
    return _state(tmp_path, world, *batches)


def _label_merged(target: Path, number: int, labels: list[str]) -> None:
    """The merged PR's labels as a collect reads them (the gate ledger, R14)."""
    path = target / "facts.json"
    raw = json.loads(path.read_text("utf-8"))
    for issue in raw["issues"]:
        for pr in issue["prs"]:
            if pr["number"] == number:
                pr["labels"] = labels
    path.write_text(json.dumps(raw), "utf-8")


def _closeout(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", "closeout", *args, "--repo", REPO, "--dir", str(tmp_path)]
    )
    return result.exit_code, result.output


def _closeouts(tmp_path: Path) -> dict[str, list[Any]]:
    batches = load_judgements(tmp_path / "judgements.yaml").batches
    return {b.id: [e for e in b.events if e.kind == "closeout"] for b in batches}


def test_without_yes_the_verb_prints_every_batchs_steps_and_writes_nothing(
    tmp_path: Path, world: World, checkout: DriveCheckout, tree: FakeTree,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _reads(monkeypatch, {})
    _landed(world, tmp_path, "b1", "b2")

    code, out = _closeout(tmp_path)

    assert code == 0, out
    assert BRANCH in out
    assert "b1: fr archive --branch feat/batch-b1 --no-issues" in out
    assert "b2: fr archive --branch feat/batch-b2 --no-issues" in out
    assert tree.calls == [] and _closeouts(tmp_path) == {"b1": [], "b2": []}


def test_with_yes_one_pr_closes_out_every_batch_on_the_shared_branch(
    tmp_path: Path, world: World, checkout: DriveCheckout, tree: FakeTree,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _reads(monkeypatch, {"feat/batch-b2": CloseoutRead(None)})  # b2: a debug batch, no run
    _landed(world, tmp_path, "b1", "b2")

    code, out = _closeout(tmp_path, "--yes")

    assert code == 0, out
    assert [c for c in world.calls if c.startswith("pr_create")] == [f"pr_create {BRANCH} -> main"]
    events = _closeouts(tmp_path)
    assert [e.archive for e in events["b1"]] == [BRANCH] and events["b1"][
        0
    ].run == "r-feat/batch-b1"
    assert [e.archive for e in events["b2"]] == [BRANCH] and events["b2"][0].run is None


def test_a_held_batch_is_named_gets_no_event_and_the_verb_exits_1(
    tmp_path: Path, world: World, checkout: DriveCheckout, tree: FakeTree,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _reads(monkeypatch, {})
    tree.codes[("archive", "feat/batch-b2")] = 2
    _landed(world, tmp_path, "b1", "b2")

    code, out = _closeout(tmp_path, "--yes")

    assert code == 1
    assert "b2: held" in out
    assert [len(v) for v in _closeouts(tmp_path).values()] == [1, 0]


def test_a_gated_batch_is_not_closed_out(
    tmp_path: Path, world: World, checkout: DriveCheckout, tree: FakeTree,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _reads(monkeypatch, {})
    _label_merged(_landed(world, tmp_path, "b1", "b2"), 102, ["gate:tester"])

    code, out = _closeout(tmp_path)

    assert code == 0, out
    assert "b1: fr archive" in out and "b2: fr" not in out


def test_naming_a_batch_that_is_not_owed_a_closeout_is_refused(
    tmp_path: Path, world: World, checkout: DriveCheckout, tree: FakeTree,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _reads(monkeypatch, {})
    _landed(world, tmp_path, "b1")
    code, out = _closeout(tmp_path, "nope")
    assert code == 2 and "nope" in out


def test_a_passed_gate_records_outcomes_and_its_pr_closes_its_rows_issues_not_a_narrowed_one(
    tmp_path: Path, world: World, checkout: DriveCheckout, tree: FakeTree,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    from fr.triage.batch_closeout import closes_from_body
    from fr.triage.batch_drive import GatedRow

    rows = (GatedRow("r", "tester", True, (f"{REPO}#7", f"{REPO}#8")),)
    _reads(monkeypatch, {"feat/batch-b1": CloseoutRead("r1", (1,), rows, (f"{REPO}#8",))})
    _label_merged(_landed(world, tmp_path, "b1"), 101, ["gate:tester-passed"])
    world.comments[101] = [{"body": "<!-- fr:gate-pass tester -->\npassed", "id": 55}]

    code, out = _closeout(tmp_path, "--yes")

    assert code == 0, out
    outcome = next(c for c in tree.calls if c[0] == "closeout")
    assert outcome[-1] == f"https://github.com/{REPO}/pull/101#issuecomment-55"
    (pr,) = [p for p in world.prs.values() if p["head_ref"] == BRANCH]
    assert closes_from_body(pr["body"]) == (f"{REPO}#7",)  # p6-r8: closed by the merge


def _holds(tmp_path: Path) -> dict[str, list[Any]]:
    batches = load_judgements(tmp_path / "judgements.yaml").batches
    return {b.id: [(e.item, e.reason) for e in b.events if e.kind == "closeout_hold"]  # type: ignore[union-attr]
            for b in batches}  # fmt: skip


def test_p6_r2_a_held_batch_gets_a_durable_hold_and_the_pr_carries_only_the_rest(
    tmp_path: Path, world: World, checkout: DriveCheckout, tree: FakeTree,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _reads(monkeypatch, {})
    tree.codes[("archive", "feat/batch-b2")] = 2
    _landed(world, tmp_path, "b1", "b2")

    code, _ = _closeout(tmp_path, "--yes")

    assert code == 1
    item = f"{REPO}/run/closeout-2026-10-02-1"
    holds = _holds(tmp_path)
    assert holds["b1"] == [] and [i for i, _ in holds["b2"]] == [item]
    judgements = load_judgements(tmp_path / "judgements.yaml")
    (marker,) = judgements.closeouts
    assert (marker.branch, marker.item, marker.pr) == (BRANCH, item, 200)
    # the driver never re-collects b2; naming it retries it
    code, out = _closeout(tmp_path)
    assert "nothing to close out" in out
    code, out = _closeout(tmp_path, "b2")
    assert code == 0 and "b2: fr archive" in out


def test_p6_r4_an_unreadable_batch_is_held_with_its_reason_and_the_rest_close_out(
    tmp_path: Path, world: World, checkout: DriveCheckout, tree: FakeTree,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    from fr.triage.errors import TriageError

    def _read(checkout: Any, ref: str, branch: str, repo: str) -> CloseoutRead:
        if branch == "feat/batch-b2":
            raise TriageError("the exit of run r2 cannot be read")
        return CloseoutRead("r1")

    monkeypatch.setattr(triage_batch_cmd, "closeout_read", _read)
    _landed(world, tmp_path, "b1", "b2")

    code, out = _closeout(tmp_path, "--yes")

    assert code == 1, out
    assert [len(v) for v in _closeouts(tmp_path).values()] == [1, 0]
    ((_, reason),) = _holds(tmp_path)["b2"]
    assert "cannot be read" in reason and "run r2" in reason


def test_p6_r9_a_rerun_on_a_branch_with_its_pr_resumes_and_another_pr_is_refused(
    tmp_path: Path, world: World, checkout: DriveCheckout, tree: FakeTree,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _reads(monkeypatch, {})
    _landed(world, tmp_path, "b1", "b2")
    world.pr(300, BRANCH, [], body="<!-- fr:closeout-members b1 -->")  # pushed, then a crash

    code, out = _closeout(tmp_path, "--yes")

    assert code == 0, out
    assert "resumed PR #300" in out and tree.calls == []  # nothing re-run, nothing re-pushed
    assert [len(v) for v in _closeouts(tmp_path).values()] == [1, 0]

    world.prs[300]["body"] = "<!-- fr:closeout-members zz -->"
    code, out = _closeout(tmp_path, "b2", "--yes", "--branch", BRANCH)
    assert code == 2 and f"{BRANCH} already has PR #300" in " ".join(out.split())
