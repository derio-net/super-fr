# Dispatch Ensure Labels Implementation Plan

> **For VK agents:** Use vk-execute to implement assigned phases.
> **For local execution:** Use subagent-driven-development or executing-plans.
> **For dispatch:** Use vk-dispatch to create Issues from this plan.

**Spec:** none (retroactive — no spec written)
**Status:** Complete

**Goal:** Fix the silent-partial-dispatch failure mode in `vk dispatch create` and `vk dispatch migrate` where `gh issue create --label X` / `gh issue edit --add-label X` fails hard if label `X` doesn't already exist on the target repo — observed on `content-factory` and `kid-laptops` where only ad-hoc labels appear.
**Architecture:** Add idempotent `ensure_label` / `ensure_labels` helpers to `src/vk/gh.py` (wrapping `gh label create --force`), and call them once from each dispatch subcommand before any Issue-mutating `gh` call. Fail-loud: first label-bootstrap failure exits with code 4 before any Issue is created or edited.
**Tech Stack:** Python 3.11+, Typer, `gh` CLI.

---

## Phase 1: `ensure_label` / `ensure_labels` in `vk.gh` [agentic]
**Depends on:** —

**Context:** `gh.py` has `create_issue(... labels=[...])` that passes labels via `--label`. `gh` refuses unknown labels (no auto-create). The existing `edit_issue(... add_labels=[...])` in migrate has the same issue. Solution: `gh label create NAME --force --repo REPO` is idempotent (creates-if-missing, updates-color-if-present), safe to call repeatedly.

### Task 1: Helpers + unit tests

**Files:**
- Modify: `src/vk/gh.py`
- Modify: `tests/unit/test_gh.py`

- [x] **Step 1: TDD — add `TestEnsureLabel` and `TestEnsureLabels`**

Seven unit tests in `tests/unit/test_gh.py`:

`TestEnsureLabel`:
- `test_calls_gh_label_create_with_force` — command shape and presence of `--force`, `--repo`, `--color`
- `test_includes_description_when_given`
- `test_omits_description_by_default`
- `test_propagates_gh_error`

`TestEnsureLabels`:
- `test_calls_once_per_name` — iteration order preserved
- `test_empty_list_is_noop`
- `test_error_aborts_remaining` — first failure propagates; caller decides recovery (partial-label state is worse than none)

- [x] **Step 2: Implement `ensure_label` and `ensure_labels`**

```python
def ensure_label(
    *,
    repo: str,
    name: str,
    color: str = "ededed",
    description: str = "",
) -> None:
    args = ["label", "create", name, "--repo", repo, "--force", "--color", color]
    if description:
        args.extend(["--description", description])
    _run_gh(args)


def ensure_labels(*, repo: str, labels: list[str]) -> None:
    for name in labels:
        ensure_label(repo=repo, name=name)
```

- [x] **Step 3: Run unit tests**

```bash
uv run pytest tests/unit/test_gh.py -q --no-cov
```

Expected: green, 7 new + existing passing.

---

## Phase 2: Call `ensure_labels` from `dispatch create` [agentic]
**Depends on:** Phase 1

**Context:** The per-phase loop in `dispatch_create` calls `gh.create_issue(repo, labels=[tag, plan:<slug>, phase:<n>])`. If any label is missing, the first create fails with `GhError`, the phase is skipped, subsequent phases continue and also fail — ending in a partial-dispatch state that requires manual cleanup.

### Task 1: Bootstrap labels once before the creation loop

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py` — `dispatch_create`
- Modify: `tests/integration/test_dispatch.py` — new `TestDispatchEnsuresLabels`

- [x] **Step 1: TDD — integration tests**

Three tests in `TestDispatchEnsuresLabels`:
- `test_dispatch_calls_ensure_labels_with_full_set` — asserts agentic + manual + `plan:<slug>` + `phase:0..N` all passed
- `test_ensure_labels_called_before_any_create_issue` — asserts ordering in the mock call log
- `test_ensure_labels_failure_aborts_before_any_issue` — exit non-zero, `create_issue` never called

- [x] **Step 2: Wire the call**

Before the phase loop:

```python
agentic_label = dispatch_cfg.labels.get("agentic", "vk-ready")
manual_label = dispatch_cfg.labels.get("manual", "manual")
required_labels = sorted({
    agentic_label,
    manual_label,
    f"plan:{slug}",
    *(f"phase:{p.number}" for p in plan.phases),
})
try:
    gh.ensure_labels(repo=target_repo, labels=required_labels)
except gh.GhError as exc:
    err_console.print(f"Error: Could not ensure labels on {target_repo}: {exc}")
    raise typer.Exit(4) from exc
```

Labels are collected as a `set` (dedup) and `sorted()` for deterministic output.

- [x] **Step 3: Run**

```bash
uv run pytest tests/integration/test_dispatch.py -q --no-cov
```

Expected: new tests green, existing `TestDispatchApply` etc. still green (they mock `vk.commands.dispatch_cmd.gh` wholesale, so `ensure_labels` silently no-ops on `MagicMock`).

---

## Phase 3: Call `ensure_labels` from `dispatch migrate` [agentic]
**Depends on:** Phase 2

**Context:** The migrate command calls `gh.edit_issue(add_labels=[plan:<slug>, phase:<n>])` per rewrite. It may mutate Issues across multiple repos (rewrites inherit the repo from each tracking URL), so labels must be ensured per unique target repo.

### Task 1: Group by repo and ensure labels per repo

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py` — `migrate`
- Modify: `tests/integration/test_dispatch_migrate.py` — new `TestMigrateEnsuresLabels`

- [x] **Step 1: TDD — integration tests**

Two tests in `TestMigrateEnsuresLabels`:
- `test_migrate_calls_ensure_labels_per_repo` — one call per unique repo with the right `plan:<slug>` + `phase:<n>` set
- `test_migrate_aborts_when_ensure_labels_fails` — exit non-zero, `edit_issue` never called

- [x] **Step 2: Wire the call**

Before the rewrites loop:

```python
labels_by_repo: dict[str, set[str]] = {}
for r in rewrites:
    labels_by_repo.setdefault(r["repo"], set()).update(
        {f"plan:{slug}", f"phase:{r['phase_number']}"}
    )
for repo_name, needed in labels_by_repo.items():
    try:
        gh.ensure_labels(repo=repo_name, labels=sorted(needed))
    except gh.GhError as exc:
        err_console.print(f"Error ensuring labels on {repo_name}: {exc}")
        raise typer.Exit(4) from exc
```

- [x] **Step 3: Run**

```bash
uv run pytest tests/integration/test_dispatch_migrate.py -q --no-cov
```

Expected: 10 tests green (2 new + 8 existing).

---

## Phase 4: Bump version and run full suite [manual]
**Depends on:** Phase 3

- [x] **Step 1: Bump to `1.1.1`**

Patch bump — this is a bug fix, not a new feature. Update `pyproject.toml`:

```
version = "1.1.1"
```

- [x] **Step 2: Refresh `uv.lock`**

```bash
uv lock
```

Expected: `Updated vk v1.1.0 -> v1.1.1`.

- [x] **Step 3: Full suite with coverage**

```bash
uv run pytest tests/ -q
```

Expected: **372 passed, 9 skipped**, total coverage ≥ 75% (measured at 80.74%).

- [x] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock src/vk/gh.py src/vk/commands/dispatch_cmd.py \
        tests/unit/test_gh.py tests/integration/test_dispatch.py \
        tests/integration/test_dispatch_migrate.py
git commit
```

Landed as `2e3ee0c` — `fix(dispatch): ensure required labels exist before creating/editing issues (v1.1.1)`.

---

## Deployment (outside plan scope)

The `vk` CLI is installed as a `uv`-managed tool on the operator's laptop and on the `secure-agent-pod`. After pushing `main`:

- Operator laptop: `uv tool upgrade vk` (or whatever the user's install path is).
- Pod: rebaked into the `agent-images` image via pyproject pin / install step; picked up on pod bump.
