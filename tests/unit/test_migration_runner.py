"""The migration runner — registered, chained, idempotent (spec §3.B).

A migration is `(kind, from_version, to_version, fn)`; the runner reads each
artifact's stamp and applies the chain up to the kind's current version. Spec
§3.B also names a second, version-INDEPENDENT shape — a **repair**, guarded by
its own predicate and idempotent because applying it makes that predicate
false. 4.0.0's only registered migration is one of those (see
`test_migration_fr_version.py`), so both shapes are exercised here.

The tests build their own `MigrationRegistry` over synthetic kinds rather than
mutating the shipped one: a test that registered into `MIGRATIONS` would leak
into every other test in the session, and the shipped registry's content is
`test_migration_fr_version.py`'s subject, not this file's.
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest
import yaml
from fr.artifacts.registry import ARTIFACT_KINDS, ArtifactKind, read_version
from fr.artifacts.runner import (
    MIGRATIONS,
    DuplicateMigrationError,
    MigrationChainError,
    MigrationRegistry,
    Repair,
    SchemaMigration,
    is_stale,
    plan_migrations,
    run_migrations,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- fixtures ------------------------------------------------------------
#
# The synthetic kind is the REAL plan kind with a moved `current_version`, so
# the stamp carrier under test is the shipped reader/writer pair rather than a
# test double that could agree with a broken runner.


def _registry(current_version: int = 3) -> MigrationRegistry:
    kind: ArtifactKind = replace(ARTIFACT_KINDS["plan"], current_version=current_version)
    return MigrationRegistry(kinds={kind.name: kind})


def _plan(root: Path, slug: str, *, version: int | None = 1, extra: str = "") -> Path:
    d = root / "docs" / "superpowers" / "plans" / slug
    d.mkdir(parents=True, exist_ok=True)
    p = d / "_meta.yaml"
    head = "" if version is None else f"schema_version: {version}\n"
    p.write_text(f"{head}plan: {slug}\ntarget_repo: derio-net/super-fr\n{extra}")
    return p


def _archived_plan(root: Path, slug: str, *, version: int = 1) -> Path:
    d = root / "docs" / "superpowers" / "implemented" / "plans" / slug
    d.mkdir(parents=True, exist_ok=True)
    p = d / "_meta.yaml"
    p.write_text(f"schema_version: {version}\nplan: {slug}\n")
    return p


def _freeze(path: Path) -> tuple[int, bytes]:
    """Pin an artifact's bytes AND mtime so `untouched` can mean untouched."""
    os.utime(path, (1_000_000, 1_000_000))
    return path.stat().st_mtime_ns, path.read_bytes()


def _unchanged(path: Path, before: tuple[int, bytes]) -> bool:
    return (path.stat().st_mtime_ns, path.read_bytes()) == before


def _append(marker: str):
    """A migration fn that appends a marker line — re-reading before writing."""

    def fn(path: Path) -> None:
        path.write_text(path.read_text() + f"{marker}: true\n")

    return fn


# --- Task 1: the chain ---------------------------------------------------


def test_the_chain_is_applied_up_to_the_kinds_current_version(tmp_path: Path) -> None:
    reg = _registry(current_version=3)
    order: list[str] = []
    reg.register(
        SchemaMigration("plan", 1, 2, lambda p: (order.append("1->2"), _append("one_two")(p))[1])
    )
    reg.register(
        SchemaMigration("plan", 2, 3, lambda p: (order.append("2->3"), _append("two_three")(p))[1])
    )
    meta = _plan(tmp_path, "a", version=1)

    report = run_migrations(tmp_path, dry_run=False, registry=reg)

    assert order == ["1->2", "2->3"], "steps must run in order, low version first"
    assert read_version("plan", meta) == 3, "the runner stamps the artifact it migrated"
    body = yaml.safe_load(meta.read_text())
    assert body["one_two"] is True and body["two_three"] is True
    assert [(a.from_version, a.to_version) for a in report.applied] == [(1, 2), (2, 3)]
    assert report.failed == ()
    assert report.changed_paths == (meta,)


def test_an_artifact_already_current_is_untouched(tmp_path: Path) -> None:
    reg = _registry(current_version=2)
    called: list[Path] = []
    reg.register(SchemaMigration("plan", 1, 2, lambda p: called.append(p)))
    meta = _plan(tmp_path, "a", version=2)
    before = _freeze(meta)

    report = run_migrations(tmp_path, dry_run=False, registry=reg)

    assert called == [], "a current artifact must not reach the migration fn at all"
    assert report.applied == ()
    assert _unchanged(meta, before), "no write, no mtime change"
    assert not is_stale(tmp_path, registry=reg)


def test_a_chain_with_a_gap_raises(tmp_path: Path) -> None:
    reg = _registry(current_version=4)
    reg.register(SchemaMigration("plan", 1, 2, _append("one_two")))
    reg.register(SchemaMigration("plan", 3, 4, _append("three_four")))  # 2 -> 3 missing
    meta = _plan(tmp_path, "a", version=1)
    before = _freeze(meta)

    with pytest.raises(MigrationChainError) as e:
        plan_migrations(tmp_path, registry=reg)

    assert "plan" in str(e.value) and "2" in str(e.value)
    assert _unchanged(meta, before), "a gap is a registry bug: write nothing, not part of it"
    with pytest.raises(MigrationChainError):
        run_migrations(tmp_path, dry_run=False, registry=reg)
    assert _unchanged(meta, before)


def test_rerunning_after_a_successful_migration_is_a_no_op(tmp_path: Path) -> None:
    reg = _registry(current_version=2)
    calls: list[Path] = []
    reg.register(SchemaMigration("plan", 1, 2, lambda p: (calls.append(p), _append("m")(p))[1]))
    meta = _plan(tmp_path, "a", version=1)

    first = run_migrations(tmp_path, dry_run=False, registry=reg)
    after_first = _freeze(meta)
    second = run_migrations(tmp_path, dry_run=False, registry=reg)

    assert len(first.applied) == 1
    assert second.applied == () and second.failed == ()
    assert calls == [meta], "the stamp is the guard — the fn runs exactly once"
    assert _unchanged(meta, after_first)


def test_a_failing_migration_is_reported_without_aborting_the_others(tmp_path: Path) -> None:
    reg = _registry(current_version=2)

    def fn(path: Path) -> None:
        if path.parent.name == "boom":
            raise RuntimeError("migration exploded")
        _append("ok")(path)

    reg.register(SchemaMigration("plan", 1, 2, fn))
    bad = _plan(tmp_path, "boom", version=1)
    good = _plan(tmp_path, "zzz-fine", version=1)
    bad_before = _freeze(bad)

    report = run_migrations(tmp_path, dry_run=False, registry=reg)

    assert _unchanged(bad, bad_before), "a raising migration leaves ITS artifact unmodified"
    assert [f.path for f in report.failed] == [bad]
    assert "migration exploded" in report.failed[0].error
    assert [a.path for a in report.applied] == [good], "one failure must not abort the rest"
    assert read_version("plan", good) == 2
    assert report.changed_paths == (good,)


def test_a_migration_that_raises_mid_write_is_not_stamped(tmp_path: Path) -> None:
    """The stamp is written by the runner AFTER the fn returns, never before.

    A stamp written first would mark a half-migrated artifact as current and
    make the damage permanent — the next run would skip it.
    """
    reg = _registry(current_version=2)

    def fn(path: Path) -> None:
        path.write_text(path.read_text() + "half: written\n")
        raise RuntimeError("died after a partial write")

    reg.register(SchemaMigration("plan", 1, 2, fn))
    meta = _plan(tmp_path, "a", version=1)

    report = run_migrations(tmp_path, dry_run=False, registry=reg)

    assert len(report.failed) == 1
    assert read_version("plan", meta) == 1, "still stale, so the next run retries it"


def test_a_dry_run_writes_nothing_but_reports_the_plan(tmp_path: Path) -> None:
    reg = _registry(current_version=2)
    reg.register(SchemaMigration("plan", 1, 2, _append("m")))
    meta = _plan(tmp_path, "a", version=1)
    before = _freeze(meta)

    report = run_migrations(tmp_path, registry=reg)  # dry-run is the DEFAULT

    assert report.dry_run is True
    assert [a.path for a in report.applied] == [meta]
    assert _unchanged(meta, before), "dry-run by default, like every other fr mutation"


def test_archived_artifacts_are_never_migrated(tmp_path: Path) -> None:
    reg = _registry(current_version=2)
    reg.register(SchemaMigration("plan", 1, 2, _append("m")))
    archived = _archived_plan(tmp_path, "shipped", version=1)
    before = _freeze(archived)

    report = run_migrations(tmp_path, dry_run=False, registry=reg)

    assert report.applied == () and report.failed == ()
    assert _unchanged(archived, before), "implemented/ records what shipped (spec §2)"


def test_an_artifact_newer_than_this_fr_is_left_alone(tmp_path: Path) -> None:
    """No downgrades (spec §2). The runner ignores it; Phase 7's validator judges it."""
    reg = _registry(current_version=2)
    reg.register(SchemaMigration("plan", 1, 2, _append("m")))
    meta = _plan(tmp_path, "a", version=9)
    before = _freeze(meta)

    report = run_migrations(tmp_path, dry_run=False, registry=reg)

    assert report.applied == ()
    assert _unchanged(meta, before)


# --- Task 1: re-reading immediately before writing (spec §4) -------------


def test_a_migration_sees_a_concurrent_write_not_a_stale_parse(tmp_path: Path) -> None:
    """Spec §4 names an agent writing the same artifact concurrently as a real
    hazard. The fn must read the file itself, at apply time."""
    reg = _registry(current_version=2)
    _plan(tmp_path, "a", version=2)
    observed: list[str] = []

    def racer(path: Path) -> bool:
        # Stands in for an agent writing between planning and applying.
        path.write_text(path.read_text() + "written_by_an_agent: true\n")
        return True

    def fn(path: Path) -> None:
        observed.append(path.read_text())

    reg.register(Repair("plan", "sees-the-race", applies=racer, fn=fn))
    run_migrations(tmp_path, dry_run=False, registry=reg)

    assert observed and "written_by_an_agent" in observed[0]


def test_an_artifact_that_became_current_after_planning_is_skipped(tmp_path: Path) -> None:
    """The runner re-reads the stamp immediately before writing, so an artifact
    another process migrated in the meantime is not migrated twice."""
    reg = _registry(current_version=2)
    a = _plan(tmp_path, "a", version=1)
    b = _plan(tmp_path, "b", version=1)
    seen: list[Path] = []

    def fn(path: Path) -> None:
        seen.append(path)
        if path == a:
            # Simulates a concurrent fr finishing b while we work on a.
            b.write_text("schema_version: 2\nplan: b\nmigrated_elsewhere: true\n")
        _append("m")(path)

    reg.register(SchemaMigration("plan", 1, 2, fn))
    report = run_migrations(tmp_path, dry_run=False, registry=reg)

    assert seen == [a], "b was already current by the time its turn came"
    assert [s.path for s in report.skipped] == [b]
    assert "migrated_elsewhere: true" in b.read_text()
    assert "m: true" not in b.read_text(), "no second application over another writer's work"


# --- Task 1: repairs are predicate-guarded, not stamp-guarded ------------


def test_a_repair_runs_without_moving_the_version_and_is_idempotent(tmp_path: Path) -> None:
    reg = _registry(current_version=2)
    calls: list[Path] = []

    def applies(path: Path) -> bool:
        return "repaired" not in path.read_text()

    def fn(path: Path) -> None:
        calls.append(path)
        path.write_text(path.read_text() + "repaired: true\n")

    reg.register(Repair("plan", "add-repaired", applies=applies, fn=fn))
    meta = _plan(tmp_path, "a", version=2)  # ALREADY current: a stamp guard would skip it

    first = run_migrations(tmp_path, dry_run=False, registry=reg)
    assert [a.path for a in first.applied] == [meta]
    assert first.applied[0].from_version is None, "a repair declares no version transition"
    assert first.applied[0].repair == "add-repaired"
    assert read_version("plan", meta) == 2, "a repair changes a constraint, not a shape"

    settled = _freeze(meta)
    second = run_migrations(tmp_path, dry_run=False, registry=reg)
    assert second.applied == ()
    assert calls == [meta], "applying it made its own predicate false"
    assert _unchanged(meta, settled)


def test_a_repair_whose_predicate_raises_is_reported_not_fatal(tmp_path: Path) -> None:
    reg = _registry(current_version=2)

    def applies(path: Path) -> bool:
        if path.parent.name == "boom":
            raise ValueError("cannot read this constraint")
        return True

    reg.register(Repair("plan", "r", applies=applies, fn=_append("r")))
    bad = _plan(tmp_path, "boom", version=2)
    good = _plan(tmp_path, "zzz-fine", version=2)
    bad_before = _freeze(bad)

    report = run_migrations(tmp_path, dry_run=False, registry=reg)

    assert [f.path for f in report.failed] == [bad]
    assert "cannot read this constraint" in report.failed[0].error
    assert _unchanged(bad, bad_before)
    assert [a.path for a in report.applied] == [good]


def test_schema_migrations_run_before_repairs_on_the_same_artifact(tmp_path: Path) -> None:
    """A repair inspects the CURRENT shape, so the shape must be current first."""
    reg = _registry(current_version=2)
    order: list[str] = []
    reg.register(SchemaMigration("plan", 1, 2, lambda p: order.append("schema")))
    reg.register(Repair("plan", "r", applies=lambda p: True, fn=lambda p: order.append("repair")))
    _plan(tmp_path, "a", version=1)

    run_migrations(tmp_path, dry_run=False, registry=reg)

    assert order == ["schema", "repair"]


# --- Task 1: registration API -------------------------------------------


def test_registering_two_migrations_for_the_same_transition_raises() -> None:
    reg = _registry()
    reg.register(SchemaMigration("plan", 1, 2, _append("a")))
    with pytest.raises(DuplicateMigrationError):
        reg.register(SchemaMigration("plan", 1, 2, _append("b")))


def test_registering_two_repairs_with_the_same_name_raises() -> None:
    reg = _registry()
    reg.register(Repair("plan", "r", applies=lambda p: True, fn=_append("a")))
    with pytest.raises(DuplicateMigrationError):
        reg.register(Repair("plan", "r", applies=lambda p: True, fn=_append("b")))


def test_registering_for_an_unknown_kind_raises() -> None:
    from fr.artifacts.registry import UnknownArtifactKindError

    reg = _registry()
    with pytest.raises(UnknownArtifactKindError):
        reg.register(SchemaMigration("nonesuch", 1, 2, _append("a")))


def test_a_migration_that_does_not_move_the_version_forward_is_rejected() -> None:
    with pytest.raises(ValueError):
        SchemaMigration("plan", 2, 2, _append("a"))
    with pytest.raises(ValueError):
        SchemaMigration("plan", 3, 2, _append("a"))


def test_is_stale_short_circuits_and_agrees_with_the_plan(tmp_path: Path) -> None:
    reg = _registry(current_version=2)
    reg.register(SchemaMigration("plan", 1, 2, _append("m")))
    assert is_stale(tmp_path, registry=reg) is False
    _plan(tmp_path, "a", version=1)
    assert is_stale(tmp_path, registry=reg) is True
    assert len(plan_migrations(tmp_path, registry=reg)) == 1
    run_migrations(tmp_path, dry_run=False, registry=reg)
    assert is_stale(tmp_path, registry=reg) is False


# --- closing f-closed-world-models-reject-a-stamp ------------------------
#
# `RunState`, `Matrix` and `PlanMeta` are all `extra="forbid"`; stamping a LIVE
# file of those kinds makes it unparseable, and for the matrix that would take
# the `fr acceptance check` CI gate down. journal/run/matrix/spec are all
# registered at version 1 and an absent stamp already READS as 1, so a correct
# runner has no reason to write to them. Phase 1 left that as an assertion;
# these two tests are the proof.


def _seed_closed_world(root: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    run = root / "docs" / "superpowers" / "runs" / "r1.yaml"
    run.parent.mkdir(parents=True)
    run.write_text(
        "run: r1\nworkflow: fr-goal@1\nbranch: b\nstarted: '2026-08-30T00:00:00'\n"
        "cursor: spec\nsteps:\n  spec:\n    state: pending\n"
    )
    paths["run"] = run
    matrix = root / "docs" / "acceptance" / "matrix.yaml"
    matrix.parent.mkdir(parents=True)
    matrix.write_text("org: derio-net\nrepo: super-fr\nrows:\n")
    paths["matrix"] = matrix
    journal = root / "docs" / "superpowers" / "journals" / "plans" / "j.md"
    journal.parent.mkdir(parents=True)
    journal.write_text("<!-- fr:journal kind=discovery scope=plan id=d created=2026-08-30 -->\n")
    paths["journal"] = journal
    spec = root / "docs" / "superpowers" / "specs" / "s-design.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# A spec\n\n## Implementation Plans\n")
    paths["spec"] = spec
    paths["plan"] = _plan(root, "live", version=2, extra="fr_version: '>=4.0.0,<5.0.0'\n")
    return paths


def test_the_shipped_runner_never_writes_to_a_closed_world_artifact(tmp_path: Path) -> None:
    from fr.acceptance.model import load_matrix
    from fr.run.model import parse_run_state

    paths = _seed_closed_world(tmp_path)
    frozen = {name: _freeze(p) for name, p in paths.items()}

    report = run_migrations(tmp_path, dry_run=False)  # the SHIPPED registry

    assert report.failed == ()
    for name, p in paths.items():
        assert _unchanged(p, frozen[name]), f"the runner wrote to a {name} artifact"
    # And the closed-world models still parse — the failure mode the finding named.
    parse_run_state(paths["run"].read_text())
    load_matrix(paths["matrix"])


def test_the_shipped_registry_registers_nothing_for_the_version_one_kinds() -> None:
    for name in ("journal", "run", "matrix", "spec"):
        assert MIGRATIONS.schema_migrations(name) == (), (
            f"{name} is at current_version=1; a schema migration for it would make the "
            f"runner stamp a live file whose model is extra='forbid'"
        )


def test_this_repos_own_artifacts_plan_only_safe_actions() -> None:
    """The runner against super-fr itself: nothing archived, nothing closed-world.

    Deliberately NOT an assertion on how many plans need migrating — 38 of the
    39 `<4.0.0` ceilings here are archived and excluded, so a count would be
    measuring the archive the runner must never touch.
    """
    actions = plan_migrations(REPO_ROOT)
    for a in actions:
        assert "implemented" not in a.path.relative_to(REPO_ROOT).parts
        assert a.kind == "plan", f"nothing but plans has a migration in 4.0.0, got {a.kind}"
        assert a.from_version is None, "the only 4.0.0 migration is a repair, not a schema bump"
