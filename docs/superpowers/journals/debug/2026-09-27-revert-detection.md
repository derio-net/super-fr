# Journal: 2026-09-27-revert-detection

<!-- fr:journal kind=repro scope=debug id=d01d6aec180f created=2026-09-27T19:28:50+00:00 -->
### d01d6aec180f · repro · #741: a --no-ff landing reverted with revert -m 1 still reads landed

Scratch repo: base report.md=head; feature adds foo, bar in two commits; main commits other.py; `git merge --no-ff feature`; `git revert -m 1 HEAD`. `git merge-base main feature` == feature tip (99fde50…), so `git diff --name-only mb feature` is empty and branch_changes_present returns changes_present=True with changed=[]. Pinned: strict xfail test_branch_changes_present_reverted_no_ff_merge_is_missing.

<!-- fr:journal kind=repro scope=debug id=7e291a77364c created=2026-09-27T19:28:53+00:00 -->
### 7e291a77364c · repro · #739: a revert applied after another edit to the path reads landed

Squash-land +foo into a..e; a later PR edits e->E (report now has foo); `git revert HEAD~1` removes foo, producing a,b,c,d,E — a blob the path never held. The #716 rule only un-lands when a post-landing commit writes a pre-landing ('held') blob, so the three-way result is never matched. Pinned: strict xfail test_branch_changes_present_three_way_revert_is_missing.

<!-- fr:journal kind=root-cause scope=debug id=9e52c689b768 created=2026-09-27T19:28:54+00:00 -->
### 9e52c689b768 · root-cause · Both: branch_changes_present infers 'reverted' only from whole-state evidence

#741: the fork point comes from `git merge-base base branch`, which for an ancestor branch is the branch tip itself — the diff of the branch's own changes is empty and every path check is skipped. The true fork point is merge-base(M^1, branch) where M is the landing merge: the oldest commit on base's first-parent line that descends from the tip (`git rev-list --first-parent --ancestry-path --reverse branch..base`, first line). For a fast-forward or an empty branch M^1 IS the tip, so this degenerates to today's behaviour. #739: _branch_blob_was_on_base recognises a revert only by the path returning to a whole blob it held before; a revert is also recognisable by its PATCH — it removes every non-blank line the branch added and adds nothing but lines the branch removed. The raw log already walks those commits, so adding -p to the same git call yields the patch. One mechanism, two evidence gaps in the same function — a single root cause as batched.

<!-- fr:journal kind=hypothesis scope=debug id=c49167c4d134 created=2026-09-27T19:45:03+00:00 -->
### c49167c4d134 · hypothesis · #741: fork from the landing merge's first parent

Confirmed: _fork_point (rev-list --first-parent --ancestry-path --reverse tip..base, first line; merge-base with its ^1) turned the no-ff test green with every other branch_changes_present test untouched. Fast-forward / empty branches keep the tip as the fork (new guard test).

<!-- fr:journal kind=ruled-out scope=debug id=501487bd5d75 created=2026-09-27T19:45:05+00:00 -->
### 501487bd5d75 · ruled-out · Attempt 1 of #739: literal \x01 byte as the log --format marker

Passing the marker as a raw \x01 byte in argv made _parse_log see no commits, so 12 isolation tests (every blob-fallback landing) went red. Not the hypothesis — the parser input: switched to git's documented %x01 escape and all 219 passed. Counted as one failed fix.

<!-- fr:journal kind=finding scope=debug id=a75dfa546a81 created=2026-09-27T19:45:07+00:00 state=fixed -->
### a75dfa546a81 · finding [fixed] · Revert detection: landing-merge fork point + inverse-patch rule

packages/fr/src/fr/isolation/local.py: _fork_point (#741); _branch_blob_was_on_base reads -p -U0 in the same log call and un-lands on a non-deleting commit whose patch is the branch's inverted (_is_inverse_patch) (#739). Failing tests first: the two strict xfails un-xfailed in the red commit; guards added for no-ff+rewrite (stays landed), fast-forward/empty branch (stay present), failed rev-list (raises), three-way revert restoring a removed line (missing). Full suite 6675 passed; ruff + mypy clean.

<!-- fr:journal kind=finding scope=debug id=review-f1 created=2026-09-27T19:59:41+00:00 state=open review_scope=in -->
### review-f1 · finding [open] (reviewer: in scope) · Review f1: three-way revert of a pure-deletion branch still reads landed

_is_inverse_patch returned False whenever the branch added no line, so a revert restoring a line the branch only removed (after an unrelated edit) was never recognised. Reproduced: test_branch_changes_present_three_way_revert_of_a_pure_deletion_is_missing fails (changes_present=True).
