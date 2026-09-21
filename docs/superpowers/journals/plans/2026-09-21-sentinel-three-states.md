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

<!-- fr:journal kind=finding scope=plan id=f-p3-ref created=2026-09-21T17:32:21 phase=3 state=open -->
### f-p3-ref · finding [open] · verify-merge reaped path preferred a possibly-stale local ref (phase 3)

A stale local branch could hide a post-merge push to origin/<b> (the #320 orphan) and read verified. Fixed: origin ref first, then local; red test test_verify_merge_reaped_prefers_origin_ref_over_a_stale_local_one.

<!-- fr:journal kind=finding scope=plan id=f-p3-ref-resolved created=2026-09-21T17:32:22 state=fixed resolves=f-p3-ref -->
### f-p3-ref-resolved · finding [fixed] · resolves f-p3-ref: verify-merge reaped path preferred a possibly-stale local ref

origin/<b> resolved before local; test added

<!-- fr:journal kind=review scope=plan id=rev-p3 created=2026-09-21T17:32:22 phase=3 -->
### rev-p3 · review · Phase 3 review (phase 3)

Raised f-p3-ref (fixed with test). Verdict logic shared via _verdict, not forked; no --branch keeps old error; unresolvable ref exits 1.

<!-- fr:journal kind=finding scope=plan id=9fb4c022ffb2-resolved created=2026-09-21T17:49:45 state=fixed resolves=9fb4c022ffb2 -->
### 9fb4c022ffb2-resolved · finding [fixed] · resolves 9fb4c022ffb2: Skill mirrors are stale on purpose until P4.T1.S2 runs BOTH sync scripts

phase 4 ran both sync scripts; --check green; full suite green (re-run by orchestrator)

<!-- fr:journal kind=review scope=plan id=rev-p4 created=2026-09-21T17:49:45 phase=4 -->
### rev-p4 · review · Phase 4 review (phase 4)

No findings. Re-ran full pytest (4069 passed, 92.35% cov), acceptance check, bump-version --check independently; 3 rows at ci, mirrors synced, 4.13.1 -> 4.13.2.

<!-- fr:journal kind=discovery scope=plan id=d8ac-correction created=2026-09-21T18:45:37 -->
### d8ac-correction · discovery · Correction: d8ac0b68f6bc was closed 'refuted' but is VALID, deferred to https://github.com/derio-net/super-fr/issues/535

The explainer really is stale. It was closed as refuted only because the journal has no deferred state and the gate needs it closed; 'refuted' claims the finding was wrong, which it was not. Tracked in https://github.com/derio-net/super-fr/issues/535.

<!-- fr:journal kind=finding scope=plan id=adv-1 created=2026-09-21T18:45:37 phase=1 state=open -->
### adv-1 · finding [open] · A pipeline-skill reload erased the stamp, so #472 was not fixed in fr-goal's own flow (phase 1)

fr-pipeline-sentinel.sh rewrote the sentinel from scratch on every fr-goal/fr-brainstorming/fr-execute load. fr-goal's order (skill, run start binds+stamps, fr-brainstorming loads) left it fresh for good; a reaped workspace then locked the session out. Reproduced in a sandbox.

<!-- fr:journal kind=finding scope=plan id=adv-1-resolved created=2026-09-21T18:45:37 state=fixed resolves=adv-1 -->
### adv-1-resolved · finding [fixed] · resolves adv-1: A pipeline-skill reload erased the stamp, so #472 was not fixed in fr-goal's own flow

Writer carries a stamp across reloads only for the same repo_root AND a still-existing workspace (a dead stamp is the previous pipeline's and would retire the new one: #529 again). Atomic tmp+mv. tests/unit/test_sentinel_lifecycle.py drives the real hooks.

<!-- fr:journal kind=finding scope=plan id=adv-2 created=2026-09-21T18:45:38 phase=1 state=open -->
### adv-2 · finding [open] · Binding to another repo restamped this repo's sentinel and silently disarmed its live pipeline (phase 1)

attach stamped any worktree it bound. After cd <B> && fr isolation up (allowed by #421), repo A's sentinel named B's worktree, the guard read it as orphaned and deleted it while A's workspace was live. Reproduced.

<!-- fr:journal kind=finding scope=plan id=adv-2-resolved created=2026-09-21T18:45:38 state=fixed resolves=adv-2 -->
### adv-2-resolved · finding [fixed] · resolves adv-2: Binding to another repo restamped this repo's sentinel and silently disarmed its live pipeline

stamp_sentinel_workspace stamps only a worktree whose git common dir matches the sentinel's repo_root; unknown ownership = foreign. Tests in test_sentinel_workspace_stamp.py and test_sentinel_lifecycle.py.

<!-- fr:journal kind=finding scope=plan id=adv-3 created=2026-09-21T18:45:39 phase=2 state=open -->
### adv-3 · finding [open] · fr isolation down still cleared every session's sentinel once zero workspaces remained (#472 third mechanism) (phase 2)

The PR claimed Closes #472 while down's clear_repo_sentinels still removed strangers' FRESH sentinels, disarming pipelines that had not created a workspace yet.

<!-- fr:journal kind=finding scope=plan id=adv-3-resolved created=2026-09-21T18:45:39 state=fixed resolves=adv-3 -->
### adv-3-resolved · finding [fixed] · resolves adv-3: fr isolation down still cleared every session's sentinel once zero workspaces remained (#472 third mechanism)

down now calls clear_workspace_sentinels: only sentinels stamped with the torn-down worktree or of sessions bound to it. down --all stays repo-wide on purpose (explicit, warned last resort). Test: test_down_of_last_workspace_spares_another_sessions_fresh_sentinel.

<!-- fr:journal kind=finding scope=plan id=adv-4 created=2026-09-21T18:45:40 phase=2 state=open -->
### adv-4 · finding [open] · External-mode checkouts would be denied every command once the count heal was gone (phase 2)

A preparer's primary checkout with a mode:external marker has no linked worktree and nothing to stamp, so its sentinel is fresh forever. The count heal had been clearing it by accident.

<!-- fr:journal kind=finding scope=plan id=adv-4-resolved created=2026-09-21T18:45:40 state=fixed resolves=adv-4 -->
### adv-4-resolved · finding [fixed] · resolves adv-4: External-mode checkouts would be denied every command once the count heal was gone

Guard allows when the pipeline repo's own toplevel carries a VALID marker (same predicate as the edit gate: worktree mode cannot pass in a primary checkout, external needs container evidence). TestPipelineRepoThatIsItselfTheWorkspace.

<!-- fr:journal kind=finding scope=plan id=adv-5 created=2026-09-21T18:45:40 phase=2 state=open -->
### adv-5 · finding [open] · Relative cd targets resolved against the hook process's cwd, not the session's (phase 2)

cd tests && ... was judged by whatever tests/ sat beside the hook's own cwd; the gone-path branch and the transition allowance could both misjudge.

<!-- fr:journal kind=finding scope=plan id=adv-5-resolved created=2026-09-21T18:45:41 state=fixed resolves=adv-5 -->
### adv-5-resolved · finding [fixed] · resolves adv-5: Relative cd targets resolved against the hook process's cwd, not the session's

cd_target anchored to the resolved session cwd once, where it is parsed. TestRelativeCdResolvesAgainstTheSessionCwd.

<!-- fr:journal kind=finding scope=plan id=adv-6 created=2026-09-21T18:45:41 phase=3 state=open -->
### adv-6 · finding [open] · verify-merge exited 1 (not verified - recover) for an unresolvable branch ref (phase 3)

fr-goal reads exit 1 as a disproved merge and prescribes cherry-pick/fresh PR; a typo'd branch disproves nothing.

<!-- fr:journal kind=finding scope=plan id=adv-6-resolved created=2026-09-21T18:45:42 state=fixed resolves=adv-6 -->
### adv-6-resolved · finding [fixed] · resolves adv-6: verify-merge exited 1 (not verified - recover) for an unresolvable branch ref

Unresolvable ref exits 2 via _fail. test_verify_merge_reaped_unresolvable_ref_exits_2_no_traceback.

<!-- fr:journal kind=finding scope=plan id=adv-7 created=2026-09-21T18:45:42 phase=1 state=open -->
### adv-7 · finding [open] · Docstring claimed the username never lands in the sentinel file (phase 1)

repo_root, written by the hook, has always been absolute; only the stamp is cache-relative. The unit test asserted the overclaim.

<!-- fr:journal kind=finding scope=plan id=adv-7-resolved created=2026-09-21T18:45:43 state=fixed resolves=adv-7 -->
### adv-7-resolved · finding [fixed] · resolves adv-7: Docstring claimed the username never lands in the sentinel file

Docstring and test now scope the privacy claim to the stamped value.
