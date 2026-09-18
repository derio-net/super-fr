# Journal: 2026-09-19-gh-429-journal-hardening

<!-- fr:journal kind=decision scope=plan id=plan-approach created=2026-09-19T00:21:39 -->
### plan-approach · decision · Preserve append-only resolution

The plan changes only duplicate-create feedback and validation; it does not revive an update-in-place verb.

<!-- fr:journal kind=discovery scope=plan id=implementation-complete created=2026-09-19T00:28:23 phase=1 -->
### implementation-complete · discovery · All reported ambiguity paths now fail closed (phase 1)

Duplicate add uses exit 2 with resolve guidance, every command validates scope before path lookup, and parser duplicate-id detection prevents ambiguous resolution records.

<!-- fr:journal kind=review scope=plan id=phase-review created=2026-09-19T00:29:07 phase=1 -->
### phase-review · review · Phase review passed (phase 1)

Reviewed the command boundary ordering and parser behavior. Scope validation runs before path lookup, duplicate add remains non-mutating, and parse failure prevents resolve writes.
