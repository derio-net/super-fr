# Journal: 2026-10-03-drive-legacy-closeouts

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-03T19:11:25+00:00 -->
### repro · repro · drive --once plans a close-out for every batch merged before 5.2.0

On derio-net/super-fr with fr 5.2.0, `fr triage batch drive --once --repo derio-net/super-fr` (no --yes) prints 50 `closeout <id>: start derio-net/super-fr/run/closeout-<id>` lines and `in flight 4, merged 50, pending 3, closing 50`, and no other action. Every batch that merged before the driver existed is planned for a close-out, including batches closed out by hand (e.g. gate-ordering, archived in #874). With --yes it would open 50 runner tabs and run post_merge 50 times. Found by wave-driver Test Plan item 15.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-03T19:11:26+00:00 -->
### root-cause · root-cause · drive_pass owes a close-out to any landed batch without a closeout event, and the default selection is 'all' when no batch has a wave

`batch_drive.drive_pass` step 2 skips a landed batch only when it has a `CloseoutEvent`, an event type that exists only since schema 3 (5.2.0); no pre-driver batch carries one, and nothing in judgements or facts records a hand close-out. `drive` with no ids selects "batches with a wave, else all" (spec Design B), and no super-fr batch has a wave yet, so all 74 batches are selected and the 50 landed ones all owe a close-out. The board had the same defect (wave-driver ri-3) and was fixed by requiring `b.wave` in `views.needs_you`; the driver pass never got the guard, and the spec never stated it.

<!-- fr:journal kind=hypothesis scope=debug id=h-archived-signal created=2026-10-03T19:12:55+00:00 -->
### h-archived-signal · hypothesis · A merged batch is archived when none of the fr artifacts its PR added is still live on the default branch

Tested on real merges, via `git diff --name-only <merge>^1 <merge>` filtered to live artifact dirs (plans, specs, journals, runs, usage) and `git cat-file -e origin/main:<path>`: #867 (gate-ordering, closed out by hand in #874) -> every path gone; #865 (forge-honesty, owed per `fr status`) -> its debug journal LIVE; #876 (wave-driver, archived in #890) -> all 13 paths gone. Verdict: confirmed. Refinement: count only paths the PR ADDED (`--diff-filter=A`), so a PR that edits another run's live artifact (a spec amendment) does not owe a close-out forever. Needs no new forge operation: the merge commit is already read per candidate, and git runs only through gitseam.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-10-03T19:26:13+00:00 state=fixed -->
### fix · finding [fixed] · Close out only waved or named batches, never an archived one

Fixed in 0da32b45. `batch_drive.drive_pass` step 2 skips a batch with no wave unless `Snapshot.named`, and any batch in `Snapshot.archived`; both before the `closing` count, so the summary and the loop's end condition no longer count legacy batches. `is_archived(added, live)`: the merge commit added at least one run artifact (live plans/specs/journals/runs/usage) and none is on `origin/<default>` — no evidence keeps the close-out owed. gitseam gains `added_paths` (`diff --diff-filter=A` against the first parent) and `exists_at`. The command snapshot applies the wave guard before any forge read. Failing tests first: `test_triage_batch_drive.py` (3 pass-level + 6 is_archived cases), `test_triage_batch_drive_cmd.py::test_a_merged_batch_with_no_wave_is_not_closed_out_unless_named` (reproduced the bug once the fixture had no waved batch) and `::test_a_named_batch_already_archived_by_hand_is_not_closed_out`, `test_triage_gitseam.py` (2, real repos). Live: the Test 15 command now prints `closing 0` (was 50); naming gate-ordering and forge-honesty plans only forge-honesty's (its journal is still live). Spec R5, Design B and Test Plan 4 amended; fr-triage skill and mirrors updated. Full suite: 8088 passed, 105 skipped.

<!-- fr:journal kind=ruled-out scope=debug id=ro-wave-guard created=2026-10-03T19:58:23+00:00 -->
### ro-wave-guard · ruled-out · The wave guard (a) is not needed and breaks no-wave repos

Independent review (Opus, read-only): on a repo with no waved batch an unnamed drive dispatches wave-less batches, merges them, then the guard skipped their close-out, so post_merge never ran and the loop ended 'done' (R2, R14). No event distinguishes a pre-driver merge from a fresh one. Measured on this repo with every batch named and only the archived check: 'closing 2' — forge-honesty and acceptance-integrity, exactly the two runs fr status lists as owed; the other 48 read as archived. Operator chose to drop (a) and keep (b). Removed in 90e6291c; spec amendments and fr-triage skill reworded; tests rewritten (wave-less merged batch is still closed out; archived hand close-out is not; a mutation disabling the archived skip fails the pass and command tests). Unnamed live plan now: closing 2. Full suite 8087 passed, 105 skipped.
