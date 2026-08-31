# Journal: 2026-08-30-artifact-migration-framework

<!-- fr:journal kind=discovery scope=plan id=d-registry-shape created=2026-08-30T13:13:29 phase=1 -->
### d-registry-shape · discovery · Registry shape: ArtifactKind + four module-level helpers (Phases 2, 6, 7 build on it) (phase 1)

packages/fr/src/fr/artifacts/registry.py is the ONE enumeration of artifact
kinds. Public shape:

- `ARTIFACT_KINDS: Mapping[str, ArtifactKind]` — keyed by kind name; order is
  plan, journal, run, matrix, spec.
- `ArtifactKind` (frozen dataclass): `name`, `current_version: int`,
  `locator: str` (glob relative to repo root), `stamp: str` (human description
  of the carrier, for `--dry-run` output and validator messages),
  `read_version: Callable[[Path], int]`,
  `write_version: Callable[[Path, int], None]`. The callables are instance
  attributes, so `kind.read_version(path)` takes only the path — no self-binding.
- `artifact_kind(name) -> ArtifactKind`, raising `UnknownArtifactKindError`
  (subclass of `ArtifactError`; the `Error` suffix is ruff N818, not taste).
- `iter_artifact_paths(repo_root, name) -> Iterator[Path]`, sorted.
- `iter_all_artifacts(repo_root) -> Iterator[tuple[ArtifactKind, Path]]` — the
  walk Phase 2's runner and Phase 7's validator both want.
- `read_version(name, path)` / `write_version(name, path, version)` —
  module-level convenience over the kind's callables.
- `PRE_FRAMEWORK_VERSION = 1`, `ARCHIVE_SEGMENT = "implemented"`.

Current versions: plan=2, journal=1, run=1, matrix=1, spec=1. The four at 1
mean every existing file of those kinds is ALREADY current — 4.0.0 changes none
of their shapes — so Phase 2's runner will not rewrite them. That matters more
than it looks; see the `extra="forbid"` finding.

Extension point for Phase 7: add a `validate` callable field to `ArtifactKind`.
Nothing else needs to change, and nothing outside this module may grow a second
list of kinds (Phase 7's tripwire).

Archive exclusion is structural: every locator is rooted at a live directory,
so `docs/superpowers/implemented/**` is unreachable by construction.
`iter_artifact_paths` re-checks `ARCHIVE_SEGMENT` anyway, because a careless
future locator edit is exactly the mistake that would otherwise silently start
rewriting shipped history.

<!-- fr:journal kind=discovery scope=plan id=d-plan-stamp-is-schema-version created=2026-08-30T13:13:32 phase=1 -->
### d-plan-stamp-is-schema-version · discovery · Decision: the plan artifact-version IS _meta.yaml schema_version, not a new field (phase 1)

The brief asked whether the artifact-framework version for plans is the
existing `schema_version` or a separate field. Decision: the same field — and
it is FORCED, not merely convenient.

Why the same field:

1. `PlanMeta` is `ConfigDict(extra="forbid")`. Any new key in `_meta.yaml`
   makes every stamped plan fail to parse. Adding one would have required
   changing plan parse behaviour, which Phase 1 is explicitly barred from
   doing — and would break plan reads under any older fr.
2. `schema_version` already MEANS "the version this artifact was written for".
   It already owns a migration chain (`fr migrate v1-to-v2`). That is exactly
   the framework's definition of a stamp; a second field would be a duplicate
   version line over the same file, and the two would drift.
3. Spec 3.A's table says as much: `plans/*/_meta.yaml` -> `schema_version`,
   status "exists".

Its meaning is UNCHANGED: it is still the plan-folder schema version. The
framework reads it; it does not redefine it.

CONSEQUENCE PHASE 2 MUST DECIDE — the part a future migration depends on. The
two version lines are now welded together, so "bump the plan stamp" and
"declare a new plan-folder schema" are the same act. 4.0.0's registered
migration widens an `fr_version` CEILING; it does not change the folder shape.
So Phase 2 picks one of:

(a) Keep plan `current_version=2` and let the fr_version migration be a
    same-version repair whose idempotence comes from its own predicate ("does
    the ceiling already admit the installed major?"). Spec 3.B allows this —
    "migrations are written to be idempotent". Cost: the runner cannot drive it
    off a version transition, so it needs a notion of a migration that runs at
    a fixed version.

(b) Bump plan `current_version` to 3 and widen `PlanMeta.schema_version` to
    `Literal[2, 3]`. Cost: claims a plan-folder schema change that did not
    happen, and every consumer pinning `Literal[2]` (including older fr and
    `fr migrate v1-to-v2`) must be revisited.

I did NOT choose for Phase 2 — both are live and the tradeoff is the runner's,
not the registry's. The registry forecloses neither: `current_version` is a
single constant in one place, and the readers/writers deliberately operate on
raw YAML rather than through `PlanMeta`, so they can already read and write a
`schema_version` of 3 that pydantic would currently reject.

<!-- fr:journal kind=finding scope=plan id=f-journal-stamp-delimiter-collision created=2026-08-30T13:14:26 phase=1 state=fixed -->
### f-journal-stamp-delimiter-collision · finding [fixed] · The spec's literal journal stamp collides with the entry delimiter and would break every journal (phase 1)

Spec 3.A's table specifies the journal stamp literally as
`<!-- fr:journal schema=N -->`. That exact string is UNUSABLE: it collides with
the journal entry delimiter.

`fr/journal/model.py` sets `_DELIM_PREFIX = "<!-- fr:journal "` and
`parse_journal` treats any line starting with that prefix (and ending ` -->`)
as an ENTRY header, then requires `kind`, `scope`, `id`, `created`. A stamp
comment written per the spec matches the prefix, so `_parse_header` returns
`{"schema": "N"}` and parsing dies with
`JournalParseError: journal entry missing required field: 'kind'`.

Blast radius had it shipped: every stamped journal becomes unreadable, taking
`fr journal render` and `fr journal check` with it — including the fail-closed
open-findings gate, and including this very journal. I would have broken my own
phase's record.

Resolved in Phase 1 by moving the token one character out of the way:

    <!-- fr:journal-schema=N -->

Space -> hyphen. It keeps everything the spec actually wanted (a header comment
on line 1, invisible in rendered Markdown, machine-readable) and cannot be
confused with an entry delimiter, since the prefix requires a space after
`fr:journal`. Pinned by
`test_journal_stamp_is_not_mistaken_for_an_entry_delimiter`, which parses a
journal with a real entry before and after stamping and asserts the entry list
is unchanged.

The alternative — relaxing `parse_journal` to skip headers without a `kind` —
was rejected: Phase 1 must not change any existing artifact's parse behaviour,
and widening the delimiter grammar to tolerate a foreign header makes the
format looser forever to save one character.

Anyone updating spec 3.A's table should correct the string there too.

<!-- fr:journal kind=finding scope=plan id=f-closed-world-models-reject-a-stamp created=2026-08-30T13:14:30 phase=1 state=fixed -->
### f-closed-world-models-reject-a-stamp · finding [open] · run/matrix/plan models are extra=forbid: stamping a live file of those kinds breaks parsing (Phase 2 must not) (phase 1)

Three of the five kinds carry a closed-world pydantic model, so writing the new
stamp into a LIVE file of that kind makes it unparseable by the current fr:

- `RunState` (`fr/run/model.py`) — `extra="forbid"`; fields run, workflow,
  branch, started, cursor, steps. A `schema_version` key raises `RunStateError`.
- `Matrix` (`fr/acceptance/model.py`) — `extra="forbid"`; fields org, repo,
  rows. A `schema_version` key raises `AcceptanceError`, which would take
  `fr acceptance check` (a CI gate) down.
- `PlanMeta` (`fr/types.py`) — `extra="forbid"` AND
  `schema_version: Literal[2]`. Writing 2 is fine; writing 3 raises.

Journals and specs are safe: `parse_journal` ignores non-delimiter lines, and
`parse_spec` is regex-based over `# Title` / `## Implementation Plans`, so YAML
front matter passes through untouched (both pinned by tests).

Phase 1 does NOT stamp any live file, so nothing is broken today. The state is
open because Phase 2 is the first code that can write to a live artifact, and
it MUST NOT stamp a run or the matrix before those models accept the field.

Why this is not urgent, and why that is by design: journal, run, matrix and
spec are all registered at `current_version = 1`, and an absent stamp already
READS as 1. Every existing file of those kinds is therefore already current, so
a correct runner has no reason to write to them at all. The models only need
widening when a kind's version actually moves past 1 — at which point the
same PR must add `schema_version: int = 1` (optional, defaulted) to the model,
per the standing obligation Phase 7 writes into
`.claude/rules/artifact-versioning.md`.

RESOLVED in Phase 2 (state flipped by hand — `fr journal add` has no
open->fixed transition). The runner derives its work list from
`read_version(path) < kind.current_version`, never from the walk, and no
schema migration is registered for any version-1 kind. See
`f-closed-world-stamp-closed-by-construction` for the three tests that pin it.

Concrete instruction for Phase 2: the runner must derive its work list from
`read_version(kind, path) < kind.current_version`. If it instead stamps
everything it walks ("normalise on write"), it will brick `fr acceptance check`
and every run file on the first invocation.

<!-- fr:journal kind=discovery scope=plan id=d-migration-blast-radius-is-one-live-plan created=2026-08-30T13:14:33 phase=1 -->
### d-migration-blast-radius-is-one-live-plan · discovery · The fr_version migration touches ONE live plan here, not 39 — the other 38 are archived (phase 1)

Spec 1 and the Phase 2 task text both say "39 of 40 plans in this repo carry
`>=3.x,<4.0.0`", implying the 4.0.0 fr_version-widening migration has a large
blast radius. Measured on this branch through the registry's own locators:

- LIVE plans (`docs/superpowers/plans/*/_meta.yaml`): 3.
    - `2026-07-09-multi-backend-git-host-adapters` — `>=3.0.0,<4.0.0`  <- the
      only one the migration touches
    - `2026-08-14-workflow-shapes-and-workitem-dispatch` — `>=3.19.0,<5.0.0`
    - `2026-08-30-artifact-migration-framework` — `>=4.0.0,<5.0.0`
- ARCHIVED plans (`docs/superpowers/implemented/plans/*/_meta.yaml`): 71, of
  which 38 carry a `<4.0.0` ceiling (22 at `>=3.0.0`, 14 at `>=3.7.0`, one each
  at `>=3.16.0` / `>=3.17.0`) and 33 carry no `fr_version` at all.

38 archived + 1 live = the "39". The framework excludes every archived one by
design (spec 2 non-goals: rewriting them would falsify history), so the real
blast radius in this repo is exactly ONE plan.

Implications for Phase 2, none of which invalidate the phase:

- The migration is still correct and still worth shipping — it is the proof
  case for the framework, and a consumer repo mid-upgrade will have many live
  plans, not one.
- Do not write a test that asserts "39 plans get migrated" against this repo;
  it would be measuring the archive, which the runner must never touch. A test
  like that passing would be evidence of a BUG.
- The 33 archived plans with no `fr_version` are a useful reminder that
  "no ceiling" is a real case; the Phase 2 task text already calls for it
  ("a plan with no fr_version is untouched").
- Verified empirically: the registry's readers ran clean over all 22 live
  artifacts in this repo (3 plans at version 2; 11 journals, 1 matrix and 7
  specs all reading 1 from an absent stamp; 0 runs — no runs/ dir yet), and the
  writers round-tripped on temp copies of every one of them with no line
  removed except a stamp being replaced in place.

<!-- fr:journal kind=discovery scope=plan id=d-migration-runner-api created=2026-08-30T13:42:50 phase=2 -->
### d-migration-runner-api · discovery · Runner registration API: MIGRATIONS, SchemaMigration, Repair, run_migrations (Phases 3, 4, 7 build on it) (phase 2)

Phases 3 (trigger), 4 (atomic commit) and 7 (validator) all call into
`fr.artifacts.runner`. Its public shape, now fixed:

REGISTERING
- `MIGRATIONS: MigrationRegistry` — the ONE registry of migrations, shipped in
  `fr/artifacts/runner.py`. `fr/artifacts/__init__.py` imports
  `fr.artifacts.fr_version` last, purely for its `MIGRATIONS.register(...)`
  side effect: a migration nobody imports is a migration that silently never
  runs, so registration rides on the package import, not on a caller
  remembering. A new built-in migration adds a module and one import line.
- `SchemaMigration(kind, from_version, to_version, fn, description="")` —
  stamp-guarded. `fn(path) -> None` rewrites the BODY only; the runner writes
  the new stamp itself, after `fn` returns. `__post_init__` rejects a
  non-forward transition.
- `Repair(kind, name, applies, fn, description="")` — see the repairs entry.
- `registry.register(m)` raises `DuplicateMigrationError` (two migrations from
  the same version, or two repairs with one name) and `UnknownArtifactKindError`
  at import time for an unregistered kind.
- `MigrationRegistry(kinds=...)` carries the artifact kinds it operates over,
  defaulting to `ARTIFACT_KINDS`. That is the ONLY injection point the runner
  has, and it exists so tests can use synthetic kinds without any second
  enumeration of kinds appearing outside `registry.py` (Phase 7's tripwire
  stays satisfiable).

RUNNING
- `plan_migrations(repo_root, *, registry=None) -> tuple[PlannedAction, ...]` —
  read-only.
- `is_stale(repo_root, *, registry=None) -> bool` — short-circuits on the first
  stale artifact. Built for PHASE 3: the callback runs before every command and
  must not walk the tree when the answer is available early.
- `run_migrations(repo_root, *, dry_run=True, registry=None) -> MigrationReport`
  — DRY-RUN BY DEFAULT. Plans the whole tree, then applies, so a chain gap
  anywhere raises before anything anywhere is written.
- `MigrationReport(dry_run, applied, skipped, failed)` with
  `.changed_paths -> tuple[Path, ...]` (ordered, deduplicated) and `.ok`.
  PHASE 4 stages exactly `report.changed_paths` — `git add -- <paths>`, never
  `-A` — and the per-action `summary` / `from_version` / `to_version` /
  `repair` fields are what its generated commit message should name.
- `PlannedAction(kind, path, summary, from_version, to_version, repair)`;
  `from_version is None` <=> it is a repair. `FailedAction(kind, path, summary,
  error)`.

Registry addition: `iter_paths_of(repo_root, kind)` in `registry.py`, taking
the kind rather than its name, with `iter_artifact_paths` now delegating. The
archive exclusion stays in exactly one function.

TWO THINGS PHASE 3 MUST HANDLE
1. `plan_migrations` / `is_stale` / `run_migrations` RAISE `MigrationChainError`
   when an artifact sits at a version no registered migration moves. That is
   deliberate (the phase contract: a gap raises, never skips) but it means the
   CLI-entry callback must catch it and refuse loudly rather than let a
   traceback escape from `fr --help`. It cannot currently fire in practice —
   `PlanMeta.schema_version` is a required `Literal[2]`, so every parseable
   plan is at 2 and every other kind is at 1 — but an unstamped `_meta.yaml`
   would trigger it.
2. A per-artifact failure is NOT an exception: it lands in `report.failed` and
   the other artifacts still migrate. Only the CLI turns that into exit 2.

<!-- fr:journal kind=discovery scope=plan id=d-repairs-vs-schema-migrations created=2026-08-30T13:43:24 phase=2 -->
### d-repairs-vs-schema-migrations · discovery · Repairs vs schema migrations: stamp-guarded chain vs predicate-guarded fix, and why 4.0.0's is a repair (phase 2)

Spec §3.B names two shapes; Phase 1 left the choice between them open (see
`d-plan-stamp-is-schema-version`). Both are now built, and the difference in
code is small but load-bearing.

SCHEMA MIGRATION — guarded by the stamp
- `SchemaMigration(kind, from_version, to_version, fn)`.
- Selected when `kind.read_version(path) < kind.current_version`; the runner
  resolves a CHAIN (1->2, 2->3, ...) up to `current_version`, and a missing
  step raises `MigrationChainError` instead of silently skipping.
- `fn(path)` rewrites the body ONLY. The runner writes the stamp itself, and
  only after `fn` returns — so a migration that dies mid-write leaves the
  artifact stale and the next run retries it, rather than marking a
  half-migrated file as current forever (pinned by
  `test_a_migration_that_raises_mid_write_is_not_stamped`).
- Idempotence is free: the new stamp makes the artifact ineligible.

REPAIR — guarded by its own predicate
- `Repair(kind, name, applies, fn)`, version-INDEPENDENT. It never touches the
  stamp.
- Selected when `applies(path)` is True. Idempotence must be BUILT: applying
  `fn` has to make `applies` False. That is the whole contract, and it is what
  the acceptance row `migration-is-idempotent` tests from the repair side.
- A predicate that RAISES is a per-artifact failure, not a crash: it is
  reported, that artifact is left unmodified, and every other artifact still
  migrates. This is how "a malformed constraint is reported, not rewritten"
  falls out of the framework rather than being special-cased in the migration.

ORDERING: all schema migrations for an artifact run before any repair on it. A
repair inspects the artifact's CURRENT shape, so the shape must be current
first (`test_schema_migrations_run_before_repairs_on_the_same_artifact`).

RE-READING (spec §4, an agent writing concurrently): the plan pass decides
nothing that the apply pass trusts. `_apply_to_one` re-reads the stamp before
every schema step and re-evaluates every predicate before applying it, and
every `fn` reads the file itself — it is handed a `Path`, never a parsed
document. An action that has become unnecessary in between is recorded in
`report.skipped`, not silently dropped.

WHY 4.0.0's ONE MIGRATION IS A REPAIR. Widening a plan's `fr_version` ceiling
(`<4.0.0` -> `<5.0.0`) changes a constraint, not a shape. A plan's artifact
stamp IS its `_meta.yaml schema_version`, so expressing the widening as a
schema migration would bump that to 3, declare a plan-folder shape change that
did not happen, and force `PlanMeta.schema_version` to `Literal[2, 3]` to
encode the lie. `test_the_repair_does_not_move_the_plan_stamp` asserts the
migrated file still validates against `Literal[2]`.

Implementation notes on the repair itself (`fr/artifacts/fr_version.py`):
- `widen_ceiling(constraint, installed) -> str | None` is pure and separately
  tested. `None` means "leave it alone", covering three distinct cases: already
  admits us, no ceiling at all, and — the subtle one — excluded by the FLOOR
  (`>=5.0.0,<6.0.0` under 4.0.0), where the plan wants a NEWER fr and widening
  would not admit us anyway. Downgrades are a spec §2 non-goal.
- It splits the constraint on commas by hand rather than iterating a
  `SpecifierSet`, which iterates a frozenset and would silently reorder the
  operator's text.
- The write is line surgery preserving the quoting style, in the same spirit as
  the registry's stamp writers: no document round-trips through
  `yaml.safe_dump`. If the value is not on a rewritable line, it refuses and
  tells the operator what to write instead.

<!-- fr:journal kind=finding scope=plan id=f-closed-world-stamp-closed-by-construction created=2026-08-30T13:43:52 phase=2 state=fixed -->
### f-closed-world-stamp-closed-by-construction · finding [fixed] · Closed: the runner cannot stamp a closed-world artifact — its work list is the stamp, never the walk (phase 2)

RESOLVES `f-closed-world-models-reject-a-stamp` (Phase 1, state open). A new
entry rather than an edit: `fr journal add` silently no-ops on an existing
`--id`, so re-adding the finding as `fixed` would have changed nothing. The
original entry stays `open` in the file; this is its disposition, and the plan
journal should be read as: finding raised in Phase 1, closed here.

WHAT THE FINDING SAID. `RunState`, `Matrix` and `PlanMeta` are all
`extra="forbid"`, so writing a `schema_version` key into a LIVE run, into
`matrix.yaml`, or bumping a plan's stamp past 2 makes the file unparseable by
the current fr — and for the matrix that would take the `fr acceptance check`
CI gate down. Phase 1 could only assert that a correct Phase 2 would never do
it. Closing it means proving it.

HOW IT IS CLOSED — three tests, not an assertion.

1. `test_the_shipped_runner_never_writes_to_a_closed_world_artifact` seeds a
   temp repo with a real run yaml, a real `matrix.yaml`, a journal, a spec and
   a plan, freezes each file's bytes AND mtime, runs the SHIPPED registry with
   `dry_run=False`, and asserts every one of them is untouched — then parses
   the run through `parse_run_state` and the matrix through `load_matrix` to
   prove the exact failure mode the finding named cannot have happened.
2. `test_the_shipped_registry_registers_nothing_for_the_version_one_kinds`
   asserts `MIGRATIONS.schema_migrations(k) == ()` for journal, run, matrix and
   spec. This is the structural half: those kinds are at `current_version=1`
   and an absent stamp already READS as 1, so no artifact of those kinds is
   stale, so the runner has no reason to write to them. A future PR that
   registers a schema migration for one of them trips this test and is told,
   in the failure message, that the model must accept `schema_version` first.
3. `test_this_repos_own_artifacts_plan_only_safe_actions` runs
   `plan_migrations` over super-fr itself and asserts every planned action is a
   plan-kind REPAIR and none is under `implemented/`. Deliberately NOT a count:
   38 of the 39 `<4.0.0` ceilings here are archived, so a count would be
   measuring the archive the runner must never touch (per
   `d-migration-blast-radius-is-one-live-plan`).

THE MECHANISM THAT MAKES IT STRUCTURAL, not vigilance. The runner's work list
comes only from `read_version(path) < kind.current_version` (schema
migrations) or a repair's predicate. There is no "normalise on write" path —
the runner never stamps an artifact it did not migrate, and a repair never
stamps at all. So the closed-world models are safe by construction, not by the
author remembering.

Verified live: `fr migrate artifacts` (dry-run) against this repo reports
exactly one action —
`docs/superpowers/plans/2026-07-09-multi-backend-git-host-adapters/_meta.yaml`,
the ceiling widening — which is precisely the blast radius Phase 1 measured.
The standing obligation still stands: the first PR that moves any kind's
`current_version` past 1 must, in the SAME PR, add an optional defaulted
`schema_version: int = 1` to that kind's model. Phase 7 writes that into
`.claude/rules/artifact-versioning.md`.

<!-- fr:journal kind=discovery scope=plan id=d-interactive-predicate-and-exemptions created=2026-08-30T14:13:54 phase=3 -->
### d-interactive-predicate-and-exemptions · discovery · Context detection is CI-unset AND both streams a TTY; the exemption list is exactly four things (phase 3)

<!-- fr:journal kind=discovery scope=plan id=d-path-scoped-commit-and-message created=2026-08-30T14:25:30 phase=4 -->
### d-path-scoped-commit-and-message · discovery · Path-scoping the commit, not just the staging: git commit needs the pathspec too, plus the generated message format (phase 4)

`fr.artifacts.commit.commit_migration(repo_root, report, *, fr_version=None)
-> CommitOutcome(committed, reason, paths, message)`. It never raises for an
expected outcome; "not a git repo" and "nothing to commit" are answers.

THE TWO GIT MISTAKES IT IS SHAPED TO AVOID. Both pass a clean-tree test, which
is exactly why the spec spells this out and why every fixture here starts dirty.

1. `git add -A` sweeps the operator's unrelated MODIFIED files into the commit.
2. A plain `git commit -m` records the WHOLE INDEX, so it sweeps in a file the
   operator had already STAGED — even when the staging was path-scoped. This is
   the one that is easy to miss: scoping the `add` is not enough, the COMMIT
   has to carry the pathspec too.

So the sequence is:

    git add -- <report.changed_paths>
    git diff --cached --name-only HEAD -- <paths>     # anything to record?
    git commit -m <generated> -- <paths>

`add` first, so an artifact a migration CREATED is tracked and can be named by
the pathspec. The pathspec on `commit` makes git build the tree from HEAD plus
those paths and leave the rest of the index alone — the operator's staged file
stays staged, and their modified file stays modified and uncommitted.

The emptiness check is against HEAD (`diff --cached --name-only HEAD`), not
against the index, so the answer does not change when the operator has staged
something unrelated. When it comes back empty we make NO COMMIT AT ALL — not
"an empty commit avoided", but the thing that stops an unrelated staged file
being committed under a migration message.

VERIFIED BY MUTATION, not by reading. Swapping in `git add -A` fails
`test_an_unrelated_modified_file_stays_modified_and_uncommitted`; dropping the
pathspec from the commit fails both
`test_an_unrelated_staged_file_is_not_swept_in` and
`test_the_commit_contains_only_the_paths_the_migration_rewrote`. Both mutations
were applied and reverted.

COMMIT MESSAGE FORMAT (`migration_commit_message(report, *, fr_version)`),
grouped by kind and transition rather than listing files — `git show --stat`
already lists them, and a consumer repo mid-upgrade migrates dozens of plans at
once. Groups keep first-seen order, so a deterministic report gives a
deterministic message.

    chore(fr): migrate 3 artifacts to fr 4.0.0

    - journal: schema 1 -> 2 (2 files)
    - plan: repair widen-fr-version-ceiling (1 file)

    Migrated automatically at fr CLI entry: the installed fr changed under
    artifacts written for an older one (artifact migration framework, spec
    2026-08-30 §3.C/§3.D). Only the rewritten artifact paths are in this
    commit; unrelated working-tree and staged changes were left alone.

Subject is singular for one artifact ("1 artifact"), plural otherwise; the
count is `len(report.changed_paths)` (deduped paths), while the per-group count
is that group's distinct paths.

WHAT IT REFUSES RATHER THAN HANDLES, each returning `committed=False` with a
reason the gate prints:

- not a git repository -> migrate without committing, no crash (spec §3.D);
- a repository with NO COMMITS YET -> a pathspec commit has no HEAD to build
  its tree from, and falling back to a whole-index commit would sweep in
  whatever was staged. An empty repo is not the case this feature exists for;
- a changed path OUTSIDE the git toplevel -> refuse. It cannot happen through
  the registry's locators, but this writes to git history from a callback that
  fires before an unrelated command, so the precondition is asserted rather
  than assumed to have been checked upstream;
- `git add` or `git commit` failing (no user.email, hooks, a lock) -> reported,
  and the CALLER STILL RUNS THE COMMAND. The files are migrated; refusing there
  would strand the operator with a migrated tree and a command that never works.

<!-- fr:journal kind=finding scope=plan id=f-live-gate-refused-ci-and-the-suite created=2026-08-30T14:26:03 phase=3 state=fixed -->
### f-live-gate-refused-ci-and-the-suite · finding [fixed] · Switching the gate on refused this repo CI and 108 of its own tests; both fixed, and agents always land on the non-interactive side (phase 3)

Turning the gate on made the repo's own CI red, and made every agent-driven
`fr` command refuse. Both were found by running the tooling, not by reasoning.

WHAT HAPPENED. The moment `fr.cli`'s callback went live, my own
`fr isolation exec -- uv run fr acceptance report` refused:

    fr: artifacts in /workspaces/... were written for a different fr and must be
    migrated before this command can run.
    This context is non-interactive (CI is set, or there is no TTY) ...

That is the feature working. But it has two consequences worth writing down.

1. CI WOULD HAVE GONE RED, and not in the phase that caused it.
   `.github/workflows/acceptance-report.yml` does `uv tool install ./packages/fr`
   (super-fr self-hosts, deliberately) and then `fr acceptance check`, with
   `CI=true`. This repo carried exactly one live stale artifact —
   `docs/superpowers/plans/2026-07-09-multi-backend-git-host-adapters/_meta.yaml`
   at `fr_version: '>=3.0.0,<4.0.0'` — so that step would have exited 2 on every
   PR. Note the plan was ALREADY unparseable under 4.0.0 (`PlanSchemaError` at
   `parser.py`); the gate did not break it, it stopped the breakage being quiet.

   FIXED by dogfooding the framework rather than hand-editing: ran
   `fr migrate artifacts --yes` from this branch's build. One line,
   `<4.0.0` -> `<5.0.0`, which is precisely the blast radius Phase 1 measured
   and Phase 2 predicted. The 38 archived plans with the same ceiling are
   untouched, as they must be. NOTE FOR THE ORCHESTRATOR: this is the one file
   in the diff that is not Phase 3/4 code, and it is uncommitted like everything
   else; it is here because leaving it would ship a repo whose own CI its own
   `fr` refuses.

2. THE WHOLE TEST SUITE REFUSED — 108 failures, none of them about migration.
   In-process `CliRunner` tests and `fr` subprocesses inherit the PYTEST
   process's cwd, so the gate resolved super-fr's own repo root and refused
   ~100 unrelated CLI tests. Left alone, the suite's result would depend on the
   repo's own artifact state rather than on the code under test — and it would
   fail confusingly, in files that have nothing to do with this feature, the
   next time anyone adds a plan with an old ceiling.

   FIXED with an autouse fixture in `tests/conftest.py` setting
   `FR_SKIP_MIGRATION=1` for the whole suite — the mechanism's own documented
   bypass, not a hole cut for tests. `tests/unit/test_migration_trigger.py` and
   `test_migration_commit.py` `monkeypatch.delenv` it for the invocations that
   must actually see the gate. Note `CliRunner(env=...)` UPDATES `os.environ`
   rather than replacing it, so omitting the variable from that dict is not
   enough; it has to be deleted.

3. AGENTS AND PODS ALWAYS LAND ON THE NON-INTERACTIVE SIDE. `fr isolation exec`,
   `claude`'s bash tool, hermes pods and CI all lack a TTY, so while any live
   artifact is stale EVERY fr command in those contexts refuses. That is spec
   §3.C as designed, and it is not a deadlock: `fr migrate artifacts --yes` is
   itself exempt from the gate and needs no TTY, so an agent that hits the
   refusal can unblock itself with exactly the command the refusal names. What
   an agent cannot do is silently proceed over stale artifacts — which is the
   point.

CONSEQUENCE FOR PHASES 5-8 AND FOR ANY FUTURE STAMP BUMP: the first PR that
moves a kind's `current_version` makes every live artifact of that kind stale in
this repo, which turns CI red until the same PR runs `fr migrate artifacts --yes`
and commits the result. That obligation belongs in Phase 7's
`.claude/rules/artifact-versioning.md` alongside the stamp/migration/validator
trio it already names.

<!-- fr:journal kind=discovery scope=plan id=d-p5-loud-refusal created=2026-08-30T14:41:41 phase=5 -->
### d-p5-loud-refusal · discovery · Phase 5: discover_plans refuses stale plans loudly, unconditionally non-interactive (phase 5)

discover_plans's PlanSchemaError catch (fr_dispatch/__init__.py:145-149) was
the swallow: it caught EVERY PlanSchemaError from parse() — both genuinely
malformed plans and (post-4.0.0) plans whose fr_version ceiling excludes the
installed major — logged a WARNING, and silently dropped the plan from
discovery. Fixed uniformly rather than distinguishing "stale" from
"malformed": both now log ERROR, push metrics.push_failure_total(reason=
"stale_artifact"), and append a message to a new `failures: list[str] | None`
outparam (mirroring tick()'s own `failures` accumulator pattern) so the
caller can fold the count into its own error total. discover_plans gained
`metrics: MetricsPusher | None = None` (defaults to NullMetrics(), same
default-injection pattern as tick's `metrics=`).

Predicate decision: did NOT call fr.artifacts.trigger.is_interactive(). The
daemon never goes through fr's CLI entry point (`ensure_artifacts_current`)
at all — bridge_cli.py calls fr_dispatch.discover_plans/tick as library
functions, not `fr <command>` as a subprocess — so there is no argv/env/TTY
context here to test in the first place. Calling is_interactive() would
answer a question that doesn't apply to this call site (and would coincidentally
always return False since stdin/stdout in caplog-captured pytest runs are
non-tty too, masking the difference between "correctly detected non-interactive"
and "the predicate literally cannot be reached here"). Refusing
unconditionally is the correct read of "reuse the predicate, don't grow a
second answer": the ANSWER (non-interactive => refuse, never migrate, never
commit) is reused; the mechanism that computes it for CLI entry is a
different question this call site doesn't need to ask.

bridge_cli.py diff: one new `discover_failures: list[str] = []` per repo
iteration, `discover_plans(r, gh, metrics=_metrics, failures=discover_failures)`
in the `_fetch_plans` closure, and `total_errors += len(discover_failures)`
after the `_gh_rate_limit_guard` call. flock, the bridge-owned checkout sync
(_pull_managed_repo/_ensure_bridge_checkout), the metrics wire format/reason
aliases, and _seen_plans.json/_done_closed.json are untouched.

Four test-double call sites needed a signature update (not a behavior change)
to tolerate the new kwargs: test_bridge_cli.py's spy_discover + two lambdas,
test_bridge_resilience.py:462, test_bridge_shape_binding.py:105 — all
`lambda repo, gh: ...` -> `lambda repo, gh, **kw: ...`.

<!-- fr:journal kind=discovery scope=plan id=d-p8-enforce-fr-version created=2026-08-30T14:56:54 phase=8 -->
### d-p8-enforce-fr-version · discovery · Phase 8: enforce_fr_version scopes the gate to execution, spec.compute_status is the one opt-out (phase 8)

fr.parser.parse gained `enforce_fr_version: bool = True` (keyword-only,
defaults on -- safety stays default, every existing caller unchanged). The
guarded block is exactly the pre-existing fr_version SpecifierSet check
(parser.py, meta.fr_version ceiling vs INSTALLED_FR_VERSION) -- the
schema_version: Literal[2] pydantic validation of _meta.yaml itself is NOT
gated by this flag (that is plan-folder SHAPE validation, unrelated to the
version-ceiling constraint; an archived plan is still a real v2 plan folder,
just possibly pinned to an fr_version range that predates the installed
major).

Only one call site passes False: fr.spec.compute_status (spec.py:370, the
per-plan-ref loop that builds SpecStatus for `fr spec status`). This is
because spec §2 declares archived plans a non-goal for migration -- they
record what shipped -- so parse-time enforcement of a stale ceiling there
was pure noise (PlanSchemaError -> state="Missing" for every archived plan
whose fr_version excludes 4.0.0, which is all 38 archived plans in this
repo once any of them carry a ceiling narrower than the current major).

Execution call sites audited and confirmed to still call parse()/pass no
enforce_fr_version kwarg (default True holds):
- fr/commands/pickup_cmd.py:29 (`fr pickup`) -- new unit test
  test_pickup_still_enforces_fr_version (test_v2_pickup.py).
- fr/commands/common.py build_plan_report (`fr status` AND `fr apply --yes`
  share this one read->observe->render->diff path by design, per
  test_status_cmd.py's own docstring: "the two can't drift") -- new unit
  test test_build_plan_report_still_enforces_fr_version (test_status_cmd.py).
  Confirms `fr status` (single-plan) is NOT the "read-only status path"
  the phase brief means -- that is fr.spec.compute_status (spec-level
  aggregate), a different function entirely; build_plan_report stays
  execution-scoped because it is apply's own read path.
- fr_dispatch/__init__.py discover_plans (the bridge daemon, Phase 5's own
  surface) -- new unit test test_discover_plans_still_enforces_fr_version
  (test_vk_bridge_discover.py), using an fr_version-excluded fixture
  (not the generic schema_version:99 fixture Phase 5's test used) to prove
  this specific gate, not just PlanSchemaError in general, stays enforced
  here.
- fr/plan_ops.py, fr/archive.py, fr/migrate.py, fr/parser.py's own
  parse_strict -- all call parse(plan_dir) with no enforce_fr_version
  kwarg; left untouched, not separately unit-tested (out of the phase's
  named execution-path list, and each is a mutation path where enforcement
  was never in question).

Fixture discipline: both new tests build a plan with `fr_version:
">=9.0.0,<10.0.0"` and monkeypatch `fr.parser.INSTALLED_FR_VERSION` to
"3.0.0" (excluded) -- same pattern the pre-existing
test_parse_enforces_fr_version already used, reused rather than
reinvented. Confirmed RED before the parser.py/spec.py edit (git stash) --
both new parser-level and spec-level tests failed exactly as predicted
(TypeError: unexpected keyword argument; state == "Missing" with a "parse
error" note) before the fix, and pass after.

<!-- fr:journal kind=discovery scope=plan id=d-p6-cursor-inference created=2026-08-31T09:29:11 phase=6 -->
### d-p6-cursor-inference · discovery · How the adopted cursor is inferred: the shape, the one rule, PR detection, and the three states the table omits (phase 6)

`fr run adopt <target>` (fr/run/adopt.py) reconstructs a cursor from artifacts
already on disk. Five inputs, one rule, and three states the spec's table does
not name.

THE TARGET. A plan folder normally; a SPEC markdown file is also accepted,
because the table's first row ("spec only") is by definition a state in which
no plan dir exists to point at — refusing it would make the row unreachable
through the command that implements the table. Anything else is a loud refusal
naming both accepted forms.

THE SHAPE. Default `fr-goal`, resolved through `resolve_workflow` (repo >
shipped), overridable with `--workflow`. Deliberately NOT
`workflow_for_plan`: that answers the granularity a plan DISPATCHES at and
defaults to the `unit: phase` sub-shape whose only step is `implement`, so a
cursor over it could never land on `plan`, `review` or `deliver`. A shape
missing the inferred step is refused loudly, naming the step, the shape's
steps and its `unit` — never silently retargeted.

THE CURSOR RULE, one line: the cursor is the inferred step; every step BEFORE
it is `done`, the cursor and everything after it are `pending`. Marking the
cursor `running` would claim a dispatch that never happened (and `fr run
advance` treats `running` as already-dispatched). Nothing here reimplements a
transition — `_complete_step` in run_cmd stays the only implementation of the
done/failed cursor asymmetry, and an adopted run advances exactly like a
started one. `derive_run_id` is imported (lazily, to avoid the cycle
run_cmd->adopt->run_cmd) rather than re-derived, so an adopted run id is
byte-identical to a started one's.

WHAT IS OBSERVED, per row:
- phases: `fr.render.plan_locally_complete` per phase — the SAME offline
  predicate the archive gate, the `fr status` sweep and the unarchived-plans
  tripwire use. No third definition of "done".
- spec: `plan.spec_path` (already lifecycle-resolved by `parse`), so an
  archived spec resolves to its current location.
- plan: the repo-relative plan dir.

HOW "PR OPEN" IS DETECTED. Only when a PR URL is NAMED (`--pr <url>`), and
resolved through `GhClient.pr_status_by_url` via `hostclient.client_for` —
the protocol method that exists for exactly this question and is implemented
for GitHub, GitLab and Gitea. So adoption inherits multi-backend support
instead of shelling out to `gh pr list`, which fr-vk was deliberately moved
AWAY from (2026-07-09 spec §6).

Rejected: discovering the PR by branch. No adapter in the protocol answers
"open PRs for head branch", adding one means three adapters plus fakes, and
the guess has a wrong answer (a phase PR) that looks right.

WHEN IT CANNOT BE DETERMINED OFFLINE: `pr_status_by_url` already fails soft
(`None` on any not-found/error condition) and `default_pr_state` extends that
to transport failures, so "cannot tell" is a first-class answer distinct from
"no PR". It lands the cursor on `review` — the last row observable WITHOUT the
network — and appends a note explaining why, printed by the CLI but NOT stored
in the run file (a run file records where the cursor is, not why). Notes travel
back through a `notes: list[str]` outparam, the same shape `discover_plans`
uses for `failures`. Failing soft DOWNWARD matters: `review` under-claims by
one step and `fr run resolve --step review --state done` fixes it in one
command, while a wrong `deliver` claims the review happened.

THREE STATES THE TABLE DOES NOT COVER, decided here:
1. A plan folder with NO phase files (a skeleton) is IN FLIGHT -> `implement`.
   `all([])` is vacuously true, so the naive reading calls an empty plan
   finished; `completed_unarchived_plans` already guards the same trap with
   `plan.phases and all(...)` and this agrees with it.
2. An open PR over a plan whose phases are NOT all complete does NOT reach
   `deliver`. The last two rows are one observation refined ("all phases
   complete" PLUS "and there is a PR"), so an open PR over unfinished work is
   a phase PR, not the delivery; landing on `deliver` would declare the
   implementation over.
3. A PR that resolves to MERGED/CLOSED is not an open one -> `review`, with a
   note naming the observed state.

<!-- fr:journal kind=discovery scope=plan id=d-p6-what-an-adopted-run-records created=2026-08-31T09:29:49 phase=6 -->
### d-p6-what-an-adopted-run-records · discovery · What an adopted run records: emitted spec/plan for archival, a new StepRecord.items for per-phase state, and why that needs no version bump (phase 6)

An adopted run file is a normal run file — same `fr.run.model` types, same
`save_run_state`, same path (`docs/superpowers/runs/<run-id>.yaml`). What it
carries, and why each piece is load-bearing:

EMITTED SPEC AND PLAN, attached to the step the SHAPE says emits them (for the
shipped fr-goal manifest: `spec` on `brainstorm`, `plan` on `plan`, `pr` on
`deliver`). This is what makes archival work: `fr.archive` locates a plan's run
by scanning every step record for `emitted.plan == <plan dir>` (2026-08-14 spec
§4.B), never by slug, because a run id is `<date>-<flattened-branch>` and a plan
slug is authored independently. A run adopted without those recordings would be
a run that never archives with its plan.

FALLBACK, and it is deliberate: if the shape has no step declaring
`emits: [plan]`, the artifact is recorded on the CURSOR step instead of being
dropped. Archival depends on the value existing SOMEWHERE in the file; losing
it to a shape's authoring choice would strand the plan. Same for `spec`/`pr`.

`pr` IS RECORDED ONLY WHEN OBSERVED OPEN. A named-but-unresolvable PR leaves
`emitted` unset — an artifact recording is a claim, and "the operator typed a
URL" is not evidence the artifact exists.

PER-PHASE STATE needed a field. `StepRecord` gained `items: dict[str, str] |
None` — additive, optional, and exactly what spec §4.B's own illustration of
run state shows (`implement: {state: running, items: {".../phase/1": done}}`);
Phase 7 built the model without it because nothing wrote one yet. Adoption is
the first writer: a half-implemented plan whose cursor says `implement` and
nothing else has lost everything that made the adoption worth having. Keys are
`phase/<n>`, the plan-relative TAIL of the §4.D identity grammar, not the full
`<repo>/<spec>/<plan>/phase/<n>` item id — composing that is
`fr_dispatch.work_item`'s job and `fr` may not import it
(`tests/unit/test_import_direction.py`); the run file already records WHICH
plan in `emitted.plan`, so the tail is unambiguous within the run. `items` is
attached to the step with `for_each: phase` (again shape-driven), falling back
to the cursor step.

NO ARTIFACT-VERSION BUMP FOLLOWS, and that needed checking rather than
assuming. The `run` kind sits at `current_version=1` in
`fr.artifacts.registry`, and `RunState`/`StepRecord` are `extra="forbid"` — the
exact hazard `f-closed-world-models-reject-a-stamp` raised in Phase 1. Adding a
field is safe here only because `docs/superpowers/runs/` is NEW in 4.0.0:
`packages/fr/src/fr/run/model.py` does not exist on origin/main and no released
fr has ever read a run file, so there is no older reader for a file carrying
`items` to break. Old files (none in the wild, and none in this repo) still
parse — the field is optional. Had runs shipped in 3.x this would have required
`current_version=2`, a schema migration, and `schema_version` on the model
first.

WHERE THE FILE IS WRITTEN: `repo_root`, directly — NOT through
`ensure_run_workspace`. `fr run start` enters isolation because a run being
BORN has no workspace yet; an adopted run describes work already under way, so
its workspace is wherever those artifacts are. Provisioning a worktree (or
starting a container) as a side effect of adopting would be the reverse of the
§4.B rule it superficially resembles: the run belongs with its plan, and the
plan is here. Adoption refuses rather than overwrite when a run id already
exists.

<!-- fr:journal kind=decision scope=plan id=d-p6-offer-reports-command-writes created=2026-08-31T09:30:20 phase=6 -->
### d-p6-offer-reports-command-writes · decision · Offered, not forced: the CLI-entry gate REPORTS the offer and never writes; only `fr run adopt` / `fr migrate artifacts --adopt` create a run (phase 6)

Spec §3.E says adoption is "offered, not forced: the migration reports
in-flight plans with no run and adopts them in the interactive path". The
operator's Phase 6 brief adds a constraint that outranks the wording: adoption
"must never silently create runs during an unrelated command — an operator
running `fr status` should not discover new tracked files."

Those collide, because the interactive migration path IS an unrelated command:
`ensure_artifacts_current` fires at CLI entry, before whatever the operator
typed. Split accordingly, so the OFFER lands in the interactive path while the
WRITE stays something the operator asked for:

1. `ensure_artifacts_current` (CLI-entry gate) — REPORTS only. After a
   migration it emits one line naming each in-flight plan with no run plus the
   exact `fr run adopt <dir>` command, and creates nothing. It reaches the
   offer only in the interactive arm; the non-interactive refusal exits before
   it (nothing migrated, so there is no "your fr changed under this work"
   moment to report an offer in). Pinned by
   `test_the_gate_creates_no_run_of_its_own` and
   `test_the_non_interactive_refusal_does_not_reach_the_offer`.
2. `fr migrate artifacts` — reports the same offer by default (naming both
   `--adopt` and the per-plan command), and ADOPTS with `--adopt`. `--adopt`
   without `--yes` is a dry-run listing what it would adopt, like every other
   fr mutation. A per-plan adoption failure is reported and the rest still
   happen — a half-adoptable tree must not make the migration look broken.
3. `fr run adopt` — the explicit single-plan command.

Both surfaces share `adoptable_plans(repo_root)`, so they cannot describe the
same situation differently. A plan is offered iff: parseable (a malformed or
version-excluded plan is a different problem and must not wedge the
migration), live (only `docs/superpowers/plans/` is walked, so archives are
excluded structurally), NOT complete, and has no run.

"NOT COMPLETE" reuses the repo's existing definition — every phase
`plan_locally_complete` — the same one `completed_unarchived_plans`, the
archive gate and the unarchived-plans tripwire use. Spec §3.E's "a cursor over
completed work is noise" therefore needs no new predicate, and cannot drift
from the archive's idea of done.

"HAS NO RUN" reuses `fr.archive.find_run_for_plan` (promoted from
`_find_run_for_plan` for this). It matches on the recorded `emitted.plan`, so
the offer set self-heals after adoption: adopt a plan and it drops out of the
offer, WITHOUT any name convention between run ids and plan slugs.

Verified live on this repo: `uv run fr migrate artifacts` (dry-run) prints
"every artifact is already current" and then offers exactly two plans —
2026-07-09-multi-backend-git-host-adapters and
2026-08-30-artifact-migration-framework — while
2026-08-14-workflow-shapes-and-workitem-dispatch, whose phases are all ticked,
is correctly not offered. No file was written.
