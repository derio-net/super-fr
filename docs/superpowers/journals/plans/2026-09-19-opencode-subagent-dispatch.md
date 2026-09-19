# Journal: 2026-09-19-opencode-subagent-dispatch

<!-- fr:journal kind=discovery scope=plan id=x-plan1 created=2026-09-20T00:01:09 -->
### x-plan1 · discovery · fr plan create silently drops a phase header's tier:

The phases-file schema `fr plan create --help` documents is {number, title, tag, depends_on, skeleton, tasks} — `tier` is not in it, and a `tier:` key present in the phases file is dropped without a warning. `fr.types.PhaseHeader.tier` accepts it fine, so the key was re-added directly to 01-05.yaml after create and self-review still passes. Worth a follow-up in fr itself: fr-goal §5 resolves each phase`s model from `tier`, so a plan authored through the documented path gets no tiering at all, silently. Not fixed here — out of scope for #494, and a silent drop deserves its own loud failure rather than a rider.

<!-- fr:journal kind=discovery scope=plan id=p1-t2-s1-live-smoke created=2026-09-20T00:07:21 phase=1 -->
### p1-t2-s1-live-smoke · discovery · opencode agent list confirms fr-phase-executor registers with the closed permission translation (phase 1)

Ran `opencode agent list` from the worktree against opencode 1.18.31 after `uv run scripts/sync-opencode.py` + `--check` (clean) + `git add .opencode/agent/fr-phase-executor.md`.

Registration line: `fr-phase-executor (subagent)`.

Resolved permission entries for that agent (filtered to the four keys the translation cares about — the full dump also lists many `external_directory` patterns under the operator's home, omitted here per .claude/rules/third-party-privacy.md):

- `edit`: allow
- `bash`: allow
- `task`: deny
- `webfetch`: deny

Matches the closed translation exactly: `tools: Read, Edit, Write, Bash, Grep, Glob` -> edit/bash allow, plus the explicit task/webfetch denies the canonical tools: line withholds. task: deny confirmed live — the load-bearing guarantee that this agent cannot dispatch further subagents.

<!-- fr:journal kind=finding scope=plan id=p1-t3-s1-preexisting-failures created=2026-09-20T00:10:25 phase=1 state=open -->
### p1-t3-s1-preexisting-failures · finding [open] · Two pytest failures at P1.T3.S1 quality gate pre-date phase 1 and are out of scope (phase 1)

Full `uv run pytest -q --no-cov` run at P1.T3.S1 shows 2 failed, 3226 passed, 85 skipped. Both failures reproduce identically with all phase-1 changes stashed (verified by `git stash push -u` then re-running just these two tests, then `git stash pop`), so neither is caused by this phase:

1. `tests/unit/test_validate_artifacts.py::test_this_repos_own_artifacts_are_structurally_valid` — fails because `docs/superpowers/specs/2026-09-19-opencode-subagent-dispatch-design.md` itself has a duplicated `## Implementation Plans` section heading (present twice near the end of the spec file, lines ~329 and ~335 in this checkout). Not touched by phase 1 — a spec-authoring defect from when the spec/plan were created, orthogonal to the sync-opencode.py work this phase does.

2. `tests/integration/test_install_bridge.py::test_install_bridge_flag_writes_wrapper` — fails in this devcontainer because the `fr` uv tool installed at `/home/vscode/.local/share/uv/tools/fr` cannot import `fr_vk.bridge` (environment/tool-install state, not a code change). Unrelated to scripts/sync-opencode.py or the agents mirror.

Recording as open findings rather than fixing here: both are outside Phase 1's scope (agents-as-fourth-sync-category), and #1 in particular likely needs a decision about which duplicate section to keep or whether to relax the validator, which is a spec-authoring call, not an implementation one.

<!-- fr:journal kind=finding scope=plan id=r-p1-f1 created=2026-09-20T00:20:43 phase=1 state=fixed -->
### r-p1-f1 · finding [fixed] · The closed permission translation silently dropped unknown tool names (phase 1)

Phase-1 review. `_agent_permission` looked each tool up in a map of the three it knew and dropped everything else. A vocabulary that drops what it does not recognise is not closed — a new Claude Code tool, or a typo, would vanish and the mirror would be quietly LESS capable than the agent it claims to mirror, with nothing reporting it. Demonstrated: `tools="Bash, Edt"` -> `{bash: allow, task: deny, webfetch: deny}`, the typo indistinguishable from a deliberate omission. FIXED: `_TOOL_PERMISSIONS` now enumerates every tool name a canonical agent may carry, including the ones that map to `None` because OpenCode has no separate key for them (Read/Grep/Glob/TodoWrite); an absent name raises `AgentTranslationError` naming the file and the tool. This follows the repo`s own standing pattern — `fr.harness.model` refuses an unknown harness key, `fr.capabilities` is closed, `_StrictLoader` refuses a duplicate YAML key — all for this same class of silent loss. Test: test_an_unknown_tool_name_is_refused_rather_than_dropped, test_every_known_tool_maps_or_is_explicitly_implicit.

<!-- fr:journal kind=finding scope=plan id=r-p1-f2 created=2026-09-20T00:20:44 phase=1 state=fixed -->
### r-p1-f2 · finding [fixed] · A constant deny overrode a granted tool — the allowlist inverted (phase 1)

Phase-1 review, found while proving f1. The default denies were applied with `permission.update(_PERMISSION_DENIES)` AFTER the mapped grants, so a deny always won. Demonstrated: a canonical `tools:` line GRANTING WebFetch produced a mirror DENYING it — an inversion of the allowlist the translation exists to carry. Latent today only because no tool mapped to `task`/`webfetch`; f1`s fix adds exactly such mappings, so the two findings compound. FIXED: the denies are DEFAULTS applied with `setdefault`, filling a gap the allowlist left and never overriding a grant. Test: test_a_granted_tool_beats_the_default_deny, plus test_the_shipped_agent_still_denies_task_and_webfetch as the regression guard that fr-phase-executor keeps both denies. Confirmed no behaviour change for the shipped agent: `.opencode/agent/fr-phase-executor.md` is byte-identical after the fix, and `sync-opencode.py --check` is clean.

<!-- fr:journal kind=finding scope=plan id=r-p1-f3 created=2026-09-20T00:20:44 phase=1 state=fixed -->
### r-p1-f3 · finding [fixed] · The spec carried a duplicated '## Implementation Plans' heading — mine, not pre-existing (phase 1)

Phase-1 review. `fr validate artifacts` failed on docs/superpowers/specs/2026-09-19-opencode-subagent-dispatch-design.md: `## Implementation Plans` at both line 329 and 335, the second an empty leftover from plan scaffolding (the section was appended, the plan folder was then rebuilt to fix the task shape, and the append repeated). The phase-1 executor reported this as "pre-existing and unrelated", verified by `git stash`ing the phase-1 changes — but that method cannot distinguish "pre-existing on main" from "introduced EARLIER ON THIS BRANCH", which is what this was. FIXED by the orchestrator: trailing empty duplicate removed, `fr validate artifacts` now reports 23 artifacts all structurally valid. Method note for later phases: scope a failure by diffing against `origin/main`, not by stashing the current phase.

<!-- fr:journal kind=finding scope=plan id=r-p1-f4 created=2026-09-20T00:21:06 phase=1 state=refuted -->
### r-p1-f4 · finding [refuted] · Three suite failures on this machine are pre-existing on main and environment-shaped, not regressions (phase 1)

Phase-1 review. The full suite fails three tests locally; `git diff origin/main --stat` shows this branch touches none of the files involved, and all three have a diagnosed environmental cause. REFUTED as a defect of this work; recorded because the executor reported a DIFFERENT pair of failures and called them "environment state", which is a hand-wave that would have hidden a real one.

(1) test_run_workspace.py::test_a_forged_worktree_marker_in_a_plain_directory_is_refused and (2) ::test_an_external_marker_without_container_evidence_is_refused — the CLI behaves correctly (exit 2, right message); the tests assert on an UNWRAPPED substring of a rich-rendered message that embeds `tmp_path`. On macOS that path is `/private/var/folders/dr/<random>/T/pytest-of-<user>/...`, long enough to push rich`s wrap point into the middle of the asserted phrase — the captured output literally reads `is not a linked git \nworktree`. Proof: `pytest tests/unit/test_run_workspace.py --basetemp=/tmp/sb` -> 9 passed. On Linux CI the tmp path is short, so CI is green and the defect is invisible there.

(3) test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable — expects "no workflow shapes found", exit 1; gets `fr-goal: ok`, exit 0. The test neutralises `FR_SHIPPED_WORKFLOWS_DIR` and the wheel-internal copy, but NOT the fourth resolution source, the Claude Code marketplace clone (`~/.claude/plugins/marketplaces/derio-net--super-fr/plugins/super-fr/workflows/fr-goal.yaml`). So a test whose whole purpose is "`--all` must not pass vacuously" is itself vacuous on any machine with super-fr installed, and only passes where nothing is installed.

All three deserve a follow-up issue of their own — a test that is green only on CI`s platform and only on a machine without the product installed is the same "green report over a state nobody verified" class this repo keeps closing. NOT fixed here: out of scope for #494, and rolling them in would hide them.

<!-- fr:journal kind=finding scope=plan id=r-p1-f5 created=2026-09-20T00:21:06 phase=1 state=refuted -->
### r-p1-f5 · finding [refuted] · The mirrored agent body carries Claude-Code-only guidance an OpenCode reader cannot act on (phase 1)

Phase-1 review. The generated `.opencode/agent/fr-phase-executor.md` body tells its reader what to do if dispatched WITH `isolation: "worktree"` — a Claude Code dispatch argument OpenCode does not have. REFUTED as a defect: the body is carried verbatim by design (spec §3.B), and the phase-1 test asserts that byte-identity precisely so the two cannot drift; forking the prose per harness is what spec §3.C explicitly rejected for skills, for the same reason. The honest fix, if it is ever worth making, is a scoped clause in the CANONICAL agent naming each harness — the shape `fr.harness.prose` already requires of skills — which would then ride into every mirror unchanged. Noted as a follow-up candidate, deliberately not done here: the agent files are not currently scanned by `scan_prose`, so extending that convention to them is its own decision.

<!-- fr:journal kind=finding scope=plan id=p1-t3-s1-preexisting-failures-resolved created=2026-09-20T00:25:37 state=fixed resolves=p1-t3-s1-preexisting-failures -->
### p1-t3-s1-preexisting-failures-resolved · finding [fixed] · resolves p1-t3-s1-preexisting-failures: Two pytest failures at P1.T3.S1 quality gate pre-date phase 1 and are out of scope

Superseded by r-p1-f3 and r-p1-f4, which re-diagnosed both claims. Claim 1 (duplicate '## Implementation Plans') was NOT pre-existing — it was introduced earlier on this branch during plan scaffolding; stashing the phase's own changes cannot distinguish that from pre-existing-on-main, which is why it read as unrelated. Fixed by the orchestrator; fr validate artifacts now reports 23 artifacts all valid. Claim 2 (test_install_bridge) does not reproduce on the host at all and passes standalone; the three failures that DO reproduce are diagnosed in r-p1-f4 as rich line-wrapping over a long macOS tmp_path (proved by --basetemp=/tmp/sb) and the Claude Code marketplace clone acting as an unneutralised fourth workflow-resolution source. Both are pre-existing on origin/main and out of scope, but for stated reasons rather than as environment state.

<!-- fr:journal kind=discovery scope=plan id=p2-t2-s1-live-smoke created=2026-09-19T22:31:50 phase=2 -->
### p2-t2-s1-live-smoke · discovery · opencode agent list confirms all four tier agents register (phase 2) (phase 2)

opencode agent list (opencode 1.18.31, from the worktree, after `uv run scripts/sync-opencode.py` + `--check` clean) shows all four tier agents registering: fr-phase-executor (subagent), fr-phase-executor-hard (subagent), fr-phase-executor-mechanical (subagent), fr-phase-executor-standard (subagent). Names only recorded per .claude/rules/third-party-privacy.md — the full dump also lists many external_directory entries under the operator home, omitted here.

<!-- fr:journal kind=discovery scope=plan id=p2-t1-s3-no-refactor created=2026-09-19T22:32:01 phase=2 -->
### p2-t1-s3-no-refactor · discovery · no-refactor-because: P2.T1.S3 (phase 2)

GREEN (P2.T1.S2) was written directly as one shared _render_agent(description, body, tools, model, canonical_name) used by both the untiered base file and every per-tier file inside canonical_agents() — there was never a duplicated two-path implementation to collapse. Also added fr.types.PHASE_TIERS (derived via typing.get_args off PhaseHeader.tier, the same technique the test uses independently) as the single-sourced tier vocabulary scripts/sync-opencode.py imports, so a fourth tier needs no edit in the generator. No further refactor found.

<!-- fr:journal kind=finding scope=plan id=r-p2-f1 created=2026-09-20T00:44:09 phase=2 state=fixed -->
### r-p2-f1 · finding [fixed] · The tier derivation only read one of the two shapes PhaseHeader.tier can have (phase 2)

Phase-2 review. `_phase_tiers()` walked `get_args(annotation)` looking for a member that was itself a Literal — which only holds while the annotation is a UNION (`Literal[...] | None`). Drop the `| None`, making `tier` required (a perfectly reasonable schema change), and `get_args` yields the tier STRINGS directly, the loop finds no Literal member, and the module raises `AssertionError("PhaseHeader.tier has no Literal member")` at IMPORT time. `scripts/sync-opencode.py` imports `PHASE_TIERS`, so the whole sync script would die with a message that tells the reader nothing about what to do. FIXED: renamed to a public, parameterised `fr.types.phase_tiers(annotation=None)` that handles the bare Literal as well as the union, and raises `TypeError` naming the annotation and pointing at itself. Test: tests/unit/test_phase_tiers.py, parameterised over four spellings — `Optional[L]`, `Union[L, None]`, bare `L`, and `L | None`. The first two carry `# noqa: UP045/UP007` with a stated reason: ruff would rewrite them to `X | None` and collapse the coverage, because `typing.Union` and `types.UnionType` are different runtime objects and pydantic may hand back either.

<!-- fr:journal kind=finding scope=plan id=r-p2-f2 created=2026-09-20T00:44:09 phase=2 state=fixed -->
### r-p2-f2 · finding [fixed] · Two canonical agents could claim one mirror filename, and the dict kept the last writer (phase 2)

Phase-2 review. `canonical_agents()` builds `result[f"{stem}-{tier}"]` by plain assignment. Every canonical agent also claims `<name>-mechanical|-standard|-hard`, so a canonical `fr-phase-executor-hard.md` sitting beside `fr-phase-executor.md` produces the key `fr-phase-executor-hard` twice — and the dict silently keeps whichever came last, so one agent never reaches `.opencode/agent/` at all. Demonstrated by key-set collision before fixing. This is the same silent-loss class as r-p1-f1, and the second time this generator has preferred a quiet winner to a loud refusal. FIXED: a `claim()` helper records which canonical file claimed each generated name and raises `AgentTranslationError` naming BOTH sides plus the tier-expansion rule that caused the overlap — the generator does not pick a winner. Test: test_a_canonical_agent_colliding_with_a_generated_tier_name_is_refused. Latent today (one canonical agent ships), which is exactly why it was worth closing before a second one exists.

<!-- fr:journal kind=discovery scope=plan id=4919945c2f82 created=2026-09-20T00:53:30 -->
### 4919945c2f82 · discovery · no-refactor-because: P3.T1.S3

The skills, commands, and agents delivery loops have sufficiently different logic (skills: mkdir + copy; commands: copy from mirror; agents: derive tier + resolve model + awk-rewrite) that a shared shell function would not improve clarity. Each loop's purpose is clear as-is.

<!-- fr:journal kind=finding scope=plan id=r-p3-f1 created=2026-09-20T01:01:36 phase=3 state=fixed -->
### r-p3-f1 · finding [fixed] · The whole point of phase 3 — install-time model resolution — had no test, and the file claimed it did (phase 3)

Phase-3 review, and the most serious finding of the run. `tests/integration/test_install_opencode_agents.py` opened with "Verified: ... a seeded ~/.config/fr/models.yaml binding appears as `model:` on each TIER file and NOT on the base file". Nothing asserted it. The only model-related test, `test_tiered_agents_lack_model_when_fr_not_installed`, asserted the OPPOSITE — no model on any file — and justified it as "expected behavior for stubbed tests". So a coverage hole was written up as a feature, and install.sh`s awk rewrite, the entire deliverable of the phase, had never once run with a non-empty model. It could have been broken outright with every test green and the file`s own docstring vouching for it.

This is the defect class this repo keeps closing: a green report over a state nobody verified. It is also the third phase running in which a report`s confident scoping had to be re-checked against the artifact.

FIXED: three tests added, driven by an `fr` stub on the sandbox PATH that answers `models resolve --harness opencode --tier <t>` and logs its argv — `fr models resolve``s own correctness is unit-tested in fr, so what install.sh owes is narrower: that it CALLS it, once per tier with the right arguments, and inserts what comes back where the generator promises the anchor is.
- test_a_resolved_binding_lands_as_model_on_each_tier_file_only — each tier file carries `model: <resolved>` immediately after `mode: subagent`, exactly one model line, and the base file none.
- test_install_asks_fr_for_every_tier_and_only_for_tiers — exactly three resolves, one per tier, none for the base, all `--harness opencode`.
- test_an_unbound_tier_inherits_rather_than_pinning_an_empty_model — an unbound tier gets no key at all, never an empty one.

NON-VACUITY PROVEN by mutation: changing the awk anchor from `/^mode: subagent$/` to a string that cannot match makes 2 of the 3 fail; install.sh was then restored byte-exact (diff -q confirmed). The implementation turned out to be correct — the defect was the absent test and the docstring that covered for it.

Also corrected: the module docstring now describes what is actually asserted, and the degradation test is renamed `test_no_model_is_pinned_when_fr_is_not_on_path_at_all` with its role stated, so it reads as the degradation path it is rather than as coverage of the feature.
