# Journal: 2026-09-19-opencode-subagent-dispatch

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-19T23:49:45 -->
### d1 · decision · OpenCode dispatches phases by default — parity with Claude Code and Hermes

Operator decision (batched Q&A, 2026-09-19). Measured tradeoff from `docs/presentation/version-1/experiment/run-metrics.csv`: arm A dispatched 13 subagents at $7.59 / 56.2 root-minutes; the two inline arms cost ~$1 at 77.6 and 105.2 minutes. About 7x the cost, and the FASTEST arm, with per-phase context isolation. Default is dispatch. Two supporting facts: (1) arm A already dispatched on OpenCode despite the skill saying inline, so inline-by-default would regress measured behaviour; (2) the cost is stated as a policy in both the skill and the parity note, per #493 — "the primitive is too expensive by default" and "no primitive exists" are different claims and only one was ever true.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-19T23:49:45 -->
### d2 · decision · Per-tier agent files; sync bakes repo config, install fills the global copies

Operator decision. Binary-level constraint verified first: OpenCode task-tool input is `{prompt, description, subagent_type, command}` and the agent is then resolved BY NAME, so a dispatch call cannot carry a model — the model comes only from the agent file's static `model:`. Therefore tier->model becomes agent-per-tier: `fr-phase-executor-{mechanical,standard,hard}` (the closed `fr.types.PhaseHeader.tier` set) plus the untiered base, dispatched as `subagent_type: fr-phase-executor-<tier>`. Who writes `model:`: `sync-opencode.py` bakes it from the repo `docs/superpowers/models.yaml` when that file exists (committed, deterministic; super-fr has no such file so its own mirror stays model-free and inherits), and `install.sh` writes the global copies using `fr models resolve --harness opencode --tier <t>` so a consumer's user-level bindings apply. Same repo>user resolution order Claude Code dispatch already uses. Consequence: the OpenCode install block must move AFTER install.sh step 10 (the fr CLI install), since it now needs `fr` on PATH.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-19T23:50:07 -->
### d3 · decision · fr.harness.observe stays hook-only — this PR does not generalise it

Operator decision. `fr.harness.check.check()` skips every `kind != "hook"` surface and `observe.py` is keyed by shipped hook SCRIPT FILENAME on purpose ("an observer that had to know surface ids would have to read the matrix, and then the two could no longer disagree"). So `subagent-dispatch` is declaration-only today, as every interaction row is, and re-declaring it makes `fr harness parity --check` no less honest than it is now. The mechanical guard this PR does add is the agent-mirror sync tripwire: it pins that the artifact exists and matches canonical. Generalising observation to interaction rows is its own spec, not a rider on this one.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-09-19T23:50:08 -->
### d4 · decision · Live proof: a cheap real dispatch in-session, the full /fr-goal run back-loaded

Operator decision. #494 acceptance demands an `opencode.db` session row with `parent_id` set and `agent = fr-phase-executor*` — a mocked test cannot show a subagent was really spawned. Split: (a) in this PR, one real `opencode run` against a free model dispatching to the shipped tier agent, with the session row quoted in the PR body; (b) a full `/fr-goal` run on a paid model stays a back-loaded `[manual]` phase the operator runs post-merge and pushes to the same PR. Precedent for the free-model half is this repo`s own matrix notes on `opencode-isolation-enforcement` and `opencode-commands-in-repo`, which verified live the same way.

<!-- fr:journal kind=discovery scope=spec id=x1 created=2026-09-19T23:50:08 -->
### x1 · discovery · Verified live on opencode 1.18.31: frontmatter, permissions, global dir, task-tool input

Four facts established against the installed binary before any design, not from docs:
1. `.opencode/agent/<name>.md` (singular) with `mode: subagent` registers as `<name> (subagent)`; the FILENAME is the agent name, OpenCode has no `name:` field.
2. `permission: {edit: allow, bash: allow, webfetch: deny}` round-trips into the agent`s fully-resolved permission array exactly as written — so the `tools: Read, Edit, Write, Bash, Grep, Glob` translation target is confirmed, not guessed. `model:`, `temperature:` and a `tools:` map also parse.
3. A global `$XDG_CONFIG_HOME/opencode/agent/<name>.md` is discovered with no project config present, and XDG_CONFIG_HOME is honoured — so install.sh has a real target dir AND the install test can sandbox it.
4. Task-tool input is `{prompt, description, subagent_type, command}`; the agent is resolved by name afterwards. No model parameter — this is what forces agent-per-tier (see d2).
Upstream `anomalyco/opencode#29616` (custom subagents not invocable) is stale, filed 2026-05-27 and fixed by this version; do not re-derive the limitation from it.
