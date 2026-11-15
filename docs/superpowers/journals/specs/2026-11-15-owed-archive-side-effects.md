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
