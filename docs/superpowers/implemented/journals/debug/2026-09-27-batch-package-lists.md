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

<!-- fr:journal kind=finding scope=debug id=installers-carry-every-runner created=2026-09-27T10:44:08 state=fixed -->
### installers-carry-every-runner · finding [fixed] · Both installers carry every fr.runners package, pinned to the entry points

Failing test first: `tests/integration/test_runner_package_lists.py` (commit before the fix) executes install.sh (install and `--install-bridge` hint) and the scaffold POST_CREATE against an argv-recording uv stub. It asserts `--with` for every package `runner_packages()` (tests/conftest.py) derives from `packages/*/pyproject.toml`. RED: install.sh had fr-vk only; POST_CREATE had none; `RUNNER_PACKAGES` did not exist. Fix: install.sh builds `FR_RUNNER_WITH` from the entry points at run time (no list to forget). `scaffold.RUNNER_PACKAGES` is a literal, because the scaffold ships in the fr wheel with no `packages/`; the test pins it. Both `.devcontainer/*/devcontainer.json` profiles are regenerated (`postCreateCommand == POST_CREATE`, already pinned by test_container_git_ownership). test_install_bridge installs the derived set. Live: the git-URL POST_CREATE install into a disposable UV_TOOL_DIR gives fr.runners [cncd, herdr, vk], and fr_vk.bridge imports.

<!-- fr:journal kind=review scope=debug id=c29916717ab7 created=2026-09-27T10:47:41 -->
### c29916717ab7 · review · Independent diff review: no defects at the reporting bar

A separate read-only reviewer checked grep-vs-tomllib agreement, bash 3.2 with set -u, POST_CREATE quoting under sh -c, and whether each test fails if a runner is dropped (it does; none is tautological). Two latent notes below the bar: (1) the grep could miss a reformatted entry-points table, but test_install_sh_installs_fr_with_every_runner_package compares against tomllib, so that drift fails CI rather than shipping. (2) An empty FR_RUNNER_WITH aborts under bash 3.2 + set -u. It cannot be empty while any runner package exists, and aborting loud is the right outcome if it ever is. No findings raised.
