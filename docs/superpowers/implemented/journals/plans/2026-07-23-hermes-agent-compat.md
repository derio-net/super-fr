# Journal: 2026-07-23-hermes-agent-compat

<!-- fr:journal kind=discovery scope=plan id=p1-standalone-scripts created=2026-07-23T21:01:17 -->
### p1-standalone-scripts · discovery · sync-hermes.py kept standalone (not sharing helpers with sync-opencode.py)

Tripwires import each sync-*.py by path; sharing a helper module would add a cross-script import for marginal DRY. Skills logic is close but not verbatim (fr category dir, .hermes paths, breadcrumb text). Refactor step P1.T1.S5 skipped intentionally.

<!-- fr:journal kind=discovery scope=plan id=p3-shared-decision-core created=2026-07-23T21:10:16 -->
### p3-shared-decision-core · discovery · Extracted lib/fr-isolation-decision.sh; Claude hook behavior byte-identical

The marker/allowlist/fr-enabled logic now lives in one sourced bash lib (fr_isolation_decide_edit, returns 0 allow / 1 block). Claude entrypoint sources it and keeps its exact deny JSON — 13/13 existing hook tests still green. Hermes entrypoint reuses the lib, adds write_file|patch tool gate + tool_input.path extraction + {"decision":"block"} shape. Callers MUST invoke the fn inside an 'if' so a deny return doesn't trip set -e.

<!-- fr:journal kind=finding scope=plan id=p4-guard-marker-based created=2026-07-23T21:12:49 phase=4 state=fixed -->
### p4-guard-marker-based · finding [fixed] · Hermes bash guard is marker-based, not sentinel-based — implemented + tested (phase 4)

Claude fr-isolation-guard.sh gates ALL base-repo commands while a pipeline SENTINEL is active (written by fr-pipeline-sentinel.sh, a Skill-PostToolUse hook). Hermes has no Skill-PostToolUse, so no sentinel writer. Decision: the Hermes guard is MARKER-based (session-independent, like the P3 edit hook) — it blocks git/gh MUTATIONS whose effective cwd (payload cwd, or a leading 'cd <target>') is an fr-enabled base clone lacking a valid isolation worktree. Escapes: fr isolation …, cd <worktree>, FR_BASE_OK=1. Read-only/unknown commands pass (discipline backstop, not a security boundary). Implemented via a new fr_isolation_decide_cwd in the shared lib.

<!-- fr:journal kind=discovery scope=plan id=p5-yaml-comment-loss created=2026-07-23T21:28:17 -->
### p5-yaml-comment-loss · discovery · fr hermes uses PyYAML; comments in cli-config.yaml are not round-tripped

Documented limitation (module docstring): mutating cli-config.yaml via PyYAML strips comments. The managed edits are confined to the hooks: key and are idempotent+reversible, but surrounding user comments aren't preserved. Acceptable for v1; ruamel would preserve them at the cost of a new dep.

<!-- fr:journal kind=discovery scope=plan id=p7-fr-execute-neutral created=2026-07-23T21:36:27 -->
### p7-fr-execute-neutral · discovery · fr-execute needs no Hermes edit; the delegated child loads it as-is

fr-goal step 6 now branches on harness: Claude Code dispatches fr-phase-executor Agent; Hermes calls delegate_task(goal, context). The delegated Hermes child loads the fr-execute skill, which is harness-neutral (agent-facing execution protocol) — no Hermes-specific edit required. SKILL.md held at exactly 120 lines by compressing the executor paragraph; TDD skill ref kept inline.

<!-- fr:journal kind=review scope=plan id=r-milestone-review created=2026-07-23T21:46:54 -->
### r-milestone-review · review · Milestone review (spec+plan+code): no defects; flipped acceptance rows

Full suite 1670 passed / 80 skipped; ruff + mypy clean; journal check + plan self-review pass. Inline adversarial review of the riskiest logic (enforcement lib refactor byte-identical via 13 Claude tests; guard mutation-regex + cd-transition; install idempotence/reversibility roundtrip; install.sh fr-before-fr-hermes ordering; .hermes tracked / .fr-isolation still ignored) found no correctness defects — all risk areas test-covered. Flipped 4 hermes rows not-implemented -> ci (unit-tested) and hermes-fr-goal-delegation -> skipped (wiring unit-tested; end-to-end is post-merge Test Plan 6). fr acceptance check: 47 rows OK.

<!-- fr:journal kind=finding scope=plan id=r2-no-guessed-models created=2026-07-23T22:22:46 phase=6 state=fixed -->
### r2-no-guessed-models · finding [fixed] · Shipped hermes model ids were fabricated AND suppressed fr-goal's first-run question (phase 6)

Operator review: the NousResearch/Hermes-4-{14B,70B,405B} ids in docs/superpowers/models.yaml were invented — super-fr cannot know which models a given Nous endpoint serves. Worse, ANY shipped binding resolves successfully, which suppresses fr-goal's documented 'unbound -> ask the operator per tier' question (SKILL.md steps 1 and 6) and silently locks the operator to a wrong model. FIXED: deleted docs/superpowers/models.yaml entirely; hermes now resolves unbound so the question fires. Replaced test_models_hermes_defaults.py with test_models_hermes_first_run.py, which FAILS if any hermes binding is ever re-introduced. Spec sections D/E/G amended.

<!-- fr:journal kind=discovery scope=plan id=p8-hermes-md-shadows-agents created=2026-07-23T23:07:59 -->
### p8-hermes-md-shadows-agents · discovery · HERMES.md shadows AGENTS.md — inline the non-negotiables, point at the rest

Operator asked for a HERMES.md + install docs. Verified against Hermes docs: exactly ONE project context file loads (.hermes.md/HERMES.md > AGENTS.md > CLAUDE.md, first match wins) and there is NO include mechanism (context_references.REFERENCE_PATTERN is for conversational @-refs, not context composition). So a naive HERMES.md would silently REMOVE every maintainer instruction from Hermes sessions. Design: HERMES.md inlines the unsafe-to-discover-late invariants (isolation, no direct-to-main, version bump, regenerate mirrors, no claude -p batch, CI gate) and points at AGENTS.md for the full map instead of duplicating it (drift). tests/unit/test_hermes_docs.py guards the pointer (AGENTS.md must exist), the inlined invariants, and the README install/uninstall docs.

<!-- fr:journal kind=finding scope=plan id=9010450e824d created=2026-07-24T17:30:11 state=fixed -->
### 9010450e824d · finding [fixed] · Phase 8 live Hermes proof found and fixed inert hook registration

Ran the pending Phase 8 in a real Hermes TUI. Installation and skill discovery succeeded, and delegate_task launched a fresh-context independent phase reviewer. The first fresh Hermes write_file/patch test exposed a real defect: 3.15.0–3.17.0 installed hooks into obsolete cli-config.yaml while this Hermes reads config.yaml. Fixed under TDD for 3.17.1, migrated stale registrations, reinstalled into the live HERMES_HOME, and reran fresh-process acceptance: outside-isolation edit blocked; linked-worktree edit allowed; FR_BASE_OK escape allowed; outside-isolation git mutation blocked; in-isolation git mutation allowed. Targeted Hermes tests: 49 passed. Broad non-image-specific suite: 1696 passed, 81 skipped. PR creation remains before marking the phase complete.

<!-- fr:journal kind=review scope=plan id=p8-hermes-delegated-review created=2026-07-24T20:27:39 phase=8 -->
### p8-hermes-delegated-review · review · Phase 8 Hermes-delegated final review: clean (phase 8)

Reviewed the complete staged and unstaged Phase 8 continuation against the plan/spec and the installed Hermes Agent v0.18.2 source/behavior. Confirmed Hermes reads config.yaml, accepts the four hook registrations and 30s timeouts, serializes pre_llm_call is_first_turn under extra, and consumes returned JSON context. Reviewed config migration/uninstall ownership boundaries, malformed-file fail-safe behavior, acceptance-nag first-turn gating, docs/plan corrections, and the then-current lockstep version. Exact requested targeted suite: 60 passed in 2.57s. git diff --check: clean. Targeted ruff: clean. No defects found; P8.T1.S4 remained pending for the live uninstall/PR proof.

<!-- fr:journal kind=finding scope=plan id=p8-live-uninstall-stale-fr created=2026-07-24T20:33:54 phase=8 state=fixed -->
### p8-live-uninstall-stale-fr · finding [fixed] · Live uninstall exposed stale-fr upgrade coupling; fixed fail-fast (phase 8)

The required Phase 8 uninstall proof found that install.sh called the previously installed fr CLI. After the snippet rename, that stale binary failed while stderr was discarded, leaving four hooks active and deleting only skills. Fixed under TDD to execute this checkout's fr via uv and abort before skill deletion on failure. Live uninstall/reinstall round-trip now passes.

<!-- fr:journal kind=review scope=plan id=p8-final-live-roundtrip created=2026-07-24T20:38:56 phase=8 -->
### p8-final-live-roundtrip · review · Final live round-trip and post-rebase gates (phase 8)

Installed the rebased 3.17.1 build into live Hermes: fr --version reports 3.17.1; hermes hooks list reports exactly four allowed hooks with 30s timeouts; fr-goal skill and managed rules are present. Live uninstall/reinstall round-trip removed/restored only managed Hermes artifacts and exposed/fixed the stale-global-fr failure path. Final targeted Hermes+version suite: 38 passed. Ruff, format, mypy, bash syntax, version lockstep, diff check, journal checks, plan self-review, and acceptance check pass. Broad post-rebase suite: 1710 passed, 81 skipped, with one unrelated origin/main baseline failure because PR #405 left its completed vk-mcp-timeout-permit-leak plan unarchived; not folded into this Hermes branch.

<!-- fr:journal kind=review scope=plan id=p8-complete-pr407 created=2026-07-24T20:39:51 phase=8 -->
### p8-complete-pr407 · review · Phase 8 complete; Hermes run delivered to PR #407 (phase 8)

The Hermes-driven run reached https://github.com/derio-net/super-fr/pull/407 after the independent Hermes delegate review, live hook enforcement proof, corrected uninstall/reinstall round-trip, 3.17.1 bump, and final gates. P8.T1.S4 and Phase 8 are complete. Operator merge remains intentionally manual.
