# vk spec-index hygiene (Threads 1a + 1b + 2)

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-29-vk-cli-hygiene-and-issue-authoring-design.md`
**Status:** Complete

**Goal:** Fix three spec-index bugs that corrupt the Implementation Plans table in specs: de-duplicate rows by file path rather than plan title, preserve trailing prose when rewriting the table, stop re-quoting `—` placeholders in the File column, preserve operator-set `Repo` and `Depends on` cells on `vk progress sync`, and warn in `vk plan self-review` when phases declare mixed `**Target repo:**` values.

**Architecture:** Three focused patches to three files. Phase 1 fixes `src/vk/spec_index.py` (path-based upsert, prose preservation, backtick guard). Phase 2 fixes `src/vk/commands/progress_cmd.py` (`_reconcile_spec_index` column preservation + path-based lookup, same fix in `transition`). Phase 3 adds `target_repo` to `Phase` model and parser, then wires the check into `plan_self_review`.

**Tech Stack:** Python 3.11+, pytest, `uv run vk`.

---

## Phase 1: Fix `spec_index.py` — path-based upsert + prose preservation [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/82 -->
**Depends on:** —

**Context:** All four `vk progress sync` corruption symptoms trace back to `spec_index.upsert_entry()`. Fixing this file first makes Phase 2 trivial (it just needs to pass the right entry; the write path is already correct).

### Task 1: Tests for `spec_index.py` fixes

**Files:**
- Edit: `tests/unit/test_spec_index.py` (add new test cases, or create if absent)

- [x] **Step 1: TDD — write failing tests**

Create or append to `tests/unit/test_spec_index.py`:

```python
"""Tests for spec_index path-based upsert fixes."""

from __future__ import annotations

from pathlib import Path

from vk.spec_index import IndexEntry, _build_table, read_index, upsert_entry


SPEC_TABLE = """\
## Implementation Plans

| Plan | Repo | File | Status | Depends on |
|------|------|------|--------|------------|
| Plan A | `org/repo-a` | `docs/superpowers/plans/plan-a.md` | Not Started | — |
| Plan B | `org/repo-b` | `docs/superpowers/plans/plan-b.md` | Not Started | Phase X |
"""

SPEC_TABLE_WITH_PROSE = """\
## Implementation Plans

| Plan | Repo | File | Status | Depends on |
|------|------|------|--------|------------|
| Plan A | `org/repo-a` | `docs/superpowers/plans/plan-a.md` | Not Started | — |

Cross-phase dependency note: Plan A must complete before Plan B.
"""


class TestUpsertByFilePath:
    def test_same_path_different_title_updates_in_place(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text(SPEC_TABLE)
        entry = IndexEntry(
            plan="Plan A (revised title)",
            repo="`org/repo-a`",
            file="docs/superpowers/plans/plan-a.md",
            status="In Progress",
            depends_on="—",
        )
        upsert_entry(spec, entry)
        text = spec.read_text()
        assert "Plan A (revised title)" in text
        assert "In Progress" in text
        # No duplicate row — file path appears only once in data rows
        assert text.count("docs/superpowers/plans/plan-a.md") == 1

    def test_new_path_appends_row(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text(SPEC_TABLE)
        entry = IndexEntry(
            plan="Plan C",
            repo="`org/repo-c`",
            file="docs/superpowers/plans/plan-c.md",
            status="Not Started",
            depends_on="—",
        )
        upsert_entry(spec, entry)
        text = spec.read_text()
        assert "Plan C" in text
        assert "plan-c.md" in text
        assert "plan-a.md" in text  # existing rows untouched
        assert "plan-b.md" in text

    def test_prose_after_table_is_preserved(self, tmp_path: Path) -> None:
        spec = tmp_path / "spec.md"
        spec.write_text(SPEC_TABLE_WITH_PROSE)
        entry = IndexEntry(
            plan="Plan A",
            repo="`org/repo-a`",
            file="docs/superpowers/plans/plan-a.md",
            status="In Progress",
            depends_on="—",
        )
        upsert_entry(spec, entry)
        text = spec.read_text()
        assert "Cross-phase dependency note" in text
        assert "In Progress" in text


class TestBuildTable:
    def test_dash_file_not_backtick_quoted(self) -> None:
        entries = [
            IndexEntry(
                plan="Operator Row",
                repo="",
                file="—",
                status="Not Started",
                depends_on="Phase 3 deployed",
            ),
        ]
        table = _build_table(entries)
        assert "| — |" in table
        assert "| `—` |" not in table

    def test_path_file_is_backtick_quoted(self) -> None:
        entries = [
            IndexEntry(
                plan="Plan A",
                repo="",
                file="docs/plans/plan-a.md",
                status="Not Started",
                depends_on="—",
            ),
        ]
        table = _build_table(entries)
        assert "`docs/plans/plan-a.md`" in table

    def test_empty_file_rendered_as_dash(self) -> None:
        entries = [
            IndexEntry(plan="Plan A", repo="", file="", status="Not Started", depends_on="—"),
        ]
        table = _build_table(entries)
        assert "| — |" in table
```

- [x] **Step 2: Run tests to confirm they fail before the fix**

```bash
uv run pytest tests/unit/test_spec_index.py -x -q --no-cov 2>&1 | head -30
```

Expected: `TestUpsertByFilePath` and `TestBuildTable` tests fail.

### Task 2: Fix `spec_index.py`

**Files:**
- Edit: `src/vk/spec_index.py`

- [x] **Step 3: Fix `upsert_entry()` — match by file path**

In `upsert_entry()`, change the matching predicate (currently `e.plan == entry.plan`):

```python
# Before (around line 92)
for i, e in enumerate(existing):
    if e.plan == entry.plan:
        existing[i] = entry
        found = True
        break

# After
for i, e in enumerate(existing):
    if e.file == entry.file:
        existing[i] = entry
        found = True
        break
```

- [x] **Step 4: Fix `upsert_entry()` — replace only the table block, preserve trailing prose**

Replace the section-replacement block at the end of `upsert_entry()`:

```python
# Before
table = _build_table(existing)
new_text = text[:section_start] + f"\n{table}\n" + text[section_end:]
spec_path.write_text(new_text, encoding="utf-8")
```

With the surgical table-only replacement:

```python
table = _build_table(existing)
section_text = text[section_start:section_end]
lines = section_text.splitlines(keepends=True)

table_first = next(
    (i for i, ln in enumerate(lines) if ln.strip().startswith("|")), None
)
table_last = max(
    (i for i, ln in enumerate(lines) if ln.strip().startswith("|")), default=None
)

if table_first is None:
    # No existing table — append before section end
    pre = text[:section_end].rstrip("\n")
    new_text = pre + f"\n\n{table}\n" + text[section_end:]
else:
    kept_before = "".join(lines[:table_first])
    kept_after = "".join(lines[table_last + 1 :])
    new_section = kept_before + table + "\n" + kept_after
    new_text = text[:section_start] + new_section + text[section_end:]

spec_path.write_text(new_text, encoding="utf-8")
```

- [x] **Step 5: Fix `_build_table()` — guard backticks on non-path File values**

```python
# Before
lines.append(f"| {e.plan} | {e.repo} | `{e.file}` | {e.status} | {e.depends_on} |")

# After
file_cell = f"`{e.file}`" if e.file and e.file not in ("—", "-", "") else (e.file or "—")
lines.append(f"| {e.plan} | {e.repo} | {file_cell} | {e.status} | {e.depends_on} |")
```

- [x] **Step 6: Run all new tests — must pass**

```bash
uv run pytest tests/unit/test_spec_index.py -x -q --no-cov
```

Expected: all pass.

- [x] **Step 7: Run full test suite — no regressions**

```bash
uv run ruff format src/ tests/
uv run pytest -q --no-cov
```

Expected: all pass.

---

## Phase 2: Fix `progress_cmd.py` — column preservation + path-based lookup [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/83 -->
**Depends on:** Phase 1

**Context:** With `upsert_entry()` fixed to match by path, the callers in `progress_cmd.py` only need to provide the correct `repo` and `depends_on` values (copied from the existing row rather than hardcoded blanks). Also extend `_reconcile_spec_index` to accept an optional `prev_plan_path` for the archive-rename case.

### Task 1: Tests for `_reconcile_spec_index` column preservation

**Files:**
- Create or edit: `tests/unit/test_progress_reconcile.py`

- [x] **Step 1: TDD — write failing tests**

```python
"""Tests for _reconcile_spec_index column preservation (Thread 2 fix)."""

from __future__ import annotations

from pathlib import Path

from vk.commands.progress_cmd import _reconcile_spec_index
from vk.spec_index import read_index


SPEC_WITH_RICH_ROW = """\
# My Spec

## Implementation Plans

| Plan | Repo | File | Status | Depends on |
|------|------|------|--------|------------|
| Plan A | `org/repo` | `docs/superpowers/plans/plan-a.md` | Not Started | Phase X of repo-b |

Cross-phase note: important prose.
"""

PLAN_CONTENT = """\
# Plan A

**Spec:** `docs/superpowers/specs/my-spec.md`
**Status:** Not Started

**Goal:** Test.

---

## Phase 1: Work [agentic]
**Depends on:** —

### Task 1: Do thing

- [x] **Step 1: Done**
"""


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    plans_dir = tmp_path / "docs" / "superpowers" / "plans"
    plans_dir.mkdir(parents=True)
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    spec_path = specs_dir / "my-spec.md"
    spec_path.write_text(SPEC_WITH_RICH_ROW)
    plan_path = plans_dir / "plan-a.md"
    plan_path.write_text(PLAN_CONTENT)
    return tmp_path, spec_path, plan_path


def test_reconcile_preserves_repo_and_depends_on(tmp_path: Path) -> None:
    repo_root, spec_path, plan_path = _setup(tmp_path)
    updated = _reconcile_spec_index(
        plan_path=plan_path,
        plan_title="Plan A",
        status="In Progress",
        repo_root=repo_root,
    )
    assert updated is True
    entries = read_index(spec_path)
    matching = [e for e in entries if "plan-a.md" in e.file]
    assert len(matching) == 1
    row = matching[0]
    assert row.status == "In Progress"
    assert row.repo == "`org/repo`"
    assert row.depends_on == "Phase X of repo-b"
    # Prose preserved
    assert "Cross-phase note" in spec_path.read_text()


def test_reconcile_noop_when_status_and_title_match(tmp_path: Path) -> None:
    repo_root, spec_path, plan_path = _setup(tmp_path)
    updated = _reconcile_spec_index(
        plan_path=plan_path,
        plan_title="Plan A",
        status="Not Started",
        repo_root=repo_root,
    )
    assert updated is False


def test_reconcile_updates_title_when_changed(tmp_path: Path) -> None:
    repo_root, spec_path, plan_path = _setup(tmp_path)
    updated = _reconcile_spec_index(
        plan_path=plan_path,
        plan_title="Plan A (revised)",
        status="Not Started",
        repo_root=repo_root,
    )
    assert updated is True
    text = spec_path.read_text()
    assert "Plan A (revised)" in text
    assert text.count("plan-a.md") == 1  # no duplicate
```

- [x] **Step 2: Run tests to confirm they fail before the fix**

```bash
uv run pytest tests/unit/test_progress_reconcile.py -x -q --no-cov 2>&1 | head -30
```

### Task 2: Fix `progress_cmd.py`

**Files:**
- Edit: `src/vk/commands/progress_cmd.py`

- [x] **Step 3: Update `_reconcile_spec_index()` signature**

Change function signature to add optional `prev_plan_path`:

```python
def _reconcile_spec_index(
    plan_path: Path,
    plan_title: str,
    status: str,
    repo_root: Path,
    *,
    dry_run: bool = False,
    prev_plan_path: Path | None = None,
) -> bool:
```

- [x] **Step 4: Rewrite lookup and entry-building in `_reconcile_spec_index()`**

Replace the existing body from `entries = read_index(...)` through `upsert_entry(...)`:

```python
entries = read_index(spec_path)
rel_file = str(plan_path.relative_to(repo_root))
lookup_path = str((prev_plan_path or plan_path).relative_to(repo_root))

existing_entry = next((e for e in entries if e.file == lookup_path), None)
if (existing_entry
        and existing_entry.status == status
        and existing_entry.plan == plan_title):
    return False

if dry_run:
    console.print(f"Would update spec index for: {spec_path.name}")
    return True

entry = IndexEntry(
    plan=plan_title,
    repo=existing_entry.repo if existing_entry else "",
    file=rel_file,
    status=status,
    depends_on=existing_entry.depends_on if existing_entry else "—",
)
upsert_entry(spec_path, entry)
console.print(f"Spec index updated: {spec_path}")
return True
```

- [x] **Step 5: Update archive-rename call site in `sync()`**

Find the second `_reconcile_spec_index` call after archiving (`sync()` line ~235) and add `prev_plan_path`:

```python
# Before
if archived_path:
    _reconcile_spec_index(archived_path, plan.title, new_status, repo_root)

# After
if archived_path:
    _reconcile_spec_index(
        archived_path, plan.title, new_status, repo_root,
        prev_plan_path=plan_path,
    )
```

- [x] **Step 6: Fix `transition` command — read existing entry before building IndexEntry**

In the `transition` command's local-mode branch, before calling `upsert_entry`, read
the existing row to preserve `repo` and `depends_on`:

```python
spec_path = _resolve_spec(plan_path)
if spec_path:
    rel_file = str(plan_path.relative_to(repo_root))
    existing_entries = read_index(spec_path)
    existing_entry = next((e for e in existing_entries if e.file == rel_file), None)
    entry = IndexEntry(
        plan=plan.title,
        repo=existing_entry.repo if existing_entry else "",
        file=rel_file,
        status=new_state,
        depends_on=existing_entry.depends_on if existing_entry else "—",
    )
    upsert_entry(spec_path, entry)
```

Remove the existing `spec_path = _resolve_spec(...)` + `entry = IndexEntry(...)` + `upsert_entry(...)` block and replace it with the above.

- [x] **Step 7: Run all tests — no regressions**

```bash
uv run ruff format src/ tests/
uv run pytest -q --no-cov
```

Expected: all pass.

---

## Phase 3: Add `target_repo` to Phase model + parser + self-review check [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/84 -->
**Depends on:** —

**Context:** Independent of Phases 1 and 2 — no shared files. The `Phase` dataclass gains a nullable field; the parser learns to extract `**Target repo:**` per phase header; `plan_self_review` adds one check that warns when dispatch is configured and phases have mixed repos.

### Task 1: Tests for multi-repo warning

**Files:**
- Create: `tests/unit/test_self_review_multi_repo.py`

- [x] **Step 1: TDD — write failing tests**

```python
"""Tests for vk plan self-review multi-repo warning (Thread 1a)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

runner = CliRunner()

_DISPATCH_CONFIG = """\
plan:
  save_to: docs/superpowers/plans/
dispatch:
  target: github-issues
  owner: derio-net
  default_repo: derio-net/frank
  labels:
    agentic: vk-ready
    manual: manual
"""

_NO_DISPATCH_CONFIG = """\
plan:
  save_to: docs/superpowers/plans/
"""

PLAN_MIXED_REPOS = """\
# Test Plan

**Spec:** `docs/superpowers/specs/some-spec.md`
**Status:** Not Started

**Goal:** Test.

---

## Phase 1: Phase A [agentic]
**Target repo:** derio-net/frank
**Depends on:** —

### Task 1: Something

- [ ] **Step 1: Do A**

## Phase 2: Phase B [agentic]
**Target repo:** derio-net/agent-images
**Depends on:** Phase 1

### Task 1: Something

- [ ] **Step 1: Do B**
"""

PLAN_SAME_REPO = """\
# Test Plan

**Spec:** `docs/superpowers/specs/some-spec.md`
**Status:** Not Started

**Goal:** Test.

---

## Phase 1: Phase A [agentic]
**Target repo:** derio-net/frank
**Depends on:** —

### Task 1: Something

- [ ] **Step 1: Do A**

## Phase 2: Phase B [agentic]
**Target repo:** derio-net/frank
**Depends on:** Phase 1

### Task 1: Something

- [ ] **Step 1: Do B**
"""

PLAN_NO_TARGET = """\
# Test Plan

**Spec:** `docs/superpowers/specs/some-spec.md`
**Status:** Not Started

**Goal:** Test.

---

## Phase 1: Phase A [agentic]
**Depends on:** —

### Task 1: Something

- [ ] **Step 1: Do A**
"""


def _write_config(tmp_path: Path, content: str) -> None:
    config_dir = tmp_path / "docs" / "superpowers"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "plan-config.yaml").write_text(content)


def _write_plan(tmp_path: Path, content: str) -> Path:
    plan_dir = tmp_path / "docs" / "superpowers" / "plans"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_path = plan_dir / "test-plan.md"
    plan_path.write_text(content)
    return plan_path


def test_mixed_target_repos_warns_with_dispatch(tmp_path: Path) -> None:
    _write_config(tmp_path, _DISPATCH_CONFIG)
    plan_path = _write_plan(tmp_path, PLAN_MIXED_REPOS)
    result = runner.invoke(app, ["plan", "self-review", str(plan_path)])
    assert result.exit_code == 1
    combined = (result.output or "") + (result.stdout or "")
    assert "Multi-repo plan" in combined


def test_same_target_repo_no_warning(tmp_path: Path) -> None:
    _write_config(tmp_path, _DISPATCH_CONFIG)
    plan_path = _write_plan(tmp_path, PLAN_SAME_REPO)
    result = runner.invoke(app, ["plan", "self-review", str(plan_path)])
    assert "Multi-repo" not in (result.output or "")


def test_no_target_repo_no_warning(tmp_path: Path) -> None:
    _write_config(tmp_path, _DISPATCH_CONFIG)
    plan_path = _write_plan(tmp_path, PLAN_NO_TARGET)
    result = runner.invoke(app, ["plan", "self-review", str(plan_path)])
    assert "Multi-repo" not in (result.output or "")


def test_mixed_target_no_dispatch_no_warning(tmp_path: Path) -> None:
    _write_config(tmp_path, _NO_DISPATCH_CONFIG)
    plan_path = _write_plan(tmp_path, PLAN_MIXED_REPOS)
    result = runner.invoke(app, ["plan", "self-review", str(plan_path)])
    assert "Multi-repo" not in (result.output or "")
```

- [x] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_self_review_multi_repo.py -x -q --no-cov 2>&1 | head -30
```

### Task 2: Add `target_repo` to Phase model

**Files:**
- Edit: `src/vk/plan/models.py`

- [x] **Step 3: Add `target_repo: str | None = None` to `Phase`**

```python
@dataclass(frozen=True)
class Phase:
    number: int
    title: str
    tag: Literal["manual", "agentic"]
    depends_on: tuple[int, ...]
    tasks: tuple[Task, ...]
    tracking_url: str | None
    track_label: str | None = None
    target_repo: str | None = None    # ← add this line
```

### Task 3: Update parser to extract `**Target repo:**`

**Files:**
- Edit: `src/vk/plan/parser.py`

- [x] **Step 4: Add regex and extraction**

Near the top of `parser.py`, add alongside the other field regexes:

```python
_RE_TARGET_REPO = re.compile(r"^\*\*Target repo:\*\*\s*(.+)$", re.MULTILINE)
```

In the phase-header parsing block (where `track_label` and `tracking_url` are
extracted), add the target_repo extraction and pass it when constructing `Phase`:

```python
target_repo_m = _RE_TARGET_REPO.search(phase_header_text)
target_repo = target_repo_m.group(1).strip() if target_repo_m else None
# ... then in Phase(...):
target_repo=target_repo,
```

The parser already extracts a "phase_header_text" block between the `## Phase N:` line
and the first `### Task` line. Use that same block for the regex search.

### Task 4: Add multi-repo check to `plan_self_review()`

**Files:**
- Edit: `src/vk/commands/plan_cmd.py`

- [x] **Step 5: Add check after Track-label lint in `plan_self_review()`**

After the `for phase in plan.phases: if phase.track_label is None: ...` block, add:

```python
# Multi-target repo check (Thread 1a)
target_repos = {p.target_repo for p in plan.phases if p.target_repo}
if len(target_repos) > 1:
    repo_root = resolve_repo_root(cwd=plan_path.parent)
    config_path = repo_root / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)
    if profile.dispatch_enabled:
        issues.append(
            f"Multi-repo plan: phases declare different **Target repo:** values "
            f"({', '.join(sorted(target_repos))}). "
            "vk dispatch --repo is plan-wide; per-phase repo overrides are not "
            "supported. Write one plan per target repo."
        )
```

Verify that `load_profile` is already imported in `plan_cmd.py` (it is used in
`plan_spec_index` via `resolve_repo_root`); add the import if needed.

- [x] **Step 6: Run all tests**

```bash
uv run ruff format src/ tests/
uv run pytest -q --no-cov
```

Expected: all pass.

- [x] **Step 7: Run `vk plan self-review` on this plan to confirm it passes**

```bash
cd /var/tmp/vibe-kanban/worktrees/2547-ffe-80-gh-80/superpowers-for-vk
uv run vk plan self-review docs/superpowers/plans/2026-04-29-vk-spec-index-hygiene.md
```

Expected: `Self-review passed.`
