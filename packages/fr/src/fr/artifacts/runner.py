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
   is reported, and does not abort the others. A *chain gap* is different: it
   is a bug in the registry, not in the data, so it raises before anything is
   written.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from fr.artifacts.registry import (
    ARTIFACT_KINDS,
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
    for name, kind in reg.kinds.items():
        for path in iter_paths_of(repo_root, kind):
            actions.extend(_actions_for(reg, name, kind, path)[0])
    return tuple(actions)


def is_stale(repo_root: Path, *, registry: MigrationRegistry | None = None) -> bool:
    """Is anything under `repo_root` out of date? Bails on the first `yes`.

    Phase 3's CLI-entry callback runs before *every* command, so it must not
    walk the whole tree when the answer is available early.
    """
    reg = registry if registry is not None else MIGRATIONS
    for name, kind in reg.kinds.items():
        for path in iter_paths_of(repo_root, kind):
            actions, _ = _actions_for(reg, name, kind, path)
            if actions:
                return True
    return False


def _actions_for(
    reg: MigrationRegistry, name: str, kind: ArtifactKind, path: Path
) -> tuple[list[PlannedAction], list[FailedAction]]:
    """What `path` needs right now — schema migrations first, then repairs.

    The order matters: a repair inspects the artifact's current shape, so the
    shape has to be current before it looks. Any *data* problem (an unreadable
    stamp, a predicate that raises) becomes a `FailedAction` for this one
    artifact; a chain gap propagates, because that is a registry bug.
    """
    actions: list[PlannedAction] = []
    failures: list[FailedAction] = []
    try:
        version = kind.read_version(path)
    except MigrationChainError:  # pragma: no cover — readers do not raise this
        raise
    except Exception as e:
        return actions, [FailedAction(name, path, f"{name} stamp", f"{type(e).__name__}: {e}")]
    for m in reg.chain(name, version):
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
) -> MigrationReport:
    """Migrate every stale artifact under `repo_root`.

    Dry-run by default, like every other fr mutation: the report says what
    *would* happen and not one byte is written.

    Plans the whole tree first, then applies — so a chain gap anywhere raises
    before anything anywhere is written, and so an action that has become
    unnecessary by the time its turn comes can be reported as `skipped` rather
    than silently vanishing.
    """
    reg = registry if registry is not None else MIGRATIONS
    planned: list[tuple[str, ArtifactKind, Path, list[PlannedAction]]] = []
    failed: list[FailedAction] = []

    for name, kind in reg.kinds.items():
        for path in iter_paths_of(repo_root, kind):
            actions, planning_failures = _actions_for(reg, name, kind, path)
            failed.extend(planning_failures)
            if actions:
                planned.append((name, kind, path, actions))

    if dry_run:
        return MigrationReport(
            dry_run=True,
            applied=tuple(a for _, _, _, actions in planned for a in actions),
            failed=tuple(failed),
        )

    applied: list[PlannedAction] = []
    skipped: list[PlannedAction] = []
    for name, kind, path, actions in planned:
        done, failures = _apply_to_one(reg, name, kind, path)
        applied.extend(done)
        failed.extend(failures)
        settled = {_key(a) for a in done} | {(f.path, f.summary) for f in failures}
        skipped.extend(
            a for a in actions if _key(a) not in settled and (a.path, a.summary) not in settled
        )

    return MigrationReport(
        dry_run=False,
        applied=tuple(applied),
        skipped=tuple(skipped),
        failed=tuple(failed),
    )


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

    # Schema migrations: re-read the stamp before each step.
    while True:
        try:
            version = kind.read_version(path)
        except Exception as e:
            failed.append(FailedAction(name, path, f"{name} stamp", f"{type(e).__name__}: {e}"))
            return applied, failed
        chain = reg.chain(name, version)
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
        applied.append(
            PlannedAction(
                kind=name,
                path=path,
                summary=step.summary,
                from_version=step.from_version,
                to_version=step.to_version,
            )
        )

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
