# Journal: 2026-09-26-acceptance-set-status-drop-level

<!-- fr:journal kind=decision scope=spec id=d-carrier created=2026-09-26T00:39:23 -->
### d-carrier · decision · Drops are carried CLI-only via RecordTarget; the record kind's shape is unchanged

Operator chose CLI-only over adding `drop_levels` to AcceptanceItem. The record artifact kind keeps version 1 (no stamp bump, no migration), so the release stays a patch. Step records still cannot drop refs; a step that needs one runs the verb.

<!-- fr:journal kind=decision scope=spec id=d-conflict created=2026-09-26T00:39:23 -->
### d-conflict · decision · The same ref in both --level and --drop-level is refused, exit 2

Contradictory intent in one call. It is refused with nothing changed, like an absent-ref drop.

<!-- fr:journal kind=decision scope=spec id=d-empty-evidence created=2026-09-26T00:39:23 -->
### d-empty-evidence · decision · A drop that empties a ci/scheduled row's evidence is allowed

The status is the operator's explicit call in the same command, with --notes; set-status never judged status against evidence, and `fr acceptance check` stays the gate.
