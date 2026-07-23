# Journal: 2026-07-23-hermes-agent-compat

<!-- fr:journal kind=discovery scope=plan id=p1-standalone-scripts created=2026-07-23T21:01:17 -->
### p1-standalone-scripts · discovery · sync-hermes.py kept standalone (not sharing helpers with sync-opencode.py)

Tripwires import each sync-*.py by path; sharing a helper module would add a cross-script import for marginal DRY. Skills logic is close but not verbatim (fr category dir, .hermes paths, breadcrumb text). Refactor step P1.T1.S5 skipped intentionally.
