# Journal: 2026-10-03-acceptance-report-pages

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-03T17:58:26+00:00 input=true -->
### operator-brief · discovery · Operator brief (verbatim)

I want to publish the acceptance coverage report in main (the linked variable), that is generated in ci, as a page in Github's Deployments. Is it built directly in main?

<!-- fr:journal kind=decision scope=spec id=q1-which-render created=2026-10-03T17:58:26+00:00 -->
### q1-which-render · decision · Publish a fresh CI render at main's SHA

Render in the deploy job with --link-mode github --ref <sha> (git-stamped, SHA-pinned links), not the committed report_linked.html.

<!-- fr:journal kind=decision scope=spec id=q2-site-layout created=2026-10-03T17:58:26+00:00 -->
### q2-site-layout · decision · One deploy workflow serves explainers plus /acceptance/

pages.yml assembles explainers and the report into one Pages artifact; Pages is one site per repo and each deploy replaces it.

<!-- fr:journal kind=decision scope=spec id=q3-trigger created=2026-10-03T17:58:26+00:00 -->
### q3-trigger · decision · Redeploy on main pushes touching explainers, acceptance or the renderer

Paths docs/explainers/**, docs/acceptance/**, packages/fr/src/fr/acceptance/**, plus workflow_dispatch.

<!-- fr:journal kind=decision scope=spec id=q4-red-matrix created=2026-10-03T17:58:26+00:00 -->
### q4-red-matrix · decision · Publish even when the matrix has failing rows

No acceptance-check gate before deploy; a red report is the one people most need to see.

<!-- fr:journal kind=decision scope=spec id=q5-verify-link created=2026-10-03T17:58:26+00:00 -->
### q5-verify-link · decision · Operator verifies post-merge; link from explainers index and README badge

Operator chose the recommended option and added: also a link/badge in the README.
