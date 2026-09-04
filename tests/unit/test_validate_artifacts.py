"""`fr validate artifacts` — every version ships a structure validator (spec §3.F).

Four properties, one per shape of failure the spec names:

1. a well-formed artifact of **every registered kind** passes;
2. a missing required field fails **naming the file and the field** — a
   validator that says "invalid" without saying where is a validator nobody
   uses;
3. an unreadable/unknown stamp fails, and a stamp **newer than this fr** fails
   closed with an upgrade message (spec §2 non-goals: no downgrades);
4. a **duplicated section block** in a spec is caught.

(4) is not hypothetical. Commit 7ece5a9 on this branch spliced a spec with
``end = text.index("## Implementation Plans")``, which matched an *inline
mention* of that heading sitting BEFORE the section being replaced; with
``end < start`` the tail was re-appended, duplicating ~640 lines and fusing a
heading mid-sentence. Nothing caught it — no test validates spec structure and
`fr acceptance check` only verifies that rows *cite* a spec. The two tests at
the bottom of this file reproduce that exact splice and assert both signals
fire.

The kind coverage is derived from `ARTIFACT_KINDS`, never from a hand-written
list: a sixth kind added to the registry with no validator must fail here, not
pass silently.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.artifacts.registry import ARTIFACT_KINDS, artifact_kind
from fr.artifacts.validate import validate_artifact, validate_repo
from fr.cli import app
from typer.testing import CliRunner

runner_cli = CliRunner()

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- fixtures: one well-formed artifact per kind --------------------------


def _w(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


PLAN_SLUG = "2019-03-04-thermosiphon-rebuild"

GOOD_META = """schema_version: 2
plan: 2019-03-04-thermosiphon-rebuild
spec: docs/superpowers/specs/2019-03-04-thermosiphon-rebuild-design.md
target_repo: derio-net/super-fr
created: '2019-03-04'
"""

GOOD_PHASE = """schema_version: 2
phase:
  number: 1
  title: Phase 1
  tag: agentic
  depends_on: []
  tracking_issue: null
tasks:
  - number: 1
    title: Task
    steps:
      - id: P1.T1.S1
        text: Do the thing
state:
  steps:
    P1.T1.S1:
      state: " "
      ticked_at: null
      note: null
  completion:
    at: null
    note: null
    observed_prs: []
"""

GOOD_JOURNAL = """# Journal

<!-- fr:journal kind=discovery scope=plan id=d-one created=2019-03-04T00:00:00 phase=1 -->
### d-one · discovery · A thing I found (phase 1)

Body.
"""

GOOD_RUN = """run: 2019-03-04-feat-widget
workflow: fr-goal@1
branch: feat/widget
started: '2019-03-04T00:00:00'
cursor: implement
steps:
  brainstorm:
    state: done
  implement:
    state: running
"""

GOOD_MATRIX = """org: derio-net
repo: super-fr
rows:
  - id: a-row
    capability: A capability
    acceptance: It works.
    origin:
      - super-fr:docs/superpowers/specs/2019-03-04-thermosiphon-rebuild-design.md
    levels:
      unit:
        - super-fr:tests/unit/test_thing.py
    status: ci
    notes: ''
"""

GOOD_SPEC = """# Thermosiphon rebuild

## 1. Problem

It leaks.

## 2. Goal

It does not leak.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2019-03-04-thermosiphon-rebuild | `derio-net/super-fr` | `2019-03-04-thermosiphon-rebuild` | — |
"""


def seed_good_repo(root: Path) -> dict[str, Path]:
    """One structurally valid live artifact per registered kind."""
    plan_dir = root / "docs" / "superpowers" / "plans" / PLAN_SLUG
    meta = _w(root, f"docs/superpowers/plans/{PLAN_SLUG}/_meta.yaml", GOOD_META)
    _w(root, f"docs/superpowers/plans/{PLAN_SLUG}/_prose.md", "# Prose\n")
    _w(root, f"docs/superpowers/plans/{PLAN_SLUG}/01.yaml", GOOD_PHASE)
    assert plan_dir.is_dir()
    return {
        "plan": meta,
        "journal": _w(root, f"docs/superpowers/journals/plans/{PLAN_SLUG}.md", GOOD_JOURNAL),
        "run": _w(root, "docs/superpowers/runs/2019-03-04-feat-widget.yaml", GOOD_RUN),
        "matrix": _w(root, "docs/acceptance/matrix.yaml", GOOD_MATRIX),
        "spec": _w(root, f"docs/superpowers/specs/{PLAN_SLUG}-design.md", GOOD_SPEC),
    }


# --- 1. a well-formed artifact of every kind passes -----------------------


def test_every_registered_kind_has_a_structure_validator() -> None:
    for name, kind in ARTIFACT_KINDS.items():
        assert callable(kind.validate), f"{name}: no structure validator (spec 3.F)"


def test_a_well_formed_artifact_of_every_kind_passes(tmp_path: Path) -> None:
    seeded = seed_good_repo(tmp_path)
    assert set(seeded) == set(ARTIFACT_KINDS), "the fixture must cover every registered kind"
    report = validate_repo(tmp_path)
    assert report.issues == (), [str(i) for i in report.issues]
    assert report.ok
    assert report.checked == len(ARTIFACT_KINDS)


def test_validation_never_writes(tmp_path: Path) -> None:
    """It runs over files an operator has open; it may not touch one."""
    seeded = seed_good_repo(tmp_path)
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in seeded.values()}
    validate_repo(tmp_path)
    for path, (data, mtime) in before.items():
        assert path.read_bytes() == data
        assert path.stat().st_mtime_ns == mtime


def test_the_archive_is_never_validated(tmp_path: Path) -> None:
    """`implemented/` records what shipped; a validator that failed on it would
    make CI red over history nobody may rewrite (spec §2 non-goals)."""
    seed_good_repo(tmp_path)
    _w(tmp_path, "docs/superpowers/implemented/specs/2018-01-01-old-design.md", "no title here\n")
    _w(
        tmp_path,
        "docs/superpowers/implemented/plans/2018-01-01-old/_meta.yaml",
        "schema_version: 2\n",
    )
    assert validate_repo(tmp_path).ok


# --- 2. a missing required field names the file AND the field -------------

MISSING_FIELD_CASES = {
    "plan": (
        f"docs/superpowers/plans/{PLAN_SLUG}/_meta.yaml",
        GOOD_META.replace("target_repo: derio-net/super-fr\n", ""),
        "target_repo",
    ),
    "journal": (
        f"docs/superpowers/journals/plans/{PLAN_SLUG}.md",
        GOOD_JOURNAL.replace("kind=discovery ", ""),
        "kind",
    ),
    "run": (
        "docs/superpowers/runs/2019-03-04-feat-widget.yaml",
        GOOD_RUN.replace("cursor: implement\n", ""),
        "cursor",
    ),
    "matrix": (
        "docs/acceptance/matrix.yaml",
        GOOD_MATRIX.replace("    status: ci\n", ""),
        "status",
    ),
    "spec": (
        f"docs/superpowers/specs/{PLAN_SLUG}-design.md",
        GOOD_SPEC.replace("# Thermosiphon rebuild\n", "Thermosiphon rebuild\n"),
        "title",
    ),
}


def test_the_missing_field_cases_cover_every_kind() -> None:
    assert set(MISSING_FIELD_CASES) == set(ARTIFACT_KINDS)


@pytest.mark.parametrize("kind_name", sorted(MISSING_FIELD_CASES))
def test_a_missing_required_field_fails_naming_file_and_field(
    tmp_path: Path, kind_name: str
) -> None:
    seed_good_repo(tmp_path)
    rel, corrupted, field = MISSING_FIELD_CASES[kind_name]
    _w(tmp_path, rel, corrupted)

    report = validate_repo(tmp_path)
    assert not report.ok
    mine = [i for i in report.issues if i.kind == kind_name]
    assert mine, f"{kind_name}: no issue reported for a missing `{field}`"
    rendered = "\n".join(str(i) for i in mine)
    assert Path(rel).name in rendered, f"the file is not named: {rendered}"
    assert field in rendered, f"the field is not named: {rendered}"


def test_only_the_corrupt_artifact_is_reported(tmp_path: Path) -> None:
    seed_good_repo(tmp_path)
    rel, corrupted, _ = MISSING_FIELD_CASES["run"]
    _w(tmp_path, rel, corrupted)
    report = validate_repo(tmp_path)
    assert {i.kind for i in report.issues} == {"run"}
    assert report.checked == len(ARTIFACT_KINDS), "a failure must not stop the other kinds"


def test_a_cross_reference_that_does_not_resolve_is_caught(tmp_path: Path) -> None:
    """Spec §3.F asks for resolvable cross-references: a run's cursor must name
    a step the run actually records."""
    seed_good_repo(tmp_path)
    _w(
        tmp_path,
        "docs/superpowers/runs/2019-03-04-feat-widget.yaml",
        GOOD_RUN.replace("cursor: implement", "cursor: nonesuch"),
    )
    report = validate_repo(tmp_path)
    assert not report.ok
    assert "nonesuch" in "\n".join(str(i) for i in report.issues)


def test_a_run_recording_per_phase_items_is_valid(tmp_path: Path) -> None:
    """`StepRecord.items` is new in Phase 6 on a still-`extra=forbid` model —
    the validator must accept it, or `fr run adopt`'s own output fails CI."""
    seed_good_repo(tmp_path)
    _w(
        tmp_path,
        "docs/superpowers/runs/2019-03-04-feat-widget.yaml",
        GOOD_RUN.replace(
            "  implement:\n    state: running\n",
            "  implement:\n    state: running\n    items:\n      phase/1: done\n",
        ),
    )
    assert validate_repo(tmp_path).ok


# --- 3. stamps: unknown fails, newer fails closed -------------------------


def test_an_unknown_stamp_version_fails(tmp_path: Path) -> None:
    seed_good_repo(tmp_path)
    _w(
        tmp_path,
        "docs/superpowers/runs/2019-03-04-feat-widget.yaml",
        "schema_version: two\n" + GOOD_RUN,
    )
    report = validate_repo(tmp_path)
    assert not report.ok
    rendered = "\n".join(str(i) for i in report.issues)
    assert "schema_version" in rendered
    assert "2019-03-04-feat-widget.yaml" in rendered


def test_a_stamp_newer_than_this_fr_fails_closed_with_an_upgrade_message(tmp_path: Path) -> None:
    """Spec §2: downgrades are a non-goal. A newer artifact is not something to
    rewrite, it is a signal that this fr is behind."""
    seeded = seed_good_repo(tmp_path)
    journal = seeded["journal"]
    journal.write_text("<!-- fr:journal-schema=99 -->\n" + journal.read_text())
    before = journal.read_bytes()

    report = validate_repo(tmp_path)
    assert not report.ok
    rendered = "\n".join(str(i) for i in report.issues)
    assert "99" in rendered
    assert "upgrade" in rendered.lower(), f"no upgrade instruction: {rendered}"
    assert journal.read_bytes() == before, "a newer artifact must never be rewritten"


def test_a_stale_stamp_is_reported_as_stale(tmp_path: Path) -> None:
    """Plans are the one kind above version 1; a v1 plan is stale, and the
    message must send the operator to the migration, not to a text editor."""
    seed_good_repo(tmp_path)
    _w(
        tmp_path,
        f"docs/superpowers/plans/{PLAN_SLUG}/_meta.yaml",
        GOOD_META.replace("schema_version: 2", "schema_version: 1"),
    )
    report = validate_repo(tmp_path)
    assert not report.ok
    rendered = "\n".join(str(i) for i in report.issues)
    assert "fr migrate artifacts" in rendered


def test_validate_artifact_takes_one_path(tmp_path: Path) -> None:
    seeded = seed_good_repo(tmp_path)
    assert validate_artifact(artifact_kind("spec"), seeded["spec"]) == ()


# --- 4. the duplicated section block (the real corruption) ----------------


def _splice_like_commit_7ece5a9(spec_text: str, replacement: str) -> str:
    """Reproduce the bad splice verbatim: `index` finds the FIRST occurrence,
    which here is an inline mention inside the prose, so `end < start` and the
    tail is re-appended."""
    start = spec_text.index("## 5. Test Plan")
    end = spec_text.index("## Implementation Plans")
    return spec_text[:start] + replacement + spec_text[end:]


SPLICEABLE_SPEC = """# Thermosiphon rebuild

## 1. Problem

`fr.spec` parses `## Implementation Plans` into `PlanRef(plan, repo, file, …)`;
`PlanMeta` carries `target_repo`.

## 2. Goal

It does not leak.

## 5. Test Plan

1. Old step.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2019-03-04-thermosiphon-rebuild | `derio-net/super-fr` | `2019-03-04-thermosiphon-rebuild` | — |
"""


def test_a_duplicated_section_block_is_caught(tmp_path: Path) -> None:
    seed_good_repo(tmp_path)
    spliced = _splice_like_commit_7ece5a9(SPLICEABLE_SPEC, "## 5. Test Plan\n\n1. New step.\n\n")
    assert spliced.count("## 2. Goal") == 2, "the fixture must actually be duplicated"
    path = _w(tmp_path, f"docs/superpowers/specs/{PLAN_SLUG}-design.md", spliced)

    issues = validate_artifact(artifact_kind("spec"), path)
    rendered = "\n".join(str(i) for i in issues)
    assert issues, "a duplicated section block passed validation"
    assert "2. Goal" in rendered, rendered
    assert "duplicat" in rendered.lower(), rendered


def test_a_heading_fused_mid_sentence_is_caught(tmp_path: Path) -> None:
    """The other half of the same corruption, verbatim from the damaged file:

        ## Implementation Plans` into `PlanRef(plan, repo, file, …)`; `PlanMeta` carries

    A heading line whose inline code never closes is prose that a heading was
    spliced into.
    """
    seed_good_repo(tmp_path)
    fused = (
        "# Thermosiphon rebuild\n\n"
        "## Implementation Plans` into `PlanRef(plan, repo, file, …)`; `PlanMeta` carries\n"
        "`target_repo` and `parent_plan`.\n"
    )
    path = _w(tmp_path, f"docs/superpowers/specs/{PLAN_SLUG}-design.md", fused)

    issues = validate_artifact(artifact_kind("spec"), path)
    assert issues, "a heading fused mid-sentence passed validation"
    assert "fused" in "\n".join(str(i) for i in issues).lower()


def test_a_legitimate_inline_mention_of_a_heading_is_not_flagged(tmp_path: Path) -> None:
    """`## Implementation Plans` inside backticks is ordinary prose — three live
    specs in this repo do it, and a validator that fails them is a validator
    that gets switched off."""
    seed_good_repo(tmp_path)
    path = _w(tmp_path, f"docs/superpowers/specs/{PLAN_SLUG}-design.md", SPLICEABLE_SPEC)
    assert validate_artifact(artifact_kind("spec"), path) == ()


def test_headings_inside_a_code_fence_are_not_sections(tmp_path: Path) -> None:
    seed_good_repo(tmp_path)
    path = _w(
        tmp_path,
        f"docs/superpowers/specs/{PLAN_SLUG}-design.md",
        GOOD_SPEC + "\n```\n# Before\n...\n# Before\n```\n",
    )
    assert validate_artifact(artifact_kind("spec"), path) == ()


# --- the CLI --------------------------------------------------------------


def _invoke(repo: Path, argv: list[str]):
    return runner_cli.invoke(app, argv, env={**os.environ, "VK_REPO_ROOT": str(repo)})


def test_cli_passes_on_a_clean_repo(tmp_path: Path) -> None:
    seed_good_repo(tmp_path)
    result = _invoke(tmp_path, ["validate", "artifacts"])
    assert result.exit_code == 0, result.output
    assert str(len(ARTIFACT_KINDS)) in result.output


def test_cli_fails_naming_the_file_and_the_field(tmp_path: Path) -> None:
    seed_good_repo(tmp_path)
    rel, corrupted, field = MISSING_FIELD_CASES["matrix"]
    _w(tmp_path, rel, corrupted)
    result = _invoke(tmp_path, ["validate", "artifacts"])
    assert result.exit_code == 1, result.output
    assert "matrix.yaml" in result.output
    assert field in result.output


def test_cli_kind_filter_checks_only_that_kind(tmp_path: Path) -> None:
    seed_good_repo(tmp_path)
    rel, corrupted, _ = MISSING_FIELD_CASES["matrix"]
    _w(tmp_path, rel, corrupted)
    assert _invoke(tmp_path, ["validate", "artifacts", "--kind", "spec"]).exit_code == 0
    assert _invoke(tmp_path, ["validate", "artifacts", "--kind", "matrix"]).exit_code == 1


def test_cli_rejects_an_unknown_kind(tmp_path: Path) -> None:
    seed_good_repo(tmp_path)
    result = _invoke(tmp_path, ["validate", "artifacts", "--kind", "brainstorm"])
    assert result.exit_code == 2, result.output
    assert "brainstorm" in result.output


# --- this repo's own artifacts -------------------------------------------


def test_this_repos_own_artifacts_are_structurally_valid() -> None:
    """What `.github/workflows/ci.yml` runs, run here too: the gate fails in
    the test suite (fast, local) before it fails in CI."""
    report = validate_repo(REPO_ROOT)
    assert report.ok, "\n".join(str(i) for i in report.issues)
    assert report.checked > 0


# --- review r4-f1: a duplicate YAML key is a SILENT drop ------------------


def test_a_duplicated_key_in_the_matrix_is_caught_not_silently_dropped(tmp_path: Path) -> None:
    """This is a bug this repo actually shipped, on this very branch.

    `docs/acceptance/matrix.yaml` carried `levels:` twice on one row. PyYAML
    keeps the LAST occurrence, so the first block — the ref to
    `test_artifact_registry.py` — vanished: absent from the committed reports,
    invisible to `fr acceptance check`, and invisible to this validator, which
    only ever saw the mapping PyYAML handed back. A row that reads as valid
    while quietly dropping half of what it claims is worse than a red row.
    """
    seed_good_repo(tmp_path)
    matrix = tmp_path / "docs" / "acceptance" / "matrix.yaml"
    matrix.write_text(
        GOOD_MATRIX.replace(
            "    status: ci\n",
            "    levels:\n      integration:\n        - super-fr:tests/x.py\n    status: ci\n",
        )
    )

    report = validate_repo(tmp_path)

    assert not report.ok
    problems = " ".join(str(i) for i in report.issues)
    assert "duplicate key" in problems
    assert "levels" in problems


@pytest.mark.parametrize(
    ("kind", "rel", "text"),
    [
        (
            "plan",
            f"docs/superpowers/plans/{PLAN_SLUG}/_meta.yaml",
            GOOD_META + "plan: 2019-03-04-thermosiphon-rebuild\n",
        ),
        (
            "run",
            "docs/superpowers/runs/2019-03-04-feat-widget.yaml",
            "cursor: implement\n" + GOOD_RUN,
        ),
        # review r5-c4: a plan is a FOLDER of YAML carriers and `NN.yaml` is
        # the one that matters — tick state lives there. A second `state:`
        # block silently replaces the first, un-ticking completed steps, and
        # `parse()`'s `yaml.safe_load` reports nothing.
        (
            "plan phase",
            f"docs/superpowers/plans/{PLAN_SLUG}/01.yaml",
            GOOD_PHASE
            + 'state:\n  steps:\n    P1.T1.S1:\n      state: " "\n      ticked_at: null\n'
            "      note: null\n  completion:\n    at: null\n    note: null\n"
            "    observed_prs: []\n",
        ),
    ],
)
def test_a_duplicated_key_is_caught_in_every_yaml_carrier(
    tmp_path: Path, kind: str, rel: str, text: str
) -> None:
    """The same silent drop is available to plans and runs. `_load_mapping` is
    shared, so the detector belongs there rather than in the matrix validator
    alone — and a duplicate `schema_version` is also what makes the migration
    runner's stamp writer chase a key the reader never sees (see
    `test_migration_runner.py::test_a_stamp_that_does_not_move...`)."""
    seed_good_repo(tmp_path)
    _w(tmp_path, rel, text)

    report = validate_repo(tmp_path)

    assert not report.ok
    assert "duplicate key" in " ".join(str(i) for i in report.issues)


def test_a_duplicate_state_block_in_a_phase_file_un_ticks_steps_invisibly(
    tmp_path: Path,
) -> None:
    """The concrete damage behind r5-c4, spelled out: the second `state:`
    block wins, so every step the first one marked done reads as pending —
    and `fr validate artifacts` said the plan was fine.
    """
    import yaml as _yaml

    seed_good_repo(tmp_path)
    ticked = GOOD_PHASE.replace('state: " "', 'state: "x"')
    unticked_tail = (
        "state:\n  steps:\n    P1.T1.S1:\n"
        '      state: " "\n      ticked_at: null\n      note: null\n'
        "  completion:\n    at: null\n    note: null\n    observed_prs: []\n"
    )
    _w(tmp_path, f"docs/superpowers/plans/{PLAN_SLUG}/01.yaml", ticked + unticked_tail)

    # PyYAML really does drop the ticked block, silently.
    loaded = _yaml.safe_load(
        (tmp_path / "docs" / "superpowers" / "plans" / PLAN_SLUG / "01.yaml").read_text()
    )
    assert loaded["state"]["steps"]["P1.T1.S1"]["state"] == " "

    report = validate_repo(tmp_path)

    assert not report.ok
    problems = " ".join(str(i) for i in report.issues)
    assert "duplicate key" in problems
    assert "01.yaml" in problems


def test_a_structurally_clean_plan_folder_still_validates(tmp_path: Path) -> None:
    """The strict load added for r5-c4 must not start rejecting good plans."""
    seed_good_repo(tmp_path)

    assert validate_repo(tmp_path).ok


# =========================================================================
# File-system answers are findings too (review r5-e11)
# =========================================================================


def test_a_symlinked_artifact_is_followed_and_validated_once(tmp_path: Path) -> None:
    """Following is right — the symlink's target is the real content. Counting
    it twice is not: an operator fixing one file would see two identical
    complaints."""
    seed_good_repo(tmp_path)
    real_dir = tmp_path / "elsewhere"
    real_dir.mkdir()
    real = real_dir / "matrix.yaml"
    real.write_text(GOOD_MATRIX.replace("status: ci", "status: not-a-status"))
    matrix = tmp_path / "docs" / "acceptance" / "matrix.yaml"
    matrix.unlink()
    matrix.symlink_to(real)

    report = validate_repo(tmp_path)

    matrix_issues = [i for i in report.issues if i.kind == "matrix"]
    assert len(matrix_issues) == 1, matrix_issues


def test_an_artifact_path_that_is_a_directory_is_reported(tmp_path: Path) -> None:
    """`iter_paths_of`'s `is_file()` filter made this silent — the plan simply
    stopped being validated, and nothing said so."""
    seed_good_repo(tmp_path)
    meta = tmp_path / "docs" / "superpowers" / "plans" / PLAN_SLUG / "_meta.yaml"
    meta.unlink()
    meta.mkdir()

    report = validate_repo(tmp_path)

    problems = " ".join(str(i) for i in report.issues)
    assert not report.ok
    assert "is a directory" in problems
    assert "_meta.yaml" in problems


def test_an_unreadable_artifact_is_a_failure_naming_it(tmp_path: Path) -> None:
    import os

    seed_good_repo(tmp_path)
    matrix = tmp_path / "docs" / "acceptance" / "matrix.yaml"
    os.chmod(matrix, 0o000)
    try:
        report = validate_repo(tmp_path)
    finally:
        os.chmod(matrix, 0o644)

    problems = " ".join(str(i) for i in report.issues)
    assert not report.ok
    assert "matrix.yaml" in problems
    assert "cannot be read" in problems


def test_non_utf8_bytes_are_a_failure_naming_the_file(tmp_path: Path) -> None:
    seed_good_repo(tmp_path)
    matrix = tmp_path / "docs" / "acceptance" / "matrix.yaml"
    matrix.write_bytes(b"schema_version: 1\nrows: \xff\xfe\n")

    report = validate_repo(tmp_path)

    problems = " ".join(str(i) for i in report.issues)
    assert not report.ok
    assert "matrix.yaml" in problems
    assert "UTF-8" in problems


# --- repo-authored workflow shapes ---------------------------------------


def test_a_broken_repo_authored_workflow_shape_is_reported(tmp_path: Path) -> None:
    """Not an artifact KIND — no stamp, no migration, no `current_version` —
    but a repo whose shapes do not parse is broken in exactly the way this
    command reports. `fr workflow check` stays the shapes' own validator."""
    seed_good_repo(tmp_path)
    _w(
        tmp_path,
        "docs/superpowers/workflows/broken.yaml",
        "workflow: broken\nschema: 1\nunit: run\n"
        "steps:\n  - id: a\n    kind: agent\n    needs: [ghost]\n",
    )

    report = validate_repo(tmp_path)

    problems = " ".join(str(i) for i in report.issues)
    assert not report.ok
    assert "broken.yaml" in problems
    assert "ghost" in problems


def test_workflow_shapes_are_not_a_registered_artifact_kind() -> None:
    """Registering them would mean inventing a stamp, a migration chain and a
    `current_version` for a hand-authored file."""
    from fr.artifacts.registry import ARTIFACT_KINDS

    assert "workflow" not in ARTIFACT_KINDS


def test_a_valid_repo_authored_shape_does_not_fail_validation(tmp_path: Path) -> None:
    seed_good_repo(tmp_path)
    _w(
        tmp_path,
        "docs/superpowers/workflows/fine.yaml",
        "workflow: fine\nschema: 1\nunit: run\nsteps:\n  - id: a\n    kind: cli\n    run: 'true'\n",
    )

    assert validate_repo(tmp_path).ok
