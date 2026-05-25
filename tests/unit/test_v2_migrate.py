"""Tests for vk.migrate — v1-to-v2 mechanical sweep."""

from __future__ import annotations

from pathlib import Path

import pytest


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "archived-plans").mkdir()
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
    from vk.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    md = _write_v1_plan(repo, slug="2026-05-10-fixture-v1")

    outcomes = migrate_repo(repo, dry_run=True, target_repo="derio-net/test")
    assert len(outcomes) == 1
    assert outcomes[0].reason == "migrated (dry run)"
    # Original .md still in place; no folder created
    assert md.exists()
    assert not (repo / "docs" / "superpowers" / "plans" / "2026-05-10-fixture-v1").exists()


def test_migrate_apply_creates_v2_folder_and_archives_md(tmp_path):
    from vk import parse
    from vk.migrate import migrate_repo

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
    from vk.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-complete", status="Complete")
    _write_v1_plan(repo, slug="2026-05-10-in-progress", status="In Progress")

    outcomes = migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    by_name = {o.plan_path.stem: o.reason for o in outcomes}
    assert by_name["2026-05-10-complete"] == "migrated"
    assert by_name["2026-05-10-in-progress"].startswith("skipped (in-progress")


def test_migrate_include_in_progress_flag(tmp_path):
    from vk.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-in-progress", status="In Progress")

    outcomes = migrate_repo(
        repo, dry_run=False, include_in_progress=True, target_repo="derio-net/test"
    )
    assert outcomes[0].reason == "migrated"


def test_migrate_rewrites_spec_table_drops_status_column(tmp_path):
    from vk.migrate import migrate_repo

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
    from vk.migrate import migrate_repo

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
    from vk.migrate import migrate_repo

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
    from vk.migrate import MigrationError, migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="legacy-plan-no-date")

    with pytest.raises(MigrationError, match="YYYY-MM-DD"):
        migrate_repo(repo, dry_run=False, target_repo="derio-net/test")


def test_migrate_preserves_freeform_track(tmp_path):
    """Origin table 'Track' cells with non-canonical values are preserved verbatim."""
    from vk import parse
    from vk.migrate import migrate_repo

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
    from vk import parse
    from vk.migrate import migrate_repo

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
    from vk import parse
    from vk.migrate import migrate_repo

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
    from vk.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-already")
    # Pre-create the v2 folder to simulate prior migration
    (repo / "docs" / "superpowers" / "plans" / "2026-05-10-already").mkdir()

    outcomes = migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    assert outcomes[0].reason.startswith("skipped (folder already exists)")


def test_migrate_rejects_per_phase_target_repo_conflict(tmp_path):
    """v1 plan with conflicting target_repo across phases → MigrationError."""
    from vk.migrate import MigrationError, migrate_repo

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
    from typer.testing import CliRunner

    from vk.cli import app

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
    from vk import parse
    from vk.migrate import migrate_repo

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
    from typer.testing import CliRunner

    from vk.cli import app

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
    from vk import parse
    from vk.migrate import migrate_repo

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
    from vk import parse
    from vk.migrate import migrate_repo

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
    from vk import parse
    from vk.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-step-subsections.md"
    p.write_text(
        "# Step Subsections\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 0: Bootstrap [agentic]\n"
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
    from vk import parse
    from vk.migrate import migrate_repo

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
    from vk.migrate import migrate_repo

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
    from vk import parse
    from vk.migrate import migrate_repo

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
    from vk import parse
    from vk.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = repo / "docs" / "superpowers" / "plans" / "2026-05-10-fenced-examples.md"
    p.write_text(
        "# Fenced Examples\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 0: Documentation [agentic]\n"
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
    from vk.migrate import migrate_repo

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
    from vk.migrate import MigrationError, migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-no-target")  # helper declares no target

    with pytest.raises(MigrationError, match="--target-repo"):
        migrate_repo(repo, dry_run=False)


def test_migrate_uses_explicit_target_repo(tmp_path):
    """#245 Bug 1: an explicit target_repo is honored (and recorded in meta)."""
    from vk import parse
    from vk.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-with-flag")

    migrate_repo(repo, dry_run=False, target_repo="derio-net/frank")
    plan = parse(_plans(repo) / "2026-05-10-with-flag")
    assert plan.meta.target_repo == "derio-net/frank"


def test_migrate_recovers_prose_depends_on(tmp_path):
    """#245 Bug 2: a '## Dependencies' / 'Blocked by Phase N' prose convention
    is recovered into depends_on instead of being flattened to []."""
    from vk import parse
    from vk.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = _plans(repo) / "2026-05-10-prose-deps.md"
    p.write_text(
        "# Prose Deps\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 0: Bootstrap [agentic]\n"
        "**Depends on:** —\n\n"
        "### Task 1: t\n\n- [x] **Step 1: x** d.\n\n"
        "## Phase 1: Build [agentic]\n\n"
        "### Task 1: t\n\n- [x] **Step 1: y** d.\n\n"
        "## Dependencies\n\n"
        "Blocked by Phase 0.\n"
    )

    outcomes = migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(_plans(repo) / "2026-05-10-prose-deps")
    deps = {ph.phase.number: list(ph.phase.depends_on) for ph in plan.phases}
    assert deps[1] == [0], deps
    # The recovery is surfaced as a warning so lossy migrations aren't silent.
    assert any("depends_on" in w.lower() for o in outcomes for w in o.warnings)


def test_migrate_recovers_multi_phase_prose_depends_on(tmp_path):
    """'Blocked by Phase 0 and 3' → depends_on == [0, 3]."""
    from vk import parse
    from vk.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    p = _plans(repo) / "2026-05-10-multi-prose-deps.md"
    p.write_text(
        "# Multi Prose Deps\n\n"
        "**Spec:** `docs/superpowers/specs/2026-05-10-test.md`\n"
        "**Status:** Complete\n\n"
        "## Phase 0: A [agentic]\n**Depends on:** —\n\n### Task 1: t\n\n- [x] **Step 1: a** d.\n\n"
        "## Phase 3: B [agentic]\n**Depends on:** —\n\n### Task 1: t\n\n- [x] **Step 1: b** d.\n\n"
        "## Phase 4: C [agentic]\n\n### Task 1: t\n\n- [x] **Step 1: c** d.\n\n"
        "## Dependencies\n\nBlocked by Phase 0 and 3.\n"
    )

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(_plans(repo) / "2026-05-10-multi-prose-deps")
    deps = {ph.phase.number: sorted(ph.phase.depends_on) for ph in plan.phases}
    assert deps[4] == [0, 3], deps


def test_migrate_preserves_task_intro_with_manual_operation_block(tmp_path):
    """#245 Bug 3: task intro prose + a fenced `# manual-operation` block before
    the first step must survive even when the task HAS parsed steps."""
    from vk import parse
    from vk.migrate import migrate_repo

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
    from vk import parse
    from vk.migrate import migrate_repo

    repo = _make_repo(tmp_path)
    _write_v1_plan(repo, slug="2026-05-10-vkver")

    migrate_repo(repo, dry_run=False, target_repo="derio-net/test")
    plan = parse(_plans(repo) / "2026-05-10-vkver")
    assert plan.meta.vk_version == ">=2.0.0,<3.0.0"
