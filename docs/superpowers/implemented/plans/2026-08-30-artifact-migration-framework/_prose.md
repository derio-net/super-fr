# Artifact migration framework — obligatory, atomic, adoptive

Implements `docs/superpowers/specs/2026-08-30-artifact-migration-framework-design.md`,
which ships in the **same PR as 4.0.0** — the version bump is this framework's
first client rather than a one-off a later framework has to generalize.

## What this plan delivers

A node's installed `fr` changes whenever the plugin updates — mid-brainstorm,
mid-plan, mid-implementation. The artifacts on disk do not change with it. Five
pieces close that gap, and they only work as a set:

- **A stamp per artifact** (`fr.artifacts.registry`). Plans, journals, runs, the
  acceptance matrix and specs each declare the version they were written for.
  Chosen over a repo-level manifest because a manifest cannot describe a
  *half-migrated tree* — it lies silently when a migration dies partway.
- **Registered, chained, idempotent migrations** (`fr.artifacts.runner`). A
  `SchemaMigration` moves a shape and is guarded by the stamp; a `Repair` is
  predicate-guarded and version-independent. 4.0.0 registers exactly one, and it
  is a repair.
- **An obligatory trigger at CLI entry** (`fr.artifacts.trigger`). Interactive:
  migrate, commit, run the command the operator typed. Non-interactive: refuse
  loudly and write nothing.
- **A path-scoped atomic commit** (`fr.artifacts.commit`). `git add -- <exactly
  the rewritten paths>` and a `commit` carrying the same pathspec.
- **A structure validator per kind** (`fr.artifacts.structure`, `fr validate
  artifacts`), run by CI over this repo's own artifacts.

## Why the phases are ordered this way

The registry (1) and the runner (2) are foundational and nothing else compiles
without them. The trigger (3) lands before the commit (4) on purpose: a trigger
that migrates and does not commit is *safe*, while a commit path with no trigger
is dead code, so the intermediate state after 3 is one you could ship.

Phase 5 is the highest-value change in the plan and is deliberately not last.
`discover_plans` used to catch `PlanSchemaError`, log a warning and continue, so
under a version bump the bridge reported a healthy tick while dispatch had
silently stopped for every affected plan. Turning that into a loud refusal is
the one change an operator would notice on the day the upgrade lands.

Phases 6–8 are the parts the spec's own author kept discovering were required:
adoption (6) exists because `fr run start` would put the cursor at step one with
the spec and plan already written; the validator and the standing rule (7) are
what stop the next shape change from shipping without a migration; and Phase 8
is a correction — excluding archived artifacts from migration collided with the
`fr_version` gate, which turned all 38 archived plans into `state="Missing"`.

## Invariants the implementation must not break

- **The archive is frozen.** No locator reaches
  `docs/superpowers/implemented/**`, no migration rewrites it, and the validator
  does not check it. A migration that "fixes" history is a bug, not a courtesy.
- **The work list comes from the stamp, never from the walk.** `RunState`,
  `Matrix` and `PlanMeta` are all `extra="forbid"`, so "normalising on write"
  would make a live file unparseable — and for the matrix would take the
  `fr acceptance check` CI gate down with it.
- **Re-read immediately before writing.** An agent may be writing the same
  artifact; nothing decided at plan time is trusted at apply time.
- **One artifact's failure is one artifact's failure.** A raising migration
  leaves that file unmodified *and unstamped*, so the next run retries it, and
  the others still migrate.
- **The gate never commits where a commit would be wrong.** Not in CI, not on a
  pod, not on the default branch, not on a detached HEAD, not over an artifact
  the operator has open, and not when git could not be asked. Every one of those
  is a refusal that names the situation and the three commands.
- **A plan's stamp IS its existing `schema_version`.** `PlanMeta` forbids extra
  keys, so a second stamp field would make every stamped plan unparseable.

## Gotchas discovered while planning and in review

- **The 4.0.0 migration must be a repair, not a schema migration.** Bumping the
  plan stamp to 3 would declare a plan-folder shape change that did not happen,
  and drag `PlanMeta.schema_version` to `Literal[2, 3]` to encode the lie. The
  ceiling widening changes a *constraint*, not a shape.
- **Agent sessions, pods and CI always land non-interactive — by design.** The
  agent runs `fr migrate artifacts --yes` itself and continues. Do not "fix"
  this by loosening the predicate; what an agent must never be able to do is
  proceed over stale artifacts.
- **Moving a `current_version` makes this repo's own CI red until you migrate.**
  `acceptance-report.yml` runs `fr acceptance check` with `CI=true`, which the
  gate then refuses. Dogfood the migration in the same PR; do not hand-edit.
- **git's failure modes are not one failure mode.** "Not a git repository"
  means *proceed*; everything else — git absent, `safe.directory` dubious
  ownership, a bare repo, an unresolvable default branch — must mean *refuse*.
  Telling them apart requires parsing stderr, which requires forcing `LC_ALL=C`.
- **A duplicate YAML key is invisible to every schema check.** PyYAML keeps the
  last occurrence silently. It is why the validator strict-loads *every* YAML
  carrier, including each `NN.yaml`, where tick state lives.
- **A truncate-then-write is not atomic.** Every stamp writer goes through
  `write_text_atomic` (temp file in the same directory, then `os.replace`), or a
  crash mid-write leaves an artifact that reads as version 1 and wedges every
  later `fr` command.

## Verification

Every phase ends green on its own tests. `fr validate artifacts` runs over this
repo's own artifacts both in CI (`validate-artifacts`) and from the suite, so
the framework is exercised against real data rather than fixtures alone. The
spec's post-merge Test Plan is operator-driven and needs a node that really is
mid-upgrade; step 1 deliberately names a **non-exempt** command, because
`fr status` is one of the five read-only exemptions and can never demonstrate a
migration.
