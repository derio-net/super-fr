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
field is not a shape change *when no released `fr` can read the file at all* —
a genuinely narrow exemption, and the example that used to sit here has expired:
it read "the `run` kind in 4.0.0 — `fr/run/model.py` does not exist on
`origin/main`", which stopped being true the moment `fr run` shipped. Check the
claim before relying on it. If a released `fr` could read the file, it IS a
shape change: the models are `extra="forbid"`, so an old reader does not ignore
your new key, it raises.

The `run` kind proved this on itself in the 2026-09-18 harness-parity PR.
Adding an optional, defaulted `StepRecord.answered_by` was treated as a shape
change, and the live evidence arrived immediately: an `fr` 4.4.0 on `PATH` reads
a cursor written by the new one and fails with `schema_version — Extra inputs
are not permitted`. Optional and defaulted buys you nothing against a
closed-world model held by an older reader.

Related obligation, from the same closed-world models: the first PR that moves
any kind's `current_version` past 1 must, in that PR, add an optional defaulted
`schema_version: int = 1` to that kind's model — `RunState`, `Matrix` and
`PlanMeta` all reject an unknown key, so the stamp the migration writes would
make the file unparseable by the `fr` that wrote it. (`PlanMeta` is the
exception that proves it: a plan's stamp *is* its existing `schema_version`.)

## Removing or moving a field freezes the old shape — migrations never read with the live model

**The first migration that removes or moves a field freezes the prior shape as a
legacy model, and no migration may validate an old file against the live one.**

Every `run` migration up to 3 → 4 "parsed first, refused rather than certified" —
correctly — but did it with the LIVE `parse_run_state`. That was sound only by
accident: every change so far had been additive, so the live model happened to
be a superset of every older shape. The 4 → 5 rewrite (2026-09-20, one record per
unit) REMOVES `items`, `dispatch` and `accounting` from an `extra="forbid"` model.
Validated against the live model, a v2 cursor carrying `items` stops parsing, and
the chain `2 → 3 → 4 → 5` refuses every older cursor **at its first hop** —
stranding exactly the files the framework exists to carry. Nothing would have
gone red: a refusal is a per-artifact failure, reported politely, forever.

So, when a change removes or moves a field:

1. **Freeze the prior shape** as its own closed-world model beside the live one
   (`fr.run.legacy.RunStateV4`, a superset of versions 1–4), with its
   vocabularies INLINED rather than imported — a frozen reader that follows a
   live vocabulary stops being a reader of the old version the day the
   vocabulary moves. Pin its source (`legacy.FROZEN_CLASS_SHA256`,
   `tests/unit/test_run_legacy.py`): a cursor on someone's unmerged branch is
   already written, and editing the reader changes what fr believes those bytes
   mean. A later removal freezes a `…V5` beside it; it does not edit `…V4`.
2. **Point EVERY hop at it**, not only the new one
   (`fr.artifacts.run_cursor.cursor_guard`). The old hops are the ones that
   break, and they break silently.
   `tests/unit/test_migration_run_unit_record.py::test_no_run_migration_names_the_live_parser`
   is the tripwire.
3. **Build the rewrite in memory and write once**, through
   `fr.artifacts.atomic.write_text_atomic`. A body rewrite can half-write in a
   way a stamp cannot: every refusal must fire before a byte moves, and a cursor
   the rewrite cannot convert is left **byte-identical** and reported as that one
   artifact's failure while the rest migrate.
4. **Survive your own crash window.** `fn` writes the body and the runner writes
   the stamp afterwards; a crash in between leaves a new body under an old stamp,
   which the frozen reader (closed-world, by design) refuses. The rewriting `fn`
   must recognise a body that is already WHOLLY in the new shape and let the
   runner finish — the one legitimate use of the live model in a migration,
   because "is this already v5?" is a question only the v5 model can answer.
5. **Assert every hop of the chain**, not just its endpoint
   (`test_the_run_kind_is_reachable_all_the_way_from_version_one_to_five`:
   `[2, 3, 4, 5]`). It is this repo's only guard against two branches allocating
   the same version number, which has now happened twice.

## What the CLI-entry gate will and will not do

It fires before every command, migrates when it can, and **refuses in four
situations rather than write** (`fr.artifacts.trigger`). All four print the same
six lines: what is stale, why fr will not act *here*, then `fr migrate
artifacts` (preview), `fr migrate artifacts --yes` (apply) and
`FR_SKIP_MIGRATION=1` (bypass).

1. **Non-interactive** — CI, a pod, an agent's Bash tool, `fr isolation exec`.
   See the section below; this is the load-bearing one.
2. **HEAD is the repository's default branch.** No automatic migration and no
   automatic commit on `main` (or whatever `origin/HEAD` says the default is).
   An `fr` command typed in the base clone used to leave a real commit on a
   protected branch that the operator then had to notice and undo. Work happens
   on a branch; `fr migrate artifacts --yes` still works anywhere, because you
   typed it.
3. **An artifact you have uncommitted changes in.** `git add -- <path>` stages
   the *whole* file, so migrating a `_meta.yaml` you are mid-edit in would
   commit your half-typed line under `chore(fr): migrate ...`. fr holds that one
   file back, reports it, and migrates the rest. Commit or stash your edit, or
   run the migration yourself. (The alternative — migrate it but leave it out
   of the commit — was rejected: it rewrites a file you have open and leaves no
   sign it did.)
4. **An artifact it cannot inspect** — an unreadable stamp, a repair predicate
   that raises, a `_meta.yaml` that is empty or truncated. Unknown state is not
   "current"; the gate refuses and names the file.

**Exempt commands** are `migrate` plus the read-only commands in
`fr.artifacts.trigger.READ_ONLY_COMMANDS` — `status`, `skills`, `isolation`, `init`,
`validate`, `harness`, `triage` and `usage` at the time of writing, but the tuple is the source of
truth; this sentence used to say "the read-only five" and was two short before anyone
noticed — along with `--help`, `--version` and `FR_SKIP_MIGRATION=1`. The criterion for
membership is the tuple's own docstring: the command never mutates a registered artifact.
`harness` meets it by only reading hook registrations; `triage` by never reading or
writing an artifact at all (its state lives under `~/.cache/fr/triage/`); `usage` by only
reading a run cursor and harness transcripts and writing under `~/.cache/fr/usage/`. Two of those
matter beyond tidiness: `fr status` is
registered as never mutating and must not mutate by proxy, and `fr validate
artifacts` is the diagnostic for exactly the state the gate repairs — if the
gate ran first, a human could never see it report a stale artifact. The list is
pinned literally by
`tests/unit/test_migration_trigger.py::test_the_exemption_list_is_exactly_these_things`:
adding an exemption means arguing for it in a diff to that line, because the
failure mode of an over-broad list is silence.

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
- A **duplicate YAML key** in any of the three YAML-carried kinds fails
  `fr validate artifacts`. PyYAML keeps the last occurrence silently, which is
  how `docs/acceptance/matrix.yaml` lost a test ref that nothing reported
  missing; `fr.artifacts.structure._StrictLoader` is the detector.

## What this rule does not cover

Archived artifacts under `docs/superpowers/implemented/`. They record what
shipped and are frozen (spec §2 non-goals): no locator reaches them, no
migration rewrites them, and `fr validate artifacts` does not check them. A
migration that "fixes" history is a bug, not a courtesy.
