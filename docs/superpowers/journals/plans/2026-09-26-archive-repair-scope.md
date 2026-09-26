# Journal: 2026-09-26-archive-repair-scope

<!-- fr:journal kind=decision scope=plan id=canonical-spec-ref-lenient-on-moved-paths created=2026-09-26T15:51:05 phase=1 -->
### canonical-spec-ref-lenient-on-moved-paths · decision · canonical_spec_ref keeps repair's slug fallback for a path that no longer exists (phase 1)

The helper shortens to the bare filename unless the named path exists as a file different from the one slug resolution picks (same-name-different-path stays verbatim). A stale full path whose spec moved to implemented/specs/ still canonicalizes by slug, preserving repair's existing doctrine.

<!-- fr:journal kind=discovery scope=plan id=scoping-single-predicate created=2026-09-26T15:51:05 phase=1 -->
### scoping-single-predicate · discovery · Scoping lives in one _in_scope predicate; canonicalization in refs.canonical_spec_ref (phase 1)

T1.S3 and T2.S3 refactors were done as part of green: repair._in_scope is the sole scoping predicate, and _repair_meta delegates spec canonicalization to refs.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-09-26T15:51:05 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

docs/mirrors/fragment task; nothing to clean
