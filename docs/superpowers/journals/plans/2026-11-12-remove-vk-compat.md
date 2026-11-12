<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-remove-vk-compat

<!-- fr:journal kind=discovery scope=plan id=p1-github-rest-capture-keeps-old-env-name created=2026-11-12T16:58:57+00:00 phase=1 -->
### p1-github-rest-capture-keeps-old-env-name · discovery · A recorded GitHub PR capture still names VK_REPO_ROOT (phase 1)

tests/fixtures/github_rest/repo_pulls_1080_files-per_page-100-page-1.json is a capture of a historical PR's file list and contains VK_REPO_ROOT. Captures are never rewritten, so the no-VK-env-names tripwire in tests/unit/test_vk_compat_removed.py skips tests/fixtures/github_rest.

<!-- fr:journal kind=discovery scope=plan id=p1-retired-plugin-seed-counts-as-sibling created=2026-11-12T16:58:57+00:00 phase=1 -->
### p1-retired-plugin-seed-counts-as-sibling · discovery · Replacing the seeded superpowers-for-vk id with retired-plugin made it a sibling (phase 1)

With the installer's sibling grep no longer excluding the vk plugin id, a seeded retired-plugin@derio-net entry reads as a sibling registration and test_no_sibling_note_when_only_our_own_ids_were_purged failed. The seed entry and its assertion were dropped instead of renamed; the bare-org purge is still covered by the super-fr and super-fr-dispatch ids.

<!-- fr:journal kind=discovery scope=plan id=p1-acceptance-rows-owed-phase-2 created=2026-11-12T16:58:57+00:00 phase=1 -->
### p1-acceptance-rows-owed-phase-2 · discovery · Three acceptance rows for this feature are still not-implemented (phase 1)

fr acceptance check lists installer-names-no-vk-residue, init-migrate-removed and isolation-up-requires-branch as not-implemented. Phase 1 added the unit tests that verify them in tests/unit/test_vk_compat_removed.py, but moving them needs fr acceptance set-status; this was not in the phase's steps, so the orchestrator or phase 2 should do it.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-12T16:58:57+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

deletions only

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-12T16:58:57+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

mechanical rename

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-12T16:58:57+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

deletions only

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-12T18:06:51+00:00 phase=1 -->
### review-p1 · review · Phase 1 code review, seven findings, all in scope (phase 1)

A separate reviewer read the phase-1 diff against the spec (R1-R8, R15, R17-R19),
ran the three mirror checks, `fr docs check`, `fr acceptance check`, the new test
file and the OpenCode plugin's tests. R1-R8, R15, R18 and R19 held. R17 did not:
three emitted remedies still named a bare `fr isolation up`. The executor's two
deviations (the `github_rest` capture skip, the dropped installer seed) were judged
to lose no coverage.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-12T18:06:51+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Three hook remedies still recommend a bare `fr isolation up` (phase 1)

`plugins/super-fr/hooks/fr-isolation-required.sh`, the cross-repo sentence of
`fr-isolation-guard.sh` and its port `packages/fr-opencode-plugin/src/guard.ts`;
`tests/fixtures/hooks/guard-verdicts.yaml` pinned the bare form ten times.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-12T18:06:51+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · The R17 tripwire could not see the Claude Code hooks or shell-escaped backticks (phase 1)

`REMEDY_FILES` omitted the two Claude Code hooks and `guard.ts`, and the regex
missed the `\`` form those hooks write.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-12T18:06:51+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · The amended row vk-legacy-fallbacks-removed contradicted R2 (phase 1)

It still said `~/.config/vk/secrets` mounts no longer resolve, and its note cited
the deleted hard-error test.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-12T18:06:51+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · The isolation rule and the phase-executor guard gave `fr isolation up --repo <path>` with no --branch (phase 1)

`plugins/super-fr/rules/fr-isolation-required.md`, its repo mirror under
`.claude/rules/`, and the deny reason of `fr-phase-executor-guard.sh`.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-12T18:06:51+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · _UP_REMEDY sat between the fr-archive comment and the constant it documents (phase 1)

`packages/fr/src/fr/isolation/local.py`.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-12T18:06:51+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · Small nits in the new tests and two docstrings (phase 1)

A leftover `test_smoke`, mid-file imports, a docstring reflow in `trigger.py`, a
placeholder in two descriptive docstrings, and two installer tests named for a
cleanup step that no longer exists.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-12T18:06:51+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · .test_durations not refreshed (phase 1)

Ten entries for deleted tests, none for the new test file.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-12T18:06:51+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Three hook remedies still recommend a bare `fr isolation up` (phase 1)

All three messages name `--branch`; the fixture was re-captured with
`capture_guard_verdicts.py`, never edited.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-12T18:06:51+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: The R17 tripwire could not see the Claude Code hooks or shell-escaped backticks (phase 1)

Three tests replace the file list for hooks: one reads each hook's non-comment
lines, one reads every captured deny reason in `guard-verdicts.yaml`, one reads the
rule and its mirror. The captured-reason test was red before the re-capture.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-12T18:06:51+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: The amended row vk-legacy-fallbacks-removed contradicted R2 (phase 1)

Two more amendments: a reword that drops the secrets-mount clause and says a mount
is followed whatever its path is named, and a set-status at the same status with a
note naming the tests that exist.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-12T18:06:51+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: The isolation rule and the phase-executor guard gave `fr isolation up --repo <path>` with no --branch (phase 1)

Both rule files and the guard's reason name `--branch <branch>`; mirrors regenerated.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-12T18:06:51+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: _UP_REMEDY sat between the fr-archive comment and the constant it documents (phase 1)

Moved above the archive comment.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-12T18:06:51+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: Small nits in the new tests and two docstrings (phase 1)

`test_smoke` removed, imports moved to the top, the reflow repaired, the two
installer tests renamed for what they still assert (user skills are left alone).
The two descriptive docstrings keep `--branch <branch>`: it is accurate, and the
file-list tripwire reads those files whole.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-12T18:06:51+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: .test_durations not refreshed (phase 1)

Refreshed by the full-suite run made after these fixes (`--store-durations`).

<!-- fr:journal kind=decision scope=plan id=p2-unrepairable-is-its-own-report-field created=2026-11-12T19:22:30+00:00 phase=2 -->
### p2-unrepairable-is-its-own-report-field · decision · An unrewritable archived file is reported in MigrationReport.unrepairable, not failed (phase 2)

R12 says an archived file the repair cannot read or rewrite is reported and never holds the
CLI-entry gate, but the gate refuses on any `report.failed` after it migrates. So such paths go
to a new `MigrationReport.unrepairable` field, which leaves `ok` true: `fr migrate artifacts`
prints each one (stderr, "not repaired (archived, left as it is)") and keeps its exit code, and
the gate prints the same line and proceeds. A vetoed (uncommitted) archived file is still a
`failed` hold, as for any path.

<!-- fr:journal kind=decision scope=plan id=p2-repair-check-field created=2026-11-12T19:22:30+00:00 phase=2 -->
### p2-repair-check-field · decision · Repair gained a second optional field, check, for the dry rewrite check (phase 2)

The runner's `_scan_extra` needs the dry rewrite check the plan describes without knowing
`plan_vk_version`, so `Repair` gained `check: Callable[[Path], object] | None = None` beside
`extra_locators`; the vk repair passes `rewritten_text`, the same function `drop_vk_version`
writes, so repairable and rewritten cannot disagree. `CEILING_REPAIR` sets neither.

<!-- fr:journal kind=discovery scope=plan id=p2-plan-migrations-has-no-failure-channel created=2026-11-12T19:22:30+00:00 phase=2 -->
### p2-plan-migrations-has-no-failure-channel · discovery · plan_migrations returns actions only, so the preview's failure is in run_migrations(dry_run=True) (phase 2)

`plan_migrations` returns a tuple of PlannedAction and has never carried failures for any
path. It lists the live and repairable archived carriers; the unrewritable archived file is
reported by `run_migrations(dry_run=True)` (what `fr migrate artifacts` previews with) in
`unrepairable`. Both are tested.

<!-- fr:journal kind=discovery scope=plan id=p2-three-archived-plans-number-phase-zero created=2026-11-12T19:22:30+00:00 phase=2 -->
### p2-three-archived-plans-number-phase-zero · discovery · Three archived plans do not parse on origin/main either (phase 0) (phase 2)

2026-04-11-plugin-canonical-skills, 2026-04-13-workspace-lifecycle-skill-hook and
2026-04-14-archive-and-unified-descriptions have a `00.yaml`; `PhaseHeader.number` is ge=1 on
origin/main too. They are allowlisted by slug with that reason in
ARCHIVED_PLANS_THAT_DO_NOT_PARSE; every other archived v2 plan parses.

<!-- fr:journal kind=discovery scope=plan id=p2-runner-repo-test-names-the-exception created=2026-11-12T19:22:30+00:00 phase=2 -->
### p2-runner-repo-test-names-the-exception · discovery · test_this_repos_own_artifacts_plan_only_safe_actions now admits the one archive repair (phase 2)

The existing runner test asserted no planned action touches the archive; it now allows an
archived action only when its repair is `drop-vk-version`. After this repo's migration no such
action remains, so it is the same assertion in practice.

<!-- fr:journal kind=discovery scope=plan id=p2-migration-preview-33 created=2026-11-12T19:22:30+00:00 phase=2 -->
### p2-migration-preview-33 · discovery · The repo's own migration rewrote exactly 33 archived _meta.yaml files (phase 2)

`fr migrate artifacts` previewed 33 actions, all archived `_meta.yaml` drop-vk-version repairs,
no failures; `--yes` applied them (33 files, 33 deletions, 0 additions). `fr migrate
artifacts` never commits, so the commit was made with the subject and trailer it printed.
`fr validate artifacts` passes (151 artifacts).

<!-- fr:journal kind=discovery scope=plan id=p2-skill-lists-fr-version created=2026-11-12T19:22:30+00:00 phase=2 -->
### p2-skill-lists-fr-version · discovery · The fr-plan skill's field list names fr_version where vk_version stood (phase 2)

`fr_version` is a real `_meta.yaml` field the list omitted, so it replaced the removed key
rather than leaving a gap. The fragment summary also names the VK_INSTALL_SKIP_PREFLIGHT
rename, which the plan's suggested text left out.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-12T19:22:30+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

single-step task: rule paragraph, fragment and page stamps, nothing to clean
