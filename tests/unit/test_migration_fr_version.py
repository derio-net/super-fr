"""4.0.0's one registered migration: widen plan `fr_version` ceilings.

Spec §3.B. `fr_version` is enforced at parse (`parser.py:132-149`), so a plan
written under 3.x carrying `>=3.x,<4.0.0` raises `PlanSchemaError` the moment
4.0.0 lands — and the bridge swallows that, so dispatch stops while the daemon
reports a healthy tick. Widening the ceiling is the fix.

It is a **repair**, not a schema migration, and that distinction is the subject
of half this file. A plan's artifact stamp IS its `_meta.yaml schema_version`
(forced: `PlanMeta` is `extra="forbid"`, so a second key would make every
stamped plan unparseable). Bumping it to 3 would declare a plan-folder shape
change that did not happen and drag `PlanMeta.schema_version` to
`Literal[2, 3]` to encode a lie. A ceiling widening changes a *constraint*, not
a shape — so it is predicate-guarded and version-independent, and its
idempotence comes from applying it making its own predicate false.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from fr.artifacts.fr_version import (
    CEILING_REPAIR,
    MalformedConstraintError,
    needs_widening,
    widen_ceiling,
)
from fr.artifacts.runner import MIGRATIONS, run_migrations
from fr.cli import app
from fr.types import PlanMeta
from packaging.version import Version
from typer.testing import CliRunner

runner_cli = CliRunner()

# The ceilings this repo actually carries (22 plans at the first, 14 at the
# second) — fixtures taken from the data, not invented.
REAL_CEILINGS = (">=3.0.0,<4.0.0", ">=3.7.0,<4.0.0")


def _plan(root: Path, slug: str, *, fr_version: str | None, quote: str = "'") -> Path:
    d = root / "docs" / "superpowers" / "plans" / slug
    d.mkdir(parents=True, exist_ok=True)
    p = d / "_meta.yaml"
    line = "" if fr_version is None else f"fr_version: {quote}{fr_version}{quote}\n"
    p.write_text(
        f"schema_version: 2\nplan: {slug}\n"
        f"spec: {slug}-design.md\ntarget_repo: derio-net/super-fr\n"
        f"{line}created: '2026-07-09'\n"
    )
    return p


def _freeze(path: Path) -> tuple[int, bytes]:
    os.utime(path, (1_000_000, 1_000_000))
    return path.stat().st_mtime_ns, path.read_bytes()


def _unchanged(path: Path, before: tuple[int, bytes]) -> bool:
    return (path.stat().st_mtime_ns, path.read_bytes()) == before


# --- the pure widening rule ---------------------------------------------


@pytest.mark.parametrize(
    ("constraint", "installed", "expected"),
    [
        (">=3.0.0,<4.0.0", "4.0.0", ">=3.0.0,<5.0.0"),
        (">=3.7.0,<4.0.0", "4.0.0", ">=3.7.0,<5.0.0"),
        (">=3.16.0,<4.0.0", "4.0.0", ">=3.16.0,<5.0.0"),
        ("<4.0.0", "4.0.0", "<5.0.0"),
        (">=3.0.0,<4.0.0", "4.2.1", ">=3.0.0,<5.0.0"),
        # Already admits the installed version: nothing to do.
        (">=3.19.0,<5.0.0", "4.0.0", None),
        (">=4.0.0,<5.0.0", "4.0.0", None),
        (">=3.0.0,<4.0.0", "3.9.0", None),
        (">=3.0.0", "4.0.0", None),
        # Excluded by the FLOOR, not the ceiling: the plan wants a newer fr.
        # Widening would not admit us, and downgrades are a non-goal (spec §2).
        (">=5.0.0,<6.0.0", "4.0.0", None),
    ],
)
def test_widen_ceiling(constraint: str, installed: str, expected: str | None) -> None:
    assert widen_ceiling(constraint, Version(installed)) == expected


def test_the_widened_constraint_actually_admits_the_installed_version() -> None:
    from packaging.specifiers import SpecifierSet

    installed = Version("4.0.0")
    for c in REAL_CEILINGS:
        widened = widen_ceiling(c, installed)
        assert widened is not None
        assert installed in SpecifierSet(widened)
        # and it is still a CEILING — the widening does not throw the bound away
        assert Version("5.0.0") not in SpecifierSet(widened)


def test_a_malformed_constraint_raises_rather_than_guessing() -> None:
    with pytest.raises(MalformedConstraintError):
        widen_ceiling(">=3.0.0,<<4.0.0", Version("4.0.0"))


# --- the repair over real plan folders ----------------------------------


def test_a_ceiling_excluding_the_installed_major_is_widened(tmp_path: Path) -> None:
    meta = _plan(tmp_path, "old", fr_version=">=3.0.0,<4.0.0")

    report = run_migrations(tmp_path, dry_run=False)

    assert [a.path for a in report.applied] == [meta]
    assert report.applied[0].repair == CEILING_REPAIR.name
    assert yaml.safe_load(meta.read_text())["fr_version"] == ">=3.0.0,<5.0.0"


def test_widening_rewrites_the_constraint_and_nothing_else(tmp_path: Path) -> None:
    meta = _plan(tmp_path, "old", fr_version=">=3.7.0,<4.0.0")
    before = meta.read_text().splitlines()

    run_migrations(tmp_path, dry_run=False)

    after = meta.read_text().splitlines()
    changed = [(b, a) for b, a in zip(before, after, strict=True) if b != a]
    assert len(before) == len(after), "no line added or removed"
    assert changed == [("fr_version: '>=3.7.0,<4.0.0'", "fr_version: '>=3.7.0,<5.0.0'")]
    assert "'" in after[before.index("fr_version: '>=3.7.0,<4.0.0'")], "quoting is preserved"


def test_the_repair_does_not_move_the_plan_stamp(tmp_path: Path) -> None:
    """The point of making it a repair: `schema_version` still says 2, and the
    file still validates against `PlanMeta`'s `Literal[2]`."""
    meta = _plan(tmp_path, "old", fr_version=">=3.0.0,<4.0.0")

    run_migrations(tmp_path, dry_run=False)

    data = yaml.safe_load(meta.read_text())
    assert data["schema_version"] == 2
    PlanMeta.model_validate(data)  # would raise if the stamp had been bumped


def test_a_plan_already_admitting_the_installed_version_is_untouched(tmp_path: Path) -> None:
    meta = _plan(tmp_path, "current", fr_version=">=3.19.0,<5.0.0")
    before = _freeze(meta)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.applied == ()
    assert _unchanged(meta, before), "no write, no mtime change"


def test_a_plan_with_no_fr_version_is_untouched(tmp_path: Path) -> None:
    meta = _plan(tmp_path, "unconstrained", fr_version=None)
    before = _freeze(meta)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.applied == ()
    assert _unchanged(meta, before)
    assert needs_widening(meta) is False


def test_a_malformed_constraint_is_reported_not_rewritten(tmp_path: Path) -> None:
    bad = _plan(tmp_path, "broken", fr_version=">=3.0.0,<<4.0.0", quote='"')
    good = _plan(tmp_path, "zzz-old", fr_version=">=3.0.0,<4.0.0")
    bad_before = _freeze(bad)

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [bad]
    assert "fr_version" in report.failed[0].error or "specifier" in report.failed[0].error.lower()
    assert _unchanged(bad, bad_before), "fr never guesses at a constraint it cannot parse"
    assert [a.path for a in report.applied] == [good], "and the others still migrate"


def test_rerunning_the_repair_is_a_no_op(tmp_path: Path) -> None:
    meta = _plan(tmp_path, "old", fr_version=">=3.0.0,<4.0.0")

    run_migrations(tmp_path, dry_run=False)
    settled = _freeze(meta)
    second = run_migrations(tmp_path, dry_run=False)

    assert second.applied == () and second.failed == ()
    assert _unchanged(meta, settled), (
        "the predicate is the guard (acceptance: migration-is-idempotent)"
    )


def test_archived_plans_keep_their_pre_4_0_0_ceilings(tmp_path: Path) -> None:
    d = tmp_path / "docs" / "superpowers" / "implemented" / "plans" / "shipped"
    d.mkdir(parents=True)
    meta = d / "_meta.yaml"
    meta.write_text("schema_version: 2\nplan: shipped\nfr_version: '>=3.0.0,<4.0.0'\n")
    before = _freeze(meta)

    run_migrations(tmp_path, dry_run=False)

    assert _unchanged(meta, before), "rewriting the archive would falsify history (spec §2)"


def test_the_repair_is_registered_as_a_repair_on_the_plan_kind() -> None:
    assert CEILING_REPAIR in MIGRATIONS.repairs("plan")
    assert MIGRATIONS.schema_migrations("plan") == (), (
        "4.0.0 changes no artifact's SHAPE; a schema migration here would bump "
        "the plan stamp and claim a plan-folder change that did not happen"
    )


# --- `fr migrate artifacts` ---------------------------------------------


def test_fr_migrate_artifacts_is_dry_run_by_default(tmp_path: Path, monkeypatch) -> None:
    meta = _plan(tmp_path, "old", fr_version=">=3.0.0,<4.0.0")
    before = _freeze(meta)
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))

    result = runner_cli.invoke(app, ["migrate", "artifacts"])

    assert result.exit_code == 0, result.output
    assert "_meta.yaml" in result.output
    assert "dry-run" in result.output
    assert _unchanged(meta, before), "dry-run by default, like every other fr mutation"


def test_fr_migrate_artifacts_yes_applies(tmp_path: Path, monkeypatch) -> None:
    meta = _plan(tmp_path, "old", fr_version=">=3.0.0,<4.0.0")
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))

    result = runner_cli.invoke(app, ["migrate", "artifacts", "--yes"])

    assert result.exit_code == 0, result.output
    assert yaml.safe_load(meta.read_text())["fr_version"] == ">=3.0.0,<5.0.0"
    assert "dry-run" not in result.output


def test_fr_migrate_artifacts_reports_nothing_to_do(tmp_path: Path, monkeypatch) -> None:
    _plan(tmp_path, "current", fr_version=">=4.0.0,<5.0.0")
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))

    result = runner_cli.invoke(app, ["migrate", "artifacts", "--yes"])

    assert result.exit_code == 0, result.output
    assert "already current" in result.output


def test_fr_migrate_artifacts_exits_non_zero_when_an_artifact_fails(
    tmp_path: Path, monkeypatch
) -> None:
    _plan(tmp_path, "broken", fr_version=">=3.0.0,<<4.0.0")
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))

    result = runner_cli.invoke(app, ["migrate", "artifacts", "--yes"])

    assert result.exit_code == 2, result.output
