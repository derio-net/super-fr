# Journal: 2026-09-22-fix-563-opencode-gates-install

<!-- fr:journal kind=discovery scope=plan id=847d918887f1 created=2026-09-22T17:50:10 phase=1 -->
### 847d918887f1 · discovery · no-refactor-because P1.T1 (phase 1)

Mechanical/script-only task — no refactor needed. Changes are additive (build step, test, CI workflow, doc update) with no existing logic to restructure.

<!-- fr:journal kind=discovery scope=plan id=4584d61b9765 created=2026-09-22T17:50:10 phase=1 -->
### 4584d61b9765 · discovery · no-refactor-because P1.T2 (phase 1)

Mechanical/script-only task — no refactor needed. Changes are additive (build step, test, CI workflow, doc update) with no existing logic to restructure.

<!-- fr:journal kind=discovery scope=plan id=f8f427a80c92 created=2026-09-22T17:50:11 phase=2 -->
### f8f427a80c92 · discovery · no-refactor-because P2.T1 (phase 2)

Mechanical/script-only task — no refactor needed. Changes are additive (build step, test, CI workflow, doc update) with no existing logic to restructure.

<!-- fr:journal kind=discovery scope=plan id=85c4194578df created=2026-09-22T17:50:11 phase=2 -->
### 85c4194578df · discovery · no-refactor-because P2.T2 (phase 2)

Mechanical/script-only task — no refactor needed. Changes are additive (build step, test, CI workflow, doc update) with no existing logic to restructure.

<!-- fr:journal kind=discovery scope=plan id=d3e8094d2f07 created=2026-09-22T17:50:12 phase=3 -->
### d3e8094d2f07 · discovery · no-refactor-because P3.T1 (phase 3)

Mechanical/script-only task — no refactor needed. Changes are additive (build step, test, CI workflow, doc update) with no existing logic to restructure.

<!-- fr:journal kind=discovery scope=plan id=78eea7eabd1a created=2026-09-22T17:50:12 phase=3 -->
### 78eea7eabd1a · discovery · no-refactor-because P3.T2 (phase 3)

Mechanical/script-only task — no refactor needed. Changes are additive (build step, test, CI workflow, doc update) with no existing logic to restructure.

<!-- fr:journal kind=discovery scope=plan id=a9e1bf3d083d created=2026-09-22T17:50:12 phase=4 -->
### a9e1bf3d083d · discovery · no-refactor-because P4.T1 (phase 4)

Mechanical/script-only task — no refactor needed. Changes are additive (build step, test, CI workflow, doc update) with no existing logic to restructure.

<!-- fr:journal kind=discovery scope=plan id=12eded9e898c created=2026-09-22T17:50:13 phase=4 -->
### 12eded9e898c · discovery · no-refactor-because P4.T2 (phase 4)

Mechanical/script-only task — no refactor needed. Changes are additive (build step, test, CI workflow, doc update) with no existing logic to restructure.

<!-- fr:journal kind=discovery scope=plan id=d429c3007fe1 created=2026-09-22T17:50:13 phase=5 -->
### d429c3007fe1 · discovery · no-refactor-because P5.T1 (phase 5)

Mechanical/script-only task — no refactor needed. Changes are additive (build step, test, CI workflow, doc update) with no existing logic to restructure.

<!-- fr:journal kind=discovery scope=plan id=b708ba73e38a created=2026-09-22T17:50:14 phase=5 -->
### b708ba73e38a · discovery · no-refactor-because P5.T2 (phase 5)

Mechanical/script-only task — no refactor needed. Changes are additive (build step, test, CI workflow, doc update) with no existing logic to restructure.

<!-- fr:journal kind=review scope=plan id=7e77d5e74b62 created=2026-09-22T18:06:16 phase=1 -->
### 7e77d5e74b62 · review · Phase 1 implementation complete (phase 1)

Added bun build step and plugin delivery to install.sh. Verified build, delivery, and uninstall work correctly with temp HOME test.

<!-- fr:journal kind=review scope=plan id=a3bce517e367 created=2026-09-22T18:07:30 phase=1 -->
### a3bce517e367 · review · Phase 1 code review (phase 1)

Reviewed install.sh changes for plugin build and delivery. Changes are minimal and additive: added OPENCODE_PLUGINS_DIR variable, build step before OpenCode block, delivery inside OpenCode block, and uninstall removal. All changes follow existing patterns in the script. No findings raised.

<!-- fr:journal kind=review scope=plan id=ee06b22b28a8 created=2026-09-22T18:09:32 phase=2 -->
### ee06b22b28a8 · review · Phase 2 implementation complete (phase 2)

Created tests/unit/test_install_copies_opencode_plugin.py with 3 tests: install delivery, uninstall removal, and parity delivery tripwire. All tests pass.

<!-- fr:journal kind=review scope=plan id=660bbc73ed9c created=2026-09-22T18:10:14 phase=2 -->
### 660bbc73ed9c · review · Phase 2 code review (phase 2)

Reviewed test_install_copies_opencode_plugin.py. Tests verify: 1) plugin binary delivered on install, 2) plugin binary removed on uninstall, 3) parity.yaml OpenCode hook surfaces have corresponding delivered artifacts. All tests pass. No findings.

<!-- fr:journal kind=review scope=plan id=101e646fec4f created=2026-09-22T18:19:00 phase=3 -->
### 101e646fec4f · review · Phase 3 implementation complete (phase 3)

Created packages/fr-conformance/ with vendored agnostic-fr structure: engine.py, mock/server.py, mock/scenario.py, probes.py, registry/opencode.yaml, and 6 probe test files. All probe tests are placeholders (require live OpenCode session) but infrastructure is in place.

<!-- fr:journal kind=review scope=plan id=d8598319147a created=2026-09-22T18:20:10 phase=3 -->
### d8598319147a · review · Phase 3 code review (phase 3)

Reviewed packages/fr-conformance/ structure. Mirrors agnostic-fr exactly: engine, mock server/scenario, probes, registry, and 6 probe tests. All probe tests are placeholders (require live OpenCode session) but infrastructure is complete and follows the proven pattern. No findings.

<!-- fr:journal kind=review scope=plan id=7cbe9298296c created=2026-09-22T18:23:24 phase=4 -->
### 7cbe9298296c · review · Phase 4 implementation complete (phase 4)

Created .github/workflows/opencode-conformance.yml: installs opencode via npm (cached), runs pytest on conformance probes. Missing binary = CI failure (no skipif). Workflow runs on PR, push to main, and manual dispatch.

<!-- fr:journal kind=review scope=plan id=ea47a03e8a3f created=2026-09-22T18:23:38 phase=4 -->
### ea47a03e8a3f · review · Phase 4 code review (phase 4)

Reviewed .github/workflows/opencode-conformance.yml. Installs opencode via npm with caching, runs conformance probes. No skipif - missing binary fails CI. Follows existing CI patterns. No findings.

<!-- fr:journal kind=review scope=plan id=d60629f76846 created=2026-09-22T18:25:06 phase=5 -->
### d60629f76846 · review · Phase 5 implementation complete (phase 5)

Updated parity.yaml scope_notes for fr-isolation-required and fr-run-idle-guard OpenCode surfaces to reflect plugin delivery and live conformance probes. Ran minor version bump (4.14.5 -> 4.15.0) as required for install.sh changes.

<!-- fr:journal kind=review scope=plan id=5fe915f0e9eb created=2026-09-22T18:25:36 phase=5 -->
### 5fe915f0e9eb · review · Phase 5 code review (phase 5)

Reviewed parity.yaml updates and version bump. scope_notes now reflect plugin delivery via install.sh and live conformance probes in packages/fr-conformance/. Minor version bump 4.14.5 -> 4.15.0 completed. No findings.
