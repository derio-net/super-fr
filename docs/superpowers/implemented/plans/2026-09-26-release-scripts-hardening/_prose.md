# Release scripts hardening — plan

One agentic phase implementing spec `2026-09-26-release-scripts-hardening-design.md`: anchor the
TOML version rewrite to `[project]` (and make it all-or-nothing), widen the fragment rule to every
plugin's skills, and run the CI fragment check under uv-managed Python. TDD: red tests for all three,
then the fixes, then a refactor/quality/acceptance pass.
