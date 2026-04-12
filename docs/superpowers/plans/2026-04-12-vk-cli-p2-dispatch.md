# VK CLI Dispatch Command Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-12-vk-cli-toolchain-design.md`
**Status:** Not Started

**Goal:** Implement `vk dispatch` -- the first real CLI subcommand. One bash call replaces ~10 tool uses and ~15 operator confirmations. Full flow: gate check, plan parse, format verification, idempotency check, issue creation via gh, project board addition, lifecycle field setting, tracking comment injection, plan commit, spec index update, summary output.
**Architecture:** `dispatch_cmd.py` orchestrates the flow using P1 core modules (config, plan parser, gh wrapper, git helpers, spec_index). `common.py` provides shared CLI primitives (`--dry-run`/`--yes` tri-state, Rich error formatting, confirmation prompts). Exit codes 0-4 encode distinct failure modes.
**Tech Stack:** Python 3.11+, typer, rich, pyyaml, pytest, typer.testing.CliRunner

---

## Phase 1: Dispatch command and shared CLI helpers [agentic]

### Task 1: Shared CLI helpers (`common.py`)

**Files:**
- Create: `src/vk/commands/common.py`
- Test: `tests/unit/test_common.py`

- [ ] **Step 1: Write the failing tests for tri-state flag validation and confirmation prompt**

Create `tests/unit/test_common.py`:

```python
# tests/unit/test_common.py
"""Tests for shared CLI helpers."""

from __future__ import annotations

import pytest

from vk.commands.common import (
    ConfirmAction,
    MutuallyExclusiveError,
    resolve_action,
    format_error,
    format_gate_refusal,
)


class TestResolveAction:
    """Tests for --dry-run / --yes tri-state resolution."""

    def test_default_returns_prompt(self) -> None:
        assert resolve_action(dry_run=False, yes=False) is ConfirmAction.PROMPT

    def test_dry_run_returns_dry_run(self) -> None:
        assert resolve_action(dry_run=True, yes=False) is ConfirmAction.DRY_RUN

    def test_yes_returns_apply(self) -> None:
        assert resolve_action(dry_run=False, yes=True) is ConfirmAction.APPLY

    def test_both_raises(self) -> None:
        with pytest.raises(MutuallyExclusiveError, match="mutually exclusive"):
            resolve_action(dry_run=True, yes=True)


class TestFormatError:
    """Tests for rich error formatting."""

    def test_format_error_includes_message(self) -> None:
        result = format_error("something broke", hint="try fixing it")
        assert "something broke" in result
        assert "try fixing it" in result

    def test_format_error_without_hint(self) -> None:
        result = format_error("something broke")
        assert "something broke" in result


class TestFormatGateRefusal:
    """Tests for dispatch gate refusal message."""

    def test_gate_refusal_includes_template(self) -> None:
        result = format_gate_refusal()
        assert "dispatch:" in result
        assert "plan-config.yaml" in result
        assert "target: github-issues" in result
        assert "owner:" in result
        assert "project_board:" in result
        assert "labels:" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_common.py -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'vk.commands.common'`

- [ ] **Step 3: Implement `common.py`**

Create `src/vk/commands/common.py`:

```python
"""Shared CLI helpers: tri-state flags, error formatting, confirmation prompts."""

from __future__ import annotations

import enum
import sys
from typing import NoReturn

import typer
from rich.console import Console
from rich.text import Text

err_console = Console(stderr=True)


class ConfirmAction(enum.Enum):
    """Result of resolving --dry-run / --yes flags."""

    DRY_RUN = "dry_run"
    PROMPT = "prompt"
    APPLY = "apply"


class MutuallyExclusiveError(typer.BadParameter):
    """Raised when --dry-run and --yes are both set."""

    def __init__(self) -> None:
        super().__init__("--dry-run and --yes are mutually exclusive")


def resolve_action(*, dry_run: bool, yes: bool) -> ConfirmAction:
    """Resolve the tri-state: dry-run, interactive prompt, or immediate apply.

    Raises MutuallyExclusiveError if both flags are set.
    """
    if dry_run and yes:
        raise MutuallyExclusiveError()
    if dry_run:
        return ConfirmAction.DRY_RUN
    if yes:
        return ConfirmAction.APPLY
    return ConfirmAction.PROMPT


def confirm_or_exit(message: str = "Proceed?") -> None:
    """Prompt the user for confirmation. Exit with code 0 if declined."""
    if not typer.confirm(message, default=False):
        raise typer.Exit(0)


def format_error(message: str, *, hint: str | None = None) -> str:
    """Format an error message with optional fix hint.

    Returns a plain string. Callers print via Rich or typer.echo.
    """
    lines = [f"Error: {message}"]
    if hint:
        lines.append(f"Hint: {hint}")
    return "\n".join(lines)


def die(message: str, *, code: int = 1, hint: str | None = None) -> NoReturn:
    """Print a Rich-formatted error to stderr and exit."""
    text = Text(f"Error: {message}", style="bold red")
    err_console.print(text)
    if hint:
        err_console.print(Text(f"Hint: {hint}", style="dim"))
    sys.exit(code)


_GATE_REFUSAL_TEMPLATE = """\
Dispatch unavailable -- no `dispatch:` block in `docs/superpowers/plan-config.yaml` for this repo.

To enable, add this to the file:

  dispatch:
    target: github-issues
    owner: <your-github-owner>
    project_board: "<Project Name>"
    default_repo: <owner>/<repo>
    labels:
      agentic: vk-ready
      manual: manual"""


def format_gate_refusal() -> str:
    """Return the canonical dispatch gate refusal message with paste-ready template."""
    return _GATE_REFUSAL_TEMPLATE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_common.py -v`
Expected: PASS -- all 7 tests pass

- [ ] **Step 5: Run quality gates**

Run: `uv run ruff check src/vk/commands/common.py tests/unit/test_common.py && uv run mypy src/vk/commands/common.py`
Expected: PASS -- no lint or type errors

- [ ] **Step 6: Commit**

```bash
git add src/vk/commands/common.py tests/unit/test_common.py
git commit -m "feat: add shared CLI helpers -- tri-state flags, error formatting, gate refusal"
```

### Task 2: gh contract tests (`test_gh.py`)

**Files:**
- Test: `tests/unit/test_gh.py`
- Verify: `src/vk/gh.py` (exists from P1)

- [ ] **Step 1: Write the contract tests for gh subprocess calls**

Create `tests/unit/test_gh.py`:

```python
# tests/unit/test_gh.py
"""Contract tests for gh subprocess wrapper.

These verify the exact command shapes passed to subprocess, not actual GitHub behavior.
All subprocess calls are mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vk.gh import (
    GhError,
    create_issue,
    edit_issue_labels,
    add_to_project,
    get_project_number,
    set_field,
)


@pytest.fixture()
def mock_run() -> MagicMock:
    """Patch subprocess.run and return the mock."""
    with patch("vk.gh.subprocess.run") as m:
        m.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/derio-net/my-repo/issues/42\n",
            stderr="",
        )
        yield m


class TestCreateIssue:
    """Verify exact gh issue create command shape."""

    def test_create_issue_command_shape(self, mock_run: MagicMock) -> None:
        url = create_issue(
            repo="derio-net/my-repo",
            title="my-feature-1-agentic",
            body="## Instruction\n\nDo the thing.",
        )

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["gh", "issue", "create"]
        assert "--repo" in cmd
        assert "derio-net/my-repo" in cmd
        assert "--title" in cmd
        assert "my-feature-1-agentic" in cmd
        assert "--body" in cmd
        assert url == "https://github.com/derio-net/my-repo/issues/42"

    def test_create_issue_failure_raises(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="HTTP 403: Must have admin access",
        )
        with pytest.raises(GhError, match="Must have admin access"):
            create_issue(
                repo="derio-net/my-repo",
                title="test",
                body="body",
            )


class TestEditIssueLabels:
    """Verify exact gh issue edit --add-label command shape."""

    def test_add_label_command_shape(self, mock_run: MagicMock) -> None:
        edit_issue_labels(
            repo="derio-net/my-repo",
            issue_number=42,
            add_labels=["vk-ready"],
        )

        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["gh", "issue", "edit"]
        assert "42" in [str(c) for c in cmd]
        assert "--add-label" in cmd
        assert "vk-ready" in cmd


class TestAddToProject:
    """Verify exact gh project item-add command shape."""

    def test_add_to_project_command_shape(self, mock_run: MagicMock) -> None:
        add_to_project(
            owner="derio-net",
            project_number=7,
            issue_url="https://github.com/derio-net/my-repo/issues/42",
        )

        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["gh", "project", "item-add"]
        assert "7" in [str(c) for c in cmd]
        assert "--owner" in cmd
        assert "derio-net" in cmd
        assert "--url" in cmd
        assert "https://github.com/derio-net/my-repo/issues/42" in cmd


class TestGetProjectNumber:
    """Verify gh project list query shape."""

    def test_get_project_number_command_shape(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"projects":[{"title":"Derio Ops","number":7}]}',
            stderr="",
        )
        num = get_project_number(owner="derio-net", project_name="Derio Ops")
        assert num == 7
        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["gh", "project", "list"]
        assert "--format" in cmd
        assert "json" in cmd


class TestSetField:
    """Verify gh project item-edit command shape."""

    def test_set_field_command_shape(self, mock_run: MagicMock) -> None:
        set_field(
            project_id="PVT_abc123",
            item_id="PVTI_item1",
            field_id="PVTSSF_field1",
            option_id="opt_plan",
        )

        cmd = mock_run.call_args[0][0]
        assert cmd[:3] == ["gh", "project", "item-edit"]
        assert "--project-id" in cmd
        assert "PVT_abc123" in cmd
        assert "--id" in cmd
        assert "PVTI_item1" in cmd
        assert "--field-id" in cmd
        assert "PVTSSF_field1" in cmd
        assert "--single-select-option-id" in cmd
        assert "opt_plan" in cmd
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_gh.py -v`
Expected: FAIL -- imports fail (functions not yet exposed or shaped for these signatures)

- [ ] **Step 3: Extend `src/vk/gh.py` with the dispatch-facing functions**

The P1 `gh.py` module provides the subprocess foundation. Add or update these functions to match the contract tests:

```python
# Additions to src/vk/gh.py (extend existing module)

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


class GhError(Exception):
    """Raised when a gh subprocess call fails."""

    def __init__(self, message: str, returncode: int = 1) -> None:
        super().__init__(message)
        self.returncode = returncode


def _run_gh(args: list[str]) -> str:
    """Run a gh CLI command and return stdout. Raise GhError on failure."""
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise GhError(result.stderr.strip(), result.returncode)
    return result.stdout.strip()


def create_issue(*, repo: str, title: str, body: str) -> str:
    """Create a GitHub Issue. Returns the issue URL."""
    return _run_gh([
        "gh", "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
    ])


def edit_issue_labels(
    *, repo: str, issue_number: int, add_labels: list[str]
) -> None:
    """Add labels to an existing issue."""
    _run_gh([
        "gh", "issue", "edit",
        str(issue_number),
        "--repo", repo,
        "--add-label", ",".join(add_labels),
    ])


def get_project_number(*, owner: str, project_name: str) -> int:
    """Look up a project board number by name."""
    raw = _run_gh([
        "gh", "project", "list",
        "--owner", owner,
        "--format", "json",
    ])
    data = json.loads(raw)
    for proj in data.get("projects", []):
        if proj["title"] == project_name:
            return int(proj["number"])
    raise GhError(f"Project '{project_name}' not found for owner '{owner}'")


def add_to_project(
    *, owner: str, project_number: int, issue_url: str
) -> None:
    """Add an issue to a project board."""
    _run_gh([
        "gh", "project", "item-add",
        str(project_number),
        "--owner", owner,
        "--url", issue_url,
    ])


def get_project_id(*, owner: str, project_number: int) -> str:
    """Get the project node ID."""
    raw = _run_gh([
        "gh", "project", "list",
        "--owner", owner,
        "--format", "json",
    ])
    data = json.loads(raw)
    for proj in data.get("projects", []):
        if proj["number"] == project_number:
            return str(proj["id"])
    raise GhError(f"Project #{project_number} not found for owner '{owner}'")


def get_item_id(
    *, owner: str, project_number: int, issue_url: str
) -> str:
    """Get the project item ID for a given issue URL."""
    raw = _run_gh([
        "gh", "project", "item-list",
        str(project_number),
        "--owner", owner,
        "--format", "json",
    ])
    data = json.loads(raw)
    for item in data.get("items", []):
        if item.get("content", {}).get("url") == issue_url:
            return str(item["id"])
    raise GhError(f"Item not found for URL: {issue_url}")


def get_field_id(
    *, owner: str, project_number: int, field_name: str
) -> str:
    """Get a project field ID by name."""
    raw = _run_gh([
        "gh", "project", "field-list",
        str(project_number),
        "--owner", owner,
        "--format", "json",
    ])
    data = json.loads(raw)
    for field in data.get("fields", []):
        if field["name"] == field_name:
            return str(field["id"])
    raise GhError(f"Field '{field_name}' not found in project #{project_number}")


def get_option_id(
    *, owner: str, project_number: int, field_name: str, option_name: str
) -> str:
    """Get a single-select option ID by name."""
    raw = _run_gh([
        "gh", "project", "field-list",
        str(project_number),
        "--owner", owner,
        "--format", "json",
    ])
    data = json.loads(raw)
    for field in data.get("fields", []):
        if field["name"] == field_name:
            for opt in field.get("options", []):
                if opt["name"] == option_name:
                    return str(opt["id"])
    raise GhError(
        f"Option '{option_name}' not found in field '{field_name}' "
        f"of project #{project_number}"
    )


def set_field(
    *,
    project_id: str,
    item_id: str,
    field_id: str,
    option_id: str,
) -> None:
    """Set a single-select field value on a project item."""
    _run_gh([
        "gh", "project", "item-edit",
        "--project-id", project_id,
        "--id", item_id,
        "--field-id", field_id,
        "--single-select-option-id", option_id,
    ])


def extract_issue_number(issue_url: str) -> int:
    """Extract the issue number from a GitHub issue URL."""
    parts = issue_url.rstrip("/").split("/")
    try:
        return int(parts[-1])
    except (ValueError, IndexError) as exc:
        raise GhError(f"Cannot extract issue number from URL: {issue_url}") from exc
```

- [ ] **Step 4: Run contract tests to verify they pass**

Run: `uv run pytest tests/unit/test_gh.py -v`
Expected: PASS -- all 7 tests pass

- [ ] **Step 5: Run quality gates**

Run: `uv run ruff check src/vk/gh.py tests/unit/test_gh.py && uv run mypy src/vk/gh.py`
Expected: PASS -- no lint or type errors

- [ ] **Step 6: Commit**

```bash
git add src/vk/gh.py tests/unit/test_gh.py
git commit -m "feat: add gh wrapper functions for dispatch -- create, label, project, field"
```

### Task 3: Dispatch command core logic (`dispatch_cmd.py`)

**Files:**
- Create: `src/vk/commands/dispatch_cmd.py`
- Modify: `src/vk/cli.py` (wire up subcommand)

- [ ] **Step 1: Write failing integration test for dry-run output**

Create `tests/integration/__init__.py` and `tests/integration/conftest.py` and `tests/integration/test_dispatch.py`:

```python
# tests/integration/__init__.py
# (empty)

# tests/integration/conftest.py
"""Integration test fixtures."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repo with plan-config.yaml."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
        check=True, capture_output=True,
    )
    # Create an initial commit so HEAD exists
    readme = tmp_path / "README.md"
    readme.write_text("# Test\n")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "."],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "init"],
        check=True, capture_output=True,
    )
    yield tmp_path


@pytest.fixture()
def dispatch_config(tmp_repo: Path) -> Path:
    """Create a dispatch-enabled plan-config.yaml."""
    config_dir = tmp_repo / "docs" / "superpowers"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "plan-config.yaml"
    config_file.write_text(textwrap.dedent("""\
        plan:
          filename: "YYYY-MM-DD-{name}.md"
          save_to: docs/superpowers/plans/

        header:
          required:
            - Spec
            - Status
          status_values:
            - Not Started
            - In Progress
            - Complete

        dispatch:
          target: github-issues
          owner: derio-net
          project_board: "Derio Ops"
          default_repo: derio-net/test-repo
          labels:
            agentic: vk-ready
            manual: manual
    """))
    return config_file


@pytest.fixture()
def phased_plan(tmp_repo: Path) -> Path:
    """Create a phased plan file for dispatch testing."""
    plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plans_dir / "2026-04-12-test-feature.md"
    plan_file.write_text(textwrap.dedent("""\
        # Test Feature Implementation Plan

        **Spec:** `docs/superpowers/specs/2026-04-12-test-feature.md`
        **Status:** Not Started

        **Goal:** Implement the test feature.

        ---

        ## Phase 1: Setup [agentic]

        ### Task 1: Create schema

        - [ ] **Step 1:** Write the test
        - [ ] **Step 2:** Implement

        ## Phase 2: Integration [manual]

        ### Task 1: Configure DNS

        - [ ] **Step 1:** Log in to dashboard
        - [ ] **Step 2:** Add records

        ## Phase 3: Finalize [agentic]

        ### Task 1: Write docs

        - [ ] **Step 1:** Draft README
    """))
    return plan_file
```

```python
# tests/integration/test_dispatch.py
"""CLI integration tests for vk dispatch."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()


class TestDispatchDryRun:
    """Dry-run output format and content."""

    def test_dry_run_shows_preview(
        self, dispatch_config: Path, phased_plan: Path, tmp_repo: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["dispatch", str(phased_plan), "--dry-run"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout or "dry run" in result.stdout.lower()
        assert "Phase 1" in result.stdout
        assert "Phase 2" in result.stdout
        assert "Phase 3" in result.stdout
        assert "agentic" in result.stdout
        assert "manual" in result.stdout
        assert "test-feature" in result.stdout

    def test_dry_run_shows_issue_titles(
        self, dispatch_config: Path, phased_plan: Path, tmp_repo: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["dispatch", str(phased_plan), "--dry-run"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 0
        assert "test-feature-1-agentic" in result.stdout
        assert "test-feature-2-manual" in result.stdout
        assert "test-feature-3-agentic" in result.stdout


class TestDispatchGateRefusal:
    """Gate check failures return exit code 1."""

    def test_no_config_file(self, tmp_repo: Path, phased_plan: Path) -> None:
        """No plan-config.yaml at all."""
        result = runner.invoke(
            app,
            ["dispatch", str(phased_plan), "--dry-run"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 1
        assert "dispatch" in result.stdout.lower() or "dispatch" in (result.stderr or "").lower()

    def test_dispatch_false(self, tmp_repo: Path, phased_plan: Path) -> None:
        """dispatch: false in config."""
        config_dir = tmp_repo / "docs" / "superpowers"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "plan-config.yaml"
        config_file.write_text("dispatch: false\n")
        result = runner.invoke(
            app,
            ["dispatch", str(phased_plan), "--dry-run"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 1

    def test_flat_plan_refused(
        self, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        """Flat plan cannot be dispatched."""
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        flat_plan = plans_dir / "2026-04-12-flat-thing.md"
        flat_plan.write_text(textwrap.dedent("""\
            # Flat Plan

            **Spec:** `specs/flat.md`
            **Status:** Not Started

            **Goal:** Do flat things.

            ---

            ### Task 1: Do something [agentic]

            - [ ] **Step 1:** Thing
        """))
        result = runner.invoke(
            app,
            ["dispatch", str(flat_plan), "--dry-run"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 2
        assert "flat" in result.stdout.lower() or "flat" in (result.stderr or "").lower()


class TestDispatchIdempotency:
    """Already-dispatched phases are skipped."""

    def test_skips_already_tracked_phases(
        self, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        """Phases with tracking comments are skipped."""
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plans_dir / "2026-04-12-tracked-feature.md"
        plan_file.write_text(textwrap.dedent("""\
            # Tracked Feature Plan

            **Spec:** `specs/tracked.md`
            **Status:** In Progress

            **Goal:** Already partially dispatched.

            ---

            ## Phase 1: Done [agentic]
            <!-- Tracking: https://github.com/derio-net/test-repo/issues/10 -->

            ### Task 1: Already done

            - [x] **Step 1:** Done

            ## Phase 2: New [agentic]

            ### Task 1: Not done yet

            - [ ] **Step 1:** Do it
        """))
        result = runner.invoke(
            app,
            ["dispatch", str(plan_file), "--dry-run"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 0
        assert "skip" in result.stdout.lower()
        # Phase 2 should still appear as pending
        assert "Phase 2" in result.stdout

    def test_all_tracked_exits_zero(
        self, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        """All phases already dispatched = noop, exit 0."""
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plans_dir / "2026-04-12-all-tracked.md"
        plan_file.write_text(textwrap.dedent("""\
            # All Tracked Plan

            **Spec:** `specs/tracked.md`
            **Status:** In Progress

            **Goal:** Fully dispatched.

            ---

            ## Phase 1: Done [agentic]
            <!-- Tracking: https://github.com/derio-net/test-repo/issues/10 -->

            ### Task 1: Done

            - [x] **Step 1:** Done
        """))
        result = runner.invoke(
            app,
            ["dispatch", str(plan_file), "--dry-run"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 0
        assert "already dispatched" in result.stdout.lower() or "noop" in result.stdout.lower()


class TestDispatchMutualExclusion:
    """--dry-run and --yes cannot be combined."""

    def test_both_flags_error(
        self, dispatch_config: Path, phased_plan: Path, tmp_repo: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["dispatch", str(phased_plan), "--dry-run", "--yes"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code != 0


class TestDispatchApply:
    """Apply mode with mocked gh creates correct issues."""

    @patch("vk.commands.dispatch_cmd.gh")
    def test_apply_creates_issues_and_injects_tracking(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        """Full apply: creates 3 issues, injects 3 tracking comments, commits."""
        # Mock gh responses
        issue_urls = [
            "https://github.com/derio-net/test-repo/issues/100",
            "https://github.com/derio-net/test-repo/issues/101",
            "https://github.com/derio-net/test-repo/issues/102",
        ]
        mock_gh.create_issue.side_effect = issue_urls
        mock_gh.extract_issue_number.side_effect = [100, 101, 102]
        mock_gh.get_project_number.return_value = 7
        mock_gh.get_project_id.return_value = "PVT_abc"
        mock_gh.get_item_id.side_effect = ["PVTI_1", "PVTI_2", "PVTI_3"]
        mock_gh.get_field_id.return_value = "PVTSSF_lifecycle"
        mock_gh.get_option_id.return_value = "opt_plan"

        result = runner.invoke(
            app,
            ["dispatch", str(phased_plan), "--yes"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 0

        # Verify issues were created
        assert mock_gh.create_issue.call_count == 3

        # Verify tracking comments were injected into the plan file
        updated = phased_plan.read_text()
        assert "<!-- Tracking: https://github.com/derio-net/test-repo/issues/100 -->" in updated
        assert "<!-- Tracking: https://github.com/derio-net/test-repo/issues/101 -->" in updated
        assert "<!-- Tracking: https://github.com/derio-net/test-repo/issues/102 -->" in updated

        # Verify labels: agentic phases get vk-ready, manual phases get manual
        label_calls = mock_gh.edit_issue_labels.call_args_list
        assert len(label_calls) == 3

    @patch("vk.commands.dispatch_cmd.gh")
    def test_partial_failure_returns_exit_4(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        """If one phase fails, others still proceed. Exit code 4."""
        from vk.gh import GhError

        mock_gh.create_issue.side_effect = [
            "https://github.com/derio-net/test-repo/issues/100",
            GhError("rate limited"),
            "https://github.com/derio-net/test-repo/issues/102",
        ]
        mock_gh.extract_issue_number.side_effect = [100, 102]
        mock_gh.get_project_number.return_value = 7
        mock_gh.get_project_id.return_value = "PVT_abc"
        mock_gh.get_item_id.side_effect = ["PVTI_1", "PVTI_3"]
        mock_gh.get_field_id.return_value = "PVTSSF_lifecycle"
        mock_gh.get_option_id.return_value = "opt_plan"

        result = runner.invoke(
            app,
            ["dispatch", str(phased_plan), "--yes"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 4
        # Phase 1 and 3 should still have tracking
        updated = phased_plan.read_text()
        assert "<!-- Tracking: https://github.com/derio-net/test-repo/issues/100 -->" in updated
        assert "issues/101" not in updated
        assert "<!-- Tracking: https://github.com/derio-net/test-repo/issues/102 -->" in updated
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_dispatch.py -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'vk.commands.dispatch_cmd'`

- [ ] **Step 3: Implement `dispatch_cmd.py`**

Create `src/vk/commands/dispatch_cmd.py`:

```python
"""vk dispatch -- dispatch a phased plan to GitHub Issues."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from vk import gh
from vk.commands.common import (
    ConfirmAction,
    confirm_or_exit,
    die,
    format_gate_refusal,
    resolve_action,
)
from vk.config import load_profile
from vk.plan.filename import derive_slug
from vk.plan.models import Phase, Plan, PlanFormat
from vk.plan.parser import parse_plan

console = Console()
err_console = Console(stderr=True)


def _find_repo_root(plan_path: Path) -> Path:
    """Find the git repo root for the plan file."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=plan_path.parent,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except FileNotFoundError:
        pass
    return plan_path.parent


def _gate_check(repo_root: Path) -> tuple[object, object]:
    """Load profile and verify dispatch is enabled. Die on failure.

    Returns (profile, dispatch_config) tuple.
    """
    profile = load_profile(repo_root)
    if not profile.dispatch_enabled:
        err_console.print(format_gate_refusal())
        raise typer.Exit(1)
    return profile, profile.dispatch


def _parse_and_validate(plan_path: Path) -> Plan:
    """Parse plan and verify it is phased format. Die on parse error."""
    try:
        plan = parse_plan(plan_path)
    except Exception as exc:
        die(f"Failed to parse plan: {exc}", code=2)
    if plan.format is not PlanFormat.PHASED:
        die("Cannot dispatch a flat plan.", code=2)
    if not plan.phases:
        die("No phases found in plan.", code=2)
    return plan


def _build_issue_title(slug: str, phase: Phase) -> str:
    """Build the issue title: {slug}-{phase_num}-{tag}."""
    return f"{slug}-{phase.number}-{phase.tag}"


def _build_issue_body_agentic(
    phase: Phase,
    plan_path: Path,
    repo: str,
    prev_issue_num: int | None,
) -> str:
    """Build issue body for an agentic phase."""
    lines = [
        "## Instruction",
        "",
        f"Use superpowers-for-vk:vk-execute to implement Phase {phase.number} of this plan.",
        "",
        "## Workspace",
        "",
        f"Repos: {repo}",
        "",
    ]
    if prev_issue_num is not None:
        lines.extend([
            "## Dependencies",
            "",
            f"- Blocked by #{prev_issue_num}",
            "",
        ])
    lines.extend([
        "---",
        "",
        f"**Plan file:** `{plan_path}`",
        f"**Phase:** {phase.number} -- {phase.title}",
    ])
    return "\n".join(lines)


def _build_issue_body_manual(
    phase: Phase,
    plan_path: Path,
    phase_body: str,
) -> str:
    """Build issue body for a manual phase."""
    lines = [
        f"# {phase.title}",
        "",
        "**Type:** Manual (operator runbook)",
        f"**Plan:** `{plan_path}`",
        f"**Phase:** {phase.number}",
        "",
        "---",
        "",
        phase_body,
    ]
    return "\n".join(lines)


def _extract_phase_body(plan_text: str, phase: Phase) -> str:
    """Extract the raw body text for a phase from the plan source."""
    pattern = rf"^## Phase {phase.number}:.*$"
    match = re.search(pattern, plan_text, re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    # Find next phase header or end of file
    next_match = re.search(r"^## Phase \d+:", plan_text[start:], re.MULTILINE)
    if next_match:
        end = start + next_match.start()
    else:
        end = len(plan_text)
    body = plan_text[start:end].strip()
    # Remove tracking comment if present
    body = re.sub(r"<!-- Tracking:.*?-->\n?", "", body).strip()
    return body


def _inject_tracking_comment(plan_text: str, phase_number: int, issue_url: str) -> str:
    """Insert <!-- Tracking: URL --> after the phase header line."""
    tracking = f"<!-- Tracking: {issue_url} -->"
    pattern = rf"(^## Phase {phase_number}:.*$)"
    replacement = rf"\1\n{tracking}"
    return re.sub(pattern, replacement, plan_text, count=1, flags=re.MULTILINE)


def _get_already_tracked(plan_text: str) -> dict[int, str]:
    """Extract phase_number -> tracking_url from existing tracking comments."""
    tracked: dict[int, str] = {}
    for match in re.finditer(
        r"^## Phase (\d+):.*\n<!-- Tracking: (https://\S+) -->",
        plan_text,
        re.MULTILINE,
    ):
        phase_num = int(match.group(1))
        url = match.group(2)
        tracked[phase_num] = url
    return tracked


def _print_dry_run(
    plan: Plan,
    slug: str,
    repo: str,
    skipped: set[int],
) -> None:
    """Print dry-run preview table."""
    console.print()
    console.print("[bold]DRY RUN -- vk dispatch[/bold]")
    console.print(f"Plan: {plan.title}")
    console.print(f"Slug: {slug}")
    console.print(f"Repo: {repo}")
    console.print()

    if not plan.phases:
        console.print("No phases to dispatch.")
        return

    all_skipped = all(p.number in skipped for p in plan.phases)
    if all_skipped:
        console.print("All phases already dispatched (noop).")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Phase")
    table.add_column("Type")
    table.add_column("Issue Title")
    table.add_column("Action")

    for phase in plan.phases:
        title = _build_issue_title(slug, phase)
        if phase.number in skipped:
            action = "[dim]skip (already tracked)[/dim]"
        else:
            action = "create"
        table.add_row(
            f"Phase {phase.number}: {phase.title}",
            str(phase.tag),
            title,
            action,
        )

    console.print(table)
    console.print()
    pending = len(plan.phases) - len(skipped)
    console.print(f"Phases to create: {pending}")


def _print_summary(
    plan: Plan,
    repo: str,
    results: dict[int, str],
    errors: dict[int, str],
    skipped: set[int],
) -> None:
    """Print post-apply summary table."""
    console.print()
    console.print("[bold]Plan Dispatched[/bold]")
    console.print(f"Plan: {plan.title}")
    console.print(f"Repo: {repo}")
    console.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Phase")
    table.add_column("Type")
    table.add_column("Issue")
    table.add_column("State")

    for phase in plan.phases:
        if phase.number in skipped:
            issue_col = "(skipped -- tracking exists)"
            state_col = "--"
        elif phase.number in results:
            url = results[phase.number]
            issue_col = url
            state_col = "plan"
        elif phase.number in errors:
            issue_col = f"FAILED: {errors[phase.number]}"
            state_col = "error"
        else:
            issue_col = "--"
            state_col = "--"
        table.add_row(
            f"Phase {phase.number}: {phase.title}",
            str(phase.tag),
            issue_col,
            state_col,
        )

    console.print(table)


def dispatch(
    plan_path: Path = typer.Argument(
        ...,
        help="Path to the phased plan file.",
        exists=True,
        readable=True,
    ),
    repo: str | None = typer.Option(
        None, "--repo",
        help="Target repo (OWNER/REPO). Defaults to config default_repo.",
    ),
    project: str | None = typer.Option(
        None, "--project",
        help="Project board name. Defaults to config project_board.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without mutations."),
    yes: bool = typer.Option(False, "--yes", help="Execute without confirmation."),
) -> None:
    """Dispatch a phased plan to GitHub Issues."""
    # Resolve action mode
    try:
        action = resolve_action(dry_run=dry_run, yes=yes)
    except Exception:
        die("--dry-run and --yes are mutually exclusive", code=1)

    plan_path = Path(plan_path).resolve()
    repo_root = _find_repo_root(plan_path)

    # Gate check
    profile, dispatch_cfg = _gate_check(repo_root)
    assert dispatch_cfg is not None  # guaranteed by gate check

    # Resolve target repo and project
    target_repo = repo or dispatch_cfg.default_repo
    target_project = project or dispatch_cfg.project_board

    # Parse and validate plan
    plan = _parse_and_validate(plan_path)
    slug = derive_slug(plan_path)

    # Read plan text for idempotency check and tracking injection
    plan_text = plan_path.read_text()
    already_tracked = _get_already_tracked(plan_text)
    skipped = set(already_tracked.keys())

    # Dry-run mode
    if action is ConfirmAction.DRY_RUN:
        _print_dry_run(plan, slug, target_repo, skipped)
        all_skipped = all(p.number in skipped for p in plan.phases)
        if all_skipped:
            console.print("All phases already dispatched (noop).")
        raise typer.Exit(0)

    # Interactive prompt mode
    if action is ConfirmAction.PROMPT:
        _print_dry_run(plan, slug, target_repo, skipped)
        pending = [p for p in plan.phases if p.number not in skipped]
        if not pending:
            console.print("All phases already dispatched (noop).")
            raise typer.Exit(0)
        confirm_or_exit()

    # Check if all already dispatched (for --yes mode)
    pending_phases = [p for p in plan.phases if p.number not in skipped]
    if not pending_phases:
        console.print("All phases already dispatched (noop).")
        raise typer.Exit(0)

    # Apply mode: create issues
    results: dict[int, str] = {}
    errors: dict[int, str] = {}
    phase_to_issue: dict[int, int] = {}

    # Pre-populate phase_to_issue from already-tracked phases
    for phase_num, url in already_tracked.items():
        try:
            phase_to_issue[phase_num] = gh.extract_issue_number(url)
        except gh.GhError:
            pass

    # Look up project board metadata once
    try:
        project_number = gh.get_project_number(
            owner=dispatch_cfg.owner,
            project_name=target_project,
        )
        project_id = gh.get_project_id(
            owner=dispatch_cfg.owner,
            project_number=project_number,
        )
        lifecycle_field_id = gh.get_field_id(
            owner=dispatch_cfg.owner,
            project_number=project_number,
            field_name="Lifecycle",
        )
        plan_option_id = gh.get_option_id(
            owner=dispatch_cfg.owner,
            project_number=project_number,
            field_name="Lifecycle",
            option_name="plan",
        )
    except gh.GhError as exc:
        die(f"Failed to query project board: {exc}", code=3)

    for phase in plan.phases:
        if phase.number in skipped:
            continue

        title = _build_issue_title(slug, phase)
        prev_num = phase_to_issue.get(phase.number - 1)

        if phase.tag == "manual":
            body = _build_issue_body_manual(
                phase, plan_path,
                _extract_phase_body(plan_text, phase),
            )
        else:
            body = _build_issue_body_agentic(phase, plan_path, target_repo, prev_num)

        try:
            # Create issue (without label for agentic -- add label after body is set)
            issue_url = gh.create_issue(
                repo=target_repo,
                title=title,
                body=body,
            )
            issue_num = gh.extract_issue_number(issue_url)
            phase_to_issue[phase.number] = issue_num
            results[phase.number] = issue_url

            # Add label
            label = (
                dispatch_cfg.labels.get("agentic", "vk-ready")
                if phase.tag == "agentic"
                else dispatch_cfg.labels.get("manual", "manual")
            )
            gh.edit_issue_labels(
                repo=target_repo,
                issue_number=issue_num,
                add_labels=[label],
            )

            # Add to project board
            gh.add_to_project(
                owner=dispatch_cfg.owner,
                project_number=project_number,
                issue_url=issue_url,
            )

            # Set lifecycle field to "plan"
            item_id = gh.get_item_id(
                owner=dispatch_cfg.owner,
                project_number=project_number,
                issue_url=issue_url,
            )
            gh.set_field(
                project_id=project_id,
                item_id=item_id,
                field_id=lifecycle_field_id,
                option_id=plan_option_id,
            )

            # Inject tracking comment into plan text
            plan_text = _inject_tracking_comment(plan_text, phase.number, issue_url)

        except gh.GhError as exc:
            errors[phase.number] = str(exc)
            continue

    # Write updated plan file with tracking comments
    plan_path.write_text(plan_text)

    # Update spec index if plan references a spec
    if plan.spec:
        spec_path = repo_root / plan.spec
        if spec_path.exists():
            try:
                from vk.spec_index import update_spec_index

                update_spec_index(
                    spec_path=spec_path,
                    plan_path=plan_path,
                    status=plan.status,
                )
                subprocess.run(
                    ["git", "add", str(spec_path)],
                    capture_output=True,
                    text=True,
                    cwd=repo_root,
                )
            except Exception:
                pass  # Non-fatal: spec index update failure should not block dispatch

    # Commit the updated plan file
    try:
        subprocess.run(
            ["git", "add", str(plan_path)],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        subprocess.run(
            ["git", "commit", "-m", "chore: link plan phases to GitHub Issues (vk-dispatch)"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
    except Exception:
        pass  # Skip commit if not in a git repo or nothing to commit

    # Print summary
    _print_summary(plan, target_repo, results, errors, skipped)

    # Exit code
    if errors and results:
        raise typer.Exit(4)  # partial success
    elif errors and not results:
        raise typer.Exit(3)  # all failed
    else:
        raise typer.Exit(0)  # full success or noop
```

- [ ] **Step 4: Wire dispatch into `cli.py`**

In `src/vk/cli.py`, replace the `dispatch_app` stub callback with the real command. Remove the `dispatch_app = typer.Typer(...)` and `app.add_typer(dispatch_app, ...)` lines. Instead register `dispatch` as a direct command:

```python
# In src/vk/cli.py -- add import and register the dispatch command
from vk.commands.dispatch_cmd import dispatch

app.command(name="dispatch")(dispatch)
```

Remove the old `dispatch_app` typer group and its `dispatch_callback` function from `cli.py`. The `dispatch` function from `dispatch_cmd.py` registers directly as `vk dispatch`.

- [ ] **Step 5: Run integration tests**

Run: `uv run pytest tests/integration/test_dispatch.py -v`
Expected: PASS -- all tests pass

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS -- all tests pass, coverage >=85%

- [ ] **Step 7: Run quality gates**

Run: `uv run ruff check src/vk/commands/dispatch_cmd.py && uv run mypy src/vk/commands/dispatch_cmd.py`
Expected: PASS -- no lint or type errors

- [ ] **Step 8: Commit**

```bash
git add src/vk/commands/dispatch_cmd.py src/vk/cli.py tests/integration/
git commit -m "feat: implement vk dispatch command -- full flow with dry-run, apply, idempotency"
```

### Task 4: Dispatch exit code coverage and edge cases

**Files:**
- Modify: `tests/integration/test_dispatch.py`
- Modify: `src/vk/commands/dispatch_cmd.py`

- [ ] **Step 1: Write failing tests for remaining exit codes and edge cases**

Append to `tests/integration/test_dispatch.py`:

```python
class TestDispatchExitCodes:
    """Verify all five exit codes are correctly produced."""

    @patch("vk.commands.dispatch_cmd.gh")
    def test_exit_3_on_total_gh_failure(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        phased_plan: Path,
        tmp_repo: Path,
    ) -> None:
        """All phases fail = exit 3."""
        from vk.gh import GhError

        mock_gh.create_issue.side_effect = GhError("auth failed")
        mock_gh.get_project_number.return_value = 7
        mock_gh.get_project_id.return_value = "PVT_abc"
        mock_gh.get_field_id.return_value = "PVTSSF_lifecycle"
        mock_gh.get_option_id.return_value = "opt_plan"

        result = runner.invoke(
            app,
            ["dispatch", str(phased_plan), "--yes"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 3

    def test_exit_2_on_nonexistent_plan(self, dispatch_config: Path, tmp_repo: Path) -> None:
        """Plan file does not exist = typer exits before we get to parse."""
        result = runner.invoke(
            app,
            ["dispatch", "/nonexistent/plan.md", "--dry-run"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code != 0

    def test_exit_2_on_no_phase_headers(
        self, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        """Plan parses but has no phase headers = exit 2."""
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        bad_plan = plans_dir / "2026-04-12-bad-plan.md"
        bad_plan.write_text(textwrap.dedent("""\
            # Bad Plan

            **Spec:** `specs/bad.md`
            **Status:** Not Started

            **Goal:** Nothing.

            ---

            Just some text, no phases at all.
        """))
        result = runner.invoke(
            app,
            ["dispatch", str(bad_plan), "--dry-run"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 2


class TestDispatchRepoOverride:
    """--repo and --project override config defaults."""

    def test_repo_override_in_dry_run(
        self, dispatch_config: Path, phased_plan: Path, tmp_repo: Path
    ) -> None:
        result = runner.invoke(
            app,
            ["dispatch", str(phased_plan), "--repo", "other-org/other-repo", "--dry-run"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 0
        assert "other-org/other-repo" in result.stdout
```

- [ ] **Step 2: Run new tests to verify they fail (for genuinely new assertions)**

Run: `uv run pytest tests/integration/test_dispatch.py -v -k "ExitCodes or RepoOverride"`
Expected: Some tests fail because edge case handling may need refinement

- [ ] **Step 3: Fix any failing edge case handling in `dispatch_cmd.py`**

Ensure:
- Plan file not found: typer's `exists=True` on the Argument handles this before dispatch logic runs. If the plan parses as flat or has zero phases, exit 2.
- All gh calls fail: if `results` is empty and `errors` is non-empty, exit 3.
- `--repo` override: the `target_repo` variable already respects the `--repo` flag.

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS -- all tests pass

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_dispatch.py src/vk/commands/dispatch_cmd.py
git commit -m "test: add dispatch exit code and edge case coverage"
```

### Task 5: Spec index update after dispatch

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`
- Test: `tests/integration/test_dispatch.py`

- [ ] **Step 1: Write failing test for spec index update**

Append to `tests/integration/test_dispatch.py`:

```python
class TestDispatchSpecIndex:
    """After dispatch, the spec's Implementation Plans table is updated."""

    @patch("vk.commands.dispatch_cmd.gh")
    def test_spec_index_updated_after_dispatch(
        self,
        mock_gh: MagicMock,
        dispatch_config: Path,
        tmp_repo: Path,
    ) -> None:
        """Spec file gets an updated plan index row."""
        # Create spec with index table
        specs_dir = tmp_repo / "docs" / "superpowers" / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        spec_file = specs_dir / "2026-04-12-test-feature.md"
        spec_file.write_text(textwrap.dedent("""\
            # Test Feature Spec

            ## Implementation Plans

            | Plan | Repo | File | Status | Depends on |
            |------|------|------|--------|------------|
        """))

        # Create plan referencing this spec
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_file = plans_dir / "2026-04-12-test-feature.md"
        plan_file.write_text(textwrap.dedent("""\
            # Test Feature Plan

            **Spec:** `docs/superpowers/specs/2026-04-12-test-feature.md`
            **Status:** Not Started

            **Goal:** Build it.

            ---

            ## Phase 1: Build [agentic]

            ### Task 1: Code

            - [ ] **Step 1:** Write code
        """))

        mock_gh.create_issue.return_value = "https://github.com/derio-net/test-repo/issues/50"
        mock_gh.extract_issue_number.return_value = 50
        mock_gh.get_project_number.return_value = 7
        mock_gh.get_project_id.return_value = "PVT_abc"
        mock_gh.get_item_id.return_value = "PVTI_1"
        mock_gh.get_field_id.return_value = "PVTSSF_lifecycle"
        mock_gh.get_option_id.return_value = "opt_plan"

        result = runner.invoke(
            app,
            ["dispatch", str(plan_file), "--yes"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 0

        # Spec index should be updated
        updated_spec = spec_file.read_text()
        assert "test-feature" in updated_spec.lower() or "Test Feature" in updated_spec
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_dispatch.py::TestDispatchSpecIndex -v`
Expected: FAIL -- spec index not updated yet

- [ ] **Step 3: Verify spec index update is wired into dispatch flow**

The spec index update logic was already added in Task 3, Step 3 (inside `dispatch_cmd.py`). If the test still fails, check that `vk.spec_index.update_spec_index` is correctly imported and called, and that the spec path resolution from the plan's `**Spec:**` header is working.

If the import fails because `spec_index` is not yet implemented (P1 dependency), add a guarded import:

```python
# In dispatch_cmd.py, in the spec index update block
try:
    from vk.spec_index import update_spec_index
    update_spec_index(spec_path=spec_path, plan_path=plan_path, status=plan.status)
except ImportError:
    pass  # spec_index module not yet available (P1 dependency)
except Exception:
    pass  # Non-fatal
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_dispatch.py::TestDispatchSpecIndex -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS -- all tests pass

- [ ] **Step 6: Commit**

```bash
git add src/vk/commands/dispatch_cmd.py tests/integration/test_dispatch.py
git commit -m "feat: update spec index after dispatch"
```

### Task 6: Version bump and final validation

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/vk/__init__.py`
- Test: `tests/unit/test_version.py`

- [ ] **Step 1: Update version test expectation**

In `tests/unit/test_version.py`, update the version assertion:

```python
def test_version_value():
    from vk import __version__
    assert __version__ == "0.4.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_version.py::test_version_value -v`
Expected: FAIL -- version is still 0.3.0

- [ ] **Step 3: Bump version in pyproject.toml and __init__.py**

In `pyproject.toml`:
```toml
version = "0.4.0"
```

In `src/vk/__init__.py`:
```python
__version__ = "0.4.0"
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS -- all tests pass, coverage >=85%

- [ ] **Step 5: Run all quality gates**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/ && uv run mypy src/`
Expected: PASS -- no lint, format, or type errors

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/vk/__init__.py tests/unit/test_version.py
git commit -m "chore: bump to v0.4.0 -- first usable CLI with vk dispatch"
```
