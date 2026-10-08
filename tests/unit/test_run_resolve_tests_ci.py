"""`tests: ci` in `fr run resolve` — spec 2026-10-07-cloud-triage R22, §I.

The token is recognised BEFORE the phase-log branch (which would read `ci` as
a log path). `fr.run.ci_evidence.verify_ci` is replaced here — its own rules
are `test_run_ci_evidence.py`'s — so these tests pin only the routing: a `done`
resolve records the witness, a pending gate exits 75 with the cursor
byte-identical, a refusal exits 2, a `failed` resolve records the bare claim
without asking the forge, and `tests: reuse` accepts a ci witness afterwards.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fr.record.model import RECORD_SCHEMA_VERSION
from fr.run import ci_evidence
from fr.run.ci_evidence import CI_PENDING_EXIT, CiEvidenceRefused, CiPending
from fr.run.code_tree import code_tree

from tests.unit.test_run_cli import _invoke, _squash
from tests.unit.test_run_evidence_separate_context import _deliver, _review
from tests.unit.test_run_suite_reuse import (
    _CODE,
    _FAILED_CODE,
    _at_code,
    _code_evidence,
    _deliver_evidence,
)

CI_SHA = "a" * 40
BASE_SHA = "b" * 40


def _witness(repo: Path) -> str:
    return f"ci:{CI_SHA}+{BASE_SHA};tree={code_tree(repo)}"


@pytest.fixture
def green(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """`verify_ci` answering a green witness for HEAD's tree; records its calls."""
    calls: list[Path] = []

    def fake(repo_root: Path, client: object = None) -> str:
        calls.append(repo_root)
        return _witness(repo_root)

    monkeypatch.setattr(ci_evidence, "verify_ci", fake)
    return calls


def _raising(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    def fake(repo_root: Path, client: object = None) -> str:
        raise exc

    monkeypatch.setattr(ci_evidence, "verify_ci", fake)


def _cursor(repo: Path) -> bytes:
    return (repo / "docs" / "superpowers" / "runs" / "r1.yaml").read_bytes()


def test_a_done_phase_records_the_ci_witness(tmp_path: Path, green: list[Path]) -> None:
    repo, shipped, _ = _at_code(tmp_path)

    result = _invoke(repo, shipped, [*_CODE, "--agent", "impl-1", "--evidence", "tests=ci"])

    assert result.exit_code == 0, result.output
    assert _code_evidence(repo)["tests"] == _witness(repo)
    assert len(green) == 1


def test_a_phase_record_may_say_tests_ci(tmp_path: Path, green: list[Path]) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    record = repo / "docs" / "superpowers" / "runs" / "r1.records" / "code__phase-1.yaml"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(
        json.dumps(
            {
                "schema_version": RECORD_SCHEMA_VERSION,
                "run": "r1",
                "step": "code",
                "item": "phase/1",
                "outcome": "done",
                "evidence": {"tests": "ci"},
            }
        )
    )
    argv = ["run", "resolve", "r1", "--step", "code", "--item", "phase/1"]

    result = _invoke(repo, shipped, [*argv, "--record", str(record), "--no-advance"])

    assert result.exit_code == 0, result.output
    assert _code_evidence(repo)["tests"] == _witness(repo)


def _to_deliver(repo: Path, shipped: Path) -> None:
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    review = _review(repo, shipped, None, "s-c", "review=rev-p1", "reviewer=r-9")
    assert review.exit_code == 0, review.output
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0


def test_deliver_may_say_tests_ci(tmp_path: Path, green: list[Path]) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    assert _invoke(repo, shipped, [*_CODE, "--agent", "impl-1"]).exit_code == 0
    _to_deliver(repo, shipped)

    result = _deliver(repo, shipped, None, "s-c", "tests=ci")

    assert result.exit_code == 0, result.output
    assert _deliver_evidence(repo)["tests"] == _witness(repo)


def test_reuse_accepts_a_ci_witness_on_an_unchanged_tree(tmp_path: Path, green: list[Path]) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    code = [*_CODE, "--agent", "impl-1", "--evidence", "tests=ci"]
    assert _invoke(repo, shipped, code).exit_code == 0
    witness = _code_evidence(repo)["tests"]
    _to_deliver(repo, shipped)

    result = _deliver(repo, shipped, None, "s-c", "tests=reuse")

    assert result.exit_code == 0, result.output
    assert _deliver_evidence(repo)["tests"] == f"reused:phase/1/code:{witness}"


def test_a_pending_gate_exits_75_and_leaves_the_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    _raising(monkeypatch, CiPending(CI_SHA))
    before = _cursor(repo)

    result = _invoke(repo, shipped, [*_CODE, "--agent", "impl-1", "--evidence", "tests=ci"])

    assert result.exit_code == CI_PENDING_EXIT == 75, result.output
    assert "resolve again when CI finishes" in _squash(result.output)
    assert _cursor(repo) == before


def test_a_pending_gate_through_a_record_restores_every_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    _raising(monkeypatch, CiPending(CI_SHA))
    record = repo / "docs" / "superpowers" / "runs" / "r1.records" / "code__phase-1.yaml"
    record.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "run": "r1",
        "step": "code",
        "item": "phase/1",
        "outcome": "done",
        "ticks": [],
        "evidence": {"tests": "ci"},
    }
    record.write_text(json.dumps(body))
    before = _cursor(repo)
    argv = ["run", "resolve", "r1", "--step", "code", "--item", "phase/1"]

    result = _invoke(repo, shipped, [*argv, "--record", str(record), "--no-advance"])

    assert result.exit_code == 75, result.output
    assert _cursor(repo) == before
    assert json.loads(record.read_text()) == body


def test_a_refused_ci_claim_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    _raising(monkeypatch, CiEvidenceRefused("tests: ci — gate check ci-ok failure (u)"))
    before = _cursor(repo)

    result = _invoke(repo, shipped, [*_CODE, "--agent", "impl-1", "--evidence", "tests=ci"])

    assert result.exit_code == 2, result.output
    assert "ci-ok failure" in _squash(result.output)
    assert _cursor(repo) == before


def test_a_failed_resolve_records_the_bare_claim_without_the_forge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    _raising(monkeypatch, AssertionError("a failed resolve must not read CI"))

    result = _invoke(repo, shipped, [*_FAILED_CODE, "--agent", "impl-1", "--evidence", "tests=ci"])

    assert result.exit_code == 0, result.output
    assert _code_evidence(repo)["tests"] == "ci"


def test_a_local_log_is_still_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, shipped, _ = _at_code(tmp_path)
    _raising(monkeypatch, AssertionError("a log never reads CI"))
    log = tmp_path / "suite.log"
    log.write_text("4051 passed\n")

    result = _invoke(
        repo, shipped, [*_FAILED_CODE, "--agent", "impl-1", "--evidence", f"tests={log}"]
    )

    assert result.exit_code == 0, result.output
    assert _code_evidence(repo)["tests"].startswith("suite.log@")
