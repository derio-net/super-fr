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
