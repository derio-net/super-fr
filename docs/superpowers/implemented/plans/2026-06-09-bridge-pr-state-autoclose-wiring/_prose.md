# Bridge PR-state auto-close wiring (#290)

## Why

`pr_state.tick()` already implements the belt-and-braces "close the linked GH
Issue when its PR merges" cascade — and it's unit-tested. But the bridge calls
it with an empty `{}` observations map (`# observations are wired in Phase 6` —
never landed), so it's a no-op. Merged phases whose PR lacked a `Closes #N`
keyword never close their Issue → read as incomplete → block downstream phases.
The whole `runs-fr-gateway-skeleton` plan wedged this way after phase 1.

## What

Per the spec (`docs/superpowers/specs/2026-06-09-bridge-pr-state-autoclose-wiring-design.md`),
**wire the observer only** (no dispatch-prompt / `Closes #N` change):

1. **New `pr_observe.observe_pr_status`** — lists cards (`In progress` /
   `In review`) and resolves each card's `latest_pr_url` to `open`/`merged` via
   `gh pr view` (injectable fetcher, mirroring `tick`'s `close_gh_issue` seam).
   Builds the `{card_id: status}` map `tick` consumes. Defensive: per-card
   failures are logged and skipped, never raised.
2. **Wire it into `bridge_cli`** — replace `_pr_state_tick(mcp, {}, …)` with
   the real observation map, inside the existing `pr_state_error` guard.
3. **Heal the backlog** — extend `tick` so `In progress + merged → Done`
   (skip-stage), so the fleet's existing merged-but-stuck cards reconcile
   (close Issue + archive workspace) on the first post-deploy tick.

## How (phases)

1. **Observer** — `observe_pr_status` + the default `gh pr view` fetcher (TDD).
2. **Skip-stage** — `In progress + merged → Done` in `pr_state.tick`; repurpose
   the mismatched-pair test (TDD).
3. **Wire + E2E** — feed the real map into `_pr_state_tick`; an end-to-end test
   proving a merge **without** `Closes #N` still closes the Issue. Plus a
   bridge regression sweep.
4. **Version bump + gates.**

Every phase is TDD and fully agentic — no manual phases. The live repro
(merge a PR without `Closes #N`, run a tick, watch the Issue close + downstream
unblock) is a **post-merge** Test Plan carried in the spec and PR body.
