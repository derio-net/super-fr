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
