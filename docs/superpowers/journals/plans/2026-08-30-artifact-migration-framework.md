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

<!-- fr:journal kind=finding scope=plan id=f-closed-world-models-reject-a-stamp created=2026-08-30T13:14:30 phase=1 state=open -->
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
