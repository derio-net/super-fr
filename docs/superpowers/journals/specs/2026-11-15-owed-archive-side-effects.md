<!-- fr:journal-schema=4 -->
# Journal: 2026-11-15-owed-archive-side-effects

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-15T17:05:43+00:00 input=true -->
### operator-brief · discovery · Operator brief: batch owed-archive (#1400, #1183, #1301, #1184), verbatim

/fr-goal Owed trackers and archive side effects

Batch `owed-archive` of derio-net/super-fr: 4 issues, delivered as ONE pull request.

## super-fr#1400: fr journal resolve closes the owed issue before the resolution reaches main
Still live. `packages/fr/src/fr/commands/journal_cmd.py:582-585` calls `_close_owed_issue` right after the local record commit, on any branch. The docstring at :746 says `The discharge is already recorded`. So the tracker closes before the resolution reaches main, and it stays closed if the PR is abandoned.
Note: The fix amends spec `2026-10-11-debt-engine` R24 (close at merge via a closing ref, or only on the default branch).

## super-fr#1183: a refused archive still writes/stages manual-phase owed entries and files issues, even on the default branch
When there are blockers and no `--force`, `fr archive` calls `_write_manual_owed` (`packages/fr/src/fr/commands/archive_cmd.py:1006-1007`) before printing "refusing to archive" and exiting 2. The owed journal entry is written and `git add`-ed (`:729-734`) with no default-branch check. Still live.
Note: Batch with #1301 (archive side effects with no preview).

## super-fr#1301: fr archive files forge issues but has no dry run
`fr archive` (`packages/fr/src/fr/commands/archive_cmd.py:851-890`) has no `--dry-run` or preview option. Even so, `_owed_step` (`:746`) and `file_open_ends` (`:695`) file forge issues. Still live.
Note: Batch with #1183. Both are about archive side effects with no preview and on refusal.

## super-fr#1184: _existing_owed's 200-issue listing cap can miss an existing marker and file a duplicate
Still live. `_existing_owed` (`packages/fr/src/fr/archive_followups.py:467-473`) lists at most 200 open issues (`gh.list_issues(repo, 'open', 200, ...)`). Past that it can miss an existing owed marker and file a duplicate tracker.
Note: Could use a marker search instead of a capped listing.

## Why these belong together
Tier 2: journal resolve closes the owed issue before the fix reaches main; a refused archive still files issues; archive gets a dry run. journal_cmd.py, archive_cmd.py.

## Delivery rules
- Work on branch `feat/batch-owed-archive`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1400
  Closes derio-net/super-fr#1183
  Closes derio-net/super-fr#1301
  Closes derio-net/super-fr#1184
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Never add the `approved-fr` label: it is the operator's approval to merge, and fr voids it on your next push.

<!-- fr:journal kind=decision scope=spec id=d1-close-at-merge created=2026-11-15T17:05:43+00:00 decided_by=operator -->
### d1-close-at-merge · decision · #1400: owed issue closes at merge

Operator chose: off the default branch resolve closes nothing and deliver's PR body carries a Closes line; on the default branch it closes at once. Amends debt-engine R24.

<!-- fr:journal kind=decision scope=spec id=d2-refusal-writes-nothing created=2026-11-15T17:05:43+00:00 decided_by=operator -->
### d2-refusal-writes-nothing · decision · #1183: a refused archive writes nothing

Operator chose: exit-2 refusal writes, stages and files nothing; held (--branch) / skipped (--all) plans still record R22 owed entries, except on the default branch, where they print what they would record.

<!-- fr:journal kind=decision scope=spec id=d3-dry-run-forge-reads created=2026-11-15T17:05:43+00:00 decided_by=operator -->
### d3-dry-run-forge-reads · decision · #1301: --dry-run makes forge reads only

Operator chose: same gates incl. forge reads; reports moves, owed entries, issues filed/reused; no file write, no git change, no forge write; exit code equals the real run's.

<!-- fr:journal kind=decision scope=spec id=d4-label-filter-fail-closed created=2026-11-15T17:05:43+00:00 decided_by=operator -->
### d4-label-filter-fail-closed · decision · #1184: find owed issues by label, fail closed at the limit

Operator chose: list only open fr:owed issues (forge-side filter); when the list reaches its limit or cannot be read, file nothing and warn. Closing reads the one issue by number.

<!-- fr:journal kind=decision scope=spec id=d5-verification created=2026-11-15T17:05:43+00:00 decided_by=operator -->
### d5-verification · decision · Verification: candidate, gate developer

Operator chose strategy candidate with gate developer; no post-merge Test Plan rows.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-15T17:05:43+00:00 lens=tests step=brainstorm -->
### lens-tests-1 · lens · Every fix is a side effect that must NOT happen; each needs a negative test proving no forge write / no file change

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-15T17:14:55+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · R4 closes only owed entries in the run's own journals; an archived journal's discharged entry never closes

target: spec. debt-engine R24 covers live or archived owed entries; resolve takes any --scope/--slug (journal_cmd.py:582-585). R4 must list every owed entry discharged on the branch, or a merge-time closer must exist.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-15T17:14:55+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · Single-plan path can refuse after a git mv; a non-typer.Exit refusal still runs the follow-ups

target: spec. archive.py:485-487 stages the plan move before the journal/run moves that can raise ArchiveError (archive_cmd.py:1041-1046); the placement refusal raises SettingsError (:907-914), so _after_moves still files --issues.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-15T17:14:55+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · The quiet/stealth dry run cannot be contained by a scratch worktree of the product repo

target: spec. _record_merged writes the fr worktree / tracking clone and pushes through git (archive_cmd.py:237-409), outside both the scratch copy and the preview forge.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-15T17:14:55+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · Replaying git diff --binary HEAD loses the index split, so the dry run can disagree with the real run

target: spec. paths_dirty (archive_cmd.py:1029-1039) and _edited_in_worktree (:604-614) read the staged/unstaged difference; ignored files and a crashed scratch worktree are unaddressed.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-15T17:14:55+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · The preview forge's synthetic ref fails _issue_ref, and raising on unknown writes is swallowed

target: spec. _issue_ref needs a URL matching TRACKED_BY_RE (archive_followups.py:536-539); file_owed_ends, ensure_labels and _after_moves catch Exception (:516-519, :533, archive_cmd.py:594-597).

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-15T17:14:55+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · On GitLab/Gitea, R10's fail-closed means owed issues are never filed

target: spec. UnsupportedBatchOps.list_issues raises (ghclient.py:664-672); fr journal file exits 1 on any owed error (journal_cmd.py:663-684), which could leave deliver's leftover refusal unpassable.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-15T17:14:55+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · _on_default_branch duplicates an existing helper and must strip the remote prefix

target: spec. remote_default_ref answers origin/main (git.py:179-206); fr.docs.load.on_default_branch (docs/load.py:90-102) already strips it and treats detached HEAD as off.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-15T17:14:55+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · The Refs-rule exemption changes the premature-close gate but has no requirement and no row

target: spec. premature_closes (pr_body.py:344-406) and _refuse_premature_closes (run_cmd.py:7139-7189); the conflict with an owed row's issues: ref is unsettled.

<!-- fr:journal kind=finding scope=spec id=s-r9 created=2026-11-15T17:14:55+00:00 state=open review_scope=in -->
### s-r9 · finding [open] (reviewer: in scope) · R4 does not say what happens under forge.pr_body minimal

target: spec. Under minimal the live body is not section-checked (run_cmd.py:7069-7081), yet the Closes line must be live to close the issue; exact text vs any closing reference unstated.

<!-- fr:journal kind=finding scope=spec id=s-r10 created=2026-11-15T17:14:55+00:00 state=open review_scope=in -->
### s-r10 · finding [open] (reviewer: in scope) · R6/R7 amend debt-engine R22 and row owed-durable-at-archive, recorded nowhere

target: spec. debt-engine R22 (implemented spec :79); row owed-durable-at-archive (debt-engine.yaml:56-63).

<!-- fr:journal kind=finding scope=spec id=s-r11 created=2026-11-15T17:14:55+00:00 state=open review_scope=in -->
### s-r11 · finding [open] (reviewer: in scope) · No Test Plan and no named negative tests for the tests lens

target: spec. test_plan is on; the rows' scenario paths are not traced in the spec.

<!-- fr:journal kind=finding scope=spec id=s-r12 created=2026-11-15T17:14:55+00:00 state=open review_scope=out -->
### s-r12 · finding [open] (reviewer: out of scope) · _existing_markers (open-ends dedupe) keeps the same 200-issue cap and best-effort fallback

target: spec. archive_followups.py:195-218. Pre-existing, outside #1184.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-15T17:14:55+00:00 -->
### spec-review-1 · review · independent spec review: 12 findings

fr-spec-reviewer checked decisions d1-d5 and lens tests against the spec, every code name in §A-§D, and internal consistency. Raised s-r1..s-r11 (in scope) and s-r12 (out of scope).

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-15T17:14:55+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: R4 closes only owed entries in the run's own journals; an archived journal's discharged entry never closes

R4 now lists every owed entry discharged on the branch in any spec/plan/debug journal, live or archived, whose resolution is absent at the default ref (§A); R2's printed line covers branches with no deliver.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-15T17:14:55+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: Single-plan path can refuse after a git mv; a non-typer.Exit refusal still runs the follow-ups

R7 defines a refusal as any non-zero exit or exception (placement refusal included); _with_followups skips _after_moves on any raise; archive_plan_dir undoes its staged moves on ArchiveError (§B).

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-15T17:14:55+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: The quiet/stealth dry run cannot be contained by a scratch worktree of the product repo

Quiet/stealth gets a read-only preview path in _record_merged that returns before append_record, commit_paths, stealth.commit_and_push, atomic_push and _push_fr (§C); R11 names the fr worktree and tracking clone.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-15T17:14:55+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: Replaying git diff --binary HEAD loses the index split, so the dry run can disagree with the real run

§C replays the index (git apply --index) then the worktree diff, copies untracked non-ignored files, has the plan pin that archive reads no ignored file, and prunes stale fr-archive-dry-run-* worktrees first.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-15T17:14:55+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: The preview forge's synthetic ref fails _issue_ref, and raising on unknown writes is swallowed

Preview forge: read allowlist delegates, create_issue answers a forge-shaped URL (n from 900000) that _issue_ref accepts, other known writes recorded, anything else recorded as refused; the record is read after the run, and a refusal exits 1 (R11).

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-15T17:14:55+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: On GitLab/Gitea, R10's fail-closed means owed issues are never filed

New R13: an adapter that cannot list issues keeps owed actions in the journal like forge.issues off; fr journal file exits 0 and deliver accepts the entry as recorded (§D).

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-15T17:14:55+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: _on_default_branch duplicates an existing helper and must strip the remote prefix

§A reuses fr.docs.load.on_default_branch, moved to fr.git, with remote_default_ref; commit.py's variant explicitly not used.

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-15T17:14:55+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: The Refs-rule exemption changes the premature-close gate but has no requirement and no row

New R5 states the exemption and its precedence: a held issue (owed row issues:, post-merge gate, unanswered narrowing) is rendered Refs with the reason and exempt from R4's check; covered by row owed-close-at-merge (origin R5).

<!-- fr:journal kind=finding scope=spec id=s-r9-resolved created=2026-11-15T17:14:55+00:00 state=fixed resolves=s-r9 -->
### s-r9-resolved · finding [fixed] · resolves s-r9: R4 does not say what happens under forge.pr_body minimal

R4's live-body check uses closing_refs (any closing keyword) and runs under forge.pr_body full and minimal alike (§A).

<!-- fr:journal kind=finding scope=spec id=s-r10-resolved created=2026-11-15T17:14:55+00:00 state=fixed resolves=s-r10 -->
### s-r10-resolved · finding [fixed] · resolves s-r10: R6/R7 amend debt-engine R22 and row owed-durable-at-archive, recorded nowhere

New R9 records the R22 amendment; this record amends row owed-durable-at-archive.

<!-- fr:journal kind=finding scope=spec id=s-r11-resolved created=2026-11-15T17:14:55+00:00 state=fixed resolves=s-r11 -->
### s-r11-resolved · finding [fixed] · resolves s-r11: No Test Plan and no named negative tests for the tests lens

Verification explains the absent Test Plan (d5: no post-merge rows) and names, per row, the negative evidence each scenario and unit test proves.

<!-- fr:journal kind=finding scope=spec id=s-r12-resolved created=2026-11-15T17:14:55+00:00 state=open resolves=s-r12 out_of_scope=true -->
### s-r12-resolved · finding [out-of-scope] · resolves s-r12: _existing_markers (open-ends dedupe) keeps the same 200-issue cap and best-effort fallback

Pre-existing in _existing_markers (open-end follow-ups), not caused by this change and outside #1184, which names _existing_owed.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-15-owed-archive-side-effects-p2 created=2026-11-15T17:17:38+00:00 -->
### phase-split-2026-11-15-owed-archive-side-effects-p2 · decision · ask: #1400 close at merge (R1-R6) is its own reviewable ask

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-11-15-owed-archive-side-effects-p3 created=2026-11-15T17:17:40+00:00 -->
### phase-split-2026-11-15-owed-archive-side-effects-p3 · decision · ask: #1301 fr archive --dry-run (R10-R11) is its own reviewable ask
