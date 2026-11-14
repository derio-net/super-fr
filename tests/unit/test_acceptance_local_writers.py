"""Every writer refuses what `local_error` refuses (spec 2026-11-14-acceptance-local-status
R2, R3): `add`, `set-status`, `amend --op set-status` and a step record's entry. A
refusal is exit 2 (or `RecordRefusedError`) with every fragment byte-identical."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.fold import load_effective

from tests.unit.test_record_apply import _acceptance_files, _matrix_repo, commit_all, git


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`_matrix_repo` (row `target`, refs own:tests/test_a.py and test_b.py), with CI."""
    root = _matrix_repo(tmp_path)
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def no_ci(repo: Path) -> Path:
    git(repo, "rm", "-rq", ".github")
    commit_all(repo, "drop ci")
    return repo


def _fr(*args: str):
    from fr.cli import app
    from typer.testing import CliRunner

    return CliRunner().invoke(app, ["acceptance", *args])


def _target(root: Path):
    return next(r for r in load_effective(root).rows if r.id == "target")


def test_add_local_with_no_level_is_refused(no_ci: Path) -> None:
    before = _acceptance_files(no_ci)
    out = _fr(
        "add", "--id", "fresh", "--capability", "Cap", "--acceptance", "a",
        "--origin", "own:docs/superpowers/specs/s.md", "--status", "local", "--notes", "n",
    )  # fmt: skip
    assert out.exit_code == 2, out.output
    assert "level ref" in out.output
    assert _acceptance_files(no_ci) == before


def test_set_status_local_in_a_repo_with_ci_is_refused(repo: Path) -> None:
    before = _acceptance_files(repo)
    out = _fr("set-status", "--id", "target", "--status", "local", "--notes", "n")
    assert out.exit_code == 2, out.output
    assert "`ci`" in out.output and "unwired" in out.output
    assert _acceptance_files(repo) == before


def test_amend_set_status_local_with_a_missing_test_is_refused(no_ci: Path) -> None:
    git(no_ci, "rm", "-q", "tests/test_b.py")
    commit_all(no_ci, "drop test b")
    before = _acceptance_files(no_ci)
    out = _fr(
        "amend", "--id", "target", "--op", "set-status", "--status", "local",
        "--notes", "n", "--why", "w",
    )  # fmt: skip
    assert out.exit_code == 2, out.output
    assert "tests/test_b.py" in out.output
    assert _acceptance_files(no_ci) == before


def test_a_record_entry_with_an_unresolved_ref_is_refused(no_ci: Path) -> None:
    from fr.record.apply import RecordRefusedError, RecordTarget, apply_record
    from fr.record.model import AcceptanceItem, StepRecord

    before = _acceptance_files(no_ci)
    item = AcceptanceItem.model_validate(
        {"id": "target", "status": "local", "notes": "n", "levels": {"unit": ["own:tests/no.py"]}}
    )
    with pytest.raises(RecordRefusedError, match="tests/no.py"):
        apply_record(no_ci, None, StepRecord(acceptance=(item,)), target=RecordTarget(message="m"))
    assert _acceptance_files(no_ci) == before


def test_set_status_local_under_ci_none_moves_the_row(no_ci: Path) -> None:
    out = _fr("set-status", "--id", "target", "--status", "local", "--notes", "n")
    assert out.exit_code == 0, out.output
    row = _target(no_ci)
    assert row.status == "local"
    assert row.local is None  # only deliver stamps


# --- review p1-r1: a write that does not move the status keeps the stamp ---------------


def _stamped(root: Path) -> None:
    """Set `target` local and stamp it as `deliver` would, then commit."""
    from fr.acceptance.edit import stamp_local
    from fr.acceptance.local import head_blobs, level_ref_paths
    from fr.acceptance.model import LocalStamp

    assert _fr("set-status", "--id", "target", "--status", "local", "--notes", "n").exit_code == 0
    blobs = head_blobs(root, level_ref_paths(_target(root)))
    assert blobs
    stamp = LocalStamp(at="2026-11-14", tree="a" * 40, log="suite.log@0123456789ab", files=blobs)
    for p in (root / "docs" / "acceptance" / "features").glob("*.yaml"):
        try:
            p.write_text(stamp_local(p.read_text(), "target", stamp))
        except Exception:  # noqa: BLE001 - only the fragment that holds the row stamps
            continue
    commit_all(root, "stamp")
    assert _target(root).local is not None


def test_a_link_only_write_keeps_a_local_rows_stamp(no_ci: Path) -> None:
    from fr.acceptance.local import local_reasons

    _stamped(no_ci)
    out = _fr("set-status", "--id", "target", "--issue", "o/demo#5")
    assert out.exit_code == 0, out.output
    row = _target(no_ci)
    assert row.status == "local" and row.local is not None
    assert local_reasons(load_effective(no_ci).rows, no_ci) == {}


def test_a_link_only_write_on_a_local_row_is_allowed_once_the_repo_has_ci(no_ci: Path) -> None:
    from fr.acceptance.local import local_reasons

    _stamped(no_ci)
    wf = no_ci / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text(
        "name: ci\non: push\njobs: {t: {runs-on: x, steps: [{run: pytest}]}}\n"
    )
    commit_all(no_ci, "ci")
    out = _fr("set-status", "--id", "target", "--issue", "o/demo#6")
    assert out.exit_code == 0, out.output
    assert local_reasons(load_effective(no_ci).rows, no_ci) == {"target": "promote to ci"}


def test_a_link_only_write_on_a_merged_local_row_keeps_its_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The merged path (p1-r1): set-status on a merged row writes a `set-status`
    amendment; a link-only one that keeps the row `local` must not clear the stamp
    `deliver` wrote on the earlier amendment, and is not refused once CI exists."""
    from fr.acceptance.edit import stamp_local
    from fr.acceptance.local import head_blobs, level_ref_paths, local_reasons
    from fr.acceptance.model import LocalStamp

    from tests.unit.acceptance_helpers import FRAGMENTS_REL
    from tests.unit.test_acceptance_amend import SLUG_B, invoke, merged_repo

    root = merged_repo(tmp_path)
    monkeypatch.chdir(root)
    git(root, "rm", "-rq", ".github")
    commit_all(root, "drop ci")
    out = invoke(
        root, monkeypatch, "set-status", "--id", "r", "--status", "local",
        "--notes", "unit tests", "--feature", SLUG_B,
    )  # fmt: skip
    assert out.exit_code == 0, out.output
    frag = root / FRAGMENTS_REL / f"{SLUG_B}.yaml"
    row = next(r for r in _rows(root) if r.id == "r")
    stamp = LocalStamp(
        at="2026-11-14",
        tree="a" * 40,
        log="suite.log@0123456789ab",
        files=head_blobs(root, level_ref_paths(row)),
    )
    frag.write_text(stamp_local(frag.read_text(), "r", stamp))
    commit_all(root, "stamp")

    out = invoke(root, monkeypatch, "set-status", "--id", "r", "--issue", "o/demo#5",
                 "--feature", SLUG_B)  # fmt: skip
    assert out.exit_code == 0, out.output
    rows = _rows(root)
    assert next(r for r in rows if r.id == "r").local == stamp
    assert local_reasons(rows, root) == {}

    wf = root / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("on: push\n")
    commit_all(root, "ci")
    out = invoke(root, monkeypatch, "set-status", "--id", "r", "--issue", "o/demo#6",
                 "--feature", SLUG_B)  # fmt: skip
    assert out.exit_code == 0, out.output
    assert local_reasons(_rows(root), root) == {"r": "promote to ci"}


def _rows(root: Path):
    from fr.acceptance.fold import clear_fold_cache

    clear_fold_cache()
    return load_effective(root).rows


# --- lens docs-accuracy r5: CI that fr cannot read is not "no CI" -----------------------

BROKEN_SERVICES = "schema_version: 2\nprofiles:\n  dev:\n    purpose: x\nci: {type: bogus}\n"


def _break_services(root: Path) -> None:
    (root / ".devcontainer").mkdir(exist_ok=True)
    (root / ".devcontainer" / "fr-profiles.yaml").write_text(BROKEN_SERVICES)
    commit_all(root, "broken services")


def test_local_is_refused_while_fr_cannot_tell_whether_the_repo_has_ci(no_ci: Path) -> None:
    _break_services(no_ci)
    before = _acceptance_files(no_ci)
    out = _fr("set-status", "--id", "target", "--status", "local", "--notes", "n")
    assert out.exit_code == 2, out.output
    assert "fr-profiles.yaml" in out.output and "fr services" in out.output
    assert _acceptance_files(no_ci) == before


def test_a_local_row_is_debt_while_fr_cannot_tell_whether_the_repo_has_ci(no_ci: Path) -> None:
    from fr.acceptance.local import local_reasons

    _stamped(no_ci)
    _break_services(no_ci)
    reasons = local_reasons(_rows(no_ci), no_ci)
    assert reasons["target"].startswith("ci unknown")
