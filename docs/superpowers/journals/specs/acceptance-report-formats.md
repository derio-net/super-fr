# Journal: acceptance-report-formats

<!-- fr:journal kind=decision scope=spec id=dec-1-names created=2026-07-25T04:40:07 -->
### dec-1-names · decision · Committed set: report_local.html, report_linked.html, report_linked.md

Exactly as operator specified. report.html leaves the committed set.

<!-- fr:journal kind=decision scope=spec id=dec-2-adhoc-html created=2026-07-25T04:40:07 -->
### dec-2-adhoc-html · decision · report.html reverts to ad-hoc + gitignored

GitHub doesn't render committed .html; report.html is git-stamped ad-hoc (CI github / local), gitignored; committed copy git rm'd.

<!-- fr:journal kind=decision scope=spec id=dec-3-md-github created=2026-07-25T04:40:07 -->
### dec-3-md-github · decision · report_linked.md uses github links (GitHub renders markdown)

The whole point: markdown renders inline on github.com, unlike committed html.

<!-- fr:journal kind=decision scope=spec id=dec-5-no-git-in-check created=2026-07-25T04:40:07 -->
### dec-5-no-git-in-check · decision · No git-tracking logic in check; writers delete stale report.github.html

check stays a filesystem existence-gate on the new set; deterministic writers clean up the renamed legacy file; operator one-liner handles git rm --cached report.html.

<!-- fr:journal kind=review scope=spec id=rev-consistency created=2026-07-25T04:40:07 -->
### rev-consistency · review · Spec review: DEC-5 de-cleverer'd; all refs real

Dropped git-coupling from check; regeneration removes stale report.github.html. render()/LinkBuilder/REPORT_SET/check/scaffold all exist.
