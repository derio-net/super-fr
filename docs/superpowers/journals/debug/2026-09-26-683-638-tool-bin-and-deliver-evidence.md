# Journal: 2026-09-26-683-638-tool-bin-and-deliver-evidence

<!-- fr:journal kind=repro scope=debug id=e42699f33a0e created=2026-09-26T11:48:31 -->
### e42699f33a0e · repro · #683: test_install_bridge relinks the host's ~/.local/bin/fr into a pytest tmpdir

tests/integration/test_install_bridge.py sets UV_TOOL_DIR to tmp_path but not UV_TOOL_BIN_DIR, then runs `uv tool install --force … packages/fr`. uv resolves the executable dir as UV_TOOL_BIN_DIR > XDG_BIN_HOME > XDG_DATA_HOME/../bin > ~/.local/bin, so the fr entry point link lands in the real bin dir, and --force replaces the operator link. When pytest reaps tmp_path the link dangles. Observed on the host 2026-09-26 (issue body). install.sh --install-bridge itself only reads `uv tool dir`, never PATH, so the link is not even needed by the test.
