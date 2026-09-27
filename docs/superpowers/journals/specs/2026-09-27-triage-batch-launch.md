# Journal: 2026-09-27-triage-batch-launch

<!-- fr:journal kind=decision scope=spec id=d1-no-subagent-override created=2026-09-27T09:03:06 -->
### d1-no-subagent-override · decision · No subagent-model override of any kind; the brief is silent on subagent models

Operator chose "No override" over an opt-in --subagent-model or a per-tier map. fr-goal/fr-debugging resolve each subagent's tier through `fr models` (repo override > user); a repo wanting other tier models sets docs/superpowers/models.yaml, not the batch.

<!-- fr:journal kind=decision scope=spec id=d2-harness-alias created=2026-09-27T09:03:06 -->
### d2-harness-alias · decision · Map the runner's harness name to fr's harness id; refuse only when no model resolves

Operator chose a fixed alias table (claude -> claude-code, others as-is) over accepting both spellings or making batches spell fr ids. Session model = batch --model, else defaults.launch.model, else the orchestrator binding; all unset -> dispatch refuses and names the `fr models set ... --tier orchestrator` line.

<!-- fr:journal kind=decision scope=spec id=d3-theme-warning created=2026-09-27T09:03:06 -->
### d3-theme-warning · decision · One-root-cause warning on create and edit, never a refusal

Operator chose create + edit over create-only or also-at-dispatch. Fires when the resulting batch is skill debug and its members carry two or more distinct non-empty themes.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-27T09:11:43 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Model-provenance display duplicates resolve_launch's own precedence order

Spec had the command layer re-derive which of batch / defaults.launch / orchestrator supplied the model, re-implementing resolve_launch's precedence (batch.py:306) — the r-p2-f2 bug class recorded in fr.models.resolved_config (models.py:63-74).

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-27T09:11:43 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · fr_dispatch.work_item docstring still says model is for every subagent and tier

packages/fr-dispatch/src/fr_dispatch/work_item.py:52 states the pre-#704 semantics; spec §D did not list the file.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-27T09:11:43 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · _probe also hardcodes workflow="fr-goal", uncovered by spec §B

triage_batch_cmd.py:587-600 builds a second WorkItem for --repair's liveness probe; spec named only _work_item.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-27T09:11:43 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · fr_herdr docstrings hardcode "launches a batch as one /fr-goal"

fr_herdr/__init__.py:3 and runner.py:3 become false once a batch can start /fr-debugging.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-27T09:11:43 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · batch_branch signature change breaks a pinned test missing from the caller inventory

tests/unit/test_triage_batch_model.py:486 calls batch_branch("lifecycle").

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-27T09:11:43 -->
### spec-review · review · independent spec review: 5 findings (all in scope)

Dispatched fr-spec-reviewer (standard tier, claude-sonnet-5). Verified the spec's file:line claims (render_brief:87, resolve_launch:306, batch_branch:69, REPO_MODELS_REL, DispatchEvent.branch consumers triage_cmd.py:141 and batch.py:146, _Strict extra=forbid, judgements.yaml not an artifact kind, golden brief test test_triage_batch_dispatch.py:333). Raised s1-s5, all in scope, all fixed in the spec.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-27T09:11:43 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Model-provenance display duplicates resolve_launch's own precedence order

Spec §A: resolve_launch returns ResolvedLaunch with model_source; command layer prints it verbatim, never re-derives.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-27T09:11:43 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: fr_dispatch.work_item docstring still says model is for every subagent and tier

Spec §D now lists work_item.py's payload docstring (workflow by skill; model is the session model).

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-27T09:11:43 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: _probe also hardcodes workflow="fr-goal", uncovered by spec §B

Spec §B: batch_workflow(batch) helper used by both _work_item and _probe; Test Plan 8 covers the probe.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-27T09:11:43 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: fr_herdr docstrings hardcode "launches a batch as one /fr-goal"

Spec §D lists fr_herdr __init__.py:3 and runner.py:3.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-09-27T09:11:43 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: batch_branch signature change breaks a pinned test missing from the caller inventory

Spec §B caller list and Test Plan 9 name the pinned test and its replacement.
