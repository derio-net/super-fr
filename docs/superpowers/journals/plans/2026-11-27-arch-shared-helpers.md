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
