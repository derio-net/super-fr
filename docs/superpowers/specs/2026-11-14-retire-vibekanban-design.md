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
implement it. No kept code depends on `fr_vk` at runtime: every reference is a
docstring or comment, and URL-only backend resolution (`client_for_url`) has live non-VK
callers (`fr/commands/gate_cmd.py:28`, `fr/commands/release_cmd.py:25`, `fr/cloud.py:130`).

What reaches VK today, outside the package:

- **The workspace and its tooling.** `pyproject.toml:7,9,18,58` (description,
  dependencies, sources, coverage `source`), `uv.lock`, the CI mypy line
  (`.github/workflows/ci.yml:35`), the dev commands in `AGENTS.md` and `HERMES.md:67`, and
  `HERMES.md:97`'s package list. `scripts/version_surfaces.py:63` finds member
  pyprojects by glob, so it follows on its own.
- **The candidate install contract.** `.fr/candidate-install:36` names `fr-vk` in its
  `git+` branch's package loop. `tests/integration/test_scenarios.py:135,175` pins that
  loop to `runner_packages()`.
- **Scaffolding.** `RUNNER_PACKAGES` (`packages/fr/src/fr/isolation/scaffold.py:434`)
  feeds `POST_CREATE`, so every devcontainer fr has scaffolded runs `uv tool install --with
  …#subdirectory=packages/fr-vk`, including this repo's `.devcontainer/dev` and
  `.devcontainer/admin` (`devcontainer.json:8` in each). Once the directory is gone from
  `main`, creating such a container fails inside `postCreateCommand`.
- **`scripts/install.sh`.** It has the `VK_MCP_BINARY` (:116) and missing-binary warning
  (:501-505), the `vibe_kanban` MCP server entry it writes into `~/.claude/.mcp.json`
  (:809-825), the `--install-bridge` flag that writes a `vk-bridge` wrapper exec'ing
  `python -m fr_vk.bridge` (:186-219), the uninstall path that removes the MCP entry
  (:235-237), and a closing verification hint naming `vibe_kanban` (:1115).
- **The `super-fr-dispatch` plugin.** `plugin.json:3,14` has the "VibeKanban adapter"
  description and the `vibekanban` keyword. The `fr-runner` skill
  (`plugins/super-fr-dispatch/skills/fr-runner/SKILL.md`, VK-only: tick metrics, orphan
  cards, `VK_*`/`FR_BRIDGE_*` env) has no OpenCode or Hermes mirror: those trees hold
  only `super-fr` plugin skills, and `install.sh` rsyncs the marketplace wholesale. It is
  named in `fr/commands/skills_cmd.py:78` (the `fr skills` overview),
  `scripts/readme-skill-summaries.yaml:18` (the source of README's generated skills
  table), and `docs/explainers/fr-dispatch.md:2-17` (title, tldr, `covers:`). The
  `fr-dispatch` skill has a "send to VK" trigger (:5) and `--to vk` examples (:18-19), and
  it already states `fr undispatch` and dispatch reachability (:20-23, :119).
- **Docstrings, comments and help text in kept code** that name `fr_vk` or VK as a live
  caller, implementation or example. In `fr_dispatch`: `__init__.py`, `protocols.py`,
  `registry.py`, `metrics.py`, `prompt.py`. In `fr_cncd`: `__init__.py`, `runner.py`. In
  `fr`: `_hosts.py`, `hostclient.py`, `ghclient.py`, `real_ghrestclient.py:916`,
  `real_glabclient.py`, `render.py:212,385`, `parser.py:47,130`, `workflow/shapes.py:3`,
  `artifacts/commit.py:426`, `isolation/{local,hostworktree}.py` (local.py:1606, :2161),
  and `commands/{apply_cmd,undispatch_cmd}.py`.
- **Tests.** 44 files under `tests/` name `fr_vk` or `fr-vk`, and some VK tests name
  neither. A test is classified by what it exercises, never by its filename or its
  imports. `tests/unit/test_bridge_prompt.py`, for example, tests the kept
  `fr_dispatch.prompt`. Wholly-VK tests include the `fr_vk` bridge, dispatch, slots,
  workspaces, dedup, PR-observe/state, card-ref, MCP-client and VK tick tests. Mixed files
  keep their non-VK cases: `test_import_direction.py`, `test_hostclient.py`,
  `test__hosts.py`, `test_tripwire_forge_writes.py`, `test_tripwire_forge_adapter.py`,
  `test_forge_error_kind.py`, `test_version_surfaces.py`, `test_tick_workitem.py`,
  `test_done_reconcile.py`, `tests/unit/fakes.py`, `tests/integration/test_cutover.py`.
  Install tests assert VK pieces without importing `fr_vk`:
  `tests/integration/test_install_sh.py:234-262,385-404` (the `vibe_kanban` entry),
  `test_runner_package_lists.py:58,82,94-107` (a `vibe-kanban-mcp` stub, `fr-vk` among
  the runners, the `--install-bridge` hint), `test_install_atomic.py` and
  `test_install_worktree_settings_hooks.py` (VK MCP stubs). `tests/conftest.py` has two
  VK autouse fixtures, `_default_vk_project_id` (:62-71) and `_fresh_vk_repo_cache` (:497).
  `.test_durations` holds their entries.
- **Docs.** `docs/explainers/fr-dispatch.md`, `docs/reference/{components,dispatch-lifecycle,install}.md`,
  `README.md` and `AGENTS.md` (the repo-shape bullet for `fr-vk`, and the "Bridge audit
  rule" requiring a read of `fr_vk.*`).
- **Acceptance rows** that cite VK tests or describe VK behaviour, in at least these
  fragments: `2026-06-08-bridge-dedicated-checkout-self-healing-sync`,
  `2026-06-09-bridge-pr-state-autoclose-wiring`, `2026-06-09-terminal-done-issue-close`,
  `2026-07-09-multi-backend-git-host-adapters`, `2026-07-24-remove-vk-legacy-fallbacks`,
  `2026-07-24-vk-mcp-timeout-permit-leak`, `2026-08-14-workflow-shapes-and-workitem-dispatch`,
  `2026-08-30-artifact-migration-framework`, `2026-09-19-gitlab-contents-ref-and-self-hosted-hosts`
  (cites `test_pr_observe.py`), `2026-10-06-forge-remainder`, `2026-11-12-remove-vk-compat`
  and `legacy`.

Some VK-named code and text stays on purpose:

- The `drop-vk-version` plan repair (`fr/artifacts/plan_vk_version.py`) carries archived
  plans that still hold the retired key. A removed migration never runs again.
- `fr/plan_config.py` strips a dead `dispatch:` block.
- The `vk-` notes in `fr/labels.py` and `fr/diff.py` record a vocabulary that is already
  removed.
- Captured data stays byte-identical: forge responses under `tests/fixtures/github_rest/`
  and `tests/scenarios/fixtures/`, and the transcript
  `tests/fixtures/transcripts/claude-code-background.jsonl`. These quote "VibeKanban" or
  `fr_vk` only inside recorded text, as evidence of a shape.

## Requirements

R1. The `fr-vk` package no longer exists. `packages/fr-vk/` is deleted, and none of these
name it any more: the workspace (`pyproject.toml` description, members, dependencies,
sources, coverage `source`), `uv.lock`, the CI mypy command, `.fr/candidate-install`, or
the dev commands and package lists in `AGENTS.md` and `HERMES.md`. No `vk` runner is
registered, and `fr apply --to vk` refuses it as an unknown runner through the registry's
existing unknown-runner path.

R2. Tests and fixtures that exercise only `fr_vk` are deleted. Mixed tests keep their
non-VK cases, and tests that assert VK install pieces assert their absence instead.
`.test_durations` names no deleted test. The behaviour tests of `fr-dispatch`, `fr-cncd`,
`fr-herdr` and `fr-claude-cloud` pass without change to what they assert. Captured data
(the Background's list) stays byte-identical.

R3. `RUNNER_PACKAGES` and the scaffolded `POST_CREATE` name no `fr-vk`, and this repo's
`.devcontainer/dev` and `.devcontainer/admin` install no `fr-vk`.

R4. In devcontainer mode, the shared `devcontainer up` path (`_devcontainer_up`, which
`fr isolation up`, `fr isolation rebuild` and exec's resume all call) refuses a profile
whose `devcontainer.json` installs `packages/fr-vk`, before it starts a container. The
refusal is an `IsolationError` (exit 2). It names the file and the
`--with '…#subdirectory=packages/fr-vk'` segment to delete, says VK support was removed,
and says to fix the profile on the default branch too, because every new branch is cut
from it. For `up`, the workspace is already recorded (gh#578), so `up`'s existing "fix the
cause and re-run" wording applies. A config file that does not exist is not this check's
concern: `devcontainer up` reports it as before.

R5. `scripts/install.sh` installs no VK pieces: no `vibe_kanban` MCP entry, no VK MCP binary
check or warning, no bridge wrapper, and no `vibe_kanban` verification hint. On install, it
removes a `vibe_kanban` entry from `~/.claude/.mcp.json` when present, and a `vk-bridge`
wrapper when its content execs `fr_vk.bridge` (at the default path or at
`VK_BRIDGE_WRAPPER_PATH`). It prints one line for each removal, and a file at the wrapper
path that fr did not write is never deleted. `--install-bridge` exits non-zero with a
message that VK support was removed. `--uninstall` keeps removing the MCP entry.

R6. The `fr-runner` skill is deleted, and nothing advertises it: not the `fr skills`
overview (`skills_cmd.py`), the README skills table (from
`scripts/readme-skill-summaries.yaml`, regenerated by `scripts/sync-readme.py`), or the
fr-dispatch explainer's title, tldr and `covers:`. The one runner-agnostic fact that
fr-dispatch does not already state, the up-front `unit_mismatch` refusal, moves into the
`fr-dispatch` skill. The `fr-dispatch` skill and `plugin.json` name no VibeKanban, and
their examples use a runner that remains.

R7. Kept code names `fr_vk` or VK nowhere as a live caller, implementation or example. This
covers docstrings, comments and help text in the files the Background lists. Behaviour does
not change.

R8. The published docs (`docs/explainers/`, `docs/*.md`, `docs/reference/`), `README.md`,
`AGENTS.md` (the repo-shape bullet and the bridge-audit rule, which now names
`fr_dispatch` and the remaining adapters) and `HERMES.md` describe no VK runner. Every
page's `covers:` names only existing paths. Historical records stay untouched:
`docs/superpowers/implemented/`, `docs/audits/`, `docs/triage/`, `CHANGELOG.md` and
earlier specs and brainstorms.

R9. Acceptance rows whose capability is VK-only are retired by amendment. Rows that also
cover a surviving capability drop their VK level refs by amendment. No row cites a deleted
test.

R10. A tripwire test fails when `fr_vk`, `fr-vk`, `vibe_kanban` or `VibeKanban`
(case-insensitive) appears in shipped sources: `packages/*/src`, `plugins/`, `scripts/`,
`.devcontainer/`, `.github/`, `.fr/`, the root `pyproject.toml` and `HERMES.md`. It also
fails when `fr-runner` appears under `plugins/`, `scripts/` or
`packages/fr/src/fr/commands/`. Exceptions are allowed by file **and** line pattern, never
by whole file. Only these are allowed: the R4 detection string, the R5 cleanup lines, and
the Background's kept items (`drop-vk-version`, the `vk-` vocabulary notes).

R11. The change ships a `major` change fragment. Its summary says VK support was removed,
and names the `devcontainer.json` fix for profiles scaffolded earlier.

## Design

**Deletion order.** The package, its tests and the workspace entries go first, together,
so the suite stays importable at every commit: a test that imports `fr_vk` cannot outlive
the package. Mixed test files lose only their VK cases, and both VK autouse fixtures in
`tests/conftest.py` go with what they reset. `uv lock` regenerates the lock, and
`scripts/bump-version.py --check` must stay green with one member fewer. This changes the
member set, not a version.

**Runner lists.** `RUNNER_PACKAGES` and `.fr/candidate-install`'s loop drop `fr-vk`. The
existing pins (`test_runner_package_lists.py:110-113`, `test_scenarios.py:135,175`,
`test_container_git_ownership.py:195`) keep checking that each list matches the entry
points. `test_runner_package_lists.py`'s VK assertions (:58, :82, :94-107) change to
assert absence. `install.sh` derives its `--with` set from the workspace, so it follows on
its own.

**Stale-profile refusal (R4).** One check in `_devcontainer_up` (`local.py:1292`), ahead of
its first side effect. If `_config_path(worktree, profile)` exists and its text contains
`subdirectory=packages/fr-vk`, it raises `IsolationError`. Putting it in the shared path
covers `up` (which calls it after `save_state`, `local.py:1257-1272`), `rebuild`
(`local.py:1402-1432`, which has no config-exists check of its own) and exec's resume
(`local.py:1380`) with one rule. It is a plain text search, so a `postCreateCommand` the
operator customised is judged by the same rule. Host-worktree and external modes never call
it.

**Installer (R5).** The VK MCP block, the binary warning, the verification hint and the
`--install-bridge` writer are deleted. A small cleanup function runs during install. It
removes only the `vibe_kanban` key with `jq`, leaving an `.mcp.json` without that key
untouched. It deletes the wrapper only when the file's content execs `fr_vk.bridge`.
`--install-bridge` prints the removal and exits 2. Uninstall keeps its existing removal.

**Skills.** `plugins/super-fr-dispatch/skills/fr-runner/` is deleted. The `fr-runner` row
leaves `skills_cmd.py` and `readme-skill-summaries.yaml`, then `scripts/sync-readme.py`
regenerates README. The fr-dispatch explainer is retitled to dispatch alone, and its
`covers:` drops the skill and `packages/fr-vk/src/**`. Neither mirror generator has an
fr-runner file to remove. `must_cover` (`.fr/docs.yaml:5-6`) then needs no page for it.

**Acceptance (R9).** Row changes go through `fr acceptance amend` (`retire`, `drop-level`),
never through hand edits. A mixed row keeps its surviving refs.

**Tripwire (R10).** It extends `tests/unit/test_vk_compat_removed.py`, which already holds
the VK-residue checks. The allowlist is a literal tuple of `(path, line regex)` pairs. An
entry that matches nothing fails the test too, so the allowlist cannot outlive what it
excuses.

## Tests

Named cases the plan turns into failing-first tests:

- **R1:** `fr apply --to vk` exits non-zero naming an unknown runner, and no
  `fr.runners` entry point is named `vk`.
- **R4:**
  - `up` refuses a profile that installs `packages/fr-vk`, leaves the workspace
    recorded, and starts no container.
  - `rebuild` refuses the same profile.
  - A customised `postCreateCommand` that still names the segment is refused.
  - A clean profile proceeds.
  - An absent config falls through to the existing behaviour.
- **R5, over a fixture home:**
  - With a `vibe_kanban` entry present, it is removed, other servers are kept, and a line
    is printed.
  - With the entry absent, `.mcp.json` is byte-identical.
  - An fr-written wrapper at the default path is removed, and so is one at
    `VK_BRIDGE_WRAPPER_PATH`.
  - A foreign file at the wrapper path is kept.
  - `--install-bridge` exits non-zero naming the removal.
  - `--uninstall` still removes the entry.
  - Install writes no `vibe_kanban` entry.
- **R6:** `fr skills` lists no `fr-runner`, `scripts/sync-readme.py --check` passes, and
  `fr docs check` passes.
- **R10:**
  - The tripwire fails on a planted `fr_vk` line in a scanned root.
  - It fails on a planted `VibeKanban` line in `plugins/`.
  - It passes on the allowlisted lines.
  - It fails when an allowlist entry matches nothing.
- **R2, R9, R11:** these are verified by CI gates rather than by new tests: the full suite
  on every shard, `fr acceptance check` (no row cites a missing test), and the
  `change-fragment` job.

## Verification

strategy: candidate
gate: developer
- vk-runner-removed: none — the R10 tripwire, the registry tests and the runner-list pins run in CI
- stale-vk-profile-refused: none — unit tests drive `_devcontainer_up` through `up` and `rebuild` over fixture profiles in CI
- installer-removes-vk-residue: none — `tests/integration/test_install_sh.py` drives install over a fixture home in CI
- dispatch-docs-name-no-vk: none — the R10 tripwire, `scripts/sync-readme.py --check` and `fr docs check` run in CI
