# Plan — spec-dispatch (superpowers-for-vk)

## What this plan delivers

The library + CLI surface for spec-level dispatch, as designed in
`docs/superpowers/specs/2026-05-13-spec-dispatch-design.md`. The bridge
cron caller that consumes this work lives in a sibling plan in
`derio-net/agent-images` (`2026-05-14-spec-dispatch-bridge`).

Two phases, two PRs:

- **Phase 1** — parser grammar + cross-repo `compute_status` upgrade.
  Purely additive. `vk spec status` keeps working for old specs; it
  also gains the ability to resolve cross-repo plans via the gh
  contents API. No new commands, no version bump.

- **Phase 2** — `vk.spec.dispatch`, the two new CLI commands
  (`vk spec apply`, `vk spec self-review`), the bridge library hook
  (`vk.bridge.discover_specs`), and the version bump to 2.2.0. This
  is the user-visible release.

## Success criteria

After both phases ship:

- `uv run vk --version` reports 2.2.0.
- `uv run vk spec self-review <spec>` validates the grammar from
  spec §1.3 — all 7 error classes flagged with the documented messages.
- `uv run vk spec apply <spec> --yes` dispatches every plan whose
  `Depends on` chain resolves to `Complete` upstreams. Plans whose
  upstreams aren't complete emit `blocked` outcomes; manual-action
  rows emit `skipped_manual`; cross-repo 404s emit `unreachable` and
  the CLI exits 6.
- Cross-repo plans in `vk spec status` no longer show as
  `Unreachable` (unless `--no-gh` is passed).
- Old specs (free-form `Depends on` prose) keep rendering under
  `vk spec status` exactly as today — opt-in to validated grammar
  is per-spec, driven by the operator who wants spec-dispatch.

## What this plan does NOT deliver

- The bridge cron caller change — that's the sibling plan in
  `agent-images`. Without it, the bridge does not auto-advance the
  DAG. Operators still get manual `vk spec apply --yes` end-to-end.
- A `vk plan convert --add-spec-deps` migration tool. Migration is
  per-spec, hand-edited by the operator. The 9 existing specs are
  unchanged by this plan.
- Cross-spec dependencies (a plan in spec A depending on a plan in
  spec B). Out of scope per spec §"Non-goals".
- Webhook-based push notifications. Pull-shape via gh contents API
  suffices per spec §2.3 cost analysis.

## Cross-cutting principles preserved

- **Derive, don't store** — no `_spec_state.yaml`, no spec-doc
  mutations by the bridge or CLI. Spec progress is computed on every
  invocation from each plan's `completion.at` markers on `main`.
- **Validation only at explicit invocation** — `parse_spec` tolerates
  any cell content; `_validate_spec` runs only at `self-review` and
  `apply` entrypoints. This is what preserves the "old specs still
  render" promise (spec §1.3, decision D7).
- **Shared primitive, two callers** — `vk.spec.dispatch()` is the
  library function used by both `vk spec apply` (operator) and
  (in the sibling plan) the bridge cron. One code path, no
  divergence risk.

## Sequencing

Phase 1 is independently shippable — it improves `vk spec status` and
adds the cross-repo read primitive used in Phase 2. Phase 2 depends
on Phase 1 (`depends_on: [1]` in `02.yaml`).

After Phase 2 merges and 2.2.0 is live, the sibling plan in
`agent-images` becomes dispatchable.

## Out-of-band operator tasks

None for this plan. Plan-internal phases are agentic. The PR review
cycle for each phase is the only human-in-the-loop step.
