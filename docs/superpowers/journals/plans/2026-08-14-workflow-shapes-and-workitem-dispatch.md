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

<!-- fr:journal kind=discovery scope=plan id=p3-item-construction-in-tick created=2026-08-15T18:04:36 phase=3 -->
### p3-item-construction-in-tick · discovery · How tick builds phase-unit items — the four derivations Phase 8's build_items must preserve (phase 3)

`_eligible_items(plan, observed, rendered, failures)` in fr_dispatch/__init__.py is the whole item builder today. It is deliberately a private helper on the phase-unit path, NOT the general `build_items` Phase 8 owns; Phase 8 should generalize it rather than add a second builder beside it (two builders is exactly how the id grammar drifts).

Four derivations it makes, each with a reason a later phase should not re-litigate casually:

1. **repo = the ISSUE's repo**, parsed from `phase.tracking_issue`, NOT `plan.meta.target_repo`. Decisive argument: `can_dispatch(item)` replaces `can_dispatch_repo(issue_repo)`, so the adapter's repo gate must be reproducible from `item.repo` alone. On a cross-repo plan the phases of one plan therefore carry DIFFERENT id prefixes — which is correct, they execute in different repos.
2. **spec_slug = Path(plan.spec_path or plan.meta.spec).stem**, mirroring render.py's `_spec_slug` so an item id and the Issue's `spec:` label name the same spec. `PlanMeta.spec` is OPTIONAL, so a plan without one degrades to the sentinel `_no-spec` rather than raising — identity is pure string composition and must stay computable when no artifact exists (this is the same property that lets a run item exist before its spec does). The multi-phase fixture exercises this path.
3. **plan_slug = plan.meta.plan** (not the directory name).
4. **workflow = "fr-goal"** (module constant `_DEFAULT_WORKFLOW`). Justification, not a placeholder: spec 4.A's shipped fr-goal manifest has `implement: for_each: phase`, which is literally what the bridge dispatches today. When Phase 6/7 make the shape real, this constant is the thing that becomes `shape.workflow`.

Payload contract for a phase item (`Mapping[str, object]`, opaque to the framework): `{"plan": Plan, "phase": PhaseDoc, "issue_number": int}`. `tracking` is the Issue URL. Phase 4's adapters get everything the old `dispatch(plan, phase, repo, issue_number)` signature gave them, with no re-parsing: `item.repo` + `item.payload['issue_number']` + `item.payload['plan'|'phase']`. `inputs` carries ArtifactRefs `plan` (repo-relative plan dir) and `spec` (when set); `parent` is `parent_id(id)` = the PLAN level, which is a parent and never a dispatchable unit.

<!-- fr:journal kind=discovery scope=plan id=p3-tests-rewritten-not-ported created=2026-08-15T18:05:07 phase=3 -->
### p3-tests-rewritten-not-ported · discovery · Two tick behaviors were REWRITTEN, not ported — failure-string format and the malformed-URL guard (phase 3)

P3.T2.S3 asks for any test rewritten rather than ported to be surfaced. tests/unit/test_tick_workitem.py is a fresh file (the old tick tests all drive VkRunner and belong to Phase 4), but two behaviors changed shape in the process and review should see them named:

**1. Failure strings are now prefixed with the item id, not `phase <n>`.** Was `f"phase {phase.phase.number}: {e}"`; is `f"{item.id}: {e}"` (e.g. `derio-net/super-fr/<spec>/<plan>/phase/3: boom`). Reasons: (a) the loop is unit-agnostic, so "phase N" is no longer a name it can always produce; (b) the old string did not say WHICH plan the phase belonged to, which on a bridge running many plans made log lines ambiguous — the id does. Consequence for Phase 4: every ported assertion of the form `assert "phase 1" in result.failures[0]` must become an id assertion. `TickResult`'s FIELDS are unchanged; only the human-readable strings inside `failures` moved.

The ONE place `phase <n>` survives is item-construction failure inside `_eligible_items` — there is no item id yet at that point, so the phase number is the only handle.

**2. The malformed-tracking-URL test could not be ported honestly — it was unreachable.** The old loop wrapped `parse_issue_url(tracking)` in a try/except and accumulated `f"phase {n}: {e}"`. That branch cannot be reached through `tick`: `observe()` runs first and calls the same `parse_issue_url` on every tracked phase WITHOUT a guard, so a malformed URL raises out of `tick` before the eligibility loop ever runs. This was true before the cutover too — the guard was defensive, not live. Rather than write a test that appears to pin per-item URL isolation while actually pinning nothing, the guard is kept (it still protects the newly-added id composition, e.g. `item_id` raising on a reserved spec slug) and pinned by calling `_eligible_items` directly with an injected bad URL. Named in the test's docstring so nobody 'fixes' it back into a tick-level test.

**Deliberate narrowing, not a rewrite but worth flagging:** eligibility moved from `FR_READY in labels and FR_SYNCED not in labels` to `state_from_labels(names) == 'queued' and DISPATCH_STAMP.name not in names`. Identical for every realistic label set (at most one lifecycle label is projected). It differs only if an Issue somehow carried BOTH `fr:ready` and a later-lifecycle label: the old code dispatched, the new code does not (`state_from_labels` scans sorted names, so `fr:in-progress` wins over `fr:ready`). The new behavior is the conservative one — refusing to re-dispatch something that projects as claimed.

<!-- fr:journal kind=finding scope=plan id=p3-adapters-red-pending-phase-4 created=2026-08-15T18:05:35 phase=3 state=fixed -->
### p3-adapters-red-pending-phase-4 · finding [fixed] · 25 tests are RED at the end of Phase 3 — every one is an adapter calling tick; Phase 4 closes them (phase 3)

The cutover is hard by design (spec 4.D, plan prose): protocol and loop move in Phase 3, adapters in Phase 4, so the branch is red in between. Recording the exact set so Phase 4's implementer can use it as a checklist and so nobody mistakes it for collateral damage.

Full suite after Phase 3: **1865 passed, 25 failed, 85 skipped** (`uv run pytest -q --no-cov`). Every failure is a test that calls `fr_dispatch.tick` with `VkRunner` or `CncdRunner`; the first v2 method call fails loud at the protocol boundary and `tick` reports it as a preflight blocker, e.g.:

    TickResult(synced=0, errors=1, skipped=1, failures=('<item-id>: runner preflight raised: VkRunner.preflight() takes 1 positional argument but 2 were given',))

unit (13): test_bridge_config.py (2), test_bridge_dedup.py (2), test_bridge_metrics.py (3), test_bridge_slots.py (1), test_vk_bridge_tick.py (5).
integration (12): test_bridge_dispatch_repo_id.py (1), test_bridge_dispatch_response_shape.py (1), test_bridge_e2e.py (2), test_bridge_project_id.py (4), test_bridge_resilience.py (2), test_cncd_stub_server.py (2).

Nothing else regressed: import-direction, cutover, no-issue-create, discover, render/diff/apply, install and tripwire suites are all green. `fr acceptance check`: 74 rows OK. `ruff check packages/ tests/`: clean. `mypy packages/fr-dispatch/src`: clean (the adapter trees are NOT clean — `mypy packages/fr-vk/src packages/fr-cncd/src` will report the stale signatures until Phase 4).

Phase 4's mechanical checklist, from the v2 signatures: `preflight(self, items)`; `can_dispatch_repo(repo)` -> `can_dispatch(item)` reading `item.repo`; `dedup_key` DELETED, so `existing_dispatches()` must return `WorkItem.id`s; `dispatch(item)` unpacking `item.payload['plan'|'phase'|'issue_number']` + `item.repo`; add a `capabilities: frozenset[str]` class attribute (declaration only — negotiation is Phase 5). Note that VK's `existing_dispatches` is the one non-mechanical piece: see the Phase 2 journal entry p2-card-title-still-title-not-key, whose recommendation (have the adapter compute ids from context rather than reconstruct them from card titles) is now concretely satisfiable because `item.payload` carries the plan and phase.

State is `open` because the branch does not go green until Phase 4 lands; flip it to `fixed` there.

<!-- fr:journal kind=discovery scope=plan id=p3-eligibility-single-rule created=2026-08-15T18:06:01 phase=3 -->
### p3-eligibility-single-rule · discovery · Eligibility became ONE predicate shared by tick and discovery — they used to state the same rule twice (phase 3)

Before this phase the same rule was written twice in fr_dispatch/__init__.py: `_plan_projects_ready` (the discovery gate behind `discover_plans`) tested `FR_READY in ri.labels and FR_SYNCED not in ri.labels`, and the tick's eligibility loop tested `FR_READY not in ri.labels or FR_SYNCED in ri.labels` — De Morgan twins that nothing forced to stay in agreement. Drift between them is the deadlock shape #251 already bit us with once (discovery seeing a plan the tick then declines, i.e. a plan re-picked every tick forever, or worse the reverse).

Both now call `_is_dispatchable(rendered_issue)`, the only place in the package that reads lifecycle labels at all: `state_from_labels(names) == 'queued' and DISPATCH_STAMP.name not in names`. `fr.labels.FR_READY` / `FR_SYNCED` are no longer imported by fr_dispatch — the module's queue vocabulary is now entirely Phase 1's `fr.item_state`, which is what makes a non-GitHub tracker adapter (Phase 10 / part c) possible without touching the loop.

Two Phase-1 facts this leans on and later phases must not forget: `state_from_labels` NEVER returns `done` (completion is the Issue's CLOSED state, not a label), so eligibility can only ever be decided among queued/blocked/in_progress/in_review; and `manual` is a routing ATTRIBUTE, not a state — a manual phase's rendered lifecycle label is `manual`, which `state_from_labels` does not recognize, so it returns None and the item is not eligible. That is the correct outcome (manual work is not routable to a runner) but it is reached incidentally, via 'no lifecycle label', rather than by an explicit routability check. Phase 5's capability negotiation should make routability explicit on the item rather than relying on this.

`discover_plans` was otherwise left alone and `tick` still contains no reference to it — asserted directly in test_tick_workitem.py so the coupling Phase 10's tripwire forbids can never appear in the first place.

<!-- fr:journal kind=finding scope=plan id=p3-label-precedence-alphabetical created=2026-08-15T18:13:47 phase=3 state=fixed -->
### p3-label-precedence-alphabetical · finding [fixed] · state_from_labels resolved multi-label sets ALPHABETICALLY — dispatch correctness rested on a naming coincidence (phase 3)

Found in coordinator review of Phase 3, not by self-review. `fr.item_state.state_from_labels` resolved a set carrying several lifecycle labels by scanning `sorted(observed_labels)` and returning the first recognized one. That is label-NAME order, not lifecycle order. It produced the right answer only because of how the GitHub label names happen to sort:

    fr:blocked < fr:in-progress < fr:pr-ready < fr:ready

i.e. `fr:ready` sorts LAST among the four, so in every real co-occurrence the other label won by accident.

Why it mattered as of Phase 3: the tick's eligibility gate became `state_from_labels(...) == 'queued'` (replacing the raw `FR_READY in labels and FR_SYNCED not in labels` check). So a rename — or any lifecycle label sorting after `fr:ready`, e.g. a hypothetical `fr:working` — would make an Issue carrying a stale `fr:ready` alongside an active-work label resolve to `queued`, and the bridge would dispatch **over an agent already working the item**. That is exactly the case the Phase 3 narrowing was introduced to prevent, so the accident sat directly under the new guarantee. Latent, not live: no current label triggers it.

**Fix — explicit state precedence, label names irrelevant.**

    _PRECEDENCE: tuple[ItemState, ...] = ('in_review', 'in_progress', 'blocked', 'queued')

`state_from_labels` now maps every observed label to its state and keeps the best-ranked one (`_PRECEDENCE_RANK`), instead of returning on first hit in sorted order. `sorted()` is gone; resolution no longer depends on iteration order at all.

**The invariant, stated for Phase 10's tracker mapping** (which will have none of these label names): `queued` MUST be last in the precedence order. `queued` is the only state that permits dispatch, so 'any other lifecycle signal is present' must always mean 'do not dispatch'. Ordering among the non-queued states is 'how much real work a duplicate dispatch would destroy': `in_review` (a PR exists) > `in_progress` (an agent holds it) > `blocked` (a dependency says no, but nobody is working). A tracker adapter defines its own vocabulary -> ItemState mapping; it does NOT get to redefine this ordering, because the ordering is about the states, not the names. An unranked state is handled fail-closed (rank -1, outranks everything, so it can only ever make an item look less dispatchable).

Tests added to tests/unit/test_item_state.py (3 RED before the fix, all pass after):
- `test_any_lifecycle_label_beats_a_stale_ready_label` — the three pairwise co-occurrences, parametrized.
- `test_ready_never_wins_over_any_other_lifecycle_label` — the PROPERTY, derived from `_STATE_BY_LABEL_NAME` so a label added tomorrow is covered without editing the test. This is the shape that would have caught the bug.
- `test_precedence_does_not_depend_on_label_names_sorting_favourably` — monkeypatches in `fr:working` (sorts AFTER `fr:ready`) and asserts `in_progress` still wins; fails outright under the old scan.
- `test_resolution_is_independent_of_iteration_order`, `test_every_label_bearing_state_has_a_declared_precedence` (tripwire: every label-bearing state is ranked, and `_PRECEDENCE[-1] == 'queued'`), `test_attributes_and_the_dispatch_stamp_never_perturb_precedence` (re-pins Phase 1's contract that `manual` and `fr:synced` are not states, now against multi-label sets).

Gate after the fix: tests/unit/test_item_state.py + test_render_characterization.py + test_tick_workitem.py = 55 passed; mypy clean over packages/fr/src + packages/fr-dispatch/src (79 files); ruff clean. Full suite 1873 passed / 25 failed — the Phase-4 red set is UNCHANGED (same 25 adapter tests, see p3-adapters-red-pending-phase-4); the +8 is this file's new tests.

<!-- fr:journal kind=discovery scope=plan id=p4-vk-dedup-uses-preflight-cached-items created=2026-08-15T18:41:49 phase=4 -->
### p4-vk-dedup-uses-preflight-cached-items · discovery · VkRunner.existing_dispatches() resolves title -> item id from THIS TICK's own items, cached by preflight(items) — not by inverting the card title (phase 4) (phase 4)

The Phase 2/3 handoff (p2-card-title-still-title-not-key, p3-adapters-red-pending-phase-4) flagged that a VK card title only ever carries (repo, issue_number) — no spec/plan slug, so existing_dispatches() -> set[str] (no-arg per the v2 Runner protocol) cannot literally invert a title into a full item_id(repo, spec_slug, plan_slug, phase=n) string.

Resolution: fr_dispatch.tick always calls runner.preflight(items) BEFORE runner.existing_dispatches() in the same tick (see the per-item dispatch block in fr_dispatch/__init__.py), and every item in one tick's items list belongs to the SAME plan. VkRunner.preflight now stashes self._items_this_tick = items; existing_dispatches() then calls the new fr_vk.dedup.map_titles_to_item_ids(titles, self._items_this_tick), which builds a {(item.repo, item.payload['issue_number']): item.id} lookup from the items themselves (no string composition, no slug guessing) and resolves each existing card title via fr_vk._cardref.parse_card_title -> (tag, repo, issue_number) against that lookup. A title with no matching item this tick (another plan's/phase's card) is simply skipped — it can never collide with item.id in existing for an item that isn't being checked against it.

This is what makes a VK card created BEFORE this cutover (title-only, zero item-id concept ever encoded on it) still dedup correctly on the first post-deploy tick: pinned directly by tests/unit/test_bridge_dedup.py::test_tick_skips_dispatch_when_card_already_exists_and_stamps_fr_synced (a card seeded 'out-of-band' with no item-id metadata at all) and end-to-end by the new tests/integration/test_bridge_dispatch_parity.py (two ready phases each get one card; a SECOND tick against the same runner instance creates zero new cards/workspaces). build_card_title's wire format is untouched — no title-format migration was needed.

<!-- fr:journal kind=discovery scope=plan id=p4-bridge-cli-needed-zero-changes created=2026-08-15T18:42:15 phase=4 -->
### p4-bridge-cli-needed-zero-changes · discovery · bridge_cli.py needed ZERO edits for the v2 tick signature — the minimal-change rule was satisfied by construction, not by restraint (phase 4) (phase 4)

P4.T3.S1 asks to 'update bridge_cli.py for the new tick signature, changing nothing else.' Audited every runner.<method> and VkRunner( call site in packages/fr-vk/src/fr_vk/bridge_cli.py: the ONLY reference is the constructor call , whose signature is unchanged by this phase, plus the opaque  call, whose signature (plan, gh, runner, *, metrics=None) was already fixed by Phase 3. bridge_cli.py never calls runner.preflight/existing_dispatches/can_dispatch/dispatch directly — those are entirely internal to fr_dispatch.tick. So this task's diff on bridge_cli.py is empty; the flock, checkout sync (#286), I9 boundary, metrics wire format + reason aliases, and _seen_plans.json/_done_closed.json are untouched because there was nothing in this file that named the old Runner surface to begin with. This is the Runner-protocol boundary (2026-06-05 split design) working as designed: the daemon frame depends only on Runner-as-a-whole and fr_dispatch.tick's stable outer signature, never on an adapter's internal method shapes.

<!-- fr:journal kind=discovery scope=plan id=p4-tests-rewritten-not-repaired created=2026-08-15T18:43:00 phase=4 -->
### p4-tests-rewritten-not-repaired · discovery · Every red test was repaired by fixing the adapter, except three deliberate rewrites for the new v2 call surface (phase 4) (phase 4)

Per the phase's hard constraint (repair over weaken), every one of the 25 originally-red tests turned green by fixing VkRunner/CncdRunner, not by loosening an assertion — with three named exceptions where the OLD test literally called a v1-only signature that no longer exists, so a straight port was impossible:

1. tests/unit/test_vk_bridge_tick.py::test_tick_mcp_failure_does_not_mark_fr_synced_so_next_tick_retries — was pinned on 'phase {n}' appearing in result.failures[0]; per Phase 3's p3-tests-rewritten-not-ported finding, tick's failure strings are now item-id-prefixed. Rewritten to assert result.failures[0].startswith(f'{expected_id}: ') using fr_dispatch.work_item.item_id to compute the expected id, preserving the original intent (which phase failed is identifiable) exactly, just via the new vocabulary.

2. tests/unit/test_cncd_runner.py — every test called v1-only methods (preflight() with no args, dedup_key(repo, n), can_dispatch_repo(repo)) that Runner v2 deletes/renames outright; there is no way to 'port' a call to a method that no longer exists. Rewritten per P4.T2.S1's own instruction to test v2 shapes directly (preflight(items), can_dispatch(item), capabilities declared, no dedup_key attribute at all) plus two new tests (test_declares_capabilities, test_preflight_ignores_items_content) documenting that cncd's preflight — unlike VK's — never inspects the items it receives (no title-to-id mapping to build; dedup is server-side).

3. tests/integration/test_cncd_stub_server.py's three direct-dispatch tests (test_dispatch_posts_plan_folder_to_v1_ingest, test_dispatch_raises_cncd_error_on_non_2xx, test_dispatch_raises_cncd_error_when_unreachable) called runner.dispatch(plan, phase, repo, issue_number) positionally — the exact signature Runner v2 replaces with dispatch(item). Rewritten via a new local _phase_item() helper that builds the same WorkItem _eligible_items would for that (plan, phase, repo, issue_number) tuple; every existing body-key assertion (kind, schema_version, plan, target_repo, repo, issue_number, phase, source_path, files) is preserved byte-for-byte, with three new assertions added for the id/unit/parent envelope P4.T2.S1 asked build_ingest_payload to gain.

Everything else — test_bridge_config.py, test_bridge_dedup.py, test_bridge_metrics.py, test_bridge_slots.py, and all 6 integration files besides test_cncd_stub_server.py — went green with ZERO test-file changes, because they only ever asserted on tick()'s externally-visible behavior (mcp.calls sequences, gh label state, TickResult counters), which the adapter migration preserved exactly.

<!-- fr:journal kind=finding scope=plan id=p4-acceptance-add-not-idempotent-on-duplicate-id created=2026-08-15T18:43:26 state=fixed -->
### p4-acceptance-add-not-idempotent-on-duplicate-id · finding [fixed] · fr acceptance add is NOT idempotent on a duplicate --id — it hard-errors, contrary to this phase's own instruction (phase 4)

P4.T3.S2 says to update the vk-dispatch-unchanged-after-cutover row with fr acceptance add, '(same id re-adds idempotently)'. Running it against the already-existing row raised 'error: duplicate row id: vk-dispatch-unchanged-after-cutover' and exited 2 — packages/fr/src/fr/commands/acceptance_cmd.py's add_cmd unconditionally checks any(r.id == new_row.id for r in matrix.rows) and refuses; there is no --force/update flag and no separate update subcommand (fr acceptance --help lists only add/check/report/status/summary/init/backfill/digest).

Worked around by editing docs/acceptance/matrix.yaml's existing row directly (adding levels.int, matching the row's exact prior capability/acceptance/origin/status so the diff is additive-only — level ref + notes only), then regenerating the three committed reports with fr acceptance report --deterministic and confirming fr acceptance check (74 rows OK) and fr acceptance report --check (in sync) both pass. This contradicts add_cmd's own docstring ('agents never hand-edit YAML shapes') for the one case — updating an EXISTING row — the CLI has no other path for. Filing as a fixed finding rather than open because the row itself IS correctly updated and verified; the gap is in fr acceptance's CLI surface (no upsert-by-id / no update command), which is a candidate fr issue for whoever next needs to flip a row's level or status without re-authoring it from scratch.

<!-- fr:journal kind=finding scope=plan id=p4-journal-add-cannot-flip-state-on-existing-id created=2026-08-15T18:47:36 state=fixed -->
### p4-journal-add-cannot-flip-state-on-existing-id · finding [fixed] · fr journal add --id <existing> --state fixed silently no-ops — it does NOT flip a finding's state, contrary to the dispatch brief's instruction (phase 4)

The Phase 4 dispatch brief said closing p3-adapters-red-pending-phase-4 is 'fr journal add ... --kind finding --state fixed --id p3-adapters-red-pending-phase-4 re-adds idempotently on the id.' Ran exactly that command: exit 0, no error — but fr journal check --scope plan --slug ... still reported '1 open finding(s): p3-adapters-red-pending-phase-4' afterward. Root cause in packages/fr/src/fr/commands/journal_cmd.py's add_cmd: 'if any(e.id == eid for e in existing): return' — re-adding an existing id is a pure no-op (the new --state/--title/--body are discarded silently, no warning), not an upsert. There is no journal update/edit subcommand (fr journal --help lists only add/render/check).

Worked around the same way as the sibling acceptance-matrix gap (p4-acceptance-add-not-idempotent-on-duplicate-id): hand-edited the entry's HTML comment (state=open -> state=fixed) and its rendered header ([open] -> [fixed]) directly in docs/superpowers/journals/plans/2026-08-14-workflow-shapes-and-workitem-dispatch.md, then verified fr journal check exits 0. No duplicate entry exists — the earlier --state fixed re-add call was confirmed a true no-op (grepped the file for a second p3-adapters-red-pending-phase-4 block; there is only one). Same shape of gap as the acceptance CLI: an --id-keyed 'idempotent add' primitive with no companion update path, so the only way to legitimately mutate an existing entry (flip a finding, correct a typo) is a direct file edit. Candidate fr issue: fr journal needs an update/edit verb, or add needs to special-case state as an allowed in-place change when --id matches and only --state/--body differ.

<!-- fr:journal kind=finding scope=plan id=r-f1 created=2026-08-27T08:29:18 phase=1 state=fixed -->
### r-f1 · finding [fixed] · phase_item_state dropped the manual routing attribute — the neutral seam now returns an ItemDecision (state + routable) (phase 1)

Milestone (phases 1-4) code review, F1. `fr.render.phase_item_state(plan, observed, n) -> ItemState` was the exported tracker-neutral decision, but `_item_state` has no `manual` branch (the pre-extraction `_lifecycle_label` checked `tag == "manual"` BEFORE deps/obs). GitHub stayed correct only because `_lifecycle_label_for_state` re-injected `MANUAL` at projection time from a SECOND read of `PhaseDoc.tag`.

Reproduced before fixing (v2_plan_minimal with `tag: manual`, empty GhState): `phase_item_state(...) == "queued"` while `render()` labelled the same phase `manual`. Why it mattered: dispatch is gated on "is this queued" — `fr_dispatch._is_dispatchable` does exactly that on the label side — so a second tracker (spec §4.G) reading the neutral seam and dispatching on `== "queued"` would hand human-only phases to an agent runner. The projection's re-read is a safety net GitHub has and no other tracker does.

Fix — routability rides WITH the state; `manual` is still not a state (spec §4.C is explicit and no `ItemState` member was added):

- `fr.item_state.ItemDecision(state: ItemState, routable: bool = True)` with a `dispatchable` property (`routable and state == "queued"`) — the single question a dispatcher should ask.
- `render.phase_item_decision(plan, observed, n) -> ItemDecision` REPLACES `phase_item_state` (pre-release, introduced in Phase 1 of this same branch, no external consumer). Replacing rather than adding is deliberate: leaving a state-only accessor beside the safe one leaves the footgun loaded.
- `render._routable(phase)` is now the one place `tag == "manual"` is read as a routing fact; `_item_decision` pairs it with `_item_state`.
- `_lifecycle_label_for_state(phase, state)` -> `_lifecycle_label_for_decision(decision)` — takes the neutral decision and NO PhaseDoc, so `MANUAL` is the projection of `routable=False` rather than a second tag read. `render()`'s tracking-only `elif` branch and the OPEN/CLOSED choice read the decision too.

Spec §4.C gained a paragraph specifying `ItemDecision` and that the GitHub `manual` label is its projection (docs/superpowers/specs/2026-08-14-workflow-shapes-and-workitem-dispatch-design.md).

Tests (RED first, tests/unit/test_item_state.py): `test_item_decision_pairs_a_state_with_routability`, `test_manual_phase_is_queued_but_not_routable` (the reproducer — asserts state stays `queued`, routable/dispatchable False, and render still emits `manual`), `test_an_agentic_queued_phase_is_routable_and_dispatchable`, `test_github_manual_label_is_projected_from_the_decision_not_the_phase_tag`. The four existing seam tests were migrated to `phase_item_decision(...).state == …` — same assertions, new vocabulary. Characterization net (byte-identical GitHub projection) unchanged and green.

For phases 5-11: Phase 5's capability negotiation should consume `ItemDecision.routable`/`dispatchable` rather than inventing a second routability notion; Phase 10's tracker protocol maps a tracker's vocabulary onto BOTH fields.

<!-- fr:journal kind=finding scope=plan id=r-f2 created=2026-08-27T08:29:38 phase=3 state=fixed -->
### r-f2 · finding [fixed] · _plan_inputs shipped a cross-repo spec ref as a repo-relative path in the WRONG repo — now split into (repo, path) (phase 3)

Milestone (phases 1-4) code review, F2. `fr_dispatch._plan_inputs` built `ArtifactRef(kind="spec", repo=plan.meta.target_repo, path=spec_rel)` where `spec_rel = plan.spec_path or plan.meta.spec`. `parser.py:178` deliberately leaves `plan.spec_path is None` when `is_cross_repo_spec(meta.spec)` (it cannot resolve a path in a checkout it does not have), so the fallback shipped the raw `<owner>/<repo>:<path>` notation as `path` — a field whose docstring says repo-relative and normalized — and attributed it to `target_repo`, the one repo the file is NOT in.

Reproduced first: a plan whose `_meta.yaml` declares `spec: other-org/other-repo:docs/superpowers/specs/elsewhere-design.md` produced `ArtifactRef(kind='spec', repo='derio-net/superpowers-for-vk', path='other-org/other-repo:docs/…')`.

Fix: `_plan_inputs` branches on `is_cross_repo_spec` and splits on the first `:` — `repo` becomes the named repo, `path` the repo-relative path inside it. Same precedent as `render.spec_url` (render.py:254) and `repair.py:212`. `fr._urls.is_cross_repo_spec` is now imported by fr_dispatch (fr-only dependency, no new coupling).

Why it is not tidiness: `inputs` refs are COORDINATES. Phase 8 (reachability from inputs) would check the wrong repo for the spec's presence on origin/HEAD; Phase 9 (multi-repo fan-out) would fan out to the wrong repo. `_spec_slug` was checked and is unaffected — `Path("owner/repo:docs/x-design.md").stem` is already `x-design`.

Tests (RED first, tests/unit/test_tick_workitem.py): `test_a_cross_repo_spec_input_names_the_other_repo_and_stays_repo_relative` (pins `plan.spec_path is None` for the cross-repo case as part of the reproduction, asserts repo/path/no-colon, and that the PLAN ref still names the plan's own repo) plus one added assertion to the existing `test_workitem_declares_its_inputs_and_workflow` that a same-repo spec is attributed to `target_repo`.

<!-- fr:journal kind=finding scope=plan id=r-f3 created=2026-08-27T08:30:04 phase=4 state=fixed -->
### r-f3 · finding [fixed] · Runner protocol v2 CHANGED: existing_dispatches(items) — the no-arg form made call ORDER load-bearing and silent (phase 4)

Milestone (phases 1-4) code review, F3. PROTOCOL CHANGE — phases 5-11 must read this.

`VkRunner.existing_dispatches()` answered from `self._items_this_tick`, stashed by `preflight(items)`. `_items_this_tick` defaults to `()`, so any caller that skipped preflight, or reordered the two calls, got an EMPTY dedup snapshot and re-dispatched every item: duplicate VK cards and duplicate workspaces, the exact failure the snapshot exists to prevent. `fr_dispatch.tick` ordered it correctly and is the only caller today, but `protocols.py:70` documented `existing_dispatches` as a standalone no-arg snapshot with no ordering contract at all — a hazard nobody reading the protocol could see.

Fix (the reviewer's preferred option, taken as-is): **pass the items**. The protocol is pre-release — this branch introduces v2 — so widening now is far cheaper than shipping a documented ordering hazard.

    def existing_dispatches(self, items: Sequence[WorkItem]) -> set[str]

Changed: `fr_dispatch/protocols.py` (signature + docstring stating that `items` is the same sequence `preflight` receives, and that returning ids outside `items` is harmless), `fr_dispatch.tick` (`runner.existing_dispatches(items)`), `VkRunner` (`_items_this_tick` and the preflight stash DELETED — `preflight` no longer touches items at all), `CncdRunner` (accepts and ignores them; still honestly empty, server-side idempotence), the `FakeRunner` in tests/unit/test_tick_workitem.py, and `fr_vk.dedup.map_titles_to_item_ids`'s docstring. Spec §4.D's Runner-protocol block was corrected with the new signature and a paragraph on why.

`bridge_cli.py` is byte-unchanged (plan invariant held): it never calls a Runner method directly — only the constructor and `tick`, whose outer signature is untouched.

Tests (RED first): tests/unit/test_bridge_dedup.py `test_existing_dispatches_answers_from_the_items_it_is_given_not_from_preflight` (calls `VkRunner.existing_dispatches([item])` with preflight DELIBERATELY not called, against an out-of-band-seeded card) and `test_existing_dispatches_is_empty_when_no_card_matches_the_given_items` (the negative half); tests/unit/test_tick_workitem.py `test_existing_dispatches_receives_this_tick_s_items` (asserts `"items" in inspect.signature(Runner.existing_dispatches).parameters` AND that tick hands over the same list preflight saw); tests/unit/test_cncd_runner.py's dedup test rewritten to pass items and assert they are ignored.

Whole dispatch/bridge surface re-run after the change: tests/unit test_tick_workitem, test_bridge_dedup, test_bridge_config, test_bridge_metrics, test_bridge_slots, test_vk_bridge_tick, test_cncd_runner + all of tests/integration — green.

Handoff: any runner adapter written from Phase 5 onward (and Phase 10's tracker/source seams, which mirror this protocol's shape) takes `items` here. Do not reintroduce a preflight-cached snapshot.

<!-- fr:journal kind=finding scope=plan id=r-f4 created=2026-08-27T08:30:27 phase=4 state=fixed -->
### r-f4 · finding [fixed] · VK dedup ignored the card title's backend tag — a gl#/gt# card could suppress a GitHub dispatch and still stamp fr:synced (phase 4)

Milestone (phases 1-4) code review, F4. `fr_vk.dedup.map_titles_to_item_ids` discarded `_tag` from `parse_card_title` and keyed its lookup on `(repo, issue_number)` only. Pre-cutover dedup was exact-title equality, tag included; `_cardref`/`TAG_FOR_BACKEND` exist precisely so `gh#`/`gl#`/`gt#` disambiguate hosts (the 2026-07-09 multi-backend design calls that parsing load-bearing, not optional). A `gl#42: [owner/repo]` card would have suppressed the GitHub dispatch of `owner/repo#42` while `tick` still stamped `fr:synced` — so the real dispatch never happens and never retries. Latent (nothing emits non-`gh` titles yet), but it disarmed the guard the tag exists for.

Fix: the lookup is keyed on the FULL `(tag, repo, issue_number)` triple `parse_card_title` returns. The expected tag is derived from `_cardref.DISPATCH_BACKEND` — a new constant in `_cardref` (the leaf module both sides already import) holding the backend the bridge stamps today (`"github"`). `fr_vk.dispatch.build_card_title` now uses that same constant instead of its own hardcoded `"github"`, so producer and dedup cannot drift when a phase's real backend is eventually threaded through.

Second half of the finding — the prefix-anchored widening — DECIDED AND KEPT: `"gh#42: [owner/repo] retry"` now dedups where exact string matching did not. `_cardref`'s regex is prefix-anchored on purpose (an operator annotation or a second bracketed token must not break the parse, matching the pre-consolidation per-file regexes). The coordinate is the identity; trailing text is presentation. Treating an annotated card as a different card would create a duplicate card + workspace for work already on the board — the failure dedup exists to prevent. Pinned by a test either way, including that the widening does NOT extend to the tag.

Tests (RED first, tests/unit/test_bridge_dedup.py): `test_a_card_tagged_for_another_backend_does_not_dedup_a_github_dispatch` (gl#/gt# reject, gh# still resolves), `test_the_expected_tag_is_derived_from_the_title_builder_not_hardcoded` (round-trips `dispatch.build_card_title` through the mapper and iterates TAG_FOR_BACKEND, so a future backend switch fails loudly instead of silently duplicating cards), `test_a_free_text_suffix_on_a_card_title_still_dedups`.

<!-- fr:journal kind=finding scope=plan id=r-f5 created=2026-08-27T08:30:46 phase=2 state=fixed -->
### r-f5 · finding [fixed] · WorkItem.__hash__ was id-only while __eq__ was field-wise — identity is now the id on both sides (phase 2)

Milestone (phases 1-4) code review, F5. `WorkItem.__hash__` returned `hash(self.id)` with a docstring claiming that keeps WorkItem usable as a set/dict key — but `@dataclass(frozen=True)` generated a field-wise `__eq__` comparing every field, including `payload` (which carries a `Plan` and a `PhaseDoc` on the phase path).

Consequence, reproduced first: two items for the same graph position with different payloads hash equal and compare unequal, so `len({a, b}) == 2` and every dict lookup runs a deep `Plan.__eq__` before answering "no". The docstring's claim was false in exactly the case it was written for.

Fix (the reviewer's preferred option): `@dataclass(frozen=True, eq=False)` plus an explicit `__eq__` comparing `self.id == other.id` and returning `NotImplemented` for a non-WorkItem. Identity IS the id — that is the whole premise of Phase 2's `item_id` — so equality and hashing now say the same thing. Module docstring updated: "Two items with the same `id` ARE the same item; `payload` is incidental cargo."

Tests (RED first, tests/unit/test_work_item.py): `test_two_items_with_the_same_id_are_the_same_item_whatever_the_payload` (eq, hash, `len({a,b}) == 1`, dict lookup by the other instance), `test_items_with_different_ids_are_not_equal`, `test_a_work_item_is_not_equal_to_a_non_work_item` (a lookalike object carrying the same `.id`, and the bare id string, must both compare unequal). The pre-existing `test_work_item_equal_fields_are_equal` still passes unchanged.

<!-- fr:journal kind=finding scope=plan id=r-f6 created=2026-08-27T08:31:10 phase=2 state=fixed -->
### r-f6 · finding [fixed] · _id_level misclassified a repo named 'phase'; run_item_id was unvalidated — id grammar is now checked by SHAPE, at construction (phase 2)

Milestone (phases 1-4) code review, F6. Two defects in the same identity grammar.

(a) `_id_level` tested `segments[-2] == "phase"` BEFORE any length check, so `_id_level("owner/phase/my-spec")` — a spec-level id in a repo literally named `phase` — returned `"phase"`. Reproduced: `parent_id` then walked two segments up to `"owner"`, and `WorkItem(id=..., unit="spec")` was rejected outright by the `__post_init__` agreement check.

(b) `run_item_id(repo, run_id)` did no validation at all, so a `run_id` containing `/` composed a 5-segment string `_id_level` later rejects as malformed — far from the caller who could say what went wrong. Phase 7's `fr run start` mints those ids and nothing constrained them.

Fix — classification by SHAPE (length first, marker second), and validation at construction:

- `_id_level`: `len == 6 and segments[4] == "phase"` -> phase; `len == 4` -> `run` if `segments[2] == "run"` else `plan`; `len == 3` -> spec; else raise. `repo` is always `owner/name`, so each level has an exact length.
- `_check_repo(repo)` — exactly two non-empty segments. Every segment count `_id_level` classifies by assumes it.
- `_check_segment(name, value)` — non-empty, no `/`. Applied to `spec_slug`, `plan_slug` (same hazard as `run_id`: an embedded `/` silently changes which level the id parses as) and `run_id`.

On the finding's "nothing reserves `phase`" remark: after the length fix, no reservation is needed and none was added. The `run` reservation exists because the run form and the plan form are BOTH `<owner>/<repo>` plus two segments — a genuine ambiguity. `phase` has no such twin: `owner/phase/<spec>` is 3 segments (spec), `owner/repo/<spec>/phase` is 4 (plan), and the phase form is 6. A reservation would forbid a legal repo/slug name for no collision. Recorded here so it is not re-litigated as an oversight.

Tests (RED first, tests/unit/test_work_item.py): `test_a_repo_literally_named_phase_is_not_a_phase_level_id` (level, `parent_id is None`, and the `unit="spec"` item now constructible), `test_the_phase_marker_still_classifies_a_real_phase_id_in_such_a_repo`, `test_id_level_rejects_ids_that_are_too_long_to_be_any_level`, `test_run_item_id_rejects_a_run_id_containing_a_slash`, `test_run_item_id_rejects_an_empty_run_id`, `test_item_id_rejects_slugs_that_would_forge_extra_segments`, `test_identity_functions_reject_a_repo_that_is_not_owner_slash_name`.

Handoff for Phase 7/8: `run_item_id` now RAISES on a `run_id` containing `/` or empty. `fr run start`'s run-id shape must be a single path segment (the spec's example `2026-08-14-ticket-polling` already is).

<!-- fr:journal kind=finding scope=plan id=r-f7 created=2026-08-27T08:31:33 phase=3 state=fixed -->
### r-f7 · finding [fixed] · Two tick failure strings still used the old 'phase N:' prefix — every accumulated failure now names the item (and therefore the plan) (phase 3)

Milestone (phases 1-4) code review, F7. Every accumulator in the dispatch loop emits `f"{item.id}: …"` — deliberately, because the id also names the plan, which matters on a bridge running many plans. Two did not: `_eligible_items`'s own `except` (`f"phase {n}: {e}"`) and tick's tracking-issue writeback (`f"phase {phase_n}: writeback failed: {e}"`). So of the failure classes an operator reads, only some identified the plan, and the two were formatted differently.

The Phase 3 journal (p3-tests-rewritten-not-ported) justified keeping `phase <n>` on the grounds that there is no item id yet at that point. True — but a REF can still be composed from the same segments.

Fix: new `_phase_item_ref(plan, phase_number, tracking=None)` in fr_dispatch, used by both sites. It composes `<repo>/<spec-slug>/<plan-slug>/phase/<n>` segment-wise and deliberately does NOT call `item_id`: this runs on the failure path and `item_id` raising is one of the things that lands there, so id composition must never be the reason a failure string cannot be produced. `repo` prefers the issue URL's repo (cross-repo plans dispatch phases in different repos) and falls back to `target_repo` when the URL is absent or malformed — a malformed URL being, typically, the failure itself.

Tests: the existing `test_a_phase_whose_item_cannot_be_built_fails_only_itself` assertion was updated from `startswith("phase 1: ")` to the item ref (plus `not startswith("phase ")`) — the format change IS the fix, not a weakened assertion. New `test_a_writeback_failure_is_named_by_item_ref_like_every_other_failure` monkeypatches `apply` to report a created issue and `plan_ops.set_tracking_issue` to raise; it covers a path that had NO test before (and that `skip_issue_create=True` makes unreachable through a normal tick — the guard stays because `apply` is not the only possible source of `created_issues`).

<!-- fr:journal kind=finding scope=plan id=r-f8-version-bump created=2026-08-27T08:33:17 phase=4 state=refuted -->
### r-f8-version-bump · finding [refuted] · REFUTED: milestone review flagged the missing 3.19.0 version bump (phase 4)

The reviewer correctly cites AGENTS.md (any PR changing packages/*/src/** MUST bump before merge) and correctly observes pyproject.toml still reads 3.19.0 after four phases rewrote the Runner protocol. Refuted as a DEFECT, not as a rule: the bump is deliberately Phase 11's (task 3 step 2, bump-version.py major), because bumping mid-run would trip the plan's own fr_version gate for every later phase - which is why _meta.yaml carries the widened >=3.19.0,<5.0.0. The rule binds at merge and this branch cannot merge without Phase 11. Note CI version-sync only checks lockstep across manifests, so nothing would catch a genuinely missing bump; the guard is the plan plus fr-goal step 8 verification.

<!-- fr:journal kind=discovery scope=plan id=p5-required-capabilities-is-a-tick-parameter created=2026-08-27T08:46:48 phase=5 -->
### p5-required-capabilities-is-a-tick-parameter · discovery · Phase 6 seam: tick(..., required_capabilities=frozenset) is the manifest hand-off, not a WorkItem field (phase 5)

Considered two seams per the dispatch brief: a field on WorkItem, or a parameter to tick. Chose the parameter — required_capabilities: frozenset[str] = frozenset(), keyword-only, empty by default. Two reasons a WorkItem field was rejected: (1) the shipped fr-goal manifest requires [git, tests, scm], but tests/unit/test_tick_workitem.py's FakeRunner declares capabilities = {git, scm} (no tests) — if _eligible_items had started stamping that requirement onto every phase item, all 25+ pre-existing tick tests would have started failing on a capability refusal that Phase 5 did not intend to introduce. A tick-wide parameter that defaults to empty cannot retroactively change any existing caller's behavior; a field with a real default baked into the builder can. (2) today there is exactly one workflow per tick (_DEFAULT_WORKFLOW = fr-goal, hardcoded), so the requirement is tick-wide, not yet per-item-varying — a parameter says that honestly. Phase 6, once shape manifests resolve a real requires: list, calls tick(..., required_capabilities=frozenset(shape.requires)) at the one call site that already resolves the shape (or threads it down to wherever _eligible_items or its Phase 6 replacement builds items, if a future phase needs per-item capability sets within one tick — the parameter can become a per-item field later without breaking this one, since the check function (_capability_blocker in fr_dispatch/__init__.py) takes items and a runner and a required set as three separate arguments already, not something baked into WorkItem's shape). bridge_cli.py needed no changes because tick's new keyword-only parameter has a default (its one existing call site: tick(plan, gh, runner, metrics=...)).

<!-- fr:journal kind=discovery scope=plan id=p5-capability-blocker-reuses-preflight-path created=2026-08-27T08:46:52 phase=5 -->
### p5-capability-blocker-reuses-preflight-path · discovery · Capability refusal reuses the exact preflight-blocker code path in tick, not a parallel one (phase 5)

Spec 4.F says preflight refuses the mismatch 'using the method that already exists for exactly this purpose' and the dispatch brief forbids inventing a second refusal mechanism, flagging that Phase 10's tracker-state refusals need to route through the same path. Implementation: a new _capability_blocker(items, runner, required_capabilities) -> str | None sits directly above tick's existing blocker = runner.preflight(items) call. tick now computes blocker = _capability_blocker(...) first; only calls runner.preflight when that returned None. Both assign the SAME local blocker variable, so the unchanged downstream code (per-item failure accumulation with m.push_failure_total(reason="preflight"), synced=0, skipped=len(items), early return before the dispatch loop) handles both refusal kinds identically — there is no branch anywhere that treats a capability refusal differently from a runner-config refusal except the message text and that runner.preflight is never called for the former. This is what makes the ordering requirement (capability check before runner.preflight, so the failure reads as a capability problem not a config one) true by construction rather than by convention: runner.preflight simply never executes when _capability_blocker returns non-None, confirmed by asserting runner.preflight_items is None in tests/unit/test_capabilities.py. Handoff for Phase 10: a tracker-state refusal should be a third function with the same str | None -> blocker-assignment shape, checked in the same short-circuit chain (capability blocker, then tracker blocker, then runner.preflight) — not a second call to the per-item failure loop, since that loop's shape (build blocker once, apply to every item, return early) is the reusable part, not any single check's logic.

<!-- fr:journal kind=discovery scope=plan id=p6-final-schema created=2026-08-27T09:07:25 phase=6 -->
### p6-final-schema · discovery · Manifest schema landed: workflow/schema/description/unit/requires/steps, Step with id/kind/run|skill|agent/needs/emits/gate/tier/for_each (phase 6)

fr.workflow.model.WorkflowManifest (pydantic, frozen=True, extra=forbid) parses the spec §4.A example verbatim (tests/unit/test_workflow_model.py::test_parses_the_spec_example_manifest). Fields: workflow: str; schema (wire key) -> schema_version: Literal[1] via Field(alias="schema") (BaseModel.schema is a deprecated pydantic v1 method name, so the Python attribute is schema_version, same reason PlanMeta.schema_version exists for NN.yaml); description: str = ""; unit: Literal["run","phase","spec"]; requires: tuple[str,...] = (); steps: tuple[Step,...] = (). Step: id: str; kind: Literal["cli","agent"]; run/skill/agent: str|None; needs/emits: tuple[str,...] = (); gate: Literal["operator"]|None; tier: str|None (free-form — "from_phase" in the example, resolved later via fr models); for_each: Literal["phase"]|None.

parse_manifest(text) -> WorkflowManifest is the ONE entry point, raising WorkflowError (never a raw yaml/pydantic exception) for: invalid YAML, a non-mapping top level, schema != 1 (checked BEFORE generic pydantic validation so the message names the supported version explicitly rather than reading as a generic literal-mismatch), and any other schema violation (unknown top-level/step key via extra=forbid, missing required field, wrong type).

Capability validation is deliberately NOT in the pydantic model: requires is typed as a bare tuple[str,...] at parse time. fr.capabilities.CAPABILITIES (moved from fr_dispatch.capabilities — see p6-capabilities-moved-to-fr) is checked only in fr.workflow.check.check_workflow, per the dispatch brief's instruction, so a typo is a validation error at fr workflow check time, not a parse-time surprise baked into the schema.

Downstream: Phase 7's run-state cursor and Phase 8's decomposition units both read WorkflowManifest.unit/steps/requires directly; Step.for_each and Step.needs/emits are the fields Phase 8's build_items and Phase 7's step-advance loop consume.

<!-- fr:journal kind=discovery scope=plan id=p6-capabilities-moved-to-fr created=2026-08-27T09:07:40 phase=6 -->
### p6-capabilities-moved-to-fr · discovery · CAPABILITIES relocated fr_dispatch -> fr — fr_dispatch cannot be a dependency of fr, and check_workflow needs the closed set (phase 6)

Phase 5 built fr_dispatch.capabilities.CAPABILITIES anticipating Phase 6 would wire a manifest's requires: through tick's required_capabilities parameter, but did not anticipate that fr.workflow.check.check_workflow (the module validating requires: against the closed set, per the dispatch brief's explicit instruction) lives in the fr package, and fr-dispatch's pyproject.toml declares dependencies = ["fr"] — fr never depends on fr_dispatch, so fr.workflow.check could not import fr_dispatch.capabilities without a cycle.

Fix: moved the canonical CAPABILITIES/missing_capabilities definitions to packages/fr/src/fr/capabilities.py (byte-identical content). packages/fr-dispatch/src/fr_dispatch/capabilities.py is now a two-line re-export (`from fr.capabilities import CAPABILITIES, missing_capabilities`) so every existing `from fr_dispatch.capabilities import ...` caller — including fr_dispatch._capability_blocker and tests/unit/test_capabilities.py's equality assertion `CAPABILITIES == frozenset({...})` — keeps working unchanged (equality, not identity, is what's asserted). tests/unit/test_capabilities.py (Phase 5's) still passes 10/10 unmodified.

This is not a tick/adapter/bridge_cli.py edit (excluded by this phase's hard constraint) — capabilities.py is a small pure module neither the tick loop, an adapter, nor the bridge daemon.

Handoff: any future capability-adjacent code should treat fr.capabilities as canonical; fr_dispatch.capabilities is a compatibility shim, not a second source of truth.

<!-- fr:journal kind=discovery scope=plan id=p6-shipped-root-design created=2026-08-27T09:07:56 phase=6 -->
### p6-shipped-root-design · discovery · resolve_workflow's 'shipped' side is an injectable shipped_root (marketplace-clone default), not repo_root-relative — a design call beyond the phase brief's literal 2-arg description (phase 6)

The phase brief's task text describes resolve_workflow(name, repo_root) resolving 'docs/superpowers/workflows/<name>.yaml' (repo) over 'plugins/super-fr/workflows/<name>.yaml' (shipped) with only one path parameter named. Read completely literally that would make BOTH paths relative to the same repo_root — which only works inside the super-fr monorepo itself (where plugins/super-fr/workflows/ genuinely exists at the repo root, per the CI tripwire). It cannot work for an actual consumer repo: a repo that merely installs the super-fr Claude Code plugin never checks out plugins/super-fr/workflows/ into its own tree, so repo_root-relative shipped resolution would silently and permanently find nothing outside this one repo.

Design taken: resolve_workflow(name, repo_root, *, shipped_root: Path | None = None). shipped_root defaults to default_shipped_workflows_dir(), which follows the SAME precedent every other 'shipped resource' lookup in this package already uses (fr.plan_validator_wrapper's _DELEGATE_PATHS, fr.isolation.local's validator-wrapper repair message): ~/.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/workflows/, overridable via $FR_SHIPPED_WORKFLOWS_DIR (tests use this exclusively — none touch $HOME/.claude). This makes shape resolution actually usable from a real consumer repo the day fr-goal wires onto it (Phase 11), at the cost of diverging from the brief's literal single-repo_root-arg phrasing.

Spec correction owed: §4.A's resolution-order block shows both paths as bare relative strings with no runtime-location note, exactly the ambiguity that produced this decision. Recommend a parenthetical after the `plugins/super-fr/workflows/<name>.yaml` line: '(the plugin's installed location, e.g. ~/.claude/plugins/marketplaces/derio-net--super-fr/... on Claude Code — not the consumer repo's own checkout)'.

<!-- fr:journal kind=discovery scope=plan id=p6-check-workflow-scope-and-location created=2026-08-27T09:08:13 phase=6 -->
### p6-check-workflow-scope-and-location · discovery · check_workflow lives in fr/workflow/check.py, not literally inside commands/workflow_cmd.py; unknown-schema is tested at the CLI layer, not via check_workflow(manifest) directly (phase 6)

Two deliberate departures from the step text's literal phrasing, both to keep the module boundaries this repo already uses (business logic in fr/*, thin typer wrapper in commands/*_cmd.py — see fr.repair/repair_cmd.py, fr.models/models_cmd.py):

1. P6.T3.S2 says 'implement the checks plus the fr workflow check command ... in packages/fr/src/fr/commands/workflow_cmd.py'. check_workflow (and its five private helpers: duplicate ids, dangling needs, cycle detection, unknown capabilities, for_each/unit conflicts) lives in fr/workflow/check.py instead, imported by workflow_cmd.py, which stays a thin typer wrapper (resolve -> check -> print/exit). This is what lets tests/unit/test_workflow_check.py call check_workflow(manifest) directly as a pure function (no CliRunner needed for 10 of its 14 tests), matching how the RED step itself was written ('check_workflow(manifest) reports...').

2. check_workflow(manifest: WorkflowManifest) takes an ALREADY-PARSED manifest, so it can never structurally receive an invalid schema — fr.workflow.model.parse_manifest refuses to construct a WorkflowManifest with schema != 1 before check_workflow ever runs. The RED step's list of things check_workflow reports ('duplicate step ids; ...; an unknown schema; ...') therefore spans TWO layers: schema-level (parse_manifest, WorkflowError) and semantic (check_workflow, list[str]). fr workflow check (the CLI) is the place both surface identically as an exit-1 report — pinned by test_cli_exits_one_on_an_unsupported_schema_version, which asserts exit 1 and 'schema' in the output, rather than a unit test calling check_workflow() with a schema-2 manifest object (which cannot exist). The four other checks (duplicate ids, dangling needs, cycle, unknown capability) plus the for_each/unit conflict ARE exercised directly through check_workflow(manifest) as the step literally asks.

<!-- fr:journal kind=discovery scope=plan id=p6-shipped-stub-landed created=2026-08-27T09:08:30 phase=6 -->
### p6-shipped-stub-landed · discovery · Took the non-vacuous-tripwire path: tripwire requires >=1 manifest, went RED as expected, landed plugins/super-fr/workflows/fr-goal.yaml as a minimal valid stub for Phase 11 to flesh out (phase 6)

Per the dispatch brief's explicit steer (avoid a tripwire that passes vacuously over an empty glob), tests/unit/test_tripwire_shipped_workflows.py::test_at_least_one_shipped_workflow_manifest_exists asserts SHIPPED_WORKFLOWS_DIR.glob('*.yaml') is non-empty. Confirmed RED before adding the stub (AssertionError: no manifests under .../plugins/super-fr/workflows).

Landed plugins/super-fr/workflows/fr-goal.yaml as a genuinely minimal but VALID stub: schema: 1, unit: run, requires: [git, scm], description marked STUB, a single cli step (isolate: fr isolation up --branch {{ run.branch }} — the spec §4.A example's own first step, so at least that one line is already real). A top-of-file comment states plainly it is a stub, names Phase 11 as the owner of the real content (the full isolate -> brainstorm -> spec-review -> plan -> plan-review -> implement -> review -> deliver pipeline), and notes nothing consumes this manifest yet (fr run doesn't exist until Phase 7).

Both tripwire tests pass: existence (non-vacuous) and test_every_shipped_workflow_manifest_passes_check_workflow (the stub is check_workflow-clean: no dangling needs, no cycle, git/scm are both valid capabilities, no for_each/unit conflict).

Handoff for Phase 11: replace plugins/super-fr/workflows/fr-goal.yaml's body with the full spec §4.A example (this phase's tests/unit/test_workflow_model.py::FULL_MANIFEST is that exact text already, ready to copy) and delete the STUB framing comment; the tripwire test file needs NO changes when that happens — it validates whatever is on disk.

<!-- fr:journal kind=finding scope=plan id=p6-default-shipped-root-untested created=2026-08-27T09:17:26 phase=6 state=fixed -->
### p6-default-shipped-root-untested · finding [fixed] · workflow-repo-authored's ci flip rested on an uncovered default-shipped-root path — fixed with 3 new tests (phase 6)

Coordinator review after Phase 6's initial pass: every resolve_workflow test (test_workflow_resolve.py) injected shipped_root=tmp_path/"shipped" explicitly. default_shipped_workflows_dir()'s two real branches — the $FR_SHIPPED_WORKFLOWS_DIR override and the $HOME-relative marketplace fallback — were exercised only partially (the override branch had one test; the fallback branch had NONE), and nothing proved resolve_workflow(name, repo_root) called WITHOUT shipped_root actually reaches that default at all.

This mattered specifically because workflow-repo-authored had already been flipped not-implemented -> ci, and its acceptance text ("a consumer repo defines its own workflow shape, or overrides a shipped one of the same name, without modifying the plugin") is a claim about a REAL consumer repo — which runs entirely through the untested default, never through an injected shipped_root. A wrong marketplace path degrades silently to "unknown workflow shape" on every lookup rather than failing loudly, and this repo has already survived one marketplace rename (AGENTS.md "Marketplace names are `<org>--<repo>`"), making a retyped/drifted path a real, not hypothetical, risk.

Fix: three additions.
1. `fr.workflow.resolve.MARKETPLACE_ROOT` made public (was `_MARKETPLACE_ROOT`) so tests build the expected default path by composing the SAME constant `default_shipped_workflows_dir()` uses, rather than retyping the marketplace string a second time — one rename, one place to fix.
2. `test_default_shipped_workflows_dir_falls_back_to_the_marketplace_clone_path` — unsets $FR_SHIPPED_WORKFLOWS_DIR, sets $HOME to a tmp dir, asserts the result equals `tmp_path / MARKETPLACE_ROOT / SHIPPED_WORKFLOWS_REL` AND spells out the literal `.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/workflows` suffix, so a drift between the constant's value and the documented convention (plan_validator_wrapper.py, isolation/local.py) still fails loud even if only the constant were wrong.
3. `test_resolve_workflow_without_shipped_root_consults_the_default` — the wiring test: calls resolve_workflow("fr-goal", repo_root) with NO shipped_root kwarg, pointing $FR_SHIPPED_WORKFLOWS_DIR at a tmp dir containing a manifest, and asserts it resolves — proving the production call site actually reaches default_shipped_workflows_dir(), not just that the helper alone computes the right value in isolation.

tests/unit/test_workflow_resolve.py: 6 -> 8 tests, all passing. workflow-repo-authored's matrix notes updated to record why it stayed at `ci` post-fix rather than being reverted. Full re-verification: ruff check/format clean, mypy clean (78 files), full suite 1972 passed / 0 failed / 85 skipped (unchanged from the pre-fix baseline — this was pure test-coverage closure, no production behavior changed beyond the constant rename).

Spec §4.A was independently amended by the coordinator (the runtime-location paragraph + the "must be covered by a test" requirement) — not duplicated here.

<!-- fr:journal kind=discovery scope=plan id=p7-run-id-derivation created=2026-08-27T09:38:01 phase=7 -->
### p7-run-id-derivation · discovery · fr run start derives a slash-free run id (date + sanitized branch), satisfying run_item_id's single-segment constraint (phase 7)

derive_run_id(branch) in fr/commands/run_cmd.py: f"{today.isoformat()}-{branch.strip('/').replace('/', '-')}" — every '/' in the branch (e.g. feat/ticket-polling) is flattened to '-', so the result is always a single path segment, which is exactly what fr_dispatch.work_item.run_item_id requires (Phase 2 review fix r-f6: run_item_id raises on an empty run_id or one containing '/'). Pinned directly: test_start_run_id_derivation_yields_a_single_path_segment starts a run with --branch feat/ticket-polling and no --run-id, asserts the written run file's stem has no '/', and round-trips it through run_item_id('derio-net/super-fr', run_id) to confirm it composes a well-formed run-level item id — the interaction the Phase 2 handoff asked this phase to test, not just the derivation in isolation. --run-id is exposed as an override for callers (and every other test) that want a deterministic id instead of a date-stamped one. The date prefix is a deliberate echo of spec 4.B's own example run id (2026-08-14-ticket-polling), which reads exactly like a plan slug — see p7-run-archival-slug-convention for why that resemblance is load-bearing for archival, not just cosmetic.

<!-- fr:journal kind=discovery scope=plan id=p7-agent-step-brief-shape created=2026-08-27T09:38:04 phase=7 -->
### p7-agent-step-brief-shape · discovery · The exact agent-step dispatch brief fr run advance emits — Phase 11's fr-goal wiring must produce/consume this same shape (phase 7)

_build_brief(step, state) in fr/commands/run_cmd.py returns a flat JSON-serializable dict, printed via json.dumps(brief, sort_keys=True) on stdout after a one-line 'STEP_ID: dispatch brief' banner: {"run": <run id>, "workflow": <name@schema>, "step": <step id>, "skill": <Step.skill or null>, "agent": <Step.agent or null>, "needs": [<artifact names Step.needs declares>], "emits": [<artifact names Step.emits declares>], "tier": <Step.tier or null>}. It is deliberately exhaustive of every agent-relevant Step field rather than a subset convenient for this phase's tests, because Phase 11 (fr-goal wiring) is the real consumer and nothing here anticipates what it will and won't need. advance marks the step 'running' (state + at) the first time it is emitted and does NOT execute anything — pinned by test_advance_agent_step_never_invokes_a_model, which monkeypatches run_cmd.subprocess.run to raise AssertionError and asserts advance still exits 0. Calling advance again while the step is still 'running' re-emits the identical brief without re-touching the record (test_advance_agent_step_brief_is_re_emitted_idempotently_while_running) — there is no 'fr run complete-step' verb in this phase; something outside fr run (the harness, after the agent finishes) is what will eventually need to move the cursor past an agent step, and that mechanism is NOT built here. Flagging for whoever builds it: right now an agent step's cursor only ever advances via a human/tool editing steps[id].state to 'done' by hand in the YAML (the same escape hatch that makes a gate: operator step resumable, see p7-run-state-notes-on-spec) — that is a real gap this phase leaves open, not an oversight to silently paper over.

<!-- fr:journal kind=discovery scope=plan id=p7-run-archival-slug-convention created=2026-08-27T09:38:07 phase=7 -->
### p7-run-archival-slug-convention · discovery · Spec 4.B never states how a run's archival ties to its plan's — inferred run-id == plan-slug convention, flagged for spec review (phase 7)

P7.T2.S3 asks archive.py to move a run file to implemented/runs/ 'alongside its plan', but neither spec 4.B nor 4.E says how a run id and the plan it eventually creates relate to each other well enough for archive_plan_dir (keyed only on a plan directory's name) to find the matching run file. Spec 4.B's own example run id, 2026-08-14-ticket-polling, is visually indistinguishable from a plan slug (compare this very plan's own dir name, 2026-08-14-workflow-shapes-and-workitem-dispatch) — the shape spec 4.A's example implement step suggests (isolate -> brainstorm -> plan, where 'plan' is a kind: agent step running super-fr:fr-plan) most naturally produces a plan directory named after the run it belongs to. Given no explicit rule, I took run_id == plan_dir.name as the archival key: _archive_run(repo_root, plan_dir.name) in archive.py, called from archive_plan_dir right after _archive_journal, no-op when no matching run file exists (back-compat with every non-run-unit plan, i.e. every plan today) or when the destination already holds one (a re-run) — same shape as _archive_journal's slug-keyed lookup. Tests: test_archive_moves_run_state_file_alongside_its_plan (a docs/superpowers/runs/<plan-slug>.yaml file moves to implemented/runs/<plan-slug>.yaml in the same archive operation) and test_archive_is_a_no_op_when_no_run_file_exists (no implemented/runs/ dir materializes for an ordinary plan). This is an INFERENCE, not a spec-stated rule — if fr-goal's Phase 11 wiring gives the plan step a different slug convention (e.g. plan slug derived from the goal description rather than the run id), this archival path silently no-ops instead of erroring, which is the safe failure direction but should be reconciled with the spec once Phase 11 makes the real answer concrete. Do not edit the spec directly per this phase's brief; flagging here for the coordinator.

<!-- fr:journal kind=finding scope=plan id=p7-agent-step-cannot-complete created=2026-08-27T09:49:50 phase=7 state=fixed -->
### p7-agent-step-cannot-complete · finding [fixed] · A run could never leave an agent step — fr run resolve added (spec §4.B amended, authorized scope addition) (phase 7)

Milestone review, deferred not caught by self-review: the original 4-command CLI (start/status/advance/check) let advance mark an agent step 'running' and correctly never execute it, but nothing could ever move that step to 'done' or 'failed' -- the cursor wedges there permanently. In the shipped fr-goal shape nearly every step is kind: agent, and the FIRST one is step 2 (brainstorm), so a real run stalls almost immediately; Phase 11 cannot wire fr-goal onto this CLI as it stood. My original journal entry (p7-agent-step-brief-shape) flagged the gap but mischaracterized it as presumably Phase 11's job -- it is not: Phase 11 wires a shape onto this CLI, it does not extend the CLI. Phase 7 owns the run surface, so the fix belongs here.\n\nFix: fr run resolve <run-id> --step <id> --state done|failed [--emitted name=path ...]. Refuses a step that is not kind: agent (points at advance instead, with a clear message) and refuses a step that is not currently running (with a clear message naming its actual state) -- both tested. On done it advances the cursor and records any --emitted artifacts into the step's record (the same shape brainstorm/plan steps use in spec 4.B's own example); on failed it records the outcome and leaves the cursor exactly where advance's cli-failure path already leaves it. The done/failed cursor-advance logic is NOT forked: both advance's cli branch and resolve now call one shared _complete_step(state, manifest, step_id, outcome, ...) in fr/commands/run_cmd.py, so there is exactly one place the asymmetry (advance-on-done, stay-put-on-failed) is implemented. resolve is equally non-executing -- pinned by monkeypatching subprocess.run to raise if called, same as advance's agent-step test.\n\nThis is a deliberate scope addition beyond 07.yaml's authored task list, authorized by the coordinator's review (spec 4.B was amended to make resolve normative, not left to my own judgment). Tests added to tests/unit/test_run_cli.py: test_resolve_done_completes_the_step_and_advances_the_cursor (includes proving the run is not wedged -- advance executes the NEXT step normally afterward), test_resolve_failed_leaves_the_cursor_put_same_as_advance, test_resolve_refuses_a_step_that_is_not_running, test_resolve_refuses_a_cli_step_pointing_at_advance_instead, test_resolve_never_invokes_a_model_either. 17/17 test_run_cli.py tests pass; full suite 2003 passed / 0 failed / 85 skipped.

<!-- fr:journal kind=finding scope=plan id=p7-run-archival-never-matched created=2026-08-27T09:49:53 phase=7 state=fixed -->
### p7-run-archival-never-matched · finding [fixed] · Run archival was keyed on a name convention that real run/plan ids never satisfy -- silent permanent no-op, fixed by matching on the recorded emitted.plan artifact (spec §4.B amended, authorized) (phase 7)

Milestone review, not caught by self-review or by my own p7-run-archival-slug-convention journal entry (which correctly flagged the assumption as unenforced but did not go on to verify it against derive_run_id, which was sitting in the same PR and actively contradicts it). _archive_run originally keyed its implemented/runs/ lookup on plan_dir.name, on the premise that a unit: run shape's plan step creates the plan under the run's own id. But fr.commands.run_cmd.derive_run_id produces <date>-<flattened-branch> -- e.g. this very branch would derive 2026-08-24-feat-fr-goal-composable-workflow against a plan dir slug like 2026-08-14-workflow-shapes-and-workitem-dispatch (different date, plus a feat- prefix a plan slug never carries). The two cannot match in real use, so the safe-looking no-op (no matching run file -> skip) was in fact a PERMANENT no-op: every run file would accumulate under docs/superpowers/runs/ forever, with nothing ever surfacing that archival silently never fired for it.\n\nRoot cause of why this passed review-by-test the first time: my own test fixture (test_archive_moves_run_state_file_alongside_its_plan) constructed the run file's name to EQUAL the plan slug, so it exercised exactly the coincidence the bug depended on and proved nothing about real usage. That is the explicit lesson the coordinator's review called out and I am recording it verbatim: a name-equality fixture hides this class of bug rather than catching it.\n\nFix: archival now matches by DATA, not name. _find_run_for_plan(repo_root, plan_rel) scans docs/superpowers/runs/*.yaml, parses each with parse_run_state (skipping any that fail to parse -- a malformed run file is not archival's problem), and returns the run whose recorded emitted.plan (on ANY step, not just one literally named 'plan') equals the plan's repo-relative path -- data every run file already carries per spec 4.B's own example (plan: {state: done, emitted: {plan: docs/superpowers/plans/2026-08-14-...}}). archive_plan_dir now calls _archive_run(repo_root, src_rel) with the plan's actual pre-move repo-relative path rather than plan_dir.name.\n\nTests (RED first, tests/unit/test_archive_cmd.py): rewrote test_archive_moves_run_state_file_alongside_its_plan to use a DELIBERATELY unrelated run id (2026-08-24-feat-fr-goal-composable-workflow) and plan slug (2026-08-20-goal-output) -- confirmed RED against the old name-keyed code (run file was left in place, not moved) before the fix, green after; added test_archive_does_not_move_an_unrelated_run_file_of_the_same_name, which seeds a run file that DOES share the plan's slug but carries no emitted.plan pointing at it, and asserts it is untouched -- proof the lookup is data-keyed, not name-keyed, in both directions. test_archive_is_a_no_op_when_no_run_file_exists (back-compat, no run file at all) still passes unchanged. Full tests/unit -k archive: 89 passed; full suite 2003 passed / 0 failed / 85 skipped; mypy clean over packages/fr/src.
