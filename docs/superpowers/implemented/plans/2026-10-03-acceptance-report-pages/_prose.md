# Publish the acceptance report on GitHub Pages — plan

One agentic phase. The spec's requirements are one reviewable ask: deploy one
combined Pages site that holds the explainers plus a fresh acceptance report at
`/acceptance/`, and link to it.

The only production surface is `.github/workflows/pages.yml`. The CLI already
supports `--out` with a non-deterministic, SHA-pinned render (spec §A,
reviewer-verified at `acceptance_cmd.py:198-205`), so the render test pins
existing behaviour. The workflow test is what drives the change.

The live deploy can only be proven after merge: the spec's Test Plan, plus the
`verify: post-merge` rows. No `[manual]` phase is needed, because merging
triggers the deploy (the PR touches `docs/acceptance/**`).
