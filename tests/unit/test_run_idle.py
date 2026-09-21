"""Liveness — `fr run check --idle` and `--stalled-after`.

Spec `2026-09-20-unit-record-unification-design.md` §4.G, phase 6: the artifact
half of gh#518. *"Keep going" was an obligation with no enforcing artifact*: a
run whose cursor was ready — `fr run advance` would have printed the next brief
immediately — was indistinguishable from one still working.

`--idle` draws that line and ONLY that line. Exit **3** exactly when the run is
advanceable and nobody is working on it; exit 0 in every legitimate stop. The
legitimate stops each get their own test below, because a false positive here
is not a wrong report — it is a Stop hook refusing to let an operator end a
turn, which is the worst outcome this whole feature can have. When in doubt the
predicate says "not idle".

`--stalled-after` is the other reading of the same record: an open attempt older
than a threshold is REPORTED, with its age, and never fails anything. fr cannot
tell a long phase from a dead agent (gh#503's executor sat 11.5 hours; a phase
of the run that built this took a legitimate 58 minutes) and says so.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import yaml
from fr.run.model import load_run_state, run_path

from tests.unit.test_run_cli import (
    _AGENT_TWO_STEP_SHAPE,
    _CLI_ONLY_SHAPE,
    _FAILING_SHAPE,
    _GATE_SHAPE,
    _GROUPED_SHAPE,
    _invoke,
    _plan_with_tags,
    _repo,
    _squash,
    _started_grouped_with_plan,
    _write_shape,
)
from tests.unit.test_run_evidence import _shape as _evidence_shape

IDLE = 3
"""The one new exit code. `fr run check` used only 0/1/2 before it."""


def _start(tmp_path: Path, name: str, shape: str) -> tuple[Path, Path]:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, name, shape)
    result = _invoke(repo, shipped, ["run", "start", name, "--branch", "b", "--run-id", "r1"])
    assert result.exit_code == 0, result.output
    return repo, shipped


def _grouped(tmp_path: Path, phases: list[tuple[int, str, tuple[int, ...]]]) -> tuple[Path, Path]:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _GROUPED_SHAPE)
    _started_grouped_with_plan(repo, shipped, _plan_with_tags(repo, phases))
    return repo, shipped


def _idle(repo: Path, shipped: Path, *argv: str):
    return _invoke(repo, shipped, ["run", "check", *argv, "--idle"])


def _idle_json(repo: Path, shipped: Path, *argv: str) -> tuple[int, dict]:
    result = _invoke(repo, shipped, ["run", "check", *argv, "--idle", "--format", "json"])
    return result.exit_code, json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Idle — the three shapes of "advance would have printed the next thing".
# ---------------------------------------------------------------------------


def test_a_run_nobody_has_started_on_is_idle_and_names_the_next_command(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)

    result = _idle(repo, shipped, "r1")

    assert result.exit_code == IDLE, result.output
    assert "fr run advance r1" in _squash(result.output), result.output


def test_the_gh518_shape_a_unit_returned_and_the_next_one_was_never_dispatched(
    tmp_path: Path,
) -> None:
    """gh#518 exactly: phase 1's executor returned and was resolved, the group
    step is still `running`, nothing is held — and the turn ended anyway."""
    repo, shipped = _grouped(tmp_path, [(1, "agentic", ()), (2, "agentic", ())])
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    unit = ["--step", "code", "--item", "phase/1"]
    assert _invoke(repo, shipped, ["run", "resolve", "r1", *unit, "--state", "done"]).exit_code == 0
    assert load_run_state(repo, "r1").steps["implement"].state == "running"

    result = _idle(repo, shipped, "r1")

    assert result.exit_code == IDLE, result.output
    assert "fr run advance r1" in _squash(result.output), result.output


def test_an_abandoned_unit_is_idle_because_its_hold_was_released(tmp_path: Path) -> None:
    """Decision u1's witness, read from the other side: `claim --abandoned`
    leaves the unit `running` and CLOSES the attempt, and `advance` re-briefs
    it. A predicate keyed on `running` would call this run busy for ever."""
    repo, shipped = _grouped(tmp_path, [(1, "agentic", ())])
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    unit = ["--step", "code", "--item", "phase/1"]
    assert _idle(repo, shipped, "r1").exit_code == 0
    assert _invoke(repo, shipped, ["run", "claim", "r1", *unit, "--abandoned"]).exit_code == 0

    assert _idle(repo, shipped, "r1").exit_code == IDLE


# ---------------------------------------------------------------------------
# The six legitimate stops — ONE TEST APIECE. Each must exit 0.
# ---------------------------------------------------------------------------


def test_stop_1_a_pending_operator_gate_is_not_idle(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "gated", _GATE_SHAPE)
    # before `advance` has ever seen it (state: pending) ...
    code, body = _idle_json(repo, shipped, "r1")
    assert (code, body["idle"], body["reason"]) == (0, False, "gate"), body
    # ... and after (state: blocked). Same answer: the run waits on a human.
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    assert load_run_state(repo, "r1").steps["brainstorm"].state == "blocked"

    code, body = _idle_json(repo, shipped, "r1")

    assert (code, body["idle"], body["reason"]) == (0, False, "gate"), body


def test_stop_2_an_outstanding_manual_phase_is_not_idle(tmp_path: Path) -> None:
    """fr-goal's front-load: `1 [manual], 2 agentic depends_on [1]`, and the
    operator has not given the go. `advance` REFUSES the whole group here
    (`_manual_placement_preflight`), so the run is not advanceable — it waits
    on a human, and blocking the stop would demand a command that cannot work.
    """
    from fr.plan_ops import tick

    phases = [(1, "manual", ()), (2, "agentic", (1,))]
    repo, shipped = _grouped(tmp_path, phases)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 2  # the premise

    code, body = _idle_json(repo, shipped, "r1")

    assert (code, body["idle"], body["reason"]) == (0, False, "manual"), body
    # ... and it is THAT which silenced it: the operator's go makes it idle.
    tick(repo / "docs/superpowers/plans/2026-09-20-tagged", "P1.T1.S1")
    assert _idle(repo, shipped, "r1").exit_code == IDLE


def test_stop_3_a_held_unit_is_not_idle(tmp_path: Path) -> None:
    """THE SUBTLE ONE. On Claude Code a dispatched executor runs in the
    background and its return arrives as a notification, so a turn that ends
    while a unit is held is CORRECT — blocking it would wedge every ordinary
    run at the exact moment it is healthiest."""
    repo, shipped = _grouped(tmp_path, [(1, "agentic", ()), (2, "agentic", ())])
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0  # dispatched

    code, body = _idle_json(repo, shipped, "r1")

    assert (code, body["idle"], body["reason"]) == (0, False, "held"), body
    assert _idle(repo, shipped, "r1").exit_code == 0


def test_stop_4_a_failed_step_is_not_idle(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "fails", _FAILING_SHAPE)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 1

    code, body = _idle_json(repo, shipped, "r1")

    assert (code, body["idle"], body["reason"]) == (0, False, "failed"), body


def test_stop_4b_a_failed_unit_of_a_group_is_not_idle(tmp_path: Path) -> None:
    repo, shipped = _grouped(tmp_path, [(1, "agentic", ()), (2, "agentic", ())])
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    unit = ["--step", "code", "--item", "phase/1"]
    assert (
        _invoke(repo, shipped, ["run", "resolve", "r1", *unit, "--state", "failed"]).exit_code == 0
    )

    code, body = _idle_json(repo, shipped, "r1")

    assert (code, body["idle"], body["reason"]) == (0, False, "failed"), body


def test_stop_5_a_finished_run_is_not_idle(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0

    code, body = _idle_json(repo, shipped, "r1")

    assert (code, body["idle"], body["reason"]) == (0, False, "finished"), body


def test_stop_6_no_run_at_all_is_not_idle(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"

    result = _invoke(repo, shipped, ["run", "check", "--idle", "--format", "json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"idle": False, "reason": "no-run", "runs": []}
    assert _invoke(repo, shipped, ["run", "check", "--idle"]).exit_code == 0


# ---------------------------------------------------------------------------
# Finding the run without being told its id — what both adapters do.
# ---------------------------------------------------------------------------


def test_with_no_run_id_it_reads_the_runs_of_the_checked_out_branch(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)

    code, body = _idle_json(repo, shipped)

    assert code == IDLE, body
    assert body["run"] == "r1" and body["next_command"] == "fr run advance r1", body


def test_a_cursor_inherited_from_another_branch_is_never_this_sessions_run(
    tmp_path: Path,
) -> None:
    """A workspace is a checkout of `main`, so it carries every cursor ever
    merged and not yet archived — this repo's own worktree held FIVE while this
    was written. One of those being advanceable is nobody's stall."""
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    path = run_path(repo, "r1")
    path.write_text(path.read_text().replace("branch: b\n", "branch: somebody-elses\n"))

    code, body = _idle_json(repo, shipped)

    assert (code, body["idle"], body["reason"]) == (0, False, "no-run"), body


def test_a_finished_run_beside_a_live_one_on_the_same_branch_does_not_hide_it(
    tmp_path: Path,
) -> None:
    """This branch's own state: a delivered run AND the `-r2` that followed."""
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    _write_shape(shipped, "agentic-two-step", _AGENT_TWO_STEP_SHAPE)
    started = _invoke(
        repo, shipped, ["run", "start", "agentic-two-step", "--branch", "b", "--run-id", "r2"]
    )
    assert started.exit_code == 0, started.output

    code, body = _idle_json(repo, shipped)

    assert code == IDLE, body
    assert body["run"] == "r2" and body["next_command"] == "fr run advance r2", body


def test_two_idle_runs_on_one_branch_is_ambiguous_and_ambiguity_is_silence(
    tmp_path: Path,
) -> None:
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    _write_shape(shipped, "agentic-two-step", _AGENT_TWO_STEP_SHAPE)
    assert (
        _invoke(
            repo, shipped, ["run", "start", "agentic-two-step", "--branch", "b", "--run-id", "r2"]
        ).exit_code
        == 0
    )

    code, body = _idle_json(repo, shipped)

    assert (code, body["idle"], body["reason"]) == (0, False, "ambiguous"), body
    assert body["runs"] == ["r1", "r2"], body


def test_an_unreadable_cursor_on_the_branch_is_silence_not_a_traceback(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    run_path(repo, "r1").write_text("run: r1\nthis is: [not a cursor\n")

    result = _invoke(repo, shipped, ["run", "check", "--idle", "--format", "json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["idle"] is False


def test_a_drifted_manifest_is_not_advanceable_so_it_is_not_idle(tmp_path: Path) -> None:
    """`advance` refuses a cursor whose shape moved under it. A guard that
    blocked here would demand, once per position, a command that cannot work."""
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    _write_shape(shipped, "cli-only", _CLI_ONLY_SHAPE.replace("id: bye", "id: farewell"))
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 2  # the premise

    code, body = _idle_json(repo, shipped, "r1")

    assert (code, body["idle"], body["reason"]) == (0, False, "not-advanceable"), body


# ---------------------------------------------------------------------------
# Phase 5's warning: evidence DEBT is not a stop condition, either way.
# ---------------------------------------------------------------------------


def _with_pregate_review_debt(tmp_path: Path) -> tuple[Path, Path]:
    """Phase 1 reviewed BEFORE the shape declared `evidence:`, then the shape
    grows it — the state every in-flight run is in on upgrade day."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "grouped", _evidence_shape(evidence=False))
    plan_rel = _plan_with_tags(repo, [(1, "agentic", ()), (2, "agentic", ())])
    _started_grouped_with_plan(repo, shipped, plan_rel)
    for member in ("code", "peer-review"):
        assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
        unit = ["--step", member, "--item", "phase/1"]
        resolved = _invoke(repo, shipped, ["run", "resolve", "r1", *unit, "--state", "done"])
        assert resolved.exit_code == 0, resolved.output
    _write_shape(shipped, "grouped", _evidence_shape(evidence=True))
    debt = _invoke(repo, shipped, ["run", "check", "r1"])
    assert "unevidenced" in debt.output, debt.output  # the premise
    return repo, shipped


def test_unevidenced_debt_does_not_stop_an_idle_run_from_being_idle(tmp_path: Path) -> None:
    repo, shipped = _with_pregate_review_debt(tmp_path)

    assert _idle(repo, shipped, "r1").exit_code == IDLE


def test_unevidenced_debt_does_not_make_a_held_run_look_idle(tmp_path: Path) -> None:
    repo, shipped = _with_pregate_review_debt(tmp_path)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0  # phase/2/code held

    code, body = _idle_json(repo, shipped, "r1")

    assert (code, body["idle"], body["reason"]) == (0, False, "held"), body


# ---------------------------------------------------------------------------
# `--format json` carries the same facts, and a position the adapters compare.
# ---------------------------------------------------------------------------


def test_json_carries_the_same_facts_as_the_text(tmp_path: Path) -> None:
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)

    code, body = _idle_json(repo, shipped, "r1")

    assert code == IDLE
    assert body["idle"] is True and body["reason"] == "idle", body
    assert body["run"] == "r1" and body["cursor"] == "hello", body
    assert body["next_command"] == "fr run advance r1", body
    assert re.fullmatch(r"[0-9a-f]{16}", body["position"]), body
    assert body["stalled"] == [], body


def test_the_position_moves_when_the_cursor_does_and_only_then(tmp_path: Path) -> None:
    """The loop breaker's key (§4.G): both adapters act at most once per
    position, so it must be stable while nothing moves and must move when
    anything does — including a unit resolving INSIDE an unmoved group step."""
    repo, shipped = _grouped(tmp_path, [(1, "agentic", ()), (2, "agentic", ())])
    _, first = _idle_json(repo, shipped, "r1")
    _, again = _idle_json(repo, shipped, "r1")
    assert first["position"] == again["position"]

    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    _, held = _idle_json(repo, shipped, "r1")
    unit = ["--step", "code", "--item", "phase/1"]
    assert _invoke(repo, shipped, ["run", "resolve", "r1", *unit, "--state", "done"]).exit_code == 0
    _, after = _idle_json(repo, shipped, "r1")

    assert after["cursor"] == first["cursor"] == "implement"
    assert len({first["position"], held["position"], after["position"]}) == 3


def test_a_failing_advance_does_not_move_the_position(tmp_path: Path) -> None:
    """The trap the loop breaker exists for: `advance` keeps failing, the
    position stays put, and the guard therefore acts ONCE."""
    repo, shipped = _grouped(tmp_path, [(1, "agentic", ())])
    _, before = _idle_json(repo, shipped, "r1")
    plan_meta = repo / "docs/superpowers/plans/2026-09-20-tagged/_meta.yaml"
    plan_meta.write_text("not: [a plan\n")
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 2
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 2

    assert load_run_state(repo, "r1").steps["implement"].state == "pending"
    # an unreadable plan is ALSO not advanceable, so the answer is silence ...
    code, body = _idle_json(repo, shipped, "r1")
    assert (code, body["reason"]) == (0, "not-advanceable"), body
    # ... at the same position as before.
    assert body["position"] == before["position"]


# ---------------------------------------------------------------------------
# Stalled — reported with its age, never a failure.
# ---------------------------------------------------------------------------


def _age_the_open_attempt(repo: Path, minutes: int) -> str:
    """Rewrite the one open attempt's `dispatched` to `minutes` ago."""
    path = run_path(repo, "r1")
    doc = yaml.safe_load(path.read_text())
    then = (dt.datetime.now(dt.UTC) - dt.timedelta(minutes=minutes)).replace(microsecond=0)
    attempts = doc["steps"]["brainstorm"]["units"]["step/brainstorm"]["attempts"]
    assert len(attempts) == 1 and "returned" not in attempts[0], attempts
    attempts[0]["dispatched"] = then.isoformat()
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return then.isoformat()


def _held_flat_step(tmp_path: Path) -> tuple[Path, Path]:
    repo, shipped = _start(tmp_path, "agentic-two-step", _AGENT_TWO_STEP_SHAPE)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    return repo, shipped


def test_an_attempt_held_past_the_threshold_is_reported_with_its_age(tmp_path: Path) -> None:
    repo, shipped = _held_flat_step(tmp_path)
    _age_the_open_attempt(repo, 690)  # gh#503's 11.5 hours

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 0, result.output
    out = _squash(result.output)
    assert "step/brainstorm has been held for 11h30m" in out, out
    assert "fr cannot tell a long phase from a dead agent" in out, out


def test_a_stalled_attempt_never_changes_the_exit_code(tmp_path: Path) -> None:
    """Asserted literally, in every mode: plain, `--idle`, and json. A stalled
    unit is HELD, and held is a legitimate stop — it must never read as idle."""
    repo, shipped = _held_flat_step(tmp_path)
    before = [
        _invoke(repo, shipped, ["run", "check", "r1"]).exit_code,
        _idle(repo, shipped, "r1").exit_code,
    ]
    dispatched = _age_the_open_attempt(repo, 690)

    after = [
        _invoke(repo, shipped, ["run", "check", "r1"]).exit_code,
        _idle(repo, shipped, "r1").exit_code,
    ]
    code, body = _idle_json(repo, shipped, "r1")

    assert before == after == [0, 0]
    assert (code, body["idle"], body["reason"]) == (0, False, "held"), body
    assert body["stalled"] == [
        {
            "step": "brainstorm",
            "unit": "step/brainstorm",
            "dispatched": dispatched,
            "age_minutes": 690,
        }
    ], body


def test_the_threshold_is_the_operators_to_move(tmp_path: Path) -> None:
    """Default 120: a legitimate 58-minute phase is NOT reported; ask for 30
    and it is."""
    repo, shipped = _held_flat_step(tmp_path)
    _age_the_open_attempt(repo, 58)

    default = _invoke(repo, shipped, ["run", "check", "r1"])
    tighter = _invoke(repo, shipped, ["run", "check", "r1", "--stalled-after", "30"])

    assert "has been held for" not in _squash(default.output), default.output
    assert "step/brainstorm has been held for 58m" in _squash(tighter.output), tighter.output
    assert (default.exit_code, tighter.exit_code) == (0, 0)


def test_an_unparseable_dispatch_time_is_not_reported_and_not_an_error(tmp_path: Path) -> None:
    repo, shipped = _held_flat_step(tmp_path)
    path = run_path(repo, "r1")
    doc = yaml.safe_load(path.read_text())
    doc["steps"]["brainstorm"]["units"]["step/brainstorm"]["attempts"][0]["dispatched"] = "whenever"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))

    result = _invoke(repo, shipped, ["run", "check", "r1"])

    assert result.exit_code == 0, result.output
    assert "has been held for" not in _squash(result.output)


def test_with_nothing_idle_it_reports_the_held_run_not_the_finished_one(tmp_path: Path) -> None:
    """Which run is REPORTED never moves the exit code, but it decides what a
    human reads — and whose stalled attempts are listed."""
    repo, shipped = _start(tmp_path, "cli-only", _CLI_ONLY_SHAPE)
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    _write_shape(shipped, "agentic-two-step", _AGENT_TWO_STEP_SHAPE)
    started = ["run", "start", "agentic-two-step", "--branch", "b", "--run-id", "r2"]
    assert _invoke(repo, shipped, started).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r2"]).exit_code == 0

    code, body = _idle_json(repo, shipped)

    assert (code, body["run"], body["reason"]) == (0, "r2", "held"), body


# ---------------------------------------------------------------------------
# The two halves of "held", each pinned ALONE. Mutation-testing found them
# covering for one another: drop either and the other still said "held", so
# neither was actually tested.
# ---------------------------------------------------------------------------


def test_a_running_unit_with_no_dispatch_record_is_held_as_advance_holds_it(
    tmp_path: Path,
) -> None:
    """An adopted or pre-gh#508 cursor: `running`, and no attempt was ever
    recorded. `advance` refuses it (ALREADY RUNNING), so it is not idle —
    `hold_on`'s recordless fallback, asked here exactly as `advance` asks it."""
    repo, shipped = _grouped(tmp_path, [(1, "agentic", ())])
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    path = run_path(repo, "r1")
    doc = yaml.safe_load(path.read_text())
    del doc["steps"]["implement"]["units"]["phase/1/code"]["attempts"]
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    refused = _invoke(repo, shipped, ["run", "advance", "r1"])
    assert refused.exit_code == 2 and "ALREADY RUNNING" in _squash(refused.output)  # the premise

    code, body = _idle_json(repo, shipped, "r1")

    assert (code, body["idle"], body["reason"]) == (0, False, "held"), body


def test_an_open_attempt_anywhere_in_the_cursor_means_somebody_is_working(
    tmp_path: Path,
) -> None:
    """Not only under the cursor step. The pure function, on a cursor whose
    open attempt sits on a step the cursor has moved past — a state fr does not
    write, which is the point: an unrecognised shape with somebody in it is
    "held", never "idle"."""
    from fr.run.liveness import is_idle
    from fr.workflow.resolve import resolve_workflow

    repo, shipped = _held_flat_step(tmp_path)
    state = load_run_state(repo, "r1")
    after = state.steps["after"]
    moved = state.model_copy(update={"cursor": "after"})
    assert after.state == "pending"
    manifest = resolve_workflow("agentic-two-step", repo, shipped_root=shipped)

    reading = is_idle(moved, manifest)

    assert (reading.idle, reading.reason) == (False, "held"), reading


def test_a_synthesized_attempt_is_cost_never_a_hold(tmp_path: Path) -> None:
    """`p3-synthesized-not-a-hold`: the 4 -> 5 migration gives most pre-gh#508
    units one identity-less attempt with no `returned`, because fr never knew
    one. Read as a hold, every migrated run would look busy for ever and the
    guard would protect nothing that was in flight on upgrade day."""
    repo, shipped = _grouped(tmp_path, [(1, "agentic", ()), (2, "agentic", ())])
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    unit = ["--step", "code", "--item", "phase/1"]
    assert _invoke(repo, shipped, ["run", "resolve", "r1", *unit, "--state", "done"]).exit_code == 0
    path = run_path(repo, "r1")
    doc = yaml.safe_load(path.read_text())
    done = doc["steps"]["implement"]["units"]["phase/1/code"]
    done["attempts"] = [{"dispatched": done["attempts"][0]["dispatched"], "synthesized": True}]
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    assert load_run_state(repo, "r1")  # still a cursor the live model reads

    assert _idle(repo, shipped, "r1").exit_code == IDLE
