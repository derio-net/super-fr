"""The migration runner — registered, chained, idempotent (spec §3.B).

A node's installed `fr` changes whenever the plugin updates; the artifacts on
disk do not change with it. This module is what closes that gap: migrations
register themselves here, and the runner walks every LIVE artifact, works out
what each one needs, and applies it.

Two shapes of migration, because not every version bump changes a shape:

- **`SchemaMigration`** — `(kind, from_version, to_version, fn)`, guarded by
  the artifact's stamp. The runner chains them (1→2, 2→3, …) up to the kind's
  `current_version` and writes the new stamp itself, *after* `fn` returns.
- **`Repair`** — predicate-guarded and version-independent. Idempotent because
  applying it makes its own predicate false; it never moves the stamp.

4.0.0 registers exactly one migration and it is a **repair**: widening plan
`fr_version` ceilings that exclude the installed major changes a *constraint*,
not a shape. Making it a schema migration would mean bumping the plan stamp —
which, since a plan's stamp IS its `_meta.yaml schema_version`, would declare a
plan-folder shape change that did not happen (see `fr_version.py`).

Three invariants the rest of the framework leans on:

1. **The work list comes from the stamp, never from the walk.** An artifact is
   migrated only when `read_version(path) < kind.current_version` (or a repair's
   predicate says so). The runner never "normalises on write": `RunState`,
   `Matrix` and `PlanMeta` are all `extra="forbid"`, so stamping a live file of
   those kinds would make it unparseable — and for the matrix would take the
   `fr acceptance check` CI gate down with it.
2. **Re-read immediately before writing.** Spec §4 names an agent writing the
   same artifact concurrently as a real hazard, so nothing decided at plan time
   is trusted at apply time: the stamp and the predicate are re-checked, and
   every `fn` reads the file itself.
3. **One artifact's failure is one artifact's failure.** A raising migration
   leaves that artifact unmodified and unstamped (so the next run retries it),
   is reported, and does not abort the others. A *chain gap* is different —
   but only when the version it gapped on came from a stamp the artifact
   actually declares. Then it is a bug in the registry, not in the data, and it
   raises before anything is written. A gap over an artifact that declares NO
   version (an empty, truncated or hand-made carrier, which reads as
   `PRE_FRAMEWORK_VERSION`) is a data problem with one file, so it is that
   file's `FailedAction` — otherwise a single empty `_meta.yaml` makes every
   `fr` command exit 2 while blaming the registry.
4. **A failure is visible or it is not a failure.** `is_stale` reports a tree
   it could not inspect as stale, so the CLI-entry gate refuses instead of
   running over it; and one problem is reported once, not once per pass.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from fr.artifacts.registry import (
    ARTIFACT_KINDS,
    PRE_FRAMEWORK_VERSION,
    ArtifactError,
    ArtifactKind,
    iter_paths_of,
)


class ArtifactMigrationError(ArtifactError):
    """Base for every migration-runner failure."""


class MigrationChainError(ArtifactMigrationError):
    """No registered migration moves an artifact off the version it is on."""


class DuplicateMigrationError(ArtifactMigrationError):
    """Two migrations claim the same transition, or two repairs the same name."""


# --- what a migration is -------------------------------------------------


@dataclass(frozen=True)
class SchemaMigration:
    """Moves one artifact kind `from_version` → `to_version`. Stamp-guarded.

    `fn` rewrites the artifact's body and nothing else: the runner writes the
    new stamp once `fn` returns. `fn` must read the file itself — it is handed
    a path, never a parsed document.
    """

    kind: str
    from_version: int
    to_version: int
    fn: Callable[[Path], None]
    description: str = ""

    def __post_init__(self) -> None:
        if self.to_version <= self.from_version:
            raise ValueError(
                f"{self.kind}: a schema migration must move the version forward, "
                f"got {self.from_version} -> {self.to_version}"
            )

    @property
    def summary(self) -> str:
        return self.description or f"{self.kind} schema {self.from_version} -> {self.to_version}"


@dataclass(frozen=True)
class Repair:
    """A version-independent fix, guarded by its own predicate.

    `applies(path)` answers "does this artifact still need it?"; applying `fn`
    must make that answer False, which is where idempotence comes from. The
    stamp is not touched: a repair changes a constraint, not a shape.
    """

    kind: str
    name: str
    applies: Callable[[Path], bool]
    fn: Callable[[Path], None]
    description: str = ""

    @property
    def summary(self) -> str:
        return self.description or f"{self.kind} repair: {self.name}"


# --- what the runner reports ---------------------------------------------


@dataclass(frozen=True)
class PlannedAction:
    """One artifact × one migration. `from_version is None` marks a repair."""

    kind: str
    path: Path
    summary: str
    from_version: int | None = None
    to_version: int | None = None
    repair: str | None = None

    @property
    def is_repair(self) -> bool:
        return self.repair is not None


@dataclass(frozen=True)
class FailedAction:
    """An artifact the runner could not migrate, and why. Never fatal."""

    kind: str
    path: Path
    summary: str
    error: str


@dataclass(frozen=True)
class MigrationReport:
    dry_run: bool
    applied: tuple[PlannedAction, ...] = ()
    skipped: tuple[PlannedAction, ...] = ()
    """Planned, then found unnecessary at apply time — another writer got there
    first. Recorded rather than dropped: it is the visible half of invariant 2."""
    failed: tuple[FailedAction, ...] = ()

    @property
    def changed_paths(self) -> tuple[Path, ...]:
        """Exactly the paths that were rewritten, in order, deduplicated.

        Phase 4 stages *these* — `git add -- <paths>`, never `-A` — so an
        operator's unrelated in-flight edits stay in the working tree.
        """
        seen: dict[Path, None] = {}
        for a in self.applied:
            seen[a.path] = None
        return tuple(seen)

    @property
    def ok(self) -> bool:
        return not self.failed


# --- the registry of migrations ------------------------------------------


@dataclass
class MigrationRegistry:
    """Every registered migration, keyed by kind.

    Holds the artifact kinds it operates over so the runner has exactly one
    injection point: `MIGRATIONS` carries the shipped `ARTIFACT_KINDS`, and a
    test can hand it synthetic kinds without any production code growing a
    second enumeration (`registry.py` remains the only one).
    """

    kinds: Mapping[str, ArtifactKind] = field(default_factory=lambda: dict(ARTIFACT_KINDS))
    _schema: dict[str, list[SchemaMigration]] = field(default_factory=dict, repr=False)
    _repairs: dict[str, list[Repair]] = field(default_factory=dict, repr=False)

    def kind(self, name: str) -> ArtifactKind:
        from fr.artifacts.registry import UnknownArtifactKindError

        try:
            return self.kinds[name]
        except KeyError:
            raise UnknownArtifactKindError(
                f"unknown artifact kind {name!r} (known: {', '.join(sorted(self.kinds))})"
            ) from None

    def register(self, migration: SchemaMigration | Repair) -> SchemaMigration | Repair:
        """Register `migration`. Returns it, so it can be used as a decorator target."""
        self.kind(migration.kind)  # unknown kind fails at import, not at run time
        if isinstance(migration, SchemaMigration):
            existing = self._schema.setdefault(migration.kind, [])
            for m in existing:
                if m.from_version == migration.from_version:
                    raise DuplicateMigrationError(
                        f"{migration.kind}: two migrations start at version "
                        f"{migration.from_version}"
                    )
            existing.append(migration)
            existing.sort(key=lambda m: m.from_version)
        else:
            repairs = self._repairs.setdefault(migration.kind, [])
            if any(r.name == migration.name for r in repairs):
                raise DuplicateMigrationError(
                    f"{migration.kind}: two repairs named {migration.name!r}"
                )
            repairs.append(migration)
        return migration

    def schema_migrations(self, kind: str) -> tuple[SchemaMigration, ...]:
        return tuple(self._schema.get(kind, ()))

    def repairs(self, kind: str) -> tuple[Repair, ...]:
        return tuple(self._repairs.get(kind, ()))

    def chain(self, kind: str, from_version: int) -> tuple[SchemaMigration, ...]:
        """The migrations that carry an artifact from `from_version` to current.

        Raises `MigrationChainError` on a gap. A gap is a registry bug, so it is
        loud: silently applying the reachable half would leave the artifact in a
        shape no version ever defined.
        """
        target = self.kind(kind).current_version
        steps: list[SchemaMigration] = []
        at = from_version
        while at < target:
            for m in self.schema_migrations(kind):
                if m.from_version == at:
                    steps.append(m)
                    at = m.to_version
                    break
            else:
                raise MigrationChainError(
                    f"{kind}: no registered migration from version {at} "
                    f"(need to reach {target}) — the chain has a gap"
                )
        return tuple(steps)


MIGRATIONS = MigrationRegistry()
"""The shipped registry. `fr.artifacts` imports the built-in migrations into it."""


# --- planning ------------------------------------------------------------


def plan_migrations(
    repo_root: Path, *, registry: MigrationRegistry | None = None
) -> tuple[PlannedAction, ...]:
    """Everything that needs doing under `repo_root`, without doing any of it.

    Reads only. Archived artifacts are excluded by construction (`iter_paths_of`).
    """
    reg = registry if registry is not None else MIGRATIONS
    actions: list[PlannedAction] = []
    for name, kind in _ordered_kinds(reg):
        for path in iter_paths_of(repo_root, kind):
            actions.extend(_actions_for(reg, name, kind, path)[0])
    return tuple(actions)


def is_stale(repo_root: Path, *, registry: MigrationRegistry | None = None) -> bool:
    """Is anything under `repo_root` out of date? Bails on the first `yes`.

    Phase 3's CLI-entry callback runs before *every* command, so it must not
    walk the whole tree when the answer is available early.

    A `FailedAction` counts as a yes. "Stale" here means *not known to be
    current*: an artifact whose stamp will not read, or whose repair predicate
    raises, is a tree of unknown state — and the gate's whole promise is to
    refuse rather than run over one. Discarding those failures made the gate
    wave through precisely the case it exists for.
    """
    reg = registry if registry is not None else MIGRATIONS
    for name, kind in _ordered_kinds(reg):
        for path in iter_paths_of(repo_root, kind):
            actions, failures = _actions_for(reg, name, kind, path)
            if actions or failures:
                return True
    return False


def _ordered_kinds(reg: MigrationRegistry) -> list[tuple[str, ArtifactKind]]:
    """Kinds in a stable, name-sorted order (review r5-e7).

    `dict` preserves insertion order, which is stable for the SHIPPED registry
    but not for one assembled by a caller — and `iter_paths_of` already sorts
    within a kind. Sorting here makes the whole walk a function of the data
    alone, so `report.changed_paths` (hence the `git add` pathspec, hence the
    commit) is byte-reproducible for a given tree.
    """
    return sorted(reg.kinds.items())


def _chain_for(
    reg: MigrationRegistry, name: str, kind: ArtifactKind, path: Path
) -> tuple[tuple[SchemaMigration, ...], FailedAction | None]:
    """The schema steps `path` needs — or the one failure that stands in for them.

    Two data problems are caught here and turned into a `FailedAction` for this
    artifact alone (invariant 3):

    - the stamp does not read at all (`ArtifactStampError`, unparseable YAML);
    - the artifact declares NO version, reads as `PRE_FRAMEWORK_VERSION`, and
      no registered migration moves it off there.

    A chain gap over a version the artifact *declares* still raises: that is a
    registry bug — a shape was bumped without a migration to reach it — and
    silently degrading it to a per-file failure would hide the one case the
    loud error was written for.
    """
    try:
        declared = kind.read_stamp(path)
    except Exception as e:
        return (), FailedAction(name, path, f"{name} stamp", f"{type(e).__name__}: {e}")
    version = PRE_FRAMEWORK_VERSION if declared is None else declared
    try:
        return reg.chain(name, version), None
    except MigrationChainError:
        if declared is not None:
            raise
        return (), FailedAction(
            name,
            path,
            f"{name} stamp",
            f"declares no version ({kind.stamp} is absent), so it reads as version "
            f"{PRE_FRAMEWORK_VERSION} — and no registered migration moves it to "
            f"{kind.current_version}. The file may be empty, truncated or hand-made; "
            f"check it and add the stamp by hand.",
        )


def _actions_for(
    reg: MigrationRegistry, name: str, kind: ArtifactKind, path: Path
) -> tuple[list[PlannedAction], list[FailedAction]]:
    """What `path` needs right now — schema migrations first, then repairs.

    The order matters: a repair inspects the artifact's current shape, so the
    shape has to be current before it looks. Any *data* problem (an unreadable
    stamp, an unstamped artifact no migration can move, a predicate that
    raises) becomes a `FailedAction` for this one artifact.
    """
    actions: list[PlannedAction] = []
    failures: list[FailedAction] = []
    chain, failure = _chain_for(reg, name, kind, path)
    if failure is not None:
        return actions, [failure]
    for m in chain:
        actions.append(
            PlannedAction(
                kind=name,
                path=path,
                summary=m.summary,
                from_version=m.from_version,
                to_version=m.to_version,
            )
        )
    for r in reg.repairs(name):
        try:
            needed = r.applies(path)
        except Exception as e:
            failures.append(FailedAction(name, path, r.summary, f"{type(e).__name__}: {e}"))
            continue
        if needed:
            actions.append(PlannedAction(kind=name, path=path, summary=r.summary, repair=r.name))
    return actions, failures


# --- running -------------------------------------------------------------


def run_migrations(
    repo_root: Path,
    *,
    dry_run: bool = True,
    registry: MigrationRegistry | None = None,
    veto: Callable[[Path], str | None] | None = None,
) -> MigrationReport:
    """Migrate every stale artifact under `repo_root`.

    Dry-run by default, like every other fr mutation: the report says what
    *would* happen and not one byte is written.

    Plans the whole tree first, then applies — so a chain gap anywhere raises
    before anything anywhere is written, and so an action that has become
    unnecessary by the time its turn comes can be reported as `skipped` rather
    than silently vanishing.

    `veto` is an optional per-artifact hold: given a path with work to do, it
    returns a reason NOT to touch it, or `None`. The caller supplies the
    policy — the CLI-entry gate passes `commit.uncommitted_veto`, which holds
    back an artifact the operator has uncommitted edits in — and the runner
    stays git-agnostic. A vetoed artifact becomes a `FailedAction`, not a
    silent skip, so the gate refuses instead of continuing.
    """
    reg = registry if registry is not None else MIGRATIONS
    planned: list[tuple[str, ArtifactKind, Path, list[PlannedAction]]] = []
    failed: list[FailedAction] = []

    for name, kind in _ordered_kinds(reg):
        for path in iter_paths_of(repo_root, kind):
            actions, planning_failures = _actions_for(reg, name, kind, path)
            failed.extend(planning_failures)
            if not actions:
                continue
            held = veto(path) if veto is not None else None
            if held is not None:
                failed.append(FailedAction(name, path, f"{name} migration held back", held))
                continue
            planned.append((name, kind, path, actions))

    if dry_run:
        return MigrationReport(
            dry_run=True,
            applied=tuple(a for _, _, _, actions in planned for a in actions),
            failed=_distinct(failed),
        )

    applied: list[PlannedAction] = []
    skipped: list[PlannedAction] = []
    for name, kind, path, actions in planned:
        done, failures = _apply_to_one(reg, name, kind, path)
        applied.extend(done)
        failed.extend(failures)
        # `skipped` means "planned, then found unnecessary — another writer got
        # there first". An action that FAILED is not skipped, and neither is
        # anything that never ran because an earlier step for the same artifact
        # failed and returned: `_apply_to_one` abandons the whole path.
        #
        # Keyed on the PATH (review r5-c5). Keying the failure half on
        # `(path, summary)` only matched the one action whose summary the
        # failure happened to carry, so an artifact with a schema step AND a
        # repair — where the schema step failed and the repair therefore never
        # ran — reported the repair as `skipped`, i.e. "already done", when it
        # had not been attempted at all.
        applied_keys = {_key(a) for a in done}
        abandoned = {f.path for f in failures}
        skipped.extend(
            a for a in actions if _key(a) not in applied_keys and a.path not in abandoned
        )

    return MigrationReport(
        dry_run=False,
        applied=tuple(applied),
        skipped=tuple(skipped),
        failed=_distinct(failed),
    )


def _distinct(failures: list[FailedAction]) -> tuple[FailedAction, ...]:
    """The same failure, reported once. Order preserved, first occurrence kept.

    Planning and applying deliberately evaluate the same guards (invariant 2:
    nothing decided at plan time is trusted at apply time), so an artifact with
    both a schema step and a raising repair predicate produced two identical
    `FailedAction`s — printed twice by the gate and by `fr migrate artifacts`,
    and double-counted in the "N artifact(s) could not be migrated" line. Two
    *different* errors on one artifact are still two failures; only exact
    duplicates collapse.
    """
    seen: dict[tuple[object, ...], FailedAction] = {}
    for f in failures:
        seen.setdefault((f.kind, f.path, f.summary, f.error), f)
    return tuple(seen.values())


def _key(action: PlannedAction) -> tuple[object, ...]:
    return (action.path, action.from_version, action.to_version, action.repair)


def _apply_to_one(
    reg: MigrationRegistry, name: str, kind: ArtifactKind, path: Path
) -> tuple[list[PlannedAction], list[FailedAction]]:
    """Apply everything `path` needs, re-deciding immediately before each write.

    Nothing here trusts the planning pass: the stamp is re-read before every
    schema step and the predicate re-evaluated before every repair, because an
    agent may have written the file in between (spec §4). Whatever the plan
    said, this is what actually happens.
    """
    applied: list[PlannedAction] = []
    failed: list[FailedAction] = []

    # Schema migrations: re-read the stamp before each step. The loop is
    # BOUNDED by the number of registered steps for this kind, and every pass
    # must observe the stamp actually move. Neither guard is theoretical: the
    # YAML carrier reads with `yaml.safe_load` (a duplicate top-level key ->
    # the LAST wins) and writes by rewriting the FIRST matching line, so a
    # `_meta.yaml` carrying `schema_version` twice made this spin forever —
    # `fr <anything>` hanging with no output and no error.
    for _ in range(len(reg.schema_migrations(name)) + 1):
        chain, failure = _chain_for(reg, name, kind, path)
        if failure is not None:
            failed.append(failure)
            return applied, failed
        if not chain:
            break
        step = chain[0]
        try:
            step.fn(path)
        except Exception as e:
            # Unstamped on purpose: the artifact stays stale, so the next run
            # retries it instead of skipping a half-migration forever.
            failed.append(FailedAction(name, path, step.summary, f"{type(e).__name__}: {e}"))
            return applied, failed
        kind.write_version(path, step.to_version)
        try:
            landed = kind.read_version(path)
        except Exception as e:
            failed.append(FailedAction(name, path, step.summary, f"{type(e).__name__}: {e}"))
            return applied, failed
        if landed != step.to_version:
            failed.append(
                FailedAction(
                    name,
                    path,
                    step.summary,
                    f"stamping it with version {step.to_version} did not take — "
                    f"{kind.stamp} still reads as {landed}. The carrier probably declares "
                    f"the stamp twice; fix it by hand and re-run.",
                )
            )
            return applied, failed
        applied.append(
            PlannedAction(
                kind=name,
                path=path,
                summary=step.summary,
                from_version=step.from_version,
                to_version=step.to_version,
            )
        )
    else:
        failed.append(
            FailedAction(
                name,
                path,
                f"{name} stamp",
                f"more than {len(reg.schema_migrations(name))} schema step(s) were still "
                f"pending after applying every registered one — the chain does not "
                f"terminate for this artifact.",
            )
        )
        return applied, failed

    # Repairs: re-evaluate the predicate immediately before applying.
    for r in reg.repairs(name):
        try:
            if not r.applies(path):
                continue
            r.fn(path)
        except Exception as e:
            failed.append(FailedAction(name, path, r.summary, f"{type(e).__name__}: {e}"))
            continue
        applied.append(PlannedAction(kind=name, path=path, summary=r.summary, repair=r.name))

    return applied, failed
