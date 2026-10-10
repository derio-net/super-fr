# Journal: 2026-10-10-opencode-managed-auto

<!-- fr:journal kind=repro scope=debug id=permission-prompt created=2026-10-10T09:28:10+00:00 -->
### permission-prompt · repro · Managed OpenCode sessions stop at permission prompts without --auto

Live reproduction during #1089 close-out: a fresh Herdr OpenCode control session started without native --auto reached OpenCode's Permission required UI when it needed the archive worktree, and work stopped until the operator approved it. Source inspection of origin/main confirms the same launch shape in all fr-managed paths: HerdrRunner.dispatch, opencode.restart_pane and replacement.launch_target pass only --model <id>. Exact regression condition: each managed OpenCode agent-start argv must end in --model <id> --auto; Claude launches must remain unchanged.

<!-- fr:journal kind=root-cause scope=debug id=launch-contract created=2026-10-10T09:30:11+00:00 -->
### launch-contract · root-cause · Managed launch contract omitted autonomous permissions

The defect is in fr-herdr's launch contract, not in OpenCode's permission engine. Every fr-owned fresh OpenCode process was constructed as opencode --model <id>, so normal OpenCode permission prompting remained active even though these are unattended agents. The construction was duplicated across initial dispatch, restart and replacement. A second coupling made a one-token patch unsafe: model_matches accepted only the old exact argv and would classify a correctly launched --auto session as the wrong model, triggering false readiness/replacement behavior. Regression proof against commit 5219322b^: the candidate test set produced 4 failures (initial dispatch, compatibility observer, restart, replacement) and 126 passes; the same set on the candidate produced 130 passes.

<!-- fr:journal kind=finding scope=debug id=replacement-observer created=2026-10-10T09:35:46+00:00 state=open -->
### replacement-observer · finding [open] · Replacement observer rejected the corrected launch argv

Retrospective audit finding against PR commit 5219322b: launch_target correctly appended --auto and opencode.wait_ready accepted it, but replacement.observe independently required argv[1:] == [--model, model]. A real replacement would therefore launch successfully, fail its post-launch observation, and report an operation failure. The installed batch-replacement scenario masked this by reconstructing the old argv instead of replaying agent start's actual arguments. Direct reproduction against 5219322b raised ManagedError: foreground process/model/cwd is unknown or changed for [opencode, --model, openai/new, --auto].

<!-- fr:journal kind=finding scope=debug id=replacement-observer-resolved created=2026-10-10T09:38:14+00:00 state=fixed resolves=replacement-observer answered_by=agent -->
### replacement-observer-resolved · finding [fixed] · resolves replacement-observer: Replacement observer rejected the corrected launch argv

replacement.observe now delegates OpenCode argv validation to opencode.model_matches, preserving old managed sessions while accepting --auto. The unit timeline and installed batch-replacement scenario replay actual launch argv. The previous candidate reproducer now succeeds; 205 focused unit tests and all three installed OpenCode lifecycle scenarios pass.

<!-- fr:journal kind=hypothesis scope=debug id=local-config created=2026-10-10T10:26:00+00:00 -->
### local-config · hypothesis · The prompt came from local OpenCode configuration

If a deny or prompt rule in the operator's OpenCode configuration caused the stop, changing fr-herdr launch argv would not be the correct system fix. Check the native CLI contract and every fr-owned process launch before changing behavior.

<!-- fr:journal kind=ruled-out scope=debug id=local-config-ruled-out created=2026-10-10T10:26:07+00:00 -->
### local-config-ruled-out · ruled-out · Native default prompting, not an anomalous local configuration

The installed OpenCode help defines --auto as auto-approve permissions not explicitly denied and defaults it to false. origin/main omitted that flag from all three managed launch paths. The live stop was therefore the expected native default for unattended sessions; explicit denies remain denies under --auto.
