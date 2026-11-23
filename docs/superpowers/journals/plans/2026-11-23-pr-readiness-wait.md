<!-- fr:journal-schema=4 -->
# Journal: 2026-11-23-pr-readiness-wait

<!-- fr:journal kind=decision scope=plan id=settle-yaml-bool-refused created=2026-11-23T10:49:48+00:00 phase=1 -->
### settle-yaml-bool-refused · decision · A YAML bool for git.settle is refused, with a quote-it hint (phase 1)

Per P1.T2.S1, `git.settle.ci: off` unquoted (PyYAML reads `false`) is refused rather
than mapped to `off` as the on/off keys do. The message says `quote it: 'off'`, so the
operator sees the fix. `fr settings init` documents the words.

<!-- fr:journal kind=decision scope=plan id=settle-off-concern-state created=2026-11-23T10:49:48+00:00 phase=1 -->
### settle-off-concern-state · decision · An off concern reads `off` in the verdict and witness; both off reads nothing (phase 1)

`evaluate` reports a concern under `off` as state `off` (witness
`off/fix:off/green@<head>`). With both keys off the verb makes no forge read at all and
exits 0. With only conflicts off, `pr_view` is still read, because the CI state needs the
head and whether the PR conflicts (`unrunnable`); the conflict state is not evaluated.

<!-- fr:journal kind=decision scope=plan id=settle-poll-committed-at created=2026-11-23T10:49:48+00:00 phase=1 -->
### settle-poll-committed-at · decision · The poll takes a committed_at(sha) callable beside the plan's signature (phase 1)

The no-CI wait needs the PR head's commit time, which the plan's `settle(...)` signature
did not carry. `poll.settle` takes `committed_at: Callable[[str], float]`; the verb passes
`fr.settle.target.committed_at` (the sha's time, else HEAD's, else now). PR discovery,
gate names and `ci none` live in `fr/settle/target.py`, keeping `settle_cmd` thin.

<!-- fr:journal kind=discovery scope=plan id=settle-acceptance-via-set-status created=2026-11-23T10:49:48+00:00 phase=1 -->
### settle-acceptance-via-set-status · discovery · implement-phase records cannot carry acceptance; rows moved with set-status (phase 1)

The shipped `implement-phase` step emits only `journal:plan` and `plan:ticks`, so its
record has no `acceptance:` section. Rows pr-settle-setting, pr-settle-verb and
pr-settle-managed were moved to `ci` with `fr acceptance set-status` (three
`chore(fr): acceptance` commits) with level refs on the new test names.

<!-- fr:journal kind=discovery scope=plan id=settle-recorded-pr-state created=2026-11-23T10:49:48+00:00 phase=1 -->
### settle-recorded-pr-state · discovery · A recorded PR that is no longer open is a refusal (exit 2) (phase 1)

The run cursor's `pr` can name a merged or closed PR. The poll refuses a view whose state
is not OPEN ("PR #n is MERGED, not open"), the same exit as no open PR (R4).

<!-- fr:journal kind=finding scope=plan id=p1-fast-tier-isolation-bash created=2026-11-23T10:49:48+00:00 phase=1 state=open review_scope=out -->
### p1-fast-tier-isolation-bash · finding [open] (reviewer: out of scope) · Fast tier's 4 red tests are environmental, not this branch's (phase 1)

`uv run pytest --fr-scope origin/main -n 2 -q --no-cov`: 4 failed, 6276 passed, 2 skipped
(1:14:21). All four are
`tests/unit/test_isolation_decision_core.py::test_a_relative_path_entry_holding_a_git_is_never_run`
(`[bin]`, `[./bin]`, `[]`, `[.]`). They fail on their own with
`FileNotFoundError: ... 'bash'`: the test runs `bash` under a relative-entry PATH, and
this host cannot resolve it. The branch changes neither that test nor
`packages/fr/src/fr/isolation` nor the hooks (`git diff origin/main` is empty there).
CI is this repo's suite evidence.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-23T10:49:48+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

managed.py is one predicate over its owners' constants and the brief edits are one line each; the import-cycle split (owners imported inside driver_managed) was settled at GREEN, so nothing was left to clean
