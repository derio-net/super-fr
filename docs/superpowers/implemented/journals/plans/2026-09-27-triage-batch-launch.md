# Journal: 2026-09-27-triage-batch-launch

<!-- fr:journal kind=decision scope=plan id=p-two-phases created=2026-09-27T09:13:53 -->
### p-two-phases · decision · Two agentic phases, one per issue,

Both issues edit render_brief; #687's debug brief is written against the brief #704 leaves behind, so #704 goes first. Both standard tier (~260 and ~320 lines). No manual phase: the herdr run-unit contract is unchanged and CI-pinned, so no live verification is owed.

<!-- fr:journal kind=discovery scope=plan id=p1-acceptance-record-refused created=2026-09-27T09:29:11 phase=1 -->
### p1-acceptance-record-refused · discovery · implement-phase's emits don't allow an `acceptance` record section (phase 1)

The shipped fr-goal manifest's `implement-phase` step emits only `[journal:plan, plan:ticks]`, so `allowed_sections` (fr.record.model) never includes `acceptance` for it — a record naming that section would be refused by `fr run resolve --record` (RecordRefusedError, "section(s) acceptance not allowed"). The step-record template's own comment names the fallback ("or use `fr acceptance set-status` ... and commit the matrix + reports"), so triage-batch-session-model was moved to `ci` that way instead, in its own commit (cc6cacb9a6903e2c5d856c0d6cc46b98a00bedef), rather than through this record's `acceptance:` field.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-27T09:29:11 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

render_brief lost only the one subagent-model line and its param; the function was already minimal and needed no further cleanup.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-09-27T09:29:11 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the checkout-before-resolve reorder and the new _orchestrator helper are the smallest shape that carries the precedence; nothing else in triage_batch_cmd.py touches launch resolution.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-09-27T09:32:25 phase=1 -->
### review-phase-1 · review · phase 1 code review (#704): no findings (phase 1)

Independent reviewer (standard tier, claude-sonnet-5) read every file in phase 1's files list against spec §A/§D and 01.yaml. Verified: resolve_launch precedence and model_source agree in every combination incl. empty-string model; orchestrator never consulted without a harness; refusal hint only when model alone is missing; _orchestrator builds over fr.models.resolved_config with no second precedence; REPO_MODELS_REL has one home; tests are behavioural and config-isolated (HOME/XDG_CONFIG_HOME sandboxed); no missed callers. No findings raised, so receiving-code-review had nothing to verify or refute.

<!-- fr:journal kind=discovery scope=plan id=p2-no-refactor-t1 created=2026-09-27T09:44:56 phase=2 -->
### p2-no-refactor-t1 · discovery · no-refactor-because P2.T1 (phase 2)

batch_branch and batch_workflow are one-line lookups keyed by batch.skill; the call-site updates are already the smallest form.

<!-- fr:journal kind=discovery scope=plan id=p2-no-refactor-t2 created=2026-09-27T09:44:56 phase=2 -->
### p2-no-refactor-t2 · discovery · no-refactor-because P2.T2 (phase 2)

render_brief's debug branch is three local substitutions inline with the existing structure; nothing to extract for a block used once.

<!-- fr:journal kind=discovery scope=plan id=p2-no-refactor-t3 created=2026-09-27T09:44:56 phase=2 -->
### p2-no-refactor-t3 · discovery · no-refactor-because P2.T3 (phase 2)

mixed_themes and --skill each do one thing already; the shared warning print is its own helper, which is the refactor this task would otherwise ask for.

<!-- fr:journal kind=finding scope=plan id=r2-1 created=2026-09-27T09:49:16 phase=2 state=open review_scope=in -->
### r2-1 · finding [open] (reviewer: in scope) · work_item.py run-unit docstring still says branch is always feat/batch-<id> (phase 2)

packages/fr-dispatch/src/fr_dispatch/work_item.py:55 — this phase made fix/batch-<id> a possible branch and updated the adjacent `workflow` bullet, but left `branch` stating the goal-only shape.

<!-- fr:journal kind=finding scope=plan id=r2-2 created=2026-09-27T09:49:16 phase=2 state=open review_scope=out -->
### r2-2 · finding [open] (reviewer: out of scope) · mixed_themes compares themes without case/whitespace normalisation (phase 2)

packages/fr/src/fr/triage/batch.py mixed_themes uses raw set equality on Judgement.theme, so "Docs" and "docs" count as two themes. Themes are unnormalised free text everywhere; the pre-existing suggest() (unchanged here) compares them the same way.

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-09-27T09:49:16 phase=2 -->
### review-phase-2 · review · phase 2 code review (#687): 2 low findings (1 in scope, fixed; 1 out of scope) (phase 2)

Independent reviewer (standard tier, claude-sonnet-5) read `git show` of 25ad08cf and 54e544ca against spec §B/§C/§D and 02.yaml, ran the targeted tests, mirror tripwires, neutrality scan, ruff and mypy (all green). Verified: every batch_branch/batch_workflow call site takes the Batch; no feat/batch- or fr-goal hardcode reachable for a debug batch; --skill edit gated past proposed; the warning fires only after a successful write; goal batches stay byte-identical; the debug brief matches fr-debugging §2. Raised r2-1 (in, verified against the file and fixed) and r2-2 (out, verified: suggest() uses the same raw comparison, so this change did not introduce it).

<!-- fr:journal kind=finding scope=plan id=r2-1-resolved created=2026-09-27T09:49:16 phase=2 state=fixed resolves=r2-1 -->
### r2-1-resolved · finding [fixed] · resolves r2-1: work_item.py run-unit docstring still says branch is always feat/batch-<id> (phase 2)

work_item.py `branch` bullet now names fix/batch-<id> for a debug batch.

<!-- fr:journal kind=finding scope=plan id=r2-2-resolved created=2026-09-27T09:49:16 phase=2 state=open resolves=r2-2 out_of_scope=true -->
### r2-2-resolved · finding [out-of-scope] · resolves r2-2: mixed_themes compares themes without case/whitespace normalisation (phase 2)

Theme normalisation is absent codebase-wide (suggest() compares raw strings too); mixed_themes follows that convention. A normalisation change belongs to both, in its own change.

<!-- fr:journal kind=finding scope=plan id=d-1 created=2026-09-27T10:01:01 phase=1 state=fixed review_scope=in -->
### d-1 · finding [fixed] (reviewer: in scope) · Change fragment summary was a block scalar; the fragment gate refused it (phase 1)

Found by the deliver-time full suite (test_change_fragments.py) and scripts/check-change-fragment.py: .changes/feat-batch-batch-launch.yaml used a folded block for summary; the schema needs one line. Phase 1 reported the gate as passing. Fixed: summary is one quoted line; check-change-fragment.py origin/main passes.

<!-- fr:journal kind=finding scope=plan id=d-2 created=2026-09-27T10:01:01 phase=2 state=fixed review_scope=in -->
### d-2 · finding [fixed] (reviewer: in scope) · fr-triage SKILL.md grew past the 120-line cap (phase 2)

Found by the deliver-time full suite (test_skill_validation.py::test_under_120_lines[fr-triage]): phase 2 took the skill to 122 lines; its gate ran the mirror tripwires but not skill validation. Fixed: paragraph tightened to two lines, both mirrors regenerated, skill tripwires green.

<!-- fr:journal kind=finding scope=plan id=r2-2-resolved-2 created=2026-09-27T10:15:12 state=open resolves=r2-2 tracked_by=#725 -->
### r2-2-resolved-2 · finding [deferred → #725] · resolves r2-2: mixed_themes compares themes without case/whitespace normalisation

Filed at closeout as #725.

<!-- fr:journal kind=finding scope=plan id=r2-2-resolved-3 created=2026-09-27T10:15:59 state=open resolves=r2-2 tracked_by=#724 -->
### r2-2-resolved-3 · finding [deferred → #724] · resolves r2-2: mixed_themes compares themes without case/whitespace normalisation

Already filed as #724 before closeout; #725 was a duplicate and is closed.
