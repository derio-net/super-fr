"""The `ops` kind's 1 -> 2 hop: the `none:` acknowledgement (spec
2026-11-01-ops-gate-probes R4). Stamp-only: every version-1 file is a valid version-2
file, so the body is kept byte for byte and only the stamp moves."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fr.artifacts import MIGRATIONS, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION

V1 = (
    "schema_version: 1\n"
    "# a comment the operator wrote\n"
    "ops:\n"
    "  - {id: a, summary: s, phase: pre-merge, check: 'true'}\n"
)


def _repo(tmp_path: Path, text: str) -> Path:
    repo = tmp_path / "repo"
    path = repo / "docs/superpowers/plans/p/ops.yaml"
    path.parent.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    path.write_text(text)
    return path


def test_the_ops_chain_is_one_hop_to_two() -> None:
    chain = MIGRATIONS.chain("ops", PRE_FRAMEWORK_VERSION)
    assert [s.to_version for s in chain] == [2]


def test_a_v1_ops_yaml_migrates_stamp_only(tmp_path: Path) -> None:
    path = _repo(tmp_path, V1)
    report = run_migrations(path.parents[4], dry_run=False)
    assert report.ok, report.failed
    assert path.read_text() == V1.replace("schema_version: 1", "schema_version: 2", 1)


def test_a_v1_file_carrying_none_is_refused_byte_identical(tmp_path: Path) -> None:
    text = "schema_version: 1\nnone: written by hand\n"
    path = _repo(tmp_path, text)
    report = run_migrations(path.parents[4], dry_run=False)
    assert not report.ok
    assert path.read_text() == text
