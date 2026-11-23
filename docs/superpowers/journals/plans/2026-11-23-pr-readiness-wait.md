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

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-23T12:34:23+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · evaluate.py:117 an unreported gate on a fresh head reads missing at once (phase 1)

Other checks finished, the gate not yet registered: missing/exit 4 regardless of age; R2 says pending until NO_CI_WAIT_SECONDS.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-23T12:34:23+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · pr_cmd.py:237 CiEvidenceRefused from declared_gates is uncaught (phase 1)

A malformed .fr/ci.yaml or no git gives a traceback and exit 1, outside R4.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-23T12:34:23+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · pr_cmd.py:252 HostRefusedError and permanent forge errors exit 75 (phase 1)

HostRefusedError subclasses the backend error; 404 and auth failures also exit 75, so an R10 loop retries forever.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-23T12:34:23+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · change fragment omits the older-fr refusal spec §A requires (phase 1)

.changes/feat-pr-readiness-wait.yaml

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-23T12:34:23+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · closeout_brief says no settle loop even for an unmanaged housekeeping PR (phase 1)

batch_drive.py:860; with a run the session's PR is chore/archive-<plan> or chore/closeout-<run>, unmanaged.

<!-- fr:journal kind=finding scope=plan id=p1-r6 created=2026-11-23T12:34:23+00:00 phase=1 state=open review_scope=in -->
### p1-r6 · finding [open] (reviewer: in scope) · poll.py:59 unsupported verdict drops a known head (phase 1)

The witness ends in a bare @.

<!-- fr:journal kind=finding scope=plan id=p1-r7 created=2026-11-23T12:34:23+00:00 phase=1 state=open review_scope=in -->
### p1-r7 · finding [open] (reviewer: in scope) · tests miss TP8 every-mode, a real glab/tea client, DRAFT, unrunnable/none cells (phase 1)

test_pr_settle_cmd.py:194, test_settle_evaluate.py:136

<!-- fr:journal kind=finding scope=plan id=p1-r8 created=2026-11-23T12:34:23+00:00 phase=1 state=open review_scope=in -->
### p1-r8 · finding [open] (reviewer: in scope) · pr_cmd.py:188 --wait default and ceiling are literals (phase 1)

Not DEFAULT_WAIT/WAIT_CEILING; the constant test does not cover the verb.

<!-- fr:journal kind=finding scope=plan id=p1-r9 created=2026-11-23T12:34:23+00:00 phase=1 state=open review_scope=in -->
### p1-r9 · finding [open] (reviewer: in scope) · settle/target.py:22 imports fr.commands; pr_view read twice (phase 1)

A cycle once run_cmd calls settle.

<!-- fr:journal kind=finding scope=plan id=p1-r10 created=2026-11-23T12:34:23+00:00 phase=1 state=open review_scope=out -->
### p1-r10 · finding [open] (reviewer: out of scope) · test_isolation_decision_core.py:663 runs bare bash under a PATH of git's dir (phase 1)

Host-dependent (bash in /usr/local/bin); the diff touches neither isolation nor the test (last changed 747e403d1).

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-23T12:34:23+00:00 phase=1 -->
### review-p1-1 · review · phase 1 code review: 10 findings (phase 1)

Findings raised: p1-r1 … p1-r10; p1-r1–r9 in scope, p1-r10 out of scope.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-23T12:34:23+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: evaluate.py:117 an unreported gate on a fresh head reads missing at once (phase 1)

5a39c9bca: an absent gate is pending until NO_CI_WAIT_SECONDS then missing, own hint; table cells added.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-23T12:34:23+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: pr_cmd.py:237 CiEvidenceRefused from declared_gates is uncaught (phase 1)

c8a084af5: CiEvidenceRefused refuses with exit 2; tested.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-23T12:34:23+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: pr_cmd.py:252 HostRefusedError and permanent forge errors exit 75 (phase 1)

c8a084af5: HostRefusedError exits 2; only warn and rate_limit forge errors exit 75, 404/401 exit 2; tested.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-23T12:34:23+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: change fragment omits the older-fr refusal spec §A requires (phase 1)

3306f6772: the fragment states the older-fr refusal.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-23T12:34:23+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: closeout_brief says no settle loop even for an unmanaged housekeeping PR (phase 1)

e365431a5: the sentence only when run is None; spec R5/§E amended to match.

<!-- fr:journal kind=finding scope=plan id=p1-r6-resolved created=2026-11-23T12:34:23+00:00 phase=1 state=fixed resolves=p1-r6 -->
### p1-r6-resolved · finding [fixed] · resolves p1-r6: poll.py:59 unsupported verdict drops a known head (phase 1)

c8a084af5: the unsupported verdict keeps the view's head.

<!-- fr:journal kind=finding scope=plan id=p1-r7-resolved created=2026-11-23T12:34:23+00:00 phase=1 state=fixed resolves=p1-r7 -->
### p1-r7-resolved · finding [fixed] · resolves p1-r7: tests miss TP8 every-mode, a real glab/tea client, DRAFT, unrunnable/none cells (phase 1)

c8a084af5: all 8 mode pairs, real RealGlabClient and RealTeaClient, DRAFT pinned, unrunnable/none cells.

<!-- fr:journal kind=finding scope=plan id=p1-r8-resolved created=2026-11-23T12:34:23+00:00 phase=1 state=fixed resolves=p1-r8 -->
### p1-r8-resolved · finding [fixed] · resolves p1-r8: pr_cmd.py:188 --wait default and ceiling are literals (phase 1)

c8a084af5: --wait default and help from poll.DEFAULT_WAIT/WAIT_CEILING; verb default tested.

<!-- fr:journal kind=finding scope=plan id=p1-r9-resolved created=2026-11-23T12:34:23+00:00 phase=1 state=fixed resolves=p1-r9 -->
### p1-r9-resolved · finding [fixed] · resolves p1-r9: settle/target.py:22 imports fr.commands; pr_view read twice (phase 1)

c8a084af5: target.py imports nothing from fr.commands; pr_cmd passes the recorded PR in; one pr_view per poll.

<!-- fr:journal kind=finding scope=plan id=p1-r10-resolved created=2026-11-23T12:34:23+00:00 phase=1 state=open resolves=p1-r10 out_of_scope=true -->
### p1-r10-resolved · finding [out-of-scope] · resolves p1-r10: test_isolation_decision_core.py:663 runs bare bash under a PATH of git's dir (phase 1)

Pre-existing, host-dependent test; not caused by this change.

<!-- fr:journal kind=finding scope=plan id=p1-fast-tier-isolation-bash-resolved created=2026-11-23T12:34:23+00:00 phase=1 state=open resolves=p1-fast-tier-isolation-bash out_of_scope=true -->
### p1-fast-tier-isolation-bash-resolved · finding [out-of-scope] · resolves p1-fast-tier-isolation-bash: Fast tier's 4 red tests are environmental, not this branch's (phase 1)

Same pre-existing host-dependent isolation test as p1-r10; not caused by this change.

<!-- fr:journal kind=decision scope=plan id=settle-read-shared created=2026-11-23T14:01:57+00:00 phase=2 -->
### settle-read-shared · decision · The verb and the deliver witness share one read, fr.settle.read.read_verdict (phase 2)

PR discovery, the first pr_view, the gate set, the poll and the forge-error rule
(only warn and rate_limit are transient, exit 75; a host refusal, 404 or auth
failure refuses, exit 2) moved from `pr_cmd.settle_cmd` into `read_verdict`, so
`fr pr settle` and `fr.settle.witness.settle_witness` (wait 0) cannot drift. The
witness raises `SettlePending` (exit 75) or `SettleRefused` (exit 2);
`deliver_witness` maps them to `typer.Exit` and run_cmd calls it after the
`derive()` block (5 added lines, the module budget holds).

<!-- fr:journal kind=decision scope=plan id=settle-witness-test-stub created=2026-11-23T14:01:57+00:00 phase=2 -->
### settle-witness-test-stub · decision · An autouse conftest stub records a fixed settle witness unless a test opts out (phase 2)

Every unit-test `deliver` resolve runs in a clone with no forge, and the real witness
refuses there (no origin repo). `tests/conftest.py`'s `_settle_witness_reads_no_forge`
replaces `fr.settle.witness.settle_witness` with `fix/fix:clean/green@stub`; a test
that requests `real_settle_witness` (`tests/unit/test_run_settle_witness.py`) gets
the real one over a fake forge. A subprocess-run `deliver` would not see the stub;
none exists in the suite today.

<!-- fr:journal kind=decision scope=plan id=settle-override-grammar created=2026-11-23T14:01:57+00:00 phase=2 -->
### settle-override-grammar · decision · The spec grammar restates SETTLE_MODES instead of importing the settings model (phase 2)

`fr.verification.spec_section.SETTLE_OVERRIDE_MODES` restates
`fr.settings.model.SETTLE_MODES` so the spec grammar reads no settings model; a test
pins the two equal. A second `settle.<key>:` line for the same key is an error naming
the line. `## PR settle` sits after `## Manual operations` in REQUIRED_SECTIONS.

<!-- fr:journal kind=discovery scope=plan id=settle-no-shape-change created=2026-11-23T14:01:57+00:00 phase=2 -->
### settle-no-shape-change · discovery · No artifact stamp moved; the new evidence key is a key of an existing dict (phase 2)

`settle` is one more key in `StepRecord.evidence`, the override is a journal
`decision` entry and a prose line to older spec readers; `fr validate artifacts`
stays green and `fr/artifacts/registry.py` is unchanged (spec §C).

<!-- fr:journal kind=discovery scope=plan id=settle-deliver-row-skills created=2026-11-23T14:01:57+00:00 phase=2 -->
### settle-deliver-row-skills · discovery · Row pr-settle-deliver moved to ci on the witness; its R9/R10 skill text is phase 3's (phase 2)

The row also cites R9 and R10 (the fix rules and fr-debugging's settle step), which
are skill text phase 3 ships with its own tripwire; that tripwire's test should be
added to the row's levels then.

<!-- fr:journal kind=discovery scope=plan id=settle-fast-tier-whole-suite created=2026-11-23T14:01:57+00:00 phase=2 -->
### settle-fast-tier-whole-suite · discovery · The branch's fast tier is now the whole unit suite, because tests/conftest.py changed (phase 2)

`--fr-scope` selects everything under a changed conftest.py, so the settle witness stub
puts every test in scope (about 17,000). On this loaded host the `-n 2` run reached 1%
in five minutes and was stopped with no failure; CI is the suite evidence (`tests: ci`).
Instead, 106 files that resolve `deliver` or read the evidence lists, sections,
manifests, spec grammar and settle code ran at `-n 6`: 2988 passed, 10 skipped and 3
failed, all three pinned deliver evidence lists in test_tripwire_shipped_workflows.py.
Those were fixed and the file re-ran green (12 passed).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-23T14:01:57+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

the settle line is one pattern and one helper beside the gate-line branch; the grammar's other branches were untouched, so nothing was left to extract

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t2 created=2026-11-23T14:01:57+00:00 phase=2 -->
### no-refactor-p2-t2 · discovery · no-refactor-because P2.T2 (phase 2)

effective_modes gained two small readers (spec, journal) behind one precedence rule; the verb's resolution of spec and journal is one helper, nothing duplicated

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-23T14:01:57+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

_settle_section is one function over run_modes with one source-label table; nothing to clean
