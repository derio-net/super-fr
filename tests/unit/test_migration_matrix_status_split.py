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

from tests.unit.acceptance_helpers import matrix_registry_up_to_v5

V5 = matrix_registry_up_to_v5()

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


def test_the_matrix_kind_reached_version_five_before_it_retired() -> None:
    assert artifact_kind("matrix").current_version == 6
    assert V5.kind("matrix").current_version == 5


def test_the_chain_from_one_reaches_five_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("matrix", PRE_FRAMEWORK_VERSION)
    assert [s.to_version for s in chain][:4] == [2, 3, 4, 5]


def test_skipped_rows_map_by_the_fixed_rule_and_nothing_else_moves(tmp_path: Path) -> None:
    path = _matrix(tmp_path)

    report = run_migrations(tmp_path, dry_run=False, registry=V5)

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

    run_migrations(tmp_path, dry_run=False, registry=V5)

    assert calls == [path]


def _git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "remote", "add", "origin", "https://github.com/acme/widget.git"],
        check=True,
    )


def test_the_hop_renders_no_report_and_leaves_existing_ones_alone(tmp_path: Path) -> None:
    """Review p2-r1: the 5 -> 6 hop deletes every committed report, so this hop
    renders none — not even when one of the set exists (it used to write all three)."""
    from fr.acceptance.report import LEGACY_REPORT_PATHS as REPORT_SET

    _git_repo(tmp_path)
    _matrix(tmp_path)
    first, *rest = REPORT_SET
    (tmp_path / first).write_text("stale\n")

    report = run_migrations(tmp_path, dry_run=False, registry=V5)

    assert report.ok, report.failed
    assert (tmp_path / first).read_text() == "stale\n"
    for rel in rest:
        assert not (tmp_path / rel).exists(), rel
    assert [p.name for p in report.changed_paths] == ["matrix.yaml"]


def test_an_unresolvable_verify_leaves_the_matrix_byte_identical(tmp_path: Path) -> None:
    path = _matrix(tmp_path, _V4.replace("verify: candidate", "verify: no-such-strategy"))
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False, registry=V5)

    assert [f.path for f in report.failed] == [path]
    assert "no-such-strategy" in report.failed[0].error
    assert path.read_bytes() == before


def test_an_unconvertible_flow_row_is_left_byte_identical(tmp_path: Path) -> None:
    flow = _HEAD + "  - {id: f, capability: Cap, acceptance: X, status: skipped}\n"
    path = _matrix(tmp_path, flow)
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False, registry=V5)

    assert [f.path for f in report.failed] == [path]
    assert path.read_bytes() == before


def test_an_unreadable_v4_matrix_is_refused_byte_identical(tmp_path: Path) -> None:
    path = _matrix(tmp_path, _V4.replace("status: ci", "status: sheduled"))
    before = path.read_bytes()

    report = run_migrations(tmp_path, dry_run=False, registry=V5)

    assert [f.path for f in report.failed] == [path]
    assert path.read_bytes() == before


def test_a_wholly_v5_body_under_a_v4_stamp_lets_the_runner_finish(tmp_path: Path) -> None:
    """The crash window: the body was rewritten, the stamp was not."""
    body = _HEAD + _ROWS["ci-row"] + _ROWS["plain-row"].replace("skipped", "manual")
    path = _matrix(tmp_path, body)

    report = run_migrations(tmp_path, dry_run=False, registry=V5)

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

    report = run_migrations(tmp_path, dry_run=False, registry=V5)

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


def test_no_matrix_migration_names_the_live_parser() -> None:
    """Review p2-r3, the rule in `.claude/rules/artifact-versioning.md`: no matrix
    hop validates an old file against the live model. Every module under
    `fr/artifacts/matrix_*.py` reads through the frozen `fr.acceptance.legacy`
    readers (`parse_matrix_v3/v4/v5`, `is_v5_body`). The final hop's crash-window
    question is answered by the fold over fragments — its new shape — never by
    the live `parse_matrix`/`load_matrix`, so no module is allowlisted."""
    import re

    import fr.artifacts as artifacts_pkg

    live = re.compile(r"\b(?:parse_matrix|load_matrix)\b(?!_v)")
    assert live.search("from fr.acceptance.model import parse_matrix"), "the pattern is blind"
    assert live.search("matrix = load_matrix(path)"), "the pattern is blind"
    assert not live.search("from fr.acceptance.legacy import parse_matrix_v5")

    src = Path(artifacts_pkg.__file__).parent
    modules = sorted(src.glob("matrix_*.py"))
    assert len(modules) >= 6, [m.name for m in modules]
    offenders = {m.name for m in modules if live.search(m.read_text())}
    assert offenders == set()
    # The 4 -> 5 hop reads the OLD body with the frozen reader (p1-r5).
    import fr.artifacts.matrix_status_split as split

    assert "parse_matrix_v4(text)" in inspect.getsource(split.split_skipped)


# --- review p1-r3: the header's status comment ----------------------------------

_OLD_STATUS_COMMENT = """\
#   status:     ci | scheduled | skipped | not-implemented | failing
#     ci               automated on every PR — cannot drift silently
#     scheduled        automated on cron/path triggers
#     skipped          verification exists but does not run in CI (proven
#                      live once / manual walk) → CI warning, backfill owed
#     not-implemented  no test or surface exists yet → CI warning
#     failing          known red → `fr acceptance check` exits 2, CI FAILS
"""


def test_the_old_scaffold_status_comment_is_replaced_by_the_current_one(tmp_path: Path) -> None:
    from fr.artifacts.matrix_status_split import current_status_comment

    head = "# Row schema:\n" + _OLD_STATUS_COMMENT + "#   notes:      evidence detail\n"
    path = _matrix(tmp_path, head + _V4)

    report = run_migrations(tmp_path, dry_run=False, registry=V5)

    assert report.ok, report.failed
    text = path.read_text()
    assert "skipped          verification exists" not in text
    assert current_status_comment() in text
    assert text.startswith("# Row schema:\n" + current_status_comment() + "#   notes:")


def test_a_customised_status_comment_is_left_alone(tmp_path: Path) -> None:
    custom = "#   status: our own words, skipped included\n"
    path = _matrix(tmp_path, custom + _V4)

    report = run_migrations(tmp_path, dry_run=False, registry=V5)

    assert report.ok, report.failed
    assert path.read_text().startswith(custom)


def test_the_current_status_comment_is_the_scaffolds() -> None:
    from fr.acceptance.scaffold import MATRIX_TEMPLATE
    from fr.artifacts.matrix_status_split import current_status_comment

    block = current_status_comment()
    assert block.startswith("#   status:") and "unwired" in block and "skipped" not in block
    assert block in MATRIX_TEMPLATE


# --- review p1-r5 ----------------------------------------------------------------


def test_the_crash_window_only_owes_the_stamp(tmp_path: Path) -> None:
    from fr.acceptance.report import LEGACY_REPORT_PATHS as REPORT_SET

    _git_repo(tmp_path)
    body = _HEAD + _ROWS["ci-row"] + _ROWS["plain-row"].replace("skipped", "unwired")
    path = _matrix(tmp_path, body)
    for rel in REPORT_SET:
        (tmp_path / rel).write_text("stale\n")

    report = run_migrations(tmp_path, dry_run=False, registry=V5)

    assert report.ok, report.failed
    assert path.read_text() == body.replace("schema_version: 4\n", "schema_version: 5\n")
    for rel in REPORT_SET:
        assert (tmp_path / rel).read_text() == "stale\n"


def test_a_skipped_row_whose_only_walk_failed_is_not_walked(tmp_path: Path) -> None:
    failed = _WALK.replace("outcome: pass", "outcome: fail")
    body = (
        _HEAD
        + _ROWS["owed-row"] + failed
        + _ROWS["plain-row"] + failed
    )  # fmt: skip
    path = _matrix(tmp_path, body)

    report = run_migrations(tmp_path, dry_run=False, registry=V5)

    assert report.ok, report.failed
    assert {r.id: r.status for r in load_matrix(path).rows} == {
        "owed-row": "walk-owed",
        "plain-row": "unwired",
    }
