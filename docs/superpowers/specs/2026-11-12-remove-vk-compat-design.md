# Remove the remaining `vk` compatibility code — design

## 1. Goal

The `vk` command was renamed to `fr`. The wording was cleaned up in #1416; this
change removes the behaviour that still exists only for installs, repos and plan
files from before the rename. After it, `vk` is the name of one thing in this
repo: the VibeKanban runner (`packages/fr-vk`, `fr apply --to vk`).

## 2. Background (read from the code)

- `packages/fr/src/fr/isolation/migrate.py` and `fr init migrate`
  (`commands/init_cmd.py`) rewrite a repo's `vk` spellings to `fr`. The
  2026-07-24 `remove-vk-legacy-fallbacks` spec removed the read-side fallbacks
  and kept this write path as the escape hatch its hard error names.
- `isolation/local.py::_ensure_mounted_env_file` raises an `IsolationError`
  naming `fr init migrate` when a devcontainer config mounts
  `~/.config/vk/secrets/`.
- `commands/isolation_cmd.py` has `DEFAULT_BRANCH = "vk-iso/work"`, the default
  of `fr isolation up --branch`. No other code reads the constant.
- `commands/common.py::resolve_repo_root` honours `$VK_REPO_ROOT`. The name is
  used in 74 unit test files, 3 integration test files, `artifacts/trigger.py`'s
  docstring and the `fr-acceptance` skill. No `FR_REPO_ROOT` exists.
- `scripts/install.sh` reads `VK_INSTALL_SKIP_PREFLIGHT`, purges the retired rule
  `vk-plan-override.md` (`RETIRED_CLAUDE_RULES`, and an `rm -f` in the rules
  step), holds `SKILL_NAMES=(vk-plan vk-dispatch vk-execute vk-progress)` for
  pre-plugin user-level copies, and names `superpowers-for-vk@` in a grep and a
  comment.
- `plan_validator_wrapper.py::is_super_fr_validator_wrapper` accepts a wrapper
  whose text contains `superpowers-for-vk` or `super-fr`.
- `scripts/bump-version.py` probes the entry points `fr` then `vk`.
- `types.py::PlanMeta` has `vk_version: str | None = None`, parsed and never
  enforced. `PlanMeta` is `extra="forbid"`. 42 archived plans under
  `docs/superpowers/implemented/plans/` carry the key, as do test fixtures. The
  `fr-plan` skill lists the key among `_meta.yaml`'s fields.
- The plan kind's stamp is `_meta.yaml`'s `schema_version` (`Literal[2]`), and
  its locator is `docs/superpowers/plans/*/_meta.yaml`. The one existing plan
  migration, `artifacts/fr_version.py`'s `CEILING_REPAIR`, is a `Repair`: it
  rewrites one top-level line in place and leaves the stamp alone.
- Not `vk`-command residue, and left alone: `packages/fr-vk`, `fr_dispatch`
  wording about the VK runner, `VK_MCP_BINARY`, `VK_BRIDGE_WRAPPER_PATH`, the
  `vk-bridge` wrapper, `VK_DERIO_OPS_PROJECT*`, `VK_MAX_CONCURRENT_EXECUTIONS`,
  and `tests/conftest.py::_fresh_vk_repo_cache` (it resets `fr_vk.config`).

## Requirements

R1. `fr init migrate` does not exist, and `fr/isolation/migrate.py` is deleted with its tests.
R2. `_ensure_mounted_env_file` has no `vk`-specific branch: an env-file path is ensured the same way whatever its directory is called.
R3. `fr isolation up` without `--branch` refuses with a usage error that names `--branch`; no default branch name exists in the code.
R4. `FR_REPO_ROOT` overrides the repo root exactly as `VK_REPO_ROOT` did, and `VK_REPO_ROOT` is not read anywhere.
R5. `scripts/install.sh` reads `FR_INSTALL_SKIP_PREFLIGHT` and no longer reads `VK_INSTALL_SKIP_PREFLIGHT`.
R6. `scripts/install.sh` no longer names `vk-plan`, `vk-dispatch`, `vk-execute`, `vk-progress`, `vk-plan-override.md` or `superpowers-for-vk`, and performs no purge for them.
R7. A plan-validator wrapper is recognised as fr's own only when it names `super-fr`.
R8. `scripts/bump-version.py` probes the `fr` entry point only.
R9. `PlanMeta` has no `vk_version` field, so parsing a plan that carries the key fails as for any unknown key.
R10. A registered plan repair removes a top-level `vk_version` line from a plan's `_meta.yaml` and changes no other byte; a file where the key is present but is not a single top-level line is reported as that artifact's failure and left byte-identical.
R11. That repair applies to archived plans (`docs/superpowers/implemented/plans/*/_meta.yaml`) as well as live ones, in any repo `fr migrate artifacts --yes` runs in.
R12. This repo's own plans, archived plans and test fixtures carry no `vk_version` after this PR, the archived ones changed by running the repair, not by hand.
R13. The `fr-plan` skill no longer lists `vk_version`, and the generated mirrors match.
R14. Comments and docstrings that describe the removed behaviour are removed or reworded: `labels.py`'s `vk-ready`/`vk-synced` docstring (the labels are `fr:ready`/`fr:synced`), `types.py`, `parser.py`, `artifacts/trigger.py`'s `fr init migrate` sentence, and the mention of `_fresh_vk_repo_cache` in `AGENTS.md` stays as it is.
R15. `.claude/rules/artifact-versioning.md` states the one exception this change makes to "archived artifacts are frozen": the `vk_version` repair, authorised by the operator.
R16. The VibeKanban runner and everything listed as left alone in §2 is unchanged.
R17. The PR adds a change fragment with `bump: major`.

## 3. Design

### 3.A Plain removals (R1, R2, R6, R7, R8)

Delete `isolation/migrate.py`, the `migrate` command in `init_cmd.py` and its
imports, and `tests/unit/test_init_migrate.py`. In `_ensure_mounted_env_file`
drop the `/.config/vk/secrets/` check and its docstring sentence. In
`install.sh` drop `RETIRED_CLAUDE_RULES` and its uninstall loop, the
`rm -f "$RULES_DIR/vk-plan-override.md"` line, `SKILL_NAMES` and whatever loop
consumes it, the `superpowers-for-vk@` alternative in the sibling-repo grep and
the comment that names it. In `plan_validator_wrapper.py` the second condition
becomes `"super-fr" in text`. In `bump-version.py` the loop over `("fr", "vk")`
becomes a single probe and the error names `fr` alone. `CHANGELOG.md` is history
and is not edited.

### 3.B `--branch` is required (R3)

`up`'s `branch` option becomes a required option (`typer.Option(...)`), so typer
itself refuses, exit 2, naming `--branch`. `DEFAULT_BRANCH` is deleted. The
comment in `exec` that mentions `vk-iso/work` is reworded to describe the
behaviour without the old default.

### 3.C Environment variables (R4, R5)

`resolve_repo_root` reads `FR_REPO_ROOT`; the empty-string rule is kept. Every
test, the `trigger.py` docstring and the `fr-acceptance` skill use the new name.
`install.sh` and its tests use `FR_INSTALL_SKIP_PREFLIGHT`. No fallback and no
warning for the old names: an unset `FR_REPO_ROOT` falls through to git, as an
unset `VK_REPO_ROOT` did.

### 3.D `vk_version` (R9–R12)

Remove the field from `PlanMeta` and the sentences about it in `types.py` and
`parser.py`.

The migration is a `Repair` on the `plan` kind, in a new module
`fr/artifacts/plan_vk_version.py` imported by `fr/artifacts/__init__.py`, modelled
on `fr_version.py`:

- `applies(path)`: the parsed YAML document is a mapping with a `vk_version`
  key.
- `fn(path)`: find the one line matching `^vk_version\s*:.*$` at column 0,
  remove it and its newline, write through `write_text_atomic`. If the key
  parses but no such single line exists (a block scalar, a flow mapping),
  raise an `ArtifactMigrationError` subclass, so the runner reports that one
  artifact and leaves it untouched.

It is a repair and not a schema migration for the reason `fr_version.py`
records: the plan stamp is `schema_version`, so a stamp bump would declare a new
plan-folder schema and make every plan unreadable by every released `fr`. No
released `fr` is affected by the key's absence, since the field was always
optional; only the new `fr` refuses its presence, and the repair is what removes
it. No frozen legacy model is needed, because the repair never validates the
file against a model.

**Reaching the archive (R11).** `Repair` gains one optional field,
`extra_locators: tuple[str, ...] = ()`. The runner's planning step, for a repair
that declares it, also globs those patterns under the repo root and offers each
match to `applies`/`fn`. Such a path is repaired only: it is not stamp-checked,
not structure-validated and not counted by `fr validate artifacts`, so nothing
else about the archive's frozen status changes. This repair declares
`("docs/superpowers/implemented/plans/*/_meta.yaml",)`. The uncommitted-changes
veto and the migration commit treat these paths like any other migrated path.
The plan phase reads `runner.py` end to end before choosing the exact seam; if
the planning step cannot take a per-repair locator without a second enumeration
of kinds (which `test_tripwire_artifact_kinds.py` forbids), that is a spec
defect to fix here, not to work around.

Test fixtures under `tests/` drop the key by edit. A fixture that exists to show
an unknown key is refused may keep using `vk_version` as its unknown key only if
no other test relies on it parsing; otherwise it uses a neutral name.

### 3.E Skill, mirrors, docs, fragment (R13–R15, R17)

Edit `plugins/super-fr/skills/fr-plan/SKILL.md`, then run `sync-opencode.py`,
`sync-hermes.py` and `sync-readme.py` (the CLI reference loses `fr init
migrate`). Pages whose `covers:` include a changed path are edited where they
describe removed behaviour, otherwise their `reviewed:` stamp moves.
`.changes/chore-remove-vk-compat.yaml` declares `bump: major`.

## 4. Decisions

See the spec journal. The operator chose: remove `vk_version` with a migration
that reaches the archive; hard-rename the environment variables; make `--branch`
required; remove every old-install path including wrapper recognition; a major
bump; CI tests as the verification.

## 5. Risks

- A consumer repo whose committed `scripts/validate-plans.sh` still says
  `superpowers-for-vk` is treated as a foreign file afterwards and is not
  refreshed. The operator confirmed none remain.
- A script outside this repo that sets `VK_REPO_ROOT` silently stops overriding.
- The archive repair rewrites 42 files in this repo in one migration commit.
  Each loses one line; the diff is reviewable by `git diff --stat` and a grep.
- Until a repo runs the migration, the new `fr` refuses its plans that carry the
  key. The CLI-entry gate runs the repair in every context that may write, and
  names `fr migrate artifacts --yes` in the others.

## Verification

gate: none
- init-migrate-removed: none — unit tests over the CLI's command tree and the import in CI; an installed CLI adds nothing
- isolation-up-requires-branch: none — a CLI-runner unit test asserts exit 2 and the flag name in CI
- fr-repo-root-override: none — unit tests set each variable and assert which one moves the root in CI
- installer-names-no-vk-residue: none — the installer's unit and integration tests run it against a fixture home in CI
- plan-vk-version-repaired: none — unit tests run the repair over live, archived and unrewritable fixtures and assert bytes in CI

## Implementation Plans

(none yet)
