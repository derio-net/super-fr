# Terminal-Done Issue close — design

**Issue:** #294 — A VK card that reaches Done out-of-band (operator manual move,
or VK auto-move on merge) has its workspace reaped but its linked GitHub Issue
is never closed → the phase reads incomplete → downstream phases stay blocked.

**Date:** 2026-06-09
**Status:** approved (fr-goal batched Q&A, 2026-06-09)

## Problem

#290 wired `observe_pr_status` → `pr_state.tick`, which closes a phase's
tracking Issue **only as part of its own transition** (`In progress`/`In
review` + merged → Done). `pr_state` only scans `In progress`/`In review`
cards. A card that is **already Done** when the bridge ticks is never scanned,
so the close cascade never runs. `reap_orphans` iterates Done cards but only
archives their workspaces — it does not close Issues.

Observed 2026-06-09 on `derio-net/runs-fr` phase 4: operator merged the PR and
moved the card to VK Done; the workspace was reaped (`reaped … gh#5, card
Done`) but Issue #5 stayed OPEN; `_phase_complete(phase 4)` was false
(completion.at set, issue open, no observable merged PR) → phase 5 stayed
`fr:blocked`. Manually closing #5 + `fr apply` unblocked it.

## Decision summary (batched Q&A, 2026-06-09)

| Decision | Choice |
|---|---|
| Scope | **Also reconcile the backlog** — close open linked Issues for ALL Done cards, including already-reaped ones, not just at reap time |
| Post-merge verification | **Live repro + self-heal proof** on the deployed bridge |

## Design

### A single Done-card Issue-close sweep (in `pr_state.py`)

A new `reconcile_done_issues` lives in `pr_state.py` — NOT `workspaces.py` —
because `pr_state` already owns the idempotent default closer
(`_default_close_gh_issue`), the title regexes, and `mcp.list_issues`. Putting
it there avoids the circular import that would arise if `workspaces` (which
`pr_state` imports `archive_for_card` from) tried to import the close helper
back.

```python
def reconcile_done_issues(
    mcp: MCPCardClient,
    *,
    project_id: str | None = None,
    seen: set[str] | None = None,
    close_gh_issue: Callable[[str, str], None] | None = None,
) -> set[str]:
    """Close the linked GH Issue of every Done card not already handled.

    Returns the updated `seen` set of `"<owner/repo>#<n>"` keys.
    """
```

- Lists cards in `status="Done"` (scoped by `project_id`). This subsumes the
  reap-time case: a card whose workspace was just reaped this tick is still a
  Done card the sweep sees. `reap_orphans` stays purely workspace-focused.
- For each Done card, parse `gh#N` **and** `[owner/repo]` **from the title**
  (`gh#N: [owner/repo]`) — both from a single source, the Issue's own
  coordinates. This is deliberately NOT `_close_linked_gh_issue` (which takes
  the repo from `latest_pr_url`): a manually-Done card may have no PR url, and
  the title is the authoritative Issue identity regardless. Reuses the
  `_GH_ISSUE_NUM_FROM_TITLE_RE` + `_GH_REPO_FROM_TITLE_RE` regexes. Cards whose
  title lacks an `[owner/repo]` are skipped (can't safely target a close).
  Build the key `"<owner/repo>#<n>"`.
- **Bounded by a persisted seen-set:** if the key is already in `seen`, skip
  (no gh call). Otherwise close the Issue (idempotent — already-closed is a
  no-op) and add the key to `seen`. So the first post-deploy tick closes the
  entire open backlog at once; every later tick is ~0 gh calls (all keys
  seen). New Done cards are closed exactly once.
- Fully defensive: a `list_issues` failure or a per-card error is logged and
  skipped — never raises (the bridge wraps it in the existing guard anyway).

### Wire into the bridge tick

`bridge_cli.main()`:

- Persist the seen-set in `~/.willikins-agent/_done_closed.json` (mirroring the
  existing `_seen_plans` load/store: `_load_done_closed` / `_store_done_closed`).
- After `reap_orphans`, inside a guarded `try/except`:
  ```python
  done_seen = _load_done_closed()
  done_seen = reconcile_done_issues(cast(Any, mcp), project_id=project_id, seen=done_seen)
  _store_done_closed(done_seen)
  ```
  A failure logs + pushes `failure_total(reason="done_reconcile_error")`; the
  tick continues.

## Components changed

- **`packages/fr-vk/src/fr_vk/pr_state.py`** — add `reconcile_done_issues`
  (reuses `_close_linked_gh_issue` / `_normalize_issues`).
- **`packages/fr-vk/src/fr_vk/bridge_cli.py`** — `_DONE_CLOSED_PATH`,
  `_load_done_closed`, `_store_done_closed`; call `reconcile_done_issues` after
  `reap_orphans`, guarded.
- Tests: new `tests/unit/test_done_reconcile.py`; an end-to-end test (Done
  card + open linked Issue → sweep closes it; seen-set prevents a second close;
  title-without-repo skip).

## Test plan

### Automated (in the PR, TDD)

- **Closes a Done card's open Issue:** a Done card with `gh#5: [o/r]` and key
  not in `seen` → injected closer called with `(o/r, "5")`; key added to the
  returned set.
- **Seen-set bounds re-close:** a key already in `seen` → closer NOT called.
- **Title without `[owner/repo]` is skipped:** a Done card whose title has no
  parseable repo → no close attempted (can't safely target it).
- **No PR-url dependence:** a Done card with `latest_pr_url=None` but a valid
  title still closes (the title is the single source).
- **Resilience:** `list_issues` failure → returns `seen` unchanged, no raise.
- **Bridge wiring:** `main()` loads → calls `reconcile_done_issues` → stores
  the seen-set, inside the guard.

### Test Plan (post-merge — operator-driven)

The bug only manifests on the deployed cron. After merge + release + deploy:

1. Move a VK card to **Done** out-of-band (manually) whose linked GH Issue is
   still OPEN and whose phase blocks a successor.
2. Run one bridge tick (`vk-bridge` wrapper / `python -m fr_vk.bridge`).
3. Assert: the tracking **GH Issue is CLOSED**, and the dependent phase
   unblocks (`fr:blocked → fr:ready`). Re-run a second tick: the Issue is not
   re-touched (seen-set holds).

## Version bump

Touches `src/` (`fr_vk`) → patch bump per `CLAUDE.md`.

## Implementation Plans

| Plan | Repo | File | Depends on |
| ---- | ---- | ---- | ---------- |
| 2026-06-09-terminal-done-issue-close | `derio-net/super-fr` | `2026-06-09-terminal-done-issue-close` | — |
