# Journal: 2026-09-26-683-638-tool-bin-and-deliver-evidence

<!-- fr:journal kind=repro scope=debug id=e42699f33a0e created=2026-09-26T11:48:31 -->
### e42699f33a0e · repro · #683: test_install_bridge relinks the host's ~/.local/bin/fr into a pytest tmpdir

tests/integration/test_install_bridge.py sets UV_TOOL_DIR to tmp_path but not UV_TOOL_BIN_DIR, then runs `uv tool install --force … packages/fr`. uv resolves the executable dir as UV_TOOL_BIN_DIR > XDG_BIN_HOME > XDG_DATA_HOME/../bin > ~/.local/bin, so the fr entry point link lands in the real bin dir, and --force replaces the operator link. When pytest reaps tmp_path the link dangles. Observed on the host 2026-09-26 (issue body). install.sh --install-bridge itself only reads `uv tool dir`, never PATH, so the link is not even needed by the test.

<!-- fr:journal kind=root-cause scope=debug id=da566ebe529b created=2026-09-26T11:51:53 -->
### da566ebe529b · root-cause · #683: UV_TOOL_BIN_DIR not isolated in test_install_bridge

The test isolates the tool ENV (UV_TOOL_DIR) but not the tool BIN dir, so `uv tool install --force` relinks the real ~/.local/bin/fr (or $XDG_BIN_HOME/fr) into tmp_path. Nothing asserted the host link survives a suite run, so it regressed silently from 4.22.2 (#635).
