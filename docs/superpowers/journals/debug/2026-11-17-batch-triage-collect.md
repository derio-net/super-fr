<!-- fr:journal-schema=4 -->
# Journal: 2026-11-17-batch-triage-collect

<!-- fr:journal kind=repro scope=debug id=9d88f14e34f6 created=2026-11-17T09:03:11+00:00 -->
### 9d88f14e34f6 · repro · #1268: fr triage collect calls ensure_approval_label for every collected repo

triage_cmd.collect_command loops facts.collected through ensure_approval_label after writing facts. Pinned as wanted by tests/unit/test_merge_train_label_board.py::test_collect_creates_the_label_on_each_collected_repo and by merge-train-safety R4, which lists collect among the check sites. Dispatch, merge (--yes), every drive pass and init scaffold already ensure it.
