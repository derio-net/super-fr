# Label Lifecycle Fix Phase 3 Implementation Plan: `vk admin labels-sync`

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-27-label-lifecycle-fix-design.md`
**Status:** Not Started

**Goal:** Add `vk admin labels-sync` — a one-shot operator command that brings every `derio-net/*` repo into line with the canonical label registry. Default mode is dry-run; `--yes` applies. With `--remove-defaults`, the command also removes GitHub's auto-created default labels (`bug`, `documentation`, `duplicate`, `enhancement`, `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`) — but only when they have *zero* attached Issues, to avoid clobbering hand-applied user data. Per-repo errors are non-blocking; one repo with a permission glitch should not abort an org-wide sweep.

**Architecture:** New module `src/vk/commands/admin_cmd.py` introduces the `vk admin` command group, wired into `src/vk/main.py` next to the existing groups. Three new `gh.py` helpers (`list_labels`, `list_repos`, `delete_label`) wrap idiomatic `gh` calls. A diff function compares each repo's current labels to the registry and produces three buckets (`create`, `update`, `remove`); a separate function lists default labels that are removable (with `--remove-defaults`) by querying Issue counts. Dry-run mode prints a per-repo table via Rich and exits 0. Apply mode prints the same table, executes the actions via `gh label create --force` / `gh label delete --yes`, and prints a one-line summary per repo. Org-wide errors accumulate; final exit is non-zero if any repo failed.

**Tech Stack:** Python 3.11+, Typer, `gh` CLI, Rich, pytest.

**Depends on the label registry shipping in `2026-04-27-label-lifecycle-fix-phase-1.md`.**

**PR strategy:** Each internal phase ships as its own PR. Phase 3's version bump is the cap.

---

## Phase 1: gh helpers, admin module skeleton, repo enumeration [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/63 -->
**Depends on:** —

**Context:** Foundation work. Three new `gh.py` helpers, a new `admin_cmd.py` module wired into `main.py`, and the repo-enumeration helper that drives the rest of the command. No business logic yet.

### Task 1: New `gh.py` helpers

**Files:**
- Modify: `src/vk/gh.py`
- Modify: `tests/unit/test_gh.py`

- [x] **Step 1: TDD — `list_labels`, `list_repos`, `delete_label`**

Add to `tests/unit/test_gh.py`:

```python
class TestListLabels:
    def test_returns_parsed_label_objects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json
        captured: list[list[str]] = []
        def fake(args: list[str]) -> str:
            captured.append(args)
            return json.dumps([
                {"name": "vk-ready", "color": "0E8AE6", "description": "queued"},
                {"name": "bug",      "color": "d73a4a", "description": "Something's wrong"},
            ])
        monkeypatch.setattr(gh, "_run_gh", fake)
        labels = gh.list_labels(repo="o/r")
        assert labels[0]["name"]  == "vk-ready"
        assert labels[0]["color"] == "0E8AE6"
        assert labels[1]["name"]  == "bug"
        assert captured[0] == [
            "label", "list", "--repo", "o/r",
            "--json", "name,color,description",
            "--limit", "200",
        ]


class TestListRepos:
    def test_returns_non_archived_repos(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json
        def fake(args: list[str]) -> str:
            return json.dumps([
                {"name": "frank",    "isArchived": False},
                {"name": "old-repo", "isArchived": True},
                {"name": "willikins", "isArchived": False},
            ])
        monkeypatch.setattr(gh, "_run_gh", fake)
        repos = gh.list_repos(owner="derio-net")
        assert [r["name"] for r in repos] == ["frank", "willikins"]


class TestDeleteLabel:
    def test_emits_delete_yes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[list[str]] = []
        monkeypatch.setattr(gh, "_run_gh",
                            lambda args: captured.append(args) or "")
        gh.delete_label(repo="o/r", name="bug")
        assert captured == [[
            "label", "delete", "bug", "--repo", "o/r", "--yes",
        ]]
```

- [x] **Step 2: Implement `list_labels`, `list_repos`, `delete_label`**

Add to `src/vk/gh.py`:

```python
def list_labels(*, repo: str) -> list[dict]:
    """Return existing labels on the repo as parsed JSON."""
    import json
    out = _run_gh([
        "label", "list", "--repo", repo,
        "--json", "name,color,description",
        "--limit", "200",
    ])
    return json.loads(out) if out else []


def list_repos(*, owner: str) -> list[dict]:
    """Return non-archived repos under the given owner.

    Returns repo objects with `name` (and other fields gh exposes).
    """
    import json
    out = _run_gh([
        "repo", "list", owner,
        "--json", "name,isArchived",
        "--limit", "200",
    ])
    repos = json.loads(out) if out else []
    return [r for r in repos if not r.get("isArchived", False)]


def delete_label(*, repo: str, name: str) -> None:
    """Delete a label from the repo. `--yes` skips gh's confirmation prompt."""
    _run_gh(["label", "delete", name, "--repo", repo, "--yes"])
```

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_gh.py -q --no-cov
```

Expected: existing + 3 new pass.

### Task 2: `vk admin` skeleton

**Files:**
- Add: `src/vk/commands/admin_cmd.py`
- Modify: `src/vk/main.py`
- Add: `tests/unit/test_admin_skeleton.py`

- [x] **Step 1: Create `admin_cmd.py` skeleton**

`src/vk/commands/admin_cmd.py`:

```python
"""vk admin — operator-driven cross-repo administration."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()
err_console = Console(stderr=True)

admin_app = typer.Typer(help="Operator-driven cross-repo administration.")


@admin_app.command(name="labels-sync")
def labels_sync(
    owner: str = typer.Option(..., "--owner", help="GitHub owner / org."),
    repo: str | None = typer.Option(
        None, "--repo", help="Single repo (without owner). Default: all repos under owner."
    ),
    remove_defaults: bool = typer.Option(
        False, "--remove-defaults",
        help="Also remove GitHub default labels with zero attached Issues."
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply",
        help="Print planned changes without mutating (default). Use --apply or --yes."
    ),
    yes: bool = typer.Option(False, "--yes", help="Apply changes without confirmation."),
) -> None:
    """Sync repo labels to the canonical registry across one or many repos."""
    if yes:
        dry_run = False
    # Body is wired in Phase 2 of this plan; apply mode in Phase 3.
    raise NotImplementedError("labels-sync body lands in Phase 2 of this plan.")
```

- [x] **Step 2: Wire into `main.py`**

In `src/vk/main.py`, register the new app alongside existing groups:

```bash
grep -n "add_typer\|Typer" src/vk/main.py
```

Add: `app.add_typer(admin_app, name="admin")`

- [x] **Step 3: Skeleton-level tests**

`tests/unit/test_admin_skeleton.py`:

```python
"""Skeleton tests for vk admin labels-sync — body is in later phases."""

from typer.testing import CliRunner

from vk.commands.admin_cmd import admin_app


runner = CliRunner()


def test_labels_sync_help_lists_flags() -> None:
    result = runner.invoke(admin_app, ["labels-sync", "--help"])
    assert result.exit_code == 0
    for flag in ("--owner", "--repo", "--remove-defaults",
                 "--dry-run", "--yes"):
        assert flag in result.stdout


def test_labels_sync_requires_owner() -> None:
    result = runner.invoke(admin_app, ["labels-sync"])
    assert result.exit_code != 0  # missing --owner
```

- [x] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_admin_skeleton.py -q --no-cov
```

Expected: 2 passed.

### Task 3: Repo enumeration logic

**Files:**
- Modify: `src/vk/commands/admin_cmd.py`
- Add: `tests/unit/test_admin_repo_enumeration.py`

- [x] **Step 1: TDD — `_resolve_target_repos`**

`tests/unit/test_admin_repo_enumeration.py`:

```python
"""Tests for the repo-enumeration helper used by vk admin labels-sync."""

import pytest

from vk import gh
from vk.commands.admin_cmd import _resolve_target_repos


class TestResolveTargetReposExplicit:
    def test_single_repo_skips_listing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = {"n": 0}
        def fake_list(*, owner: str) -> list[dict]:
            called["n"] += 1
            return []
        monkeypatch.setattr(gh, "list_repos", fake_list)
        result = _resolve_target_repos(owner="derio-net", repo="frank")
        assert result == ["derio-net/frank"]
        assert called["n"] == 0  # never called list_repos


class TestResolveTargetReposOrgWide:
    def test_lists_all_non_archived(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gh, "list_repos", lambda *, owner: [
            {"name": "frank"}, {"name": "willikins"}
        ])
        result = _resolve_target_repos(owner="derio-net", repo=None)
        assert result == ["derio-net/frank", "derio-net/willikins"]
```

- [x] **Step 2: Implement `_resolve_target_repos`**

In `src/vk/commands/admin_cmd.py`:

```python
from vk import gh


def _resolve_target_repos(*, owner: str, repo: str | None) -> list[str]:
    """Resolve target repos as `owner/name` slugs.

    With explicit `repo`, returns the single slug. Without, enumerates
    non-archived repos under `owner` via gh.list_repos.
    """
    if repo:
        return [f"{owner}/{repo}"]
    return [f"{owner}/{r['name']}" for r in gh.list_repos(owner=owner)]
```

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_admin_repo_enumeration.py -q --no-cov
```

Expected: 2 passed.

### Task 4: Format, type-check, full suite, commit

- [x] **Step 1: Format and type-check**

```bash
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/
```

Expected: clean.

- [x] **Step 2: Full suite**

```bash
uv run pytest -q --no-cov
```

Expected: green.

- [ ] **Step 3: Commit and PR**

```bash
git checkout -b labels-sync-phase-1-skeleton
git add src/vk/gh.py src/vk/commands/admin_cmd.py src/vk/main.py \
        tests/unit/test_gh.py tests/unit/test_admin_skeleton.py \
        tests/unit/test_admin_repo_enumeration.py
git commit -m "feat(admin): vk admin labels-sync skeleton + gh helpers"
git push -u origin labels-sync-phase-1-skeleton
gh pr create --title "Labels-sync Phase 1 · Module skeleton + gh helpers + repo enumeration" \
  --body "Foundation for vk admin labels-sync. No diff/apply logic yet — that lands in Phase 2."
```

---

## Phase 2: Diff logic, dry-run rendering, default-label removal logic [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/64 -->
**Depends on:** Phase 1

**Context:** The brain of the command. Compares each repo's existing labels to the registry, computes `create` / `update` / `remove` buckets, and renders the dry-run table. With `--remove-defaults`, also queries Issue counts to filter the `remove` bucket to defaults that have zero attached Issues. Apply mode is still stubbed.

### Task 1: `_diff_labels` — compute action buckets

**Files:**
- Modify: `src/vk/commands/admin_cmd.py`
- Add: `tests/unit/test_admin_diff.py`

- [x] **Step 1: TDD — `_diff_labels` cases**

`tests/unit/test_admin_diff.py`:

```python
"""Tests for the registry-diff logic in vk admin labels-sync."""

from vk import labels
from vk.commands.admin_cmd import _diff_labels, LabelAction


def _existing(name: str, color: str, desc: str = "") -> dict:
    return {"name": name, "color": color, "description": desc}


class TestDiffLabelsCreate:
    def test_registry_label_missing_yields_create(self) -> None:
        existing = []
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert len(actions) == 1
        assert actions[0].kind   == "create"
        assert actions[0].name   == "vk-ready"
        assert actions[0].new_color == "0E8AE6"


class TestDiffLabelsUpdate:
    def test_wrong_color_yields_update(self) -> None:
        existing = [_existing("vk-ready", "aaaaaa", "")]
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert actions[0].kind == "update"
        assert actions[0].old_color == "aaaaaa"
        assert actions[0].new_color == "0E8AE6"

    def test_wrong_description_yields_update(self) -> None:
        existing = [_existing("vk-ready", "0E8AE6", "wrong")]
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert actions[0].kind == "update"


class TestDiffLabelsAlreadyCorrect:
    def test_matching_label_yields_unchanged(self) -> None:
        existing = [_existing("vk-ready", "0E8AE6", labels.VK_READY.description)]
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert actions[0].kind == "unchanged"


class TestDiffLabelsCaseInsensitiveColor:
    def test_color_matches_ignoring_case(self) -> None:
        existing = [_existing("vk-ready", "0e8ae6", labels.VK_READY.description)]
        actions = _diff_labels(existing=existing, registry=[labels.VK_READY])
        assert actions[0].kind == "unchanged"
```

- [x] **Step 2: Implement `_diff_labels` + `LabelAction`**

In `src/vk/commands/admin_cmd.py`:

```python
from dataclasses import dataclass

from vk import labels as _labels


@dataclass(frozen=True)
class LabelAction:
    kind: str          # "create" | "update" | "remove" | "unchanged"
    name: str
    old_color: str = ""
    new_color: str = ""
    old_desc: str = ""
    new_desc: str = ""


def _diff_labels(
    *,
    existing: list[dict],
    registry: list[_labels.LabelDef],
) -> list[LabelAction]:
    """Compute per-label actions to bring existing in line with the registry."""
    by_name = {e["name"]: e for e in existing}
    actions: list[LabelAction] = []
    for ld in registry:
        cur = by_name.get(ld.name)
        if cur is None:
            actions.append(LabelAction(
                kind="create", name=ld.name,
                new_color=ld.color, new_desc=ld.description,
            ))
            continue
        cur_color = cur.get("color", "").lower()
        cur_desc  = cur.get("description", "")
        if cur_color == ld.color.lower() and cur_desc == ld.description:
            actions.append(LabelAction(kind="unchanged", name=ld.name))
        else:
            actions.append(LabelAction(
                kind="update", name=ld.name,
                old_color=cur.get("color", ""), new_color=ld.color,
                old_desc=cur_desc, new_desc=ld.description,
            ))
    return actions
```

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_admin_diff.py -q --no-cov
```

Expected: 4 passed.

### Task 2: `_default_label_actions` — `--remove-defaults` with safety guard

**Files:**
- Modify: `src/vk/gh.py` — new `count_issues_with_label` helper
- Modify: `src/vk/commands/admin_cmd.py`
- Modify: `tests/unit/test_gh.py`
- Add: `tests/unit/test_admin_defaults.py`

- [x] **Step 1: TDD — `gh.count_issues_with_label`**

In `tests/unit/test_gh.py`:

```python
class TestCountIssuesWithLabel:
    def test_returns_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import json
        captured: list[list[str]] = []
        def fake(args: list[str]) -> str:
            captured.append(args)
            return json.dumps([{"id": 1}, {"id": 2}, {"id": 3}])
        monkeypatch.setattr(gh, "_run_gh", fake)
        n = gh.count_issues_with_label(repo="o/r", name="bug")
        assert n == 3
        assert captured[0] == [
            "issue", "list", "--repo", "o/r",
            "--label", "bug", "--state", "all",
            "--json", "id", "--limit", "1000",
        ]

    def test_empty_returns_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(gh, "_run_gh", lambda args: "[]")
        assert gh.count_issues_with_label(repo="o/r", name="bug") == 0
```

- [x] **Step 2: Implement `gh.count_issues_with_label`**

```python
def count_issues_with_label(*, repo: str, name: str) -> int:
    """Count Issues (any state) that carry this label. Cap at 1000."""
    import json
    out = _run_gh([
        "issue", "list", "--repo", repo,
        "--label", name, "--state", "all",
        "--json", "id", "--limit", "1000",
    ])
    return len(json.loads(out)) if out else 0
```

- [x] **Step 3: TDD — `_default_label_actions`**

`tests/unit/test_admin_defaults.py`:

```python
"""Tests for default-label removal logic."""

import pytest

from vk import gh
from vk.commands.admin_cmd import _default_label_actions, DEFAULT_LABELS


def _existing(name: str) -> dict:
    return {"name": name, "color": "ededed", "description": ""}


class TestDefaultLabelActions:
    def test_default_with_zero_issues_yields_remove(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        existing = [_existing("bug"), _existing("documentation")]
        monkeypatch.setattr(gh, "count_issues_with_label",
                            lambda *, repo, name: 0)
        actions = _default_label_actions(repo="o/r", existing=existing)
        kinds = {a.kind for a in actions}
        assert kinds == {"remove"}
        assert {a.name for a in actions} == {"bug", "documentation"}

    def test_default_with_issues_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        existing = [_existing("bug")]
        monkeypatch.setattr(gh, "count_issues_with_label",
                            lambda *, repo, name: 5)
        actions = _default_label_actions(repo="o/r", existing=existing)
        # Skipped — should not return a remove action for "bug" when used.
        assert all(a.kind != "remove" for a in actions)

    def test_non_default_label_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        existing = [_existing("custom-label")]
        monkeypatch.setattr(gh, "count_issues_with_label",
                            lambda *, repo, name: 0)
        actions = _default_label_actions(repo="o/r", existing=existing)
        assert actions == []
```

- [x] **Step 4: Implement `DEFAULT_LABELS` + `_default_label_actions`**

In `src/vk/commands/admin_cmd.py`:

```python
DEFAULT_LABELS = frozenset({
    "bug", "documentation", "duplicate", "enhancement",
    "good first issue", "help wanted", "invalid", "question", "wontfix",
})


def _default_label_actions(
    *,
    repo: str,
    existing: list[dict],
) -> list[LabelAction]:
    """Return remove actions for default labels with zero attached Issues.

    Defaults with attached Issues are silently skipped — that's user data.
    """
    actions: list[LabelAction] = []
    for lbl in existing:
        name = lbl.get("name", "")
        if name not in DEFAULT_LABELS:
            continue
        if gh.count_issues_with_label(repo=repo, name=name) == 0:
            actions.append(LabelAction(
                kind="remove", name=name,
                old_color=lbl.get("color", ""),
                old_desc=lbl.get("description", ""),
            ))
    return actions
```

- [x] **Step 5: Run tests**

```bash
uv run pytest tests/unit/test_admin_defaults.py tests/unit/test_gh.py::TestCountIssuesWithLabel -q --no-cov
```

Expected: 5 passed.

### Task 3: Dry-run rendering

**Files:**
- Modify: `src/vk/commands/admin_cmd.py`
- Add: `tests/unit/test_admin_dryrun.py`

- [x] **Step 1: TDD — dry-run table rows match action buckets**

`tests/unit/test_admin_dryrun.py`:

```python
"""Tests for dry-run rendering — verify the table contains expected rows."""

import pytest
from typer.testing import CliRunner

from vk import gh, labels
from vk.commands.admin_cmd import admin_app


runner = CliRunner()


def _patch_minimal_repo(monkeypatch: pytest.MonkeyPatch,
                       existing_labels: list[dict]) -> None:
    monkeypatch.setattr(gh, "list_repos", lambda *, owner: [{"name": "r"}])
    monkeypatch.setattr(gh, "list_labels",
                        lambda *, repo: existing_labels)
    monkeypatch.setattr(gh, "count_issues_with_label",
                        lambda *, repo, name: 0)


class TestDryRunRendersActions:
    def test_create_appears_when_label_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_minimal_repo(monkeypatch, existing_labels=[])
        result = runner.invoke(admin_app, [
            "labels-sync", "--owner", "o", "--repo", "r", "--dry-run",
        ])
        assert result.exit_code == 0
        # Expect each registry label to appear with action "create"
        for ld in (labels.VK_READY, labels.IN_PROGRESS, labels.PR_READY):
            assert ld.name in result.stdout
            assert "create" in result.stdout

    def test_unchanged_when_correct(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_minimal_repo(monkeypatch, existing_labels=[
            {"name": ld.name, "color": ld.color, "description": ld.description}
            for ld in labels.LIFECYCLE.values()
        ])
        result = runner.invoke(admin_app, [
            "labels-sync", "--owner", "o", "--repo", "r", "--dry-run",
        ])
        assert result.exit_code == 0
        assert "unchanged" in result.stdout.lower() or "= already correct" in result.stdout.lower()
```

- [x] **Step 2: Implement `_render_dryrun_table` + wire into `labels_sync`**

In `src/vk/commands/admin_cmd.py`:

```python
from rich.table import Table


def _render_dryrun_table(
    *,
    repo: str,
    actions: list[LabelAction],
) -> None:
    table = Table(title=f"{repo}", show_header=True, header_style="bold")
    table.add_column("Action")
    table.add_column("Label")
    table.add_column("Detail")
    for a in actions:
        if a.kind == "create":
            table.add_row("+ create",   a.name, f"color={a.new_color}")
        elif a.kind == "update":
            table.add_row("~ update",   a.name,
                          f"{a.old_color or '?'} → {a.new_color}")
        elif a.kind == "remove":
            table.add_row("- remove",   a.name, "(default, no Issues)")
        else:
            table.add_row("= unchanged", a.name, "")
    console.print(table)


@admin_app.command(name="labels-sync")
def labels_sync(
    owner: str = typer.Option(..., "--owner"),
    repo: str | None = typer.Option(None, "--repo"),
    remove_defaults: bool = typer.Option(False, "--remove-defaults"),
    dry_run: bool = typer.Option(True, "--dry-run/--apply"),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    """Sync repo labels to the canonical registry."""
    if yes:
        dry_run = False

    repos = _resolve_target_repos(owner=owner, repo=repo)
    if not repos:
        err_console.print(f"No repos found for owner '{owner}'.")
        raise typer.Exit(1)

    registry = list(_labels.LIFECYCLE.values())  # lifecycle labels only

    any_errors = False
    for slug in repos:
        try:
            existing = gh.list_labels(repo=slug)
        except gh.GhError as exc:
            err_console.print(f"{slug}: list-labels failed: {exc}")
            any_errors = True
            continue

        actions = _diff_labels(existing=existing, registry=registry)
        if remove_defaults:
            actions += _default_label_actions(repo=slug, existing=existing)

        _render_dryrun_table(repo=slug, actions=actions)

        if dry_run:
            continue
        # Apply mode lands in Phase 3 of this plan.
        raise NotImplementedError("apply mode lands in Phase 3 of this plan.")

    if any_errors:
        raise typer.Exit(1)
```

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_admin_dryrun.py -q --no-cov
```

Expected: 2 passed.

### Task 4: Format, type-check, full suite, commit

- [x] **Step 1: Format, type-check**

```bash
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/
```

Expected: clean.

- [x] **Step 2: Full suite**

```bash
uv run pytest -q --no-cov
```

Expected: green.

- [ ] **Step 3: Commit and PR**

```bash
git checkout -b labels-sync-phase-2-diff-and-dryrun
git add src/vk/gh.py src/vk/commands/admin_cmd.py tests/
git commit -m "feat(admin): labels-sync diff + dry-run rendering + defaults guard"
git push -u origin labels-sync-phase-2-diff-and-dryrun
gh pr create --title "Labels-sync Phase 2 · Diff logic + dry-run rendering" \
  --body "Computes per-repo action buckets and renders the dry-run table. Apply mode still stubbed; lands in Phase 3."
```

---

## Phase 3: Apply mode and version bump [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/65 -->
**Depends on:** Phase 2

**Context:** Wires `--apply` / `--yes` to actually run `gh.ensure_label` (for create/update) and `gh.delete_label` (for remove). Per-repo errors don't abort the run. Bumps the plugin version (minor — new user-visible subcommand).

### Task 1: Apply mode

**Files:**
- Modify: `src/vk/commands/admin_cmd.py`
- Add: `tests/unit/test_admin_apply.py`

- [ ] **Step 1: TDD — apply mode invokes correct gh calls**

`tests/unit/test_admin_apply.py`:

```python
"""Tests for apply mode — verifies gh calls dispatch correctly."""

import pytest
from typer.testing import CliRunner

from vk import gh, labels
from vk.commands.admin_cmd import admin_app


runner = CliRunner()


def _stub(monkeypatch: pytest.MonkeyPatch,
          existing_labels: list[dict],
          ensure_calls: list[dict],
          delete_calls: list[dict]) -> None:
    monkeypatch.setattr(gh, "list_repos", lambda *, owner: [{"name": "r"}])
    monkeypatch.setattr(gh, "list_labels",
                        lambda *, repo: existing_labels)
    monkeypatch.setattr(gh, "count_issues_with_label",
                        lambda *, repo, name: 0)

    def fake_ensure(*, repo, name, color="", description=""):
        ensure_calls.append({"repo": repo, "name": name,
                             "color": color, "description": description})
    monkeypatch.setattr(gh, "ensure_label", fake_ensure)

    def fake_delete(*, repo, name):
        delete_calls.append({"repo": repo, "name": name})
    monkeypatch.setattr(gh, "delete_label", fake_delete)


class TestApplyCreatesMissingLabels:
    def test_yes_flag_invokes_ensure_label_for_creates(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ensure_calls: list[dict] = []
        delete_calls: list[dict] = []
        _stub(monkeypatch, existing_labels=[],
              ensure_calls=ensure_calls, delete_calls=delete_calls)
        result = runner.invoke(admin_app, [
            "labels-sync", "--owner", "o", "--repo", "r", "--yes",
        ])
        assert result.exit_code == 0
        names_called = {c["name"] for c in ensure_calls}
        assert names_called == {"vk-ready", "manual",
                                "in-progress", "pr-ready"}


class TestApplyRemovesUnusedDefaults:
    def test_remove_defaults_invokes_delete_label(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ensure_calls: list[dict] = []
        delete_calls: list[dict] = []
        _stub(monkeypatch,
              existing_labels=[{"name": "bug", "color": "d73a4a",
                               "description": ""}],
              ensure_calls=ensure_calls, delete_calls=delete_calls)
        result = runner.invoke(admin_app, [
            "labels-sync", "--owner", "o", "--repo", "r",
            "--remove-defaults", "--yes",
        ])
        assert result.exit_code == 0
        assert {"repo": "o/r", "name": "bug"} in delete_calls


class TestApplyPerRepoErrorIsNonFatal:
    def test_one_repo_error_does_not_abort_others(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repos = [{"name": "good"}, {"name": "bad"}, {"name": "good2"}]
        monkeypatch.setattr(gh, "list_repos", lambda *, owner: repos)

        def fake_list_labels(*, repo: str) -> list[dict]:
            if repo.endswith("/bad"):
                raise gh.GhError("HTTP 403", stderr="HTTP 403", returncode=1)
            return []
        monkeypatch.setattr(gh, "list_labels", fake_list_labels)
        monkeypatch.setattr(gh, "count_issues_with_label",
                            lambda *, repo, name: 0)
        monkeypatch.setattr(gh, "ensure_label", lambda **kw: None)
        monkeypatch.setattr(gh, "delete_label", lambda **kw: None)

        result = runner.invoke(admin_app, [
            "labels-sync", "--owner", "o", "--yes",
        ])
        # Non-zero because one repo failed
        assert result.exit_code != 0
        # But o/good and o/good2 still got processed — verify by checking
        # that the error message mentions "bad" but not "good"
        assert "bad" in result.stdout
```

- [ ] **Step 2: Implement apply mode**

In `src/vk/commands/admin_cmd.py` `labels_sync`, replace the `raise NotImplementedError` block:

```python
        if dry_run:
            continue

        # Apply mode
        repo_summary = {"created": 0, "updated": 0, "removed": 0, "unchanged": 0}
        try:
            for a in actions:
                if a.kind == "create" or a.kind == "update":
                    ld = next(
                        (d for d in registry if d.name == a.name),
                        None,
                    )
                    if ld is None:
                        # Should not happen — diff only emits actions for
                        # registry labels.
                        continue
                    gh.ensure_label(repo=slug, name=ld.name,
                                    color=ld.color, description=ld.description)
                    repo_summary["created" if a.kind == "create" else "updated"] += 1
                elif a.kind == "remove":
                    gh.delete_label(repo=slug, name=a.name)
                    repo_summary["removed"] += 1
                else:
                    repo_summary["unchanged"] += 1
        except gh.GhError as exc:
            err_console.print(f"{slug}: apply failed: {exc}")
            any_errors = True
            continue

        console.print(
            f"{slug}: {repo_summary['created']} created, "
            f"{repo_summary['updated']} updated, "
            f"{repo_summary['removed']} removed, "
            f"{repo_summary['unchanged']} unchanged."
        )
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_admin_apply.py -q --no-cov
```

Expected: 3 passed.

### Task 2: Format, type-check, full suite

- [ ] **Step 1: Format, type-check**

```bash
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/
```

Expected: clean.

- [ ] **Step 2: Full suite**

```bash
uv run pytest -q --no-cov
```

Expected: green.

### Task 3: Version bump

**Files:**
- Modify: `pyproject.toml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `uv.lock` (regenerated)

**Context:** Minor bump per `CLAUDE.md`. New user-visible subcommand `vk admin labels-sync`.

- [ ] **Step 1: Confirm current version**

```bash
grep -E '"version"|^version' pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

Note the current. The exact bump depends on which of (label-lifecycle Phase 1, project-board excision Phase 2, this plan's Phase 3) merge first. Each plan declares its bump at merge time; resolve by checking what's already in `pyproject.toml`.

- [ ] **Step 2: Bump (minor)**

If current is `1.3.x` from label-lifecycle, this plan bumps to `1.4.0`. If current is still `1.2.x`, bumps to `1.3.0`. Update all three files consistently.

- [ ] **Step 3: Refresh lockfile**

```bash
uv sync
uv run vk --version
```

Expected: reports the new minor version.

- [ ] **Step 4: Final test run**

```bash
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest -q --no-cov
```

Expected: clean / green.

- [ ] **Step 5: Commit and PR**

```bash
git checkout -b labels-sync-phase-3-apply-and-bump
git add src/vk/commands/admin_cmd.py tests/unit/test_admin_apply.py \
        pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json uv.lock
git commit -m "feat(admin): labels-sync apply mode + version bump"
git push -u origin labels-sync-phase-3-apply-and-bump
gh pr create --title "Labels-sync Phase 3 · Apply mode + version bump" \
  --body "Final phase. Wires apply mode to ensure_label / delete_label, with per-repo error tolerance. Minor bump per CLAUDE.md release rule. Depends on Labels-sync Phase 2."
```
