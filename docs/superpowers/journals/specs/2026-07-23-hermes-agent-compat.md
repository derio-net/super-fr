# Journal: 2026-07-23-hermes-agent-compat

<!-- fr:journal kind=decision scope=spec id=d1-scope created=2026-07-23T20:40:58 -->
### d1-scope · decision · v1 scope = full OpenCode-parity track

Operator chose full parity: fr-* skills -> ~/.hermes/skills/fr/, 3 rules -> Hermes context, isolation hook, on_session_start nag, install/uninstall (opt-in), sync-hermes.py + tripwires, dedicated CI job, hermes: model-tier defaults. Not the leaner enforcement-only or skills-only cuts.

<!-- fr:journal kind=decision scope=spec id=d2-rules created=2026-07-23T20:40:59 -->
### d2-rules · decision · Rules delivered as a managed block in global ~/.hermes/SOUL.md

Hermes has no instructions-array; SOUL.md is the only always-on global surface (analog to ~/.claude/rules). super-fr owns a delimited <!-- super-fr:rules START/END --> block appended on install, stripped on uninstall. Chosen over per-repo context file (first-match-wins shadowing risk) and skill-embedded (non-global, duplicated).

<!-- fr:journal kind=decision scope=spec id=d3-gatedepth created=2026-07-23T20:41:01 -->
### d3-gatedepth · decision · Isolation gate covers edits AND bash/push on Hermes

Hermes pre_tool_call shell hook gates write_file/patch (edits) AND terminal/execute_code (bash) -- porting fr-isolation-required + fr-isolation-guard + fr-merged-pr-push-guard. Closes the bash gap OpenCode's TS plugin still has; achieves Claude-Code enforcement parity.

<!-- fr:journal kind=decision scope=spec id=d4-phasedispatch created=2026-07-23T20:41:02 -->
### d4-phasedispatch · decision · fr-goal phase execution runs inside Hermes via delegate_task (in scope for v1)

Beyond plugin-surface delivery: wire fr-goal phase dispatch to Hermes native delegate_task/subagent (fr-phase-executor equivalent), journal-fed brief handoff, structured-result parsing -- full autonomous run inside Hermes. Significantly larger scope; operator opted in.

<!-- fr:journal kind=review scope=spec id=r1-yaml-merge created=2026-07-23T20:48:17 -->
### r1-yaml-merge · review · install.sh is jq-only; YAML merge into cli-config.yaml needs tested code

FIXED. Spec hedged 'bash+jq/yq-only, TBD'. jq cannot merge YAML; cli-config.yaml is a shared user-owned YAML file. Resolved by moving hooks/allowlist/SOUL mutations into a tested 'fr hermes install/uninstall' subcommand (reuses fr's yaml dep, no new external dep), invoked by install.sh. Matches 'guards = tested code' convention. Added unit-test row in §F.

<!-- fr:journal kind=review scope=spec id=r2-acceptance-rule-leak created=2026-07-23T20:48:18 -->
### r2-acceptance-rule-leak · review · Repo-local acceptance-matrix rule wrongly shipped into consumer global SOUL.md

FIXED. §B originally concatenated acceptance-matrix into the global SOUL.md block. But install.sh ships only the 3 plugin rules to ~/.claude/rules for Claude; acceptance-matrix is repo-maintainer-only (no plugin equivalent). Fix: global SOUL block = 3 shipped rules only; acceptance-matrix stays in super-fr's repo-local .hermes/ dogfooding context, never installed globally.
