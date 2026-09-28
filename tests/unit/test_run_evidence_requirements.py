"""The requirements-traceability run gates (spec
`2026-09-28-requirements-traceability-design.md` §C, §D, §F, §G; Test Plan
5-8, 12's gate half).

Three DERIVED evidence names, all checked by `fr run resolve` itself and none
ever passed: `requirements` (brainstorm and spec-review), `coverage`
(spec-review) and `requirement-rows` (deliver). A run whose brainstorm carries
no `requirements` evidence predates the gate, and records that instead of
refusing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from fr.run import units
from fr.run.model import load_run_state

from tests.unit.requirements_support import (
    COVERAGE_BLOCK,
    INPUT_TEXT,
    MATRIX_REL,
    REQUIREMENTS_SECTION,
    now,
    row,
    seed_requirements,
    write_input_entry,
    write_matrix,
)
from tests.unit.test_run_cli import _invoke, _repo, _squash, _write_shape

SPEC = "docs/superpowers/specs/2026-09-28-widget-design.md"
SLUG = "2026-09-28-widget"


def _shape(
    *,
    brainstorm: str = "[requirements]",
    spec_review: str = "[review, reviewer, findings, requirements]",
    deliver: str = "[requirement-rows]",
) -> str:
    return f"""
workflow: traced
schema: 1
unit: run
steps:
  - id: brainstorm
    kind: agent
    emits: [spec, journal:spec, acceptance]
    evidence: {brainstorm}
  - id: spec-review
    kind: agent
    needs: [spec]
    emits: [journal:spec, acceptance]
    evidence: {spec_review}
  - id: deliver
    kind: agent
    needs: [spec]
    emits: [acceptance]
    evidence: {deliver}
"""


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _commit(root: Path) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "work", "--no-verify", "--allow-empty")


def _started(tmp_path: Path, **shape: str) -> tuple[Path, Path]:
    """A run `r1` of the `traced` shape with `brainstorm` open."""
    repo = _repo(tmp_path)
    shipped = tmp_path / "shipped"
    _write_shape(shipped, "traced", _shape(**shape))
    out = _invoke(repo, shipped, ["run", "start", "traced", "--branch", "b", "--run-id", "r1"])
    assert out.exit_code == 0, out.output
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    return repo, shipped


def _spec(repo: Path, body: str = REQUIREMENTS_SECTION) -> None:
    path = repo / SPEC
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Widget\n" + body)


def _brainstorm(repo: Path, shipped: Path, *extra: str):
    return _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "brainstorm", "--state", "done",
         "--emitted", f"spec={SPEC}", *extra],
    )  # fmt: skip


def _evidence(repo: Path, step: str) -> dict[str, str]:
    return units.evidence_of(load_run_state(repo, "r1").steps[step], f"step/{step}")


def _record(repo: Path, data: dict[str, object]) -> Path:
    from fr.record.model import RECORD_SCHEMA_VERSION

    step = str(data["step"])
    path = repo / "docs" / "superpowers" / "runs" / "r1.records" / f"{step}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"schema_version": RECORD_SCHEMA_VERSION, "run": "r1", "outcome": "done", **data}
    path.write_text(yaml.safe_dump(body, sort_keys=False))
    return path


def _resolve_record(repo: Path, shipped: Path, step: str, record: Path):
    return _invoke(repo, shipped, ["run", "resolve", "r1", "--step", step, "--record", str(record)])


# --- Task 1: `requirements` on brainstorm ------------------------------------


def test_brainstorm_derives_and_stores_the_requirements_witness(tmp_path: Path) -> None:
    import hashlib

    from fr.requirements import requirements_digest

    repo, shipped = _started(tmp_path)
    _spec(repo)
    seed_requirements(repo, SPEC)

    out = _brainstorm(repo, shipped)

    assert out.exit_code == 0, out.output
    stored = _evidence(repo, "brainstorm")["requirements"]
    digest = requirements_digest((repo / SPEC).read_text())
    assert stored == f"1 requirements:{digest}"
    assert len(digest) == len(hashlib.sha256().hexdigest())


def test_brainstorm_refuses_with_no_input_entry(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _spec(repo)
    write_matrix(repo, [row(SPEC)])

    out = _brainstorm(repo, shipped)

    assert out.exit_code == 2, out.output
    assert "no input entry" in _squash(out.output)
    assert load_run_state(repo, "r1").steps["brainstorm"].state != "done"


def test_brainstorm_refuses_a_spec_with_no_requirements_section(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _spec(repo, "\n## Design\n\nsomething\n")
    write_input_entry(repo, SPEC)
    write_matrix(repo, [])

    out = _brainstorm(repo, shipped)

    assert out.exit_code == 2, out.output
    assert "no `## Requirements` section" in _squash(out.output)


def test_brainstorm_refuses_a_quote_absent_from_the_input(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _spec(repo, REQUIREMENTS_SECTION.replace("build the widget", "paint the widget"))
    write_input_entry(repo, SPEC)
    write_matrix(repo, [row(SPEC)])

    out = _brainstorm(repo, shipped)

    assert out.exit_code == 2, out.output
    assert "does not match any input entry" in _squash(out.output)


def test_brainstorm_refuses_an_unknown_decision(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _spec(repo, REQUIREMENTS_SECTION.replace('input "build the widget"', "decision d-nope"))
    write_input_entry(repo, SPEC)
    write_matrix(repo, [row(SPEC)])

    out = _brainstorm(repo, shipped)

    assert out.exit_code == 2, out.output
    assert "d-nope" in _squash(out.output)


def test_brainstorm_refuses_an_uncited_requirement(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _spec(repo)
    write_input_entry(repo, SPEC)
    write_matrix(repo, [row(SPEC, fragment="R9")])

    out = _brainstorm(repo, shipped)

    assert out.exit_code == 2, out.output
    assert "requirement R1: not cited" in _squash(out.output)


def test_a_caller_supplied_requirements_is_refused_as_derived(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _spec(repo)
    seed_requirements(repo, SPEC)

    out = _brainstorm(repo, shipped, "--evidence", "requirements=x")

    assert out.exit_code == 2, out.output
    assert "not yours to pass" in _squash(out.output)


def test_a_brainstorm_record_finds_its_spec_and_counts_its_staged_rows(tmp_path: Path) -> None:
    """The record form: the spec comes from the record's own `emitted:`, the
    input entry from its `journal:`, and the rows it stages in `acceptance:`
    are what the gate reads — the matrix as the record leaves it (§C)."""
    repo, shipped = _started(tmp_path)
    _spec(repo)
    write_matrix(repo, [])
    _commit(repo)
    record = _record(
        repo,
        {
            "step": "brainstorm",
            "emitted": {"spec": SPEC},
            "journal": [
                {
                    "kind": "discovery",
                    "id": "input-1",
                    "title": "operator input",
                    "body": INPUT_TEXT,
                    "input": True,
                }
            ],
            "acceptance": [
                {
                    "id": "req-r1",
                    "capability": "Widget",
                    "acceptance": "the widget is built",
                    "origin": [f"t:{SPEC}#R1"],
                    "status": "not-implemented",
                }
            ],
        },
    )

    out = _resolve_record(repo, shipped, "brainstorm", record)

    assert out.exit_code == 0, out.output
    assert _evidence(repo, "brainstorm")["requirements"].startswith("1 requirements:")


def test_a_brainstorm_record_without_the_rows_is_refused_and_restored(tmp_path: Path) -> None:
    repo, shipped = _started(tmp_path)
    _spec(repo)
    write_matrix(repo, [])
    _commit(repo)
    record = _record(
        repo,
        {
            "step": "brainstorm",
            "emitted": {"spec": SPEC},
            "journal": [
                {
                    "kind": "discovery",
                    "id": "input-1",
                    "title": "operator input",
                    "body": INPUT_TEXT,
                    "input": True,
                }
            ],
        },
    )

    out = _resolve_record(repo, shipped, "brainstorm", record)

    assert out.exit_code == 2, out.output
    assert "not cited" in _squash(out.output)
    assert load_run_state(repo, "r1").steps["brainstorm"].state != "done"


# --- Task 1: `requirements` re-derived on spec-review -------------------------


def _review_entry(repo: Path, eid: str = "sr-1", body: str = "no findings") -> None:
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path

    append_journal_entry(
        journal_path(repo, "spec", SLUG),
        SLUG,
        JournalEntry(
            kind="review", scope="spec", id=eid, created=now(), title="spec review", body=body
        ),
    )


def _at_spec_review(tmp_path: Path, **shape: str) -> tuple[Path, Path]:
    repo, shipped = _started(tmp_path, **shape)
    _spec(repo)
    seed_requirements(repo, SPEC)
    assert _brainstorm(repo, shipped).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    return repo, shipped


def _spec_review(repo: Path, shipped: Path, *extra: str):
    return _invoke(
        repo,
        shipped,
        ["run", "resolve", "r1", "--step", "spec-review", "--state", "done",
         "--evidence", "review=sr-1", "--evidence", "reviewer=rv-1", *extra],
    )  # fmt: skip


def test_spec_review_re_derives_requirements_after_a_spec_edit(tmp_path: Path) -> None:
    repo, shipped = _at_spec_review(tmp_path)
    before = _evidence(repo, "brainstorm")["requirements"]
    # The review's fix edits the spec: a second requirement and its row.
    (repo / SPEC).write_text(
        (repo / SPEC).read_text().rstrip("\n")
        + '\n| R2 | It counts. | input "counts from 1–20" |\n'
    )
    write_matrix(repo, [row(SPEC), row(SPEC, rid="req-r2", fragment="R2")])
    _review_entry(repo)

    out = _spec_review(repo, shipped)

    assert out.exit_code == 0, out.output
    after = _evidence(repo, "spec-review")["requirements"]
    assert after.startswith("2 requirements:")
    assert after.split(":", 1)[1] != before.split(":", 1)[1]


def test_spec_review_refuses_a_requirement_added_without_its_row(tmp_path: Path) -> None:
    repo, shipped = _at_spec_review(tmp_path)
    (repo / SPEC).write_text(
        (repo / SPEC).read_text().rstrip("\n")
        + '\n| R2 | It counts. | input "counts from 1–20" |\n'
    )
    _review_entry(repo)

    out = _spec_review(repo, shipped)

    assert out.exit_code == 2, out.output
    assert "requirement R2: not cited" in _squash(out.output)


def test_a_spec_review_record_adding_a_requirement_and_its_row_applies(tmp_path: Path) -> None:
    repo, shipped = _at_spec_review(tmp_path)
    (repo / SPEC).write_text(
        (repo / SPEC).read_text().rstrip("\n")
        + '\n| R2 | It counts. | input "counts from 1–20" |\n'
    )
    _commit(repo)
    record = _record(
        repo,
        {
            "step": "spec-review",
            "journal": [{"kind": "review", "id": "sr-1", "title": "spec review", "body": "b"}],
            "acceptance": [
                {
                    "id": "req-r2",
                    "capability": "Widget",
                    "acceptance": "it counts",
                    "origin": [f"t:{SPEC}#R2"],
                    "status": "not-implemented",
                }
            ],
            "evidence": {"review": "sr-1", "reviewer": "rv-1"},
        },
    )

    out = _resolve_record(repo, shipped, "spec-review", record)

    assert out.exit_code == 0, out.output
    assert _evidence(repo, "spec-review")["requirements"].startswith("2 requirements:")
    assert "req-r2" in (repo / MATRIX_REL).read_text()


__all__ = ["COVERAGE_BLOCK"]
