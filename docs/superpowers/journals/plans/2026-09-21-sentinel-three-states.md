# Journal: 2026-09-21-sentinel-three-states

<!-- fr:journal kind=discovery scope=plan id=6b0b933da713 created=2026-09-21T16:59:25 phase=4 -->
### 6b0b933da713 · discovery · no-refactor-because P4.T1 (phase 4)

Phase 4 is release bookkeeping (matrix status, mirrors, version bump, gate run); it writes no logic to refactor.

<!-- fr:journal kind=discovery scope=plan id=8db2ec540344 created=2026-09-21T17:02:38 phase=1 -->
### 8db2ec540344 · discovery · P1: stamp_sentinel_workspace + attach stamping landed (phase 1)

types.py now imports fr.artifacts.atomic.write_text_atomic; stamp is cache-relative (posix), no-op on missing/malformed sentinel or worktree outside ~/.cache/fr. Hook header documents optional workspace field. Refactor was doc-only (S3).

<!-- fr:journal kind=review scope=plan id=rev-p1 created=2026-09-21T17:03:16 phase=1 -->
### rev-p1 · review · Phase 1 review (phase 1)

Read diff vs spec 2.A. No findings: relative path (both sides resolved), atomic write, no-op on missing/malformed/outside-cache, other keys preserved, 7 tests pass.

<!-- fr:journal kind=discovery scope=plan id=2025ec65361e created=2026-09-21T17:17:04 phase=2 -->
### 2025ec65361e · discovery · P2: three-state heal + #432 denials landed in fr-isolation-guard.sh (phase 2)

Count heal (`grep -c '^worktree '` == 1) deleted; replaced by a per-sentinel read of `.workspace` (jq) resolved against $HOME/.cache/fr, with dir-exists AND listed-linked-worktree, both sides pwd -P'd (the worktree-list paths are resolved line by line, so a symlinked HOME still classifies live as live). Failed `git worktree list` = unknown -> deny. Orphaned removes ONLY this session's sentinel. Denials: new leading branch when the cd target is not a directory ("no longer exists", names the path, points at `fr isolation status` + `up --branch`, never mentions --all); standard denial now leads with status/up and keeps `down --all` only as a warned last resort naming its blast radius. Comments updated in the guard, fr-pipeline-sentinel.sh, clear_repo_sentinels()'s docstring and fr-isolation SKILL.md; test setups that kept a worktree alive for the count-heal now say why they are belt-and-braces. 91 tests in test_hooks_guard.py pass; shellcheck -x reports only the pre-existing SC1091.

<!-- fr:journal kind=finding scope=plan id=d8ac0b68f6bc created=2026-09-21T17:17:23 phase=2 state=open -->
### d8ac0b68f6bc · finding [open] · docs/explainers/fr-isolation.html still describes the count-based self-heal, and this repo cannot regenerate it (phase 2)

The published page (https://derio-net.github.io/super-fr) says: 'self-heal — If no linked worktree survives, the companion Bash guard fails open and clears its stale sentinel'. Phase 2 makes that false: the heal is per-sentinel and a worktree-less repo no longer heals anything. Per .claude/rules/explainers-currency.md this PR owes an update — but fr-isolation.html is one of the two pages with NO committed .md source (known gap #1), and the rule forbids hand-editing a rendered page (it is overwritten by the next regeneration and carries a do-not-hand-edit banner). So the page is KNOWINGLY behind and the PR body must say so. Options for whoever closes this: bring the source in-repo (the gap the rule already records as owed), or have the source holder re-render the one paragraph. The heading-level tripwire cannot catch it — prose inside an unchanged section.

<!-- fr:journal kind=finding scope=plan id=9fb4c022ffb2 created=2026-09-21T17:17:24 state=open -->
### 9fb4c022ffb2 · finding [open] · Skill mirrors are stale on purpose until P4.T1.S2 runs BOTH sync scripts

Phase 2 edited plugins/super-fr/skills/fr-isolation/SKILL.md (the orphaned-sentinel recovery bullet), and the dispatch brief reserves the sync scripts for phase 4. So test_tripwire_opencode_skills_sync.py and test_tripwire_hermes_skills_sync.py are RED on this branch by design, and a full-suite run in phase 3 will show exactly two unexplained failures. Do not re-diagnose them: P4.T1.S2 runs scripts/sync-opencode.py AND scripts/sync-hermes.py (both — AGENTS.md records three sessions that ran only the first) and commits .opencode/skills/ + .hermes/skills/. The skill is back at exactly 120 lines, the cap test_skill_validation.py enforces.

<!-- fr:journal kind=review scope=plan id=rev-p2 created=2026-09-21T17:25:33 phase=2 -->
### rev-p2 · review · Phase 2 review (phase 2)

Read guard diff vs spec 2.B/2.C. Findings raised: d8ac0b68f6bc (explainers page describes count heal). No logic defects: per-sentinel decision, pwd -P both sides, failed worktree list denies, only this sentinel removed, cd-target-gone branch precedes cross-repo branches, down --all only as warned last resort.

<!-- fr:journal kind=finding scope=plan id=d8ac0b68f6bc-resolved created=2026-09-21T17:25:40 state=refuted resolves=d8ac0b68f6bc -->
### d8ac0b68f6bc-resolved · finding [refuted] · resolves d8ac0b68f6bc: docs/explainers/fr-isolation.html still describes the count-based self-heal, and this repo cannot regenerate it

docs/explainers/fr-isolation.html has no committed .md source (explainers-currency known gap 1) and hand-editing a rendered page is forbidden; a patch bump does not trigger the rule. Disclosed in the PR body: the published page still describes the count heal.

<!-- fr:journal kind=discovery scope=plan id=ccd8ff87c958 created=2026-09-21T17:30:03 phase=3 -->
### ccd8ff87c958 · discovery · P3: verify-merge reaped fallback landed (phase 3)

LocalWorktreeDevcontainerTarget.verify_merge_reaped + shared _verdict (verify_merge delegates; verdict logic not forked). Ref resolved local, origin/<b>, one targeted fetch, else IsolationError naming ref -> CLI exit 1. Old 'ghost branch exits 2' test replaced: explicit --branch with no state is now the reaped path. SKILL.md fr-goal line left as is (does not imply live workspace).
