# Retire VibeKanban support

Issue: derio-net/super-fr#1459 (batch `retire-vk`). Refs derio-net/frank#950.

## Background

super-fr shipped a VibeKanban (VK) runner: the `fr-vk` package
(`packages/fr-vk/src/fr_vk/`: `runner.py`'s `VkRunner`, `bridge.py`/`bridge_cli.py`, the
`python -m fr_vk.bridge` cron daemon, `dispatch.py`, `slots.py`, `workspaces.py`,
`dedup.py`, `pr_observe.py`, `pr_state.py`, `_cardref.py`, `_mcp_client.py`, `config.py`),
registered as the `vk` entry point of the `fr.runners` group
(`packages/fr-vk/pyproject.toml:9`). Its only deployment was retired on 2026-11-13
(frank#950), so nothing runs it. `packages/fr/src/fr/isolation/local.py:2161` already
says `fr_vk` "is being dropped".

The runner contract (`fr_dispatch`) stays: `fr-cncd`, `fr-herdr` and `fr-claude-cloud`
implement it.

What reaches VK today, outside the package:

- the workspace: `pyproject.toml` (members, dependencies, `fr-vk` source, coverage
  `source`), `uv.lock`, and the CI mypy line (`.github/workflows/ci.yml:35`);
- scaffolding: `RUNNER_PACKAGES` (`packages/fr/src/fr/isolation/scaffold.py:434`) feeds
  `POST_CREATE`, so every devcontainer fr has scaffolded runs `uv tool install --with
  …#subdirectory=packages/fr-vk`, this repo's `.devcontainer/dev` and
  `.devcontainer/admin` included. Once the directory is gone from `main`, creating such a
  container fails inside `postCreateCommand`;
- `scripts/install.sh`: `VK_MCP_BINARY` with its missing-binary warning (≈ line 501), the
  `vibe_kanban` MCP server entry it writes into `~/.claude/.mcp.json` (≈ line 809), the
  `--install-bridge` flag that writes a `vk-bridge` wrapper exec'ing
  `python -m fr_vk.bridge` (≈ line 186), and the uninstall path that removes the MCP entry;
- the `super-fr-dispatch` plugin: `plugin.json`'s "VibeKanban adapter" description and the
  `vibekanban` keyword, the `fr-runner` skill (VK-only: tick metrics, orphan cards,
  `VK_*`/`FR_BRIDGE_*` env), and the `fr-dispatch` skill's "send to VK" trigger and
  `--to vk` examples;
- docstrings and comments in kept code that name `fr_vk` as a caller or the "first
  implementation": `fr_dispatch` (`__init__.py`, `protocols.py`, `registry.py`,
  `metrics.py`, `prompt.py`), `fr_cncd` (`__init__.py`, `runner.py`), `fr/_hosts.py`,
  `fr/hostclient.py`, `fr/ghclient.py`, `fr/real_glabclient.py`, `fr/artifacts/commit.py`,
  `fr/isolation/{local,hostworktree}.py`, `fr/commands/{apply_cmd,undispatch_cmd}.py`;
- tests: about 60 files under `tests/unit` and `tests/integration` that import `fr_vk`, some
  wholly VK (`test_bridge_*`, `test_vk_*`, `test_cardref`, `test_mcp_client*`,
  `test_pr_observe`, …), some mixed (`test_import_direction.py`, `test_hostclient.py`,
  `test__hosts.py`, `test_tripwire_forge_writes.py`, `fakes.py`, `tests/conftest.py`'s
  `_fresh_vk_repo_cache`), plus their `.test_durations` entries;
- docs: `docs/explainers/fr-dispatch.md` (covers `packages/fr-vk/src/**`),
  `docs/reference/{components,dispatch-lifecycle,install}.md`, `README.md`, `AGENTS.md`;
- acceptance rows that cite VK tests or describe VK behaviour (in at least
  `2026-06-08-bridge-dedicated-checkout-self-healing-sync`,
  `2026-06-09-bridge-pr-state-autoclose-wiring`, `2026-06-09-terminal-done-issue-close`,
  `2026-07-09-multi-backend-git-host-adapters`, `2026-07-24-remove-vk-legacy-fallbacks`,
  `2026-07-24-vk-mcp-timeout-permit-leak`, `2026-08-14-workflow-shapes-and-workitem-dispatch`,
  `2026-08-30-artifact-migration-framework`, `2026-10-06-forge-remainder`,
  `2026-11-12-remove-vk-compat` and `legacy`).

Some VK-named code stays on purpose. The `drop-vk-version` plan repair
(`fr/artifacts/plan_vk_version.py`) carries archived plans that still hold the retired
key; a removed migration never runs again. `fr/plan_config.py` strips a dead `dispatch:`
block, and the `vk-` notes in `fr/labels.py` and `fr/diff.py` record a vocabulary already
removed. Captured forge responses under `tests/fixtures/github_rest/` and
`tests/scenarios/fixtures/` quote "VibeKanban" only inside recorded PR bodies and check
names. They are evidence of an API's shape and stay byte-identical.

## Requirements

R1. The `fr-vk` package no longer exists: `packages/fr-vk/` is deleted, and the workspace
(`pyproject.toml` members, dependencies, sources, coverage `source`), `uv.lock`, the CI
mypy command, the version surfaces and `AGENTS.md`'s dev commands no longer name it. No
`vk` runner is registered, and `fr apply --to vk` refuses it as an unknown runner through
the registry's existing unknown-runner path.

R2. Tests and fixtures that exercise only `fr_vk` are deleted. Mixed tests keep their
non-VK cases, and `.test_durations` names no deleted test. The behaviour tests of
`fr-dispatch`, `fr-cncd`, `fr-herdr` and `fr-claude-cloud` pass without change to what
they assert. Captured forge fixtures stay byte-identical.

R3. `RUNNER_PACKAGES` and the scaffolded `POST_CREATE` name no `fr-vk`, and this repo's
`.devcontainer/dev` and `.devcontainer/admin` install no `fr-vk`.

R4. `fr isolation up` and `fr isolation rebuild` in devcontainer mode refuse, before they
start a container, a profile whose `devcontainer.json` installs `packages/fr-vk`. The
refusal exits 2, names the file and the `--with '…#subdirectory=packages/fr-vk'` segment to
delete, and says VK support was removed.

R5. `scripts/install.sh` installs no VK pieces: no `vibe_kanban` MCP entry, no VK MCP binary
check or warning, and no bridge wrapper. On install it removes a `vibe_kanban` entry from
`~/.claude/.mcp.json` and a `vk-bridge` wrapper that execs `fr_vk.bridge` (at the default
path or at `VK_BRIDGE_WRAPPER_PATH`) when present, and prints one line for each removal.
`--install-bridge` exits non-zero with a message that VK support was removed.
`--uninstall` keeps removing the MCP entry.

R6. The `fr-runner` skill is deleted, along with its OpenCode and Hermes mirrors and its
install wiring. Its few runner-agnostic facts move into the `fr-dispatch` skill: `fr
undispatch`, the up-front `unit_mismatch` refusal, and dispatch reachability. The
`fr-dispatch` skill and `plugin.json` name no VibeKanban, and their examples use a runner
that remains.

R7. Kept code names `fr_vk` or VK nowhere as a live caller, implementation or example. This
covers docstrings, comments and help text in the files the Background lists. Behaviour does
not change: URL-only backend resolution (`fr/_hosts.py`, `fr/hostclient.py`) stays, because
the triage batch verbs still call it.

R8. The published docs (`docs/explainers/`, `docs/*.md`, `docs/reference/`) and
`README.md` describe no VK runner, and every page's `covers:` names only existing paths.
Historical records stay untouched: `docs/superpowers/implemented/`, `docs/audits/`,
`docs/triage/`, `CHANGELOG.md` and earlier specs and brainstorms.

R9. Acceptance rows whose capability is VK-only are retired by amendment. Rows that also
cover a surviving capability drop their VK level refs by amendment. No row cites a deleted
test.

R10. A tripwire test fails when `fr_vk`, `fr-vk` or `vibe_kanban` appears in shipped sources
(`packages/*/src`, `plugins/`, `scripts/`, `.devcontainer/`). It allows only the R4
detection and the R5 cleanup, by exact file, plus the R7 exceptions the Background names
(`drop-vk-version` and the `vk-` vocabulary notes).

R11. The change ships a `major` change fragment whose summary says VK support was removed,
and names the `devcontainer.json` fix for profiles scaffolded earlier.

## Design

**Deletion order.** The package, its tests and the workspace entries go first, together,
so the suite stays importable at every commit: a test that imports `fr_vk` cannot outlive
the package. Mixed test files lose only their VK cases. `tests/conftest.py`'s
`_fresh_vk_repo_cache` fixture goes with the cache it resets. `uv lock` regenerates the
lock, and `scripts/bump-version.py --check` must stay green with one member fewer. This is
a version-surface list change, not a version edit.

**Runner lists.** `RUNNER_PACKAGES` drops `fr-vk`.
`tests/integration/test_runner_package_lists.py` keeps pinning it to the entry points, so
the change is checked by an existing guard. `install.sh` derives its `--with` set from the
workspace, so it follows on its own.

**Stale-profile refusal (R4).** The check reads the profile's `devcontainer.json` (the
worktree copy `local.py` already resolves at line 1223, and the path `rebuild` uses) and
searches the text for `subdirectory=packages/fr-vk`. It runs after the existing
config-exists check and before `devcontainer up`. It is a plain text search, so a
`postCreateCommand` the operator customised is judged by the same rule. Host-worktree and
external modes never read a profile, so they are unaffected.

**Installer (R5).** The VK MCP block and the `--install-bridge` writer are deleted. A small
cleanup runs during install. It removes the `vibe_kanban` key with `jq` (only that key; an
`.mcp.json` without it is left alone), and it deletes a wrapper only when its content
execs `fr_vk.bridge`. A file at that path that fr did not write is never deleted. Uninstall
keeps its existing removal.

**Skills.** `fr-runner` is deleted from `plugins/super-fr-dispatch/skills/`, then both
mirror generators run (`scripts/sync-opencode.py`, `scripts/sync-hermes.py`), followed by
`scripts/sync-readme.py`. The `must_cover` rule (`.fr/docs.yaml`) then needs no page for it.

**Acceptance (R9).** Row changes go through `fr acceptance amend` (`retire`, `drop-level`),
never through hand edits. A mixed row keeps its surviving refs.

**Tripwire (R10).** It extends the existing `tests/unit/test_vk_compat_removed.py` rather
than adding a sibling, because that file already holds the VK-residue checks.

## Verification

strategy: candidate
gate: developer
- vk-runner-removed: none — the R10 tripwire and the registry and import tests run in CI
- stale-vk-profile-refused: none — unit tests drive `fr isolation up`/`rebuild` over a fixture profile in CI
- installer-removes-vk-residue: none — `tests/integration/test_install_sh.py` drives install over a fixture home in CI
- dispatch-docs-name-no-vk: none — the R10 tripwire, the mirror tripwires and `fr docs check` run in CI
</content>
