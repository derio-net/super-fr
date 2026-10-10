# Journal: 2026-10-10-opencode-managed-auto

<!-- fr:journal kind=repro scope=debug id=permission-prompt created=2026-10-10T09:28:10+00:00 -->
### permission-prompt · repro · Managed OpenCode sessions stop at permission prompts without --auto

Live reproduction during #1089 close-out: a fresh Herdr OpenCode control session started without native --auto reached OpenCode's Permission required UI when it needed the archive worktree, and work stopped until the operator approved it. Source inspection of origin/main confirms the same launch shape in all fr-managed paths: HerdrRunner.dispatch, opencode.restart_pane and replacement.launch_target pass only --model <id>. Exact regression condition: each managed OpenCode agent-start argv must end in --model <id> --auto; Claude launches must remain unchanged.
