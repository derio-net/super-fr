# Bridge PR-state auto-close wiring — design

**Issue:** #290 — Bridge Issue auto-close is dead: the `pr_state` sweep is fed
an empty observations map (the "Phase 6" wiring never landed), so merged
phases never close their tracking Issue and downstream phases stay blocked.

**Date:** 2026-06-09
**Status:** approved (fr-goal batched Q&A, 2026-06-09)

## Problem

`pr_state.tick()` (`packages/fr-vk/src/fr_vk/pr_state.py`) transitions VK cards
on their linked PR's status and — as a belt-and-braces for PRs lacking a
`Closes #N` keyword — closes the linked GH Issue when the card goes Done. It is
fully implemented and unit-tested. But the bridge calls it with an **empty
observations map**:

```python
# bridge_cli.py — "observations are wired in Phase 6"
_pr_state_tick(cast(Any, mcp), {}, project_id=project_id)
```

`tick()`'s contract: *"Cards without an entry in the map are left untouched."*
Empty map → **no-op**. So no card ever transitions and no Issue is ever closed
by this path. The "Phase 6" wiring (the `vk.observe` call that builds the
`{card_id: "open"|"merged"}` map) was never built; the v2-bridge-rebuild
Phase 6 was marked complete without it.

Consequence (observed 2026-06-09 on `derio-net/runs-fr`): phases whose PR
merged without a `Closes #N` keyword never close their Issue → read as
incomplete → block downstream phases. The other intended close path (`apply()`
projection-close) is circular — it needs a merged PR observed via GitHub's
closing-reference, the very keyword v2 removed. Net: no working auto-close.

## Decision summary (batched Q&A, 2026-06-09)

| Decision | Choice |
|---|---|
| Scope | **Wire the observer only** — activate the existing tested belt-and-braces; no dispatch-prompt / issue-body / `Closes #N` change |
| Backlog | **Also heal In-progress+merged** — a card stuck `In progress` with an already-merged PR transitions straight to Done (skip-stage), so the existing backlog self-heals on the first post-deploy tick |
| Post-merge verification | **Live repro + self-heal proof** on the deployed bridge |

Observer source (design decision, not operator-owned): **gh-based** —
`gh pr view <latest_pr_url>` per card. Self-contained, matches
`_default_close_gh_issue`'s existing gh usage, and doesn't assume VK's card
schema exposes merge state.

## Design

### 1. New PR-status observer

A new module `packages/fr-vk/src/fr_vk/pr_observe.py` exposing:

```python
def observe_pr_status(
    mcp: MCPCardClient,
    *,
    project_id: str | None = None,
    pr_status_fetch: Callable[[str], str | None] | None = None,
) -> dict[str, str]:
    """Build the {card_id: "open"|"merged"} map pr_state.tick() consumes."""
```

- Lists cards in `In progress` and `In review` via
  `mcp.list_issues(status=..., project_id=...)` (same surface `tick` uses).
- For each card with a `latest_pr_url`, resolve the PR's state via
  `pr_status_fetch(url)` (defaults to a `gh pr view <url> --json
  state,isDraft` subprocess; injectable for tests, mirroring
  `tick`'s `close_gh_issue` seam):
  - gh `state == "MERGED"` → `"merged"`
  - gh `state == "OPEN"` and not draft → `"open"`
  - otherwise (draft, closed-unmerged, unknown) → omit the card (no
    transition).
- Per-card failures (gh error, malformed url) are logged and skipped — never
  raise; a bad card must not drop the whole map. Cards without a
  `latest_pr_url` are skipped (nothing to observe yet).

Returns `{card_id: status}`. One `gh pr view` per active card per tick —
acceptable at the bridge's scale (a handful of active cards); GraphQL batching
is YAGNI.

### 2. Wire it into the bridge tick

In `bridge_cli.main()`, replace the `{}` stub:

```python
pr_obs = observe_pr_status(cast(Any, mcp), project_id=project_id)
_pr_state_tick(cast(Any, mcp), pr_obs, project_id=project_id)
```

Both inside the existing `try/except` that already guards the pr_state sweep
(`reason="pr_state_error"`), so an observer hiccup still can't kill a tick.

### 3. Heal the In-progress+merged backlog

Existing wedged cards are stuck `In progress` with an already-merged PR — they
never reached `In review` because observations were empty the whole time, and
`tick()` currently skips `In progress + merged` (the mismatched-pair guard).
Extend the transition table:

```
In progress + open    → In review        (unchanged)
In progress + merged  → Done             (NEW — skip-stage: PR merged before
                                           we ever observed In review)
In review   + merged  → Done             (unchanged)
```

The Done cascade (archive workspace + close linked GH Issue) runs for **both**
Done paths. This lets the first post-deploy tick reconcile the fleet's backlog
of merged-but-stuck cards. `test_tick_ignores_mismatched_status_pr_pairs` is
repurposed: `In progress + merged` now transitions; the remaining genuine
mismatches (e.g. `In review + open`) stay ignored.

## Components changed

- **`packages/fr-vk/src/fr_vk/pr_observe.py`** (new) — `observe_pr_status` +
  the default gh PR-status fetcher.
- **`packages/fr-vk/src/fr_vk/pr_state.py`** — add the `In progress + merged →
  Done` skip-stage transition; keep the Done cascade shared.
- **`packages/fr-vk/src/fr_vk/bridge_cli.py`** — call `observe_pr_status` and
  pass the real map to `_pr_state_tick` (replacing `{}`); drop the
  "wired in Phase 6" TODO.
- Tests: new `tests/unit/test_pr_observe.py`; update
  `tests/unit/test_bridge_pr_state.py` (skip-stage transition); an
  end-to-end test (observer → tick → issue closed) proving a merge **without**
  `Closes #N` still closes the Issue.

## Test plan

### Automated (in the PR, TDD)

- **Observer maps merged/open/skip:** fake `list_issues` + injected
  `pr_status_fetch` → assert `{card_id: "merged"|"open"}`, drafts/closed/no-url
  omitted, per-card gh failure skipped (no raise).
- **Skip-stage transition:** card `In progress` + `merged` → `update_issue(...,
  status="Done")` + archive + close cascade fires.
- **End-to-end (the regression guard):** observer builds `{card: "merged"}`
  from a merged-PR card whose PR body has **no** `Closes #N`; `tick` closes the
  Issue via the injected closer. Proves the close no longer depends on the
  keyword.
- **Resilience:** observer never raises; an empty/failed observation leaves
  cards untouched (existing `{}`-is-no-op behavior preserved for the failure
  path).

### Test Plan (post-merge — operator-driven)

The bug only manifests on the deployed cron. After merge + release + deploy:

1. Identify (or create) a VK card whose linked PR is **merged without a
   `Closes #N` keyword** and whose tracking GH Issue is still OPEN.
2. Run one bridge tick (`python -m fr_vk.bridge` via the wrapper).
3. Assert: the card → **Done**, its workspace is **archived**, and the tracking
   **GH Issue is CLOSED**; any phase that depended on it unblocks
   (`fr:blocked → fr:ready`).

## Version bump

Touches `src/` (`fr_vk`) → patch bump per `CLAUDE.md`.

## Implementation Plans

| Plan | Repo | File | Depends on |
| ---- | ---- | ---- | ---------- |
