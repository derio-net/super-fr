"""The `matrix` kind's 4 -> 5 migration (spec `2026-10-11-debt-engine-design.md`
§D, R6): `skipped` splits into `unwired` / `walk-owed` / `walked` / `manual`.

A status REMOVAL, so the full artifact-versioning rule applies: the frozen
`MatrixV4` on every hop, one in-memory build written atomically (the body and
its committed reports together), the crash window recognised, a refused file
left byte-identical, and every hop of the chain asserted.
"""

from __future__ import annotations

import hashlib
import inspect
import subprocess
from pathlib import Path

import pytest
from fr.acceptance.model import AcceptanceError, load_matrix, parse_matrix
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION

_WALK = """\
    walks:
      - strategy: live
        harness: claude-code
        model: m
        outcome: pass
        at: "2026-10-01T10:00:00+00:00"
        evidence: "walked by hand"
"""

_HEAD = """\
# header comment — must survive
schema_version: 4
org: acme
repo: widget
rows:
"""

_ROWS = {
    "walked-row": """\
  - id: walked-row
    capability: "Cap"
    acceptance: "A passing walk makes it walked"
    status: skipped
    notes: "status: skipped is quoted in this note and must stay"
    verify: live
"""
    + _WALK,
    "owed-row": """\
  - id: owed-row
    capability: "Cap"
    acceptance: "A post-merge strategy without a pass owes a walk"
    status: 'skipped'   # a trailing comment
    verify: live
""",
    "plain-row": """\
  - id: plain-row
    capability: "Cap"
    acceptance: "No verify, no walk: unwired"
    status: skipped
""",
    "pre-row": """\
  - id: pre-row
    capability: "Cap"
    acceptance: "A pre-merge strategy is not a walk owed"
    status: skipped
    verify: candidate
""",
    "ci-row": """\
  - id: ci-row
    capability: "Cap"
    acceptance: "Other statuses are untouched"
    status: ci
""",
}

_V4 = _HEAD + "".join(_ROWS.values())
_EXPECTED = {
    "walked-row": "walked",
    "owed-row": "walk-owed",
    "plain-row": "unwired",
    "pre-row": "unwired",
    "ci-row": "ci",
}


def _matrix(root: Path, text: str = _V4) -> Path:
    path = root / "docs" / "acceptance" / "matrix.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_matrix_kind_is_at_version_five() -> None:
    assert artifact_kind("matrix").current_version == 5


def test_the_chain_from_one_reaches_five_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("matrix", PRE_FRAMEWORK_VERSION)
    assert [s.to_version for s in chain] == [2, 3, 4, 5]


def test_skipped_rows_map_by_the_fixed_rule_and_nothing_else_moves(tmp_path: Path) -> None:
    path = _matrix(tmp_path)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    expected = (
        _V4.replace("schema_version: 4\n", "schema_version: 5\n")
        .replace(
            '    status: skipped\n    notes: "status: skipped',
            '    status: walked\n    notes: "status: skipped',
        )
        .replace(
            "    status: 'skipped'   # a trailing comment\n",
            "    status: walk-owed   # a trailing comment\n",
        )
        .replace("    status: skipped\n", "    status: unwired\n")
    )
    assert path.read_text() == expected
    m = load_matrix(path)
    assert m.schema_version == 5
    assert {r.id: r.status for r in m.rows} == _EXPECTED


def test_the_rewrite_is_written_once_and_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.artifacts.matrix_status_split as mod

    calls: list[Path] = []
    real = mod.write_text_atomic

    def _spy(p: Path, text: str) -> None:
        calls.append(p)
        real(p, text)

    monkeypatch.setattr(mod, "write_text_atomic", _spy)
    path = _matrix(tmp_path)

    run_migrations(tmp_path, dry_run=False)

    assert calls == [path]


def _git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "remote", "add", "origin", "https://github.com/acme/widget.git"],
        check=True,
    )


def test_the_committed_reports_are_regenerated_in_the_same_write(tmp_path: Path) -> None:
    from fr.acceptance.report import REPORT_SET, render_committed_set

    _git_repo(tmp_path)
    path = _matrix(tmp_path)
    for rel in REPORT_SET:
        (tmp_path / rel).write_text("stale\n")

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    want = render_committed_set(load_matrix(path), tmp_path)
    for rel in REPORT_SET:
        assert (tmp_path / rel).read_text() == want[rel]
    assert "walked live" in (tmp_path / "docs/acceptance/report_linked.md").read_text()


def test_an_unresolvable_verify_leaves_the_matrix_byte_identical(tmp_path: Path) -> None:
    path = _matrix(tmp_path, _V4.replace("verify: candidate", "verify: no-such-strategy"))
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [path]
    assert "no-such-strategy" in report.failed[0].error
    assert path.read_bytes() == before


def test_an_unconvertible_flow_row_is_left_byte_identical(tmp_path: Path) -> None:
    flow = _HEAD + "  - {id: f, capability: Cap, acceptance: X, status: skipped}\n"
    path = _matrix(tmp_path, flow)
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [path]
    assert path.read_bytes() == before


def test_an_unreadable_v4_matrix_is_refused_byte_identical(tmp_path: Path) -> None:
    path = _matrix(tmp_path, _V4.replace("status: ci", "status: sheduled"))
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [path]
    assert path.read_bytes() == before


def test_a_wholly_v5_body_under_a_v4_stamp_lets_the_runner_finish(tmp_path: Path) -> None:
    """The crash window: the body was rewritten, the stamp was not."""
    body = _HEAD + _ROWS["ci-row"] + _ROWS["plain-row"].replace("skipped", "manual")
    path = _matrix(tmp_path, body)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path.read_text() == body.replace("schema_version: 4\n", "schema_version: 5\n")


def test_a_v1_matrix_with_skipped_rows_climbs_the_whole_chain(tmp_path: Path) -> None:
    """Every hop reads through a frozen reader: with the live one, `skipped`
    (and `post-merge`) would be refused at the first hop."""
    v1 = (
        _HEAD.replace("schema_version: 4\n", "")
        + _ROWS["plain-row"]
        + _ROWS["owed-row"].replace("verify: live", "verify: post-merge")
        + _ROWS["ci-row"]
    )
    path = _matrix(tmp_path, v1)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    m = load_matrix(path)
    assert m.schema_version == 5
    assert {r.id: (r.status, r.verify) for r in m.rows} == {
        "plain-row": ("unwired", None),
        "owed-row": ("walk-owed", "live"),
        "ci-row": ("ci", None),
    }


def test_the_live_model_refuses_skipped_by_name() -> None:
    with pytest.raises(AcceptanceError, match="fr migrate artifacts --yes"):
        parse_matrix(_V4.replace("schema_version: 4", "schema_version: 5"))


def test_the_structure_validator_rejects_a_v5_matrix_carrying_skipped(tmp_path: Path) -> None:
    from fr.artifacts.structure import validate_matrix

    path = _matrix(tmp_path, _V4.replace("schema_version: 4", "schema_version: 5"))

    problems = validate_matrix(path)

    assert problems and any("skipped" in p for p in problems)


def test_the_frozen_v4_reader_is_pinned() -> None:
    from fr.acceptance import legacy

    for name, sha in legacy.FROZEN_V4_CLASS_SHA256.items():
        source = inspect.getsource(getattr(legacy, name))
        assert hashlib.sha256(source.encode()).hexdigest() == sha, name


def test_no_matrix_migration_reads_with_the_live_parser() -> None:
    """Every matrix hop's body check goes through a frozen reader; the live
    parser only answers the crash-window question of the newest hop."""
    import fr.artifacts.matrix_strategies as strategies
    import fr.artifacts.matrix_verify as verify

    assert "parse_matrix(" not in inspect.getsource(strategies).replace("parse_matrix_v", "")
    assert "parse_matrix(" not in inspect.getsource(verify).replace("parse_matrix_v", "")
