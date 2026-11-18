<!-- fr:journal-schema=4 -->
# Journal: 2026-11-18-batch-owed-followups

<!-- fr:journal kind=decision scope=debug id=d-four-causes created=2026-11-18T13:09:58+00:00 decided_by=operator -->
### d-four-causes · decision · Four independent root causes, one PR (operator)

Investigation found #1483, #1485, #1486 and #1488 are four separate defects in four code paths, not one root cause. The operator chose to fix all four in this one PR, each with its own failing test.

<!-- fr:journal kind=repro scope=debug id=repro-1483 created=2026-11-18T13:09:59+00:00 -->
### repro-1483 · repro · #1483: a symlinked live plans root gets .gitkeep written through it

docs/superpowers/plans -> ../elsewhere (an in-repo symlink), one plan under it. archive_plan_dir moves the plan, then _keep_live_root's mkdir/iterdir/os.open follow the link and create docs/elsewhere/.gitkeep; git add then fails 'beyond a symbolic link'. O_NOFOLLOW covers only the last component. (A link pointing outside the repo is refused earlier by the plan_dir.resolve() check.)

<!-- fr:journal kind=repro scope=debug id=repro-1485 created=2026-11-18T13:10:01+00:00 -->
### repro-1485 · repro · #1485: _existing_markers returns {} on any listing error or past 200 issues

archive_followups._existing_markers lists 200 open issues; an error, a missing viewer or a listing past the cap all read as 'no existing issue', so file_open_ends files a duplicate follow-up. _existing_owed fails closed in all three cases (OwedLookup.reason). The repo has 168 open issues today, so the 200 cap is close to being reached.
