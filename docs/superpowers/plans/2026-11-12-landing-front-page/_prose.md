# Landing front page

One agentic phase, because the three asks (the landing renderer, the essay's move,
the top bar) are one change to `scripts/build-site.py` and the front page's source,
reviewed together: the bar's anchors are the landing's page-list ids, and the essay's
move is what frees `index.md`.

Order: move the essay first with a placeholder index so the suite stays green; then
the pure parser, the renderer and the bar, each test-first without the blog-craft
renderer; then the copy; then a real build with screenshots; then guidance and the
matrix.

The spec is `docs/superpowers/specs/2026-11-12-landing-front-page-design.md`. No
change fragment: nothing under `packages/*/src`, `plugins/` or `scripts/install.sh`
changes, and no version surface is touched.
