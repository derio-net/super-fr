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

<!-- fr:journal kind=repro scope=debug id=repro-1486 created=2026-11-18T13:10:02+00:00 -->
### repro-1486 · repro · #1486: unreadable default ref reads as off-default in _write_manual_owed; GitUnavailableError escapes

head_on_default_branch returns False when remote_default_ref is None or a GitRefusal. That is the safe answer for R3 (resolve closes nothing), but for R8 (_write_manual_owed) 'off default' means 'write and stage an owed entry', which may land on main. on_default_branch raises GitUnavailableError, and archive_cmd._write_manual_owed calls head_on_default_branch outside its try, so it crashes the archive.

<!-- fr:journal kind=repro scope=debug id=repro-1488 created=2026-11-18T13:10:04+00:00 -->
### repro-1488 · repro · #1488: a foreign-host issue URL satisfies deliver's owed closing check

_refuse_unclosed_owed normalizes each closing ref with normalize_issue_ref, whose _URL_REF accepts any host and keeps only the path. 'Closes https://evil.example/derio-net/super-fr/issues/9' normalizes to derio-net/super-fr#9, so deliver accepts the body, but GitHub does not close #9 when the PR merges.

<!-- fr:journal kind=root-cause scope=debug id=rc-1483 created=2026-11-18T13:34:05+00:00 -->
### rc-1483 · root-cause · #1483: _keep_live_root checks only the last path component for a link

O_NOFOLLOW and the lstat of .gitkeep cover .gitkeep alone; live_root.mkdir, iterdir and the open path walk every component above it, so a symlinked plans root (or docs/superpowers) is followed.

<!-- fr:journal kind=root-cause scope=debug id=rc-1485 created=2026-11-18T13:34:10+00:00 -->
### rc-1485 · root-cause · #1485: _existing_markers reads unknown as 'no duplicate'

A failed listing, a listing at its 200 cap, and a missing viewer each returned {}, which file_open_ends reads as 'no existing issue'. _existing_owed was already made fail-closed for the same cases.

<!-- fr:journal kind=root-cause scope=debug id=rc-1486 created=2026-11-18T13:34:14+00:00 -->
### rc-1486 · root-cause · #1486: head_on_default_branch has two answers for three states

It folds 'cannot tell' into False. That is safe for R3 (off-default closes nothing) but not for R8, where off-default writes and stages. And on_default_branch raises GitUnavailableError, called outside _write_manual_owed's try.

<!-- fr:journal kind=root-cause scope=debug id=rc-1488 created=2026-11-18T13:34:18+00:00 -->
### rc-1488 · root-cause · #1488: normalize_issue_ref drops the URL host

_URL_REF matched any host and kept only the path, so a lookalike URL on another host normalised to this repo's issue and satisfied _refuse_unclosed_owed.

<!-- fr:journal kind=decision scope=debug id=d-unsupported-listing created=2026-11-18T13:34:22+00:00 -->
### d-unsupported-listing · decision · A forge that cannot list issues keeps R11's no-dedup fallback for open ends

UnsupportedForgeOperation (glab, tea) is a known capability gap, not an unknown answer; refusing there would stop follow-up filing on those forges entirely. test_dedup_falls_back_to_none_when_the_forge_cannot_list keeps pinning it. Only failed, capped or viewer-less listings now fail closed.

<!-- fr:journal kind=decision scope=debug id=d-unknown-is-default created=2026-11-18T13:34:26+00:00 -->
### d-unknown-is-default · decision · R8 treats an unknown default-branch answer as the default branch

New git.default_branch_answer returns True/False/None. _write_manual_owed previews and writes nothing unless the answer is a readable False. head_on_default_branch (R3's reader) is unchanged.
