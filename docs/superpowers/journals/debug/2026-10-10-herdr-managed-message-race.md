# Journal: 2026-10-10-herdr-managed-message-race

<!-- fr:journal kind=repro scope=debug id=stale-idle-snapshot created=2026-10-10T05:38:50+00:00 -->
### stale-idle-snapshot · repro · Managed message can race a previously idle source becoming busy

Independent review identified runner.message under-lock recheck validating name/harness but not fresh agent_status/interactive_ready. Wave-driver idle snapshot can precede working/blocked transition; a locked message can still send prompt. Reuse feat/1089 and PR1115; smallest additional fail-closed state/readiness predicate, no live controls or expanded feature scope.
