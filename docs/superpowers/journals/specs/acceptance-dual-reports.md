# Journal: acceptance-dual-reports

<!-- fr:journal kind=decision scope=spec id=dec-1-names created=2026-07-24T22:00:15 -->
### dec-1-names · decision · report.html (local) + report.github.html (github)

Keep existing local path stable; .github. infix for the github-links twin.

<!-- fr:journal kind=decision scope=spec id=dec-2-enforce-check created=2026-07-24T22:00:15 -->
### dec-2-enforce-check · decision · Enforce via fr acceptance check (gated on report existence), not a new workflow step

Only way ask #2 reaches EXISTING consumer repos with no per-repo workflow edit. Existence-gate bounds blast radius; report-less fixtures/repos unaffected.

<!-- fr:journal kind=decision scope=spec id=dec-3-github-ref-main created=2026-07-24T22:00:15 -->
### dec-3-github-ref-main · decision · github report pins ref=main (deterministic)

Matches #403 github determinism + report's sibling-pins-main shortcut.

<!-- fr:journal kind=decision scope=spec id=dec-4-keep-artifact created=2026-07-24T22:00:16 -->
### dec-4-keep-artifact · decision · Keep ephemeral CI artifact (zero-risk)

Committed github report supersedes it but removing is unrelated churn; artifact step runs after check so no clobber.

<!-- fr:journal kind=review scope=spec id=rev-blast-radius created=2026-07-24T22:00:16 -->
### rev-blast-radius · review · Spec review: fold-in is low blast radius

check() appends errors→exit 1; only init generates a report before check (update init→both); no import cycle. Design sound.
