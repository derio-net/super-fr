"""Phase 3 of 2026-09-24-fr-goal-scope-proportion-cost (spec §C): the two
optional phase-header fields the proportionality report reads.

- `files` (repo-relative globs) and `estimate_lines` (expected added+deleted
  lines) follow the `tier`/`skeleton`/`acceptance` precedent: optional,
  defaulted, omitted from written phase files when unset, and NO plan stamp
  bump — a plan that uses them raises its `fr_version` floor instead.
- `fr plan create` writes that floor (4.20.0) and refuses an explicit
  constraint that would let an older fr try to read the plan.
- `fr plan self-review` warns on an agentic phase with no `files`, and
  errors when the fields ride under a pre-4.20 `fr_version`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from fr.cli import app
from fr.parser import parse as parse_plan
from fr.plan_ops import PhaseSpec, create, self_review
from fr.types import PhaseHeader
from pydantic import ValidationError
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()

SCOPED_PHASES = (
    "- number: 1\n  title: One\n  tier: standard\n  skeleton: true\n"
    "  files: ['packages/fr/src/fr/*.py', 'tests/unit/test_x.py']\n"
    "  estimate_lines: 120\n"
    "  tasks:\n    - number: 1\n      title: t\n"
    "      steps:\n        - id: P1.T1.S1\n          text: s\n"
)
PLAIN_PHASES = (
    "- number: 1\n  title: One\n  tier: standard\n  skeleton: true\n"
    "  tasks:\n    - number: 1\n      title: t\n"
    "      steps:\n        - id: P1.T1.S1\n          text: s\n"
)


def _repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "plans").mkdir()
    return tmp_path


def _cli_create(repo: Path, monkeypatch: pytest.MonkeyPatch, phases_yaml: str, *extra: str):
    phases_file = repo / "phases.yaml"
    phases_file.write_text(phases_yaml)
    monkeypatch.chdir(repo)
    return runner.invoke(
        app,
        [
            "plan",
            "create",
            "--slug",
            "2026-09-24-toy",
            "--target-repo",
            "derio-net/own",
            "--phases-file",
            str(phases_file),
            *extra,
        ],
    )


def _plan_dir(repo: Path) -> Path:
    return repo / "docs" / "superpowers" / "plans" / "2026-09-24-toy"


# ── the model ────────────────────────────────────────────────────────────────


def test_phase_header_accepts_files_and_estimate_lines() -> None:
    h = PhaseHeader(
        number=1,
        title="t",
        tag="agentic",
        files=("a/*.py", "b.md"),
        estimate_lines=40,
    )

    assert h.files == ("a/*.py", "b.md")
    assert h.estimate_lines == 40


def test_phase_header_defaults_leave_both_fields_unset() -> None:
    h = PhaseHeader(number=1, title="t", tag="agentic")

    assert h.files == ()
    assert h.estimate_lines is None


def test_a_negative_estimate_is_refused() -> None:
    with pytest.raises(ValidationError):
        PhaseHeader(number=1, title="t", tag="agentic", estimate_lines=-1)


def test_an_archived_plans_headers_still_validate_without_the_fields() -> None:
    """Round-trip over real, frozen plan files: every archived phase header
    validates on the widened model and gains neither field when dumped
    without defaults — the byte-stability the precedent promises."""
    archived = REPO_ROOT / "docs" / "superpowers" / "implemented" / "plans" / "opencode-adaptation"
    phase_files = sorted(archived.glob("[0-9][0-9].yaml"))
    assert phase_files, "fixture plan went missing"
    for f in phase_files:
        raw = yaml.safe_load(f.read_text())["phase"]
        dumped = PhaseHeader.model_validate(raw).model_dump(exclude_defaults=True)
        assert "files" not in dumped and "estimate_lines" not in dumped
        assert "files" not in raw and "estimate_lines" not in raw


def test_create_omits_both_fields_when_unset(tmp_path: Path) -> None:
    plan = create(
        repo_root=tmp_path,
        slug="2026-09-24-plain",
        spec=None,
        target_repo="derio-net/test",
        fr_version=">=4.2.0,<5.0.0",
        phases=[PhaseSpec(number=1, title="Build", tag="agentic", skeleton=True)],
        prose="# x\n",
    )

    text = (plan.dir / "01.yaml").read_text()
    assert "files" not in text
    assert "estimate_lines" not in text


# ── fr plan create: the fr_version floor ─────────────────────────────────────


def test_create_floors_fr_version_when_a_phase_sets_the_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The floor names the release that ships the fields; until the bump lands
    # the installed fr is older, so pretend it has (create re-parses the plan).
    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "4.20.0")
    repo = _repo(tmp_path)

    result = _cli_create(repo, monkeypatch, SCOPED_PHASES)

    assert result.exit_code == 0, result.output
    meta = (_plan_dir(repo) / "_meta.yaml").read_text()
    assert "fr_version: '>=4.20.0,<5.0.0'" in meta
    header = yaml.safe_load((_plan_dir(repo) / "01.yaml").read_text())["phase"]
    assert header["files"] == ["packages/fr/src/fr/*.py", "tests/unit/test_x.py"]
    assert header["estimate_lines"] == 120
    parsed = parse_plan(_plan_dir(repo))
    assert parsed.phases[0].phase.estimate_lines == 120


def test_create_floors_when_only_estimate_lines_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "4.20.0")
    repo = _repo(tmp_path)
    phases = PLAIN_PHASES.replace("  tasks:", "  estimate_lines: 10\n  tasks:")

    result = _cli_create(repo, monkeypatch, phases)

    assert result.exit_code == 0, result.output
    assert "'>=4.20.0,<5.0.0'" in (_plan_dir(repo) / "_meta.yaml").read_text()


def test_create_refuses_an_explicit_constraint_admitting_a_pre_4_20_fr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mirrors the `--workflow` refusal: an explicit constraint is the
    operator's, so it is refused rather than rewritten."""
    repo = _repo(tmp_path)

    result = _cli_create(repo, monkeypatch, SCOPED_PHASES, "--fr-version", ">=4.0.0,<5.0.0")

    assert result.exit_code == 2, result.output
    assert "4.20.0" in result.output
    assert not _plan_dir(repo).exists()


def test_create_refuses_an_exact_pre_4_20_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)

    result = _cli_create(repo, monkeypatch, SCOPED_PHASES, "--fr-version", "==4.5.0")

    assert result.exit_code == 2, result.output


def test_create_leaves_fr_version_alone_without_the_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)

    result = _cli_create(repo, monkeypatch, PLAIN_PHASES)

    assert result.exit_code == 0, result.output
    assert "fr_version: '>=3.0.0,<5.0.0'" in (_plan_dir(repo) / "_meta.yaml").read_text()


# ── fr plan self-review ──────────────────────────────────────────────────────


def _programmatic(tmp_path: Path, *, fr_version: str, **fields) -> Path:
    """`create()` itself does not floor (the CLI does), which is exactly how a
    plan carrying the fields under a too-low constraint comes to exist."""
    return create(
        repo_root=tmp_path,
        slug="2026-09-24-direct",
        spec=None,
        target_repo="derio-net/test",
        fr_version=fr_version,
        phases=[
            PhaseSpec(
                number=1, title="Build", tag="agentic", skeleton=True, tier="standard", **fields
            ),
            PhaseSpec(number=2, title="Hands", tag="manual"),
        ],
        prose="# x\n",
    ).dir


def _messages(plan_dir: Path, needle: str) -> list:
    return [i for i in self_review(parse_plan(plan_dir)) if needle in i.message]


def test_self_review_warns_on_an_agentic_phase_with_no_files(tmp_path: Path) -> None:
    issues = _messages(_programmatic(tmp_path, fr_version=">=4.2.0,<5.0.0"), "lists no files")

    assert [i.severity for i in issues] == ["warn"], issues
    assert "phase 1" in issues[0].message


def test_self_review_is_silent_about_files_on_a_manual_phase(tmp_path: Path) -> None:
    issues = _messages(_programmatic(tmp_path, fr_version=">=4.2.0,<5.0.0"), "phase 2")

    assert not [i for i in issues if "files" in i.message], issues


def test_self_review_errors_when_the_fields_ride_a_pre_4_20_fr_version(
    tmp_path: Path,
) -> None:
    plan_dir = _programmatic(tmp_path, fr_version=">=3.0.0,<5.0.0", files=("a/*.py",))

    floor = _messages(plan_dir, "4.20.0")

    assert [i.severity for i in floor] == ["error"], floor
    assert not _messages(plan_dir, "lists no files")


def test_self_review_floor_also_catches_estimate_lines_alone(tmp_path: Path) -> None:
    plan_dir = _programmatic(tmp_path, fr_version=">=3.0.0,<5.0.0", estimate_lines=5)

    assert [i.severity for i in _messages(plan_dir, "4.20.0")] == ["error"]


def test_self_review_has_no_floor_issue_under_a_4_20_floor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("fr.parser.INSTALLED_FR_VERSION", "4.20.0")
    plan_dir = _programmatic(tmp_path, fr_version=">=4.20.0,<5.0.0", files=("a/*.py",))

    assert not _messages(plan_dir, "4.20.0")


# ── review p3-f3: exact pins between probes ──────────────────────────────────


@pytest.mark.parametrize("pin", ["==4.19.3", "==4.5.0", "===4.19.7", "==4.19.3,<5"])
def test_create_refuses_an_exact_pre_4_20_pin_between_probes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pin: str
) -> None:
    """A probe list only answers for the versions in it; an exact pin is
    compared directly, so `==4.19.3` cannot slip between `4.19.2` and `4.19.999`."""
    repo = _repo(tmp_path)

    result = _cli_create(repo, monkeypatch, SCOPED_PHASES, "--fr-version", pin)

    assert result.exit_code == 2, result.output


@pytest.mark.parametrize("constraint", ["==4.5.0", ">=4.0,<4.10", "==4.19.3", "~=4.3"])
def test_self_review_floor_catches_constraints_that_exclude_4_19_99(
    tmp_path: Path, constraint: str
) -> None:
    """Probing only 4.19.99 passed every constraint that happens to exclude it
    while still admitting an older fr."""
    plan_dir = _programmatic(tmp_path, fr_version=">=3.0.0,<5.0.0", files=("a/*.py",))
    meta = plan_dir / "_meta.yaml"
    meta.write_text(meta.read_text().replace("'>=3.0.0,<5.0.0'", repr(constraint)))

    floor = [
        i
        for i in self_review(parse_plan(plan_dir, enforce_fr_version=False))
        if "4.20.0" in i.message
    ]

    assert [i.severity for i in floor] == ["error"], (constraint, floor)
