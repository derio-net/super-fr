# Journal: 2026-08-14-workflow-shapes-and-workitem-dispatch

<!-- fr:journal kind=finding scope=plan id=pr1 created=2026-08-15T17:03:10 state=fixed -->
### pr1 · finding [fixed] · Plan omitted the spec's no-PR-shape mitigation

Spec section 6 lists 'shapes that emit no PR' as a risk with the mitigation 'pinned by a test shape that emits only a document'. The 11-phase plan covered sections 4.A-4.H and 5 but implemented no such test. Added Phase 8 task 3 (P8.T3.S1/S2): a fixture manifest emitting only a report, asserted through check_workflow, build_items and tick, kept permanently under tests/fixtures/workflows/. Found by reading the phases back against the spec, not by self-review - self-review validates acceptance-id linkage and agentic purity, not spec coverage.

<!-- fr:journal kind=discovery scope=plan id=p1-render-absorbed-cleanly created=2026-08-15T17:24:30 phase=1 -->
### p1-render-absorbed-cleanly · discovery · render.py absorbed the ItemState extraction cleanly — spec's optimistic assumption holds (phase 1)

The spec (§6) flagged 'render.py is 22K and Issue-shaped' as its most optimistic assumption. It held. The extraction is +2 functions and 3 changed lines in the render loop; nothing was restructured.

Shape: `_lifecycle_label(phase, obs, plan, observed)` was cut in two along the seam that was already implicit in it — `_item_state(...) -> ItemState` (the decision, names no label) and `_lifecycle_label_for_state(phase, state) -> LabelDef | None` (the GitHub projection). `_lifecycle_label` survives as a one-line delegation so existing callers/tests are untouched. `render()` now computes `item_state` once and uses it for BOTH the lifecycle label and the OPEN/CLOSED decision (`item_state == 'done'` replaced two `_phase_complete(phase, obs)` calls inside the loop).

Why it was easy: the state decision was already a single pure function with no I/O and no label construction beyond its return value. The label vocabulary was the return TYPE, not woven through the body. Projection stayed exactly where it was — inside `render()`'s label-set assembly.

Untouched on purpose: `archive_gate`, `_drift_warnings`, `_phase_complete`, `plan_locally_complete`, `render_body`, `enrichment_block`. Byte-identical projection confirmed by tests/unit/test_render_characterization.py (5 phases, full body + sorted label names + Issue state as literals) plus the 142 pre-existing render/diff/apply/labels/status tests.

<!-- fr:journal kind=discovery scope=plan id=p1-manual-is-outside-itemstate created=2026-08-15T17:24:53 phase=1 -->
### p1-manual-is-outside-itemstate · discovery · `manual` is a sixth GitHub label but NOT an ItemState — the spec's 5-state mapping is incomplete for the real renderer (phase 1)

Spec §4.C lists five states and their labels. The renderer today emits a SIXTH lifecycle label the spec never mentions: `manual`. In `_lifecycle_label` it short-circuits ahead of the dependency check, so a manual phase that is dependency-blocked renders `manual`, not `fr:blocked`.

Resolution taken: `manual` is a routing ATTRIBUTE (human-only; not routable to an agent), not an item state — same category as `runner:<name>` and `phase:<n>`, and it is how the existing code already comments it (render.py's tracking-only branch). So it stays out of `ItemState` and lives in the projection: `_lifecycle_label_for_state` returns MANUAL for any non-`done` state when `phase.tag == 'manual'`, and `project_github` never emits it.

Consequence for later phases: a tracker adapter reading `ItemState` alone cannot tell a manual phase from an agentic one. Phase 5's capability negotiation and Phase 10's tracker protocol must carry routability as a separate item ATTRIBUTE, not expect it in the state enum. Do not 'fix' this by adding a `manual` member to ItemState — a manual phase still has a real state (queued/blocked/in_progress/done); `manual` answers a different question.

<!-- fr:journal kind=discovery scope=plan id=p1-seam-signature-two-functions created=2026-08-15T17:25:15 phase=1 -->
### p1-seam-signature-two-functions · discovery · phase_item_state needed a two-function split: an existing test passes obs decoupled from observed (phase 1)

The plan specifies the public seam as `phase_item_state(plan, observed, phase_number)`, i.e. obs is looked up from `observed`. But tests/unit/test_v2_render.py::test_lifecycle_label_projection calls `_lifecycle_label(plan.phases[0], obs, plan, GhState(phases={}))` — an explicit `obs` against an EMPTY `observed`. Collapsing everything onto the lookup form would have silently turned that test's obs into None and made every parametrized case return 'queued'.

So the extraction is two functions: private `_item_state(phase, obs, plan, observed)` (obs passed in — used by `_lifecycle_label` and by `render()`, which already has obs in hand) and public `phase_item_state(plan, observed, phase_number)` (looks obs up, then delegates; raises KeyError for an unknown phase). Downstream phases should consume the PUBLIC form; `observed` is still needed by both because dependency-blocked is computed from the predecessors' observations, not the item's own.

Also pinned: `obs is None` (never dispatched) yields 'queued', not a sixth state. 'No tracker item exists yet' is a projection concern — `render()` withholds the lifecycle label from a tracking-only Issue via `labels.is_queued`, which is unchanged.

<!-- fr:journal kind=discovery scope=plan id=p1-labels-py-had-no-duplicate created=2026-08-15T17:25:38 phase=1 -->
### p1-labels-py-had-no-duplicate · discovery · P1.T3.S3's optional refactor was a no-op: labels.py holds no logic project_github duplicates (phase 1)

Task 3 step 3 offered deleting label-set logic in labels.py duplicated by `project_github`. Inspected; there is none, and labels.py was left byte-unchanged.

- `QUEUE_MARKER_NAMES` / `is_queued` answer 'did this Issue ever enter a runner queue?' — a membership question that deliberately INCLUDES `fr:synced` and `runner:*`. That is not the state mapping; `project_github` must never include `fr:synced` (asserted in test_item_state.py).
- `LIFECYCLE` (role name -> LabelDef) includes `manual`, which is not an ItemState. It has no non-test caller in the repo; leaving it alone rather than deleting it during a projection-preserving phase.

Deriving `QUEUE_MARKER_NAMES` from `project_github` was rejected: it would make labels.py import item_state, inverting the required dependency direction (item_state -> labels, never the reverse). `is_queued`'s signature is unchanged, as required.

<!-- fr:journal kind=finding scope=plan id=p1-install-bridge-env-failure created=2026-08-15T17:26:02 phase=1 state=fixed -->
### p1-install-bridge-env-failure · finding [fixed] · Full-suite red was environmental: stale uv-tool fr, not the extraction (phase 1)

First full-suite run: 1 failed, 1837 passed, 85 skipped. The failure was tests/integration/test_install_bridge.py::test_install_bridge_flag_writes_wrapper — 'ERROR: ~/.local/share/uv/tools/fr/bin/python cannot import fr_vk.bridge'. This is the known recurring devcontainer condition (stale uv-tool install of fr), unrelated to render.py or item_state.

Fixed in the workspace by re-running the command the error message itself prints:
  uv tool install --force --with packages/fr-vk packages/fr
Re-run: 1 passed. Later phases hitting this same failure should reinstall rather than debug it.

Post-fix gate for Phase 1: pytest full suite green (the 1837+1), ruff check clean, ruff format touched only a quote style in the new test file, mypy clean over packages/fr/src (72 files), `fr acceptance check` 74 rows OK.

<!-- fr:journal kind=discovery scope=plan id=p1-no-version-bump-in-phase-1 created=2026-08-15T17:26:22 phase=1 -->
### p1-no-version-bump-in-phase-1 · discovery · Phase 1 deliberately does NOT bump the version — Phase 11 owns the 3.19.0 -> 4.0.0 bump (phase 1)

AGENTS.md requires a version bump for any PR changing packages/*/src/**, and Phase 1 adds packages/fr/src/fr/item_state.py and edits render.py. The bump was NOT performed here: the plan assigns the 3.19.0 -> 4.0.0 major bump to Phase 11, and `_meta.yaml` is authored `fr_version: >=3.19.0,<5.0.0` precisely so phases straddle it. Whoever opens the PR for this branch must make sure Phase 11 (or the PR itself, if it ships before Phase 11) carries the bump — Phase 1 alone on main would violate the bump rule.

Also unchanged by design: docs/acceptance/matrix.yaml. The spec's matrix rows cover §4.A/B/D/E/F/G; there is no row waiting on §4.C's ItemState extraction, and Phase 1 ships no user-observable surface. `fr acceptance check` stays green (74 rows OK).
