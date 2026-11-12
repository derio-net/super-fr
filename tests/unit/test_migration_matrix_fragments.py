"""The `matrix` kind's last hop, 5 -> 6: the split into fragments (spec
`2026-11-04-repo-feature-settings-design.md` R19).

`docs/acceptance/matrix.yaml` is split by origin spec into
`docs/acceptance/features/<slug>.yaml`, path refs become logical ones, rows
without exactly one origin spec go to `legacy.yaml`, and the matrix and its
committed reports are deleted. The old body is read with the frozen
`fr.acceptance.legacy.MatrixV5`, never the live model.

The input is the captured excerpt of this repo's own v5 matrix
(`tests/fixtures/acceptance/matrix_v5_excerpt.yaml`), never a composed one.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.acceptance.fold import clear_fold_cache, fold
from fr.acceptance.fragment import parse_fragment
from fr.acceptance.legacy import parse_matrix_v5
from fr.acceptance.logical import to_logical
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION, artifact_kind
from fr.artifacts.runner import MIGRATIONS, run_migrations

FIXTURE = Path(__file__).parents[1] / "fixtures" / "acceptance" / "matrix_v5_excerpt.yaml"
REPORTS = (
    "docs/acceptance/report_local.html",
    "docs/acceptance/report_linked.html",
    "docs/acceptance/report_linked.md",
    "docs/acceptance/report.github.html",
)
FEATURES = "docs/acceptance/features"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


def _repo(tmp_path: Path, text: str | None = None) -> Path:
    root = tmp_path / "repo"
    (root / "docs" / "acceptance").mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "docs" / "acceptance" / "matrix.yaml").write_text(
        FIXTURE.read_text() if text is None else text
    )
    for rel in REPORTS:
        (root / rel).write_text("<rendered>\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    _git(root, "checkout", "-q", "-b", "feat/x")
    clear_fold_cache()
    return root


def _fragments(root: Path) -> dict[str, str]:
    return {p.stem: p.read_text() for p in sorted((root / FEATURES).glob("*.yaml"))}


def test_the_split_writes_one_fragment_per_origin_spec_and_a_legacy_one(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    report = run_migrations(root, dry_run=False)

    assert report.ok, report.failed
    frags = {
        stem: parse_fragment(text, source=f"{FEATURES}/{stem}.yaml")
        for stem, text in _fragments(root).items()
    }
    assert set(frags) == {
        "2026-07-04-acceptance-matrix",
        "2026-10-20-opencode-2-support",
        "2026-09-29-fr-goal-light-path",
        "2026-10-06-driver-sessions",
        "legacy",
    }
    assert [r.id for r in frags["2026-07-04-acceptance-matrix"].rows] == [
        "acceptance-pipeline-rows",
        "acceptance-nag-channels",
    ]
    # two distinct specs, and debug-journal origins: legacy
    assert [r.id for r in frags["legacy"].rows] == [
        "acceptance-report-dual",
        "runner-unit-refusal",
        "agent-worktrees-reaped-by-fr",
    ]
    assert {f.repo for f in frags.values()} == {"derio-net/super-fr"}
    light = frags["2026-09-29-fr-goal-light-path"].rows[0]
    assert light.origin == (
        "spec:2026-09-29-fr-goal-light-path#R1",
        "spec:2026-09-29-fr-goal-light-path#R2",
    )


def test_no_row_is_lost_or_duplicated_and_only_refs_change(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    old = parse_matrix_v5(FIXTURE.read_text())

    run_migrations(root, dry_run=False)

    effective = fold(root)
    got = {r.id: r.model_dump() for r in effective.matrix.rows}
    assert len(got) == len(effective.matrix.rows) == len(old.rows)
    for row in old.rows:
        want = row.model_dump()
        want["origin"] = tuple(to_logical(o, own_repo="super-fr") for o in row.origin)
        want["levels"] = {
            lv: tuple(to_logical(r, own_repo="super-fr") for r in refs)
            for lv, refs in row.levels.items()
        }
        assert got[row.id] == want, row.id
    assert (effective.matrix.org, effective.matrix.repo) == ("derio-net", "super-fr")


def test_the_matrix_and_every_committed_report_are_deleted(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    report = run_migrations(root, dry_run=False)

    assert not (root / "docs" / "acceptance" / "matrix.yaml").exists()
    for rel in REPORTS:
        assert not (root / rel).exists(), rel
    changed = {p.relative_to(root).as_posix() for p in report.changed_paths}
    assert {"docs/acceptance/matrix.yaml", *REPORTS} <= changed
    assert f"{FEATURES}/legacy.yaml" in changed


def test_the_crash_window_finishes_without_rewriting_the_fragments(tmp_path: Path) -> None:
    """Fragments written, the matrix not yet deleted: the rerun only deletes."""
    root = _repo(tmp_path)
    run_migrations(root, dry_run=False)
    written = _fragments(root)
    _git(root, "checkout", "-q", "HEAD", "--", "docs/acceptance")  # matrix + reports back
    for p in (root / FEATURES).glob("*.yaml"):
        p.write_text(p.read_text())  # same bytes, fresh mtime

    report = run_migrations(root, dry_run=False)

    assert report.ok, report.failed
    assert not (root / "docs" / "acceptance" / "matrix.yaml").exists()
    assert _fragments(root) == written


def test_a_fragment_already_there_with_other_bytes_is_refused(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / FEATURES).mkdir(parents=True)
    clash = root / FEATURES / "legacy.yaml"
    clash.write_text("schema_version: 1\nfeature: legacy\nrepo: derio-net/super-fr\nrows:\n")
    matrix = root / "docs" / "acceptance" / "matrix.yaml"
    before = matrix.read_bytes()

    report = run_migrations(root, dry_run=False)

    (failure,) = report.failed
    assert "legacy.yaml" in failure.error
    assert matrix.read_bytes() == before
    assert [p.name for p in (root / FEATURES).iterdir()] == ["legacy.yaml"]


def test_a_matrix_the_frozen_reader_refuses_is_left_byte_identical(tmp_path: Path) -> None:
    text = FIXTURE.read_text().replace("status: ci", "status: sheduled", 1)
    root = _repo(tmp_path, text)
    matrix = root / "docs" / "acceptance" / "matrix.yaml"
    before = matrix.read_bytes()

    report = run_migrations(root, dry_run=False)

    (failure,) = report.failed
    assert failure.kind == "matrix"
    assert matrix.read_bytes() == before
    assert not (root / FEATURES).exists()
    for rel in REPORTS:
        assert (root / rel).exists()


def test_a_matrix_with_no_identity_and_no_remote_is_refused(tmp_path: Path) -> None:
    text = FIXTURE.read_text().replace("org: derio-net\nrepo: super-fr\n", "")
    root = _repo(tmp_path, text)

    report = run_migrations(root, dry_run=False)

    (failure,) = report.failed
    assert "repo" in failure.error
    assert (root / "docs" / "acceptance" / "matrix.yaml").exists()


def test_the_migration_commit_stages_the_removals(tmp_path: Path) -> None:
    from fr.artifacts.commit import commit_migration

    root = _repo(tmp_path)
    outcome = commit_migration(root, run_migrations(root, dry_run=False))

    assert outcome.committed, outcome.reason
    tracked = _git(root, "ls-files").splitlines()
    assert "docs/acceptance/matrix.yaml" not in tracked
    assert not set(REPORTS) & set(tracked)
    assert f"{FEATURES}/legacy.yaml" in tracked
    assert _git(root, "status", "--porcelain") == ""


def test_rerendering_a_migrated_fragment_changes_nothing(tmp_path: Path) -> None:
    from fr.acceptance.edit import render_fragment

    root = _repo(tmp_path)
    run_migrations(root, dry_run=False)

    for stem, text in _fragments(root).items():
        frag = parse_fragment(text, source=f"{FEATURES}/{stem}.yaml")
        assert render_fragment(frag.feature, frag.repo, frag.rows) == text, stem


def test_every_hop_of_the_matrix_chain_is_registered_and_the_last_retires() -> None:
    assert artifact_kind("matrix").current_version == 6
    assert artifact_kind("matrix").retired
    chain = MIGRATIONS.chain("matrix", PRE_FRAMEWORK_VERSION)
    assert [(s.from_version, s.to_version) for s in chain] == [
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 5),
        (5, 6),
    ]
    assert [s.retires for s in chain] == [False, False, False, False, True]


@pytest.mark.parametrize("version", [5])
def test_a_dry_run_writes_nothing(tmp_path: Path, version: int) -> None:
    root = _repo(tmp_path)
    report = run_migrations(root, dry_run=True)
    assert [(a.from_version, a.to_version) for a in report.applied if a.kind == "matrix"] == [
        (version, 6)
    ]
    assert (root / "docs" / "acceptance" / "matrix.yaml").exists()
    assert not (root / FEATURES).exists()


def test_the_split_converts_line_anchors(tmp_path: Path) -> None:
    """gh#531's conversion rides on the split now that no repair can run after it."""
    text = FIXTURE.read_text().replace(
        "super-fr:tests/unit/test_hooks_acceptance_nag.py", "super-fr:tests/unit/test_w.py#L1", 1
    )
    assert "test_w.py#L1" in text, "fixture drift: pick another ref to re-point"
    root = _repo(tmp_path, text)
    (root / "tests" / "unit").mkdir(parents=True)
    (root / "tests" / "unit" / "test_w.py").write_text("def test_w(): pass\n")

    run_migrations(root, dry_run=False)

    rows = {r.id: r for r in fold(root).matrix.rows}
    assert "super-fr:tests/unit/test_w.py#test_w" in rows["acceptance-nag-channels"].refs()


_V4_PLAIN = """\
schema_version: 4
org: acme
repo: widget
rows:
  - id: plain-row
    capability: "Cap"
    acceptance: "No verify, no walk: unwired"
    status: skipped
  - id: ci-row
    capability: "Cap"
    acceptance: "Other statuses are untouched"
    status: ci
"""


def test_a_v4_matrix_with_a_partial_report_set_migrates_and_commits(tmp_path: Path) -> None:
    """Review p2-r1: the 4 -> 5 hop renders no reports (the next hop deletes them),
    so a repo that tracked only one report ends with none, and the commit holds
    exactly what git knew about."""
    from fr.artifacts.commit import commit_migration

    root = _repo(tmp_path, _V4_PLAIN)
    for rel in REPORTS[1:]:
        _git(root, "rm", "-q", rel)
    _git(root, "commit", "-qm", "only report_local.html is tracked")

    report = run_migrations(root, dry_run=False)
    outcome = commit_migration(root, report)

    assert report.ok, report.failed
    assert outcome.committed, outcome.reason
    for rel in REPORTS:
        assert not (root / rel).exists(), rel
    tracked = _git(root, "ls-files").splitlines()
    assert "docs/acceptance/report_local.html" not in tracked
    assert _git(root, "status", "--porcelain") == ""


def test_an_untracked_report_is_left_alone_and_not_listed(tmp_path: Path) -> None:
    """Review p2-r2: only a report git tracks is the repo's committed report. An
    untracked one (the ad-hoc render) is the user's file: not deleted, not listed,
    so the commit does not name a path git never knew."""
    from fr.artifacts.commit import commit_migration

    root = _repo(tmp_path)
    adhoc = "docs/acceptance/report.github.html"
    _git(root, "rm", "-q", "--cached", adhoc)
    _git(root, "commit", "-qm", "the ad-hoc report is not tracked")

    report = run_migrations(root, dry_run=False)
    outcome = commit_migration(root, report)

    assert report.ok, report.failed
    assert (root / adhoc).read_text() == "<rendered>\n"
    changed = {p.relative_to(root).as_posix() for p in report.changed_paths}
    assert adhoc not in changed
    assert set(REPORTS) - {adhoc} <= changed
    assert outcome.committed, outcome.reason
