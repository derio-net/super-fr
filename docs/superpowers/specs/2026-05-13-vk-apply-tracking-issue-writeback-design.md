# `vk apply` tracking_issue writeback — Design

## Problem

`vk apply --yes` (and `vk.bridge.tick`, which shares the same library path) creates GitHub Issues via `gh.create_issue(...)` and captures the new URLs in `ApplyResult.created_issues`. **Neither caller writes those URLs back to the plan yaml's `phase.tracking_issue` field.**

The dispatch decision in `vk/diff.py:117-132` pivots per-phase on `phase.phase.tracking_issue is None`:

```python
tracking = phase.phase.tracking_issue
obs = observed.phases.get(phase_n)
if tracking is None or obs is None:
    mutations.append(IssueCreate(...))
    continue
```

Consequence: re-running `vk apply --yes` on a plan whose Issues were created in a previous run sees `tracking_issue: null` for each phase on disk, so `diff()` emits another `IssueCreate` — producing **duplicate Issues on GitHub**.

The bug is also latent in `vk/bridge/__init__.py:151` (`apply_result.created_issues` is read for failure accounting but never written back). The bridge is partially masked today by the `vk-ready` gate, but the code path is the same shape.

A second consequence: the bridge daemon's `discover_plans` (`bridge/__init__.py:80-94`) iterates phases that have `tracking_issue` set in its **local checkout** and queries GH for the `vk-ready` label. Without the writeback, no operator-side commit can make a freshly-dispatched phase discoverable — the URL never lands in any checkout.

The bug has been latent since v2 shipped. The integration test at `tests/integration/test_v2_full_lifecycle.py:70,136` already hand-stamps `raw["phase"]["tracking_issue"] = new_url` to paper over the gap.

## Options considered

1. **Library-level writeback inside `apply()`.** Pass plan-dir context into `apply()`; `apply.py` itself persists the URL after each successful `IssueCreate`. *Rejected.* The codebase commits to a layering rule (`apply.py` is GH-side-only; `plan_ops.py` is THE plan-file writer). Pushing plan-file mutations into `apply()` weakens that rule for marginal convenience.

2. **Callback parameter: `apply(..., on_issue_created=cb)`.** `apply()` invokes a caller-provided callback per `IssueCreate` success. *Rejected.* Adds function-pointer plumbing the codebase doesn't use elsewhere; cleaner separation than option 1 but with no offsetting benefit over option 3.

3. **New `plan_ops.set_tracking_issue()` writer, called by callers.** Both call sites (`apply_cmd._apply_one` and `bridge.tick`) iterate `result.created_issues` and invoke the helper. *Accepted.* Mirrors the existing convention (`tick()`, `complete_phase()`, `rework_add_origin()` are all in `plan_ops`, all stage but don't commit). Two callers, each a small loop.

## Decision

Adopt option 3.

### New writer

```python
# vk/plan_ops.py
def set_tracking_issue(plan_dir: Path, phase_n: int, url: str) -> None:
    """Persist phase.tracking_issue back to <plan_dir>/<NN>.yaml.

    Idempotent on re-call with the same url. Re-parses to validate the
    write still passes schema. Stages but does not commit. Raises
    PlanEditError if the phase yaml is missing or the post-write
    re-parse fails.
    """
```

Pattern mirrors `tick()`:

1. `<plan_dir>/<NN>.yaml` where `NN = f"{phase_n:02d}"`. Raise `PlanEditError` if the file does not exist.
2. `yaml.safe_load` the file into a dict.
3. If `raw["phase"]["tracking_issue"] == url`, return early (idempotent — defensive; in practice `diff()` would not have emitted `IssueCreate` if it were already set).
4. Mutate `raw["phase"]["tracking_issue"] = url`. (Silently overwrites a previous non-null URL — see *Overwrite semantics* below.)
5. `_yaml_dump` and write the file.
6. `parse(plan_dir)` to validate schema integrity.
7. `_stage(repo_root, [phase_path])`.
8. Tag-agnostic: behaves identically for `tag: agentic` and `tag: manual` phases.

No schema change — `phase.tracking_issue` already exists in `vk/types.py:86` (`str | None`).

**Overwrite semantics.** A re-call with a *different* URL silently overwrites the existing value. This is intentional: it handles the recovery path where an operator manually deletes the GitHub Issue. In that case `observe()` returns no `PhaseObservation` for the phase, `diff()` re-emits `IssueCreate` even with a non-null `tracking_issue`, and the writeback must replace the stale URL or the plan would point to a deleted Issue forever. No warning is logged because the writeback is invoked in lock-step with a successful new `IssueCreate` — by construction the new URL is the right one.

### Caller wiring — CLI

In `vk/commands/apply_cmd.py::_apply_one`, after `result = apply(d, gh)`:

```python
writeback_failures: list[dict[str, Any]] = []
for phase_n, url in result.created_issues.items():
    try:
        plan_ops.set_tracking_issue(plan_dir, phase_n, url)
    except (PlanEditError, OSError, PlanSchemaError) as e:
        writeback_failures.append(
            {"phase_number": phase_n, "url": url, "error": str(e)}
        )
```

New imports `apply_cmd.py` must add:

```python
from vk import plan_ops
from vk.plan_ops import PlanEditError
```

(`PlanSchemaError` is already imported from `vk.parser`.)

The existing failure-display block at `apply_cmd.py:160-163` is extended to print writeback failures alongside `result.failures` (human-readable: `f"phase {phase_n}: writeback of {url} failed: {error} (backfill `phase.tracking_issue` manually or re-run apply)"`). Exit code is `4` if either list is non-empty.

**JSON output shape** gains one new key — `tracking_issue_writeback_failures` — keeping `failures` semantically pure as "GH-mutation failures":

```json
{
  "plan": "...",
  "mutations": [...],
  "warnings": [...],
  "applied": true,
  "failures": [
    {"mutation": "IssueCreate", "error": "..."}
  ],
  "created_issues": {"1": "https://github.com/..."},
  "tracking_issue_writeback_failures": [
    {"phase_number": 2, "url": "https://github.com/...", "error": "..."}
  ]
}
```

The key is always present (empty list when nothing to report), so consumers don't need to feature-detect.

### Caller wiring — bridge

In `vk/bridge/__init__.py::tick`, after `apply_result = apply(d, gh, plan=plan)`:

```python
for phase_n, url in apply_result.created_issues.items():
    try:
        plan_ops.set_tracking_issue(plan.dir, phase_n, url)
    except (PlanEditError, OSError, PlanSchemaError) as e:
        failures.append(f"phase {phase_n}: writeback failed: {e}")
```

The `Plan` model already exposes `plan.dir` (the source directory, set by `parse()` — see `vk/parser.py:37-49`). No new helper is required.

`TickResult.failures: tuple[str, ...]` keeps its existing string-list shape — the bridge daemon consumes formatted strings, not structured records. The CLI uses a structured shape (see above) because `--format json` consumers benefit from it; the bridge's MCP-fed logging surface does not.

## Failure handling

`ApplyResult` is `frozen=True`; the writeback failures cannot be merged into `result.failures` post-return. They are collected in a parallel list and emitted via the existing failure-reporting path:

- **Exit code reused.** `vk apply --yes` already returns `4` for any GH-side failure. Writeback failures map to the same exit code — operationally identical from the operator's view ("something needs human attention"). No new exit code.
- **Failure message names the URL.** So an operator who hits a disk error during a 12-phase apply can still hand-backfill the missing `tracking_issue` fields. If they don't, the next run will produce a duplicate — that's a known regression and the message says so.
- **Subsequent IssueCreates continue.** Writeback failure does not abort the loop; it appends to the failure list and proceeds. Matches the existing failure-accumulation pattern in `apply()`.

## Branch context (workflow note, not a code change)

`vk apply` does not create branches, commit, or push. The writeback follows the existing `plan_ops` convention: write to working tree, `git add`, **no commit**. Three workflow shapes are equally supported:

| Operator's branch when running `vk apply --yes` | What happens |
|---|---|
| `main` directly | Staged on `main`. Operator commits + pushes. |
| Feature branch (editing the plan) | Staged on the feature branch. Operator commits → PR → merge → main. |
| Per-plan branch convention | Same as feature branch — we use HEAD as-is. |

`vk-ready` is applied **at GH-Issue-creation time** (the renderer projects it into the rendered label set, so `gh.create_issue` lands the Issue with `vk-ready` already on it). It is not a separate later step. The bridge's ability to discover the phase is gated entirely by **the URL appearing in the yaml in the bridge's local checkout** — which means: operator commits → merges to main → bridge checkout `git pull`s → bridge sees `tracking_issue` on next tick.

This spec does not change git-workflow behavior. Auto-commit / auto-branch / auto-PR is out of scope here.

## Manual phases

`render.py:58-59` projects `MANUAL`, not `VK_READY`, for `tag: manual` phases. The writeback is **tag-agnostic** by design:

- `vk apply --yes` still creates the Issue (diff() pivots on `tracking_issue is None`, not on `tag`).
- The Issue lands with the `manual` label, not `vk-ready`.
- The bridge ignores it (`_any_phase_is_vk_ready` requires `vk-ready` on the gh Issue).
- The writeback still persists the URL to the yaml — **required for idempotency**. Without it, re-running apply duplicates manual Issues exactly like agentic ones.

Manual phases are completed via `vk plan complete-phase --note "..."`; the renderer then projects `state: CLOSED` and the next `vk apply --yes` closes the Issue. No new interaction with the writeback path.

## Local-only workflow (no bridge)

Identical to the bridged case minus the bridge:

- Operator runs `vk apply --yes` from any branch.
- Issue created on GH; yaml updated; staged.
- Operator commits at their cadence; never pushes if the plan is local-only.
- Re-running `vk apply --yes` is now genuinely idempotent — no duplicates on the second invocation.

This is in fact the workflow where the bug is most visible today: an operator iterating on a plan locally and re-running apply after each tweak produces N duplicate Issues per phase.

## `vk-dispatch` skill update

The current skill (`skills/vk-dispatch/SKILL.md`) ends after "Relay the Issue URLs" without telling the operator/agent to commit the now-staged `tracking_issue` change. That leaves the bridge blind even though the writeback succeeded.

Add a new step after "Relay the Issue URLs":

> **5. Commit the staged writeback.** `vk apply --yes` stages the `tracking_issue` line into each affected `<plan>/<NN>.yaml`. Commit and push (or open a PR — operator's convention) so the bridge's checkout can see the URLs on its next tick. Suggested message: `vk apply: persist tracking_issue for <plan>`.

(Renumber the existing step 5 — "On refusal, stop" — to step 6.)

The skill update ships in the same PR as the code change. No separate version bump.

## Tests

Tests live in three layers (unit on the helper, unit on each caller, integration end-to-end).

| Test | Where | Asserts |
|---|---|---|
| `set_tracking_issue` writes yaml, re-parse validates, file is `git add`-staged | `tests/unit/test_plan_ops.py` **(new file)** | Helper correctness |
| `set_tracking_issue` is idempotent on re-call with the same URL (no rewrite) | same | Idempotency |
| `set_tracking_issue` overwrites a different non-null URL without raising (operator-deletes-on-GH recovery path) | same | Overwrite semantics |
| `set_tracking_issue` raises `PlanEditError` if the post-write yaml fails schema validation | same | Failure path |
| `set_tracking_issue` raises `PlanEditError` if `<NN>.yaml` for that phase doesn't exist | same | Defensive guard |
| `set_tracking_issue` works identically for `tag: manual` phases | same | Tag-agnostic guarantee |
| After `apply_command --yes` against a plan with `tracking_issue: null`, every affected phase yaml now carries the new URL | extend `tests/unit/test_v2_apply.py` | CLI integration |
| **Second** `apply_command --yes` invocation against the same plan produces zero `IssueCreate` mutations | same | Idempotency / no duplicates (the core regression-prevention test) |
| `apply_command` **without** `--yes` (dry-run) leaves plan yaml unchanged even when `created_issues` would have been non-empty | same | Dry-run safety |
| If GH `create_issue` fails for one phase but succeeds for siblings, siblings still get their writeback; the failed phase's yaml stays `null` | same | Partial-failure isolation |
| If `set_tracking_issue` raises, the failure is surfaced as a `tracking_issue_writeback_failures` entry in `--format json` output AND in the text output, exit code is `4` | same | Writeback failure path |
| `apply_command --all` writes back per plan independently; a later-plan failure does not roll back an earlier-plan writeback | same | `--all` isolation |
| `bridge.tick` writes back tracking_issue identically (positive path) | extend `tests/unit/test_vk_bridge_tick.py` | Bridge integration |
| `bridge.tick` accumulates writeback failures into `TickResult.failures` as formatted strings | same | Bridge failure path |
| Integration: **replace** the manual `raw["phase"]["tracking_issue"] = new_url` stamps at `tests/integration/test_v2_full_lifecycle.py:69-71` and `:135-137` with a call to `plan_ops.set_tracking_issue(plan_dir, 1, new_url)`. The test must continue to pass | `tests/integration/test_v2_full_lifecycle.py` | Helper produces the same yaml state as the hand-written mutation, and documents the canonical caller pattern. The test calls `apply()` (the library) directly, not `apply_command` (the CLI), so the writeback is not auto-invoked here |

## Version bump

Per `CLAUDE.md`: user-observable plugin behavior change (CLI side-effect: plan files now written, plus skill content updated). Patch bump: `2.1.1 → 2.1.2`.

Lockstep update across:

- `pyproject.toml::[project].version`
- `.claude-plugin/plugin.json::.version`
- `.claude-plugin/marketplace.json::.plugins[0].version`

Run `uv sync` to refresh `uv.lock`, then `uv run vk --version` to confirm.

## Out of scope

- **Backfilling `tracking_issue` for already-orphaned Issues.** A one-off concern; an operator can hand-edit, or `vk plan migrate` already handles historical v1 → v2 cases (`migrate.py:496`).
- **Other state writes from apply** (e.g. `state.completion.at`). Those flow through `vk plan tick` / `complete-phase` and are owned by the agent / `vk-execute` skill.
- **Auto-commit / auto-branch / auto-PR.** The `vk` CLI deliberately leaves git workflow to the operator. Per-plan-branch automation is a much larger design conversation; if pursued, it belongs in a separate spec.
- **Cross-repo `depends_on:` semantics.** Already on the backlog as a separate thread.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-05-13-vk-apply-tracking-issue-writeback | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-05-13-vk-apply-tracking-issue-writeback/` | — |
