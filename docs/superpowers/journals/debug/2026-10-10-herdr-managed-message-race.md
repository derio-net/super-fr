# Journal: 2026-10-10-herdr-managed-message-race

<!-- fr:journal kind=repro scope=debug id=stale-idle-snapshot created=2026-10-10T05:38:50+00:00 -->
### stale-idle-snapshot · repro · Managed message can race a previously idle source becoming busy

Independent review identified runner.message under-lock recheck validating name/harness but not fresh agent_status/interactive_ready. Wave-driver idle snapshot can precede working/blocked transition; a locked message can still send prompt. Reuse feat/1089 and PR1115; smallest additional fail-closed state/readiness predicate, no live controls or expanded feature scope.

<!-- fr:journal kind=root-cause scope=debug id=identity-without-current-eligibility created=2026-10-10T05:42:28+00:00 -->
### identity-without-current-eligibility · root-cause · Under-lock identity check omitted current eligibility

Five deterministic race cases failed before the fix with DID NOT RAISE: working/blocked/unknown and false/missing readiness after earlier idle snapshot. The existing pane lock prevents cooperating writers, but fresh agent identity alone did not prove current idle input eligibility. Added only fresh agent_status in idle/done and interactive_ready is True before descriptor handback save/prompt. Regression also proves no prompt and unchanged descriptor; both idle/done positive paths remain accepted.

<!-- fr:journal kind=finding scope=debug id=managed-message-fresh-eligibility created=2026-10-10T05:42:32+00:00 state=fixed -->
### managed-message-fresh-eligibility · finding [fixed] · Fail closed on fresh busy or unready managed target

Five-line runner predicate fixed the independent finding. 166 targeted runner/managed/restart/replacement tests passed, including stale idle snapshot transitioning working under the lock and no side effects. Ruff passed; mypy passed all eight fr-herdr source files. No native session mutations or broader source changes.
