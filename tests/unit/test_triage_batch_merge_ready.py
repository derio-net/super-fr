"""`merge_ready`: `merge_one` without the wait (wave-driver spec §B, R4).

Built on the fakes of `test_triage_batch_merge` (an in-memory forge and clone).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from fr.triage.batch import pr_open_queue
from fr.triage.batch_merge import (
    MergeAttempt,
    MergeContext,
    MergeStopError,
    merge_ready,
    plan_queue,
)
from fr.triage.model import load_facts, load_judgements

from tests.unit.test_triage_batch_merge import REPO, FakeCheckout, MergeForge, _setup


def _ctx(tmp_path: Path, forge: MergeForge, checkout: FakeCheckout) -> tuple[MergeContext, list]:
    facts = load_facts(tmp_path / "facts.json")
    judgements = load_judgements(tmp_path / "judgements.yaml")
    ctx = MergeContext(
        client=forge,  # type: ignore[arg-type]
        checkout=checkout,  # type: ignore[arg-type]
        repo=REPO,
        version=facts.config_for(REPO).version,
        scratch_root=tmp_path / "merge",
        method="squash",
        say=lambda line: None,
    )
    queue = pr_open_queue(judgements.batches, facts, judgements.issues)
    slots, _ = plan_queue(ctx, queue)
    return ctx, slots


def _solo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[MergeForge, FakeCheckout]:
    return _setup(tmp_path, monkeypatch, [("solo", 1, None, "minor", "4.22.0", ["a.py"])])


def test_a_ready_pr_merges_without_waiting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    assert merge_ready(ctx, slot, None) == MergeAttempt("merged", head="head-solo")
    assert forge.merged == [(1001, "head-solo", "squash")]
    assert forge.waits == []


def test_a_draft_is_reported_and_never_merged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    forge.prs[1001]["draft"] = True
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    assert merge_ready(ctx, slot, None).outcome == "draft"
    assert forge.merged == []


def test_pending_checks_are_reported_without_waiting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    forge.checks[1001] = [{"name": "test", "bucket": "pending"}]
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    got = merge_ready(ctx, slot, None)
    assert (got.outcome, got.checks) == ("pending", ("test",))
    assert forge.merged == [] and forge.waits == []


def test_failing_checks_are_named(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    forge.checks[1001] = [{"name": "lint", "bucket": "fail"}, {"name": "test", "bucket": "pass"}]
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    got = merge_ready(ctx, slot, None)
    assert (got.outcome, got.checks) == ("failing", ("lint",))
    assert forge.merged == []


def test_an_already_merged_pr_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    forge.prs[1001]["state"] = "MERGED"
    assert merge_ready(ctx, slot, None).outcome == "already-merged"


def test_a_moved_head_stops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    forge.prs[1001]["head_oid"] = "elsewhere"
    with pytest.raises(MergeStopError, match="head moved"):
        merge_ready(ctx, slot, None)


def test_a_pr_behind_its_base_is_updated_and_left_for_a_later_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    checkout.up_to_date.discard("head-solo")
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    got = merge_ready(ctx, slot, None)
    assert got.outcome == "updated"
    assert forge.merged == [] and forge.waits == []


def test_a_merge_emits_exactly_one_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    forge, checkout = _solo(tmp_path, monkeypatch)
    ctx, (slot,) = _ctx(tmp_path, forge, checkout)
    lines: list[str] = []
    ctx = dataclasses.replace(ctx, say=lines.append)
    assert merge_ready(ctx, slot, None).outcome == "merged"
    assert len(lines) == 1 and lines[0].startswith("merged PR #")
