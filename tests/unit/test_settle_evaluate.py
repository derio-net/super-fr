"""The pure settle engine: states, modes and the verdict (spec 2026-11-23-pr-readiness-wait
R2, R4)."""

from __future__ import annotations

from typing import Any

import pytest
from fr.run.ci_evidence import NO_CI_WAIT_SECONDS
from fr.settle.evaluate import evaluate
from fr.settle.model import Modes

HEAD = "a" * 40
NOW = 1_000_000.0
OLD = NOW - NO_CI_WAIT_SECONDS - 1
FRESH = NOW - 10


def _view(mergeable: str = "MERGEABLE", merge_state: str = "CLEAN") -> dict[str, Any]:
    return {
        "head_oid": HEAD,
        "base_ref": "main",
        "mergeable": mergeable,
        "merge_state": merge_state,
    }


def _check(name: str, bucket: str) -> dict[str, Any]:
    return {"name": name, "bucket": bucket, "state": bucket.upper()}


GREEN = [_check("ci-ok", "pass")]


def _modes(conflicts: str = "fix", ci: str = "fix") -> Modes:
    return Modes.from_setting(conflicts=conflicts, ci=ci, source="default")


def _eval(
    view: dict[str, Any] | None = None,
    checks: list[dict[str, Any]] | None = None,
    gates: list[str] | None = None,
    modes: Modes | None = None,
    *,
    ci_none: bool = False,
    committed: float | None = OLD,
    estimated: bool = False,
) -> Any:
    return evaluate(
        view if view is not None else _view(),
        GREEN if checks is None else checks,
        gates,
        modes or _modes(),
        ci_none=ci_none,
        head_committed_at=committed,
        head_time_estimated=estimated,
        now=NOW,
    )


# ---- conflict states (R2) ----------------------------------------------------------


@pytest.mark.parametrize(
    ("mergeable", "merge_state", "state"),
    [
        ("MERGEABLE", "CLEAN", "clean"),
        ("MERGEABLE", "BLOCKED", "clean"),
        ("MERGEABLE", "UNSTABLE", "clean"),
        ("MERGEABLE", "DRAFT", "clean"),
        ("CONFLICTING", "DIRTY", "conflicting"),
        ("CONFLICTING", "UNKNOWN", "conflicting"),
        ("MERGEABLE", "DIRTY", "conflicting"),
        ("UNKNOWN", "UNKNOWN", "unknown"),
        ("UNKNOWN", "CLEAN", "unknown"),
        ("MERGEABLE", "UNKNOWN", "unknown"),
        ("", "", "unknown"),
    ],
)
def test_conflict_state(mergeable: str, merge_state: str, state: str) -> None:
    assert _eval(_view(mergeable, merge_state)).conflict_state == state


# ---- CI states (R2) ----------------------------------------------------------------


def test_ci_green() -> None:
    assert _eval(checks=[_check("a", "pass"), _check("b", "skipping")]).ci_state == "green"


def test_ci_red_names_the_failing_checks() -> None:
    v = _eval(checks=[_check("lint", "fail"), _check("test", "fail"), _check("ok", "pass")])
    assert v.ci_state == "red"
    assert v.failing_checks == ("lint", "test")
    assert any("lint" in ln and "test" in ln for ln in v.lines)


def test_a_cancelled_check_is_pending_never_red() -> None:
    """Spec 2026-11-24-ci-economy R3: a cancelled run was superseded."""
    v = _eval(checks=[_check("test", "cancel"), _check("ok", "pass")])
    assert v.ci_state == "pending" and v.failing_checks == ()
    red = _eval(checks=[_check("lint", "fail"), _check("test", "cancel")])
    assert red.ci_state == "red" and red.failing_checks == ("lint",)


def test_ci_pending_while_a_check_has_not_finished() -> None:
    assert _eval(checks=[_check("a", "pass"), _check("b", "pending")]).ci_state == "pending"


def test_ci_pending_when_no_check_reported_on_a_fresh_head() -> None:
    assert _eval(checks=[], committed=FRESH).ci_state == "pending"


def test_ci_missing_when_no_check_reported_after_the_wait() -> None:
    assert _eval(checks=[], committed=OLD).ci_state == "missing"


def test_ci_unrunnable_on_a_conflicting_pr() -> None:
    assert _eval(_view("CONFLICTING", "DIRTY"), checks=[]).ci_state == "unrunnable"


def test_ci_none_under_ci_none() -> None:
    assert _eval(checks=[], ci_none=True).ci_state == "none"


def test_a_gate_set_filters_the_checks() -> None:
    checks = [_check("ci-ok", "pass"), _check("advisory", "fail")]
    assert _eval(checks=checks, gates=["ci-ok"]).ci_state == "green"
    assert _eval(checks=checks, gates=None).ci_state == "red"


def test_an_unreported_gate_is_pending_while_ci_runs_and_missing_after() -> None:
    running = [_check("lint", "pending")]
    assert _eval(checks=running, gates=["ci-ok"]).ci_state == "pending"
    done = [_check("lint", "pass")]
    assert _eval(checks=done, gates=["ci-ok"]).ci_state == "missing"
    assert _eval(checks=[], gates=["ci-ok"], committed=FRESH).ci_state == "pending"


def test_an_unreported_gate_on_a_fresh_head_is_pending_while_other_checks_finished() -> None:
    done = [_check("lint", "pass")]
    v = _eval(checks=done, gates=["ci-ok"], committed=FRESH)
    assert v.ci_state == "pending" and v.exit_code == 75
    assert any("ci-ok" in ln for ln in v.lines)
    v = _eval(checks=done, gates=["ci-ok"], committed=OLD)
    assert v.ci_state == "missing" and v.exit_code == 4


def test_an_absent_gate_has_its_own_hint() -> None:
    absent = _eval(checks=[_check("lint", "pass")], gates=["ci-ok"], committed=OLD)
    nothing = _eval(checks=[], committed=OLD)
    assert absent.ci_state == nothing.ci_state == "missing"
    ci_line = next(ln for ln in absent.lines if ln.startswith("ci "))
    assert "ci-ok" in ci_line and "gate" in ci_line
    assert ci_line != next(ln for ln in nothing.lines if ln.startswith("ci "))


# ---- modes and the exit code (R4) --------------------------------------------------

CONFLICT_VIEWS = {
    "clean": _view(),
    "conflicting": _view("CONFLICTING", "DIRTY"),
    "unknown": _view("UNKNOWN", "UNKNOWN"),
}
CI_CHECKS: dict[str, tuple[list[dict[str, Any]], float]] = {
    "green": (GREEN, OLD),
    "red": ([_check("t", "fail")], OLD),
    "pending": ([_check("t", "pending")], OLD),
    "missing": ([], OLD),
    "gate-absent-fresh": ([_check("lint", "pass")], FRESH),
    "gate-absent-old": ([_check("lint", "pass")], OLD),
}
CI_STATE = {"gate-absent-fresh": "pending", "gate-absent-old": "missing"}
CI_GATES = {"gate-absent-fresh": ["ci-ok"], "gate-absent-old": ["ci-ok"]}
CONFLICT_CODE = {"clean": 0, "conflicting": 4, "unknown": 75}
CI_CODE = {
    "green": 0,
    "red": 4,
    "pending": 75,
    "missing": 4,
    "gate-absent-fresh": 75,
    "gate-absent-old": 4,
    "unrunnable": 4,
    "none": 0,
}


@pytest.mark.parametrize("state", sorted(CONFLICT_VIEWS))
@pytest.mark.parametrize("mode", ["off", "report", "fix"])
def test_the_conflict_concern_decides_the_code_only_under_fix(mode: str, state: str) -> None:
    v = _eval(CONFLICT_VIEWS[state], modes=_modes(conflicts=mode, ci="off"))
    assert v.exit_code == (CONFLICT_CODE[state] if mode == "fix" else 0)
    assert v.conflict_state == ("off" if mode == "off" else state)


@pytest.mark.parametrize("state", sorted(CI_CODE))
@pytest.mark.parametrize("mode", ["off", "report", "fix"])
def test_the_ci_concern_decides_the_code_only_under_fix(mode: str, state: str) -> None:
    modes = _modes(conflicts="off", ci=mode)
    if state == "unrunnable":
        v = _eval(CONFLICT_VIEWS["conflicting"], checks=[], modes=modes)
    elif state == "none":
        v = _eval(checks=[], ci_none=True, modes=modes)
    else:
        checks, committed = CI_CHECKS[state]
        v = _eval(checks=checks, gates=CI_GATES.get(state), committed=committed, modes=modes)
    assert v.exit_code == (CI_CODE[state] if mode == "fix" else 0)
    assert v.ci_state == ("off" if mode == "off" else CI_STATE.get(state, state))


def test_unrunnable_ci_fails_under_fix_and_reports_under_report() -> None:
    view = CONFLICT_VIEWS["conflicting"]
    assert _eval(view, checks=[], modes=_modes(conflicts="off", ci="fix")).exit_code == 4
    assert _eval(view, checks=[], modes=_modes(conflicts="off", ci="report")).exit_code == 0


def test_none_ci_is_settled() -> None:
    assert _eval(checks=[], ci_none=True).exit_code == 0


def test_a_failing_fix_concern_outranks_a_pending_one() -> None:
    v = _eval(CONFLICT_VIEWS["unknown"], checks=[_check("t", "fail")])
    assert v.exit_code == 4


def test_a_report_concern_never_changes_the_code() -> None:
    v = _eval(CONFLICT_VIEWS["conflicting"], checks=[], modes=_modes(conflicts="report"))
    # CI under fix is unrunnable (4); the report concern's conflict adds nothing.
    assert v.exit_code == 4
    v = _eval(CONFLICT_VIEWS["conflicting"], modes=_modes(conflicts="report", ci="report"))
    assert v.exit_code == 0
    assert v.conflict_state == "conflicting"
    assert any("conflicting" in ln for ln in v.lines)


def test_the_witness_value() -> None:
    v = _eval(modes=_modes(conflicts="report", ci="fix"))
    assert v.witness == f"report/fix:clean/green@{HEAD}"
    v = _eval(modes=_modes(conflicts="off", ci="fix"))
    assert v.witness == f"off/fix:off/green@{HEAD}"


def test_settled_concerns_say_so() -> None:
    v = _eval()
    assert v.exit_code == 0
    assert v.settled
    assert not _eval(checks=[_check("t", "pending")]).settled


# ---- the head's commit time (review l-errors-r7) ------------------------------------


def test_an_unknown_commit_time_is_pending_never_missing() -> None:
    v = _eval(checks=[], committed=None)
    assert v.ci_state == "pending"
    assert "commit time could not be read" in v.lines[1]
    absent = _eval(checks=[_check("lint", "pass")], gates=["ci-ok"], committed=None)
    assert absent.ci_state == "pending"


def test_an_estimated_commit_time_is_said_on_the_line() -> None:
    v = _eval(checks=[], committed=OLD, estimated=True)
    assert v.ci_state == "missing"
    assert "estimated from local HEAD" in v.lines[1]
    green = _eval(estimated=True)
    assert "estimated" not in green.lines[1]


# ---- the whole product, against R4 restated here (review l-tests-r5) ----------------
#
# The expectations below come from the spec's words, written out as tables in this
# test, never from the engine: R2 says a conflicting PR's CI is `unrunnable` and a
# `ci none` repo's CI is `none`; R4 says only a `fix` concern decides the code.

R4_FIX_CODE = {
    "clean": 0, "conflicting": 4, "unknown": 75,
    "green": 0, "red": 4, "pending": 75, "missing": 4, "unrunnable": 4, "none": 0,
}  # fmt: skip
UNSETTLED_STATES = {"unknown", "pending"}
CI_INPUTS: dict[str, tuple[list[dict[str, Any]], bool]] = {
    "green": (GREEN, False),
    "red": ([_check("t", "fail")], False),
    "pending": ([_check("t", "pending")], False),
    "missing": ([], False),
    "none": ([], True),
}
MODES = ("off", "report", "fix")


def _expected_ci(conflict: str, ci_input: str) -> str:
    if ci_input == "none":
        return "none"
    return "unrunnable" if conflict == "conflicting" else ci_input


@pytest.mark.parametrize("conflict", sorted(CONFLICT_VIEWS))
@pytest.mark.parametrize("ci_input", sorted(CI_INPUTS))
@pytest.mark.parametrize("c_mode", MODES)
@pytest.mark.parametrize("ci_mode", MODES)
def test_every_state_and_mode_pair_against_r4(
    conflict: str, ci_input: str, c_mode: str, ci_mode: str
) -> None:
    checks, ci_none = CI_INPUTS[ci_input]
    v = _eval(
        CONFLICT_VIEWS[conflict],
        checks=checks,
        ci_none=ci_none,
        committed=OLD,
        modes=_modes(conflicts=c_mode, ci=ci_mode),
    )

    c_state = "off" if c_mode == "off" else conflict
    ci_state = "off" if ci_mode == "off" else _expected_ci(conflict, ci_input)
    codes = [
        R4_FIX_CODE[c_state] if c_mode == "fix" else 0,
        R4_FIX_CODE[ci_state] if ci_mode == "fix" else 0,
    ]
    expected = 4 if 4 in codes else 75 if 75 in codes else 0
    assert (v.conflict_state, v.ci_state) == (c_state, ci_state)
    assert v.exit_code == expected
    assert v.settled == (c_state not in UNSETTLED_STATES and ci_state not in UNSETTLED_STATES)
    assert v.witness == f"{c_mode}/{ci_mode}:{c_state}/{ci_state}@{HEAD}"


@pytest.mark.parametrize("c_mode", ["off", "report"])
def test_a_relaxed_conflict_key_names_the_coupling_to_ci(c_mode: str) -> None:
    """l-tests-r6: CI cannot run on a conflicting PR, so relaxing only conflicts leaves CI
    `unrunnable` under fix: the line says to relax `settle.ci` too, or merge the base."""
    v = _eval(CONFLICT_VIEWS["conflicting"], checks=[], modes=_modes(conflicts=c_mode, ci="fix"))

    assert (v.ci_state, v.exit_code) == ("unrunnable", 4)
    assert "settle.ci" in v.lines[1] and "conflict" in v.lines[1]


def test_the_deliver_line_names_the_coupling() -> None:
    from fr.settle.instructions import DELIVER_LINE

    assert "settle.conflicts" in DELIVER_LINE and "settle.ci" in DELIVER_LINE
    assert "unrunnable" in DELIVER_LINE


def test_a_cancelled_check_counts_as_running_while_a_gate_is_absent() -> None:
    """Review p1-r2 (spec 2026-11-24-ci-economy R3): with the gate not yet reported, a
    cancelled check is pending, so the gate reads as pending, never as absent."""
    from fr.settle.evaluate import _ci_state

    checks = [{"name": "test (1)", "bucket": "cancel"}]
    state, _, hint, absent = _ci_state(False, checks, ["ci-ok"], ci_none=False,
                                       age=NO_CI_WAIT_SECONDS + 1)  # fmt: skip
    assert (state, hint, absent) == ("pending", "gate-pending", ("ci-ok",))
