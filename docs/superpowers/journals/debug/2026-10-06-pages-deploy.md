# Journal: 2026-10-06-pages-deploy

<!-- fr:journal kind=repro scope=debug id=8d1839f764fb created=2026-10-06T16:36:03+00:00 -->
### 8d1839f764fb · repro · A migration-gate refusal in the report render skips the whole Pages deploy

pages.yml runs `fr acceptance report ... --out _site/acceptance/index.html` as a plain step between "Assemble site" and the three Pages actions. Repro (scratch clone, one plan stale by setting its `fr_version` ceiling to `<5.0.0`, `CI=true`): the render exits 2 with "artifacts ... must be migrated before this command can run" and writes no page. A failed step with no `continue-on-error` makes GitHub Actions skip every later step, so `upload-pages-artifact`/`deploy-pages` never run and the explainers do not ship either. Not observed live: the last 47 pages.yml runs were all green, so this is latent. Separately, `concurrency: {group: pages, cancel-in-progress: true}` lets a later push cancel a deploy that is already running.

<!-- fr:journal kind=root-cause scope=debug id=ea6cc1d81fef created=2026-10-06T16:36:28+00:00 -->
### ea6cc1d81fef · root-cause · pages.yml makes the explainers deploy hostage to the report render and to the next push

The deploy job is all-or-nothing: the report render is an ordinary step ahead of `upload-pages-artifact`/`deploy-pages`, so its failure (a migration-gate refusal on stale artifacts, by design under `CI=true`) skips the deploy, and every Pages deploy replaces the whole site, so the explainers stay at their previous version. The same coupling shows up in `cancel-in-progress: true`: a later push to main cancels a deploy that is already running, instead of queueing behind it. The refusal itself is correct (spec 2026-10-03 §A step 5: a report rendered over unmigrated artifacts would describe a matrix the shipped fr cannot read, so no `FR_SKIP_MIGRATION`). What is wrong is that refusal reaching the explainers. Decision (from the batch title, which answers #924's "to decide"): the render fails alone; the site still deploys with an honest placeholder at /acceptance/ saying the report was not rendered at this commit, and the run still goes red after the deploy; `cancel-in-progress: false`.

<!-- fr:journal kind=finding scope=debug id=pages-deploy-coupled created=2026-10-06T16:52:01+00:00 state=fixed -->
### pages-deploy-coupled · finding [fixed] · Render fails alone; deploy is never cancelled

pages.yml: render step gets id report + continue-on-error; on steps.report.outcome == failure a placeholder /acceptance/index.html names the commit and links the run and the committed report_linked.md; after deploy-pages a step fails the run, so the refusal stays red without holding the explainers back. concurrency cancel-in-progress: false. FR_SKIP_MIGRATION still absent (spec 2026-10-03 §A step 5 kept). Pinned first by five failing tests in tests/unit/test_pages_workflow.py (one executes the placeholder script); matrix row pages-deploy-survives-report-refusal.

<!-- fr:journal kind=review scope=debug id=148252a4bb8c created=2026-10-06T16:54:09+00:00 -->
### 148252a4bb8c · review · Independent review: one finding, fixed

A read-only reviewer checked outcome-vs-conclusion semantics, the heredoc inside the YAML block scalar, injection (runner-controlled vars only, no ${{ }} in run blocks), placeholder overwrite of a partial report, cancel-in-progress: false queue semantics, and that the tests are not tautological: no high-confidence issues. One lower-confidence observation acted on: a failing step inside the job carrying environment: github-pages would mark the deployment record failed though the site went live. The red signal moved to a separate report-status job (needs: deploy, gated on the deploy job's report output); test_a_failed_render_still_fails_the_run_after_deploying was rewritten first and seen red.
