# Label Lifecycle Fix Phase 2 Implementation Plan: Project-Board Excision

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** `docs/superpowers/specs/2026-04-27-label-lifecycle-fix-design.md`
**Status:** Not Started

**Goal:** Excise the vestigial `project_board` config field, six dead `gh.py` project helpers (~150 LOC), the reserved-but-unused `vk dispatch --project` flag, the never-implemented `vk progress transition` dispatch branch, the body-text-only `vk progress create --lifecycle` flag, and the entire `_run_dispatch_audit` block — none of which `superpowers-for-vk` actually uses anymore. After this plan ships, `vk progress audit` runs purely local checks (status drift, spec-index drift, stale plans) regardless of dispatch mode, and the dispatch-config surface drops one field plus several reserved-future code paths that were never built.

**Architecture:** Two-phase subtractive change. Phase 1 deletes the dead helpers and the config field plus the dispatch flag and scaffold/fixture references — touches `gh.py`, `config.py`, `dispatch_cmd.py`, `init_cmd.py`, `common.py`, two fixtures, and unit tests. Phase 2 deletes the dispatch-mode features in `vk progress` (`audit`, `create --lifecycle`, `transition` dispatch branch) and lands the version bump. Independent of label-lifecycle Phase 1: both phases touch some shared files (`config.py`, `dispatch_cmd.py`, `gh.py`) but at different lines; whichever PR merges second rebases cleanly.

**Tech Stack:** Python 3.11+, Typer, `gh` CLI, pytest.

**PR strategy:** Each internal phase ships as its own PR. Phase 2's version bump is the cap.

---

## Phase 1: Drop dead gh helpers, config field, dispatch flag, scaffold refs [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/61 -->
**Depends on:** —

**Context:** The bulk of the deletions. After this phase, `dispatch.project_board` no longer exists in `DispatchConfig`, six gh project helpers are gone, the `--project` CLI flag is gone, and `vk init`'s YAML scaffold no longer mentions a project board.

### Task 1: Delete dead helpers from `src/vk/gh.py`

**Files:**
- Modify: `src/vk/gh.py`
- Modify: `tests/unit/test_gh.py`

**Context:** Six functions delete cleanly — none have non-test callers. The unit test for `add_to_project` goes with it. `get_project_number`, `list_project_items`, and `BoardItem` are alive only via `_run_dispatch_audit` (deleted in Phase 2 of this plan); they move out together with their last consumer to avoid a transient broken state.

- [x] **Step 1: Identify deletion targets via grep**

```bash
grep -n "^def add_to_project\|^def set_field\|^def get_project_id\|^def get_item_id\|^def get_field_id\|^def get_option_id" src/vk/gh.py
```

Expected: six matches at the lines noted in the spec's excision table (149, 171, 233, 252, 276, 299).

- [x] **Step 2: Delete the six functions**

In `src/vk/gh.py`, remove these function definitions (and any contiguous comment block above each):

- `add_to_project` (around lines 149-168)
- `set_field` (around lines 171-196)
- `get_project_id` (around lines 233-249)
- `get_item_id` (around lines 252-273)
- `get_field_id` (around lines 276-297)
- `get_option_id` (around lines 299-336)

Leave intact:
- `get_project_number` (211-230)
- `list_project_items` (338-372)
- `BoardItem` dataclass

These three are deleted in Phase 2 of this plan together with their final consumer.

- [x] **Step 3: Delete `add_to_project` test from `tests/unit/test_gh.py`**

```bash
grep -n "add_to_project" tests/unit/test_gh.py
```

Remove the import on line 14 and the test body around line 100.

- [x] **Step 4: Run unit tests**

```bash
uv run pytest tests/unit/test_gh.py -q --no-cov
```

Expected: green (one fewer test class).

### Task 2: Drop `project_board` from `DispatchConfig` and `_parse_dispatch`

**Files:**
- Modify: `src/vk/config.py`
- Modify: `tests/unit/test_config.py`

- [x] **Step 1: TDD — assert field absence**

In `tests/unit/test_config.py`, add:

```python
class TestDispatchConfigNoProjectBoard:
    def test_dataclass_has_no_project_board_field(self) -> None:
        from dataclasses import fields
        from vk.config import DispatchConfig
        names = {f.name for f in fields(DispatchConfig)}
        assert "project_board" not in names

    def test_yaml_with_project_board_key_does_not_break(self) -> None:
        # Backward-compat: existing plan-config.yaml files in the wild still
        # have the key. Parser must ignore it, not error.
        raw = {"target": "github-issues", "owner": "o",
               "project_board": "Some Board",
               "default_repo": "o/r"}
        cfg = _parse_dispatch(raw)
        assert cfg is not None
        # No assertion on project_board itself — it's gone.
```

Update existing tests that reference `cfg.project_board` (lines 64, 75) — drop those assertions.

- [x] **Step 2: Drop the field**

In `src/vk/config.py`:

- Remove `project_board: str = "Derio Ops"` from the `DispatchConfig` dataclass (line 42).
- Remove `project_board=raw.get("project_board", "Derio Ops"),` from `_parse_dispatch` (line 89).

`_parse_dispatch` continues to accept YAML containing the `project_board:` key — `dict.get` on the `raw` map silently ignores unknown keys at the dataclass-construction step. No backward-compat issue for repos that still have it in their `plan-config.yaml`.

- [x] **Step 3: Run tests**

```bash
uv run pytest tests/unit/test_config.py -q --no-cov
```

Expected: green.

### Task 3: Drop `--project` flag from `vk dispatch`

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`
- Modify: `tests/integration/test_dispatch.py` (if it asserts the flag)

- [x] **Step 1: Locate references**

```bash
grep -n "project" src/vk/commands/dispatch_cmd.py
```

Expected: lines 192-194 (option declaration) and line 220 (the discarded read).

- [x] **Step 2: Remove the flag and the discard**

In `src/vk/commands/dispatch_cmd.py`:

- Remove the `project: str | None = typer.Option(...)` parameter (lines 192-194).
- Remove the `_ = project or dispatch_cfg.project_board  # reserved for project board operations` line (220).

- [x] **Step 3: Confirm tests still pass**

```bash
uv run pytest tests/integration/test_dispatch.py -q --no-cov
grep -n "\-\-project\b\|project=\b" tests/integration/test_dispatch.py
```

Expected: green; second grep should produce no matches. If any test invokes the `--project` flag, drop those invocations.

### Task 4: Update scaffold (`init_cmd.py`, `common.py`)

**Files:**
- Modify: `src/vk/commands/init_cmd.py`
- Modify: `src/vk/commands/common.py`
- Modify: `tests/unit/test_common.py`

- [x] **Step 1: Update `init_cmd.py` YAML scaffold**

In `src/vk/commands/init_cmd.py` around lines 59-64, remove the `project_name = project or "Derio Ops"` resolution (line 59) and the `"project_board": project_name,` entry from the scaffold dict (line 64). If `init`'s function signature has a `--project` parameter, drop that too.

- [x] **Step 2: Update `common.py` scaffold docstring**

In `src/vk/commands/common.py` around line 113, remove the `project_board: "<Project Name>"` line from the scaffold-template docstring.

- [x] **Step 3: Update `test_common.py`**

In `tests/unit/test_common.py` around line 55, drop the `assert "project_board:" in result` assertion. If a test asserts `assert "project_board:" not in result`, add that instead.

- [x] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_common.py -q --no-cov
```

Expected: green.

### Task 5: Update fixtures

**Files:**
- Modify: `tests/integration/conftest.py`
- Modify: `tests/fixtures/configs/dispatch-enabled.yaml`

- [x] **Step 1: Drop `project_board` from `conftest.py:62`**

```bash
grep -n "project_board" tests/integration/conftest.py
```

Remove the line that sets `project_board: "Derio Ops"` in the fixture YAML string.

- [x] **Step 2: Drop `project_board` from the fixture YAML**

```bash
grep -n "project_board" tests/fixtures/configs/dispatch-enabled.yaml
```

Remove line 17 (`project_board: "Derio Ops"`).

- [x] **Step 3: Run integration tests**

```bash
uv run pytest tests/integration/ -q --no-cov
```

Expected: green.

### Task 6: Format, type-check, full suite, commit

- [x] **Step 1: Format and type-check**

```bash
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/
```

Expected: clean.

- [x] **Step 2: Full unit + integration suite**

```bash
uv run pytest -q --no-cov
```

Expected: green.

- [x] **Step 3: Commit and PR**

```bash
git checkout -b excision-phase-1-config-and-helpers
git add src/vk/gh.py src/vk/config.py src/vk/commands/dispatch_cmd.py \
        src/vk/commands/init_cmd.py src/vk/commands/common.py \
        tests/unit/test_gh.py tests/unit/test_config.py \
        tests/unit/test_common.py tests/integration/conftest.py \
        tests/fixtures/configs/dispatch-enabled.yaml \
        tests/integration/test_dispatch.py
git commit -m "refactor: excise project_board config, dead gh helpers, --project flag"
git push -u origin excision-phase-1-config-and-helpers
gh pr create --title "Excision Phase 1 · Drop project_board config + dead gh helpers + --project flag" \
  --body "Phase 1 of project-board excision per the label-lifecycle-fix spec. No behavior change for any code path actually used by anyone."
```

---

## Phase 2: Drop dispatch-mode progress features and version bump [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/62 -->
**Depends on:** Phase 1

**Context:** Removes `_run_dispatch_audit` and its three remaining `gh.py` callees (`get_project_number`, `list_project_items`, `BoardItem`), drops `vk progress create --lifecycle`, and replaces `vk progress transition`'s dispatch branch with a clean refusal. Bumps the plugin version (patch — removing reserved/dead surface, no functional change for working code paths).

### Task 1: Delete `_run_dispatch_audit` and its callees

**Files:**
- Modify: `src/vk/commands/progress_cmd.py`
- Modify: `src/vk/gh.py`
- Modify: `tests/unit/test_audit.py`

- [x] **Step 1: Delete the audit's dispatch-mode block**

In `src/vk/commands/progress_cmd.py`:

- Delete `_run_dispatch_audit` (lines 380-444 approximately — verify with `grep -n "_run_dispatch_audit\|^def " src/vk/commands/progress_cmd.py`).
- Delete the `if profile.dispatch_enabled: dispatch_issues = _run_dispatch_audit(...)` block in `audit` (around line 530-533).
- Simplify the `mode` variable: `audit` no longer has dispatch-vs-local divergence, so `mode = "local"` everywhere or just drop the variable.

- [x] **Step 2: Delete `get_project_number`, `list_project_items`, `BoardItem`**

In `src/vk/gh.py`:

- Delete `BoardItem` dataclass (search for `class BoardItem` or `@dataclass` near `list_project_items`).
- Delete `get_project_number` (211-230).
- Delete `list_project_items` (338-372).

- [x] **Step 3: Delete board-mocking tests in `test_audit.py`**

```bash
grep -n "TestDispatchAudit\|get_project_number\|list_project_items\|class.*Audit" tests/unit/test_audit.py | head
```

Delete every test class that depends on `gh.get_project_number` or `gh.list_project_items` mocks. Keep the local-audit tests (status drift, spec-index drift, stale plans). Roughly 8+ test cases get removed; the local-audit ones remain.

- [x] **Step 4: Run tests**

```bash
uv run pytest tests/unit/test_audit.py tests/unit/test_gh.py -q --no-cov
```

Expected: green, with significantly fewer audit tests.

### Task 2: Drop `vk progress create --lifecycle`

**Files:**
- Modify: `src/vk/commands/progress_cmd.py`
- Modify: `tests/` if any test invokes `--lifecycle`

- [x] **Step 1: Drop the flag and its body emission**

In `src/vk/commands/progress_cmd.py` `create` (line 281-312):

- Remove the `lifecycle: str = typer.Option("idea", "--lifecycle", ...)` parameter (line 285).
- Update `body=f"Type: {type_label}\nLifecycle: {lifecycle}"` → `body=f"Type: {type_label}"` (line 306).

- [x] **Step 2: Confirm no tests invoke `--lifecycle`**

```bash
grep -rn "\-\-lifecycle\|lifecycle=" tests/ 2>/dev/null
```

Drop any invocations / assertions about lifecycle text in the body.

- [x] **Step 3: Run tests**

```bash
uv run pytest -q --no-cov -k "progress and create"
```

Expected: green.

### Task 3: Drop `vk progress transition` dispatch branch

**Files:**
- Modify: `src/vk/commands/progress_cmd.py`

**Context:** The dispatch branch returns "not yet implemented" (line 358-360) — never worked. After excision, transition is local-only.

- [x] **Step 1: Replace dispatch branch with explicit gate**

In `src/vk/commands/progress_cmd.py` `transition` (line 315-360), drop the `if not profile.dispatch_enabled:` gate and its `else: console.print("Dispatch-mode transition: not yet implemented"); raise typer.Exit(1)` branch. The function operates on plan files regardless of dispatch mode. Update the docstring: `target` is always a plan path, never an Issue URL.

The simplified shape:

```python
def transition(
    target: str = typer.Argument(..., help="Plan file path."),
    new_state: str = typer.Argument(..., help="New Status value."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
) -> None:
    """Transition a plan's Status header (and spec-index entry)."""
    repo_root = _find_repo_root(Path.cwd())
    config_path = repo_root / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)

    plan_path = Path(target).resolve()
    if not plan_path.exists():
        err_console.print(f"Plan not found: {plan_path}")
        raise typer.Exit(2)

    plan = parse_plan(plan_path)
    allowed = profile.header.status_values
    if new_state not in allowed:
        err_console.print(f"Invalid status '{new_state}'. Allowed: {', '.join(allowed)}")
        raise typer.Exit(2)

    if not yes:
        if not typer.confirm(
            f"Transition {plan.title}: {plan.status} -> {new_state}?", default=False
        ):
            raise typer.Exit(0)

    _rewrite_status(plan_path, new_state)
    console.print(f"Status: {plan.status} -> {new_state}")

    spec_path = _resolve_spec(plan_path)
    if spec_path:
        entry = IndexEntry(
            plan=plan.title,
            repo="",
            file=str(plan_path.relative_to(repo_root)),
            status=new_state,
            depends_on="—",
        )
        upsert_entry(spec_path, entry)
```

- [x] **Step 2: Update tests if needed**

```bash
grep -rn "transition.*dispatch\|dispatch.*transition\|not yet implemented" tests/ 2>/dev/null | head
```

If any test asserts the "not yet implemented" exit, delete it.

### Task 4: Format, type-check, full suite

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

### Task 5: Version bump

**Files:**
- Modify: `pyproject.toml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `uv.lock` (regenerated)

**Context:** Patch bump per `CLAUDE.md`. Removing reserved/dead user surface — no functional behavior change for any code path that worked before.

- [x] **Step 1: Confirm current version**

```bash
grep -E '"version"|^version' pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

Note the current version. If the label-lifecycle-fix-phase-1 PR has already merged with its `1.3.0` bump, current is `1.3.0` and this excision bumps to `1.3.1`. If excision lands first, current is `1.2.0` and this bumps to `1.2.1`. Resolve at merge time.

- [x] **Step 2: Bump all three files (patch)**

Update the three version strings to current+patch. Keep the bump consistent across all three files.

- [x] **Step 3: Refresh lockfile**

```bash
uv sync
uv run vk --version
```

Expected: `vk --version` reports the new patch version.

- [x] **Step 4: Final test run**

```bash
uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/ && uv run pytest -q --no-cov
```

Expected: clean / green.

- [ ] **Step 5: Commit and PR**

```bash
git checkout -b excision-phase-2-progress-and-bump
git add src/vk/commands/progress_cmd.py src/vk/gh.py tests/unit/test_audit.py \
        pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json uv.lock
git commit -m "refactor: drop _run_dispatch_audit, --lifecycle, transition dispatch branch + bump"
git push -u origin excision-phase-2-progress-and-bump
gh pr create --title "Excision Phase 2 · Drop progress dispatch-mode features + version bump" \
  --body "Final phase of project-board excision. Removes _run_dispatch_audit, vk progress create --lifecycle, and the never-implemented vk progress transition dispatch branch. Patch bump per CLAUDE.md release rule. Depends on Excision Phase 1."
```
