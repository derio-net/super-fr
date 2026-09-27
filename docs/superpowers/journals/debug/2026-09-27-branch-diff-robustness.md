# Journal: 2026-09-27-branch-diff-robustness

<!-- fr:journal kind=repro scope=debug id=ef410c409b1b created=2026-09-27T08:25:21 -->
### ef410c409b1b · repro · branch_changes_present trusts both git diff --name-only calls blindly

Two defects in one function (fr/isolation/local.py). (1) #705: neither `git diff --name-only` call's returncode is checked, so a git failure yields changed=[] (early return changes_present=True) or differing=[] (missing=[] -> changes_present=True): a failed diff reads as ALL CHANGES PRESENT. (2) #717: without -z, git C-quotes non-ASCII/special paths (core.quotePath), so the quoted name names no file and a landed change reads missing (fail-safe false not-verified). Repro: a runner whose git diff exits 128; a real repo whose branch adds a non-ASCII path, squash-merged.

<!-- fr:journal kind=root-cause scope=debug id=5aedb662179a created=2026-09-27T08:25:32 -->
### 5aedb662179a · root-cause · Both git diff --name-only calls ignore returncode and parse newline-quoted output

One cause, one function: branch_changes_present reads names.stdout / diff.stdout with splitlines() and never checks returncode (merge-base alone is checked). A failing diff has empty stdout, which the function's own logic reads as 'nothing changed' / 'nothing differs' -> changes_present=True, the unsafe direction, in the guard behind verify-merge, the down/gc reap hazard, and gc's _merged_by_content. Separately, without -z git C-quotes paths, so the parsed names do not name real files. Fix: raise IsolationError on non-zero exit (every caller already maps it to not-verified: verify-merge exit 2, down's hazard 'unverifiable', gc's _merged_by_content False) and read both lists with -z split on NUL. Single hypothesis, confirmed by reading every caller.
