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
