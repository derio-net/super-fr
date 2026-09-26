# Journal: 2026-09-26-dynamic-brainstorm-question-rounds

<!-- fr:journal kind=decision scope=plan id=plan-three-phases created=2026-09-26T12:45:07 -->
### plan-three-phases · decision · Three phases: record v2 skeleton -> gate -> contract prose

Phase 1 is the walking skeleton (record kind bump, dogfooded via fr migrate artifacts on this run's own live records so later phases resolve on v2). Gate before prose so the prose never promises a verification that does not exist.

<!-- fr:journal kind=discovery scope=plan id=record-fixtures-hardcoded-schema-version created=2026-09-26T13:03:32 phase=1 -->
### record-fixtures-hardcoded-schema-version · discovery · Several test fixtures hardcoded record schema_version: 1, breaking on the v2 bump (phase 1)

Bumping RECORD_SCHEMA_VERSION broke three fixtures that build a record body from scratch rather than through render_template: tests/unit/record_support.py's implement_record, test_record_apply.py's _review_record, and test_validate_artifacts.py's GOOD_RECORD, plus test_record_schema.py's own SPEC_EXAMPLE and its schema_version-refused-with-a-named-needle case. All now reference the live fr.record.model.RECORD_SCHEMA_VERSION constant instead of the literal 1, the same fix record/template.py needed. Worth remembering for phase 2/3 and any future record-shape bump: grep for `"schema_version": 1` / `schema_version: 1` in tests/ before assuming the version-bump obligations end at registry.py + model.py + migration + template.
