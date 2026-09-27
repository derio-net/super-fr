# Journal: 2026-09-27-branch-diff-robustness

<!-- fr:journal kind=repro scope=debug id=ef410c409b1b created=2026-09-27T08:25:21 -->
### ef410c409b1b · repro · branch_changes_present trusts both git diff --name-only calls blindly

Two defects in one function (fr/isolation/local.py). (1) #705: neither `git diff --name-only` call's returncode is checked, so a git failure yields changed=[] (early return changes_present=True) or differing=[] (missing=[] -> changes_present=True): a failed diff reads as ALL CHANGES PRESENT. (2) #717: without -z, git C-quotes non-ASCII/special paths (core.quotePath), so the quoted name names no file and a landed change reads missing (fail-safe false not-verified). Repro: a runner whose git diff exits 128; a real repo whose branch adds a non-ASCII path, squash-merged.

<!-- fr:journal kind=root-cause scope=debug id=5aedb662179a created=2026-09-27T08:25:32 -->
### 5aedb662179a · root-cause · Both git diff --name-only calls ignore returncode and parse newline-quoted output

One cause, one function: branch_changes_present reads names.stdout / diff.stdout with splitlines() and never checks returncode (merge-base alone is checked). A failing diff has empty stdout, which the function's own logic reads as 'nothing changed' / 'nothing differs' -> changes_present=True, the unsafe direction, in the guard behind verify-merge, the down/gc reap hazard, and gc's _merged_by_content. Separately, without -z git C-quotes paths, so the parsed names do not name real files. Fix: raise IsolationError on non-zero exit (every caller already maps it to not-verified: verify-merge exit 2, down's hazard 'unverifiable', gc's _merged_by_content False) and read both lists with -z split on NUL. Single hypothesis, confirmed by reading every caller.

<!-- fr:journal kind=ruled-out scope=debug id=3297ca9c43ad created=2026-09-27T08:26:00 -->
### 3297ca9c43ad · ruled-out · #717's 'fails safe (false not-verified)' is wrong: a quoted path is a false PASS

Probed live on the unfixed code: a branch adding café.py that was NEVER merged returns MergeVerification(changed=['"caf\\303\\251.py"'], missing=[], changes_present=True). The quoted name is fed back as a pathspec to the second diff, matches no file, so differing=[] and nothing is checked. So #717 is the same unsafe direction as #705, not a fail-safe. Same root cause and same fix (-z both calls); the red test pins the orphan case, not only the squash one.

<!-- fr:journal kind=finding scope=debug id=1a151ec36a0d created=2026-09-27T08:37:37 state=fixed -->
### 1a151ec36a0d · finding [fixed] · _diff_names: both diffs now -z and raise IsolationError on non-zero exit

New helper _diff_names in fr/isolation/local.py runs git diff --name-only -z, raises IsolationError (naming exit + stderr) on failure, and splits on NUL. branch_changes_present uses it for both calls. Pinned red-first by test_branch_changes_present_failed_diff_raises[1,2] (a runner whose 1st/2nd diff exits 128), test_branch_changes_present_non_ascii_path_unmerged_is_missing (the false PASS) and ..._non_ascii_path_squash (non-ASCII + tab paths land). Callers unchanged: verify-merge exits 2, down's hazard reads unverifiable, gc's _merged_by_content returns False. #716 (reverted merges) untouched.
