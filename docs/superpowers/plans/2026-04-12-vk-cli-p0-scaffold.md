# VK CLI Scaffolding Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-12-vk-cli-toolchain-design.md`
**Status:** Not Started

**Goal:** Create the walking skeleton — `vk --version` and `vk --help` work, one passing test, CI green.
**Architecture:** Standard Python `src/` layout with typer CLI, pytest, ruff, mypy. Entry point `vk = "vk.cli:app"`. Stub subcommand groups for all planned commands.
**Tech Stack:** Python 3.11+, uv, typer, pyyaml, rich, pytest, ruff, mypy

---

## Phase 1: Project skeleton [agentic]

### Task 1: pyproject.toml and package init

**Files:**
- Create: `pyproject.toml`
- Create: `src/vk/__init__.py`
- Create: `src/vk/__main__.py`
- Test: `tests/unit/test_version.py`

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py`, `tests/unit/__init__.py`, and `tests/unit/test_version.py`:

```python
# tests/__init__.py
# (empty)

# tests/unit/__init__.py
# (empty)

# tests/unit/test_version.py
from vk import __version__


def test_version_is_string():
    assert isinstance(__version__, str)


def test_version_is_semver():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_version_value():
    from vk import __version__
    assert __version__ == "0.3.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_version.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk'`

- [ ] **Step 3: Create pyproject.toml**

```toml
[project]
name = "vk"
version = "0.3.0"
description = "VK toolchain: phase-structured plans, GitHub Issue dispatch, progress tracking"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "pyyaml>=6",
    "rich>=13",
]

[project.scripts]
vk = "vk.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vk"]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "ruff>=0.6",
    "mypy>=1.11",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--strict-markers --cov=vk --cov-report=term-missing --cov-fail-under=85"

[tool.mypy]
strict = true
python_version = "3.11"
```

- [ ] **Step 4: Create src/vk/__init__.py**

```python
"""VK CLI toolchain."""

__version__ = "0.3.0"
```

- [ ] **Step 5: Create src/vk/__main__.py**

```python
"""Allow `python -m vk`."""

from vk.cli import app

app()
```

- [ ] **Step 6: Run uv sync and verify test passes**

Run: `uv sync && uv run pytest tests/unit/test_version.py -v`
Expected: PASS — all 3 tests pass

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "feat: scaffold Python package with version and pyproject.toml"
```

### Task 2: CLI app with stub subcommands

**Files:**
- Create: `src/vk/cli.py`
- Create: `src/vk/commands/__init__.py`
- Test: `tests/unit/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_cli.py
from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.3.0" in result.stdout


def test_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "plan" in result.stdout
    assert "dispatch" in result.stdout
    assert "progress" in result.stdout
    assert "execute" in result.stdout
    assert "init" in result.stdout
    assert "install-skills" in result.stdout


def test_plan_help():
    result = runner.invoke(app, ["plan", "--help"])
    assert result.exit_code == 0


def test_dispatch_help():
    result = runner.invoke(app, ["dispatch", "--help"])
    assert result.exit_code == 0


def test_progress_help():
    result = runner.invoke(app, ["progress", "--help"])
    assert result.exit_code == 0


def test_execute_help():
    result = runner.invoke(app, ["execute", "--help"])
    assert result.exit_code == 0


def test_init_help():
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vk.cli'`

- [ ] **Step 3: Write src/vk/cli.py**

```python
"""VK CLI — main entry point."""

from typing import Optional

import typer

from vk import __version__

app = typer.Typer(
    name="vk",
    help="VK toolchain: plans, dispatch, progress, execution.",
    no_args_is_help=True,
)

plan_app = typer.Typer(help="Write, save, and maintain plan files.")
dispatch_app = typer.Typer(help="Dispatch a phased plan to GitHub Issues.")
progress_app = typer.Typer(help="Track work lifecycle.")
execute_app = typer.Typer(help="Helpers for phase/task execution.")

app.add_typer(plan_app, name="plan")
app.add_typer(dispatch_app, name="dispatch")
app.add_typer(progress_app, name="progress")
app.add_typer(execute_app, name="execute")


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"vk {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """VK toolchain: plans, dispatch, progress, execution."""


@app.command()
def init(
    dispatch: Optional[str] = typer.Option(
        None, "--dispatch", help="Enable dispatch with OWNER/REPO."
    ),
    project: Optional[str] = typer.Option(
        None, "--project", help="Project board name."
    ),
) -> None:
    """Scaffold plan-config.yaml in a new repo."""
    typer.echo("vk init: not yet implemented")
    raise typer.Exit(1)


@app.command(name="install-skills")
def install_skills(
    copy: bool = typer.Option(False, "--copy", help="Copy instead of symlink."),
) -> None:
    """Symlink SKILL.md files into ~/.claude/skills/."""
    typer.echo("vk install-skills: not yet implemented")
    raise typer.Exit(1)


# Stub subcommands so --help works for each group

@plan_app.callback(invoke_without_command=True)
def plan_callback(ctx: typer.Context) -> None:
    """Write, save, and maintain plan files."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@dispatch_app.callback(invoke_without_command=True)
def dispatch_callback(ctx: typer.Context) -> None:
    """Dispatch a phased plan to GitHub Issues."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@progress_app.callback(invoke_without_command=True)
def progress_callback(ctx: typer.Context) -> None:
    """Track work lifecycle."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@execute_app.callback(invoke_without_command=True)
def execute_callback(ctx: typer.Context) -> None:
    """Helpers for phase/task execution."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
```

- [ ] **Step 4: Create src/vk/commands/__init__.py**

```python
# (empty — package marker)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: PASS — all 7 tests pass

- [ ] **Step 6: Run full suite with coverage**

Run: `uv run pytest -v`
Expected: PASS — all 10 tests pass, coverage ≥85%

- [ ] **Step 7: Commit**

```bash
git add src/vk/cli.py src/vk/commands/ tests/unit/test_cli.py
git commit -m "feat: add typer CLI with stub subcommand groups"
```

### Task 3: CI workflow and quality gates

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create tests/conftest.py**

```python
"""Shared pytest fixtures."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT
```

- [ ] **Step 2: Create .github/workflows/ci.yml**

```yaml
name: CI
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run ruff check src/ tests/
      - run: uv run ruff format --check src/ tests/

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run mypy src/

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run pytest
```

- [ ] **Step 3: Run lint locally**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
Expected: PASS — no lint errors, no format issues

- [ ] **Step 4: Run mypy locally**

Run: `uv run mypy src/`
Expected: PASS — no type errors (may need minor type annotation fixes)

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS — all tests pass, coverage ≥85%

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml tests/conftest.py
git commit -m "feat: add CI workflow with lint, typecheck, and test jobs"
```

- [ ] **Step 7: Generate uv.lock and final commit**

Run: `uv sync` (generates/updates `uv.lock`)

```bash
git add uv.lock
git commit -m "chore: add uv.lock"
```
