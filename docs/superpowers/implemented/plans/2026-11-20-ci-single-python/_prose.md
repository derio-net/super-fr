# One Python, 3.14, for the whole base

Implements spec `2026-11-20-ci-single-python-design.md` (#1589) in one agentic phase: every ask is
a part of one change (the floor, the CI layout that tests it, the scaffold and pages that name it),
and none is reviewable alone. The host is loaded, so the executor runs single test files only;
CI on the draft PR is the suite evidence (`tests: ci`).
