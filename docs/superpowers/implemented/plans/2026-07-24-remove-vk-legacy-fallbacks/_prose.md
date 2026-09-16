# Remove vk-spelling dual-read fallbacks — plan

Retires the 3.1-era dual-read fallbacks one minor later (#276), per the design
in `docs/superpowers/specs/2026-07-24-remove-vk-legacy-fallbacks-design.md`.
After this, only the `fr` spellings resolve; an unmigrated repo fails loudly and
points at `fr init migrate` (the write path, kept). The VibeKanban-product names
(`VK_DERIO_OPS_PROJECT_ID`, `willikins_vk_bridge_*`, …) are untouched.

## Approach

Two independent removal phases (isolation reads; bridge env) each rewrite their
"fallback warns" unit tests to "fallback gone" (red), then delete the fallback
(green) — TDD, no behavior added. A small release phase flips the acceptance row
to `ci` and applies the minor version bump. The phases are independent
(`depends_on: []`) except the release phase, which fans in on both.

The one surface that changes shape rather than disappearing is the legacy
secrets mount: `local._ensure_mounted_env_file` warned and created the vk file;
it now raises `IsolationError` pointing at `fr init migrate`, matching the spec.

## Phases

1. **Isolation reads retired** — `isolation/types.py` (`profiles_config`
   vk-profiles.yaml fallback; `.git/vk/isolation` state reads in `load_state` /
   `list_states` / `delete_state`; `_legacy_state_dir`) and
   `isolation/local.py` (`_ensure_mounted_env_file` → hard error). Closes with
   removing the now-dead `_warn_legacy` (+ its `import sys`).
2. **Bridge env fallback retired** — `fr_vk/config.py::bridge_env` reads only
   `FR_BRIDGE_*`; the `VK_BRIDGE_*` fallback + warning go, along with the stale
   docstring notes in `bridge_cli.py`.
3. **Release** — flip acceptance row `vk-legacy-fallbacks-removed` to `ci`;
   minor version bump 3.15.0 → 3.16.0 via `scripts/bump-version.py`.

## Out of scope / operator-owned

- **Pre-flight gate** (merge precondition): zero `[fr] WARNING: legacy` lines in
  a week of bridge logs + local usage, fleet sweep merged, pod ran the oneshot.
  The PR ships as a draft with this foregrounded.
- **Host cleanup** (post-merge, per machine): `rm -rf ~/.config/vk/secrets` —
  operational, in the spec's Test Plan, not a code phase.
- `fr init migrate` and the kept VibeKanban-product env / metric names.
