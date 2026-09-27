# Journal: 2026-09-27-batch-package-lists

<!-- fr:journal kind=repro scope=debug id=f4f694bf49d5 created=2026-09-27T10:25:49 -->
### f4f694bf49d5 · repro · Installed fr registers only the vk runner; the workspace registers all three

Host uv-tool fr: `entry_points(group="fr.runners")` -> `["vk"]`. `uv run` in the workspace -> `["cncd", "herdr", "vk"]`. So `fr triage batch dispatch --to herdr` works under `uv run fr` (what tests and every batch dispatch use) and fails on the installed fr (#650). In the devcontainer, POST_CREATE installs fr from git with no `--with` at all, so the container fr has no runners and `install.sh --install-bridge` refuses at its `import fr_vk.bridge` check (#645).

<!-- fr:journal kind=root-cause scope=debug id=e32242f6168d created=2026-09-27T10:25:50 -->
### e32242f6168d · root-cause · Runner packages are hand-kept lists in each installer, and none derives from the fr.runners entry points

Three `fr.runners` packages exist (`packages/{fr-vk,fr-cncd,fr-herdr}/pyproject.toml` declare the entry point). Each installer spells out its own list by hand: `scripts/install.sh:670` has `--with packages/fr-vk` only (the `--install-bridge` hint at :112 repeats it); `fr/isolation/scaffold.py` POST_CREATE has none, and it is copied into both committed `.devcontainer/{dev,admin}/devcontainer.json`. Adding fr-cncd and fr-herdr updated neither list, and nothing tested either list against the workspace, because tests run `uv run fr`, which sees every workspace member. One cause, two symptoms: #650 (host) and #645 (container).
