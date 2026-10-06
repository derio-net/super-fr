"""The `matrix` kind's 3 -> 4 migration (spec
`2026-10-06-verification-strategies-design.md` §B, R7).

`Row.verify` names a verification strategy now, and the old
`verify: post-merge` becomes `verify: live` — a BODY rewrite, so the full
artifact-versioning rule applies: frozen reader on every hop, one atomic
write, the crash window recognised, a refused file left byte-identical, and
every hop of the chain asserted.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.model import AcceptanceError, load_matrix, parse_matrix
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION

_HEAD = """\
# header comment — must survive
schema_version: 3
org: acme
repo: widget
rows:
"""

_ROW_A = """\
  - id: a
    capability: "Cap"
    acceptance: "Operator can do X"
    origin: ["widget:docs/x.md"]
    status: ci
    notes: "verify: post-merge is quoted in this note and must stay"
    verify: post-merge
"""

_ROW_B = """\
  - id: b
    capability: "Cap"
    acceptance: "Operator can do Y"
    status: skipped
    notes: ""
"""

_ROW_C = """\
  - id: c
    capability: "Cap"
    acceptance: "Operator can do Z"
    status: not-implemented
    verify: 'post-merge'   # a trailing comment
"""

_V3 = _HEAD + _ROW_A + _ROW_B + _ROW_C


def _matrix(root: Path, text: str = _V3) -> Path:
    path = root / "docs" / "acceptance" / "matrix.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_matrix_kind_is_at_version_four() -> None:
    assert artifact_kind("matrix").current_version == 4


def test_the_chain_from_one_reaches_four_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("matrix", PRE_FRAMEWORK_VERSION)
    assert [s.to_version for s in chain] == [2, 3, 4]


def test_post_merge_becomes_live_and_nothing_else_moves(tmp_path: Path) -> None:
    path = _matrix(tmp_path)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    expected = (
        _V3.replace("schema_version: 3\n", "schema_version: 4\n")
        .replace("    verify: post-merge\n", "    verify: live\n")
        .replace(
            "    verify: 'post-merge'   # a trailing comment\n",
            "    verify: live   # a trailing comment\n",
        )
    )
    assert path.read_text() == expected
    m = load_matrix(path)
    assert m.schema_version == 4
    assert {r.id: r.verify for r in m.rows} == {"a": "live", "b": None, "c": "live"}


def test_the_rewrite_is_written_once_and_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.artifacts.matrix_strategies as mod

    calls: list[Path] = []
    real = mod.write_text_atomic

    def _spy(p: Path, text: str) -> None:
        calls.append(p)
        real(p, text)

    monkeypatch.setattr(mod, "write_text_atomic", _spy)
    path = _matrix(tmp_path)

    run_migrations(tmp_path, dry_run=False)

    assert calls == [path]


def test_a_wholly_v4_body_under_a_v3_stamp_lets_the_runner_finish(tmp_path: Path) -> None:
    """The crash window: the body was rewritten, the stamp was not."""
    body = (_HEAD + _ROW_A + _ROW_B).replace("verify: post-merge\n", "verify: live\n")
    body += "    scenario: tests/scenarios/b.sh\n"
    path = _matrix(tmp_path, body)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path.read_text() == body.replace("schema_version: 3\n", "schema_version: 4\n")


def test_an_unconvertible_matrix_is_left_byte_identical(tmp_path: Path) -> None:
    """A flow-style row carries `post-merge` where no line rewrite can reach it
    safely: the file is that artifact's failure, untouched."""
    flow = _HEAD + ("  - {id: f, capability: Cap, acceptance: X, status: ci, verify: post-merge}\n")
    path = _matrix(tmp_path, flow)
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [path]
    assert path.read_bytes() == before


def test_an_unreadable_v3_matrix_is_refused_byte_identical(tmp_path: Path) -> None:
    path = _matrix(tmp_path, _V3.replace("status: ci", "status: sheduled"))
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [path]
    assert path.read_bytes() == before


def test_a_v1_matrix_with_post_merge_climbs_the_whole_chain(tmp_path: Path) -> None:
    """Hops 1 -> 2 and 2 -> 3 read through the frozen reader: with the live one
    the old spelling would be refused at the first hop."""
    path = _matrix(tmp_path, _V3.replace("schema_version: 3\n", ""))

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    m = load_matrix(path)
    assert m.schema_version == 4
    assert m.rows[0].verify == "live"


def test_the_live_model_refuses_the_old_spelling() -> None:
    with pytest.raises(AcceptanceError, match="post-merge"):
        parse_matrix(_V3.replace("schema_version: 3", "schema_version: 4"))
