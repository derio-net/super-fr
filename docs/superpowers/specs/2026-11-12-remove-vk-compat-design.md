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
  enforced. `PlanMeta` is `extra="forbid"`. 33 archived `_meta.yaml` files under
  `docs/superpowers/implemented/plans/` carry the key and no live plan does; test
  fixtures carry it too. Archived plans ARE parsed with `fr.parser.parse`: by
  `fr status` (`spec.py::compute_status`) and by gate backfill
  (`gatebackfill/candidates.py`), both of which catch the parse error and report
  the plan as missing or unknown. The
  `fr-plan` skill lists the key among `_meta.yaml`'s fields.
- The plan kind's stamp is `_meta.yaml`'s `schema_version` (`Literal[2]`), and
  its locator is `docs/superpowers/plans/*/_meta.yaml`. The one existing plan
  migration, `artifacts/fr_version.py`'s `CEILING_REPAIR`, is a `Repair`: it
  rewrites one top-level line in place and leaves the stamp alone.
- The runner has no single planning step. `plan_migrations`, `is_stale`,
  `inspection_failures` and `run_migrations` (`artifacts/runner.py`) each walk
  `registry.iter_paths_of`, which skips the archive, and each path goes through
  `_actions_for`, which checks the stamp before any repair. The
  uncommitted-changes veto and the migration commit are path-generic.
  `fr validate artifacts` walks `iter_paths_of` only.
- Messages that recommend a bare `fr isolation up` as the remedy:
  `commands/isolation_cmd.py` (three), `isolation/sessions.py`,
  `isolation/local.py`, the two Hermes hooks under
  `plugins/super-fr/hooks/hermes/`, `packages/fr-opencode-plugin/src/index.ts`
  (two), and the golden fixture `tests/fixtures/hooks/guard-verdicts.yaml`.
- The merged acceptance row `vk-legacy-fallbacks-removed` (status `ci`) asserts
  that an unmigrated repo fails loudly pointing at `fr init migrate`.
- Not `vk`-command residue, and left alone: `packages/fr-vk`, `fr_dispatch`
  wording about the VK runner, `VK_MCP_BINARY`, `VK_BRIDGE_WRAPPER_PATH`, the
  `vk-bridge` wrapper, `VK_DERIO_OPS_PROJECT*`, `VK_MAX_CONCURRENT_EXECUTIONS`,
  and `tests/conftest.py::_fresh_vk_repo_cache` (it resets `fr_vk.config`).

## Requirements

R1. `fr init migrate` does not exist, and `fr/isolation/migrate.py` is deleted with its tests.
R2. `_ensure_mounted_env_file` has no `vk`-specific branch: an env-file path is ensured the same way whatever its directory is called, so a config that mounts `~/.config/vk/secrets/<f>` gets that file created like any other.
R3. `fr isolation up` without `--branch` refuses with a usage error that names `--branch`; no default branch name exists in the code.
R4. `FR_REPO_ROOT` overrides the repo root exactly as `VK_REPO_ROOT` did, and `VK_REPO_ROOT` is not read anywhere.
R5. `scripts/install.sh` reads `FR_INSTALL_SKIP_PREFLIGHT` and no longer reads `VK_INSTALL_SKIP_PREFLIGHT`.
R6. `scripts/install.sh` contains no code or text naming `vk-plan`, `vk-dispatch`, `vk-execute`, `vk-progress`, `vk-plan-override.md` or `superpowers-for-vk`. The generic bare-org purge, which drops every `*@derio-net` id whatever it is called, is unchanged.
R7. A plan-validator wrapper is recognised as fr's own only when it names `super-fr`; recognition of the old `marketplaces/derio-net/` delegate path is unchanged.
R8. `scripts/bump-version.py` probes the `fr` entry point only.
R9. `PlanMeta` has no `vk_version` field, so parsing a plan that carries the key fails as for any unknown key.
R10. A registered plan repair removes the top-level `vk_version` entry from a plan's `_meta.yaml` and changes no other byte. A file where the key is present but cannot be removed as exactly one whole top-level line (a block or multi-line scalar, a duplicated key, a flow mapping) is reported as that artifact's failure and left byte-identical.
R11. That repair applies to archived plans (`docs/superpowers/implemented/plans/*/_meta.yaml`) as well as live ones, both when `fr migrate artifacts --yes` is typed and when the CLI-entry gate migrates.
R12. An archived file the repair cannot read or rewrite is reported by `fr migrate artifacts` and never makes the repo stale: it does not hold the CLI-entry gate.
R13. After this PR no `_meta.yaml` in this repo, live or archived, has a `vk_version` key, the archived ones changed by running the repair and not by hand, and every archived plan in this repo parses. (Other archived files that mention the string in prose or phase YAML are history and are not touched.)
R14. The `fr-plan` skill no longer lists `vk_version`, and the generated mirrors match.
R15. Text that this change makes false is removed or reworded: the `vk-ready`/`vk-synced` wording in `labels.py` and `render.py` (the labels are `fr:ready`/`fr:synced`), the `vk_version` sentences in `types.py` and `parser.py`, `artifacts/trigger.py`'s `fr init migrate` sentence, `bump-version.py`'s rebrand comment, and the "archives are never migrated" statements in `artifacts/registry.py`, `artifacts/runner.py`, `parser.py` and `spec.py`, which gain the one exception.
R16. `.claude/rules/artifact-versioning.md` states the one exception this change makes to "archived artifacts are frozen": the `vk_version` repair, authorised by the operator.
R17. Every message that recommends `fr isolation up` as a remedy names `fr isolation up --branch <branch>`, in the CLI, the Hermes hooks, the OpenCode plugin and their golden fixtures.
R18. The merged acceptance row `vk-legacy-fallbacks-removed` is amended in this PR so it no longer asserts an error that points at `fr init migrate`.
R19. The VibeKanban runner and everything listed as left alone in §2 is unchanged, including `tests/conftest.py::_fresh_vk_repo_cache`, its mention in `AGENTS.md`, and the `vk-ready`/`vk-synced` wording inside `packages/fr-vk`.
R20. The PR adds a change fragment with `bump: major`.

## 3. Design

### 3.A Plain removals (R1, R2, R6, R7, R8, R18)

Delete `isolation/migrate.py`, the `migrate` command in `init_cmd.py` and its
imports, and `tests/unit/test_init_migrate.py`.

In `_ensure_mounted_env_file` drop the `/.config/vk/secrets/` check and its
docstring sentence. The test that pins the error
(`tests/unit/test_isolation.py`, `match="fr init migrate"`) is replaced by one
asserting the file is created at the mounted path. `fr acceptance amend --id
vk-legacy-fallbacks-removed --op reword --feature 2026-11-12-remove-vk-compat`
rewords that row to what still holds (vk spellings do not resolve) without the
`fr init migrate` pointer.

In `install.sh` drop `RETIRED_CLAUDE_RULES` and its `--uninstall` loop, the
`rm -f "$RULES_DIR/vk-plan-override.md"` line, `SKILL_NAMES` and its two
consumers (the uninstall loop and install step 6), the `^superpowers-for-vk@`
alternative in the sibling-repo grep, and both comments that name
`superpowers-for-vk`. Consequence, accepted: a machine whose only purged
bare-org id is `superpowers-for-vk@derio-net` would be told some purged ids
belong to sibling repos. The operator confirmed no such machine remains. The
tests that pin these (`tests/integration/test_install_sh.py`'s retired-rule and
legacy-skill cases, and the seeded id and assertion in
`test_install_marketplace_namespace.py`) are deleted or moved to a neutral
bare-org id.

In `plan_validator_wrapper.py` the second condition becomes `"super-fr" in
text`; `test_plan_validator_wrapper_rename.py`'s `PRE_SWEEP_WRAPPER` case
inverts (such a wrapper is foreign). In `bump-version.py` the loop over
`("fr", "vk")` becomes a single probe and the error names `fr` alone.
`CHANGELOG.md` is history and is not edited.

### 3.B `--branch` is required (R3, R17)

`up`'s `branch` option becomes a required option (`typer.Option(...)`), so typer
itself refuses, exit 2, naming `--branch`. `DEFAULT_BRANCH` is deleted. No
in-repo caller invokes `up` without the flag. The comment in `exec` that
mentions `vk-iso/work` is reworded.

Every remedy message listed in §2 becomes `fr isolation up --branch <branch>`.
The Hermes hook texts and the OpenCode plugin's strings change together with
`tests/fixtures/hooks/guard-verdicts.yaml` and any parity fixture that quotes
them; the Claude Code hooks already name the flag.

### 3.C Environment variables (R4, R5)

`resolve_repo_root` reads `FR_REPO_ROOT`; the empty-string rule is kept. Every
test, the `trigger.py` docstring and the `fr-acceptance` skill use the new name.
`install.sh` and the tests that set it use `FR_INSTALL_SKIP_PREFLIGHT`. No
fallback and no warning for the old names.

### 3.D `vk_version` (R9–R13)

Remove the field from `PlanMeta` and the sentences about it in `types.py` and
`parser.py`.

The migration is a `Repair` on the `plan` kind, in a new module
`fr/artifacts/plan_vk_version.py` imported by `fr/artifacts/__init__.py`. It is
a repair and not a schema migration for the reason `fr_version.py` records: the
plan stamp is `schema_version`, so a stamp bump would declare a new plan-folder
schema and make every plan unreadable by every released `fr`. No released `fr`
is affected by the key's absence. No frozen legacy model is needed, because the
repair never validates the file against a model.

**The predicate.** `applies(path)` first tests the raw bytes for `vk_version`
and answers False without parsing when absent, so the steady state costs one
read per file. Only then does it parse and answer whether the document is a
mapping with that key.

**The rewrite.** `fn(path)` reads with `registry.read_verbatim` and splits with
`registry.split_lines` (never `read_text`, which normalises CRLF and mishandles
a BOM). It requires exactly one line matching `^vk_version\s*:` at column 0,
removes that line with its terminator, then re-parses the new text and requires
it to equal the original mapping minus `vk_version`. Any other outcome raises
an `ArtifactMigrationError` subclass before a byte is written. It writes through
`write_text_atomic`.

**Reaching the archive.** `Repair` gains one optional field,
`extra_locators: tuple[str, ...] = ()`; this repair declares
`("docs/superpowers/implemented/plans/*/_meta.yaml",)` and `CEILING_REPAIR`
declares none, so the fr_version repair still skips the archive.
`iter_paths_of` is untouched. The runner gains one helper that, for each
registered repair with extra locators, globs them and yields the paths where
`applies` is true, with no stamp check, no schema chain and no structure
validation: these paths are repaired only. The four walks use it as follows:

| Walk | Archive paths |
|---|---|
| `plan_migrations` (preview) | listed as repair actions; a failing one listed as a failure |
| `run_migrations` (apply, typed or by the gate) | repaired through a repair-only apply path; a failing one reported, the rest applied |
| `is_stale` (the gate's trigger) | a path whose predicate is true makes the repo stale; a path whose predicate or rewrite check raises does not |
| `inspection_failures` | never includes an archive path |

So the gate fires for a repo whose only carriers are archived (this repo's
case), and an unreadable or unrewritable archived file is reported by
`fr migrate artifacts` and holds nothing (R12). The veto and the migration
commit take these paths unchanged. `fr validate artifacts` stays blind to the
archive.

Before migration, `fr status` and gate backfill (both exempt from the gate)
report an archived plan that carries the key as missing or unknown, as they do
for any archived plan that fails to parse. Running any gated command, or
`fr migrate artifacts --yes`, ends that.

Test fixtures under `tests/` drop the key by edit, and the three tests that
assert it parses (`test_v2_parse.py`, `test_plan_folder_corpus.py`) are removed
or inverted. The unknown-key test in `test_v2_parse.py` uses a neutral key name,
so it does not pass merely because `vk_version` became unknown.

### 3.E Skill, mirrors, docs, wording, fragment (R14–R16, R20)

Edit `plugins/super-fr/skills/fr-plan/SKILL.md`, then run `sync-opencode.py`,
`sync-hermes.py` and `sync-readme.py` (the CLI reference loses `fr init
migrate`). Reword the text R15 lists. Pages whose `covers:` include a changed
path are edited where they describe removed behaviour, otherwise their
`reviewed:` stamp moves. `.changes/chore-remove-vk-compat.yaml` declares
`bump: major`.

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
- The archive repair rewrites 33 `_meta.yaml` files in this repo in one
  migration commit. Each loses one line; `git diff --stat` shows it.
- Until a repo migrates, the new `fr` refuses live plans that carry the key and
  `fr status` reports archived ones as missing. The gate runs the repair in
  every context that may write. In a context that may not (a daemon checkout,
  the opt-out), a repo with any repairable carrier, archived ones included, is
  refused until a migration reaches its default branch, as for any stale
  artifact.
- The predicate runs before every gated command over an archive that only
  grows; the byte test keeps that to one read per archived plan.

## 6. Cases the unit tests cover

- R1: the `init` command group has no `migrate`; `fr.isolation.migrate` does not import.
- R2: a config mounting `~/.config/vk/secrets/x.env` gets the file created, no error.
- R3: `up` with no `--branch` exits 2 and names the flag; nothing is created.
- R4: `FR_REPO_ROOT` moves the root; `VK_REPO_ROOT` alone does not; empty string falls through.
- R5–R6: the installer tests run under `FR_INSTALL_SKIP_PREFLIGHT`; `install.sh` contains none of the retired names.
- R7: a wrapper naming only `superpowers-for-vk` is foreign; the old delegate path naming `super-fr` is still fr's own.
- R8: `bump-version.py` names no `vk` entry point.
- R9: a `_meta.yaml` with `vk_version` fails to parse; one without parses.
- R10: the repair over LF, CRLF, BOM, last-line-without-newline and quoted-value files removes exactly the one line; block scalar, multi-line quoted scalar, duplicated key and flow mapping each raise and leave the file byte-identical; a second run is a no-op.
- R11: preview lists archived carriers; apply repairs live and archived in one commit; `is_stale` is true with only an archived carrier; `CEILING_REPAIR` still skips the archive; the existing archive-exclusion tests stay green.
- R12: an unrewritable archived file is reported, the others are repaired, and `is_stale` is false afterwards.
- R13: no `_meta.yaml` in this repo has the key; every archived plan in this repo parses.
- R14: the mirror tripwires pass. R17: the golden hook fixtures match the new remedy text.

## Verification

gate: none
- init-migrate-removed: none — unit tests over the CLI's command tree and the import in CI; an installed CLI adds nothing
- isolation-up-requires-branch: none — a CLI-runner unit test asserts exit 2 and the flag name in CI
- fr-repo-root-override: none — unit tests set each variable and assert which one moves the root in CI
- installer-names-no-vk-residue: none — the installer's unit and integration tests run it against a fixture home in CI
- plan-vk-version-repaired: none — unit tests run the repair over live, archived and unrewritable fixtures and assert bytes in CI
- archived-plans-readable-after-repair: none — a unit test parses every archived plan in this repo in CI

## Implementation Plans

(none yet)
