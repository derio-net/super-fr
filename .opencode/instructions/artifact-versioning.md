# Artifact versioning — a shape change ships its own migration

## Rule

`fr` and the skills generate five kinds of artifact — plans, journals, runs,
the acceptance matrix, specs — and every one of them declares the version it
was written for (`fr.artifacts.registry`, spec
`2026-08-30-artifact-migration-framework-design.md` §3.A). A node's installed
`fr` changes whenever the plugin updates, mid-flight; the files on disk do not
change with it.

**Any PR that changes an artifact's shape ships three things in the SAME PR:**

1. a **stamp bump** — `current_version` for that kind, in
   `packages/fr/src/fr/artifacts/registry.py`, and nowhere else;
2. a **registered migration** that moves an artifact from the old version to
   the new one — `SchemaMigration` when the shape moves, `Repair` when only a
   constraint does — registered into `MIGRATIONS` via a module imported by
   `fr/artifacts/__init__.py`. *A migration nobody imports never runs*;
3. a **structure validator** for that kind, reached as `ArtifactKind.validate`
   (`fr.artifacts.structure`) and exercised by `fr validate artifacts`, which
   CI runs over this repo's own artifacts.

"Shape" means what a reader must handle: a new required field, a renamed or
removed one, a changed carrier, a new nesting. Adding an **optional, defaulted**
field is not a shape change *when no released `fr` can read the file at all*
(the `run` kind in 4.0.0 — `fr/run/model.py` does not exist on `origin/main`).
If a released `fr` could read it, it is a shape change: the models are
`extra="forbid"`, so an old reader does not ignore your new key, it raises.

Related obligation, from the same closed-world models: the first PR that moves
any kind's `current_version` past 1 must, in that PR, add an optional defaulted
`schema_version: int = 1` to that kind's model — `RunState`, `Matrix` and
`PlanMeta` all reject an unknown key, so the stamp the migration writes would
make the file unparseable by the `fr` that wrote it. (`PlanMeta` is the
exception that proves it: a plan's stamp *is* its existing `schema_version`.)

## Two operational facts, learned by running the thing

### 1. Agent sessions, pods and CI always land non-interactive — by design

`fr.artifacts.trigger.is_interactive` needs a TTY on **both** stdin and stdout
and treats `CI` being set as decisive. `fr isolation exec`, an agent's Bash
tool, a hermes pod and every CI runner fail that predicate. So while any live
artifact is stale, the **first `fr` command in those contexts refuses** and
writes nothing:

    fr: artifacts in <repo> were written for a different fr and must be
    migrated before this command can run.

That is not a deadlock and not a bug to route around. `fr migrate artifacts` is
itself exempt from the gate and needs no TTY, so **the agent runs
`fr migrate artifacts --yes` itself** and continues. This is the operator's
deliberate choice — safe by default, one explicit step — chosen over
auto-migrating in contexts where a surprise commit is worst (the bridge
`reset --hard`s its checkout every tick, so a commit there is discarded *and*
misleading). **Do not "fix" it later by loosening the predicate**, adding an
agent-detecting exemption, or making non-interactive contexts migrate silently.
What an agent must never be able to do is proceed over stale artifacts.

### 2. Moving `current_version` makes this repo's own CI red until you migrate

The moment a kind's `current_version` moves, every live artifact of that kind
in *this* repo is stale — and `.github/workflows/acceptance-report.yml`
installs `fr` from this checkout and runs `fr acceptance check` with `CI=true`,
which the gate then refuses. So:

**Any PR that moves a kind's `current_version` runs `fr migrate artifacts --yes`
and commits the result in the same PR.**

Dogfood it; do not hand-edit the artifacts. This already happened once, on the
branch that built the framework: turning the gate on refused the repo's own CI
over a single plan carrying `fr_version: '>=3.0.0,<4.0.0'`, and the fix was to
run the framework's own migration (one line, `<4.0.0` → `<5.0.0`) rather than
patch the file by hand.

## Enforcement

- `fr validate artifacts` — stamp (unreadable, stale, or newer-than-this-`fr`
  all fail closed) plus per-kind structure. Run in CI by the
  `validate-artifacts` job in `.github/workflows/ci.yml`, and locally by
  `tests/unit/test_validate_artifacts.py::test_this_repos_own_artifacts_are_structurally_valid`.
- `tests/unit/test_tripwire_artifact_kinds.py` — nothing outside
  `fr.artifacts.registry` may enumerate artifact kinds. Adding a kind stays a
  one-module edit; a second list is how a kind gets migrated but never
  validated.
- `tests/unit/test_migration_runner.py::test_the_shipped_registry_registers_nothing_for_the_version_one_kinds`
  — registering a schema migration for a kind still at version 1 fails, and the
  failure message tells you the model must accept `schema_version` first.

## What this rule does not cover

Archived artifacts under `docs/superpowers/implemented/`. They record what
shipped and are frozen (spec §2 non-goals): no locator reaches them, no
migration rewrites them, and `fr validate artifacts` does not check them. A
migration that "fixes" history is a bug, not a courtesy.
