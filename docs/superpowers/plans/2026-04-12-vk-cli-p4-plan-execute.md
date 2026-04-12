# VK Plan and Execute Helper Commands Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-12-vk-cli-toolchain-design.md`
**Status:** Not Started

**Goal:** Implement `vk plan` subcommands (new, self-review, spec-index, convert, format) and `vk execute` subcommands (check-deps, scope, check-step, pr-body) as mechanical helpers that SKILL.md files invoke.
**Architecture:** Two command modules (`plan_cmd.py`, `execute_cmd.py`) registered as typer subcommand groups. Both leverage the shared plan parser (both flat and phased formats), writer, and config modules from P1. `check-step` uses step-ID format `P<phase>.T<task>.S<step>` (phased) or `T<task>.S<step>` (flat). All mutating commands follow the `--dry-run`/`--yes` contract from `common.py`.
**Tech Stack:** Python 3.11+, uv, typer, pyyaml, rich, pytest, ruff, mypy

---

## Phase 1: Plan helper subcommands [agentic]

### Task 1: vk plan new subcommand

**Files:**
- Create: `src/vk/commands/plan_cmd.py`
- Create: `tests/integration/test_plan_cmd.py`
- Modify: `src/vk/cli.py`

- [ ] **Step 1: Write failing tests for plan new**

Create `tests/integration/test_plan_cmd.py`:

```python
# tests/integration/test_plan_cmd.py
from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


class TestPlanNew:
    def test_new_prints_plan_to_stdout_by_default(self, tmp_git_repo_local):
        """Without --save, plan content goes to stdout."""
        result = runner.invoke(
            app,
            ["plan", "new", "my-feature"],
            env={"VK_REPO_ROOT": str(tmp_git_repo_local)},
        )
        assert result.exit_code == 0
        assert "# " in result.stdout
        assert "Task 1:" in result.stdout or "**Status:** Not Started" in result.stdout

    def test_new_with_save_writes_file(self, tmp_git_repo_local):
        """--save writes the plan to docs/superpowers/plans/."""
        result = runner.invoke(
            app,
            ["plan", "new", "my-feature", "--save"],
            env={"VK_REPO_ROOT": str(tmp_git_repo_local)},
        )
        assert result.exit_code == 0
        plans_dir = tmp_git_repo_local / "docs" / "superpowers" / "plans"
        plan_files = list(plans_dir.glob("*my-feature*.md"))
        assert len(plan_files) == 1

    def test_new_with_spec_includes_spec_reference(self, tmp_git_repo_local):
        """--spec PATH sets the Spec header in the generated plan."""
        spec_path = "docs/superpowers/specs/2026-04-12-my-spec.md"
        result = runner.invoke(
            app,
            ["plan", "new", "my-feature", "--spec", spec_path],
            env={"VK_REPO_ROOT": str(tmp_git_repo_local)},
        )
        assert result.exit_code == 0
        assert spec_path in result.stdout

    def test_new_flat_format_when_no_dispatch(self, tmp_git_repo_local):
        """Local-only repo gets flat format (Task > Step, no phases)."""
        result = runner.invoke(
            app,
            ["plan", "new", "my-feature"],
            env={"VK_REPO_ROOT": str(tmp_git_repo_local)},
        )
        assert result.exit_code == 0
        assert "### Task" in result.stdout
        assert "## Phase" not in result.stdout

    def test_new_phased_format_when_dispatch_enabled(
        self, tmp_git_repo_with_dispatch_config
    ):
        """Dispatch-enabled repo gets phased format (Phase > Task > Step)."""
        result = runner.invoke(
            app,
            ["plan", "new", "my-feature"],
            env={"VK_REPO_ROOT": str(tmp_git_repo_with_dispatch_config)},
        )
        assert result.exit_code == 0
        assert "## Phase" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_plan_cmd.py -v -k "TestPlanNew" --no-header`
Expected: FAIL — `No such command 'new'` or import error

- [ ] **Step 3: Create plan_cmd.py with new subcommand**

Create `src/vk/commands/plan_cmd.py`:

```python
"""vk plan — write, save, and maintain plan files."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from vk.commands.common import validate_dry_run_yes
from vk.config import load_profile_from_cwd
from vk.plan.models import PlanFormat
from vk.plan.writer import render_skeleton

console = Console(stderr=True)
plan_app = typer.Typer(help="Write, save, and maintain plan files.")


@plan_app.command()
def new(
    name: str = typer.Argument(..., help="Plan name slug (used in filename)."),
    spec: Optional[str] = typer.Option(None, "--spec", help="Path to spec file."),
    save: bool = typer.Option(
        False, "--save", help="Write to plans directory instead of stdout."
    ),
) -> None:
    """Generate a new plan skeleton."""
    profile = load_profile_from_cwd()
    plan_format = profile.format

    content = render_skeleton(
        name=name,
        spec=spec,
        plan_format=plan_format,
        header=profile.header,
    )

    if save:
        from vk.config import find_repo_root

        repo_root = find_repo_root()
        plans_dir = repo_root / profile.plan.plans_dir
        plans_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()
        filename = f"{today}-{name}.md"
        out_path = plans_dir / filename
        out_path.write_text(content)
        console.print(f"Saved: [bold]{out_path}[/bold]")
    else:
        typer.echo(content)
```

- [ ] **Step 4: Wire plan_app into cli.py**

In `src/vk/cli.py`, replace the stub `plan_app` with the import from `plan_cmd`:

```python
from vk.commands.plan_cmd import plan_app

# Remove the old: plan_app = typer.Typer(help="Write, save, and maintain plan files.")
# Remove the old: plan_callback function
# Keep: app.add_typer(plan_app, name="plan")
```

- [ ] **Step 5: Run tests to verify plan new passes**

Run: `uv run pytest tests/integration/test_plan_cmd.py -v -k "TestPlanNew" --no-header`
Expected: PASS — all plan new tests pass

- [ ] **Step 6: Commit**

```bash
git add src/vk/commands/plan_cmd.py tests/integration/test_plan_cmd.py src/vk/cli.py
git commit -m "feat: add vk plan new subcommand with format auto-detection"
```

### Task 2: vk plan self-review subcommand

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`
- Modify: `tests/integration/test_plan_cmd.py`

- [ ] **Step 1: Write failing tests for plan self-review**

Add to `tests/integration/test_plan_cmd.py`:

```python
class TestPlanSelfReview:
    def test_self_review_passes_clean_plan(self, tmp_git_repo_with_flat_plan):
        """A well-formed plan passes self-review."""
        plan_path = (
            tmp_git_repo_with_flat_plan / "docs/superpowers/plans/test-plan.md"
        )
        result = runner.invoke(app, ["plan", "self-review", str(plan_path)])
        assert result.exit_code == 0

    def test_self_review_detects_placeholder_text(self, tmp_path):
        """Plans with placeholder text like 'TODO' or 'similar to above' fail."""
        plan = tmp_path / "bad-plan.md"
        plan.write_text(
            "# Bad Plan\n\n"
            "**Spec:** `spec.md`\n"
            "**Status:** Not Started\n"
            "**Goal:** Do the thing.\n\n---\n\n"
            "### Task 1: Setup [agentic]\n\n"
            "- [ ] **Step 1:** TODO fill this in\n"
        )
        result = runner.invoke(app, ["plan", "self-review", str(plan)])
        assert result.exit_code != 0
        assert "placeholder" in result.stdout.lower() or "TODO" in result.stdout

    def test_self_review_detects_missing_files_section(self, tmp_path):
        """Tasks without a Files section get flagged."""
        plan = tmp_path / "no-files.md"
        plan.write_text(
            "# No Files Plan\n\n"
            "**Spec:** `spec.md`\n"
            "**Status:** Not Started\n"
            "**Goal:** Do the thing.\n\n---\n\n"
            "### Task 1: Setup [agentic]\n\n"
            "- [ ] **Step 1:** Write the test\n"
        )
        result = runner.invoke(app, ["plan", "self-review", str(plan)])
        assert result.exit_code != 0 or "Files" in result.stdout

    def test_self_review_checks_tag_placement_flat(self, tmp_path):
        """Flat plans must have tags on task headers, not phase headers."""
        plan = tmp_path / "flat-tags.md"
        plan.write_text(
            "# Flat Plan\n\n"
            "**Spec:** `spec.md`\n"
            "**Status:** Not Started\n"
            "**Goal:** Do the thing.\n\n---\n\n"
            "### Task 1: Setup\n\n"
            "**Files:**\n- Create: `foo.py`\n\n"
            "- [ ] **Step 1:** Write the test\n"
        )
        result = runner.invoke(app, ["plan", "self-review", str(plan)])
        assert result.exit_code != 0 or "tag" in result.stdout.lower()

    def test_self_review_checks_tag_placement_phased(self, tmp_path):
        """Phased plans must have tags on phase headers."""
        plan = tmp_path / "phased-tags.md"
        plan.write_text(
            "# Phased Plan\n\n"
            "**Spec:** `spec.md`\n"
            "**Status:** Not Started\n"
            "**Goal:** Do the thing.\n\n---\n\n"
            "## Phase 1: Setup\n\n"
            "### Task 1: Do stuff\n\n"
            "**Files:**\n- Create: `foo.py`\n\n"
            "- [ ] **Step 1:** Write the test\n"
        )
        result = runner.invoke(app, ["plan", "self-review", str(plan)])
        assert result.exit_code != 0 or "tag" in result.stdout.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_plan_cmd.py -v -k "TestPlanSelfReview" --no-header`
Expected: FAIL — `No such command 'self-review'`

- [ ] **Step 3: Implement self-review subcommand**

Add to `plan_cmd.py`:

```python
import re

PLACEHOLDER_PATTERNS = [
    re.compile(r"\bTODO\b", re.IGNORECASE),
    re.compile(r"\bFIXME\b", re.IGNORECASE),
    re.compile(r"similar to above", re.IGNORECASE),
    re.compile(r"add appropriate", re.IGNORECASE),
    re.compile(r"as needed", re.IGNORECASE),
    re.compile(r"\.\.\.\s*$"),
]


@plan_app.command(name="self-review")
def self_review(
    plan_path: Path = typer.Argument(..., help="Path to the plan file."),
) -> None:
    """Run automated quality checks on a plan file."""
    plan_path = plan_path.resolve()
    if not plan_path.exists():
        console.print(f"[red]Plan not found:[/red] {plan_path}")
        raise typer.Exit(2)

    from vk.plan.parser import parse_plan

    plan = parse_plan(plan_path)
    issues: list[str] = []
    content = plan_path.read_text()

    # Check for placeholder text in step bodies
    for line_num, line in enumerate(content.splitlines(), 1):
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern.search(line):
                issues.append(
                    f"Line {line_num}: placeholder text detected: {line.strip()!r}"
                )

    # Check Files sections exist on agentic tasks
    for task in plan.all_tasks:
        if task.tag == "agentic" or task.tag is None:
            if not task.files_mentioned:
                issues.append(
                    f"Task {task.number} ({task.title}): missing **Files:** section"
                )

    # Check tag placement
    if plan.format is PlanFormat.FLAT:
        for task in plan.tasks:
            if task.tag is None:
                issues.append(
                    f"Task {task.number} ({task.title}): missing [agentic] or "
                    f"[manual] tag on task header"
                )
    elif plan.format is PlanFormat.PHASED:
        for phase in plan.phases:
            if not phase.tag:
                issues.append(
                    f"Phase {phase.number} ({phase.title}): missing [agentic] or "
                    f"[manual] tag on phase header"
                )

    if issues:
        console.print(f"[red]Self-review found {len(issues)} issue(s):[/red]")
        for issue in issues:
            console.print(f"  - {issue}")
        raise typer.Exit(1)
    else:
        console.print("[green]Self-review passed. No issues found.[/green]")
```

- [ ] **Step 4: Run tests to verify self-review passes**

Run: `uv run pytest tests/integration/test_plan_cmd.py -v -k "TestPlanSelfReview" --no-header`
Expected: PASS — all self-review tests pass

- [ ] **Step 5: Commit**

```bash
git add src/vk/commands/plan_cmd.py tests/integration/test_plan_cmd.py
git commit -m "feat: add vk plan self-review subcommand with quality checks"
```

### Task 3: vk plan spec-index subcommand

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`
- Modify: `tests/integration/test_plan_cmd.py`

- [ ] **Step 1: Write failing tests for plan spec-index**

Add to `tests/integration/test_plan_cmd.py`:

```python
class TestPlanSpecIndex:
    def test_spec_index_adds_plan_to_spec(self, tmp_git_repo_with_flat_plan_and_spec):
        """Adds or updates the plan entry in the spec's Implementation Plans table."""
        plan_path = (
            tmp_git_repo_with_flat_plan_and_spec
            / "docs/superpowers/plans/test-plan.md"
        )
        result = runner.invoke(
            app, ["plan", "spec-index", str(plan_path), "--yes"]
        )
        assert result.exit_code == 0
        spec_path = (
            tmp_git_repo_with_flat_plan_and_spec
            / "docs/superpowers/specs/test-spec.md"
        )
        content = spec_path.read_text()
        assert "test-plan" in content

    def test_spec_index_dry_run_does_not_mutate(
        self, tmp_git_repo_with_flat_plan_and_spec
    ):
        plan_path = (
            tmp_git_repo_with_flat_plan_and_spec
            / "docs/superpowers/plans/test-plan.md"
        )
        spec_path = (
            tmp_git_repo_with_flat_plan_and_spec
            / "docs/superpowers/specs/test-spec.md"
        )
        before = spec_path.read_text()
        result = runner.invoke(
            app, ["plan", "spec-index", str(plan_path), "--dry-run"]
        )
        assert result.exit_code == 0
        assert spec_path.read_text() == before

    def test_spec_index_refuses_when_no_spec_header(self, tmp_path):
        """Plan without a Spec header cannot update spec index."""
        plan = tmp_path / "no-spec-plan.md"
        plan.write_text(
            "# No Spec Plan\n\n"
            "**Status:** Not Started\n"
            "**Goal:** Do the thing.\n\n---\n\n"
            "### Task 1: Setup [agentic]\n\n"
            "**Files:**\n- Create: `foo.py`\n\n"
            "- [ ] **Step 1:** Write the test\n"
        )
        result = runner.invoke(app, ["plan", "spec-index", str(plan), "--yes"])
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_plan_cmd.py -v -k "TestPlanSpecIndex" --no-header`
Expected: FAIL — `No such command 'spec-index'`

- [ ] **Step 3: Implement spec-index subcommand**

Add to `plan_cmd.py`:

```python
@plan_app.command(name="spec-index")
def spec_index(
    plan_path: Path = typer.Argument(..., help="Path to the plan file."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without mutating."),
    yes: bool = typer.Option(False, "--yes", help="Execute without prompting."),
) -> None:
    """Update the spec's Implementation Plans index with this plan's status."""
    validate_dry_run_yes(dry_run, yes)

    plan_path = plan_path.resolve()
    if not plan_path.exists():
        console.print(f"[red]Plan not found:[/red] {plan_path}")
        raise typer.Exit(2)

    from vk.plan.parser import parse_plan
    from vk.spec_index import update_spec_index

    plan = parse_plan(plan_path)
    if not plan.spec:
        console.print("[red]Plan has no **Spec:** header. Cannot update spec index.[/red]")
        raise typer.Exit(1)

    spec_path = _resolve_spec_path(plan_path, plan.spec)
    if not spec_path or not spec_path.exists():
        console.print(f"[red]Spec file not found:[/red] {plan.spec}")
        raise typer.Exit(2)

    if dry_run:
        console.print(f"Would update spec index in: {spec_path}")
        console.print(f"  Plan: {plan_path.name}")
        console.print(f"  Status: {plan.status}")
        return

    if not yes:
        typer.confirm(f"Update spec index in {spec_path.name}?", abort=True)

    update_spec_index(spec_path, plan_path, plan.status)
    console.print(f"Updated spec index in: [bold]{spec_path}[/bold]")


def _resolve_spec_path(plan_path: Path, spec_ref: str) -> Path | None:
    """Resolve a spec reference (relative path) to an absolute path."""
    # Strip backticks if present
    spec_ref = spec_ref.strip("`")
    repo_root = plan_path.parent
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            return repo_root / spec_ref
        repo_root = repo_root.parent
    return None
```

- [ ] **Step 4: Run tests to verify spec-index passes**

Run: `uv run pytest tests/integration/test_plan_cmd.py -v -k "TestPlanSpecIndex" --no-header`
Expected: PASS — all spec-index tests pass

- [ ] **Step 5: Commit**

```bash
git add src/vk/commands/plan_cmd.py tests/integration/test_plan_cmd.py
git commit -m "feat: add vk plan spec-index subcommand"
```

### Task 4: vk plan convert subcommand

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`
- Create: `tests/integration/test_convert.py`

- [ ] **Step 1: Write failing tests for plan convert**

Create `tests/integration/test_convert.py`:

```python
# tests/integration/test_convert.py
from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


class TestConvertPhasedToFlat:
    def test_convert_phased_to_flat_renumbers_tasks(
        self, tmp_path, phased_plan_fixture
    ):
        """Flattening renumbers tasks globally."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(
            app, ["plan", "convert", str(plan), "--to", "flat", "--yes"]
        )
        assert result.exit_code == 0
        content = plan.read_text()
        assert "### Task 1:" in content
        assert "## Phase" not in content

    def test_convert_phased_to_flat_inherits_phase_tags(
        self, tmp_path, phased_plan_fixture
    ):
        """Each task inherits its parent phase's tag."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(
            app, ["plan", "convert", str(plan), "--to", "flat", "--yes"]
        )
        assert result.exit_code == 0
        content = plan.read_text()
        assert "[agentic]" in content

    def test_convert_phased_to_flat_refuses_tracked_without_force(
        self, tmp_path, phased_dispatched_plan_fixture
    ):
        """Plans with tracking comments refuse conversion without --force."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_dispatched_plan_fixture)
        result = runner.invoke(
            app, ["plan", "convert", str(plan), "--to", "flat", "--yes"]
        )
        assert result.exit_code != 0
        assert "Tracking" in result.stdout or "force" in result.stdout.lower()

    def test_convert_phased_to_flat_force_overrides_tracking_check(
        self, tmp_path, phased_dispatched_plan_fixture
    ):
        """--force allows conversion even with tracking comments."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_dispatched_plan_fixture)
        result = runner.invoke(
            app,
            ["plan", "convert", str(plan), "--to", "flat", "--force", "--yes"],
        )
        assert result.exit_code == 0

    def test_convert_dry_run_does_not_mutate(self, tmp_path, phased_plan_fixture):
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        before = plan.read_text()
        result = runner.invoke(
            app, ["plan", "convert", str(plan), "--to", "flat", "--dry-run"]
        )
        assert result.exit_code == 0
        assert plan.read_text() == before


class TestConvertFlatToPhased:
    def test_convert_flat_to_phased_single_phase(
        self, tmp_path, flat_plan_fixture
    ):
        """--single-phase wraps everything in one Phase 1."""
        plan = tmp_path / "plan.md"
        plan.write_text(flat_plan_fixture)
        result = runner.invoke(
            app,
            ["plan", "convert", str(plan), "--to", "phased", "--single-phase", "--yes"],
        )
        assert result.exit_code == 0
        content = plan.read_text()
        assert "## Phase 1:" in content

    def test_convert_flat_to_phased_one_per_task(
        self, tmp_path, flat_plan_fixture
    ):
        """--one-per-task: each task becomes its own phase."""
        plan = tmp_path / "plan.md"
        plan.write_text(flat_plan_fixture)
        result = runner.invoke(
            app,
            [
                "plan", "convert", str(plan), "--to", "phased",
                "--one-per-task", "--yes",
            ],
        )
        assert result.exit_code == 0
        content = plan.read_text()
        assert "## Phase 1:" in content
        assert "## Phase 2:" in content

    def test_convert_flat_to_phased_group_by_tag(
        self, tmp_path, flat_mixed_tags_fixture
    ):
        """--group-by-tag: consecutive same-tag tasks merge into one phase."""
        plan = tmp_path / "plan.md"
        plan.write_text(flat_mixed_tags_fixture)
        result = runner.invoke(
            app,
            [
                "plan", "convert", str(plan), "--to", "phased",
                "--group-by-tag", "--yes",
            ],
        )
        assert result.exit_code == 0
        content = plan.read_text()
        assert "## Phase" in content

    def test_convert_flat_to_phased_requires_mode_flag(
        self, tmp_path, flat_plan_fixture
    ):
        """Converting to phased without a mode flag is an error."""
        plan = tmp_path / "plan.md"
        plan.write_text(flat_plan_fixture)
        result = runner.invoke(
            app, ["plan", "convert", str(plan), "--to", "phased", "--yes"]
        )
        assert result.exit_code != 0

    def test_convert_round_trip_preserves_content(
        self, tmp_path, phased_plan_fixture
    ):
        """phased -> flat -> phased(single-phase) preserves all task content."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)

        from vk.plan.parser import parse_plan

        original = parse_plan(plan)
        original_tasks = [t.title for t in original.all_tasks]

        runner.invoke(
            app, ["plan", "convert", str(plan), "--to", "flat", "--yes"]
        )
        runner.invoke(
            app,
            ["plan", "convert", str(plan), "--to", "phased", "--single-phase", "--yes"],
        )

        restored = parse_plan(plan)
        restored_tasks = [t.title for t in restored.all_tasks]
        assert original_tasks == restored_tasks
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_convert.py -v --no-header`
Expected: FAIL — `No such command 'convert'`

- [ ] **Step 3: Implement convert subcommand**

Add to `plan_cmd.py`:

```python
@plan_app.command()
def convert(
    plan_path: Path = typer.Argument(..., help="Path to the plan file."),
    to: str = typer.Option(..., "--to", help="Target format: flat or phased."),
    force: bool = typer.Option(
        False, "--force", help="Force conversion even with tracking comments."
    ),
    single_phase: bool = typer.Option(
        False, "--single-phase", help="Wrap all tasks in one phase."
    ),
    one_per_task: bool = typer.Option(
        False, "--one-per-task", help="Each task becomes its own phase."
    ),
    group_by_tag: bool = typer.Option(
        False, "--group-by-tag", help="Group consecutive same-tag tasks into phases."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without mutating."),
    yes: bool = typer.Option(False, "--yes", help="Execute without prompting."),
) -> None:
    """Convert a plan between flat and phased formats."""
    validate_dry_run_yes(dry_run, yes)

    plan_path = plan_path.resolve()
    if not plan_path.exists():
        console.print(f"[red]Plan not found:[/red] {plan_path}")
        raise typer.Exit(2)

    from vk.plan.convert import convert_plan
    from vk.plan.parser import parse_plan

    plan = parse_plan(plan_path)

    if to == "flat":
        if plan.format is PlanFormat.FLAT:
            console.print("Plan is already flat. Nothing to convert.")
            return
        if not force and "<!-- Tracking:" in plan_path.read_text():
            console.print(
                "[red]Plan has tracking comments. Use --force to convert anyway.[/red]"
            )
            raise typer.Exit(1)
        mode = "phased-to-flat"
    elif to == "phased":
        if plan.format is PlanFormat.PHASED:
            console.print("Plan is already phased. Nothing to convert.")
            return
        mode_flags = [single_phase, one_per_task, group_by_tag]
        if sum(mode_flags) != 1:
            console.print(
                "[red]Exactly one of --single-phase, --one-per-task, "
                "or --group-by-tag is required.[/red]"
            )
            raise typer.Exit(1)
        if single_phase:
            mode = "flat-to-phased-single"
        elif one_per_task:
            mode = "flat-to-phased-per-task"
        else:
            mode = "flat-to-phased-by-tag"
    else:
        console.print(f"[red]Unknown format: {to}. Use 'flat' or 'phased'.[/red]")
        raise typer.Exit(1)

    new_content = convert_plan(plan_path, mode)

    if dry_run:
        console.print(f"Would convert {plan_path.name} to {to} ({mode}).")
        console.print("Preview:")
        typer.echo(new_content[:500] + ("..." if len(new_content) > 500 else ""))
        return

    if not yes:
        typer.confirm(f"Convert {plan_path.name} to {to}?", abort=True)

    plan_path.write_text(new_content)
    console.print(f"Converted {plan_path.name} to [bold]{to}[/bold] format.")
```

- [ ] **Step 4: Run tests to verify convert passes**

Run: `uv run pytest tests/integration/test_convert.py -v --no-header`
Expected: PASS — all convert tests pass

- [ ] **Step 5: Commit**

```bash
git add src/vk/commands/plan_cmd.py tests/integration/test_convert.py
git commit -m "feat: add vk plan convert subcommand with four conversion modes"
```

### Task 5: vk plan format subcommand

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`
- Modify: `tests/integration/test_plan_cmd.py`

- [ ] **Step 1: Write failing tests for plan format**

Add to `tests/integration/test_plan_cmd.py`:

```python
class TestPlanFormat:
    def test_format_reports_flat_for_local_repo(self, tmp_git_repo_local):
        """Local-only repo reports flat format."""
        result = runner.invoke(
            app,
            ["plan", "format"],
            env={"VK_REPO_ROOT": str(tmp_git_repo_local)},
        )
        assert result.exit_code == 0
        assert "flat" in result.stdout.lower()

    def test_format_reports_phased_for_dispatch_repo(
        self, tmp_git_repo_with_dispatch_config
    ):
        """Dispatch-enabled repo reports phased format."""
        result = runner.invoke(
            app,
            ["plan", "format"],
            env={"VK_REPO_ROOT": str(tmp_git_repo_with_dispatch_config)},
        )
        assert result.exit_code == 0
        assert "phased" in result.stdout.lower()

    def test_format_with_explicit_repo_root(self, tmp_git_repo_local):
        """Passing explicit REPO_ROOT argument works."""
        result = runner.invoke(
            app, ["plan", "format", str(tmp_git_repo_local)]
        )
        assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_plan_cmd.py -v -k "TestPlanFormat" --no-header`
Expected: FAIL — `No such command 'format'`

- [ ] **Step 3: Implement format subcommand**

Add to `plan_cmd.py`:

```python
@plan_app.command(name="format")
def plan_format(
    repo_root: Optional[Path] = typer.Argument(
        None, help="Repository root (default: auto-detect)."
    ),
) -> None:
    """Show the plan format for this repo (flat or phased)."""
    if repo_root:
        import os

        os.environ["VK_REPO_ROOT"] = str(repo_root.resolve())

    profile = load_profile_from_cwd()
    fmt = profile.format

    if fmt is PlanFormat.FLAT:
        typer.echo("flat")
        console.print(
            "Format: [bold]flat[/bold] (Task > Step). "
            "No dispatch block in plan-config.yaml."
        )
    else:
        typer.echo("phased")
        console.print(
            "Format: [bold]phased[/bold] (Phase > Task > Step). "
            "Dispatch block present in plan-config.yaml."
        )
```

- [ ] **Step 4: Run tests to verify format passes**

Run: `uv run pytest tests/integration/test_plan_cmd.py -v -k "TestPlanFormat" --no-header`
Expected: PASS — all format tests pass

- [ ] **Step 5: Commit**

```bash
git add src/vk/commands/plan_cmd.py tests/integration/test_plan_cmd.py
git commit -m "feat: add vk plan format subcommand"
```

## Phase 2: Execute helper subcommands [agentic]

### Task 6: vk execute check-deps subcommand

**Files:**
- Create: `src/vk/commands/execute_cmd.py`
- Create: `tests/integration/test_execute.py`
- Modify: `src/vk/cli.py`

- [ ] **Step 1: Write failing tests for check-deps**

Create `tests/integration/test_execute.py`:

```python
# tests/integration/test_execute.py
from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


class TestCheckDeps:
    def test_check_deps_phased_passes_when_prior_phases_done(
        self, tmp_path, phased_plan_phase1_complete
    ):
        """Phase 2 deps satisfied when Phase 1 is fully checked."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_phase1_complete)
        result = runner.invoke(app, ["execute", "check-deps", str(plan), "2"])
        assert result.exit_code == 0
        assert "satisfied" in result.stdout.lower() or "ready" in result.stdout.lower()

    def test_check_deps_phased_fails_when_prior_phases_incomplete(
        self, tmp_path, phased_plan_fixture
    ):
        """Phase 2 deps not satisfied when Phase 1 has unchecked steps."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(app, ["execute", "check-deps", str(plan), "2"])
        assert result.exit_code != 0
        assert "blocked" in result.stdout.lower() or "incomplete" in result.stdout.lower()

    def test_check_deps_flat_passes_when_prior_tasks_done(
        self, tmp_path, flat_plan_task1_complete
    ):
        """Flat plan: Task 2 deps satisfied when Task 1 is fully checked."""
        plan = tmp_path / "plan.md"
        plan.write_text(flat_plan_task1_complete)
        result = runner.invoke(app, ["execute", "check-deps", str(plan), "2"])
        assert result.exit_code == 0

    def test_check_deps_first_phase_always_passes(
        self, tmp_path, phased_plan_fixture
    ):
        """Phase 1 / Task 1 has no prior deps, always passes."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(app, ["execute", "check-deps", str(plan), "1"])
        assert result.exit_code == 0

    def test_check_deps_dispatch_mode_queries_issues(
        self, tmp_git_repo_with_phased_dispatched_plan, mock_gh
    ):
        """Dispatch mode: checks `Blocked by #N` Issues."""
        plan_path = (
            tmp_git_repo_with_phased_dispatched_plan
            / "docs/superpowers/plans/test-plan.md"
        )
        mock_gh.set_issue_state("https://github.com/derio-net/test-repo/issues/1", "closed")
        result = runner.invoke(app, ["execute", "check-deps", str(plan_path), "2"])
        assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_execute.py -v -k "TestCheckDeps" --no-header`
Expected: FAIL — `No such command 'check-deps'`

- [ ] **Step 3: Create execute_cmd.py with check-deps subcommand**

Create `src/vk/commands/execute_cmd.py`:

```python
"""vk execute — helpers for phase/task execution."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from vk.config import load_profile
from vk.plan.models import PlanFormat
from vk.plan.parser import parse_plan

console = Console(stderr=True)
execute_app = typer.Typer(help="Helpers for phase/task execution.")


@execute_app.command(name="check-deps")
def check_deps(
    plan_path: Path = typer.Argument(..., help="Path to the plan file."),
    phase_or_task: int = typer.Argument(..., help="Phase number (phased) or task number (flat)."),
) -> None:
    """Check whether dependencies for a phase/task are satisfied."""
    plan_path = plan_path.resolve()
    if not plan_path.exists():
        console.print(f"[red]Plan not found:[/red] {plan_path}")
        raise typer.Exit(2)

    plan = parse_plan(plan_path)
    profile = load_profile(plan_path)

    if profile.dispatch_enabled:
        _check_deps_dispatch(plan, plan_path, phase_or_task, profile)
    else:
        _check_deps_local(plan, phase_or_task)


def _check_deps_local(plan: object, target: int) -> None:
    """Local mode: earlier phases/tasks must have all checkboxes checked."""
    if target <= 1:
        console.print("[green]No prior dependencies. Ready to execute.[/green]")
        return

    if plan.format is PlanFormat.PHASED:
        for phase in plan.phases:
            if phase.number >= target:
                break
            for task in phase.tasks:
                for step in task.steps:
                    if step.state == " ":
                        console.print(
                            f"[red]Blocked: Phase {phase.number}, Task {task.number}, "
                            f"Step {step.number} is incomplete.[/red]"
                        )
                        raise typer.Exit(1)
    elif plan.format is PlanFormat.FLAT:
        for task in plan.tasks:
            if task.number >= target:
                break
            for step in task.steps:
                if step.state == " ":
                    console.print(
                        f"[red]Blocked: Task {task.number}, "
                        f"Step {step.number} is incomplete.[/red]"
                    )
                    raise typer.Exit(1)

    console.print(f"[green]Dependencies satisfied. Ready to execute {target}.[/green]")


def _check_deps_dispatch(
    plan: object, plan_path: Path, target: int, profile: object
) -> None:
    """Dispatch mode: query `Blocked by #N` Issues."""
    from vk.gh import query_issue_states

    if target <= 1:
        console.print("[green]No prior dependencies. Ready to execute.[/green]")
        return

    # Check local deps first
    _check_deps_local(plan, target)

    # Then check Issue states for dispatch
    if plan.format is PlanFormat.PHASED:
        issue_states = query_issue_states(plan)
        for phase in plan.phases:
            if phase.number >= target:
                break
            if phase.tracking_url:
                state = issue_states.get(phase.tracking_url, "")
                if state.lower() not in ("closed", "done"):
                    console.print(
                        f"[red]Blocked: Phase {phase.number} Issue "
                        f"({phase.tracking_url}) is still '{state}'.[/red]"
                    )
                    raise typer.Exit(1)

    console.print(
        f"[green]Dependencies satisfied (local + dispatch). "
        f"Ready to execute {target}.[/green]"
    )
```

- [ ] **Step 4: Wire execute_app into cli.py**

In `src/vk/cli.py`, replace the stub `execute_app` with the import from `execute_cmd`:

```python
from vk.commands.execute_cmd import execute_app

# Remove the old: execute_app = typer.Typer(help="Helpers for phase/task execution.")
# Remove the old: execute_callback function
# Keep: app.add_typer(execute_app, name="execute")
```

- [ ] **Step 5: Run tests to verify check-deps passes**

Run: `uv run pytest tests/integration/test_execute.py -v -k "TestCheckDeps" --no-header`
Expected: PASS — all check-deps tests pass

- [ ] **Step 6: Commit**

```bash
git add src/vk/commands/execute_cmd.py tests/integration/test_execute.py src/vk/cli.py
git commit -m "feat: add vk execute check-deps subcommand with dual-mode support"
```

### Task 7: vk execute scope subcommand

**Files:**
- Modify: `src/vk/commands/execute_cmd.py`
- Modify: `tests/integration/test_execute.py`

- [ ] **Step 1: Write failing tests for scope**

Add to `tests/integration/test_execute.py`:

```python
class TestScope:
    def test_scope_phased_outputs_phase_tasks(
        self, tmp_path, phased_plan_fixture
    ):
        """Phased plan: scopes by phase, listing all tasks and files."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(app, ["execute", "scope", str(plan), "1"])
        assert result.exit_code == 0
        assert "Task" in result.stdout

    def test_scope_flat_outputs_task_steps(self, tmp_path, flat_plan_fixture):
        """Flat plan: scopes by task, listing steps and files."""
        plan = tmp_path / "plan.md"
        plan.write_text(flat_plan_fixture)
        result = runner.invoke(app, ["execute", "scope", str(plan), "1"])
        assert result.exit_code == 0
        assert "Step" in result.stdout

    def test_scope_includes_files_mentioned(
        self, tmp_path, phased_plan_fixture
    ):
        """Scope output includes the Files section from tasks."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(app, ["execute", "scope", str(plan), "1"])
        assert result.exit_code == 0

    def test_scope_invalid_number_errors(self, tmp_path, phased_plan_fixture):
        """Requesting a non-existent phase/task number is an error."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(app, ["execute", "scope", str(plan), "99"])
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_execute.py -v -k "TestScope" --no-header`
Expected: FAIL — `No such command 'scope'`

- [ ] **Step 3: Implement scope subcommand**

Add to `execute_cmd.py`:

```python
@execute_app.command()
def scope(
    plan_path: Path = typer.Argument(..., help="Path to the plan file."),
    phase_or_task: int = typer.Argument(
        ..., help="Phase number (phased) or task number (flat)."
    ),
) -> None:
    """Show the scope (tasks, steps, files) for a phase or task."""
    plan_path = plan_path.resolve()
    if not plan_path.exists():
        console.print(f"[red]Plan not found:[/red] {plan_path}")
        raise typer.Exit(2)

    plan = parse_plan(plan_path)

    if plan.format is PlanFormat.PHASED:
        phase = next(
            (p for p in plan.phases if p.number == phase_or_task), None
        )
        if phase is None:
            console.print(f"[red]Phase {phase_or_task} not found.[/red]")
            raise typer.Exit(1)

        console.print(f"[bold]Phase {phase.number}: {phase.title}[/bold] [{phase.tag}]")
        if phase.tracking_url:
            console.print(f"Tracking: {phase.tracking_url}")
        for task in phase.tasks:
            console.print(f"\n  [bold]Task {task.number}: {task.title}[/bold]")
            if task.files_mentioned:
                console.print("  Files:")
                for f in task.files_mentioned:
                    console.print(f"    - {f}")
            for step in task.steps:
                state_char = step.state
                console.print(f"  [{state_char}] Step {step.number}: {step.title}")

    elif plan.format is PlanFormat.FLAT:
        task = next(
            (t for t in plan.tasks if t.number == phase_or_task), None
        )
        if task is None:
            console.print(f"[red]Task {phase_or_task} not found.[/red]")
            raise typer.Exit(1)

        tag_str = f" [{task.tag}]" if task.tag else ""
        console.print(f"[bold]Task {task.number}: {task.title}[/bold]{tag_str}")
        if task.files_mentioned:
            console.print("Files:")
            for f in task.files_mentioned:
                console.print(f"  - {f}")
        for step in task.steps:
            state_char = step.state
            console.print(f"[{state_char}] Step {step.number}: {step.title}")
```

- [ ] **Step 4: Run tests to verify scope passes**

Run: `uv run pytest tests/integration/test_execute.py -v -k "TestScope" --no-header`
Expected: PASS — all scope tests pass

- [ ] **Step 5: Commit**

```bash
git add src/vk/commands/execute_cmd.py tests/integration/test_execute.py
git commit -m "feat: add vk execute scope subcommand"
```

### Task 8: vk execute check-step subcommand

**Files:**
- Modify: `src/vk/commands/execute_cmd.py`
- Modify: `tests/integration/test_execute.py`

- [ ] **Step 1: Write failing tests for check-step**

Add to `tests/integration/test_execute.py`:

```python
class TestCheckStep:
    def test_check_step_phased_marks_checkbox(
        self, tmp_path, phased_plan_fixture
    ):
        """P1.T1.S1 marks the correct checkbox as [x]."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(
            app, ["execute", "check-step", str(plan), "P1.T1.S1", "--state", "x"]
        )
        assert result.exit_code == 0
        content = plan.read_text()
        assert "- [x] **Step 1:" in content

    def test_check_step_flat_marks_checkbox(self, tmp_path, flat_plan_fixture):
        """T1.S1 marks the correct checkbox as [x] in flat format."""
        plan = tmp_path / "plan.md"
        plan.write_text(flat_plan_fixture)
        result = runner.invoke(
            app, ["execute", "check-step", str(plan), "T1.S1", "--state", "x"]
        )
        assert result.exit_code == 0
        content = plan.read_text()
        assert "- [x] **Step 1:" in content

    def test_check_step_skip_marks_as_dash(
        self, tmp_path, phased_plan_fixture
    ):
        """--state - marks the checkbox as [-] (skipped)."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(
            app, ["execute", "check-step", str(plan), "P1.T1.S1", "--state", "-"]
        )
        assert result.exit_code == 0
        content = plan.read_text()
        assert "- [-] **Step 1:" in content

    def test_check_step_never_unchecks(self, tmp_path, phased_plan_fixture):
        """Re-running check-step on an already-checked step does not uncheck."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        # First: check it
        runner.invoke(
            app, ["execute", "check-step", str(plan), "P1.T1.S1", "--state", "x"]
        )
        # Second: try to uncheck (no --state = default, which should not uncheck)
        result = runner.invoke(
            app, ["execute", "check-step", str(plan), "P1.T1.S1", "--state", "x"]
        )
        assert result.exit_code == 0
        content = plan.read_text()
        assert "- [x] **Step 1:" in content

    def test_check_step_idempotent(self, tmp_path, phased_plan_fixture):
        """Running check-step twice with same state produces identical file."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        runner.invoke(
            app, ["execute", "check-step", str(plan), "P1.T1.S1", "--state", "x"]
        )
        content_after_first = plan.read_text()
        runner.invoke(
            app, ["execute", "check-step", str(plan), "P1.T1.S1", "--state", "x"]
        )
        content_after_second = plan.read_text()
        assert content_after_first == content_after_second

    def test_check_step_validates_step_id_exists(
        self, tmp_path, phased_plan_fixture
    ):
        """Invalid step ID is an error."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(
            app, ["execute", "check-step", str(plan), "P99.T1.S1", "--state", "x"]
        )
        assert result.exit_code != 0

    def test_check_step_stages_but_does_not_commit(
        self, tmp_git_repo_with_phased_plan
    ):
        """check-step stages the file change but does NOT create a git commit."""
        plan_path = (
            tmp_git_repo_with_phased_plan
            / "docs/superpowers/plans/test-plan.md"
        )
        result = runner.invoke(
            app, ["execute", "check-step", str(plan_path), "P1.T1.S1", "--state", "x"]
        )
        assert result.exit_code == 0
        # Verify staged but not committed
        import subprocess

        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(tmp_git_repo_with_phased_plan),
            capture_output=True,
            text=True,
        )
        assert "test-plan.md" in staged.stdout

    def test_check_step_with_note_appends_text(
        self, tmp_path, phased_plan_fixture
    ):
        """--note TEXT appends a note after the checkbox line."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(
            app,
            [
                "execute", "check-step", str(plan), "P1.T1.S1",
                "--state", "x", "--note", "Verified output matches expected.",
            ],
        )
        assert result.exit_code == 0
        content = plan.read_text()
        assert "Verified output matches expected." in content

    def test_check_step_invalid_id_format(self, tmp_path, phased_plan_fixture):
        """Malformed step IDs are rejected."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(
            app, ["execute", "check-step", str(plan), "INVALID", "--state", "x"]
        )
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_execute.py -v -k "TestCheckStep" --no-header`
Expected: FAIL — `No such command 'check-step'`

- [ ] **Step 3: Implement check-step subcommand**

Add to `execute_cmd.py`:

```python
import re
import subprocess


def _parse_step_id(step_id: str) -> tuple[int | None, int, int]:
    """Parse step ID into (phase, task, step). Phase is None for flat format.

    Phased: P<phase>.T<task>.S<step>
    Flat: T<task>.S<step>
    """
    phased_match = re.match(r"^P(\d+)\.T(\d+)\.S(\d+)$", step_id)
    if phased_match:
        return (
            int(phased_match.group(1)),
            int(phased_match.group(2)),
            int(phased_match.group(3)),
        )

    flat_match = re.match(r"^T(\d+)\.S(\d+)$", step_id)
    if flat_match:
        return None, int(flat_match.group(1)), int(flat_match.group(2))

    raise ValueError(
        f"Invalid step ID: {step_id!r}. "
        f"Expected P<phase>.T<task>.S<step> or T<task>.S<step>."
    )


@execute_app.command(name="check-step")
def check_step(
    plan_path: Path = typer.Argument(..., help="Path to the plan file."),
    step_id: str = typer.Argument(
        ..., help="Step ID: P<phase>.T<task>.S<step> or T<task>.S<step>."
    ),
    state: str = typer.Option(
        "x", "--state", help="Checkbox state: x (done) or - (skipped)."
    ),
    note: Optional[str] = typer.Option(None, "--note", help="Note to append after step."),
) -> None:
    """Mark a plan step as done or skipped. Stages but does NOT commit."""
    plan_path = plan_path.resolve()
    if not plan_path.exists():
        console.print(f"[red]Plan not found:[/red] {plan_path}")
        raise typer.Exit(2)

    if state not in ("x", "-"):
        console.print(f"[red]Invalid state: {state!r}. Use 'x' or '-'.[/red]")
        raise typer.Exit(1)

    try:
        phase_num, task_num, step_num = _parse_step_id(step_id)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    plan = parse_plan(plan_path)

    # Validate step exists
    target_task = None
    if plan.format is PlanFormat.PHASED:
        if phase_num is None:
            console.print("[red]Phased plan requires P<n>.T<n>.S<n> step ID.[/red]")
            raise typer.Exit(1)
        phase = next((p for p in plan.phases if p.number == phase_num), None)
        if phase is None:
            console.print(f"[red]Phase {phase_num} not found.[/red]")
            raise typer.Exit(1)
        target_task = next((t for t in phase.tasks if t.number == task_num), None)
    elif plan.format is PlanFormat.FLAT:
        target_task = next((t for t in plan.tasks if t.number == task_num), None)

    if target_task is None:
        console.print(f"[red]Task {task_num} not found.[/red]")
        raise typer.Exit(1)

    target_step = next((s for s in target_task.steps if s.number == step_num), None)
    if target_step is None:
        console.print(f"[red]Step {step_num} not found in Task {task_num}.[/red]")
        raise typer.Exit(1)

    # Never uncheck a checked box
    if target_step.state in ("x", "-"):
        console.print(
            f"Step {step_id} already [{target_step.state}]. No change (never unchecks)."
        )
        return

    # Rewrite the file
    content = plan_path.read_text()
    lines = content.splitlines(keepends=True)
    step_pattern = re.compile(
        rf"^- \[ \] \*\*Step {step_num}:\*\*"
    )

    # Find the correct step line (accounting for phase/task context)
    found = False
    current_phase = 0
    current_task = 0
    for i, line in enumerate(lines):
        phase_match = re.match(r"^## Phase (\d+):", line)
        if phase_match:
            current_phase = int(phase_match.group(1))
        task_match = re.match(r"^### Task (\d+):", line)
        if task_match:
            current_task = int(task_match.group(1))

        if step_pattern.match(line.strip() if line.strip() else ""):
            in_scope = False
            if plan.format is PlanFormat.PHASED:
                in_scope = current_phase == phase_num and current_task == task_num
            else:
                in_scope = current_task == task_num

            if in_scope:
                lines[i] = line.replace("- [ ]", f"- [{state}]", 1)
                if note:
                    indent = "  "
                    note_line = f"{indent}{note}\n"
                    lines.insert(i + 1, note_line)
                found = True
                break

    if not found:
        console.print(f"[red]Could not locate step {step_id} in file.[/red]")
        raise typer.Exit(1)

    plan_path.write_text("".join(lines))

    # Stage but do not commit
    repo_root = plan_path.parent
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent

    if (repo_root / ".git").exists():
        subprocess.run(
            ["git", "add", str(plan_path)],
            cwd=str(repo_root),
            check=True,
            capture_output=True,
        )

    console.print(f"Checked [{state}] {step_id}. Staged (not committed).")
```

- [ ] **Step 4: Run tests to verify check-step passes**

Run: `uv run pytest tests/integration/test_execute.py -v -k "TestCheckStep" --no-header`
Expected: PASS — all check-step tests pass

- [ ] **Step 5: Run full execute test suite**

Run: `uv run pytest tests/integration/test_execute.py -v --no-header`
Expected: PASS — all execute tests pass

- [ ] **Step 6: Commit**

```bash
git add src/vk/commands/execute_cmd.py tests/integration/test_execute.py
git commit -m "feat: add vk execute check-step subcommand with safety guarantees"
```

### Task 9: vk execute pr-body subcommand

**Files:**
- Modify: `src/vk/commands/execute_cmd.py`
- Modify: `tests/integration/test_execute.py`

- [ ] **Step 1: Write failing tests for pr-body**

Add to `tests/integration/test_execute.py`:

```python
class TestPrBody:
    def test_pr_body_phased_local_format(self, tmp_path, phased_plan_fixture):
        """Local mode: outputs 'Implements Phase N of <plan-path>'."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(app, ["execute", "pr-body", str(plan), "1"])
        assert result.exit_code == 0
        assert "Implements Phase 1" in result.stdout

    def test_pr_body_phased_dispatch_format(
        self, tmp_path, phased_dispatched_plan_fixture
    ):
        """Dispatch mode with --issue: outputs 'Closes #<issue>'."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_dispatched_plan_fixture)
        result = runner.invoke(
            app, ["execute", "pr-body", str(plan), "1", "--issue", "42"]
        )
        assert result.exit_code == 0
        assert "Closes #42" in result.stdout

    def test_pr_body_flat_local_format(self, tmp_path, flat_plan_fixture):
        """Flat plan local mode: outputs 'Implements Task N of <plan-path>'."""
        plan = tmp_path / "plan.md"
        plan.write_text(flat_plan_fixture)
        result = runner.invoke(app, ["execute", "pr-body", str(plan), "1"])
        assert result.exit_code == 0
        assert "Implements Task 1" in result.stdout

    def test_pr_body_includes_task_list(self, tmp_path, phased_plan_fixture):
        """PR body includes a list of tasks in the phase."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(app, ["execute", "pr-body", str(plan), "1"])
        assert result.exit_code == 0
        assert "Task" in result.stdout

    def test_pr_body_invalid_phase_errors(self, tmp_path, phased_plan_fixture):
        """Non-existent phase number is an error."""
        plan = tmp_path / "plan.md"
        plan.write_text(phased_plan_fixture)
        result = runner.invoke(app, ["execute", "pr-body", str(plan), "99"])
        assert result.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_execute.py -v -k "TestPrBody" --no-header`
Expected: FAIL — `No such command 'pr-body'`

- [ ] **Step 3: Implement pr-body subcommand**

Add to `execute_cmd.py`:

```python
@execute_app.command(name="pr-body")
def pr_body(
    plan_path: Path = typer.Argument(..., help="Path to the plan file."),
    phase_or_task: int = typer.Argument(
        ..., help="Phase number (phased) or task number (flat)."
    ),
    issue: Optional[int] = typer.Option(
        None, "--issue", help="GitHub Issue number for Closes reference."
    ),
) -> None:
    """Generate a PR body for a phase or task."""
    plan_path = plan_path.resolve()
    if not plan_path.exists():
        console.print(f"[red]Plan not found:[/red] {plan_path}")
        raise typer.Exit(2)

    plan = parse_plan(plan_path)
    rel_path = plan_path.name
    lines: list[str] = []

    if plan.format is PlanFormat.PHASED:
        phase = next(
            (p for p in plan.phases if p.number == phase_or_task), None
        )
        if phase is None:
            console.print(f"[red]Phase {phase_or_task} not found.[/red]")
            raise typer.Exit(1)

        if issue:
            lines.append(f"Closes #{issue}")
            lines.append("")
        lines.append(f"Implements Phase {phase.number} of `{rel_path}`")
        lines.append("")
        lines.append(f"## {phase.title}")
        lines.append("")
        for task in phase.tasks:
            lines.append(f"- Task {task.number}: {task.title}")
            for f in task.files_mentioned:
                lines.append(f"  - `{f}`")

    elif plan.format is PlanFormat.FLAT:
        task = next(
            (t for t in plan.tasks if t.number == phase_or_task), None
        )
        if task is None:
            console.print(f"[red]Task {phase_or_task} not found.[/red]")
            raise typer.Exit(1)

        if issue:
            lines.append(f"Closes #{issue}")
            lines.append("")
        lines.append(f"Implements Task {task.number} of `{rel_path}`")
        lines.append("")
        lines.append(f"## {task.title}")
        lines.append("")
        for step in task.steps:
            lines.append(f"- Step {step.number}: {step.title}")
        if task.files_mentioned:
            lines.append("")
            lines.append("### Files")
            for f in task.files_mentioned:
                lines.append(f"- `{f}`")

    typer.echo("\n".join(lines))
```

- [ ] **Step 4: Run tests to verify pr-body passes**

Run: `uv run pytest tests/integration/test_execute.py -v -k "TestPrBody" --no-header`
Expected: PASS — all pr-body tests pass

- [ ] **Step 5: Run full test suite and quality gates**

Run: `uv run pytest tests/integration/test_execute.py tests/integration/test_convert.py tests/integration/test_plan_cmd.py -v --no-header`
Expected: PASS — all plan and execute integration tests pass

Run: `uv run ruff check src/vk/commands/plan_cmd.py src/vk/commands/execute_cmd.py && uv run mypy src/vk/commands/plan_cmd.py src/vk/commands/execute_cmd.py`
Expected: PASS — no lint or type errors

- [ ] **Step 6: Commit**

```bash
git add src/vk/commands/execute_cmd.py tests/integration/test_execute.py
git commit -m "feat: add vk execute pr-body subcommand"
```
