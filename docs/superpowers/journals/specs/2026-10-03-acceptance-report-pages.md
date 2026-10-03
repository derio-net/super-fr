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

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-10-03T18:01:50+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Spec's Test Plan names no acceptance-matrix rows

Rows existed (added at brainstorm, citing #R1-#R6) but the spec did not name them, or say that the PR touches docs/acceptance/**. Reviewer evidence: check.py:242-266.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-10-03T18:01:50+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · index.html foot row already has three spans; the new link is the fourth

Evidence docs/explainers/index.html:577-581.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-10-03T18:01:50+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · The CLI-entry migration gate can refuse the render in CI, which R4's 'never gates' leaves out

trigger.py:390-405; report is not in READ_ONLY_COMMANDS.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-10-03T18:01:50+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · The render test checks neither the git stamp nor the repo-relative --out CI uses

acceptance_cmd.py:198-205; report.py:482-491; test_acceptance_report.py:280-292.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-03T18:01:50+00:00 -->
### spec-review-1 · review · independent spec review: 4 findings

fr-spec-reviewer raised s1-s4, all in scope; decisions q1-q5 all honoured; every named file was verified with a file:line.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-10-03T18:01:50+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Spec's Test Plan names no acceptance-matrix rows

Added §E naming the three rows, their requirement ids, the matrix/report touch, and the post-merge debt; Test Plan step 1 now says the trigger comes from the matrix rows.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-10-03T18:01:50+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: index.html foot row already has three spans; the new link is the fourth

§B now says fourth span, placed on the line after 580 with the same markup.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-10-03T18:01:50+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: The CLI-entry migration gate can refuse the render in CI, which R4's 'never gates' leaves out

§A step 5 states the gate refusal is accepted (same as acceptance-report.yml today, already caught by validate-artifacts); FR_SKIP_MIGRATION is not set; R4 is scoped to row statuses.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-10-03T18:01:50+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: The render test checks neither the git stamp nor the repo-relative --out CI uses

§D render test now lives in test_acceptance_report.py, uses the repo-relative --out _site/acceptance/index.html, and asserts the (ref <sha>) stamp.
