"""fr refuses a `tests` log that marks itself advisory (spec
2026-11-19-local-suite-cost R7, §3.E): at `deliver` and at a phase unit, a log
with the line `fr-scope: advisory — not deliver evidence` on a line of its own is
not the whole suite. A log that only quotes the string inside other output is
accepted, and a phase log refused here never becomes a witness, so
`tests: reuse` cannot carry it into `deliver`."""

from __future__ import annotations

from pathlib import Path

from fr.run.ci_evidence import ADVISORY_LINE
from fr.run.model import load_run_state

from tests.unit.test_run_cli import _invoke, _squash
from tests.unit.test_run_evidence_separate_context import (
    _at_deliver,
    _deliver,
    _later,
    _review,
    _soon,
)
from tests.unit.test_run_suite_reuse import _CODE, _at_code, _code_evidence
from tests.unit.transcript_sessions import ran_at, write_session

ADVISORY_LOG = f"..........\n{ADVISORY_LINE}\n10 passed in 1.00s\n"


def _assert_refused_as_advisory(output: str) -> None:
    out = _squash(output)
    assert ADVISORY_LINE in out
    assert '-m ""' in out
    assert "tests: ci" in out


def test_deliver_refuses_an_advisory_log(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    write_session(root, session_id="s-d")
    repo, shipped, opened = _at_deliver(tmp_path, root=root)
    (repo / "c1.log").write_text("  " + ADVISORY_LOG.replace("\n", "  \n", 2))
    ran_at(root, _later(opened), session_id="s-d", until=_soon(), log=repo / "c1.log")

    result = _deliver(repo, shipped, root, "s-d", "tests=c1.log")

    assert result.exit_code == 2, result.output
    _assert_refused_as_advisory(result.output)
    assert load_run_state(repo, "r1").steps["deliver"].state == "running"


def test_deliver_accepts_a_log_that_only_quotes_the_line(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    write_session(root, session_id="s-d")
    repo, shipped, opened = _at_deliver(tmp_path, root=root)
    (repo / "c1.log").write_text(f"PASSED test_x - asserted {ADVISORY_LINE!r}\n291 passed\n")
    ran_at(root, _later(opened), session_id="s-d", until=_soon(), log=repo / "c1.log")

    result = _deliver(repo, shipped, root, "s-d", "tests=c1.log")

    assert result.exit_code == 0, result.output


def test_a_phase_unit_refuses_an_advisory_log(tmp_path: Path) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    log = tmp_path / "suite.log"
    log.write_text(ADVISORY_LOG)

    result = _invoke(repo, shipped, [*_CODE, "--agent", "impl-1", "--evidence", f"tests={log}"])

    assert result.exit_code == 2, result.output
    _assert_refused_as_advisory(result.output)
    assert "tests" not in _code_evidence(repo)


def test_a_phase_log_refused_as_advisory_leaves_nothing_for_reuse(tmp_path: Path) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    log = tmp_path / "suite.log"
    log.write_text(ADVISORY_LOG)
    refused = _invoke(repo, shipped, [*_CODE, "--agent", "impl-1", "--evidence", f"tests={log}"])
    assert refused.exit_code == 2, refused.output
    resolved = _invoke(repo, shipped, [*_CODE, "--agent", "impl-1"])
    assert resolved.exit_code == 0, resolved.output
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    review = _review(repo, shipped, None, "s-c", "review=rev-p1", "reviewer=r-9")
    assert review.exit_code == 0, review.output
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0

    result = _deliver(repo, shipped, None, "s-c", "tests=reuse")

    assert result.exit_code == 2, result.output
    assert "no phase unit recorded a suite log" in _squash(result.output)
