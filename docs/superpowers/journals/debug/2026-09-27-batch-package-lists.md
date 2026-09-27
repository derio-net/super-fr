# Journal: 2026-09-27-batch-package-lists

<!-- fr:journal kind=repro scope=debug id=f4f694bf49d5 created=2026-09-27T10:25:49 -->
### f4f694bf49d5 · repro · Installed fr registers only the vk runner; the workspace registers all three

Host uv-tool fr: `entry_points(group="fr.runners")` -> `["vk"]`. `uv run` in the workspace -> `["cncd", "herdr", "vk"]`. So `fr triage batch dispatch --to herdr` works under `uv run fr` (what tests and every batch dispatch use) and fails on the installed fr (#650). In the devcontainer, POST_CREATE installs fr from git with no `--with` at all, so the container fr has no runners and `install.sh --install-bridge` refuses at its `import fr_vk.bridge` check (#645).

<!-- fr:journal kind=root-cause scope=debug id=e32242f6168d created=2026-09-27T10:25:50 -->
### e32242f6168d · root-cause · Runner packages are hand-kept lists in each installer, and none derives from the fr.runners entry points

Three `fr.runners` packages exist (`packages/{fr-vk,fr-cncd,fr-herdr}/pyproject.toml` declare the entry point). Each installer spells out its own list by hand: `scripts/install.sh:670` has `--with packages/fr-vk` only (the `--install-bridge` hint at :112 repeats it); `fr/isolation/scaffold.py` POST_CREATE has none, and it is copied into both committed `.devcontainer/{dev,admin}/devcontainer.json`. Adding fr-cncd and fr-herdr updated neither list, and nothing tested either list against the workspace, because tests run `uv run fr`, which sees every workspace member. One cause, two symptoms: #650 (host) and #645 (container).

<!-- fr:journal kind=ruled-out scope=debug id=772b62b3e81a created=2026-09-27T10:25:51 -->
### 772b62b3e81a · ruled-out · test_install_bridge.py is no longer non-hermetic

#645 says `tests/integration/test_install_bridge.py:18` tests the host global uv-tool env. Since #683/#688 (7f50d74c) it installs a disposable fr into `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR` under tmp_path, so it no longer reads the host env. That part of #645 is already fixed. What is left is its own hand-kept `--with packages/fr-vk`. It becomes the derived list too, so the test installs what install.sh installs.
