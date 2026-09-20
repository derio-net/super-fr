# Journal: 2026-09-20-agentic-dispatch-verb-lint

<!-- fr:journal kind=decision scope=spec id=d1-scope created=2026-09-20T15:00:59 -->
### d1-scope · decision · Scope: #428 items 1, 2 and 4 ship; item 3 stays open

Operator answered the batched Q&A: ship the `fr plan self-review` lint (item 1), the executor contract that refuses the tick (item 2, `fr-phase-executor.md` + `fr-execute`), and fr-plan's outcomes-not-mechanisms guidance (item 4). Item 3 (`fr journal check --require-reviews`) is a new CLI surface and stays open as its own issue. Rationale given: a gate that errors without saying what to write instead is half a fix, so 2 and 4 are what make 1 actionable. #496 is explicitly out of scope (owned by the parallel fr run cursor run).

<!-- fr:journal kind=decision scope=spec id=d2-precision created=2026-09-20T15:00:59 -->
### d2-precision · decision · Precision-first, single error tier — the issue's literal pattern list is unusable here

Measured during the brainstorm over all 1419 agentic steps in this repo's 43 parseable plan folders (live + archived): #428's literal proposal fires 237 times on bare `dispatch` alone (16.7% of steps), 42 times on a bare `<word>:<word>` token (`start:end`, `cli:app`, `fr:synced`), plus hits on `spawn`, `delegate to`, `subagent_type` and `Task tool` — every one a false positive, because super-fr is a repo ABOUT dispatch. At error severity that breaks self-review on super-fr's own plans. Chosen instead: an imperative-head dispatch verb with an agent-shaped object, plus explicit mechanism tokens. Measured 0 hits / 1419 steps while still matching the frank case verbatim. This mirrors the existing agentic-purity comment: 'Deliberately conservative (precision over recall)'. No warn tier (~240 warnings would train authors to ignore the output) and no per-step suppression marker.

<!-- fr:journal kind=decision scope=spec id=d3-escape created=2026-09-20T15:01:00 -->
### d3-escape · decision · A [manual] phase is the escape route — no new override mechanism

When a plan genuinely needs subagent work, it goes in a `[manual]` phase. The lint only inspects agentic phases, so the escape already exists and needs no code. Perfectly parallel to #252's rule, which this mirrors: dispatch is orchestrator-only work exactly as #252's target is human-only work. Rejected: a spec-scope override decision in the shape of `skeleton-override-<plan-slug>` — it is more machinery AND it would let an agentic phase keep a step the executor still cannot perform, which is the defect itself.

<!-- fr:journal kind=decision scope=spec id=d4-tiers created=2026-09-20T15:01:00 -->
### d4-tiers · decision · Model tiers rebound: claude-code/standard sonnet-5 → opus-5

Operator asked for 'standard & deep -> opus, fast -> sonnet'. fr's real tier vocabulary is `mechanical | standard | hard`, not fast/standard/deep (the question used the wrong names); mapped deep→hard, fast→mechanical. Resulting claude-code config: hard=claude-opus-5 (already bound), standard=claude-opus-5 (CHANGED from claude-sonnet-5), mechanical=claude-sonnet-5 (already bound). All three tiers are now bound, so no phase dispatch in this run can silently inherit the session model. opencode bindings untouched.

<!-- fr:journal kind=review scope=spec id=r1-corpus-honesty created=2026-09-20T15:05:38 -->
### r1-corpus-honesty · review · Corpus claim was misleading: 43 of 105 plan folders parse, and the test could have gone green reading nothing

Spec review against codebase reality. The draft said the measurement covered 'every parseable plan folder ... 43 plans' without saying what the other 62 were. Census: 43 parse, 41 raise PlanSchemaError (38 of them on a frozen `fr_version: '>=3.0.0,<4.0.0'` pin that fr 4.8.0 can never satisfy — archived artifacts are deliberately never migrated — and 3 on PhaseDoc validation), 21 entries are not folders. Two fixes: §2.D now states the shortfall and why; §4.A's corpus test now asserts a FLOOR on plans parsed (>=30) and agentic steps scanned (>=1000), because 'skip unparseable, assert zero hits' degrades silently into a passing test that read nothing the day a schema bump lands. A green check that verifies nothing is this repo's recurring defect class.

<!-- fr:journal kind=review scope=spec id=r2-agent-mirror-guard created=2026-09-20T15:05:38 -->
### r2-agent-mirror-guard · review · OpenCode agent-variant drift is guarded by test_opencode_agent_mirror.py, not the skills tripwire

The draft named only test_tripwire_opencode_skills_sync.py as the drift guard for §4.B's two edits. That tripwire covers .opencode/skills/; the four .opencode/agent/fr-phase-executor{,-mechanical,-standard,-hard}.md variants are covered by tests/unit/test_opencode_agent_mirror.py. Both are now named — a plan that runs sync-opencode.py and only checks the skills tripwire would miss agent drift.

<!-- fr:journal kind=review scope=spec id=r3-claims-verified created=2026-09-20T15:05:38 -->
### r3-claims-verified · review · Every other file, helper and quotation the spec names was verified to exist

Verified in the worktree: fr.plan_ops.self_review and _MANUAL_VERB_RES with its 'Deliberately conservative (precision over recall)' comment quoted verbatim; fr-phase-executor.md's `tools: Read, Edit, Write, Bash, Grep, Glob` (no Agent); .opencode/agent/fr-phase-executor-hard.md's `task: deny`; plugins/super-fr/hooks/fr-phase-executor-guard.sh; tests/unit/test_skill_tokens.py with its FR_PLAN/FR_EXECUTE/FR_PHASE_EXECUTOR constants; fr-plan SKILL.md's 'Pure agentic phases' bullet (the sibling insertion point); fr-execute SKILL.md's Procedure step 3 and Constraints; docs/explainers/01-fr-goal.md line 364's 'manual work hidden inside an agentic phase' (the sibling sentence's insertion point); scripts/sync-opencode.py's handling of all four agent variants. Also confirmed the no-parity-row claim: test_tripwire_harness_parity.py pairs shipped HOOK SCRIPTS to rows (test_every_shipped_hook_script_has_a_parity_row) and no hook ships here.
