"""Matrix kind 4's `Row` (spec 2026-10-06-verification-strategies §B, R7/R10/R13/R14):
`verify` names a strategy or `none`; a row may carry `scenario`, `issues`,
`harnesses` and `walks`; `fr validate artifacts` checks that `verify` resolves.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.model import Row, Walk
from fr.artifacts.structure import validate_matrix
from pydantic import ValidationError

_BASE = {"id": "a", "capability": "c", "acceptance": "x", "status": "ci"}


def _walk(**over: str) -> dict[str, str]:
    return {
        "strategy": "live",
        "harness": "claude-code",
        "model": "opus",
        "outcome": "pass",
        "at": "2026-10-06T12:00:00Z",
        "evidence": "walk.log",
        **over,
    }


def test_verify_takes_any_strategy_name_or_none() -> None:
    assert Row(**_BASE, verify="candidate").verify == "candidate"
    assert Row(**_BASE, verify="none").verify == "none"


def test_verify_refuses_the_v3_spelling_and_non_strings() -> None:
    with pytest.raises(ValidationError, match="post-merge"):
        Row(**_BASE, verify="post-merge")
    with pytest.raises(ValidationError):
        Row(**_BASE, verify=True)  # type: ignore[arg-type]


def test_the_new_fields_default_empty_and_round_trip() -> None:
    row = Row(**_BASE)
    assert (row.scenario, row.issues, row.harnesses, row.walks) == (None, (), (), ())
    row = Row(
        **_BASE,
        scenario="tests/scenarios/x.sh",
        issues=("derio-net/super-fr#1",),
        harnesses=("claude-code", "opencode"),
        walks=(Walk(**_walk()),),
    )
    assert row.walks[0].outcome == "pass"
    assert row.issues == ("derio-net/super-fr#1",)


@pytest.mark.parametrize("bad", ["super-fr#1", "#1", "o/r#x", "o/r 1", "https://x/o/r/issues/1"])
def test_an_issue_must_be_owner_repo_number(bad: str) -> None:
    with pytest.raises(ValidationError, match="owner/repo#n"):
        Row(**_BASE, issues=(bad,))


def test_a_walk_outcome_is_pass_or_fail_and_walks_are_frozen() -> None:
    with pytest.raises(ValidationError):
        Walk(**_walk(outcome="maybe"))
    w = Walk(**_walk())
    with pytest.raises(ValidationError):
        w.outcome = "fail"  # type: ignore[misc]


def _matrix_file(root: Path, verify: str) -> Path:
    path = root / "docs" / "acceptance" / "matrix.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "schema_version: 4\nrows:\n"
        f"  - {{id: a, capability: c, acceptance: x, status: ci, verify: {verify}}}\n"
    )
    return path


@pytest.mark.parametrize("verify", ["live", "candidate", "none"])
def test_validate_accepts_a_resolving_strategy_or_none(tmp_path: Path, verify: str) -> None:
    assert validate_matrix(_matrix_file(tmp_path, verify)) == []


def test_validate_refuses_a_strategy_that_does_not_resolve(tmp_path: Path) -> None:
    problems = validate_matrix(_matrix_file(tmp_path, "bogus"))
    assert len(problems) == 1
    assert "a" in problems[0] and "bogus" in problems[0]


def test_validate_reports_a_bad_issue_and_walk_outcome(tmp_path: Path) -> None:
    path = tmp_path / "matrix.yaml"
    path.write_text(
        "schema_version: 4\nrows:\n"
        "  - id: a\n    capability: c\n    acceptance: x\n    status: ci\n"
        "    issues: [nope]\n"
    )
    assert any("owner/repo#n" in p for p in validate_matrix(path))
    path.write_text(
        "schema_version: 4\nrows:\n"
        "  - id: a\n    capability: c\n    acceptance: x\n    status: ci\n"
        "    walks:\n      - {strategy: live, harness: h, model: m, outcome: maybe,"
        " at: '2026', evidence: e}\n"
    )
    assert any("outcome" in p for p in validate_matrix(path))
