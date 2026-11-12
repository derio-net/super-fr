# Remove the remaining vk compatibility code

Spec: `docs/superpowers/specs/2026-11-12-remove-vk-compat-design.md`.

The `vk` command became `fr`. This plan removes what still exists only for
installs, repos and plan files from before the rename. The VibeKanban runner
(`packages/fr-vk`, `fr apply --to vk`, `VK_MCP_BINARY`, `VK_BRIDGE_*`,
`VK_DERIO_OPS_PROJECT*`) is a live adapter and is not touched by either phase.

## Phase 1: removals and renames

Plain deletions and mechanical renames, each pinned by a test in one new file,
`tests/unit/test_vk_compat_removed.py`: `fr init migrate` and its module, the
legacy-secrets hard error, the `vk-iso/work` default (`--branch` becomes
required and every remedy message names it), `VK_REPO_ROOT` and
`VK_INSTALL_SKIP_PREFLIGHT` (hard-renamed to `FR_*`), the installer's `vk-*`
purges, `superpowers-for-vk` wrapper recognition, and the `vk` probe in
`bump-version.py`. The merged row `vk-legacy-fallbacks-removed` is amended,
since it asserted the error this phase deletes.

## Phase 2: the `vk_version` plan key

`PlanMeta` rejects unknown keys, so dropping the field makes every plan that
carries it unparseable until the key is gone from the file. A plan repair
removes the one line, verified by re-parsing before any write. It is the only
migration that reaches `docs/superpowers/implemented/plans/`, through a new
`Repair.extra_locators` field, by the operator's decision; the phase reads the
runner end to end first, because four separate walks enumerate artifacts and
each needs a stated behaviour for archive paths. This repo's 33 archived
carriers are migrated by running the framework, not by hand.

Phase 2 is `hard`: it changes the migration runner and the CLI-entry gate's
staleness test, which every command passes through.
