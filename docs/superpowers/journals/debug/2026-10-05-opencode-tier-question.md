# Journal: 2026-10-05-opencode-tier-question

<!-- fr:journal kind=repro scope=debug id=b780615415f0 created=2026-10-05T20:38:18+00:00 -->
### b780615415f0 · repro · fr-goal brainstorm brief carries no tier bindings; tier question depends on recall

Re-verified on 5.5.0 (gh#538 §1). `plugins/super-fr/skills/fr-goal/SKILL.md` §1 still reads 'a model-per-tier one if `fr models resolve` is unbound', and `fr run advance`'s brief (`run_cmd._build_brief`) has no key naming tier bindings — the only way the question fires is the model remembering to run `fr models resolve` per tier, which the observed OpenCode run never did.

<!-- fr:journal kind=root-cause scope=debug id=5b4acc1f03a9 created=2026-10-05T20:38:19+00:00 -->
### 5b4acc1f03a9 · root-cause · The tier question's trigger is a check outside the brief

`_build_brief` emits Step fields + run identity + record, nothing about models.yaml. The condition fr already knows (`fr.models.resolve` for the detected harness, `detect_harness` honouring FR_HARNESS / nearest-ancestor since gh#537) never reaches the orchestrator, so the gate question is triggered by recall rather than data. gh#538 §2 (a confirm-question restating a requirement) is a separate, model-behaviour cause and out of this batch's scope.

<!-- fr:journal kind=finding scope=debug id=ffc2becdbd57 created=2026-10-05T20:50:13+00:00 state=fixed -->
### ffc2becdbd57 · finding [fixed] · Brief states unbound_tiers; fr-goal §1 reads it

`run_cmd._unbound_tiers` (via `detect_harness` + `_resolved_model`) feeds a new `unbound_tiers` brief key: PHASE_TIERS order, `[]` when all bound, `null` when no harness is detected. fr-goal SKILL.md §1 asks per listed tier (all three on null). Pinned by `tests/unit/test_run_cli.py::test_gate_brief_*` and `test_fr_goal_triggers_the_tier_question_from_the_brief`, committed failing first.
