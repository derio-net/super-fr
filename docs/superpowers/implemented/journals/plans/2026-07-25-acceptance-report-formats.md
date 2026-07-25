# Journal: 2026-07-25-acceptance-report-formats

<!-- fr:journal kind=review scope=plan id=rev-independent created=2026-07-25T04:58:37 -->
### rev-independent · review · Independent review: no blockers/majors; 3 nits

Markdown escaping (md_cell order), determinism, and REPORT_SET tuple plumbing all verified sound. Fixed: stale --out help, 'both reports' wording, and angle-bracketed markdown link destinations (robust for arbitrary ref paths).

<!-- fr:journal kind=finding scope=plan id=f1-help created=2026-07-25T04:58:37 state=fixed -->
### f1-help · finding [fixed] · Stale --out help + 'both reports' wording

Updated --out help to name the 3-file set; check/tripwire messages say 'the report set'.

<!-- fr:journal kind=finding scope=plan id=f3-md-links created=2026-07-25T04:58:37 state=fixed -->
### f3-md-links · finding [fixed] · Markdown link destinations now angle-bracketed

[label](<url>) form so a ref path with a space/paren can't break the link; latent but cheap hardening for consumer repos.
