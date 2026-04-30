# vk issue command (Thread 4)

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-29-vk-cli-hygiene-and-issue-authoring-design.md`
**Status:** In Progress

**Goal:** Add a `vk issue` subcommand with two verbs — `create` (author a bridge-compatible GitHub Issue from a free-form topic) and `convert` (append the bridge contract to an existing plain Issue) — so agents and operators can file well-formed Issues without hand-assembling the `## Instruction` / `## Workspace` / `## Dependencies` sections.

**Architecture:** New `src/vk/commands/issue_cmd.py` exports a Typer app; registered in `src/vk/cli.py` as `vk issue`. Body-building logic lives in a private `_build_issue_body()` helper and is validated by the existing `validate_issue_body()` from `dispatch_body_validator.py`. Repo resolution calls `git remote get-url origin`. GitHub mutations run via `subprocess` + `gh` CLI (same pattern as `execute_cmd.py`). Phase 1 implements `create`; Phase 2 implements `convert` and bumps the version.

**Tech Stack:** Python 3.11+, Typer, `gh` CLI, pytest, `uv run vk`.

---

## Phase 1: `vk issue create` command [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/85 -->
**Depends on:** —

**Context:** The `create` subcommand is the primary use case — closing the brainstorm-to-Issue loop. It builds a bridge-compatible body, validates it, and optionally calls `gh issue create`. The `--dry-run` flag is critical for testing without GitHub side effects.

### Task 1: Tests for `vk issue create`

**Files:**
- Create: `tests/unit/test_issue_cmd.py`

- [ ] **Step 1: TDD — write failing tests for `create`**

```python
"""Tests for vk issue create subcommand."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vk.cli import app
from vk.commands.issue_cmd import _build_issue_body, _resolve_repo

runner = CliRunner()


class TestBuildIssueBody:
    def test_contains_all_required_sections(self) -> None:
        body = _build_issue_body(
            topic="Investigate the foo bug",
            skill="superpowers:brainstorming",
            repos="derio-net/superpowers-for-vk",
            blockers="None — no blocking phases.",
        )
        assert "## Instruction" in body
        assert "## Workspace" in body
        assert "## Dependencies" in body

    def test_topic_appears_in_body(self) -> None:
        body = _build_issue_body(
            topic="Investigate the foo bug",
            skill="superpowers:brainstorming",
            repos="derio-net/superpowers-for-vk",
            blockers="None — no blocking phases.",
        )
        assert "Investigate the foo bug" in body

    def test_skill_appears_in_instruction(self) -> None:
        body = _build_issue_body(
            topic="Topic",
            skill="superpowers:systematic-debugging",
            repos="derio-net/superpowers-for-vk",
            blockers="None — no blocking phases.",
        )
        assert "superpowers:systematic-debugging" in body

    def test_repos_appear_in_workspace(self) -> None:
        body = _build_issue_body(
            topic="Topic",
            skill="superpowers:brainstorming",
            repos="derio-net/frank",
            blockers="None — no blocking phases.",
        )
        assert "derio-net/frank" in body

    def test_body_validates_against_bridge_contract(self) -> None:
        from vk.commands.dispatch_body_validator import validate_issue_body
        body = _build_issue_body(
            topic="Some topic",
            skill="superpowers:brainstorming",
            repos="derio-net/superpowers-for-vk",
            blockers="None — no blocking phases.",
        )
        # Should not raise
        validate_issue_body(body, phase_number=0)

    def test_body_validates_with_blocker_lines(self) -> None:
        from vk.commands.dispatch_body_validator import validate_issue_body
        body = _build_issue_body(
            topic="Some topic",
            skill="superpowers:brainstorming",
            repos="derio-net/superpowers-for-vk",
            blockers="- Blocked by #42\n- Blocked by #43",
        )
        validate_issue_body(body, phase_number=0)


class TestCreateDryRun:
    def test_dry_run_prints_title_and_body(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "issue", "create",
                "Investigate the foo regression",
                "--dry-run",
                "--repo", "derio-net/superpowers-for-vk",
            ],
        )
        assert result.exit_code == 0
        assert "Investigate the foo regression" in result.output
        assert "## Instruction" in result.output

    def test_dry_run_does_not_call_gh(self) -> None:
        with patch("subprocess.run") as mock_run:
            result = runner.invoke(
                app,
                [
                    "issue", "create",
                    "Topic",
                    "--dry-run",
                    "--repo", "derio-net/superpowers-for-vk",
                ],
            )
        assert result.exit_code == 0
        mock_run.assert_not_called()

    def test_stdin_topic(self) -> None:
        result = runner.invoke(
            app,
            ["issue", "create", "-", "--dry-run", "--repo", "derio-net/superpowers-for-vk"],
            input="Topic from stdin\n",
        )
        assert result.exit_code == 0
        assert "Topic from stdin" in result.output

    def test_custom_skill(self) -> None:
        result = runner.invoke(
            app,
            [
                "issue", "create", "Topic",
                "--dry-run",
                "--skill", "superpowers:systematic-debugging",
                "--repo", "derio-net/superpowers-for-vk",
            ],
        )
        assert result.exit_code == 0
        assert "superpowers:systematic-debugging" in result.output
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_issue_cmd.py -x -q --no-cov 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or attribute errors — the module doesn't exist yet.

### Task 2: Implement `src/vk/commands/issue_cmd.py`

**Files:**
- Create: `src/vk/commands/issue_cmd.py`

- [ ] **Step 3: Create the module with `_build_issue_body` and `_resolve_repo`**

```python
"""vk issue — author bridge-compatible GitHub Issues."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from vk.commands.dispatch_body_validator import validate_issue_body

console = Console()
err_console = Console(stderr=True)

issue_app = typer.Typer(help="Author bridge-compatible GitHub Issues.")


def _resolve_repo(repo: str | None) -> str:
    """Resolve owner/repo from --repo flag or git remote origin."""
    if repo:
        return repo
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        # Strip SSH or HTTPS to owner/repo
        # git@github.com:owner/repo.git or https://github.com/owner/repo.git
        if url.startswith("git@"):
            # git@github.com:owner/repo.git
            path_part = url.split(":", 1)[-1]
        else:
            # https://github.com/owner/repo.git
            path_part = "/".join(url.rstrip("/").split("/")[-2:])
        return path_part.removesuffix(".git")
    except subprocess.CalledProcessError:
        err_console.print("Error: could not resolve repo from git remote. Pass --repo explicitly.")
        raise typer.Exit(2)


def _build_issue_body(topic: str, skill: str, repos: str, blockers: str) -> str:
    """Build a bridge-compatible Issue body."""
    return (
        f"{topic}\n\n"
        f"---\n\n"
        f"## Instruction\n\n"
        f"Use {skill} to explore the above and produce deliverables.\n\n"
        f"## Workspace\n\n"
        f"Repos: {repos}\n\n"
        f"## Dependencies\n\n"
        f"{blockers}\n"
    )


@issue_app.command()
def create(
    topic: str = typer.Argument(
        ...,
        help="Free-form problem description. Pass '-' to read from stdin.",
    ),
    skill: str = typer.Option(
        "superpowers:brainstorming",
        "--skill",
        help="Skill the next agent should use.",
    ),
    repo: str | None = typer.Option(
        None,
        "--repo",
        help="Target repo (owner/repo). Defaults to git remote origin.",
    ),
    blockers: str = typer.Option(
        "None — no blocking phases.",
        "--blockers",
        help="Dependency string for ## Dependencies section.",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Issue title. Defaults to first 72 chars of topic.",
    ),
    label: str = typer.Option(
        "vk-ready",
        "--label",
        help="Label to apply. Pass empty string to skip.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print output without creating Issue."),
) -> None:
    """Create a bridge-compatible GitHub Issue from a free-form topic."""
    if topic == "-":
        topic = sys.stdin.read().rstrip("\n")

    resolved_repo = _resolve_repo(repo)
    issue_title = title or topic[:72].rstrip()

    body = _build_issue_body(
        topic=topic,
        skill=skill,
        repos=resolved_repo,
        blockers=blockers,
    )

    try:
        validate_issue_body(body, phase_number=0)
    except Exception as exc:
        err_console.print(f"Error: generated body failed validation: {exc}")
        raise typer.Exit(1)

    if dry_run:
        console.print(f"[bold]Title:[/bold] {issue_title}")
        console.print(f"\n[bold]Body:[/bold]\n")
        console.print(body)
        raise typer.Exit(0)

    cmd = ["gh", "issue", "create", "--title", issue_title, "--body", body]
    if label:
        cmd += ["--label", label]
    cmd += ["--repo", resolved_repo]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        url = result.stdout.strip()
        console.print(f"Created: {url}")
    except subprocess.CalledProcessError as exc:
        err_console.print(f"Error: gh issue create failed: {exc.stderr.strip()}")
        raise typer.Exit(3)
```

### Task 3: Register in CLI

**Files:**
- Edit: `src/vk/cli.py`

- [ ] **Step 4: Register `issue_app` in `src/vk/cli.py`**

```python
# Add import
from vk.commands.issue_cmd import issue_app

# Add to app registrations
app.add_typer(issue_app, name="issue")
```

- [ ] **Step 5: Run all tests — no regressions**

```bash
uv run ruff format src/ tests/
uv run pytest -q --no-cov
```

Expected: all pass, including new `test_issue_cmd.py` tests.

- [ ] **Step 6: Smoke-test `vk issue create --dry-run`**

```bash
uv run vk issue create "Test topic for smoke test" \
  --dry-run \
  --repo derio-net/superpowers-for-vk
```

Expected: prints title and body with all three contract sections.

---

## Phase 2: `vk issue convert` + version bump [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/86 -->
**Depends on:** Phase 1

**Context:** `convert` retroactively makes existing plain Issues bridge-routable by appending the contract block. Also bumps the version since new user-visible subcommands shipped.

### Task 1: Tests for `vk issue convert`

**Files:**
- Edit: `tests/unit/test_issue_cmd.py`

- [x] **Step 1: TDD — write failing tests for `convert`**

Add to `tests/unit/test_issue_cmd.py`:

```python
class TestConvertDryRun:
    def test_dry_run_appends_contract_to_plain_body(self) -> None:
        plain_body = "This is a plain bug report without contract sections."
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = f'{{"body": "{plain_body}"}}'
            mock_run.return_value.returncode = 0
            result = runner.invoke(
                app,
                [
                    "issue", "convert", "42",
                    "--dry-run",
                    "--repo", "derio-net/superpowers-for-vk",
                ],
            )
        assert result.exit_code == 0
        assert "## Instruction" in result.output
        assert "## Workspace" in result.output
        assert "## Dependencies" in result.output
        assert plain_body in result.output

    def test_dry_run_noop_when_already_has_sections(self) -> None:
        body_with_contract = (
            "Topic\n\n---\n\n## Instruction\n\nUse skill.\n\n"
            "## Workspace\n\nRepos: org/repo\n\n## Dependencies\n\nNone — no blocking phases.\n"
        )
        import json
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps({"body": body_with_contract})
            mock_run.return_value.returncode = 0
            result = runner.invoke(
                app,
                [
                    "issue", "convert", "42",
                    "--dry-run",
                    "--repo", "derio-net/superpowers-for-vk",
                ],
            )
        assert result.exit_code == 0
        assert "already has contract sections" in result.output

    def test_convert_does_not_mutate_in_dry_run(self) -> None:
        plain_body = "Plain bug report."
        import json
        with patch("subprocess.run") as mock_run:
            # First call: gh issue view
            mock_run.return_value.stdout = json.dumps({"body": plain_body})
            mock_run.return_value.returncode = 0
            result = runner.invoke(
                app,
                ["issue", "convert", "42", "--dry-run", "--repo", "derio-net/superpowers-for-vk"],
            )
        assert result.exit_code == 0
        # Only one subprocess call (the view), not the edit
        assert mock_run.call_count == 1
```

- [x] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_issue_cmd.py::TestConvertDryRun -x -q --no-cov 2>&1 | head -20
```

### Task 2: Implement `vk issue convert`

**Files:**
- Edit: `src/vk/commands/issue_cmd.py`

- [x] **Step 3: Add `_build_contract_block()` helper and `convert` command**

Add to `issue_cmd.py`:

```python
_REQUIRED_SECTIONS = ("## Instruction", "## Workspace", "## Dependencies")


def _build_contract_block(skill: str, repos: str, blockers: str) -> str:
    """Build only the contract section block (no topic prefix)."""
    return (
        f"## Instruction\n\n"
        f"Use {skill} to explore the above and produce deliverables.\n\n"
        f"## Workspace\n\n"
        f"Repos: {repos}\n\n"
        f"## Dependencies\n\n"
        f"{blockers}\n"
    )


@issue_app.command()
def convert(
    number: int = typer.Argument(..., help="GitHub Issue number to convert."),
    repo: str | None = typer.Option(None, "--repo", help="Target repo (owner/repo)."),
    skill: str = typer.Option("superpowers:brainstorming", "--skill"),
    blockers: str = typer.Option("None — no blocking phases.", "--blockers"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Append bridge contract sections to an existing GitHub Issue."""
    resolved_repo = _resolve_repo(repo)

    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(number), "--repo", resolved_repo, "--json", "body"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        err_console.print(f"Error: could not fetch Issue #{number}: {exc.stderr.strip()}")
        raise typer.Exit(2)

    import json as _json
    existing_body = _json.loads(result.stdout).get("body", "")

    if all(section in existing_body for section in _REQUIRED_SECTIONS):
        console.print(f"Issue #{number} already has contract sections. Nothing to do.")
        raise typer.Exit(0)

    contract_block = _build_contract_block(
        skill=skill,
        repos=resolved_repo,
        blockers=blockers,
    )
    new_body = existing_body.rstrip("\n") + "\n\n---\n\n" + contract_block

    try:
        validate_issue_body(new_body, phase_number=0)
    except Exception as exc:
        err_console.print(f"Error: converted body failed validation: {exc}")
        raise typer.Exit(1)

    if dry_run:
        console.print(f"[bold]Converted body for Issue #{number}:[/bold]\n")
        console.print(new_body)
        raise typer.Exit(0)

    try:
        subprocess.run(
            ["gh", "issue", "edit", str(number), "--repo", resolved_repo, "--body", new_body],
            capture_output=True,
            text=True,
            check=True,
        )
        console.print(f"Issue #{number} updated with bridge contract.")
    except subprocess.CalledProcessError as exc:
        err_console.print(f"Error: gh issue edit failed: {exc.stderr.strip()}")
        raise typer.Exit(3)
```

- [x] **Step 4: Run all tests**

```bash
uv run ruff format src/ tests/
uv run pytest -q --no-cov
```

Expected: all pass.

### Task 3: Version bump

**Files:**
- Edit: `pyproject.toml`
- Edit: `.claude-plugin/plugin.json`
- Edit: `.claude-plugin/marketplace.json`

- [x] **Step 5: Bump version in all three files**

Find the current version:

```bash
uv run vk --version
```

Increment the patch number (e.g. `1.3.0` → `1.3.1`) in all three files:
- `pyproject.toml` → `[project].version`
- `.claude-plugin/plugin.json` → `.version`
- `.claude-plugin/marketplace.json` → `.plugins[0].version`

- [x] **Step 6: Run `uv sync` and confirm version**

```bash
uv sync
uv run vk --version
```

Expected: new version number printed.

- [x] **Step 7: Run `vk plan self-review` on both plans**

```bash
uv run vk plan self-review docs/superpowers/plans/2026-04-29-vk-spec-index-hygiene.md
uv run vk plan self-review docs/superpowers/plans/2026-04-29-vk-issue-command.md
```

Expected: both report `Self-review passed.`

- [x] **Step 8: Update spec index for both plans**

```bash
uv run vk plan spec-index docs/superpowers/plans/2026-04-29-vk-spec-index-hygiene.md --yes
uv run vk plan spec-index docs/superpowers/plans/2026-04-29-vk-issue-command.md --yes
```
