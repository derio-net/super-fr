# Journal: 2026-09-26-dynamic-brainstorm-question-rounds

<!-- fr:journal kind=decision scope=plan id=plan-three-phases created=2026-09-26T12:45:07 -->
### plan-three-phases · decision · Three phases: record v2 skeleton -> gate -> contract prose

Phase 1 is the walking skeleton (record kind bump, dogfooded via fr migrate artifacts on this run's own live records so later phases resolve on v2). Gate before prose so the prose never promises a verification that does not exist.

<!-- fr:journal kind=discovery scope=plan id=record-fixtures-hardcoded-schema-version created=2026-09-26T13:03:32 phase=1 -->
### record-fixtures-hardcoded-schema-version · discovery · Several test fixtures hardcoded record schema_version: 1, breaking on the v2 bump (phase 1)

Bumping RECORD_SCHEMA_VERSION broke three fixtures that build a record body from scratch rather than through render_template: tests/unit/record_support.py's implement_record, test_record_apply.py's _review_record, and test_validate_artifacts.py's GOOD_RECORD, plus test_record_schema.py's own SPEC_EXAMPLE and its schema_version-refused-with-a-named-needle case. All now reference the live fr.record.model.RECORD_SCHEMA_VERSION constant instead of the literal 1, the same fix record/template.py needed. Worth remembering for phase 2/3 and any future record-shape bump: grep for `"schema_version": 1` / `schema_version: 1` in tests/ before assuming the version-bump obligations end at registry.py + model.py + migration + template.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-09-26T13:06:41 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Template gate wiring untested: tests recompute gated= instead of going through record_brief (phase 1)

tests/unit/test_record_template.py copied record_brief's gated= logic; deleting the wiring would stay green.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-09-26T13:06:41 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · Unreadable-record refusal not asserted byte-identical; no invalid-YAML case (phase 1)

test_migration_record_questions.py checked only a missing stamp and only a schema-invalid body.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-09-26T13:06:41 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · v1 fixture lacks the `schema_version: 1` line every real template-rendered record carries (phase 1)

The stamp-rewrite path for real in-flight records was untested.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-09-26T13:06:41 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · Migration guard refuses an empty record that parse_record accepts (phase 1)

record_questions._guard raised on None; the file would stay stale and block the CLI gate.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-09-26T13:06:41 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · Whitespace-only questions.reason accepted for rounds: 2 (phase 1)

model.py used `not self.reason`; phase 2 writes the reason into a journal decision.

<!-- fr:journal kind=review scope=plan id=review-phase-1 created=2026-09-26T13:06:41 phase=1 -->
### review-phase-1 · review · Phase 1 code review: 5 in-scope findings, 0 out of scope (phase 1)

Dispatched code reviewer over 6342e663..HEAD (packages, tests) against spec §3.B, plan 01.yaml and artifact-versioning.md. No blocking issues; versioning obligations met. Raised p1-r1..p1-r5 (2 medium, 3 low), all verified against the code and fixed with tests. Two sub-threshold notes (message names live version; frozen-ness tested by config) not filed.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-09-26T13:06:41 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Template gate wiring untested: tests recompute gated= instead of going through record_brief (phase 1)

New test drives record_brief for the gated brainstorm step; implement-phase brief asserted to carry no questions hint.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-09-26T13:06:41 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: Unreadable-record refusal not asserted byte-identical; no invalid-YAML case (phase 1)

Refusal asserts byte-identity; new invalid-YAML (truncated) case asserts failed + byte-identical.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-09-26T13:06:41 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: v1 fixture lacks the `schema_version: 1` line every real template-rendered record carries (phase 1)

Stamp test parametrized over no-stamp and schema_version: 1; the latter asserts exact text with only the stamp line changed.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-09-26T13:06:41 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: Migration guard refuses an empty record that parse_record accepts (phase 1)

Guard treats None as {} like parse_record; new test stamps a comment-only record.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-09-26T13:06:41 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: Whitespace-only questions.reason accepted for rounds: 2 (phase 1)

Validator strips reason; parametrized whitespace case added.

<!-- fr:journal kind=decision scope=plan id=p2-rounds-share-one-walk created=2026-09-26T13:20:43 phase=2 -->
### p2-rounds-share-one-walk · decision · operator_answered_since is now "at least one answered round" over answered_rounds_since's walk (phase 2) (phase 2)

P2.T1.S3. The two predicates read the same records by the same rules (main thread,
stamped at/after `since`, answered = non-empty `toolUseResult.answers` paired by
tool_use id). Every asked id belongs to exactly one round and a round counts when any
of its ids was answered, so `bool(answered_rounds_since(...))` equals the old result
exactly; operator_answered_since delegates to it and its existing tests stay green
unchanged. The gate calls answered_rounds_since once and derives the observed/unobserved
split from it, so the two can never disagree inside one resolve.

<!-- fr:journal kind=decision scope=plan id=p2-round-two-needs-a-spec created=2026-09-26T13:20:43 phase=2 -->
### p2-round-two-needs-a-spec · decision · A declared second round with no spec to journal it on is refused, like --no-questions (phase 2) (phase 2)

Spec §3.C says the `gate-question-rounds-<step>` decision goes "to the same journal"
as the no-questions entry. That journal is the spec this resolve emits, else one an
earlier step emitted; with neither, review r1-5's reasoning applies unchanged — the
reason would reach only stderr. So `rounds: 2` without a reachable spec is refused
before the transcript is read and before any byte moves. The brainstorm step always
emits its spec, so the shipped fr-goal path never hits it.

<!-- fr:journal kind=finding scope=plan id=p2-member-resolve-dropped-gate-flags created=2026-09-26T13:20:43 phase=2 state=open review_scope=in -->
### p2-member-resolve-dropped-gate-flags · finding [open] (reviewer: in scope) · Gate flags on a grouped-member resolve were silently dropped (phase 2) (phase 2)

Found by the new "questions on a resolve that clears no gate" test: `_resolve_body`
delegates a `for_each` member (implement-phase, review-phase) to `_resolve_member`
BEFORE the review r1-7 "clears none" refusal, so `--no-questions --reason` (and now
`questions`) on a member resolve exited 0 with the flags ignored — on both the flag
path and the record path. Fixed: the member branch refuses gate flags first, via one
`_refuse_gate_flags` helper shared with the top-level refusal. Both paths tested in
tests/unit/test_run_question_rounds.py.

<!-- fr:journal kind=finding scope=plan id=p2-member-resolve-dropped-gate-flags-resolved created=2026-09-26T13:20:43 phase=2 state=fixed resolves=p2-member-resolve-dropped-gate-flags -->
### p2-member-resolve-dropped-gate-flags-resolved · finding [fixed] · resolves p2-member-resolve-dropped-gate-flags: Gate flags on a grouped-member resolve were silently dropped (phase 2) (phase 2)

member branch now refuses gate flags before delegating; tested on both paths.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · Round-3 refusal suggested --no-questions, which would record a false 'cleared without asking' (phase 2)

question_rounds_refusal pointed at the bypass whose provenance (answered_by: agent) contradicts an operator who answered.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · Unverified notice claimed a rounds: 1 declaration was recorded when nothing is written (phase 2)

Only rounds: 2 journals.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · Round.answered is always True (phase 2)

Constant field; its test only checked the code against itself.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · answered_rounds_since duplicated _this_session (phase 2)

Third copy of the harness/session front half; plan P2.T1.S3 asked for sharing.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · Test Plan 3 only partly covered: declined gate, ungated step, no-spec round-two, member --no-questions untested (phase 2)

The _clears_gate branch and two new refusals had no test.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · Retry idempotence keyed on id only kept a stale body; retry test hand-wrote the entry (phase 2)

A retry with a changed reason silently kept the first body.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-09-26T13:37:27 phase=2 state=open review_scope=out -->
### p2-r7 · finding [open] (reviewer: out of scope) · Flag-path journal append not rolled back when a later resolve step refuses (phase 2)

Pre-existing for gate-no-questions entries (guard=None on the flag path); the round-two entry inherits it.

<!-- fr:journal kind=finding scope=plan id=p2-r8 created=2026-09-26T13:37:27 phase=2 state=open review_scope=in -->
### p2-r8 · finding [open] (reviewer: in scope) · Bookkeeping tool calls between question batches split one round and can strand the gate (phase 2)

Reviewer tagged this out of scope as a spec design risk; reclassified in scope by the orchestrator because this change introduces the round rule and the n>2 refusal that makes it strand a gate.

<!-- fr:journal kind=review scope=plan id=review-phase-2 created=2026-09-26T13:37:27 phase=2 -->
### review-phase-2 · review · Phase 2 code review: 7 in-scope findings (1 reclassified), 1 out of scope (phase 2)

Dispatched code reviewer over 37410263 and eb4da954 against spec §3.B/§3.C and plan 02.yaml. Grouping rule, operator_answered_since equivalence, verdict table, pre-write refusals and both threading paths verified correct. Raised p2-r1 (medium) and p2-r2..r6 (low) in scope, p2-r7/p2-r8 out of scope; p2-r8 reclassified in. Fixes in ab531445, each pinned by tests; 384 targeted tests re-run green by the orchestrator. Side effect accepted: a --no-questions retry with a changed reason is now refused rather than silently keeping the stale entry (same rule as p2-r6).

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: Round-3 refusal suggested --no-questions, which would record a false 'cleared without asking' (phase 2)

Refusal now offers --state failed and re-running the step; tests assert --no-questions absent from every refusing verdict.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: Unverified notice claimed a rounds: 1 declaration was recorded when nothing is written (phase 2)

rounds: 1 reads 'accepted, unverified'; rounds: 2 keeps 'recorded as claimed too'; both pinned.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: Round.answered is always True (phase 2)

Field removed; tests updated.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: answered_rounds_since duplicated _this_session (phase 2)

answered_rounds_since uses _this_session; None semantics unchanged, existing tests green.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: Test Plan 3 only partly covered: declined gate, ungated step, no-spec round-two, member --no-questions untested (phase 2)

Four refusal tests over both paths asserting exit 2, byte-identical snapshot, unmoved HEAD.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: Retry idempotence keyed on id only kept a stale body; retry test hand-wrote the entry (phase 2)

_append_gate_decision refuses a differing body before any write; real first-resolve retry test and changed-reason test on both paths.

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-09-26T13:37:27 phase=2 state=open resolves=p2-r7 out_of_scope=true -->
### p2-r7-resolved · finding [out-of-scope] · resolves p2-r7: Flag-path journal append not rolled back when a later resolve step refuses (phase 2)

Existing behaviour of the flag path for gate-no-questions entries since r1-6; retry idempotence is the existing mitigation. Not caused by this change.

<!-- fr:journal kind=finding scope=plan id=p2-r8-resolved created=2026-09-26T13:37:27 phase=2 state=fixed resolves=p2-r8 -->
### p2-r8-resolved · finding [fixed] · resolves p2-r8: Bookkeeping tool calls between question batches split one round and can strand the gate (phase 2)

ROUND_NEUTRAL_TOOLS (Claude Code progress trackers) do not close a round; TodoWrite-between = 1 round, Read-between = 2 rounds pinned; spec §3.C updated.
