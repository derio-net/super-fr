<!-- fr:journal-schema=4 -->
# Journal: 2026-11-17-batch-triage-collect

<!-- fr:journal kind=repro scope=debug id=9d88f14e34f6 created=2026-11-17T09:03:11+00:00 -->
### 9d88f14e34f6 · repro · #1268: fr triage collect calls ensure_approval_label for every collected repo

triage_cmd.collect_command loops facts.collected through ensure_approval_label after writing facts. Pinned as wanted by tests/unit/test_merge_train_label_board.py::test_collect_creates_the_label_on_each_collected_repo and by merge-train-safety R4, which lists collect among the check sites. Dispatch, merge (--yes), every drive pass and init scaffold already ensure it.

<!-- fr:journal kind=repro scope=debug id=d559a56eaff2 created=2026-11-17T09:03:13+00:00 -->
### d559a56eaff2 · repro · #1197: render._pr_row counts mergeStateStatus BLOCKED as a conflict

render.py:611 conflict = merge in {DIRTY, BLOCKED} or mergeable == CONFLICTING. mergeability.conflicting() is the one predicate (exit-gates R19) and excludes BLOCKED (branch protection).

<!-- fr:journal kind=repro scope=debug id=3f4804cd27c1 created=2026-11-17T09:03:15+00:00 -->
### 3f4804cd27c1 · repro · #1210: scope retire never sees closed issues a retired scope holds

scope_retire_command filters facts.issues to state == open. Dropping the filter alone fixes nothing: closed issues in facts carry no claims (collect reads comments for open issues only, and carried closed issues get claims: []). Closed claimed issues appear only in facts.stale_in_progress as state=held, with no signer recorded, so retire cannot tell whose they are.

<!-- fr:journal kind=repro scope=debug id=4df37d0ec4f5 created=2026-11-17T09:03:17+00:00 -->
### 4df37d0ec4f5 · repro · #1300: facts schema version spelled in three model.py places and many tests

model.py: FACTS_SCHEMA Literal[13] = 13, FACTS_READS tuple, Facts.schema_ Literal[3..13] = Field(13). Tests assert == 13 and the full reads tuple in at least seven modules.

<!-- fr:journal kind=hypothesis scope=debug id=db145d129a2d created=2026-11-17T09:03:19+00:00 -->
### db145d129a2d · hypothesis · Four independent defects, not one root cause

1268 is a policy choice pinned by a spec requirement; 1197 is a duplicated predicate; 1210 is missing data (closed-claim signers not collected); 1300 is a duplicated constant. 1210's fix needs a facts-schema bump (signers on StaleInProgress), which is when 1300 says to do its refactor.

<!-- fr:journal kind=decision scope=debug id=ab6d79d735fb created=2026-11-17T09:21:35+00:00 decided_by=operator -->
### ab6d79d735fb · decision · Operator: fix all four in one PR; collect reports the missing label; schema 14 for closed claims

Asked at the batch's multi-root-cause stop. Answers: fix all 4 in the one PR. #1268: collect drops ensure_approval_label and prints one line counting repos that lack approved-fr; the approval-label-created row is amended. #1210: StaleInProgress gains claims (facts schema 14, #1300 refactor rides it); scope retire releases a retired scope's claims on closed issues with unlabel, leaving them settled.

<!-- fr:journal kind=finding scope=debug id=a5639e5e74bc created=2026-11-17T09:26:19+00:00 state=fixed -->
### a5639e5e74bc · finding [fixed] · #1197 fixed: render._pr_row asks mergeability.conflicting

Test test_triage_prs_render.py::test_blocked_is_not_a_conflict_on_the_triage_page (BLOCKED+MERGEABLE -> 0, DIRTY -> 1, BLOCKED+CONFLICTING -> 1) failed before, passes now.

<!-- fr:journal kind=finding scope=debug id=ada78e7dc3ea created=2026-11-17T09:27:33+00:00 state=fixed -->
### ada78e7dc3ea · finding [fixed] · #1268 fixed: collect reports the missing approved-fr label, never creates it

triage_cmd.collect_command calls approval.approval_label_missing (read-only; labels off or a forge error reports nothing) and prints one line. Tests test_merge_train_label_board.py::test_collect_writes_no_label_and_says_which_repos_lack_it and ::test_collect_counts_no_repo_whose_labels_are_off failed before. Row approval-label-created amended in legacy.yaml.

<!-- fr:journal kind=root-cause scope=debug id=4b8fbbb3cf3c created=2026-11-17T09:31:56+00:00 -->
### 4b8fbbb3cf3c · root-cause · #1210: closed claimed issues carried no signer in facts, so retire had nothing to act on

Retire filtered to open issues, and the only facts record of a closed fr:claimed issue (stale_in_progress) held a state but not whose claim it was.
