# Journal: 2026-09-16-codex-harness-adapter

<!-- fr:journal kind=discovery scope=spec id=v1 created=2026-09-16T07:27:35 -->
### v1 · discovery · VERIFIED: $CODEX_HOME/skills IS scanned, despite the build-skills doc omitting it

Empirical, this session. `codex debug prompt-input` (offline prompt render, codex-cli 0.153.4) run from a neutral dir lists `fr-goal` and `fr-isolation`. Those two exist ONLY as symlinks in ~/.codex/skills (absolute links into the Claude plugin cache) - they are not in ~/.agents/skills. So $CODEX_HOME/skills is a real scanned location and absolute symlinks are followed. The docs page learn.chatgpt.com/docs/build-skills lists only $CWD/.agents/skills, $CWD/../.agents/skills, $REPO_ROOT/.agents/skills, $HOME/.agents/skills, /etc/codex/skills and "bundled" - it omits $CODEX_HOME/skills. OpenAI own bundled skill-installer SKILL.md corroborates the empirical result: "Installs into $CODEX_HOME/skills/<skill-name> (defaults to ~/.codex/skills)". Treat the docs list as incomplete, not authoritative.

<!-- fr:journal kind=discovery scope=spec id=v2 created=2026-09-16T07:27:37 -->
### v2 · discovery · VERIFIED: repo-level .agents/skills is discovered with no git repo required

Created a scratch dir codexprobe/.agents/skills/zzz-probe-repo/SKILL.md (no git init) and ran `codex debug prompt-input` from that dir: zzz-probe-repo appears in the rendered prompt. Confirms the repo/CWD-level .agents/skills channel, and that it does not require a git repository.

<!-- fr:journal kind=discovery scope=spec id=v3 created=2026-09-16T07:27:39 -->
### v3 · discovery · VERIFIED: a dangling skill symlink is skipped SILENTLY - root cause of the stale fr-* links

Added a dangling symlink zzz-dangling -> /nonexistent/... beside the good probe skill and re-ran `codex debug prompt-input`: exit 0, EMPTY stderr, zzz-probe-repo still listed, zzz-dangling absent. So a broken skill link produces no error, no warning and no catalog entry - the skill simply stops existing from the model point of view. This is precisely how the operator ~/.codex/skills/fr-* links (pointing at the retired ~/.claude/plugins/marketplaces/derio-net/... path) failed invisibly. It is the core justification for shipping `fr codex doctor` + repair-on-install rather than a one-time relink.

<!-- fr:journal kind=discovery scope=spec id=v4 created=2026-09-16T07:27:41 -->
### v4 · discovery · VERIFIED: Codex PreToolUse payload and deny shapes (learn.chatgpt.com/docs/hooks)

Input on stdin: {session_id, transcript_path, cwd, hook_event_name, permission_mode, turn_id, tool_name, tool_use_id, tool_input}. Docs state plainly: "Bash and apply_patch use tool_input.command". tool_name is "apply_patch" for edits even when the MATCHER is written as Edit or Write; shell is "Bash". Deny shapes accepted: hookSpecificOutput.permissionDecision=deny with permissionDecisionReason, legacy {decision:block,reason}, or exit 2 with the reason on stderr. Matchers are regex (alternation and .* supported). NOT verified live: no Codex session was run against a real hook this session, so the payload is doc-confirmed, not observed.

<!-- fr:journal kind=discovery scope=spec id=v5 created=2026-09-16T07:27:43 -->
### v5 · discovery · VERIFIED: hook config locations, trust model, and the project-trust caveat

Config locations: ~/.codex/hooks.json, ~/.codex/config.toml [hooks], <repo>/.codex/hooks.json, <repo>/.codex/config.toml, and plugin-bundled hooks/hooks.json. Live schema confirmed by reading the operator existing ~/.codex/hooks.json (read-only): {hooks:{Event:[{matcher?, hooks:[{type:command,command,timeout?}]}]}} - identical in shape to Claude hooks.json. TRUST: "Before a non-managed hook can run, Codex requires you to review and trust the exact hook definition", trust is recorded against the hook HASH, so a CHANGED hook is re-marked for review and SKIPPED until re-trusted. Plugin-bundled hooks are NOT exempt. config-reference adds: projects.<path>.trust_level - "Untrusted projects skip project-scoped .codex/ layers, including project-local config, hooks, and rules." Consequence: an installed hook is not a running hook, and every super-fr version bump that edits a hook silently disarms it until re-trusted.

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-16T07:27:45 -->
### d1 · decision · d1: ship BOTH an in-repo generated tree and an `fr codex install` subcommand

Mirrors how the two existing non-Claude harnesses split the job, for the same reasons. The in-repo generated tree (scripts/sync-codex.py, CI drift-tripwired) is what makes super-fr itself workable under Codex and gives a consuming repo like willikins a concrete, reviewable artifact to copy - the OpenCode .opencode/ role. The `fr codex install` subcommand owns the invasive, user-owned-file mutations (hooks.json merge, AGENTS.md managed block, skill relinking) as tested Python - the `fr hermes install` role, adopted because install.sh is bash+jq only and these mutations must be idempotent and fully reversible. Neither alone is sufficient: a repo tree cannot wire ~/.codex, and an installer with no tripwired source of truth drifts.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-16T07:27:48 -->
### d2 · decision · d2: skills install to $CODEX_HOME/skills/<name>; repo mirror at .agents/skills/<name>

User-level target is $CODEX_HOME/skills (default ~/.codex/skills) per v1: empirically scanned, matches OpenAI own skill-installer default, and matches where the operator existing fr-* links already live - so install REPAIRS the real failure in place instead of creating a second competing location. Repo-level mirror is .agents/skills/<name>/SKILL.md per v2 (the documented repo channel; .codex/skills is NOT a skills location). Byte-copy of plugins/super-fr/skills/<name>/SKILL.md with a .source breadcrumb, exactly like the OpenCode and Hermes mirrors. super-fr SKILL.md frontmatter (name + description) already satisfies Codex required fields - no transform.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-16T07:27:49 -->
### d3 · decision · d3: rules reach Codex via a delimited managed block in ~/.codex/AGENTS.md, budget-capped

~/.codex/AGENTS.md is Codex only always-on global instruction surface - the analog of ~/.claude/rules/ and Hermes SOUL.md. Codex MERGES the global file with the project AGENTS.md chain (root -> cwd), so a managed block there is additive and does not shadow a repo own AGENTS.md (unlike Hermes, where one project file wins and HERMES.md had to inline invariants). Constraint that shapes the design: project_doc_max_bytes defaults to 32 KiB and discovery STOPS at the threshold, so an oversized block would silently evict the consuming repo own instructions. Therefore the block is size-budgeted and test-enforced, and full rule bodies are also installed as files under $CODEX_HOME/rules/super-fr/ for reference. Block is delimited by super-fr:rules START/END markers, idempotent, and stripped cleanly on uninstall; content outside the markers is never touched. The operator ~/.codex/AGENTS.md is currently 0 bytes, so this is non-destructive today.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-09-16T07:27:51 -->
### d4 · decision · d4: port the edit gate AND the bash guard; DEFER the merged-PR push guard and the acceptance nag

Edit gate (apply_patch) is the load-bearing new work. The bash guard is included because Codex reports shell as tool_name "Bash" with tool_input.command - the same shape the existing guards already parse - so marker-based git/gh mutation gating is a cheap port that closes the bash hole OpenCode still has (edits-only). DEFERRED with reasons, not forgotten: (a) fr-merged-pr-push-guard needs `gh` and is fail-open on every PR-state ambiguity, so it adds dependency surface for strictly less isolation value; (b) the SessionStart acceptance nag needs a Codex-specific context-INJECTION shape that this session did not verify (the Claude nag emits Claude-specific JSON), and shipping an unverified injection shape would be guessing. Both are named as follow-ups rather than half-built.

<!-- fr:journal kind=decision scope=spec id=d5 created=2026-09-16T07:27:53 -->
### d5 · decision · d5: register hooks at USER level with absolute paths; do NOT ship a project-level .codex/hooks.json

`fr codex install` copies the hook tree to $CODEX_HOME/super-fr-hooks/ and merges entries into ~/.codex/hooks.json with ABSOLUTE command paths - the proven `fr hermes install` pattern, which requires no assumption about a hook working directory. A project-level <repo>/.codex/hooks.json would need a relative or interpolated command path whose resolution base this session could NOT verify, and per v5 it additionally loads only when the project is trust_level=trusted. Shipping an unverified path shape that fails silently is worse than not shipping it. The project-level option is documented in the README as operator-owned rather than generated.

<!-- fr:journal kind=decision scope=spec id=d6 created=2026-09-16T07:27:55 -->
### d6 · decision · d6: no-JSON-parser fails CLOSED (explicit refusal), not open - and "jq absent" alone must stay fully armed

The task brief asked for a test covering "fail-open when jq is absent". Building that literally would ship a test weaker than its name: the shared library resolves python3 FIRST and jq only as a fallback, so with jq removed and python3 present the hook is still fully armed and still denies. Naming that "fail-open" would assert nothing. Two honest tests replace it: (1) jq absent + python3 present -> the gate still DENIES (guard stays armed); (2) NO parser resolvable at all (FR_PYTHON_CANDIDATES= FR_JQ_CANDIDATES=) -> an EXPLICIT refusal is emitted. Posture (2) follows the Hermes hooks, which were hardened to fail closed precisely because a PATH-missing jq once aborted the script before it printed a decision and SILENTLY DISARMED the guards. A visible refusal beats a silent bypass. Divergence from the brief is deliberate and recorded here.

<!-- fr:journal kind=decision scope=spec id=d7 created=2026-09-16T07:27:57 -->
### d7 · decision · d7: relative apply_patch paths MUST be resolved against the payload cwd before the decision call

Correctness trap at the heart of this feature. fr_isolation_decide_edit() returns ALLOW for any non-absolute path (case $_fr_file in /*) ;; *) return 0), because a relative path would otherwise resolve against the wrong repo. apply_patch paths are repo/cwd-relative. So an entrypoint that passed them through verbatim would ALLOW EVERY PATCH while appearing to work - a fully disarmed gate that no naive test would catch. The Codex entrypoint therefore joins each extracted path onto the payload cwd before calling the library, and a dedicated test asserts a relative-path patch DENIES.

<!-- fr:journal kind=decision scope=spec id=d8 created=2026-09-16T07:27:59 -->
### d8 · decision · d8: a patch is atomic - ANY blocked path denies the whole apply_patch

apply_patch carries multiple files per call (Add File / Update File / Delete File / Move to). Codex offers no partial-apply, so a per-path allow/deny cannot be expressed in the response. The gate extracts every target path, evaluates each through the shared library, and denies the entire call if any one path is blocked, naming the offending path in the reason. A mixed patch (one .fr-isolation-allow-exempt path + one tracked path) must therefore DENY - tested explicitly, since the tempting bug is to allow when the FIRST path passes.

<!-- fr:journal kind=decision scope=spec id=d9 created=2026-09-16T07:28:01 -->
### d9 · decision · d9: minor version bump 4.4.0 -> 4.5.0

AGENTS.md release policy: bump for packages/*/src/** and plugins/super-fr/rules/**, both of which this PR touches, so the version-bump-required CI gate applies. Minor rather than patch per the same policy own example - "Minor = user-visible workflow additions (new subcommand/skill/mandatory behavior) - e.g. the OpenCode-support release". A new harness plus a new `fr codex` subcommand is the same class of change.

<!-- fr:journal kind=decision scope=spec id=d10 created=2026-09-16T07:28:03 -->
### d10 · decision · d10: DEFER Codex phase-execution dispatch in fr-goal; both SKILL.md files are at the 120-line cap

Codex reports multi_agent=stable/true, so a Codex branch for fr-goal step 6 (the Hermes delegate_task analog) is feasible - but it is a separate capability from harness delivery, and tests/unit/test_skill_validation.py::test_under_120_lines enforces a hard 120-line cap that BOTH fr-goal/SKILL.md and fr-isolation/SKILL.md are already exactly at. Adding a harness branch means compressing existing prose, which is spec-worthy work of its own. In scope here: a single compressed Codex line in fr-isolation status-line section (required by the brief). Out of scope: fr-goal phase dispatch under Codex. Recorded as a follow-up.

<!-- fr:journal kind=decision scope=spec id=d11 created=2026-09-16T07:28:05 -->
### d11 · decision · d11: brainstorm Q&A self-answered - no operator available (deviation, declared)

fr-goal step 1 specifies ONE batched AskUserQuestion and treats an unanswered gate as a hard stop. This run was dispatched explicitly autonomous with no operator to answer, so the operator-owned decisions were resolved from the dispatch brief and recorded as d1-d10 above rather than asked. Declaring the deviation at the moment it is taken, per the operator standing rule against silently converting interactive work into headless execution. Every decision above is reversible by the operator at PR review; the ones most worth a second opinion are d3 (rules land in the user global AGENTS.md), d4 (deferred guards) and d5 (no project-level hooks.json).

<!-- fr:journal kind=finding scope=spec id=r1 created=2026-09-16T07:31:40 state=fixed -->
### r1 · finding [fixed] · r1: the AGENTS.md rules block CANNOT inline rule bodies - measured 90% budget consumption

Spec-review, measured against codebase reality rather than estimated. The 4 shipped rules concatenate to 13,066 bytes; the existing Hermes-style full-inline block (.hermes/SOUL.d/super-fr-rules.md) is 13,129 bytes; super-fr own AGENTS.md is 16,365 bytes. project_doc_max_bytes defaults to 32,768 and discovery STOPS at the cap. Full inline + super-fr own AGENTS.md = 29,494 bytes = 90% of the budget IN SUPER-FR OWN REPO, and any consuming repo with a larger AGENTS.md would have its own instructions silently truncated. The draft §4.B claimed a test-enforced 8 KiB budget while also inlining bodies - internally contradictory, since full inline is 13 KiB and cannot fit 8 KiB. FIXED: §4.B now installs full rule bodies as FILES under $CODEX_HOME/rules/super-fr/ (zero prompt cost) and reduces the AGENTS.md block to a compact POINTER block inlining only the unsafe-to-discover-late invariants, test-enforced at <= 2 KiB (~6% of budget). §3.2 now carries the measurement table and §5 the residual risk.

<!-- fr:journal kind=finding scope=spec id=r2 created=2026-09-16T07:31:43 state=fixed -->
### r2 · finding [fixed] · r2: shipped rule set is FOUR rules behind an allowlist, not three

Spec-review against scripts/sync-hermes.py. The draft said "the three shipped plugin rules ... plus fr-worktree-override", which is both miscounted and misses the mechanism. Reality: SHIPPED_RULE_NAMES = (fr-isolation-required, fr-plan-override, fr-worktree-override, no-claude-p-batch) - four - and it is an explicit ALLOWLIST whose documented purpose is that "a new maintainer-only rule dropped into plugins/super-fr/rules/ never silently leaks into a consumer SOUL.md". install.sh copies exactly those four to ~/.claude/rules (lines 503-511). FIXED: §4.B now says four, names them, and states that sync-codex.py reuses the same allowlist rather than globbing the rules dir - otherwise the repo-local maintainer rules (acceptance-matrix, artifact-versioning, explainers-currency) could leak into a consumer global instructions.

<!-- fr:journal kind=review scope=spec id=r3 created=2026-09-16T07:31:45 -->
### r3 · review · r3: spec-review - claims checked against codebase reality

Checked every file/helper the spec names, not just the prose. CONFIRMED to exist and to work as the spec assumes: plugins/super-fr/hooks/lib/fr-isolation-decision.sh with fr_isolation_decide_edit/decide_cwd and the relative-path ALLOW behaviour d7 depends on; the Hermes hook entrypoints as the thin-adapter precedent; scripts/sync-opencode.py and sync-hermes.py as generator precedent (canonical/mirror/find_drift/sync + --check); packages/fr/src/fr/hermes.py and commands/hermes_cmd.py as the install-command precedent; fr.cli app.add_typer registration; install.sh opt-in gating and uninstall-only-our-files pattern; tests/unit/test_skill_validation.py::test_under_120_lines (hard 120 cap, and fr-isolation/SKILL.md + fr-goal/SKILL.md are BOTH exactly at 120); test_install_copies_rules.py and test_hermes_docs.py as the doc/install guard style; docs/acceptance/matrix.yaml schema. ALSO CONFIRMED: .agents/ and .codex/ are NOT gitignored (git check-ignore clean), so the generated mirror will actually commit - a silent-no-op risk ruled out. `fr validate artifacts` passes (21 artifacts). Two defects found and fixed (r1, r2). Spec otherwise reads back true against the Q&A decisions d1-d11.
