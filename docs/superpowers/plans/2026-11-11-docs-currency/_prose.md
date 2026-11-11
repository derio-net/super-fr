# Docs currency

Spec: `docs/superpowers/specs/2026-11-11-docs-currency-design.md`.

Five phases, one PR. Phase 1 builds the gate (`fr docs check`, `fr docs status`) and is the
skeleton. Phase 2 puts the gate in every flow: `deliver`, the skills, a shipped rule and this
repo's CI. Phase 3 makes the published site a build product: a build script, the pinned
renderer, Markdown sources for the two hand-authored pages, front matter on the guides.
Phase 4 writes a page for every skill and turns `must_cover` on. Phase 5 rewrites the README
as a front door with generated tables and moves its reference sections to pages.

Phases 2 and 3 depend only on 1; 4 and 5 depend on 3 (they add pages to the config it
creates). They run serially on the one branch.

Notes for every phase:

- Run `fr` as `uv run fr` in the workspace; the `fr` on PATH is the released one and has no
  `docs` group.
- After editing a canonical skill, rule or agent run BOTH `scripts/sync-opencode.py` and
  `scripts/sync-hermes.py`.
- Never edit a version surface; the change fragment is added in phase 1.
- The blog-craft renderer is cloned at `/home/user/derio-net/blog-craft` (the pinned commit).
  Render from `/` with `--isolated`, into a directory outside the repo.
