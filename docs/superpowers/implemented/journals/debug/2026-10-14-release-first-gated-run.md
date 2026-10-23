<!-- fr:journal-schema=3 -->
# Journal: 2026-10-14-release-first-gated-run

<!-- fr:journal kind=repro scope=debug id=repro-rc-suite-red created=2026-10-14T11:54:28+00:00 -->
### repro-rc-suite-red · repro · Release run 38557522803 refused 5.27.0-rc.1: staged suite red on 3 version-shape tests

First release after #1195 (exit-gates). Gating chose an RC (#1195 waits on a post-merge gate), bumped 5.26.0 -> 5.27.0-rc.1 in 12 files, ran the staged suite: 3 failed, 12738 passed. Nothing pushed, tagged or published. Failures: tests/unit/test_version.py::test_version_is_semver (int-splits __version__ '5.27.0rc1'); tests/unit/test_version_surfaces.py::test_every_surface_value_equals_the_root_version (set {'5.27.0-rc.1','5.27.0rc1'} != {'5.27.0rc1'}); tests/unit/test_bridge_cli.py::test_tick_first_log_line_has_version_and_timestamp (banner regex v\d+.\d+.\d+ rejects v5.27.0rc1). Repro: bump-version.py 5.27.0-rc.1 in a worktree (uncommitted), run the three tests.

<!-- fr:journal kind=root-cause scope=debug id=rc-self-referential-version-tests created=2026-10-14T11:55:05+00:00 -->
### rc-self-referential-version-tests · root-cause · Three tests read the repo's own version and assume a final X.Y.Z; only the release runner ever stages an RC

Phase 7 of exit-gates (#1195) taught scripts/versions.Version both RC spellings and routed every release script through it, but three tests assert on the LIVE version: test_version_is_semver int-splits fr.__version__ (PEP 440 '5.27.0rc1'), the bridge banner regex allows only v\d+.\d+.\d+, and test_every_surface_value_equals_the_root_version demands one string although an RC is two spellings by design (R25: X.Y.ZrcN on pyproject/uv.lock, X.Y.Z-rc.N elsewhere). A PR's tree is always final, so PR CI cannot see this; the staged suite on the release runner is the first tree at an RC, and it refused correctly (gh#854 gate). No other test failed (3 of 12741).

<!-- fr:journal kind=finding scope=debug id=fix-rc-version-tests created=2026-10-14T12:02:01+00:00 state=fixed -->
### fix-rc-version-tests · finding [fixed] · Version-shape tests accept a staged RC (both spellings)

test_version_is_semver: fullmatch X.Y.Z(rcN)?; bridge banner regex allows rcN; test_every_surface_value_equals_the_root_version: every surface parses to the root Version AND carries vs.spelling(file, root). Red at a locally staged 5.27.0-rc.1 (bump-version, uncommitted): 3 failed; green after: 27 passed at the RC and 27 passed at 5.26.0 after restoring the version files. Tests only, no fragment.

<!-- fr:journal kind=review scope=debug id=review-pr-1209 created=2026-10-14T12:02:40+00:00 -->
### review-pr-1209 · review · PR #1209 reviewed by the debugging session: no findings

Self-review of a 3-test, test-only diff; no independent reviewer dispatched (proportionate to size). Checked: the patterns admit exactly X.Y.Z and X.Y.ZrcN (N>=1, no leading zero), matching scripts/versions._VERSION_RE's PEP 440 branch; the surfaces test is stricter than before (per-file spelling via version_surfaces.spelling) and passes at both a final and an RC. No findings.
