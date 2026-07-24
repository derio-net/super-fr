# Journal: 2026-07-24-isolation-host-modes

<!-- fr:journal kind=discovery scope=plan id=spec-row-manual-repair created=2026-07-24T11:48:52 -->
### spec-row-manual-repair · discovery · Spec table row hand-added — _append_spec_row false-idempotency (known bug)

fr plan create reported success but wrote no Implementation Plans row: the idempotence guard scans the whole spec and the plan slug is a substring of the spec's own filename. Row added manually; separate bugfix PR already owed from the hermes archival session.
