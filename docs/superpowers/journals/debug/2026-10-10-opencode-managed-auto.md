# Journal: 2026-10-10-opencode-managed-auto

<!-- fr:journal kind=repro scope=debug id=permission-prompt created=2026-10-10T09:28:10+00:00 -->
### permission-prompt · repro · Managed OpenCode sessions stop at permission prompts without --auto

Live reproduction during #1089 close-out: a fresh Herdr OpenCode control session started without native --auto reached OpenCode's Permission required UI when it needed the archive worktree, and work stopped until the operator approved it. Source inspection of origin/main confirms the same launch shape in all fr-managed paths: HerdrRunner.dispatch, opencode.restart_pane and replacement.launch_target pass only --model <id>. Exact regression condition: each managed OpenCode agent-start argv must end in --model <id> --auto; Claude launches must remain unchanged.

<!-- fr:journal kind=root-cause scope=debug id=launch-contract created=2026-10-10T09:30:11+00:00 -->
### launch-contract · root-cause · Managed launch contract omitted autonomous permissions

The defect is in fr-herdr's launch contract, not in OpenCode's permission engine. Every fr-owned fresh OpenCode process was constructed as opencode --model <id>, so normal OpenCode permission prompting remained active even though these are unattended agents. The construction was duplicated across initial dispatch, restart and replacement. A second coupling made a one-token patch unsafe: model_matches accepted only the old exact argv and would classify a correctly launched --auto session as the wrong model, triggering false readiness/replacement behavior. Regression proof against commit 5219322b^: the candidate test set produced 4 failures (initial dispatch, compatibility observer, restart, replacement) and 126 passes; the same set on the candidate produced 130 passes.
