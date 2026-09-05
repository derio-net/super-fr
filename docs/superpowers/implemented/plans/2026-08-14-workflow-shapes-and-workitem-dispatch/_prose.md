# Workflow shapes and WorkItem dispatch

Implements `docs/superpowers/specs/2026-08-14-workflow-shapes-and-workitem-dispatch-design.md`
(a1 + a2). The spec's b and c parts are seams only — Phase 10 defines them and
ships no adapter.

## What this plan delivers

Two things that are easy to confuse:

- **a1 — fr-goal becomes data.** A workflow *shape* is a YAML manifest of steps
  (`kind: cli` executed by fr, `kind: agent` dispatched to the harness,
  `gate: operator` pauses), resolved repo-over-shipped, with a durable
  git-tracked run cursor under `docs/superpowers/runs/`. `fr-goal <shape>`
  selects one; no argument means today's pipeline, unchanged.
- **a2 — dispatch stops assuming phases.** `Runner.dispatch(plan, phase, repo,
  issue_number)` becomes `dispatch(item: WorkItem)`, where the granularity
  (`run` | `phase` | `spec`) is declared by the shape. This is a **hard cutover**:
  both adapters and the bridge daemon move in the same PR, no compatibility shim.

## Why the phases are ordered this way

Phase 1 is first because it is the **riskiest**, not because it is foundational.
Lifting the queue state vocabulary off GitHub labels touches `render.py` — 22K,
the largest module in the package — and the spec's most optimistic assumption is
that the state *decision* can be made tracker-neutral without restructuring the
GitHub *projection*. Phase 1 proves or disproves that immediately, and its green
bar is a characterization test asserting a byte-identical projection for an
unchanged plan.

Phase 1 also avoids speculative generality: it extracts `ItemState` **and**
rewires `labels.py` / `render.py` to consume it in the same phase, so the
abstraction has a real caller the moment it exists.

Phases 2–5 are the cutover proper, ordered so each lands green: the value type,
then the protocol and loop, then the adapters, then capability negotiation.
Phases 6–9 build the shape axis on top. Phase 10 defines the seams (b) and (c)
will consume. Phase 11 wires fr-goal itself onto its own manifest and performs
the major bump.

`depends_on` states real blockers only. Phases 2 and 5 deliberately do not
depend on 1 — a phase-unit dispatch of this plan could run them concurrently.

## Invariants the implementation must not break

- **`tick`'s failure doctrine.** Per-item failure accumulation; one bad item
  never aborts the loop; a raising `dispatch` leaves the synced stamp unwritten
  so the next tick retries. Phase 3 restates every one of these as a test before
  the loop is rewritten.
- **Issue creation stays operator-only.** `apply(skip_issue_create=True)` in the
  tick — the 2026-05-18 incident. No phase relaxes this.
- **The bridge frame is untouched.** Phase 4 changes `bridge_cli.py` only where
  the tick signature forces it. The flock, the bridge-owned checkout sync
  (#286), the per-plan I9 boundary, the metrics wire format, and the seen-plans /
  done-closed state files all stay exactly as they are.
- **`fr:synced` is not an `ItemState`.** It is dispatch bookkeeping that happens
  to live on the Issue because there is nowhere better; it is typed separately so
  a tracker that cannot express it is still usable.
- **fr never invokes a model.** `kind: agent` steps produce a brief for the
  harness to dispatch. `fr run advance` must never shell out to an LLM — that is
  the structural form of the `no-claude-p-batch` rule, not merely compliance
  with it.

## Gotchas discovered while planning

- **`fr_version` must span the bump.** This plan performs the 3.19.0 → 4.0.0
  bump in Phase 11, so phases after it execute under 4.0.0. `fr plan create`'s
  default `>=3.0.0,<4.0.0` would trip the plan's own gate mid-run; the plan is
  authored `>=3.19.0,<5.0.0`.
- **Model tiers resolve host-side, not in the container.** `fr models resolve`
  run through `fr isolation exec` reports *unbound* because the devcontainer's
  `$HOME` is not the operator's. Resolve on the host.
- **Card titles stop being identity but stay presentation.** VK dedup must map
  existing card titles back to item ids, or every card created before this change
  duplicates on the first post-deploy tick.

## Verification

Every phase ends green on its own tests. Phase 11 runs the full CI gate
(`ruff format`, `ruff check`, `mypy` over all four `src` trees, `pytest` with
`cov-fail-under=75`, `bump-version.py --check`). The live bridge walk is the
spec's post-merge Test Plan, driven by the operator — `vk-dispatch-unchanged-after-cutover`
stays `not-implemented` until that walk completes, even though its integration
half lands in Phase 4.
