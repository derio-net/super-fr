# Journal: 2026-09-27-branch-diff-robustness

<!-- fr:journal kind=repro scope=debug id=ef410c409b1b created=2026-09-27T08:25:21 -->
### ef410c409b1b · repro · branch_changes_present trusts both git diff --name-only calls blindly

Two defects in one function (fr/isolation/local.py). (1) #705: neither `git diff --name-only` call's returncode is checked, so a git failure yields changed=[] (early return changes_present=True) or differing=[] (missing=[] -> changes_present=True): a failed diff reads as ALL CHANGES PRESENT. (2) #717: without -z, git C-quotes non-ASCII/special paths (core.quotePath), so the quoted name names no file and a landed change reads missing (fail-safe false not-verified). Repro: a runner whose git diff exits 128; a real repo whose branch adds a non-ASCII path, squash-merged.
