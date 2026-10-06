"""`fr plan self-review` sizes phases to the spec's asks (spec
2026-09-28-phase-sizing-design.md §B/§C, Test Plan items 2–4).

Every repo is a `tmp_path` sandbox; nothing here touches the checkout.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from fr.cli import app
from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    archived_journal_path,
    journal_path,
)
from fr.parser import Plan
from fr.parser import parse as parse_plan
from fr.plan_ops import PhaseSpec, ReviewIssue, _phase_sizing_issues, create
from fr.version_floor import CEILING_VERSION
from typer.testing import CliRunner

runner = CliRunner()

SPEC_REL = "docs/superpowers/specs/2026-09-28-toy-design.md"
SPEC_SLUG = "2026-09-28-toy"
PLAN = "2026-09-28-toy"

REQUIREMENTS = """\
## Requirements

R1. First ask.
R2. Second ask.
R3. Third ask.
"""

LEGACY_REQUIREMENTS = """\
## Requirements

| id | requirement | source |
|---|---|---|
| R1 | First ask. | decision d1 |
| R2 | Second ask. | decision d2 |
| R3 | Third ask. | decision d3 |
"""
"""A spec written before 5.0.0: the three-column table still sizes a plan."""


def _row(rid: str, *reqs: str, spec: str = SPEC_REL) -> str:
    origins = "".join(f"    - own:{spec}#{r}\n" for r in reqs) or "    - own:docs/x.md\n"
    return (
        f"  - id: {rid}\n    capability: Cap\n    acceptance: A\n    origin:\n{origins}"
        "    levels: {}\n    status: not-implemented\n    notes: ''\n"
    )


MATRIX = (
    "org: derio-net\nrepo: own\nrows:\n"
    + _row("row-r1", "R1")
    + _row("row-r2", "R2")
    + _row("row-r1b", "R1")
    + _row("row-none")
)


def _repo(tmp_path: Path, *, matrix: bool = True, requirements: str | None = REQUIREMENTS) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir()
    if matrix:
        (tmp_path / "docs" / "acceptance").mkdir(parents=True)
        (tmp_path / "docs" / "acceptance" / "matrix.yaml").write_text(MATRIX)
    body = "# Toy\n\n"
    if requirements is not None:
        body += requirements + "\n"
    body += "## Test Plan\n\n1. walk\n\n"
    body += "## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|--|--|--|--|\n"
    (tmp_path / SPEC_REL).write_text(body)
    return tmp_path


@dataclass(frozen=True)
class P:
    rows: tuple[str, ...] = ()
    tag: str = "agentic"
    skeleton: bool = False
    steps: int = 1


def _plan(repo: Path, *phases: P, spec: str = SPEC_REL) -> Plan:
    specs = []
    for i, p in enumerate(phases, start=1):
        steps = [{"id": f"P{i}.T1.S{s}", "text": "do it"} for s in range(1, p.steps + 1)]
        specs.append(
            PhaseSpec(
                number=i,
                title=f"Phase {i}",
                tag=p.tag,  # type: ignore[arg-type]
                acceptance=p.rows,
                skeleton=p.skeleton,
                tier="standard" if p.tag == "agentic" else None,
                files=("x/**",) if p.tag == "agentic" else (),
                tasks=({"number": 1, "title": "t", "steps": steps},),
            )
        )
    plan = create(
        repo_root=repo,
        slug=PLAN,
        spec=spec,
        target_repo="derio-net/own",
        fr_version=f">=4.20.0,<{CEILING_VERSION}",
        phases=specs,
        prose="# toy\n",
    )
    return parse_plan(plan.dir)


def _decide(repo: Path, n: int, title: str, *, archived: bool = False, k: int = 0) -> None:
    path = (archived_journal_path if archived else journal_path)(repo, "spec", SPEC_SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    append_journal_entry(
        path,
        SPEC_SLUG,
        JournalEntry(
            kind="decision",
            scope="spec",
            id=f"phase-split-{PLAN}-p{n}" + (f"-{k}" if k else ""),
            created="2026-09-28T00:00:00+00:00",
            title=title,
        ),
    )


def _errors(issues: list[ReviewIssue]) -> list[str]:
    return [i.message for i in issues if i.severity == "error"]


def _warns(issues: list[ReviewIssue]) -> list[str]:
    return [i.message for i in issues if i.severity == "warn"]


# ── the cut-off: silent unless the spec's Requirements list parses ───────────


def test_silent_without_a_requirements_section(tmp_path: Path) -> None:
    repo = _repo(tmp_path, requirements=None)
    plan = _plan(repo, P(skeleton=True), P(("row-r1",)))
    assert _phase_sizing_issues(plan) == []


def test_silent_with_a_legacy_prose_requirements_section(tmp_path: Path) -> None:
    repo = _repo(tmp_path, requirements="## Requirements\n\n- It must be fast.\n- And cheap.\n")
    plan = _plan(repo, P(skeleton=True), P(("row-r1",)))
    assert _phase_sizing_issues(plan) == []


def test_silent_with_a_cross_repo_spec(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = _plan(repo, P(skeleton=True), P(("row-r1",)), spec="other/repo:docs/specs/x-design.md")
    assert _phase_sizing_issues(plan) == []


def test_silent_when_the_spec_file_does_not_exist(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = _plan(repo, P(skeleton=True), P(("row-r1",)))
    (repo / SPEC_REL).unlink()
    assert _phase_sizing_issues(plan) == []


def test_an_unparseable_requirements_list_gives_one_not_checked_warning(tmp_path: Path) -> None:
    broken = REQUIREMENTS.replace("R3. Third", "R2. Third")
    repo = _repo(tmp_path, requirements=broken)
    plan = _plan(repo, P(skeleton=True), P(("row-r1",)))
    issues = _phase_sizing_issues(plan)
    assert len(issues) == 1
    assert issues[0].severity == "warn"
    assert "Requirements list does not parse (" in issues[0].message
    assert "R2" in issues[0].message
    assert "sizing was not checked" in issues[0].message


def test_a_legacy_requirements_table_still_sizes_the_plan(tmp_path: Path) -> None:
    legacy = _repo(tmp_path / "legacy", requirements=LEGACY_REQUIREMENTS)
    plain = _repo(tmp_path / "plain")
    shape = (P(skeleton=True), P(("row-r1",)))
    assert [i.message for i in _phase_sizing_issues(_plan(legacy, *shape))] == [
        i.message for i in _phase_sizing_issues(_plan(plain, *shape))
    ]


# ── the floor and the ceiling ────────────────────────────────────────────────


def test_one_agentic_phase_with_an_own_ask_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = _plan(repo, P(("row-r1", "row-r2")))
    assert _phase_sizing_issues(plan) == []


def test_one_agentic_phase_citing_no_requirement_fails_the_floor(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = _plan(repo, P(("row-none",)))
    errors = _errors(_phase_sizing_issues(plan))
    assert len(errors) == 1
    assert "phase 1 serves no ask" in errors[0]
    assert "none of its acceptance rows cites" in errors[0]
    assert SPEC_REL in errors[0]


def _745_shape(repo: Path) -> Plan:
    """#745: a skeleton with no rows, two ask phases, a one-step screenshots phase."""
    return _plan(
        repo,
        P(skeleton=True),
        P(("row-r1",)),
        P(("row-r2",)),
        P(tag="manual", steps=1),
    )


def test_the_745_shape_fails_floor_and_ceiling_and_warns_on_the_manual_step(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    issues = _phase_sizing_issues(_745_shape(repo))
    errors = _errors(issues)
    assert any(e.startswith("phase 1 serves no ask") for e in errors)
    assert any(e.startswith("phase 2 is agentic phase #2") for e in errors)
    assert any(e.startswith("phase 3 is agentic phase #3") for e in errors)
    assert len(errors) == 3
    warns = _warns(issues)
    assert len(warns) == 1
    assert warns[0].startswith("phase 4 is a single operator step")
    assert "verify: live" in warns[0]


def test_a_multi_step_trailing_manual_phase_is_not_warned(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = _plan(repo, P(("row-r1",)), P(tag="manual", steps=2))
    assert _phase_sizing_issues(plan) == []


def _folded(repo: Path) -> Plan:
    return _plan(repo, P(("row-r1",), skeleton=True), P(("row-r2",)))


def test_the_folded_shape_with_an_ask_split_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _decide(repo, 2, "ask: the second ask, reviewable alone")
    assert _phase_sizing_issues(_folded(repo)) == []


def test_the_folded_shape_without_the_split_decision_hits_the_ceiling(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    errors = _errors(_phase_sizing_issues(_folded(repo)))
    assert len(errors) == 1
    assert errors[0].startswith("phase 2 is agentic phase #2")
    assert "needs a recorded split reason" in errors[0]
    assert f"--id phase-split-{PLAN}-p2" in errors[0]
    assert f"--slug {SPEC_SLUG}" in errors[0]
    for token in ("ask:", "tier:", "risk-first:", "review-size:"):
        assert token in errors[0]


def test_a_floor_message_names_the_three_waivers_and_never_ask(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = _plan(repo, P(("row-r1",), skeleton=True), P(("row-r1b",)))
    _decide(repo, 2, "ask: claims its own ask")
    errors = _errors(_phase_sizing_issues(plan))
    assert len(errors) == 2  # both share R1: neither owns it
    for e in errors:
        assert "serves no ask of its own" in e
        for token in ("tier:", "risk-first:", "review-size:"):
            assert token in e
        assert "ask:" not in e
    assert "also served by phase(s) 2" in errors[0]


def test_the_shared_ask_tier_pair_passes(tmp_path: Path) -> None:
    """Review s2: R1 split by tier — p1 keeps R1, p2 passes by its waiver."""
    repo = _repo(tmp_path)
    plan = _plan(repo, P(("row-r1",), skeleton=True), P(("row-r1b",)))
    _decide(repo, 2, "tier: the parser needs the hard tier")
    assert _phase_sizing_issues(plan) == []


def test_an_ask_split_without_an_own_ask_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = _plan(repo, P(("row-r1",), skeleton=True), P(("row-none",)))
    _decide(repo, 2, "ask: it is its own ask")
    errors = _errors(_phase_sizing_issues(plan))
    assert len(errors) == 1
    assert errors[0].startswith("phase 2 serves no ask")


def test_a_waiver_on_the_first_phase_passes_it(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = _plan(repo, P(("row-none",)))
    _decide(repo, 1, "risk-first: the migration lands alone")
    assert _phase_sizing_issues(plan) == []


def test_a_malformed_split_prefix_is_an_error(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _decide(repo, 2, "because: I said so")
    errors = _errors(_phase_sizing_issues(_folded(repo)))
    assert len(errors) == 1
    assert f"phase-split-{PLAN}-p2" in errors[0]
    assert "no reason token" in errors[0]


def test_an_archived_spec_journal_is_read(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _decide(repo, 2, "ask: archived but still recorded", archived=True)
    assert _phase_sizing_issues(_folded(repo)) == []


def test_no_matrix_keeps_the_ceiling_and_warns_the_ask_is_unverifiable(tmp_path: Path) -> None:
    repo = _repo(tmp_path, matrix=False)
    plan = _plan(repo, P(skeleton=True), P(), P())
    _decide(repo, 2, "ask: cannot be checked")
    issues = _phase_sizing_issues(plan)
    errors = _errors(issues)
    assert len(errors) == 1  # the floor is skipped; phase 3's ceiling stands
    assert errors[0].startswith("phase 3 is agentic phase #3")
    warns = _warns(issues)
    assert len(warns) == 1
    assert "unverifiable without docs/acceptance/matrix.yaml" in warns[0]


# ── CLI (Test Plan item 4) ──────────────────────────────────────────────────


def test_cli_self_review_fails_the_745_shape(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = _745_shape(repo)
    result = runner.invoke(app, ["plan", "self-review", str(plan.dir)])
    assert result.exit_code != 0, result.output
    assert "serves no ask" in result.output


def test_cli_self_review_passes_the_folded_shape(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _decide(repo, 2, "ask: the second ask")
    plan = _folded(repo)
    result = runner.invoke(app, ["plan", "self-review", str(plan.dir)])
    assert result.exit_code == 0, result.output


# ── review fixes r1, r3, r4, r6, r8 ─────────────────────────────────────────


def test_r1_the_floor_fix_names_the_next_free_id_and_running_it_clears_the_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`fr journal add` refuses a taken id, so the suggested command must name
    one past the decision that already exists — and running it must work."""
    repo = _repo(tmp_path)
    plan = _plan(repo, P(("row-r1",), skeleton=True), P(("row-none",)))
    _decide(repo, 2, "ask: it is its own ask")
    errors = _errors(_phase_sizing_issues(plan))
    assert len(errors) == 1
    m = re.search(r"`(fr journal add [^`]*)`", errors[0])
    assert m is not None, errors[0]
    assert f"--id phase-split-{PLAN}-p2-1 " in m.group(1)
    argv = shlex.split(m.group(1).replace("<reason>: …", "review-size: too large to review"))
    monkeypatch.chdir(repo)
    added = runner.invoke(app, argv[1:])
    assert added.exit_code == 0, added.output
    assert _phase_sizing_issues(parse_plan(plan.dir)) == []


def test_r1_the_malformed_error_names_the_next_free_id(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _decide(repo, 2, "because: I said so")
    errors = _errors(_phase_sizing_issues(_folded(repo)))
    assert len(errors) == 1
    assert f"--id phase-split-{PLAN}-p2-1 " in errors[0]


def test_r1_a_malformed_decision_superseded_by_a_valid_one_no_longer_errors(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    _decide(repo, 2, "because: I said so")
    _decide(repo, 2, "ask: the second ask", k=1)
    assert _phase_sizing_issues(_folded(repo)) == []


def test_r3_an_unloadable_matrix_warns_instead_of_reading_as_absent(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "docs" / "acceptance" / "matrix.yaml").write_text("rows: [unclosed\n")
    plan = _plan(repo, P(("row-r1",), skeleton=True), P(("row-none",)))
    _decide(repo, 2, "ask: cannot be checked")
    issues = _phase_sizing_issues(plan)
    assert _errors(issues) == []
    warns = _warns(issues)
    assert len(warns) == 1
    assert warns[0].startswith("acceptance matrix unreadable (")
    assert warns[0].endswith("ask floor not checked.")
    assert "without docs/acceptance/matrix.yaml" not in warns[0]


def test_r3_a_matrix_whose_repo_identity_cannot_be_resolved_warns(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    matrix = repo / "docs" / "acceptance" / "matrix.yaml"
    matrix.write_text(matrix.read_text().replace("org: derio-net\nrepo: own\n", ""))
    plan = _plan(repo, P(("row-r1",)))
    warns = _warns(_phase_sizing_issues(plan))
    assert len(warns) == 1
    assert warns[0].startswith("acceptance matrix unreadable (")
    assert "cannot resolve repo identity" in warns[0]


def test_r6_a_decision_naming_no_agentic_phase_is_an_orphan_warning(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = _plan(repo, P(("row-r1",), skeleton=True), P(("row-r2",)), P(tag="manual", steps=2))
    _decide(repo, 2, "ask: the second ask")
    _decide(repo, 3, "tier: a manual phase")
    _decide(repo, 7, "because: malformed and orphaned")
    issues = _phase_sizing_issues(plan)
    assert _errors(issues) == []
    warns = _warns(issues)
    assert len(warns) == 2
    assert all("names no agentic phase; it waives nothing" in w for w in warns)
    assert any(f"phase-split-{PLAN}-p3" in w for w in warns)
    assert any(f"phase-split-{PLAN}-p7" in w for w in warns)


def test_r8_an_ask_phase_sharing_its_only_ask_with_a_waived_phase_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    plan = _plan(repo, P(("row-r1",), skeleton=True), P(("row-r1b",)))
    _decide(repo, 1, "tier: the parser needs the hard tier")
    _decide(repo, 2, "ask: claims R1")
    errors = _errors(_phase_sizing_issues(plan))
    assert len(errors) == 1
    assert errors[0].startswith("phase 2 serves no ask of its own")
    assert "also served by phase(s) 1" in errors[0]
