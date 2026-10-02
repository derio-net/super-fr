"""The `fr_version` ceiling of a NEW plan is derived from the installed major.

Debug journal `2026-09-29-derive-fr-version-ceiling`. 4.0.0 wrote `<5.0.0` as a
literal in `plan_cmd.py` and six other places; 5.0.0 then refused every plan it
wrote (`requires fr_version >=4.20.0,<5.0.0 but installed is 5.0.0`) and the
suite went 414 red — while `main`'s CI looked green, because the release commit
triggers none. Nothing recomputed the ceiling when the major moved.

Pinned here, so the NEXT major cannot repeat it:

- one derivation (`fr.version_floor.ceiling_for`), and the default, `--workflow`
  and files/estimate_lines paths of `fr plan create` all parse at the installed
  fr (the scope path is the one every fr-goal run takes at its `plan` step);
- the parse error never tells a user to install an OLDER fr;
- `scripts/floors.py` still sees a derived floor's lower bound, so
  `check-change-fragment` and `release.py` keep checking it;
- no `>=X,<Y` literal survives in `packages/*/src` (tripwire).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from fr.cli import app
from fr.parser import INSTALLED_FR_VERSION, PlanSchemaError, parse
from packaging.version import Version
from typer.testing import CliRunner

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("floors", REPO / "scripts" / "floors.py")
assert _spec and _spec.loader
floors = importlib.util.module_from_spec(_spec)
sys.modules["floors"] = floors
_spec.loader.exec_module(floors)

SLUG = "2026-09-29-toy"
SCOPED_PHASES = (
    "- number: 1\n  title: One\n  tier: standard\n  skeleton: true\n"
    "  files: ['packages/fr/src/fr/*.py']\n  estimate_lines: 40\n"
    "  tasks:\n    - number: 1\n      title: t\n"
    "      steps:\n        - id: P1.T1.S1\n          text: s\n"
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@x"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True)
    (repo / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "plans").mkdir()
    return repo


def _create(repo: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.chdir(repo)
    return CliRunner().invoke(
        app, ["plan", "create", "--slug", SLUG, "--target-repo", "o/r", *args]
    )


def _plan_dir(repo: Path) -> Path:
    return repo / "docs" / "superpowers" / "plans" / SLUG


# ── one derivation ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("installed", "ceiling"),
    [("4.40.1", "5.0.0"), ("5.0.0", "6.0.0"), ("5.0.1", "6.0.0"), ("6.2.0.dev1", "7.0.0")],
)
def test_the_ceiling_is_the_next_major(installed: str, ceiling: str) -> None:
    from fr.version_floor import ceiling_for

    assert ceiling_for(installed) == ceiling


def test_the_module_ceiling_tracks_the_installed_major() -> None:
    from fr.version_floor import CEILING_VERSION, ceiling_for

    assert CEILING_VERSION == ceiling_for(INSTALLED_FR_VERSION)
    assert Version(INSTALLED_FR_VERSION) < Version(CEILING_VERSION)


def test_the_repair_and_the_defaults_share_one_formula() -> None:
    """`widen_ceiling` (existing plans) and the defaults (new plans) once each
    carried their own `major + 1`; the defaults' copy was the literal."""
    from fr.artifacts.fr_version import widen_ceiling
    from fr.version_floor import ceiling_for

    assert widen_ceiling(">=3.0.0,<5.0.0", Version("5.3.0")) == f">=3.0.0,<{ceiling_for('5.3.0')}"


# ── every `fr plan create` path parses at the installed fr ───────────────────


def test_create_default_path_parses_at_the_installed_fr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)

    result = _create(repo, monkeypatch)

    assert result.exit_code == 0, result.output
    parse(_plan_dir(repo))  # enforces fr_version against the installed fr


def test_create_scope_path_parses_at_the_installed_fr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The path that fired live: fr-plan asks every phase for files/estimate_lines,
    so this is the constraint every fr-goal run writes at its `plan` step."""
    from fr.version_floor import CEILING_VERSION

    repo = _repo(tmp_path)
    phases = repo / "phases.yaml"
    phases.write_text(SCOPED_PHASES)

    result = _create(repo, monkeypatch, "--phases-file", str(phases))

    assert result.exit_code == 0, result.output
    assert (
        f"fr_version: '>=4.20.0,<{CEILING_VERSION}'" in (_plan_dir(repo) / "_meta.yaml").read_text()
    )
    parse(_plan_dir(repo))


def test_create_workflow_path_parses_at_the_installed_fr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.version_floor import CEILING_VERSION

    repo = _repo(tmp_path)

    result = _create(repo, monkeypatch, "--workflow", "fr-goal-phase-dispatch")

    assert result.exit_code == 0, result.output
    assert (
        f"fr_version: '>=4.0.0,<{CEILING_VERSION}'" in (_plan_dir(repo) / "_meta.yaml").read_text()
    )
    parse(_plan_dir(repo))


# ── the parse error never advises a downgrade ────────────────────────────────


def _plan_with(tmp_path: Path, constraint: str) -> Path:
    plan_dir = tmp_path / "p"
    plan_dir.mkdir()
    (plan_dir / "_meta.yaml").write_text(
        "schema_version: 2\n"
        f"plan: {SLUG}\n"
        "target_repo: o/r\n"
        "created: '2026-09-29'\n"
        f'fr_version: "{constraint}"\n'
    )
    return plan_dir


@pytest.mark.parametrize("constraint", [">=3.0.0,<5.0.0", ">=4.20.0,<=4.99.0", "==4.0.0"])
def test_a_plan_the_installed_fr_has_outgrown_points_at_migrate_not_a_downgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, constraint: str
) -> None:
    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "5.0.0")

    with pytest.raises(PlanSchemaError) as e:
        parse(_plan_with(tmp_path, constraint))

    msg = str(e.value)
    assert f"requires fr_version {constraint}" in msg
    assert "fr migrate artifacts --yes" in msg
    assert "uv tool install" not in msg
    assert "To upgrade" not in msg


@pytest.mark.parametrize("constraint", [">=99.0.0,<100.0.0", ">5.0.0", ">=4.0.0,>5.0.0"])
def test_a_plan_that_needs_a_newer_fr_still_says_to_upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, constraint: str
) -> None:
    """`>5.0.0` under 5.0.0 is a LOWER bound sitting exactly on the installed fr:
    `fr migrate artifacts` treats `>` as a floor problem and does nothing, so
    saying "run migrate" would leave the user stuck (review of this fix)."""
    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "5.0.0")

    with pytest.raises(PlanSchemaError) as e:
        parse(_plan_with(tmp_path, constraint))

    assert "To upgrade" in str(e.value)
    assert "fr migrate artifacts" not in str(e.value)


# ── scripts/floors.py still sees a derived floor ─────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        '>=4.20.0,<{CEILING_VERSION}"',  # 3.11: the whole f-string is one STRING token
        ">=4.20.0,<",  # 3.12+: FSTRING_MIDDLE stops where the replacement field starts
    ],
)
def test_floors_sees_the_lower_bound_of_a_derived_floor(text: str) -> None:
    found = floors._floors_in(text, 1)

    assert [(f.lower, f.upper) for f in found] == [("4.20.0", None)]


def test_floors_sees_a_derived_floor_in_real_source() -> None:
    source = 'X = 1\nSCOPE = f">=4.20.0,<{CEILING_VERSION}"\nHINT = f"floor at >=3.12.0,<{C}."\n'

    assert [(f.lower, f.line) for f in floors.floors_in_source(source)] == [
        ("4.20.0", 2),
        ("3.12.0", 3),
    ]


def test_an_unreleased_derived_floor_is_still_checked() -> None:
    after = 'SCOPE = f">=4.99.0,<{CEILING_VERSION}"\n'

    [floor] = floors.new_floors('SCOPE = f">=4.20.0,<{CEILING_VERSION}"\n', after)

    assert not floors.lower_bound_ok(floor.lower, "4.40.1", "4.41.0")
    assert floors.lower_bound_ok(floor.lower, "4.40.1", "4.99.0")


# ── tripwire ─────────────────────────────────────────────────────────────────


def test_no_hardcoded_fr_version_ceiling_survives_in_package_source() -> None:
    """A `>=X,<Y` literal in `packages/*/src` is the bug: it strands at the next
    major. Derive the ceiling (`fr.version_floor.CEILING_VERSION`) and keep the
    lower bound literal — `f">=4.20.0,<{CEILING_VERSION}"`."""
    hard = [
        f"{rel}:{f.line}: >={f.lower},<{f.upper}"
        for rel, f in floors.scan_floors(REPO)
        if f.upper is not None
    ]

    assert hard == [], "hardcoded fr_version ceiling(s):\n  " + "\n  ".join(hard)


def test_no_shortened_ceiling_literal_slips_past_the_floor_scan() -> None:
    """`floors.FLOOR_RE` wants three dotted parts, so `">=4.20.0,<5"` or `<5.0`
    would pass the tripwire above yet strand at the next major all the same.
    This one reads raw text (comments included) for `>=…,<` followed by ANY digit;
    a derived ceiling is `<{`, which it does not match."""
    import re

    loose = re.compile(r">=\s*\d[\d.]*\s*,\s*<=?\s*\d")
    hits = [
        f"{path.relative_to(REPO).as_posix()}:{n}: {line.strip()}"
        for path in sorted((REPO / "packages").glob("*/src/**/*.py"))
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if loose.search(line)
    ]

    assert hits == [], "hardcoded fr_version ceiling(s):\n  " + "\n  ".join(hits)


# ── an explicit --fr-version must admit the installed fr, checked before writing (#855) ──


@pytest.mark.parametrize("constraint", [">=4.20.0,<5.0.0", ">=99.0.0", "==4.0.0"])
def test_an_explicit_constraint_excluding_the_installed_fr_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, constraint: str
) -> None:
    """Live: `--fr-version '>=4.20.0,<5.0.0'` on fr 5.0.1 wrote the plan dir, its
    journal and the validator wrapper, then failed its own re-parse and left all
    three staged and uncommitted."""
    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "5.0.0")
    repo = _repo(tmp_path)
    before = sorted(p.relative_to(repo) for p in repo.rglob("*") if ".git" not in p.parts)

    result = _create(repo, monkeypatch, "--fr-version", constraint)

    assert result.exit_code == 2, result.output
    assert "5.0.0" in result.output and constraint in result.output
    after = sorted(p.relative_to(repo) for p in repo.rglob("*") if ".git" not in p.parts)
    assert after == before
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
    )
    assert status.stdout == ""


# ── a pre-release installed fr is inside a spec that spans it (#855) ───────────


def _packaging_25_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """What `installed in spec` meant before packaging 26: a pre-release is
    excluded unless the spec names one. fr declares `packaging>=24`, so an
    install may still resolve that behaviour."""
    from packaging.specifiers import SpecifierSet

    monkeypatch.setattr(
        SpecifierSet, "__contains__", lambda self, item: self.contains(item, prereleases=False)
    )


def test_a_dev_install_parses_a_plan_whose_spec_spans_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _packaging_25_default(monkeypatch)
    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "5.0.1.dev0")

    parse(_plan_with(tmp_path, ">=4,<6"))


def test_the_repair_agrees_with_the_parser_about_a_dev_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fr.artifacts.fr_version import widen_ceiling

    _packaging_25_default(monkeypatch)

    assert widen_ceiling(">=4,<6", Version("5.0.1.dev0")) is None
    assert widen_ceiling(">=4,<5.0.0", Version("5.0.1.dev0")) == ">=4,<6.0.0"


def test_no_bare_specifier_membership_test_survives_in_src() -> None:
    """Tripwire: `x in SpecifierSet(...)` leaves pre-release handling to the
    library default, which moved in packaging 26. Use `fr.version_floor.admits`."""
    import re

    bare = re.compile(r"\bin SpecifierSet\(|\binstalled (?:not )?in \w")
    hits = [
        f"{p.relative_to(REPO)}:{n}"
        for p in (REPO / "packages").glob("*/src/**/*.py")
        for n, line in enumerate(p.read_text().splitlines(), 1)
        if bare.search(line.split("#", 1)[0])
    ]
    assert hits == []
