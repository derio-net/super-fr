# Journal: 2026-09-18-acceptance-journal-state-updates

<!-- fr:journal kind=decision scope=spec id=cli-shape created=2026-09-18T11:03:07 -->
### cli-shape · decision · Use explicit state-mutation commands

Operator selected acceptance set-status/add-level and journal update; duplicate journal add IDs must fail loudly rather than silently no-op.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-18T11:03:38 -->
### spec-review · review · Spec review passed

Verified the issue's commands fit existing acceptance mutation/report flow and journal parser/serializer behavior. Explicit commands avoid ambiguous upsert semantics; no artifact shape changes are needed.
