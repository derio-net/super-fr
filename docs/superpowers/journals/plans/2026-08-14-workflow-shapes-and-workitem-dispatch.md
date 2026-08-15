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

<!-- fr:journal kind=discovery scope=plan id=p2-identity-grammar created=2026-08-15T17:37:19 phase=2 -->
### p2-identity-grammar · discovery · item_id grammar pinned: repo/spec[/plan[/phase/n]], segment-count parent_id (phase 2)

Identity grammar (spec §4.D) implemented exactly as three id shapes, distinguished by segment count once split on "/" (repo is always owner/name, i.e. 2 segments, which is what pins the counts):

  spec   <repo>/<spec-slug>                       -> 3 segments
  run    <repo>/<spec-slug>/<plan-slug>            -> 4 segments
  phase  <repo>/<spec-slug>/<plan-slug>/phase/<n>  -> 6 segments (second-to-last segment literal "phase")

`item_id(repo, spec_slug, plan_slug=None, phase=None) -> str` is pure string join, no I/O. `phase` without `plan_slug` raises ValueError ("a phase cannot exist outside a plan").

`parent_id(item_id) -> str | None` walks back up the SAME string (no separate lookup table): if the id's second-to-last segment is literally "phase", drop the last two segments (phase -> run level); elif 4 segments, drop the last one (run -> spec level); elif 3 segments, return None (spec is the root). This assumes slugs never contain "/", which is consistent with every slug producer in the repo (kebab-case).

WorkItem.unit ("run"|"phase"|"spec" per spec §4.D/E) is validated against this SAME id-shape classifier in __post_init__ — constructing unit="phase" with a run-level or spec-level id raises ValueError. This means `unit` is redundant with `id`'s shape by construction; Phase 3+ callers should treat `unit` as a convenience/readability field, not an independent source of truth — if they ever diverge, `id` is what identity/dedup keys off.

WorkItem.__hash__ is overridden to `hash(self.id)` rather than the dataclass-default all-fields hash, because `payload: Mapping[str, object]` is commonly a plain dict (unhashable) — hashing on `id` alone is also more correct semantically: two WorkItems are "the same dispatch slot" iff they have the same id, regardless of payload contents at a given tick.

<!-- fr:journal kind=discovery scope=plan id=p2-card-title-still-title-not-key created=2026-08-15T17:37:44 phase=2 -->
### p2-card-title-still-title-not-key · discovery · build_card_title stays VK's title-string presentation; Phase 4 must map it back to item_id for dedup (phase 2)

Read packages/fr-vk/src/fr_vk/dispatch.py: `build_card_title(repo, issue_n) -> str` returns `"gh#{n}: [{owner/repo}]"` (delegates to `fr_vk._cardref.build_card_title("github", repo, issue_n)`), format pinned by test D2, and is the ONLY thing VK dedup keys off today (`fr_dispatch.tick`'s dedup snapshot is the pre-cutover `Runner.dedup_key(repo, issue_number)`, not present in this phase's scope).

This phase does not touch build_card_title, protocols.py, or tick — confirmed unmodified. But per the spec (§4.D "Adapter migration is mechanical") and the plan's own gotcha ("Card titles stop being identity but stay presentation"), Phase 4 needs a concrete answer for one thing this phase's identity grammar makes newly visible:

A card created BEFORE the cutover has no `item.id` baked into it anywhere — only a title of the form `"gh#{n}: [{owner/repo}]"` plus whatever `(repo, issue_number)` VK's own board stores. Phase 4's `existing_dispatches()` (returning item ids per the v2 Runner protocol: `def existing_dispatches(self) -> set[str]`) must therefore RECONSTRUCT the phase-level item_id for each existing card from `(repo, issue_number)` it can already parse off the title/board state — i.e. `item_id(repo, spec_slug, plan_slug, phase=n)` — not merely relabel the old dedup_key. spec_slug/plan_slug are not encoded in the card title at all today (only repo + issue number are), so Phase 4 needs a lookup path from issue_number back to (spec_slug, plan_slug, phase) — almost certainly via the Issue's own body/labels (tracking_issue is already stored on PhaseDoc, so the plan folder -> phase -> issue_number mapping is available locally; the adapter would need the REVERSE, issue_number -> (plan, phase), which today it gets by having been handed `(plan, phase, repo, issue_number)` directly by `tick` rather than needing to invert anything).

Concretely: **do not derive existing_dispatches() ids from card title parsing alone** — the title has no spec/plan slug in it, only owner/repo/issue_number. Phase 4 either (a) has tick continue to supply `(plan, phase)` context so the adapter can compute item_id itself rather than reconstructing it from board state, or (b) VK must start persisting item_id somewhere it does not today (e.g. a card description/field). Flagging (a) as the much cheaper path since tick already has plan+phase in hand at the call site before it ever reaches the adapter.

<!-- fr:journal kind=finding scope=plan id=p2-run-identity-gap created=2026-08-15T17:44:11 phase=2 state=fixed -->
### p2-run-identity-gap · finding [fixed] · Original 3-level id grammar could not express a run item — spec §4.D amended, grammar corrected to 4 levels (phase 2)

Found in coordinator review, not by self-review. The original Phase 2 grammar (`<repo>/<spec-slug>[/<plan-slug>[/phase/<n>]]`) classified any 4-segment id as `unit: "run"`. That silently required a run item to carry a plan slug — but per spec §4.E, a `unit: run` item is dispatched BEFORE its spec and plan exist; both are the run's *outputs*, not inputs (this is the entire reason §4.E says the reachability gate does not apply to run-unit dispatch). At creation a run item therefore has neither slug: under the old grammar it would have been built as a bare 3-segment id (`<repo>/??`) and misclassified as `unit: "spec"`, or been impossible to construct at all without inventing a fake plan slug.

Root cause: the grammar conflated "4 segments" with "the run unit" when in fact 4 segments is ALSO the natural shape of the plan level (`<repo>/<spec-slug>/<plan-slug>`), which the original design never named as its own grammar level. The spec itself was ambiguous here (§4.D implied `<repo>/<spec-slug>/…` for every unit) — the coordinator amended §4.D in the same review that caught this.

Fix — grammar is now four levels, three of which are units:

    run    <repo>/run/<run-id>                        unit: run
    spec   <repo>/<spec-slug>                          unit: spec
    plan   <repo>/<spec-slug>/<plan-slug>              (parent level only — NOT a unit)
    phase  <repo>/<spec-slug>/<plan-slug>/phase/<n>    unit: phase

- New `run_item_id(repo, run_id) -> str` (kept separate from `item_id` rather than adding a `run_id` kwarg to it — the run form shares no other parameters with the spec/plan/phase form, so a separate function reads clearer against the four-level grammar than one function with mutually-exclusive optional args).
- `item_id` now rejects `spec_slug == "run"` — both the run form and the plan form are "<owner>/<repo> plus two segments"; the literal `run/` marker is what disambiguates them, and this guard is what keeps a spec-level id from ever colliding with a run-level one.
- `_id_level` (internal) now returns one of FOUR values (`run | spec | plan | phase`), not three — it classifies by marker (`segments[-2] == "phase"`, `segments[2] == "run"`) rather than by segment count alone, since segment count alone can't distinguish run-form from plan-form (both 4 segments).
- `WorkItem.__post_init__`'s unit/id agreement check needed NO logic change: `unit: Literal["run","phase","spec"]` never equals `_id_level`'s `"plan"` result, so a plan-form id is automatically rejected for every unit value, including `"run"` — the bug is closed structurally, not by an extra branch.
- `parent_id` of a run item: **`None`**. Reasoning: a run item is a root exactly like a spec item — it has no spec yet, and per spec §6 / Phase 8 task 3 (the no-PR-shape mitigation, a fixture manifest emitting only a document) a run may never gain one at all. Treating a run's parent as `None` rather than inventing a placeholder keeps `WorkItem.parent` meaning "the item's actual position in a graph that already exists," which is the same meaning it has for a spec item today.

Tests added (RED confirmed before the fix, all pass after): `test_run_item_id_format`, `test_run_item_id_is_deterministic`, `test_item_id_rejects_run_as_spec_slug`, `test_parent_id_of_run_item_is_none`, `test_parent_id_of_plan_is_still_the_spec_level_not_confused_with_run`, `test_work_item_run_unit_matches_run_form_id`, `test_work_item_rejects_plan_form_id_for_any_unit`. Full suite: 22 passed (tests/unit/test_work_item.py), mypy clean, ruff clean.

Handoff for Phase 8 (owns `fr run start`/the run-id shape and the no-PR-shape fixture): a run item's `id` is `run_item_id(repo, run_id)` where `run_id` is whatever `fr run start` assigns (§4.B shows `run: 2026-08-14-ticket-polling` as an example run id — looks like a date-prefixed slug, same shape as a plan slug, but it is NOT a plan slug and must not be passed through `item_id`). When/if a run later spawns a spec+plan (the common case, not the no-PR-shape case), the resulting spec/plan/phase items' `parent` should point at the run's `run_item_id`, NOT at `None` — only the run item itself has no parent.
