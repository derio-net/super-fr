"""#434 — `--phases-file` silently dropped `phase.tier`: a hardcoded field
whitelist in `plan_cmd.py`'s ingestion loop mirrored an omission in
`PhaseSpec`, one layer upstream of the `extra="forbid"` on `PhaseHeader` that
would otherwise have complained. `acceptance` and `skeleton` survived;
`tier` did not, and nothing failed — the plan scaffolded and looked right.

Task 1 covers the round-trip (class-level, derived from `PhaseHeader.model_fields`,
plus the gh#434 instance). Task 2 covers the pre-flight rejection of an invalid
`tier` value, so a typo does not strand a half-built plan folder (#133's
failure mode).

Every test here drives the real CLI via `typer.testing.CliRunner` + `fr.cli.app`
— never `plan_ops.create()` directly. The defect lives in the CLI ingestion
layer (`plan_cmd.py`'s `--phases-file` loop), so a test that calls `create()`
would have passed throughout #434's life; it is `create()`'s own `PhaseSpec`
construction from the CLI that dropped the field.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml
from fr.cli import app
from fr.types import PhaseHeader
from typer.testing import CliRunner

runner = CliRunner()

# ── shared fixture shape (mirrors tests/unit/test_plan_acceptance_links.py) ─


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir()
    return tmp_path


def _spec(repo: Path) -> Path:
    p = repo / "docs" / "superpowers" / "specs" / "2026-07-04-toy.md"
    p.write_text(
        "# Toy\n\n## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|--|--|--|--|\n"
    )
    return p


def _create_via_cli(repo: Path, phases_file: Path) -> Any:
    return runner.invoke(
        app,
        [
            "plan",
            "create",
            "--slug",
            "2026-07-04-toy",
            "--target-repo",
            "derio-net/own",
            "--spec",
            "docs/superpowers/specs/2026-07-04-toy.md",
            "--phases-file",
            str(phases_file),
        ],
    )


# ── Task 1: the class-level round-trip, derived from PhaseHeader.model_fields ──

# Representative values for every OPTIONAL PhaseHeader field (has a default)
# other than `tracking_issue`, which `--phases-file` has never accepted (it is
# set post-creation via `fr set-tracking-issue`, not at scaffold time). A field
# added to `PhaseHeader` with no entry here fails the test below loudly — the
# same silent-skip shape as the whitelist bug itself, just moved into the test.
_REPRESENTATIVE_VALUES: dict[str, Any] = {
    "depends_on": [1],
    "acceptance": ["row-a"],
    "tier": "hard",
    "skeleton": True,
    "files": ["src/**", "tests/unit/test_x.py"],
    "estimate_lines": 120,
}

# Header keys `_build_phase_doc` writes unconditionally. Everything else is
# emitted ONLY when set, so that plans written before each field existed stay
# byte-stable and still parse on an older, `extra="forbid"` reader. Deriving
# the omission set from this rather than listing the omitted fields means a
# new optional field that someone emits unconditionally fails the test below,
# which is the half of #434's contract that has no other guard.
_ALWAYS_EMITTED = {"number", "title", "tag", "depends_on", "tracking_issue"}


def _optional_header_fields() -> list[str]:
    return [
        name
        for name, info in PhaseHeader.model_fields.items()
        if not info.is_required() and name != "tracking_issue"
    ]


def test_every_optional_phase_header_field_survives_phases_file(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Both halves of the contract, derived from the model rather than listed.

    Two phases: the second carries every optional field (and so must round-trip
    each one), the first carries none (and so must OMIT every field that is not
    unconditionally emitted). `depends_on: [1]` lives on phase 2 deliberately —
    on phase 1 it would be a self-dependency, which is invalid per the plan's
    backward-only rule and would break confusingly the day
    `_preflight_phase_error` grows a cycle check.
    """
    optional_fields = _optional_header_fields()
    missing_from_table = [f for f in optional_fields if f not in _REPRESENTATIVE_VALUES]
    assert not missing_from_table, (
        f"PhaseHeader gained optional field(s) {missing_from_table} with no "
        "representative value in this test's table — add one here before "
        "trusting --phases-file to round-trip it (this is exactly how #434 "
        "happened: a field the ingestion whitelist never learned about)."
    )

    repo = _repo(tmp_path)
    _spec(repo)
    bare: dict[str, Any] = {
        "number": 1,
        "title": "Bare",
        "tasks": [{"number": 1, "title": "t", "steps": [{"id": "P1.T1.S1", "text": "s"}]}],
    }
    loaded: dict[str, Any] = {
        "number": 2,
        "title": "Loaded",
        "tasks": [{"number": 1, "title": "t", "steps": [{"id": "P2.T1.S1", "text": "s"}]}],
    }
    for field in optional_fields:
        loaded[field] = _REPRESENTATIVE_VALUES[field]

    phases_file = tmp_path / "phases.yaml"
    phases_file.write_text(yaml.dump([bare, loaded]))
    monkeypatch.chdir(repo)
    # `files`/`estimate_lines` floor fr_version at 4.20.0, and create re-parses
    # what it wrote against the installed fr — which may predate the release.
    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "4.20.0")

    result = _create_via_cli(repo, phases_file)
    assert result.exit_code == 0, result.output

    plan_dir = repo / "docs" / "superpowers" / "plans" / "2026-07-04-toy"
    loaded_header = yaml.safe_load((plan_dir / "02.yaml").read_text())["phase"]
    bare_header = yaml.safe_load((plan_dir / "01.yaml").read_text())["phase"]

    for field in optional_fields:
        assert field in loaded_header, (
            f"{field!r} did not survive --phases-file — header: {loaded_header!r}"
        )
        assert loaded_header[field] == _REPRESENTATIVE_VALUES[field]

    for field in optional_fields:
        if field in _ALWAYS_EMITTED:
            continue
        assert field not in bare_header, (
            f"{field!r} was emitted on a phase that never set it, so every plan "
            "written before the field existed now differs — header: "
            f"{bare_header!r}"
        )


def test_tier_survives_phases_file(tmp_path: Path, monkeypatch: Any) -> None:
    """The gh#434 instance: a phases file carrying `tier: hard` must reach the
    dumped phase header, not be silently dropped."""
    repo = _repo(tmp_path)
    _spec(repo)
    phases_file = tmp_path / "phases.yaml"
    phases_file.write_text(
        "- number: 1\n  title: One\n  tier: hard\n"
        "  tasks:\n    - number: 1\n      title: t\n"
        "      steps:\n        - id: P1.T1.S1\n          text: s\n"
    )
    monkeypatch.chdir(repo)

    result = _create_via_cli(repo, phases_file)
    assert result.exit_code == 0, result.output

    doc = yaml.safe_load(
        (repo / "docs" / "superpowers" / "plans" / "2026-07-04-toy" / "01.yaml").read_text()
    )
    assert doc["phase"]["tier"] == "hard"


# ── Task 2: an invalid tier is refused pre-flight, not after the folder exists ──


def test_an_invalid_tier_is_refused_without_stranding_the_folder(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """A typo'd `tier: hrad` must be refused before any plan folder is
    written (#133's failure mode: a post-write schema rejection strands a
    half-built folder that then blocks the corrected re-run)."""
    repo = _repo(tmp_path)
    _spec(repo)
    phases_file = tmp_path / "phases.yaml"
    phases_file.write_text(
        "- number: 1\n  title: One\n  tier: hrad\n"
        "  tasks:\n    - number: 1\n      title: t\n"
        "      steps:\n        - id: P1.T1.S1\n          text: s\n"
    )
    monkeypatch.chdir(repo)

    result = _create_via_cli(repo, phases_file)

    assert result.exit_code != 0
    assert "hrad" in result.output
    assert "mechanical" in result.output and "standard" in result.output and "hard" in result.output
    assert not (repo / "docs" / "superpowers" / "plans" / "2026-07-04-toy").exists()
