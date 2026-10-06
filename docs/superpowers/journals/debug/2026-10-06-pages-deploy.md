# Journal: 2026-10-06-pages-deploy

<!-- fr:journal kind=repro scope=debug id=8d1839f764fb created=2026-10-06T16:36:03+00:00 -->
### 8d1839f764fb · repro · A migration-gate refusal in the report render skips the whole Pages deploy

pages.yml runs `fr acceptance report ... --out _site/acceptance/index.html` as a plain step between "Assemble site" and the three Pages actions. Repro (scratch clone, one plan stale by setting its `fr_version` ceiling to `<5.0.0`, `CI=true`): the render exits 2 with "artifacts ... must be migrated before this command can run" and writes no page. A failed step with no `continue-on-error` makes GitHub Actions skip every later step, so `upload-pages-artifact`/`deploy-pages` never run and the explainers do not ship either. Not observed live: the last 47 pages.yml runs were all green, so this is latent. Separately, `concurrency: {group: pages, cancel-in-progress: true}` lets a later push cancel a deploy that is already running.
