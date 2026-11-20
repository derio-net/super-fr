"""The wave merge queue executor's decisions that read no git (spec
2026-11-19-wave-merge-queue R7, R20, R33, R35; Test Plan 12, 14, 25).

The `queue:` config block, the refusals of a repo that cannot run the queue, each
combination's checks under the required-checks rule, and when landings pause.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fr.triage.model import Batch, QueueRecord, TriageConfig, parse_triage_config
from fr.triage.queue_exec import (
    gate_checks_of,
    pause_landings,
    post_merge_owed,
    queue_config,
    queue_refusal,
    slot_check,
)
from fr.triage.wave_queue import QueueAction, QueueConfig, QueuePlan

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
REPO = "example-org/demo"


def _check(name: str, status: str = "completed", conclusion: str = "success") -> dict[str, Any]:
    return {"name": name, "workflow": "ci", "status": status, "conclusion": conclusion}


# ------------------------------------------------------------------ config


def test_the_queue_block_takes_the_specs_defaults() -> None:
    config, ignored = parse_triage_config({"queue": {"ci": "push"}})
    assert ignored == () and config.queue is not None
    assert queue_config(config.queue) == QueueConfig(
        ci="push", depth=2, land="push", check_wait_minutes=60, release="workflow",
        release_workflow=None, release_wait_hours=6, stall_hours=4,
    )  # fmt: skip
    assert TriageConfig().queue is None  # no block: the repo is not driven by the queue


def test_the_queue_block_reads_every_key() -> None:
    block = {"ci": "none", "depth": 3, "land": "merge", "check_wait_minutes": 5,
             "release": "none", "release_workflow": "release.yml", "release_wait_hours": 2,
             "stall_hours": 1}  # fmt: skip
    config, _ = parse_triage_config({"queue": block})
    assert config.queue is not None
    assert queue_config(config.queue) == QueueConfig(**block)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [{"depth": 0}, {"land": "rebase"}, {"ci": "pull"}, {"x": 1}])
def test_a_bad_queue_block_is_refused(bad: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        parse_triage_config({"queue": {"ci": "push", **bad}})


# ------------------------------------------------------------------ refusals (R7, R20)


def test_a_missing_queue_ci_refuses_the_queue_naming_the_line_to_add() -> None:
    config, _ = parse_triage_config({"queue": {"depth": 2}})
    assert config.queue is not None
    why = queue_refusal(config.queue, ci_none=False)
    assert why is not None and "queue.ci" in why and "ci: push" in why
    assert "fr-queue/**" in why


def test_queue_ci_none_is_refused_where_services_report_ci() -> None:
    config, _ = parse_triage_config({"queue": {"ci": "none"}})
    assert config.queue is not None
    why = queue_refusal(config.queue, ci_none=False)
    assert why is not None and "ci none" in why
    assert queue_refusal(config.queue, ci_none=True) is None


def test_queue_ci_push_is_accepted() -> None:
    config, _ = parse_triage_config({"queue": {"ci": "push"}})
    assert config.queue is not None and queue_refusal(config.queue, ci_none=False) is None


# ------------------------------------------------------------------ slot checks (R7)


def test_a_combinations_verdict_reads_the_required_checks_only() -> None:
    checks = [_check("test"), _check("lint", conclusion="failure")]
    verdict, needs = slot_check(checks, ["test"], built_at=NOW, now=NOW, wait_minutes=60)
    assert verdict.verdict == "green" and needs == ()
    verdict, _ = slot_check(checks, ["test", "lint"], built_at=NOW, now=NOW, wait_minutes=60)
    assert verdict.verdict == "failing" and verdict.failing == ("lint",)
    running = [_check("test", status="in_progress", conclusion="")]
    assert slot_check(running, ["test"], built_at=NOW, now=NOW, wait_minutes=60)[0].verdict == (
        "pending"
    )


def test_with_no_required_names_every_check_counts_and_none_is_pending() -> None:
    assert slot_check([], [], built_at=NOW, now=NOW, wait_minutes=60)[0].verdict == "pending"
    failing = [_check("x", conclusion="failure")]
    assert slot_check(failing, [], built_at=NOW, now=NOW, wait_minutes=60)[0].verdict == "failing"
    assert slot_check([_check("x")], [], built_at=NOW, now=NOW, wait_minutes=60)[0].verdict == (
        "green"
    )


def test_a_required_check_that_never_reported_is_a_need_after_the_wait() -> None:
    early = slot_check([_check("test")], ["test", "acceptance"], built_at=NOW, now=NOW,
                       wait_minutes=60)  # fmt: skip
    assert early[0].verdict == "pending" and early[1] == ()
    late = slot_check([_check("test")], ["test", "acceptance"], built_at=NOW,
                      now=NOW + timedelta(minutes=61), wait_minutes=60)  # fmt: skip
    assert late[0].verdict == "pending"
    assert late[1] == ("acceptance",)


def test_gate_checks_of_reads_the_ci_yaml_names() -> None:
    assert gate_checks_of("gate_checks: [ci-ok, docs]\n") == ["ci-ok", "docs"]
    assert gate_checks_of(None) is None
    assert gate_checks_of("tests: ci\n") is None


# ------------------------------------------------------------------ post_merge (R33)


def _batch(bid: str, *events: dict[str, Any]) -> Batch:
    return Batch.model_validate({
        "id": bid, "title": bid, "ids": [f"demo#{len(bid)}"], "wave": 1,
        "events": [{"kind": "dispatch", "at": "2026-11-20T09:00:00Z", "runner": "fake",
                    "handle": "h", "branch": f"feat/batch-{bid}"}, *events],
    })  # fmt: skip


def _record(*events: dict[str, Any]) -> QueueRecord:
    return QueueRecord.model_validate(
        {"repo": REPO, "wave": 1, "scope": "s", "base": "m" * 40, "events": list(events)}
    )


LAND = {"kind": "queue_land", "at": "2026-11-20T11:00:00Z", "main": "t" * 40,
        "entries": [{"batch": "a"}, {"batch": "b"}]}  # fmt: skip


def test_post_merge_is_owed_for_the_last_landing_until_every_batch_recorded_it() -> None:
    record = _record({"kind": "queue_open", "at": "2026-11-20T10:00:00Z"}, LAND)
    done = {"kind": "post_merge", "at": "2026-11-20T11:05:00Z"}
    assert post_merge_owed(record, [_batch("a"), _batch("b")]) == ("a", "b")
    assert post_merge_owed(record, [_batch("a", done), _batch("b", done)]) == ()
    stale = {"kind": "post_merge", "at": "2026-11-20T10:30:00Z"}  # before this landing
    assert post_merge_owed(record, [_batch("a", stale), _batch("b", done)]) == ("a",)
    assert post_merge_owed(_record({"kind": "queue_open", "at": "2026-11-20T10:00:00Z"}),
                           []) == ()  # fmt: skip


def test_pausing_strips_the_landing_and_says_why_with_a_need() -> None:
    plan = QueuePlan(REPO, "open", 1, (
        QueueAction("queue-land", REPO, "land a", entries=("a",), sha="t"),
        QueueAction("queue-build", REPO, "build c", entries=("c",), slots=(1,)),
    ))  # fmt: skip
    paused = pause_landings(plan, "post_merge failed: boom")
    assert [a.kind for a in paused.actions] == ["queue-build", "queue-need"]
    assert "post_merge failed: boom" in paused.actions[-1].detail
    assert pause_landings(plan, None) is plan
