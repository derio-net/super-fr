# Front page, second pass

Spec: `docs/superpowers/specs/2026-11-12-front-page-second-pass-design.md`.

Two agentic phases. Phase 1 builds the figure mechanism for any page and uses it on two
new explainers (the wave driver and exit gates), so the front page's act-two sections have
pages to cite. Phase 2 rewrites the front page: two acts, six numbered sections, the card
grid, a terminal hero, four diagrams, a dark look of its own with a light variant, and
CSS-only motion.

Suite evidence is CI (`tests: ci`): the cloud container cannot run the install and
scenario integration tests. Each phase runs the targeted unit tests locally, commits,
pushes, and CI on the draft PR is the full-suite evidence.

No manual phase. The one post-merge step is the spec's Test Plan line (the published
site), gate `developer`.
