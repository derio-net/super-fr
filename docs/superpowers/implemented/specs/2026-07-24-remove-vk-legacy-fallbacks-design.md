# Remove vk-spelling dual-read fallbacks — design

**Issue:** derio-net/super-fr#276 (follow-up to #272 / #275, mirrors the #270
label-cutover playbook). **Scope:** delete the 3.1-era dual-read fallbacks one
minor version later, now that the fleet sweep merged everywhere and the pod ran
`scripts/pod-fr-rename-oneshot.sh` (willikins#235).

## Goal

`fr init migrate` (#272) rewrites a repo from the `vk` spellings to `fr`; the
matching *reads* were dual: fr-first, `vk`-fallback + a loud
`[fr] WARNING: legacy …` line. This chore removes those read-side fallbacks so
`vk` spellings simply stop resolving — an unmigrated repo now fails loudly and
points at `fr init migrate` instead of limping along with a warning.

The migration **write** path (`fr init migrate`, `migrate.py`) is deliberately
**kept** — it is the escape hatch the new hard error points at.

## Removals

Each is a fr-first / vk-fallback read; after this change only the fr spelling
resolves.

1. **`vk-profiles.yaml` fallback** — `isolation/types.py::profiles_config`.
   Drop `vk-profiles.yaml` from the filename tuple and its `_warn_legacy`
   branch; read only `fr-profiles.yaml`.
2. **`.git/vk/isolation` legacy state dir** — `isolation/types.py`. Remove
   `_legacy_state_dir`, the legacy unlink in `delete_state`, the legacy
   fallback in `load_state`, and the legacy glob in `list_states`. State is
   read/written/deleted under `.git/fr/isolation` only.
3. **`/.config/vk/secrets/` mount-follow warning → hard error** —
   `isolation/local.py::_ensure_mounted_env_file`. A committed
   `devcontainer.json` that still mounts `~/.config/vk/secrets/**` now raises
   `IsolationError` naming the file and `fr init migrate`, instead of warning
   and creating the vk file. The fr path continues to be ensured normally.
4. **`VK_BRIDGE_*` env fallback** — `fr_vk/config.py::bridge_env`. Read only
   `FR_BRIDGE_<name>`; the `VK_BRIDGE_<name>` fallback and its warning are
   gone. Callers (`REPOS`, `CHECKOUT_DIR`, `LOCK_PATH`,
   `RECOVER_ORPHAN_CARDS`) are unchanged; the "legacy: VK_BRIDGE_*" docstring
   notes in `bridge_cli.py` are dropped.
5. **Dead `_warn_legacy`** — once 1–4 land, `isolation/types.py::_warn_legacy`
   (and its `import sys`) and the `_warn_legacy` import in `local.py` are dead;
   remove them.

## Kept forever (VibeKanban-the-product, not brand residue)

`VK_DERIO_OPS_PROJECT_ID`, `VK_ORG_ID`, `VK_API_BASE`, the
`willikins_vk_bridge_*` metric wire names, the `VK_DERIO_OPS_PROJECT` →
`_PROJECT_ID` dual-read (a VibeKanban-domain read, not a rebrand fallback), and
`fr init migrate` itself. None are touched.

## Operator-owned decisions

- **Pre-flight gate (merge precondition, operator-owned).** The removal PR must
  not merge until the operator has confirmed **zero `[fr] WARNING: legacy`
  lines in a week of bridge logs + local usage**, the fleet sweep merged
  everywhere, and the pod ran `scripts/pod-fr-rename-oneshot.sh` (willikins#235).
  This cannot be verified from the build environment, so the PR ships as a
  **draft** with the gate foregrounded; the operator marks it ready / merges
  once satisfied.
- **Version bump: minor (3.15.0 → 3.16.0).** Removing a user-observable
  fallback is a user-visible behavior change; the issue frames it as "one minor
  later". Not a major — no CLI/plan-schema break for a migrated repo.
- **Host / pod cleanup (post-merge operational, not a code phase).** Deleting
  `~/.config/vk/secrets` on each host (the copy-no-clobber source) is a manual,
  per-machine operator action with no code change. It carries no plan phase —
  it lives in the Test Plan as a post-merge, operator-driven step and is
  foregrounded in the PR body, not automated here.

## Non-goals

- No change to `fr init migrate` behavior, dispatch/tick logic, plan formats,
  labels, or the kept VibeKanban env/metric names.
- No automatic host secrets move or deletion (`migrate.py` still only *prints*
  the copy-no-clobber block).

## Test Plan

Unit tests are rewritten from "fallback warns" to "fallback gone":

1. `profiles_config` reads `fr-profiles.yaml`; a lone `vk-profiles.yaml` is
   **ignored** (returns `{}`), no warning.
2. `load_state` / `list_states` return None / `[]` when only the legacy
   `.git/vk/isolation` copy exists; fr copies still resolve.
3. `up()` against a repo whose `devcontainer.json` still mounts
   `~/.config/vk/secrets/**` raises `IsolationError` matching `fr init migrate`;
   no vk file is created.
4. `bridge_env("REPOS")` returns None when only `VK_BRIDGE_REPOS` is set; reads
   `FR_BRIDGE_REPOS` when present; no warning on any path.
5. No `_warn_legacy` symbol remains (`grep` tripwire in the removal itself; the
   full suite exercises the reads above).

**Post-merge (operator-driven):** confirm the pre-flight gate is satisfied
before merge; after merge, `rm -rf ~/.config/vk/secrets` on each host that ran
the fleet sweep.

## Implementation Plans

| Plan | Repo | File | Depends on |
| ---- | ---- | ---- | ---------- |
| 2026-07-24-remove-vk-legacy-fallbacks | `derio-net/super-fr` | `2026-07-24-remove-vk-legacy-fallbacks` | — |
