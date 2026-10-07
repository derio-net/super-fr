"""The `usage` kind's 1 -> 2 migration (cost-evidence spec §C, R5).

Stamp-only: a v1 body reads with the live model (the new sections are absent,
which means "not observed"); a file that does not parse is refused and left
byte-identical. Every writer of a NEW usage file stamps the current version.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.artifacts import ARTIFACT_KINDS, MIGRATIONS, run_migrations
from fr.artifacts.registry import read_version
from fr.artifacts.structure import validate_usage
from fr.usage.file import UsageFile, parse_usage

V1 = """schema_version: 1
run: r1
captures:
  - host: h-3f9a2c1e
    harness: claude-code
    mode: host-worktree
    captured_at: '2026-10-06T00:00:00+00:00'
    at: [deliver]
    sessions:
      - session: s-one
        unavailable: no session found
"""


def _seed(root: Path, text: str) -> Path:
    path = root / "docs" / "superpowers" / "usage" / "r1.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_usage_kind_is_at_two_and_one_hop_reaches_it() -> None:
    assert ARTIFACT_KINDS["usage"].current_version == 2
    chain = MIGRATIONS.chain("usage", 1)
    assert [(m.from_version, m.to_version) for m in chain] == [(1, 2)]
    assert [m.to_version for m in chain] == [2]


def test_a_v1_file_is_stamped_two_and_its_body_is_untouched(tmp_path: Path) -> None:
    path = _seed(tmp_path, V1)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.failed == (), report.failed
    assert read_version("usage", path) == 2
    assert path.read_text() == V1.replace("schema_version: 1", "schema_version: 2")
    assert parse_usage(path.read_text()).captures[0].sessions[0].steps_by_role == {}


def test_an_unparseable_body_is_refused_and_left_byte_identical(tmp_path: Path) -> None:
    broken = V1 + "nonsense_key: 1\n"
    path = _seed(tmp_path, broken)

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [path]
    assert "version-1" in report.failed[0].error
    assert path.read_text() == broken


def test_a_fresh_file_is_born_stamped_with_the_current_version() -> None:
    from fr.usage.file import current_usage_schema_version

    assert current_usage_schema_version() == ARTIFACT_KINDS["usage"].current_version
    assert UsageFile(run="r").schema_version == 1  # an unstamped file still reads as v1


# --- every writer of a new file stamps explicitly --------------------------------

SPLIT = """      - session: s-one
        models: {}
        activity: {}
        steps: {}
        %s
"""


def _file(extra: str) -> str:
    return V1.replace("        unavailable: no session found\n", SPLIT % extra).replace(
        "schema_version: 1", "schema_version: 2"
    )


@pytest.mark.parametrize(
    ("extra", "needle"),
    [
        ("steps_by_role: {admin: {x: {usd: null, turns: 1}}}", "role"),
        ("units: {not-a-unit: {executor: {usd: null, turns: 1}}}", "unit"),
        ("units: {phase/1/implement-phase: {boss: {usd: null, turns: 1}}}", "role"),
        ("steps_by_role: {main: {x: {usd: null, turns: -1}}}", "negative"),
        ("units: {(unattributed): {subagent: {usd: -0.5, turns: 1}}}", "negative"),
        ("units: {(unattributed): {subagent: {usd: null, turns: 1, output: -3}}}", "negative"),
    ],
)
def test_the_validator_refuses_a_bad_role_unit_key_or_negative_figure(
    tmp_path: Path, extra: str, needle: str
) -> None:
    problems = validate_usage(_seed(tmp_path, _file(extra)))
    assert any(needle in p for p in problems), problems


def test_the_validator_accepts_a_well_formed_split(tmp_path: Path) -> None:
    extra = (
        "steps_by_role: {main: {brainstorm: {usd: 0.5, turns: 2, input: 1}}, "
        "subagent: {implement: {usd: null, turns: 1}}}\n        "
        "units: {step/spec-review: {agent: {usd: null, turns: 1}}, "
        "phase/1/review-phase: {reviewer: {usd: 1.0, turns: 1}, orchestrator: {turns: 1}}, "
        "(unattributed): {subagent: {usd: null, turns: 1}}}"
    )
    assert validate_usage(_seed(tmp_path, _file(extra))) == []
