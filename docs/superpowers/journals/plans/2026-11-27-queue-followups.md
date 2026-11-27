<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-queue-followups

<!-- fr:journal kind=discovery scope=plan id=p1-cmd-due-list-feeds-existing-probe created=2026-11-27T15:06:48+00:00 phase=1 -->
### p1-cmd-due-list-feeds-existing-probe · discovery · The command's close-out due list only decides which live close-out sessions are asked about (phase 1)

`drive_pass` computes `due` itself from `snap.queue_records`, so a queue-landed batch is
started without the command's change. The command's `due` list (triage_batch_cmd ~:4640)
feeds `_existing`, `_collected_reads` and `closeout_waits`; its test therefore uses a live
close-out tab (recorded, not redispatched) to tell the two apart.

<!-- fr:journal kind=decision scope=plan id=p1-planned-at-uses-plan-clock created=2026-11-27T15:06:48+00:00 phase=1 -->
### p1-planned-at-uses-plan-clock · decision · planned_at is stamped with the clock `Pacer.plan` used, not the clock at record_summary (phase 1)

`deadline_repos` reads the window (planned_at, now]. Stamping the later record_summary time
would drop a deadline that fell between the plan and its record. `Pacer.plan` keeps its
`now` in `_planning_at`, and `record_summary` stamps it (falling back to the clock).

<!-- fr:journal kind=decision scope=plan id=p1-wave-hold-only-when-collecting created=2026-11-27T15:06:48+00:00 phase=1 -->
### p1-wave-hold-only-when-collecting · decision · The R6 `held` action is emitted only for a wave that has a due member to collect (phase 1)

A wave whose members are all not yet due starts nothing anyway; emitting `held` there would
add an action to every single-batch pass inside the fallback window (and break
test_no_closeout_before_the_release_commit_or_the_fallback). The held line names each
blocker as `<id> (not due|unverified|ledger unread)`. No existing assertion changed.

<!-- fr:journal kind=decision scope=plan id=p1-docs-updated created=2026-11-27T15:06:48+00:00 phase=1 -->
### p1-docs-updated · decision · fr-wave-driver.md describes the new close-out timing and the probe's classification (phase 1)

The conflict-probe paragraph no longer says stamps and generated files count as conflicts;
the close-out step says a queue-landed batch is ready at once, the wave waits for every
member and names them, and a deadline wakes a quiet paced pass. Four other covering pages
got `reviewed` stamps (fr-triage, index, herdr-control-sessions, cli reference).

<!-- fr:journal kind=discovery scope=plan id=p1-fast-tier-selects-nearly-everything created=2026-11-27T15:06:48+00:00 phase=1 -->
### p1-fast-tier-selects-nearly-everything · discovery · The --fr-scope fast tier selected about the whole suite for this phase and ran at ~17 tests/min here (phase 1)

The changes reach batch_drive.py, triage_batch_cmd.py and docs/ (which selects every
own_artifacts test), so `--fr-scope origin/main -n 2` selected roughly the full suite; at host
load ~20 it ran ~290 tests in 17 minutes and was stopped. The touched test files and their
neighbours were run instead (18 files, 862 passed; advisory, like the fast tier); CI is this
repo's tests evidence.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-27T15:06:48+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a one-expression change (repo names lower-cased) with nothing around it to tidy

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-27T15:06:48+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

the classification is one small helper beside trial_conflicts; ruff format only dropped the except parentheses

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-27T15:06:48+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

tidied in T6: the per-repo queue-landed set became batch_drive.queue_landed_by_repo, shared with the pacer's deadline_repos

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-27T15:06:48+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

the blockers were first joined strings and split back; refactored to (id, why) tuples, and the key renamed wave_key after mypy caught a shadowed `key`

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-27T15:06:48+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

deadline_repos reuses queue_landed_by_repo, closeout_event, LANDED and parse_aware; nothing left duplicated
