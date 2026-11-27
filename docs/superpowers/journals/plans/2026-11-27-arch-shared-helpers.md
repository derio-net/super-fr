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
