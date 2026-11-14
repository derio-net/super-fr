"""The `acceptance-fragment` kind's 1 -> 2 hop: the `local` status and its stamp
(spec 2026-11-14-acceptance-local-status R7, §E). Stamp only."""

from __future__ import annotations

from pathlib import Path

import fr.artifacts  # noqa: F401  (registration rides on the package import)
from fr.artifacts.registry import ARTIFACT_KINDS
from fr.artifacts.runner import MIGRATIONS, run_migrations
from fr.artifacts.structure import validate_fragment

BODY = """\
feature: f
repo: o/demo
rows:
  - id: r1
    capability: C
    acceptance: a
    origin: []
    levels: {}
    status: unwired
    notes: n
"""

LOCAL_ROW = """\
  - id: r2
    capability: C
    acceptance: a
    origin: []
    levels:
      unit:
      - demo:tests/test_x.py
    status: {status}
    notes: n
    local:
      at: '2026-11-14'
      tree: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
      log: suite.log@0123456789ab
      files:
        {files}
"""


def _fragment(root: Path, text: str) -> Path:
    path = root / "docs" / "acceptance" / "features" / "f.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_fragment_kind_is_at_version_two() -> None:
    assert ARTIFACT_KINDS["acceptance-fragment"].current_version == 2


def test_the_fragment_chain_from_one_reaches_two_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("acceptance-fragment", 1)
    assert [(m.from_version, m.to_version) for m in chain] == [(1, 2)]
    assert chain[0].fn.__module__ == "fr.artifacts.fragment_local"


def test_a_v1_fragment_migrates_by_its_stamp_alone(tmp_path: Path) -> None:
    path = _fragment(tmp_path, "schema_version: 1\n" + BODY)
    report = run_migrations(tmp_path, dry_run=False)
    assert report.ok, report.failed
    assert path.read_text() == "schema_version: 2\n" + BODY


def test_a_v1_fragment_already_holding_local_is_refused_and_left_alone(tmp_path: Path) -> None:
    text = "schema_version: 1\n" + BODY + LOCAL_ROW.format(status="local", files="t.py: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    path = _fragment(tmp_path, text)
    report = run_migrations(tmp_path, dry_run=False)
    assert not report.ok
    assert path.read_text() == text


def test_the_validator_accepts_a_well_formed_stamp(tmp_path: Path) -> None:
    text = "schema_version: 2\n" + BODY + LOCAL_ROW.format(status="local", files="t.py: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    assert validate_fragment(_fragment(tmp_path, text)) == []


def test_the_validator_refuses_a_malformed_stamp(tmp_path: Path) -> None:
    text = "schema_version: 2\n" + BODY + LOCAL_ROW.format(status="local", files="{}")
    problems = validate_fragment(_fragment(tmp_path, text))
    assert problems and any("local" in p for p in problems)


def test_the_validator_refuses_a_stamp_on_a_row_that_is_not_local(tmp_path: Path) -> None:
    text = "schema_version: 2\n" + BODY + LOCAL_ROW.format(status="unwired", files="t.py: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    problems = validate_fragment(_fragment(tmp_path, text))
    assert problems and any("r2" in p and "local" in p for p in problems)


def test_the_validator_refuses_a_stamp_on_a_set_status_that_is_not_local(tmp_path: Path) -> None:
    text = (
        "schema_version: 2\n" + BODY + "amendments:\n"
        "  - row: r1\n    op: set-status\n    base: 0\n    status: ci\n    notes: n\n"
        "    local: {at: '2026-11-14', tree: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa, log: suite.log@0123456789ab, files: {t.py: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb}}\n    why: w\n"
    )
    problems = validate_fragment(_fragment(tmp_path, text))
    assert problems and any("r1" in p and "local" in p for p in problems)
