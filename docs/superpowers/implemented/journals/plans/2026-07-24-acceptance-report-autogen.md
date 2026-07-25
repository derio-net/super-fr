# Journal: 2026-07-24-acceptance-report-autogen

<!-- fr:journal kind=finding scope=plan id=f1-eol-pin created=2026-07-24T17:43:44 state=fixed -->
### f1-eol-pin · finding [fixed] · Byte-compared report could false-fail on CRLF checkout

Added repo .gitattributes pinning docs/acceptance/report.html to 'text eol=lf'. Consumer-repo Windows CI + scaffolded .gitattributes noted as a follow-up (out of scope this PR).

<!-- fr:journal kind=finding scope=plan id=f2-init-degrade created=2026-07-24T17:43:45 state=fixed -->
### f2-init-degrade · finding [fixed] · scaffold.init report render could crash a partial scaffold

Wrapped render in try/except → skipped, not crash (mirrors add's warn-don't-roll-back). Reachable only by calling scaffold.init() directly (init_cmd resolves identity upfront); covered by test_init_degrades_when_report_identity_unresolvable.

<!-- fr:journal kind=finding scope=plan id=f3-resolve-paths created=2026-07-24T17:43:45 state=fixed -->
### f3-resolve-paths · finding [fixed] · add vs tripwire could diverge on symlinked root (sibling refs)

render_deterministic now resolves root/out_dir so all callers render byte-identically. Moot for super-fr (no sibling refs) but hardens consumers. Report bytes unchanged.

<!-- fr:journal kind=review scope=plan id=rev-independent created=2026-07-24T17:43:45 -->
### rev-independent · review · Independent code review: no blockers, no majors

Determinism verified (explicit matrix org/repo → no git dependency; probe=False; relpath lexical). --check writes nothing, exit 3 on drift / 1 on error. add regen matches tripwire params, never rolls back. 3 minor/nit findings all fixed.
