"""Tests for vk.migrate — v1-to-v2 mechanical sweep."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.cli import app
from typer.testing import CliRunner


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "implemented" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir()
    return tmp_path


def _write_v1_plan(repo: Path, *, slug: str, status: str = "Complete") -> Path:
    """Write a minimal v1 phased plan markdown file."""
    p = repo / "docs" / "superpowers" / "plans" / f"{slug}.md"
    p.write_text(
        f"# {slug.replace('-', ' ').title()}\n\n"
        f"**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        f"**Status:** {status}\n\n"
        f"## Phase 1: Setup [agentic]\n"
        f"**Depends on:** —\n\n"
        f"### Task 1: Initial setup\n\n"
        f"- [x] **Step 1: Do the first thing** Some details here.\n"
        f"- [ ] **Step 2: Do the second thing** More details.\n"
    )
    return p


def test_migrate_dry_run_lists_outcomes_without_writing(tmp_path):
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    md = _write_v1_plan(repo, slug="2026-05-10-fixture-v1")

    outcomes = migrate_repo(repo, dry_run=True, target_repo="derio-net/test")
    assert len(outcomes) == 1
    assert outcomes[0].reason == "migrated (dry run)"
    # Original .md still in place; no folder created
    assert md.exists()
    assert not (repo / "docs" / "superpowers" / "plans" / "2026-05-10-fixture-v1").exists()


def test_migrate_apply_creates_v2_folder_and_archives_md(tmp_path):
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    md = _write_v1_plan(repo, slug="2026-05-10-fixture-v1")

    outcomes = migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    assert len(outcomes) == 1
    assert outcomes[0].reason == "migrated"

    # New folder exists
    new = repo / "docs" / "superpowers" / "plans" / "2026-05-10-fixture-v1"
    assert new.is_dir()
    assert (new / "_meta.yaml").exists()
    assert (new / "_prose.md").exists()
    assert (new / "01.yaml").exists()

    # Original .md moved to .v1-archive
    assert not md.exists()
    assert md.with_suffix(".md.v1-archive").exists()

    # New plan parses cleanly
    plan = parse(new)
    assert plan.meta.plan == "2026-05-10-fixture-v1"
    # First step was [x] in v1 → state == "x" in v2
    assert plan.phases[0].state.steps["P1.T1.S1"].state == "x"
    assert plan.phases[0].state.steps["P1.T1.S2"].state == " "


def test_migrate_skips_in_progress_by_default(tmp_path):
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-complete", status="Complete")
    _write_v1_plan(repo, slug="2026-05-10-in-progress", status="In Progress")

    outcomes = migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    by_name = {o.plan_path.stem: o.reason for o in outcomes}
    assert by_name["2026-05-10-complete"] == "migrated"
    assert by_name["2026-05-10-in-progress"].startswith("skipped (in-progress")


def test_migrate_include_in_progress_flag(tmp_path):
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-in-progress", status="In Progress")

    outcomes = migrate_repo(
        repo, dry_run=False, include_in_progress=True, target_repo="derio-net/test"
    )
    assert outcomes[0].reason == "migrated"


def test_migrate_rewrites_spec_table_drops_status_column(tmp_path):
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    spec_path = repo / "docs" / "superpowers" / "specs" / "2026-05-10-test.md"
    spec_path.write_text(
        "# test\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Repo | File | Status | Depends on |\n"
        "|------|------|------|--------|------------|\n"
        "| Some plan | `derio-net/x` | `docs/superpowers/plans/x/` | Complete | — |\n"
    )

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    new_text = spec_path.read_text()
    assert "Status" not in new_text.splitlines()[2]  # header line no longer has Status
    # The data row should have 4 cells now, no Status
    rows = [line for line in new_text.splitlines() if line.startswith("| Some plan")]
    assert len(rows) == 1
    assert rows[0].count("|") == 5  # 4 cells = 5 pipes


def test_migrate_rewrites_file_cells_md_to_folder(tmp_path):
    """Spec File cells pointing at `<path>.md` get rewritten to `<path>/`
    after migration converts them to v2 folders."""
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-cells-fixture")
    spec_path = repo / "docs" / "superpowers" / "specs" / "2026-05-10-test.md"
    spec_path.write_text(
        "# test\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Repo | File | Status | Depends on |\n"
        "|------|------|------|--------|------------|\n"
        "| The plan | `derio-net/x` "
        "| `docs/superpowers/plans/2026-05-10-cells-fixture.md` | Complete | — |\n"
    )

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    new_text = spec_path.read_text()
    assert "2026-05-10-cells-fixture/" in new_text
    assert "2026-05-10-cells-fixture.md" not in new_text


def test_migrate_leaves_file_cells_when_folder_does_not_exist(tmp_path):
    """If a row points at `<path>.md` but no `<path>/` folder exists,
    the cell is left alone — re-running after fixing the cause completes
    the rewrite."""
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    spec_path = repo / "docs" / "superpowers" / "specs" / "2026-05-10-test.md"
    spec_path.write_text(
        "# test\n\n"
        "## Implementation Plans\n\n"
        "| Plan | Repo | File | Status | Depends on |\n"
        "|------|------|------|--------|------------|\n"
        "| Cross-repo | `derio-net/y` | `docs/superpowers/plans/never-here.md` | Complete | — |\n"
    )

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    new_text = spec_path.read_text()
    # Status column is dropped; File cell is unchanged because folder doesn't exist
    assert "never-here.md" in new_text
    assert "Status" not in new_text.splitlines()[2]


def test_migrate_rejects_non_iso_date_slug(tmp_path):
    """Plans whose slug doesn't begin with YYYY-MM-DD raise MigrationError."""
    from fr.migrate import MigrationError, migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="legacy-plan-no-date")

    with pytest.raises(MigrationError, match="YYYY-MM-DD"):
        migrate_repo(repo, dry_run=False, target_repo="derio-net/test")


def test_migrate_preserves_freeform_track(tmp_path):
    """Origin table 'Track' cells with non-canonical values are preserved verbatim."""
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-base-rework-2.md"
    p.write_text(
        "# Base — Rework 2\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "**Parent plan:** "
        "`docs/superpowers/archived-plans/2026-05-08-base.md` (merged + archived)\n\n"
        "---\n\n"
        "## Origin\n\n"
        "| # | Item | Source | Track |\n"
        "|---|------|--------|-------|\n"
        "| 1 | first item | demo | development (future-triggered) |\n"
        "| 2 | second item | demo | decision → development |\n\n"
        "---\n\n"
        "## Phase 1: Apply rework [agentic]\n"
        "**Depends on:** —\n\n"
        "### Task 1: Apply\n\n"
        "- [ ] **Step 1: Do the work** Details.\n"
    )

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    new = repo / "docs" / "superpowers" / "plans" / "2026-05-10-base-rework-2"
    plan = parse(new)
    assert plan.meta.origin_items[0].track == "development (future-triggered)"
    assert plan.meta.origin_items[1].track == "decision → development"


def test_migrate_does_not_treat_rework_substring_as_rework(tmp_path):
    """A plan whose slug merely *contains* `rework` (e.g. a plan that adds a
    rework feature) is NOT a rework plan — its parent_plan / origin_items
    fields must NOT be populated. Anchored slug regex is the gate.
    """
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    # Slug contains "rework" but does NOT end with `-rework-N`
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-vk-plan-rework-feature.md"
    p.write_text(
        "# A plan adding rework support\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        # Even if the markdown body mentions a parent_plan (illustrative
        # example for the docs), the migration should NOT pick it up
        # because the slug isn't a rework slug.
        "**Parent plan:** `docs/superpowers/archived-plans/2026-04-08-foo.md`\n\n"
        "## Phase 1: Build [agentic]\n"
        "**Depends on:** —\n\n"
        "### Task 1: t\n\n"
        "- [x] **Step 1: x** d.\n"
    )

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    new = repo / "docs" / "superpowers" / "plans" / "2026-05-10-vk-plan-rework-feature"
    plan = parse(new)
    assert plan.meta.parent_plan is None, (
        f"non-rework plan got parent_plan={plan.meta.parent_plan!r} — rework detection is too loose"
    )
    assert plan.meta.origin_items == []


def test_migrate_rework_extracts_origin_table(tmp_path):
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-base-rework-1.md"
    p.write_text(
        "# Base — Rework 1\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "**Parent plan:** "
        "`docs/superpowers/archived-plans/2026-05-08-base.md` (merged + archived)\n\n"
        "---\n\n"
        "## Origin\n\n"
        "| # | Item | Source | Track |\n"
        "|---|------|--------|-------|\n"
        "| 1 | first item | PR #50 review | development |\n"
        "| 2 | second item | demo | operations |\n\n"
        "---\n\n"
        "## Phase 1: Apply rework [agentic]\n"
        "**Depends on:** —\n\n"
        "### Task 1: Apply\n\n"
        "- [ ] **Step 1: Do the work** Details.\n"
    )

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    new = repo / "docs" / "superpowers" / "plans" / "2026-05-10-base-rework-1"
    plan = parse(new)
    assert plan.meta.parent_plan is not None
    assert "2026-05-08-base" in plan.meta.parent_plan
    assert len(plan.meta.origin_items) == 2
    assert plan.meta.origin_items[0].track == "development"
    assert plan.meta.origin_items[1].track == "operations"


def test_migrate_skips_already_migrated(tmp_path):
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-already")
    # Pre-create the v2 folder to simulate prior migration
    (repo / "docs" / "superpowers" / "plans" / "2026-05-10-already").mkdir()

    outcomes = migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    assert outcomes[0].reason.startswith("skipped (folder already exists)")


def test_migrate_rejects_per_phase_target_repo_conflict(tmp_path):
    """v1 plan with conflicting target_repo across phases → MigrationError."""
    from fr.migrate import MigrationError, migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-multi-target.md"
    p.write_text(
        "# Multi target\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 1: First [agentic]\n"
        "**Target repo:** derio-net/repo-a\n"
        "**Depends on:** —\n\n"
        "### Task 1: t\n\n"
        "- [x] **Step 1: x** d.\n\n"
        "## Phase 2: Second [agentic]\n"
        "**Target repo:** derio-net/repo-b\n"
        "**Depends on:** Phase 1\n\n"
        "### Task 1: t\n\n"
        "- [x] **Step 1: x** d.\n"
    )

    with pytest.raises(MigrationError, match="different target repos"):
        migrate_repo(repo, dry_run=False)


def test_migrate_cli_default_is_dry_run(tmp_path, monkeypatch):
    """No --yes flag → preview mode; nothing gets written."""
    from fr.cli import app
    from typer.testing import CliRunner

    repo = _make_repo(tmp_path)
    md = _write_v1_plan(repo, slug="2026-05-10-cli-default")
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(app, ["migrate", "v1-to-v2", "--target-repo", "derio-net/test"])
    assert result.exit_code == 0, result.output
    assert "(dry-run; pass --yes to apply)" in result.output
    # Original .md still in place
    assert md.exists()
    assert not (repo / "docs" / "superpowers" / "plans" / "2026-05-10-cli-default").exists()


def test_migrate_flat_plan_emits_single_phase_yaml(tmp_path):
    """v1 flat-format plans (no ## Phase headings) must produce 01.yaml.

    The v1 parser puts tasks into v1plan.tasks (not v1plan.phases) for flat
    plans. Without the fix the migration would create an empty folder with
    only _meta.yaml; with the fix all tasks land in a synthetic Phase 1.
    """
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-flat-plan.md"
    p.write_text(
        "# Flat Plan\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "### Task 1: Bootstrap\n\n"
        "- [x] **Step 1: Do the thing** Some details.\n"
        "- [ ] **Step 2: Verify** Check the output.\n\n"
        "### Task 2: Finalise\n\n"
        "- [ ] **Step 1: Clean up** Remove temp files.\n"
    )

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    new = repo / "docs" / "superpowers" / "plans" / "2026-05-10-flat-plan"
    assert (new / "01.yaml").exists(), "flat plan must produce 01.yaml"

    plan = parse(new)
    assert len(plan.phases) == 1
    phase = plan.phases[0]
    assert phase.phase.number == 1
    assert len(phase.tasks) == 2
    assert phase.tasks[0].steps[0].id == "P1.T1.S1"
    assert phase.state.steps["P1.T1.S1"].state == "x"
    assert phase.state.steps["P1.T1.S2"].state == " "
    assert phase.state.steps["P1.T2.S1"].state == " "


def test_migrate_cli_apply_yes(tmp_path, monkeypatch):
    from fr.cli import app
    from typer.testing import CliRunner

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-cli-test")
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(app, ["migrate", "v1-to-v2", "--yes", "--target-repo", "derio-net/test"])
    assert result.exit_code == 0, result.output
    assert "1 migrated" in result.output
    # Hint suffix should NOT appear when --yes was given
    assert "(dry-run" not in result.output


def test_migrate_step_bold_paragraph_format(tmp_path):
    """`**Step N: title**` (no checkbox) — bold-paragraph step format.

    Frank's argocd-infrastructure, openrgb-* plans and many others use bare
    bold paragraphs instead of `- [x] **Step N:**` checkboxes. Before 2.0.4
    the regex required the checkbox prefix and silently dropped every step.
    """
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-bold-paragraph.md"
    p.write_text(
        "# Bold Paragraph\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "### Task 1: Bootstrap\n\n"
        "**Step 1: Do the first thing**\n\n"
        "Some prose body here.\n\n"
        "**Step 2: Do the second**\n\n"
        "More body.\n"
    )
    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(repo / "docs" / "superpowers" / "plans" / "2026-05-10-bold-paragraph")
    task = plan.phases[0].tasks[0]
    assert len(task.steps) == 2
    assert task.steps[0].text.startswith("Do the first thing")
    # Body got merged into step text
    assert "Some prose body here" in task.steps[0].text


def test_migrate_step_bold_prefix_format(tmp_path):
    """`- [x] **Step N:** title` — bold-prefix-only format (title outside bold).

    Used in willikins/stoa-goals-entry plan. Distinct from `**Step N: title**`
    because the closing `**` comes immediately after the colon.
    """
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-bold-prefix.md"
    p.write_text(
        "# Bold Prefix\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "### Task 1: Enter goal\n\n"
        "- [x] **Step 1:** Create goal verbatim from spec — `level: company`, `status: active`.\n"
    )
    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(repo / "docs" / "superpowers" / "plans" / "2026-05-10-bold-prefix")
    task = plan.phases[0].tasks[0]
    assert len(task.steps) == 1
    assert "Create goal verbatim from spec" in task.steps[0].text
    # State == "x" (checkbox was ticked)
    assert plan.phases[0].state.steps["P1.T1.S1"].state == "x"


def test_migrate_phase_with_step_subsections_fallback(tmp_path):
    """`### Step N:` h3 headers (instead of `### Task N:`) trigger phase-level fallback.

    Content-factory's content-pipeline-foundation uses `### Step N:` as the
    sub-section header under `## Phase N:`. Without fallback, the migrator
    emits `tasks: []`. With fallback, each `### Step` becomes a synthetic
    task with the raw body preserved as a single step.
    """
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-step-subsections.md"
    p.write_text(
        "# Step Subsections\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 1: Bootstrap [agentic]\n"
        "**Depends on:** —\n\n"
        "### Step 1: Create repo\n\n"
        "- [x] **Create repo and clone**\n\n"
        "```bash\ngh repo create foo\ngit clone foo\n```\n\n"
        "### Step 2: Add files\n\n"
        "- [x] **Add .gitignore**\n"
    )
    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(repo / "docs" / "superpowers" / "plans" / "2026-05-10-step-subsections")
    phase = plan.phases[0]
    assert len(phase.tasks) == 2, "fallback should synthesize a task per ### Step"
    assert "Create repo" in phase.tasks[0].title
    # Each synthetic task has one step with the raw body
    assert len(phase.tasks[0].steps) == 1
    assert "Create repo and clone" in phase.tasks[0].steps[0].text
    assert "gh repo create foo" in phase.tasks[0].steps[0].text


def test_migrate_task_with_no_parseable_steps_fallback(tmp_path):
    """Task whose body uses an unrecognised step format gets its raw body
    spliced in as a single synthetic step (no silent content loss).
    """
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-task-body-fallback.md"
    p.write_text(
        "# Task Body Fallback\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "### Task 1: Research candidates\n\n"
        "Evaluated: ElevenLabs, XTTS, Bark. Tested with sample content.\n"
        "Documented in `docs/decisions/tts-evaluation.md`.\n"
    )
    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(repo / "docs" / "superpowers" / "plans" / "2026-05-10-task-body-fallback")
    task = plan.phases[0].tasks[0]
    assert len(task.steps) == 1, "task with no parseable steps must get one synthetic step"
    assert "Evaluated: ElevenLabs" in task.steps[0].text
    assert "tts-evaluation.md" in task.steps[0].text


def test_migrate_force_re_migrates_existing_folder(tmp_path):
    """`--force` tears down an existing v2 folder + restores the .v1-archive."""
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-force-target")

    # First migration succeeds normally.
    out1 = migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    assert out1[0].reason == "migrated"
    folder = repo / "docs" / "superpowers" / "plans" / "2026-05-10-force-target"
    archive = repo / "docs" / "superpowers" / "plans" / "2026-05-10-force-target.md.v1-archive"
    assert folder.is_dir()
    assert archive.exists()

    # Tamper with the migrated yaml to prove it gets regenerated.
    (folder / "01.yaml").write_text(
        "schema_version: 2\n"
        "phase:\n  number: 1\n  title: TAMPERED\n  tag: agentic\n"
        "  depends_on: []\n  tracking_issue: null\n"
        "tasks: []\n"
        "state:\n  steps: {}\n  completion:\n"
        "    at: null\n    note: null\n    observed_prs: []\n"
    )

    # Second run with --force re-migrates from the archive.
    out2 = migrate_repo(repo, dry_run=False, force=True, target_repo="derio-net/test")
    by_name = {o.plan_path.stem: o.reason for o in out2}
    assert by_name["2026-05-10-force-target"] == "migrated"
    # Fresh yaml — no longer tampered.
    assert "TAMPERED" not in (folder / "01.yaml").read_text()


def test_migrate_task_body_fallback_with_phase_tag_suffix(tmp_path):
    """`### Task N: title [agentic]` — tag suffix doesn't break body lookup.

    The parsed `task.title` strips the `[agentic]` suffix while the raw
    `### Task` header in md_text retains it. Body lookup must ignore the
    suffix or the fallback never finds the task body.
    """
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-tagged-task.md"
    p.write_text(
        "# Tagged Task\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 1: Stage [agentic]\n"
        "**Depends on:** —\n\n"
        "### Task 1: Bootstrap [agentic]\n\n"
        "Plain prose body, no recognised step markers.\n"
    )
    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(repo / "docs" / "superpowers" / "plans" / "2026-05-10-tagged-task")
    task = plan.phases[0].tasks[0]
    assert task.title == "Bootstrap"
    # Fallback must find the body even though md_text has `[agentic]` suffix
    assert len(task.steps) == 1
    assert "Plain prose body" in task.steps[0].text


def test_migrate_fallback_ignores_fenced_code_block_examples(tmp_path):
    """`### Task N:` inside a fenced code block must not register as a real task.

    Plans that document the plan format frequently include fenced examples.
    Without fence-stripping the body-extraction regex would treat those as
    real headers and emit spurious synthetic tasks.
    """
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-fenced-examples.md"
    p.write_text(
        "# Fenced Examples\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 1: Documentation [agentic]\n"
        "**Depends on:** —\n\n"
        "### Step 1: Document the format\n\n"
        "Plans use this format:\n\n"
        "```markdown\n"
        "### Task 1: Example task\n"
        "### Step 2: Example step\n"
        "```\n\n"
        "End of section.\n"
    )
    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(repo / "docs" / "superpowers" / "plans" / "2026-05-10-fenced-examples")
    phase = plan.phases[0]
    # Only ONE synthetic task — the fenced examples must not register.
    assert len(phase.tasks) == 1, (
        f"fence-stripping failed: got {len(phase.tasks)} tasks, expected 1"
    )
    assert phase.tasks[0].title == "Document the format"
    # And the code block content survives in the step body
    assert "Example task" in phase.tasks[0].steps[0].text


def test_migrate_force_dry_run_does_not_destroy(tmp_path):
    """`--force` in dry-run mode reports re-migration but doesn't touch disk."""
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-force-dryrun")
    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")  # initial migration

    folder = repo / "docs" / "superpowers" / "plans" / "2026-05-10-force-dryrun"
    archive = repo / "docs" / "superpowers" / "plans" / "2026-05-10-force-dryrun.md.v1-archive"
    yaml_before = (folder / "01.yaml").read_text()

    outcomes = migrate_repo(repo, dry_run=True, force=True, target_repo="derio-net/test")
    assert any("dry run" in o.reason for o in outcomes)
    # Folder + archive both still in place; yaml unchanged
    assert folder.is_dir()
    assert archive.exists()
    assert (folder / "01.yaml").read_text() == yaml_before


# ---------------------------------------------------------------------------
# #245 — migrator lossiness fixes


def _plans(repo: Path) -> Path:
    return repo / "docs" / "superpowers" / "plans"


def test_migrate_fails_loud_without_target_repo(tmp_path):
    """#245 Bug 1: a plan with no per-phase '**Target repo:**' and no
    --target-repo must fail loud — never silently default to the plugin repo."""
    from fr.migrate import MigrationError, migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-no-target")  # helper declares no target

    with pytest.raises(MigrationError, match="--target-repo"):
        migrate_repo(repo, dry_run=False)


def test_migrate_uses_explicit_target_repo(tmp_path):
    """#245 Bug 1: an explicit target_repo is honored (and recorded in meta)."""
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-with-flag")

    migrate_repo(repo, dry_run=False, target_repo="derio-net/frank")
    plan = parse(_plans(repo) / "2026-05-10-with-flag")
    assert plan.meta.target_repo == "derio-net/frank"


def test_migrate_phase_zero_v1_plan_fails_loud(tmp_path):
    """Phase numbering starts at 1: migrating a v1 plan with '## Phase 0'
    must raise at migration time — not silently produce an invalid v2 folder
    the bridge would skip forever. The source .md stays unarchived and no
    half-built folder is stranded, so a renumber + re-run just works."""
    from fr.migrate import MigrationError, migrate_repo

    repo = _make_repo(tmp_path)
    p = _plans(repo) / "2026-05-10-zero-phase.md"
    p.write_text(
        "# Zero Phase\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 0: Bootstrap [agentic]\n"
        "**Depends on:** —\n\n"
        "### Task 1: t\n\n- [x] **Step 1: x** d.\n"
    )
    with pytest.raises(MigrationError, match="00.yaml"):
        migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    assert p.exists(), "source .md must not be archived on failed migration"
    assert not (_plans(repo) / "2026-05-10-zero-phase").is_dir(), (
        "failed migration must not strand a half-built folder"
    )


def test_migrate_recovers_prose_depends_on(tmp_path):
    """#245 Bug 2: a '## Dependencies' / 'Blocked by Phase N' prose convention
    is recovered into depends_on instead of being flattened to []."""
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = _plans(repo) / "2026-05-10-prose-deps.md"
    p.write_text(
        "# Prose Deps\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 1: Bootstrap [agentic]\n"
        "**Depends on:** —\n\n"
        "### Task 1: t\n\n- [x] **Step 1: x** d.\n\n"
        "## Phase 2: Build [agentic]\n\n"
        "### Task 1: t\n\n- [x] **Step 1: y** d.\n\n"
        "## Dependencies\n\n"
        "Blocked by Phase 1.\n"
    )

    outcomes = migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(_plans(repo) / "2026-05-10-prose-deps")
    deps = {ph.phase.number: list(ph.phase.depends_on) for ph in plan.phases}
    assert deps[2] == [1], deps
    # The recovery is surfaced as a warning so lossy migrations aren't silent.
    assert any("depends_on" in w.lower() for o in outcomes for w in o.warnings)


def test_migrate_recovers_multi_phase_prose_depends_on(tmp_path):
    """'Blocked by Phase 1 and 3' → depends_on == [1, 3]."""
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = _plans(repo) / "2026-05-10-multi-prose-deps.md"
    p.write_text(
        "# Multi Prose Deps\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 1: A [agentic]\n**Depends on:** —\n\n### Task 1: t\n\n- [x] **Step 1: a** d.\n\n"
        "## Phase 3: B [agentic]\n**Depends on:** —\n\n### Task 1: t\n\n- [x] **Step 1: b** d.\n\n"
        "## Phase 4: C [agentic]\n\n### Task 1: t\n\n- [x] **Step 1: c** d.\n\n"
        "## Dependencies\n\nBlocked by Phase 1 and 3.\n"
    )

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(_plans(repo) / "2026-05-10-multi-prose-deps")
    deps = {ph.phase.number: sorted(ph.phase.depends_on) for ph in plan.phases}
    assert deps[4] == [1, 3], deps


def test_migrate_prose_depends_on_ignores_unrelated_digits(tmp_path):
    """#245 review: 'Blocked by Phase N' recovery must capture only the phase
    list, not version numbers / day counts / years in the surrounding prose."""
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = _plans(repo) / "2026-05-10-noisy-deps.md"
    p.write_text(
        "# Noisy Deps\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 1: A [agentic]\n**Depends on:** —\n\n### Task 1: t\n\n- [x] **Step 1: a** d.\n\n"
        "## Phase 2: B [agentic]\n\n### Task 1: t\n\n- [x] **Step 1: b** d.\n\n"
        "## Dependencies\n\nBlocked by Phase 1 which took 5 days (v2.1 rollout in 2026).\n"
    )

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(_plans(repo) / "2026-05-10-noisy-deps")
    deps = {ph.phase.number: sorted(ph.phase.depends_on) for ph in plan.phases}
    assert deps[2] == [1], f"over-captured unrelated digits: {deps}"


def test_migrate_preserves_task_intro_with_manual_operation_block(tmp_path):
    """#245 Bug 3: task intro prose + a fenced `# manual-operation` block before
    the first step must survive even when the task HAS parsed steps."""
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = _plans(repo) / "2026-05-10-manual-op.md"
    p.write_text(
        "# Manual Op\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 1: Bootstrap [agentic]\n"
        "**Depends on:** —\n\n"
        "### Task 3: Bootstrap Secret (Manual Operation)\n\n"
        "The GitHub App credentials must exist as a Secret before the runner registers.\n\n"
        "```yaml\n# manual-operation\nid: arc-github-app-secret\n```\n\n"
        "- [ ] **Step 1: Create secrets directory** Follow the manual-operation block above.\n"
    )

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(_plans(repo) / "2026-05-10-manual-op")
    task = plan.phases[0].tasks[0]
    all_text = "\n".join(s.text for s in task.steps)
    assert "# manual-operation" in all_text, "manual-operation block was dropped"
    assert "arc-github-app-secret" in all_text
    # The original parsed step is still present alongside the preserved intro.
    assert "Create secrets directory" in all_text


def test_migrate_aligns_vk_version_with_create_default(tmp_path):
    """#245 Minor: migrated plans get the same vk_version as freshly-created ones."""
    from fr import parse
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-vkver")

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(_plans(repo) / "2026-05-10-vkver")
    assert plan.meta.fr_version == ">=3.0.0,<4.0.0"


# ---------------------------------------------------------------------------
# fr migrate dirs (2026-06-05 dispatch-guards spec, Phase 3)


def _legacy_layout_repo(tmp_path: Path) -> Path:
    """Git repo with legacy archived-plans/ + two specs (one fully
    implemented, one still active)."""
    import shutil as _shutil

    sp = tmp_path / "docs" / "superpowers"
    (sp / "plans").mkdir(parents=True)
    (sp / "archived-plans").mkdir()
    (sp / "specs").mkdir()

    fixture = Path(__file__).parent / "fixtures" / "v2_plan_minimal"
    # A completed v2 plan archived under the legacy dir.
    _shutil.copytree(fixture, sp / "archived-plans" / "2026-05-01-done-plan")
    # A v1 flat archive rides along untouched.
    (sp / "archived-plans" / "2026-04-01-old-flat.md").write_text("# old v1 plan\n")
    # An active plan.
    _shutil.copytree(fixture, sp / "plans" / "2026-06-01-active-plan")

    (sp / "specs" / "2026-05-01-done-design.md").write_text(
        "# Done design\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n|---|---|---|---|\n"
        "| done | derio-net/test | `docs/superpowers/plans/2026-05-01-done-plan` | — |\n"
    )
    (sp / "specs" / "2026-06-01-active-design.md").write_text(
        "# Active design\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n|---|---|---|---|\n"
        "| active | derio-net/test | `docs/superpowers/plans/2026-06-01-active-plan` | — |\n"
    )

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=tmp_path,
        check=True,
    )
    return tmp_path


def test_migrate_dirs_dry_run_plans_moves_without_touching_fs(tmp_path, monkeypatch):
    repo = _legacy_layout_repo(tmp_path)
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(app, ["migrate", "dirs"])
    assert result.exit_code == 0, result.output
    assert "archived-plans" in result.output and "implemented/plans" in result.output
    assert "dry-run" in result.output
    sp = repo / "docs" / "superpowers"
    assert (sp / "archived-plans").is_dir(), "dry-run must not move anything"
    assert not (sp / "implemented").exists()


def test_migrate_dirs_yes_moves_layout_and_implemented_specs(tmp_path, monkeypatch):
    repo = _legacy_layout_repo(tmp_path)
    monkeypatch.chdir(repo)
    runner = CliRunner()
    result = runner.invoke(app, ["migrate", "dirs", "--yes"])
    assert result.exit_code == 0, result.output
    sp = repo / "docs" / "superpowers"
    assert not (sp / "archived-plans").exists()
    assert (sp / "implemented" / "plans" / "2026-05-01-done-plan").is_dir()
    assert (sp / "implemented" / "plans" / "2026-04-01-old-flat.md").is_file()
    # Fully-implemented spec moved; active spec stayed.
    assert (sp / "implemented" / "specs" / "2026-05-01-done-design.md").is_file()
    assert (sp / "specs" / "2026-06-01-active-design.md").is_file()
    # Moves are staged (git mv), not raw renames.
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout
    assert "R " in porcelain or "A " in porcelain


def test_migrate_dirs_noop_on_migrated_repo(tmp_path, monkeypatch):
    repo = _legacy_layout_repo(tmp_path)
    monkeypatch.chdir(repo)
    runner = CliRunner()
    assert runner.invoke(app, ["migrate", "dirs", "--yes"]).exit_code == 0
    result = runner.invoke(app, ["migrate", "dirs", "--yes"])
    assert result.exit_code == 0, result.output
    assert "nothing to migrate" in result.output.lower()


def test_migrate_dirs_moves_archived_specs_entries(tmp_path, monkeypatch):
    """Legacy archived-specs/ entries ride along into implemented/specs/
    (review finding, 2026-06-06)."""
    repo = _legacy_layout_repo(tmp_path)
    legacy_specs = repo / "docs" / "superpowers" / "archived-specs"
    legacy_specs.mkdir()
    (legacy_specs / "2026-04-01-old-design.md").write_text("# old design\n")
    (legacy_specs / "plan-config.yaml").write_text("x: 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "specs"],
        cwd=repo,
        check=True,
    )
    monkeypatch.chdir(repo)
    result = CliRunner().invoke(app, ["migrate", "dirs", "--yes"])
    assert result.exit_code == 0, result.output
    sp = repo / "docs" / "superpowers"
    assert (sp / "implemented" / "specs" / "2026-04-01-old-design.md").is_file()
    assert (sp / "implemented" / "specs" / "plan-config.yaml").is_file()
    assert not (sp / "archived-specs").exists()


# ── 2026-06-06 spec-path-repair: slug-derived gh-lookup candidates ──


def test_archive_path_variants_legacy_form_cell():
    """THE bug's cross-repo arm: a legacy archived-plans/ cell must yield
    usable candidates (old gate returned (None, None))."""
    from fr.migrate import _archive_path_variants

    active, implemented, legacy = _archive_path_variants(
        "docs/superpowers/archived-plans/2026-05-10-x/"
    )
    assert active == "docs/superpowers/plans/2026-05-10-x"
    assert implemented == "docs/superpowers/implemented/plans/2026-05-10-x"
    assert legacy == "docs/superpowers/archived-plans/2026-05-10-x"


def test_archive_path_variants_bare_slug_cell():
    from fr.migrate import _archive_path_variants

    active, implemented, legacy = _archive_path_variants("2026-05-10-x")
    assert active == "docs/superpowers/plans/2026-05-10-x"
    assert implemented == "docs/superpowers/implemented/plans/2026-05-10-x"
    assert legacy == "docs/superpowers/archived-plans/2026-05-10-x"


def test_archive_path_variants_placeholder():
    from fr.migrate import _archive_path_variants

    assert _archive_path_variants("—") == (None, None, None)


def test_spec_fully_implemented_cross_repo_slug_row(tmp_path):
    """A cross-repo row in canonical slug form counts as done when the
    other repo has the plan under implemented/plans/ — and the 'still
    active' check probes the ACTIVE variant, not the raw cell."""
    from fr.migrate import _spec_fully_implemented

    from tests.unit.fakes import FakeGhClient

    spec = tmp_path / "docs" / "superpowers" / "specs" / "2026-05-10-fixture.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "# Fixture\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|---|---|---|---|\n"
        "| Remote plan | `derio-net/other` | `2026-05-10-x` | — |\n"
    )
    gh = FakeGhClient()
    gh.remote_files = {("derio-net/other", "docs/superpowers/implemented/plans/2026-05-10-x")}
    implemented, note = _spec_fully_implemented(spec, tmp_path, gh)
    assert implemented, note


def test_migrate_dirs_repairs_stale_refs_in_passing(tmp_path, monkeypatch):
    """`fr migrate dirs --yes` normalizes refs after relocating the legacy
    tree — the repo converges in one operation."""
    import subprocess

    from fr.cli import app
    from typer.testing import CliRunner

    sp = tmp_path / "docs" / "superpowers"
    (sp / "plans").mkdir(parents=True)
    (sp / "specs").mkdir()
    legacy_plan = sp / "archived-plans" / "2026-05-10-old"
    legacy_plan.mkdir(parents=True)
    (legacy_plan / "_meta.yaml").write_text(
        "schema_version: 2\nplan: 2026-05-10-old\n"
        "target_repo: derio-net/test\nvk_version: '>=1.0.0,<3.0.0'\ncreated: 2026-05-10\n"
    )
    spec = sp / "specs" / "2026-05-10-spec.md"
    spec.write_text(
        "# S\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|---|---|---|---|\n"
        "| Old | `derio-net/test` | `docs/superpowers/archived-plans/2026-05-10-old/` | — |\n"
    )
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    result = CliRunner().invoke(app, ["migrate", "dirs", "--yes"])
    assert result.exit_code == 0, result.output
    # the spec may itself have been swept to implemented/specs/
    moved_spec = sp / "implemented" / "specs" / spec.name
    text = (moved_spec if moved_spec.exists() else spec).read_text()
    assert "| `2026-05-10-old` |" in text
    assert "archived-plans" not in text


# --- plan-config dead-key stripping during migration (2026-06-16 cleanup) ----

_DEAD_PLAN_CONFIG = (
    'plan:\n  filename: "YYYY-MM-DD-{name}.md"\n  save_to: docs/superpowers/plans/\n\n'
    "dispatch:\n  target: github-issues\n  owner: derio-net\n\n"
    "header:\n  required:\n    - Status\n"
)


def test_migrate_apply_strips_plan_config_dead_keys(tmp_path):
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-x")
    cfg = repo / "docs" / "superpowers" / "plan-config.yaml"
    cfg.write_text(_DEAD_PLAN_CONFIG)

    outcomes = migrate_repo(repo, dry_run=False, target_repo="derio-net/test")

    text = cfg.read_text()
    assert "save_to" not in text and "dispatch:" not in text
    assert 'filename: "YYYY-MM-DD-{name}.md"' in text  # live key intact
    assert any("plan-config" in o.reason for o in outcomes)


def test_migrate_dry_run_reports_plan_config_without_writing(tmp_path):
    from fr.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-x")
    cfg = repo / "docs" / "superpowers" / "plan-config.yaml"
    cfg.write_text(_DEAD_PLAN_CONFIG)

    outcomes = migrate_repo(repo, dry_run=True, target_repo="derio-net/test")

    assert cfg.read_text() == _DEAD_PLAN_CONFIG  # untouched on dry-run
    assert any("plan-config" in o.reason for o in outcomes)


# ── 2026-07-05 spec-sweep slice guard (#351): pending-slice rows hold a spec ──


def test_is_pending_placeholder():
    """The recognizer: a File cell whose first token is `pending`/`tbd`
    (case-insensitive, word-bounded) marks a decided-but-unbuilt slice."""
    from fr.migrate import _is_pending_placeholder

    for cell in (
        "pending",
        "PENDING",
        "Pending",
        "tbd",
        "TBD",
        "pending — no plan yet",
        "pending (slice B)",
    ):
        assert _is_pending_placeholder(cell), cell
    for cell in (
        "—",
        "-",
        "",
        "2026-05-10-x",
        "docs/superpowers/plans/2026-05-10-x/",
        "pendingish",  # word boundary: must NOT match
        "depending",
        # A real plan slug beginning with the token is NOT a placeholder: the
        # rule is "the first whitespace-delimited token is exactly pending/tbd",
        # so a hyphen/slug continuation disqualifies it (review #351).
        "pending-cleanup",
        "tbd-foo",
        "pending/x",
    ):
        assert not _is_pending_placeholder(cell), cell


def _sliced_spec(tmp_path, *, pending_repo="derio-net/other"):
    """A spec whose rows are one archived plan + one pending slice."""
    sp = tmp_path / "docs" / "superpowers"
    (sp / "specs").mkdir(parents=True)
    (sp / "implemented" / "plans" / "2026-07-01-a").mkdir(parents=True)
    (sp / "implemented" / "plans" / "2026-07-01-a" / "_meta.yaml").write_text(
        "schema_version: 2\nplan: 2026-07-01-a\n"
    )
    spec = sp / "specs" / "2026-07-01-sliced.md"
    spec.write_text(
        "# Sliced\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n|---|---|---|---|\n"
        "| Slice A | `derio-net/super-fr` | "
        "`docs/superpowers/implemented/plans/2026-07-01-a/` | — |\n"
        f"| Slice B | `{pending_repo}` | `pending` | — |\n"
    )
    return spec


def test_spec_fully_implemented_pending_row_holds(tmp_path):
    """A pending-placeholder row holds the spec with a clear 'pending' note —
    NOT the misleading 'unresolved locally' branch (the guard precedes
    resolution)."""
    from fr.migrate import _spec_fully_implemented

    spec = _sliced_spec(tmp_path)
    implemented, note = _spec_fully_implemented(spec, tmp_path, None)
    assert implemented is False
    assert note is not None
    assert "pending" in note.lower()
    assert "Slice B" in note
    assert "unresolved locally" not in note


def test_spec_fully_implemented_pending_deterministic_with_gh(tmp_path):
    """The hold never reaches the gh contents probe — deterministic offline,
    on outage, and for cross-repo cells."""
    from fr.migrate import _spec_fully_implemented

    from tests.unit.fakes import FakeGhClient

    spec = _sliced_spec(tmp_path, pending_repo="derio-net/other")
    gh = FakeGhClient()  # no remote_files preloaded
    implemented, note = _spec_fully_implemented(spec, tmp_path, gh)
    assert implemented is False
    assert "pending" in (note or "").lower()
    # No gh probe was made for the pending row.
    assert not any(c[0] == "file_exists" for c in gh.calls)


def test_spec_fully_implemented_no_pending_row_still_sweeps(tmp_path):
    """Regression: a spec whose rows are all archived (no pending row) still
    qualifies — this change is a pure superset."""
    from fr.migrate import _spec_fully_implemented

    sp = tmp_path / "docs" / "superpowers"
    (sp / "specs").mkdir(parents=True)
    (sp / "implemented" / "plans" / "2026-07-01-a").mkdir(parents=True)
    (sp / "implemented" / "plans" / "2026-07-01-a" / "_meta.yaml").write_text(
        "schema_version: 2\nplan: 2026-07-01-a\n"
    )
    spec = sp / "specs" / "2026-07-01-done.md"
    spec.write_text(
        "# Done\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n|---|---|---|---|\n"
        "| Slice A | `derio-net/super-fr` | "
        "`docs/superpowers/implemented/plans/2026-07-01-a/` | — |\n"
    )
    assert _spec_fully_implemented(spec, tmp_path, None) == (True, None)


def test_spec_archive_sweep_holds_pending_spec(tmp_path):
    """Integration: the sweep leaves a pending-slice spec in place and reports
    a note; it does not appear in moves."""
    from fr.archive import spec_archive_sweep

    from tests.unit.fakes import FakeGhClient

    _sliced_spec(tmp_path)  # archived row + pending Slice B
    result = spec_archive_sweep(tmp_path, FakeGhClient())
    assert all("2026-07-01-sliced.md" not in str(m.src) for m in result.moves)
    assert any("pending" in n.lower() and "2026-07-01-sliced" in n for n in result.notes)
    # still on disk under specs/
    assert (tmp_path / "docs" / "superpowers" / "specs" / "2026-07-01-sliced.md").is_file()


def test_migrate_dirs_holds_pending_spec(tmp_path, monkeypatch):
    """`fr migrate dirs` shares `_spec_fully_implemented`, so a pending-slice
    spec is held from the sweep there too (not moved to implemented/specs/).

    Regression-lock, not a red-first test: a `pending` cell already failed
    resolution on baseline (via the misleading "unresolved locally" branch),
    so the "not moved" assertion held before this change too. It pins that
    `migrate dirs` keeps honoring the hold; the discriminating red-first
    assertions (clean note, no gh probe) live in the `_spec_fully_implemented`
    unit tests above.
    """
    import subprocess

    from fr.cli import app
    from typer.testing import CliRunner

    _sliced_spec(tmp_path)  # archived row + pending Slice B
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True, exist_ok=True)
    for cmd in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    result = CliRunner().invoke(app, ["migrate", "dirs", "--yes"])
    assert result.exit_code == 0, result.output
    sp = tmp_path / "docs" / "superpowers"
    assert (sp / "specs" / "2026-07-01-sliced.md").is_file()
    assert not (sp / "implemented" / "specs" / "2026-07-01-sliced.md").exists()
