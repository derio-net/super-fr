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
