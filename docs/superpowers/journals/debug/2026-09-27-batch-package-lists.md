# Journal: 2026-09-27-batch-package-lists

<!-- fr:journal kind=repro scope=debug id=f4f694bf49d5 created=2026-09-27T10:25:49 -->
### f4f694bf49d5 · repro · Installed fr registers only the vk runner; the workspace registers all three

Host uv-tool fr: `entry_points(group="fr.runners")` -> `["vk"]`. `uv run` in the workspace -> `["cncd", "herdr", "vk"]`. So `fr triage batch dispatch --to herdr` works under `uv run fr` (what tests and every batch dispatch use) and fails on the installed fr (#650). In the devcontainer, POST_CREATE installs fr from git with no `--with` at all, so the container fr has no runners and `install.sh --install-bridge` refuses at its `import fr_vk.bridge` check (#645).
