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
    committed: float = OLD,
) -> Any:
    return evaluate(
        view if view is not None else _view(),
        GREEN if checks is None else checks,
        gates,
        modes or _modes(),
        ci_none=ci_none,
        head_committed_at=committed,
        now=NOW,
    )


# ---- conflict states (R2) ----------------------------------------------------------


@pytest.mark.parametrize(
    ("mergeable", "merge_state", "state"),
    [
        ("MERGEABLE", "CLEAN", "clean"),
        ("MERGEABLE", "BLOCKED", "clean"),
        ("MERGEABLE", "UNSTABLE", "clean"),
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
    v = _eval(checks=[_check("lint", "fail"), _check("test", "cancel"), _check("ok", "pass")])
    assert v.ci_state == "red"
    assert v.failing_checks == ("lint", "test")
    assert any("lint" in ln and "test" in ln for ln in v.lines)


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
}
CONFLICT_CODE = {"clean": 0, "conflicting": 4, "unknown": 75}
CI_CODE = {"green": 0, "red": 4, "pending": 75, "missing": 4}


@pytest.mark.parametrize("state", sorted(CONFLICT_VIEWS))
@pytest.mark.parametrize("mode", ["off", "report", "fix"])
def test_the_conflict_concern_decides_the_code_only_under_fix(mode: str, state: str) -> None:
    v = _eval(CONFLICT_VIEWS[state], modes=_modes(conflicts=mode, ci="off"))
    assert v.exit_code == (CONFLICT_CODE[state] if mode == "fix" else 0)
    assert v.conflict_state == ("off" if mode == "off" else state)


@pytest.mark.parametrize("state", sorted(CI_CHECKS))
@pytest.mark.parametrize("mode", ["off", "report", "fix"])
def test_the_ci_concern_decides_the_code_only_under_fix(mode: str, state: str) -> None:
    checks, committed = CI_CHECKS[state]
    v = _eval(checks=checks, committed=committed, modes=_modes(conflicts="off", ci=mode))
    assert v.exit_code == (CI_CODE[state] if mode == "fix" else 0)
    assert v.ci_state == ("off" if mode == "off" else state)


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
