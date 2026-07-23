# Journal: 2026-07-23-hermes-agent-compat

<!-- fr:journal kind=discovery scope=plan id=p1-standalone-scripts created=2026-07-23T21:01:17 -->
### p1-standalone-scripts · discovery · sync-hermes.py kept standalone (not sharing helpers with sync-opencode.py)

Tripwires import each sync-*.py by path; sharing a helper module would add a cross-script import for marginal DRY. Skills logic is close but not verbatim (fr category dir, .hermes paths, breadcrumb text). Refactor step P1.T1.S5 skipped intentionally.

<!-- fr:journal kind=discovery scope=plan id=p3-shared-decision-core created=2026-07-23T21:10:16 -->
### p3-shared-decision-core · discovery · Extracted lib/fr-isolation-decision.sh; Claude hook behavior byte-identical

The marker/allowlist/fr-enabled logic now lives in one sourced bash lib (fr_isolation_decide_edit, returns 0 allow / 1 block). Claude entrypoint sources it and keeps its exact deny JSON — 13/13 existing hook tests still green. Hermes entrypoint reuses the lib, adds write_file|patch tool gate + tool_input.path extraction + {"decision":"block"} shape. Callers MUST invoke the fn inside an 'if' so a deny return doesn't trip set -e.
