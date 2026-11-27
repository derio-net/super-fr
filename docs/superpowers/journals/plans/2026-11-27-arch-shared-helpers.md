<!-- fr:journal-schema=4 -->
# Journal: 2026-11-27-arch-shared-helpers

<!-- fr:journal kind=discovery scope=plan id=p1-admit-caller created=2026-11-27T09:37:59+00:00 phase=1 -->
### p1-admit-caller · discovery · triage/admit.py also imported claims._created (phase 1)

The plan named only claims' own caller, but fr/triage/admit.py imported the private `_created` too (mypy found it). It now calls parse_as_utc(comment.get("created_at")), like claims.

<!-- fr:journal kind=discovery scope=plan id=p1-record-support-name created=2026-11-27T09:37:59+00:00 phase=1 -->
### p1-record-support-name · discovery · tests/unit/record_support.py already defines a different write_record (phase 1)

test_record_lens.py imports both, so it imports the new helper as `write_record_text`; the helper keeps the spec's name everywhere else.

<!-- fr:journal kind=discovery scope=plan id=p1-unhashable-key created=2026-11-27T09:37:59+00:00 phase=1 -->
### p1-unhashable-key · discovery · PyYAML itself refuses an unhashable key (phase 1)

The unhashable-key test asserts PyYAML's own `found unhashable key` error surfaces (the duplicate check skips it, as before), not a successful load.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-27T09:37:59+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

prose, mirrors and stamps only; nothing to test-drive or clean

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-27T09:51:13+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · admit.py:80-82 comment left dangling after the split parse_as_utc(...) call (phase 1)

ruff format split the call and left the comment after the closing paren. Fix: comment on its own line above the call.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-27T09:51:13+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Five hermetic-git modules import unused apply_hermetic_git behind noqa F401 (phase 1)

test_gatebackfill_{candidates,delivery,discharged,render}.py and test_status_owed.py; only test_merge_evidence.py calls it. Fix: import only hermetic_git.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-27T09:51:13+00:00 phase=1 state=open review_scope=out -->
### p1-r3 · finding [open] (reviewer: out of scope) · parse_as_utc body-scan guard would not catch a re-added copy of the removed readers (phase 1)

tests/unit/test_triage_timestamps.py:114 matches parse_as_utc's exact body; none of the five removed copies had
it. Spec R8 defines the guard this way, so the change meets its contract. A broader heuristic (fromisoformat +
replace(tzinfo=...) outside the owners) hits three more naive-to-UTC readers no issue or spec covers
(run/telemetry.py:230 parse_timestamp, triage/pacing_state.py:55 _parsed, triage/quota.py:51 budget_from_json),
so it needs a decision about those first: a follow-up, not this batch.

<!-- fr:journal kind=review scope=plan id=review-p1-1 created=2026-11-27T09:51:13+00:00 phase=1 -->
### review-p1-1 · review · Phase 1 review: 3 findings (p1-r1, p1-r2 in; p1-r3 out) (phase 1)

Independent reviewer compared every removed body with its replacement (strict loaders, the five naive-as-UTC
readers, _created_since, _pr_time, admit.py), the --gate help bytes, the 11 record payloads and stems, and the
hermetic-git activation in the 6 modules plus stub_fetch's importers; found no behaviour change and no stale
reference; ran the touched modules and new guards green. Findings p1-r1, p1-r2 (fixed in f3af52681), p1-r3 (out).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-27T09:51:13+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: admit.py:80-82 comment left dangling after the split parse_as_utc(...) call (phase 1)

Comment moved above `at = parse_as_utc(comment.get("created_at"))` (f3af52681); test_triage_admit green.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-27T09:51:13+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Five hermetic-git modules import unused apply_hermetic_git behind noqa F401 (phase 1)

The five modules import only `hermetic_git  # noqa: F401` (f3af52681); the seven affected modules pass (152 passed).

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-27T09:51:13+00:00 phase=1 state=open resolves=p1-r3 out_of_scope=true -->
### p1-r3-resolved · finding [out-of-scope] · resolves p1-r3: parse_as_utc body-scan guard would not catch a re-added copy of the removed readers (phase 1)

True, but not caused by this change: the guard is exactly what spec R8 asks for, and widening it means deciding about three other naive-to-UTC readers outside this batch. Filed as a follow-up at deliver.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-27T09:56:55+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · test_gatebackfill_closes.py:90 still copies the null-device GIT_CONFIG setenv; hand-listed guards cannot catch it

tests/unit/test_gatebackfill_closes.py:90-91 set GIT_CONFIG_GLOBAL=/dev/null and GIT_CONFIG_NOSYSTEM=1 (beside its
HOME); tests/unit/test_hermetic_git.py's MODULES list never looks at it. Reviewer also proposed globbing the R4
record guard in tests/unit/test_record_helpers.py.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-27T09:56:55+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · No test requests the hermetic_git fixture and asserts the env it sets; activation is only checked by AST text

tests/unit/test_hermetic_git.py tested apply_hermetic_git directly and the usefixtures marks as text only.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-27T09:56:55+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · The parse_aware/parse_as_utc swaps at _created_since, _pr_time and _worth_reading have no caller-level tests for awkward inputs

collect.py:1346, triage_batch_cmd.py:2423 and usage/backfill.py:165 had no tests for None, empty, naive or garbage stamps.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-27T09:56:55+00:00 -->
### lens-review-1 · review · Lens review: docs-accuracy none; tests 3 findings (l-tests-r1..r3), all fixed

docs-accuracy: the nine stamped pages, the rule, its mirror and sync-opencode.py checked against the code; the
--gate help stays byte-identical; the shape file matches the diff. No findings.
tests: three in-scope findings, fixed in 74767434d.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-27T09:56:55+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: test_gatebackfill_closes.py:90 still copies the null-device GIT_CONFIG setenv; hand-listed guards cannot catch it

test_gatebackfill_closes.py keeps its HOME and calls apply_hermetic_git(monkeypatch); test_hermetic_git.py gains
a glob over tests/unit/*.py that fails any module but hermetic_git.py pointing GIT_CONFIG_GLOBAL at the null device
itself. The R4 record guard stays scoped to its eleven modules: a glob false-positives on four modules that write
into r1.records for other reasons (test_migration_trigger, test_run_resolve_tests_ci, test_run_suite_reuse,
test_run_tests_log_opencode). Spec R5 and Background updated.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-27T09:56:55+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: No test requests the hermetic_git fixture and asserts the env it sets; activation is only checked by AST text

test_hermetic_git.py runs the fixture itself and asserts both variables; test_gatebackfill_render.py gains a probe that its module-level usefixtures takes effect.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-27T09:56:55+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: The parse_aware/parse_as_utc swaps at _created_since, _pr_time and _worth_reading have no caller-level tests for awkward inputs

tests/unit/test_timestamp_callers.py parametrizes _created_since and _pr_time over None, empty, garbage, naive, Z and offset stamps; test_usage_backfill.py tests _worth_reading with unreadable, naive old, naive recent and Z captured_at.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved-2 created=2026-11-27T09:57:29+00:00 phase=1 state=open resolves=p1-r3 tracked_by=https://github.com/derio-net/super-fr/issues/1725 -->
### p1-r3-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1725] · resolves p1-r3: parse_as_utc body-scan guard would not catch a re-added copy of the removed readers (phase 1)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1725.
