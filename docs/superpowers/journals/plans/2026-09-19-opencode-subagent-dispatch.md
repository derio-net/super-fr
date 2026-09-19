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
