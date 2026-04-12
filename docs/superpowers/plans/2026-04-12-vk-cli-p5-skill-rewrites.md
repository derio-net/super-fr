# SKILL.md Rewrites + vk init + vk install-skills Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-12-vk-cli-toolchain-design.md`
**Status:** Not Started

**Goal:** Replace all four prose SKILL.md files with thin CLI wrappers, add `vk init` and `vk install-skills` utility commands, and replace the bash validation script with pytest.
**Architecture:** Four SKILL.md files become decision-layer prose (~275 lines total) that delegate mechanical work to `vk` CLI subcommands. Two new command modules (`init_cmd.py`, `install_cmd.py`) implement scaffolding and skill deployment. `test_skill_validation.py` replaces `scripts/validate-skills.sh` with structured assertions.
**Tech Stack:** Python 3.11+, uv, typer, pyyaml, rich, pytest, ruff, mypy

---

## Phase 1: Utility commands and skill validation tests [agentic]

### Task 1: Skill validation test suite

**Files:**
- Create: `tests/unit/test_skill_validation.py`

- [ ] **Step 1: Write the skill validation tests**

```python
# tests/unit/test_skill_validation.py
"""Validate SKILL.md files have correct structure.

Replaces scripts/validate-skills.sh with structured pytest assertions.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent.parent
SKILLS_DIR = REPO_ROOT / "skills"


def skill_files() -> list[Path]:
    """Discover all SKILL.md files."""
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


@pytest.fixture(params=skill_files(), ids=lambda p: p.parent.name)
def skill_path(request: pytest.FixtureRequest) -> Path:
    return request.param


def test_skill_files_exist() -> None:
    """At least one SKILL.md exists."""
    files = skill_files()
    assert len(files) > 0, "No SKILL.md files found in skills/"


def test_first_line_is_frontmatter_open(skill_path: Path) -> None:
    """First non-empty line must be '---' (catches fence-leak bugs)."""
    lines = skill_path.read_text().splitlines()
    first_nonempty = next((line for line in lines if line.strip()), None)
    assert first_nonempty == "---", (
        f"{skill_path.parent.name}/SKILL.md: first non-empty line is "
        f"{first_nonempty!r}, not '---'. Possible fence-leak from plan source."
    )


def test_frontmatter_parses_as_yaml(skill_path: Path) -> None:
    """YAML frontmatter between first and second '---' must parse."""
    text = skill_path.read_text()
    parts = text.split("---", maxsplit=2)
    assert len(parts) >= 3, (
        f"{skill_path.parent.name}/SKILL.md: could not find closing '---' for frontmatter"
    )
    frontmatter = yaml.safe_load(parts[1])
    assert isinstance(frontmatter, dict), (
        f"{skill_path.parent.name}/SKILL.md: frontmatter is not a YAML mapping"
    )


def test_frontmatter_has_name_and_description(skill_path: Path) -> None:
    """Frontmatter must have 'name' and 'description' fields."""
    text = skill_path.read_text()
    parts = text.split("---", maxsplit=2)
    frontmatter = yaml.safe_load(parts[1])
    assert "name" in frontmatter, (
        f"{skill_path.parent.name}/SKILL.md: frontmatter missing 'name' field"
    )
    assert "description" in frontmatter, (
        f"{skill_path.parent.name}/SKILL.md: frontmatter missing 'description' field"
    )


def test_file_under_120_lines(skill_path: Path) -> None:
    """SKILL.md files must stay under 120 lines (guardrail against prose re-bloat)."""
    lines = skill_path.read_text().splitlines()
    assert len(lines) <= 120, (
        f"{skill_path.parent.name}/SKILL.md: {len(lines)} lines exceeds 120-line limit"
    )
```

- [ ] **Step 2: Run tests to verify they pass against current SKILL.md files (except line limit)**

Run: `uv run pytest tests/unit/test_skill_validation.py -v`
Expected: Most tests pass; `test_file_under_120_lines` will FAIL for current verbose SKILL.md files (vk-plan is 347 lines, vk-dispatch is 273 lines, vk-progress is 284 lines). This confirms the guardrail works. The tests will all pass after the SKILL.md rewrites in Phase 2.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_skill_validation.py
git commit -m "test: add skill validation test suite replacing validate-skills.sh"
```

### Task 2: `vk init` command

**Files:**
- Create: `src/vk/commands/init_cmd.py`
- Test: `tests/unit/test_init_cmd.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_init_cmd.py
"""Tests for vk init command."""

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo in tmp_path."""
    import subprocess

    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    return tmp_path


def test_init_creates_local_config(tmp_repo: Path) -> None:
    """Without --dispatch, creates a fail-closed local-only config."""
    result = runner.invoke(app, ["init"], catch_exceptions=False, env={"VK_REPO_ROOT": str(tmp_repo)})
    assert result.exit_code == 0

    config_path = tmp_repo / "docs" / "superpowers" / "plan-config.yaml"
    assert config_path.exists()

    config = yaml.safe_load(config_path.read_text())
    assert "plan" in config
    assert "dispatch" not in config or config.get("dispatch") is False


def test_init_creates_directories(tmp_repo: Path) -> None:
    """Creates docs/superpowers/{specs,plans,archived-plans}/."""
    runner.invoke(app, ["init"], catch_exceptions=False, env={"VK_REPO_ROOT": str(tmp_repo)})

    assert (tmp_repo / "docs" / "superpowers" / "specs").is_dir()
    assert (tmp_repo / "docs" / "superpowers" / "plans").is_dir()
    assert (tmp_repo / "docs" / "superpowers" / "archived-plans").is_dir()


def test_init_with_dispatch(tmp_repo: Path) -> None:
    """With --dispatch, creates a full dispatch block."""
    result = runner.invoke(
        app,
        ["init", "--dispatch", "derio-net/my-repo", "--project", "My Project"],
        catch_exceptions=False,
        env={"VK_REPO_ROOT": str(tmp_repo)},
    )
    assert result.exit_code == 0

    config_path = tmp_repo / "docs" / "superpowers" / "plan-config.yaml"
    config = yaml.safe_load(config_path.read_text())
    assert isinstance(config.get("dispatch"), dict)
    assert config["dispatch"]["owner"] == "derio-net"
    assert config["dispatch"]["default_repo"] == "derio-net/my-repo"
    assert config["dispatch"]["project_board"] == "My Project"


def test_init_refuses_overwrite(tmp_repo: Path) -> None:
    """Refuses to overwrite existing config without --force."""
    runner.invoke(app, ["init"], catch_exceptions=False, env={"VK_REPO_ROOT": str(tmp_repo)})
    result = runner.invoke(app, ["init"], catch_exceptions=False, env={"VK_REPO_ROOT": str(tmp_repo)})
    assert result.exit_code != 0
    assert "already exists" in result.stdout.lower() or "already exists" in (result.stderr or "").lower()


def test_init_force_overwrites(tmp_repo: Path) -> None:
    """--force allows overwriting existing config."""
    runner.invoke(app, ["init"], catch_exceptions=False, env={"VK_REPO_ROOT": str(tmp_repo)})
    result = runner.invoke(
        app, ["init", "--force"], catch_exceptions=False, env={"VK_REPO_ROOT": str(tmp_repo)}
    )
    assert result.exit_code == 0


def test_init_dispatch_without_project_uses_default(tmp_repo: Path) -> None:
    """--dispatch without --project uses 'Derio Ops' as default."""
    runner.invoke(
        app,
        ["init", "--dispatch", "derio-net/my-repo"],
        catch_exceptions=False,
        env={"VK_REPO_ROOT": str(tmp_repo)},
    )

    config_path = tmp_repo / "docs" / "superpowers" / "plan-config.yaml"
    config = yaml.safe_load(config_path.read_text())
    assert config["dispatch"]["project_board"] == "Derio Ops"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_init_cmd.py -v`
Expected: FAIL — `ImportError` or command not implemented

- [ ] **Step 3: Implement init_cmd.py**

```python
# src/vk/commands/init_cmd.py
"""vk init — scaffold plan-config.yaml in a new repo."""

from __future__ import annotations

import os
from pathlib import Path

import typer
import yaml


def _resolve_repo_root() -> Path:
    """Resolve repo root from VK_REPO_ROOT env var or git."""
    env_root = os.environ.get("VK_REPO_ROOT")
    if env_root:
        return Path(env_root)

    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    return Path.cwd()


def init(
    dispatch: str | None = typer.Option(
        None, "--dispatch", help="Enable dispatch with OWNER/REPO.",
    ),
    project: str | None = typer.Option(
        None, "--project", help="Project board name.",
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing config.",
    ),
) -> None:
    """Scaffold plan-config.yaml in a new repo."""
    repo_root = _resolve_repo_root()
    superpowers_dir = repo_root / "docs" / "superpowers"
    config_path = superpowers_dir / "plan-config.yaml"

    if config_path.exists() and not force:
        typer.echo(f"Config already exists: {config_path}")
        typer.echo("Use --force to overwrite.")
        raise typer.Exit(1)

    # Create directory structure
    for subdir in ("specs", "plans", "archived-plans"):
        (superpowers_dir / subdir).mkdir(parents=True, exist_ok=True)

    # Build config
    config: dict[str, object] = {
        "plan": {
            "save_to": "docs/superpowers/plans/",
            "filename": "YYYY-MM-DD-{name}.md",
        },
        "header": {
            "required": ["Spec", "Status"],
            "status_values": ["Not Started", "In Progress", "Complete"],
        },
    }

    if dispatch:
        parts = dispatch.split("/", maxsplit=1)
        if len(parts) != 2:
            typer.echo(f"Invalid --dispatch format: {dispatch!r}. Expected OWNER/REPO.")
            raise typer.Exit(1)

        owner = parts[0]
        project_name = project or "Derio Ops"

        config["dispatch"] = {
            "target": "github-issues",
            "owner": owner,
            "project_board": project_name,
            "default_repo": dispatch,
            "labels": {
                "agentic": "vk-ready",
                "manual": "manual",
            },
        }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
    typer.echo(f"Created {config_path}")

    if dispatch:
        typer.echo("Dispatch enabled — phased plan format active.")
    else:
        typer.echo("Local-only config — flat plan format active. Add a dispatch: block to enable dispatch.")
```

- [ ] **Step 4: Wire init command into cli.py**

Replace the stub `init` command in `src/vk/cli.py` with:

```python
from vk.commands.init_cmd import init as init_command

@app.command()
def init(
    dispatch: Optional[str] = typer.Option(
        None, "--dispatch", help="Enable dispatch with OWNER/REPO."
    ),
    project: Optional[str] = typer.Option(
        None, "--project", help="Project board name."
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing config."
    ),
) -> None:
    """Scaffold plan-config.yaml in a new repo."""
    init_command(dispatch=dispatch, project=project, force=force)
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `uv run pytest tests/unit/test_init_cmd.py -v`
Expected: PASS — all 6 tests pass

- [ ] **Step 6: Run lint and type check**

Run: `uv run ruff check src/vk/commands/init_cmd.py tests/unit/test_init_cmd.py && uv run mypy src/vk/commands/init_cmd.py`
Expected: PASS — no lint or type errors

- [ ] **Step 7: Commit**

```bash
git add src/vk/commands/init_cmd.py tests/unit/test_init_cmd.py src/vk/cli.py
git commit -m "feat: add vk init command for repo scaffolding"
```

### Task 3: `vk install-skills` command

**Files:**
- Create: `src/vk/commands/install_cmd.py`
- Test: `tests/unit/test_install_cmd.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_install_cmd.py
"""Tests for vk install-skills command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


@pytest.fixture
def mock_skills(tmp_path: Path) -> Path:
    """Create mock skill directories with SKILL.md files."""
    for name in ("vk-plan", "vk-dispatch", "vk-progress", "vk-execute"):
        skill_dir = tmp_path / "skills" / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n# {name}\n")
    return tmp_path


@pytest.fixture
def mock_claude_dir(tmp_path: Path) -> Path:
    """Create a mock ~/.claude directory."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return claude_dir


def test_install_skills_creates_symlinks(
    mock_skills: Path, mock_claude_dir: Path
) -> None:
    """Default mode creates symlinks."""
    result = runner.invoke(
        app,
        ["install-skills"],
        catch_exceptions=False,
        env={
            "VK_PACKAGE_ROOT": str(mock_skills),
            "VK_CLAUDE_HOME": str(mock_claude_dir),
        },
    )
    assert result.exit_code == 0

    skills_target = mock_claude_dir / "skills"
    for name in ("vk-plan", "vk-dispatch", "vk-progress", "vk-execute"):
        link = skills_target / name
        assert link.is_symlink()
        assert link.resolve() == (mock_skills / "skills" / name).resolve()


def test_install_skills_copy_mode(
    mock_skills: Path, mock_claude_dir: Path
) -> None:
    """--copy copies instead of symlinking."""
    result = runner.invoke(
        app,
        ["install-skills", "--copy"],
        catch_exceptions=False,
        env={
            "VK_PACKAGE_ROOT": str(mock_skills),
            "VK_CLAUDE_HOME": str(mock_claude_dir),
        },
    )
    assert result.exit_code == 0

    skills_target = mock_claude_dir / "skills"
    for name in ("vk-plan", "vk-dispatch", "vk-progress", "vk-execute"):
        target = skills_target / name
        assert target.is_dir()
        assert not target.is_symlink()
        assert (target / "SKILL.md").exists()


def test_install_skills_overwrites_existing(
    mock_skills: Path, mock_claude_dir: Path
) -> None:
    """Re-running replaces existing symlinks/copies."""
    runner.invoke(
        app,
        ["install-skills"],
        catch_exceptions=False,
        env={
            "VK_PACKAGE_ROOT": str(mock_skills),
            "VK_CLAUDE_HOME": str(mock_claude_dir),
        },
    )
    # Run again
    result = runner.invoke(
        app,
        ["install-skills"],
        catch_exceptions=False,
        env={
            "VK_PACKAGE_ROOT": str(mock_skills),
            "VK_CLAUDE_HOME": str(mock_claude_dir),
        },
    )
    assert result.exit_code == 0


def test_install_skills_reports_count(
    mock_skills: Path, mock_claude_dir: Path
) -> None:
    """Reports how many skills were installed."""
    result = runner.invoke(
        app,
        ["install-skills"],
        catch_exceptions=False,
        env={
            "VK_PACKAGE_ROOT": str(mock_skills),
            "VK_CLAUDE_HOME": str(mock_claude_dir),
        },
    )
    assert "4" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_install_cmd.py -v`
Expected: FAIL — command not implemented

- [ ] **Step 3: Implement install_cmd.py**

```python
# src/vk/commands/install_cmd.py
"""vk install-skills — symlink or copy SKILL.md dirs into ~/.claude/skills/."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import typer


def _resolve_package_root() -> Path:
    """Resolve the superpowers-for-vk package root."""
    env_root = os.environ.get("VK_PACKAGE_ROOT")
    if env_root:
        return Path(env_root)
    # Default: the installed package's grandparent (src/vk -> superpowers-for-vk)
    return Path(__file__).parent.parent.parent.parent


def _resolve_claude_home() -> Path:
    """Resolve the Claude home directory."""
    env_home = os.environ.get("VK_CLAUDE_HOME")
    if env_home:
        return Path(env_home)
    return Path.home() / ".claude"


def install_skills(
    copy: bool = typer.Option(
        False, "--copy", help="Copy instead of symlink (for cross-filesystem installs).",
    ),
) -> None:
    """Symlink SKILL.md files into ~/.claude/skills/."""
    package_root = _resolve_package_root()
    claude_home = _resolve_claude_home()
    skills_src = package_root / "skills"

    if not skills_src.is_dir():
        typer.echo(f"Skills directory not found: {skills_src}")
        raise typer.Exit(1)

    skills_target = claude_home / "skills"
    skills_target.mkdir(parents=True, exist_ok=True)

    installed = 0
    for skill_dir in sorted(skills_src.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
            continue

        dest = skills_target / skill_dir.name

        # Remove existing link or directory
        if dest.is_symlink():
            dest.unlink()
        elif dest.is_dir():
            shutil.rmtree(dest)

        if copy:
            shutil.copytree(skill_dir, dest)
            typer.echo(f"  Copied {skill_dir.name}/")
        else:
            dest.symlink_to(skill_dir.resolve())
            typer.echo(f"  Linked {skill_dir.name}/ -> {skill_dir.resolve()}")

        installed += 1

    typer.echo(f"Installed {installed} skill(s) into {skills_target}")
```

- [ ] **Step 4: Wire install-skills command into cli.py**

Replace the stub `install_skills` command in `src/vk/cli.py` with:

```python
from vk.commands.install_cmd import install_skills as install_skills_command

@app.command(name="install-skills")
def install_skills(
    copy: bool = typer.Option(False, "--copy", help="Copy instead of symlink."),
) -> None:
    """Symlink SKILL.md files into ~/.claude/skills/."""
    install_skills_command(copy=copy)
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `uv run pytest tests/unit/test_install_cmd.py -v`
Expected: PASS — all 4 tests pass

- [ ] **Step 6: Run lint and type check**

Run: `uv run ruff check src/vk/commands/install_cmd.py tests/unit/test_install_cmd.py && uv run mypy src/vk/commands/install_cmd.py`
Expected: PASS — no lint or type errors

- [ ] **Step 7: Commit**

```bash
git add src/vk/commands/install_cmd.py tests/unit/test_install_cmd.py src/vk/cli.py
git commit -m "feat: add vk install-skills command for skill deployment"
```

### Task 4: Delete validate-skills.sh

**Files:**
- Delete: `scripts/validate-skills.sh`

- [ ] **Step 1: Verify test_skill_validation.py covers all validate-skills.sh checks**

Run: `uv run pytest tests/unit/test_skill_validation.py -v`
Confirm: the pytest suite checks first-line-is-`---`, frontmatter parses, name+description present, and line count limit. This is a strict superset of the bash script (which only checked first line).

- [ ] **Step 2: Delete the bash script**

```bash
git rm scripts/validate-skills.sh
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: delete validate-skills.sh, replaced by test_skill_validation.py"
```

## Phase 2: SKILL.md rewrites [agentic]

### Task 1: Rewrite vk-dispatch/SKILL.md

**Files:**
- Rewrite: `skills/vk-dispatch/SKILL.md`

- [ ] **Step 1: Write the new vk-dispatch/SKILL.md**

Write the following content to `skills/vk-dispatch/SKILL.md` verbatim. Do not include the BEGIN/END markers in the output file.

<!-- BEGIN FILE: skills/vk-dispatch/SKILL.md -->
---
name: vk-dispatch
description: >
  Dispatch a phase-structured plan to GitHub Issues with profile-driven config.
  Reads dispatch settings from plan-config.yaml (project board, labels, target repo).
  Enforces single-repo plan scope — reject if plan references cross-repo phases.
  Use when: "dispatch this plan", "send to VK", "create issues from plan",
  "dispatch phases", "break this plan into issues".
---

# VK Dispatch

Dispatches a phased plan to GitHub Issues. One Issue per phase, sequential dependencies, project board placement, tracking links back into the plan file.

**Announce at start:** "I'm using vk-dispatch to dispatch this plan."

## Workflow

1. **Dry-run first, always:**
   ```bash
   vk dispatch <plan-path> --dry-run
   ```
   Show the preview to the operator. Confirm before proceeding.

2. **Apply on approval:**
   ```bash
   vk dispatch <plan-path> --yes
   ```
   Creates Issues, adds to project board, sets lifecycle to `plan`, inserts `<!-- Tracking: -->` comments, commits.

3. **Report results** — the CLI prints a summary table of dispatched phases.

## Error Table

| Exit code | Meaning | Action |
|-----------|---------|--------|
| 0 | Success (or all phases already dispatched) | Done |
| 1 | Gate disabled / config error | Add `dispatch:` block to `plan-config.yaml` |
| 2 | Plan parse error (flat format, missing phases) | Fix plan structure or convert with `vk plan convert` |
| 3 | gh error (auth, rate limit, access) | Check `gh auth status` |
| 4 | Partial success (some phases failed) | Re-run; idempotent on already-dispatched phases |

## Gate Check

Dispatch requires a `dispatch:` map in `docs/superpowers/plan-config.yaml`. Missing file, missing key, `dispatch: false` — all mean disabled. The CLI prints a refusal message with a paste-ready config template.

## Single-Repo Rule

All phases of a plan dispatch to one repo. If the operator passes a different `--repo`, the CLI warns and confirms. Cross-repo features should be split into multiple plans.

## Integration

- **Upstream:** `vk-plan` creates the plan this skill dispatches
- **Downstream:** `vk-execute` agents implement agentic phases
- **Sync:** `vk-progress` syncs Issue states back to plan checkboxes
<!-- END FILE: skills/vk-dispatch/SKILL.md -->

- [ ] **Step 2: Run skill validation tests**

Run: `uv run pytest tests/unit/test_skill_validation.py -k "vk-dispatch" -v`
Expected: PASS — all validation checks pass, file is under 120 lines

- [ ] **Step 3: Commit**

```bash
git add skills/vk-dispatch/SKILL.md
git commit -m "docs: rewrite vk-dispatch/SKILL.md as thin CLI wrapper"
```

### Task 2: Rewrite vk-plan/SKILL.md

**Files:**
- Rewrite: `skills/vk-plan/SKILL.md`

- [ ] **Step 1: Write the new vk-plan/SKILL.md**

Write the following content to `skills/vk-plan/SKILL.md` verbatim. Do not include the BEGIN/END markers in the output file.

<!-- BEGIN FILE: skills/vk-plan/SKILL.md -->
---
name: vk-plan
description: >
  Canonical plan skill for derio-net repos. Write phase-structured plans with
  manual/agentic phase tagging. Profile-driven per-repo behavior via plan-config.yaml.
  Maintains spec-to-plans forward index. Use when: "write a plan", "vk plan",
  "create a plan", "phase-structured plan", "plan for vk", "create a dispatchable plan".
---

# VK Plan — Canonical Plan Skill

**This skill replaces `superpowers:writing-plans`.** It produces phase-structured implementation plans with profile-driven per-repo behavior and spec index maintenance.

**Announce at start:** "I'm using vk-plan to create the implementation plan."

## Plan Format

Detect format with: `vk plan format`

- **Dispatch enabled** (profile has `dispatch:` block) -> **Phased:** Phase > Task > Step
- **Dispatch disabled** -> **Flat:** Task > Step

## Writing Flow

1. Read profile: `docs/superpowers/plan-config.yaml` (filename pattern, required headers, status values)
2. Brainstorm scope, architecture, file structure with the operator
3. Write the plan following Phase > Task > Step (or Task > Step for flat) hierarchy
4. Every agentic task follows TDD: write failing test, see it fail, implement, see it pass, commit
5. Save: `vk plan new <name> --spec <spec-path> --save`
6. Self-review: `vk plan self-review <plan-path>`
7. Update spec index: `vk plan spec-index <plan-path> --yes`

## Anti-Pattern Rules

- **No placeholders.** Every step has actual code. No "TBD", "similar to above", "add appropriate handling".
- **Test first, always.** First step of any implementation task is "Write the failing test."
- **No fence leaks.** Full file rewrites use `<!-- BEGIN FILE -->` / `<!-- END FILE -->` markers, not nested code fences.
- **Single-repo scope.** All phases target one repo. Cross-repo features use multiple plans.
- **Bite-sized steps.** Each step is one action (2-5 minutes). One task = one commit.

## Phase Structure

```markdown
## Phase N: <name> [manual|agentic]

### Task 1: <component>

**Files:**
- Create: `path/to/file.py`
- Test: `tests/path/to/test.py`

- [ ] **Step 1: Write the failing test**
...
```

- Phases are sequential. Each `[agentic]` phase = one PR.
- `[manual]` phases are operator runbooks with exact URLs, commands, and verification steps.

## Execution Handoff

After saving and updating the spec index, offer execution paths:

- **Dispatch to VK** (if dispatch enabled): invoke `vk-dispatch`
- **Subagent-driven (in-session):** invoke `superpowers:subagent-driven-development`
- **Inline execution:** invoke `superpowers:executing-plans`

If dispatch is disabled, omit the dispatch option and note: "Dispatch unavailable -- add a `dispatch:` block to `plan-config.yaml` to enable."

## Integration

- **Upstream:** brainstorming feeds into vk-plan (via user-level rule redirect)
- **Downstream:** vk-dispatch dispatches phases to GitHub Issues
- **Execution:** vk-execute (agentic phases), subagent-driven-development, executing-plans
- **Tracking:** vk-progress syncs Issue states and updates spec index status
<!-- END FILE: skills/vk-plan/SKILL.md -->

- [ ] **Step 2: Run skill validation tests**

Run: `uv run pytest tests/unit/test_skill_validation.py -k "vk-plan" -v`
Expected: PASS — all validation checks pass, file is under 120 lines

- [ ] **Step 3: Commit**

```bash
git add skills/vk-plan/SKILL.md
git commit -m "docs: rewrite vk-plan/SKILL.md as thin CLI wrapper"
```

### Task 3: Rewrite vk-progress/SKILL.md

**Files:**
- Rewrite: `skills/vk-progress/SKILL.md`

- [ ] **Step 1: Write the new vk-progress/SKILL.md**

Write the following content to `skills/vk-progress/SKILL.md` verbatim. Do not include the BEGIN/END markers in the output file.

<!-- BEGIN FILE: skills/vk-progress/SKILL.md -->
---
name: vk-progress
description: >
  Work lifecycle tracking — sync plan progress, query status boards, create/transition
  work items, health summaries, and audit. Absorbs work-lifecycle + progress-sync.
  Also syncs plan status back to spec index tables.
  Use when: "sync progress", "status board", "what's in progress", "what's broken",
  "update the plan", "health summary", "create work item", "transition state",
  "audit", "refresh plan status", "how far along is the plan".
---

# VK Progress — Work Lifecycle Tracking

Five capabilities. Use the triage table below to pick the right subcommand.

**Announce at start:** "I'm using vk-progress for [capability]."

## Triage Table

| User intent | Subcommand | Notes |
|-------------|------------|-------|
| "sync the plan", "refresh progress" | `vk progress sync <plan-path> --dry-run` then `--yes` | Syncs Issue/checkbox states + spec index |
| "status board", "what's in progress" | `vk progress board` | `--format table\|json`, `--stale-days N` |
| "create a work item", "new issue" | `vk progress create <title> --type TYPE` | Dispatch-only; refuses in local mode |
| "move to in-progress", "deploy this" | `vk progress transition <target> <state> --yes` | Validates allowed transitions |
| "health check", "what's broken" | `vk progress audit` | `--format report\|json` |

## Dual-Mode Behavior

Each subcommand auto-detects mode from the dispatch gate:

| Capability | Dispatch enabled | Dispatch disabled |
|------------|-----------------|-------------------|
| Sync | Issue states -> checkboxes -> spec index | Checkbox states -> Status header -> spec index |
| Board | Query project board by lifecycle | Scan local plan files by Status header |
| Create | Create Issue + board entry | Unavailable (prints gate refusal) |
| Transition | Move Issue lifecycle state | Edit plan `**Status:**` header + spec index |
| Audit | Issues + local drift + spec index | Local-only drift checks |

## Workflow Pattern

For mutating commands (sync, transition):

1. Run with `--dry-run` first to preview changes
2. Show preview to operator
3. Run with `--yes` on approval

## Safety Rules

- Never uncheck a manually checked box — progress only moves forward
- Never mark complete unless all phases/tasks are done
- Spec index updates are additive — never remove rows

## Integration

- **Upstream:** vk-dispatch created the tracking links this skill reads
- **Execution:** vk-execute agents whose progress this tracks
- **Plan:** vk-plan created the plan file and seeded the spec index
<!-- END FILE: skills/vk-progress/SKILL.md -->

- [ ] **Step 2: Run skill validation tests**

Run: `uv run pytest tests/unit/test_skill_validation.py -k "vk-progress" -v`
Expected: PASS — all validation checks pass, file is under 120 lines

- [ ] **Step 3: Commit**

```bash
git add skills/vk-progress/SKILL.md
git commit -m "docs: rewrite vk-progress/SKILL.md as thin CLI wrapper"
```

### Task 4: Rewrite vk-execute/SKILL.md

**Files:**
- Rewrite: `skills/vk-execute/SKILL.md`

- [ ] **Step 1: Write the new vk-execute/SKILL.md**

Write the following content to `skills/vk-execute/SKILL.md` verbatim. Do not include the BEGIN/END markers in the output file.

<!-- BEGIN FILE: skills/vk-execute/SKILL.md -->
---
name: vk-execute
description: >
  Execute an agentic phase from a VK-dispatched plan. Understands Phase > Task > Step
  hierarchy. Agent-facing skill — not directly invoked by the operator. VK workspace
  agents use this to implement their assigned phase.
---

# VK Execute

Implements a single agentic phase from a VK plan. Agent-facing skill — referenced in GitHub Issue bodies created by `vk-dispatch`.

**Announce at start:** "I'm using vk-execute to implement this phase."

## Mode Selection

| Source | Input | How to start |
|--------|-------|-------------|
| Dispatched (Issue) | Issue URL or number | Read Issue body for plan path + phase number |
| Local (direct) | `(plan-path, phase-or-task)` | Operator provides plan path and scope directly |

## Procedure

### 1. Resolve scope

```bash
vk execute scope <plan-path> <phase-or-task-number>
```

Prints the tasks and steps in scope. Review before proceeding.

### 2. Check dependencies

```bash
vk execute check-deps <plan-path> <phase-or-task-number>
```

Exit 0 = clear to proceed. Non-zero = blocked; stop and report.

For dispatched mode: checks `Blocked by #N` Issues are closed.
For local mode: checks earlier phases/tasks have all checkboxes checked.

### 3. Execute tasks

Use `superpowers:executing-plans` (or `superpowers:subagent-driven-development` if subagents available) for the scoped tasks. Follow `superpowers:test-driven-development` for all implementation.

- Work through tasks sequentially within the phase
- Each step is one action — TDD cycle, then commit
- Never touch other phases — they belong to other agents or the operator

### 4. Update checkboxes

```bash
vk execute check-step <plan-path> <step-id> --state x
```

Step IDs: `P<phase>.T<task>.S<step>` (phased) or `T<task>.S<step>` (flat).

Guarantees: never unchecks a checked box, validates step exists, idempotent.

### 5. Open PR

```bash
vk execute pr-body <plan-path> <phase-or-task-number> [--issue NUMBER]
```

Generates PR body with phase summary. Dispatched mode: includes `Closes #<issue>`. Then invoke `superpowers:finishing-a-development-branch`.

## Constraints

- **One phase = one PR.** Do not combine or split phases.
- **Stop if blocked.** Missing deps, infra from manual phase, unresolvable test failure — stop and report. For test failures, follow `superpowers:systematic-debugging` first.
- **Respect boundaries.** Note out-of-scope work in PR description, don't do it.

## Integration

- **Upstream:** vk-dispatch created the Issue; vk-plan created the plan
- **Execution:** `superpowers:executing-plans`, `superpowers:test-driven-development`
- **Completion:** `superpowers:finishing-a-development-branch`
- **Progress:** vk-progress syncs completion state back to plan
<!-- END FILE: skills/vk-execute/SKILL.md -->

- [ ] **Step 2: Run skill validation tests**

Run: `uv run pytest tests/unit/test_skill_validation.py -k "vk-execute" -v`
Expected: PASS — all validation checks pass, file is under 120 lines

- [ ] **Step 3: Commit**

```bash
git add skills/vk-execute/SKILL.md
git commit -m "docs: rewrite vk-execute/SKILL.md as thin CLI wrapper"
```

### Task 5: Full validation and version bump

**Files:**
- Modify: `src/vk/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Run all skill validation tests**

Run: `uv run pytest tests/unit/test_skill_validation.py -v`
Expected: PASS — all 4 skills pass all 4 checks (16 total assertions)

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS — all tests pass, coverage >= 85%

- [ ] **Step 3: Run lint and type check**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/`
Expected: PASS — no issues

- [ ] **Step 4: Bump version to 1.0.0**

Update `src/vk/__init__.py`:
```python
__version__ = "1.0.0"
```

Update `pyproject.toml`:
```toml
version = "1.0.0"
```

- [ ] **Step 5: Commit**

```bash
git add src/vk/__init__.py pyproject.toml
git commit -m "chore: bump to v1.0.0 — feature-complete skill cutover"
```

- [ ] **Step 6: Run full suite one more time**

Run: `uv run pytest -v`
Expected: PASS — version tests reflect 1.0.0, all other tests pass
