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
