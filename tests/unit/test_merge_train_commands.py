"""`fr triage batch merge` under the approval gate (spec 2026-10-11-merge-train-safety
§A "Recording and voiding", R1, R2, R4; 2026-11-19-wave-merge-queue R12, R23).

The approval is the queue's entry rule: `batch merge` settles it exactly as the driver's pass
does (it is that pass, in the foreground), and only an approved PR is an entry. The drive
tests' `World` is the forge and a `RecordingQueue` stands in for the queue's executor.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.triage.model import JUDGEMENTS_SCHEMA, load_judgements

from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    World,
    _sandbox,
    runner_fixture,
    world_fixture,
)
from tests.unit.test_triage_batch_merge import (  # noqa: F401 - fixtures
    _land_on_the_second_nap,
    _merge,
    _ready,
    clone_fixture,
)


def _events(tmp_path: Path, bid: str) -> list[dict[str, object]]:
    raw = yaml.safe_load((tmp_path / "judgements.yaml").read_text("utf-8"))
    batch = next(b for b in raw["batches"] if b["id"] == bid)
    return [e for e in batch["events"] if e["kind"] != "dispatch"]


def test_a_default_merge_holds_an_unlabelled_batch_and_queues_the_rest(
    tmp_path: Path, world: World, clone: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ready(world, tmp_path, 1, 2)
    world.prs[101]["labels"] = []
    _land_on_the_second_nap(monkeypatch, world, 102)
    code, out = _merge(tmp_path, "--yes")
    assert code == 0, out
    assert "approval of PR #102 recorded" in out and "approval of PR #101" not in out
    assert _events(tmp_path, "b1") == [] and [e["kind"] for e in _events(tmp_path, "b2")][:1] == [
        "approval"
    ]
    assert any(a.kind == "queue-open" for a in world.queue_plans)  # type: ignore[attr-defined]


def test_naming_an_unapproved_batch_exits_2_naming_the_label(
    tmp_path: Path, world: World, clone: object
) -> None:
    _ready(world, tmp_path, 1)
    world.prs[101]["labels"] = []
    code, out = _merge(tmp_path, "b1", "--yes")
    assert code == 2
    assert "approved-fr" in out and "b1" in out
    assert world.queue_plans == [] and world.merged == []  # type: ignore[attr-defined]


def test_when_every_batch_is_unapproved_there_is_nothing_to_merge(
    tmp_path: Path, world: World, clone: object
) -> None:
    _ready(world, tmp_path, 1, 2)
    for pr in world.prs.values():
        pr["labels"] = []
    code, out = _merge(tmp_path, "--yes")
    assert code == 0, out
    assert "nothing left to merge" in out
    assert world.queue_plans == [] and world.merged == []  # type: ignore[attr-defined]


def test_merge_settles_approvals_only_under_yes(
    tmp_path: Path, world: World, clone: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ready(world, tmp_path, 1)
    code, out = _merge(tmp_path)
    assert code == 0, out
    assert _events(tmp_path, "b1") == []  # a plan records nothing

    _land_on_the_second_nap(monkeypatch, world, 101)
    code, out = _merge(tmp_path, "--yes")
    assert code == 0, out
    assert "approval of PR #101 recorded at sha-101" in out
    (approval, *_) = _events(tmp_path, "b1")
    assert (approval["kind"], approval["pr"], approval["head"]) == ("approval", 101, "sha-101")
    # the write restamps the file at the writer schema
    assert load_judgements(tmp_path / "judgements.yaml").schema_ == JUDGEMENTS_SCHEMA


def test_a_session_push_after_approval_voids_it_and_removes_the_label(
    tmp_path: Path, world: World, clone: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R12: a push that changes the diff voids the approval (label off, void recorded); a
    PR the approval no longer covers is not an entry, and `batch merge` stops there."""
    _ready(world, tmp_path, 1)
    clone.patch_ids = {"sha-101": "p1", "sha-session": "p2"}  # type: ignore[attr-defined]
    world.checks[101] = [{"name": "lint", "bucket": "fail"}]  # recorded, not queued
    _merge(tmp_path, "--yes")
    assert _events(tmp_path, "b1")[0]["kind"] == "approval"
    world.prs[101]["head_oid"] = "sha-session"
    world.checks[101] = [{"name": "lint", "bucket": "pass"}]
    code, out = _merge(tmp_path, "--yes")
    assert "approval of PR #101 at sha-101 voided: its diff changed at sha-session" in out
    assert "approved-fr" not in world.prs[101]["labels"]
    assert _events(tmp_path, "b1")[-1]["voided_at"] == "sha-session"
    assert world.merged == []  # type: ignore[attr-defined]


def test_merge_creates_the_missing_label_under_yes_only(
    tmp_path: Path, world: World, clone: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ready(world, tmp_path, 1)
    world.labels_defined.clear()  # type: ignore[attr-defined]
    code, out = _merge(tmp_path)
    assert "created label" not in out and "ensure_labels" not in world.calls
    _land_on_the_second_nap(monkeypatch, world, 101)
    code, out = _merge(tmp_path, "--yes")
    assert "ensure_labels" in world.calls
