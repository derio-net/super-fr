"""The fold follows a fragment's spelling through history (spec
2026-11-17-batch-acceptance-edits §F, R15/R17; review p1-r1, p1-r2).

p1-r1: once the `-design` repair lands on the default ref, `<slug>.yaml` either has no
history before the repair commit (a pure rename) or first holds the `-design` file's
amendments there (a merge into an existing `<slug>.yaml`). Each of those amendments
keeps the position its `-design` commit gave it, so the repair changes no fold.

p1-r2: a default ref that never ran the repair folds as it did before §F, with or
without a working set: a tip `<slug>-design.yaml` is respelled only when the branch
performed the rename."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fr.acceptance.fold import clear_fold_cache, fold

from tests.unit.acceptance_helpers import FRAGMENTS_REL

SLUG = "2026-01-01-alpha"
OTHER = "2026-01-02-beta"
UNIT = "widget:tests/test_w.py#test_w"


def _row(rid: str, slug: str = SLUG) -> str:
    return (
        f"  - id: {rid}\n"
        "    capability: Widget\n"
        f"    acceptance: {rid} works\n"
        "    origin:\n"
        f"    - spec:{slug}#R1\n"
        "    levels:\n"
        "      unit:\n"
        f"      - {UNIT}\n"
        "    status: unwired\n"
        "    notes: a test exists\n"
    )


def _amend(rid: str, notes: str, base: int) -> str:
    return (
        f"  - row: {rid}\n"
        "    op: set-status\n"
        f"    base: {base}\n"
        "    status: unwired\n"
        f"    notes: {notes}\n"
        "    why: because\n"
    )


def _frag(feature: str, rows: str = "", amendments: str = "") -> str:
    text = f"schema_version: 2\nfeature: {feature}\nrepo: acme/widget\n"
    text += f"rows:\n{rows}" if rows else "rows: []\n"
    return text + (f"amendments:\n{amendments}" if amendments else "")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


def _commit(root: Path, files: dict[str, str | None], msg: str) -> str:
    for name, text in files.items():
        path = root / FRAGMENTS_REL / name
        if text is None:
            path.unlink()
        else:
            path.write_text(text)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", msg)
    return _git(root, "rev-parse", "HEAD").strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "widget"
    (root / FRAGMENTS_REL).mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    return root


def _fold_at(root: Path, sha: str):
    clear_fold_cache()
    return fold(root, ref=sha, include_pending=False)


A_DESIGN = _frag(f"{SLUG}-design", _row("r"), _amend("r", "a's note", 0))
B_AMENDS = _frag(OTHER, _row("b", OTHER), _amend("r", "b's note", 1))
A_OWN_ROWS = _row("own")
A_OWN_AMEND = _amend("own", "own note", 0)


def _history(tmp_path: Path, *, merge_into_existing: bool) -> tuple[Path, str, str]:
    """main: (0) A's rows, (1) A's `-design` fragment amends r (base 0), (2) B amends r
    (base 1), (3) the repair renames A's fragment (or merges it into `<slug>.yaml`).
    Returns (root, sha of (2), sha of (3))."""
    root = _repo(tmp_path)
    start: dict[str, str | None] = {f"{SLUG}-design.yaml": _frag(f"{SLUG}-design", _row("r"))}
    if merge_into_existing:
        start[f"{SLUG}.yaml"] = _frag(SLUG, A_OWN_ROWS, A_OWN_AMEND)
    _commit(root, start, "feat: alpha")
    _commit(root, {f"{SLUG}-design.yaml": A_DESIGN}, "feat: alpha amends r")
    before = _commit(root, {f"{OTHER}.yaml": B_AMENDS}, "feat: beta amends r")
    if merge_into_existing:
        repaired = _frag(SLUG, A_OWN_ROWS + _row("r"), A_OWN_AMEND + _amend("r", "a's note", 0))
    else:
        repaired = A_DESIGN.replace(f"feature: {SLUG}-design\n", f"feature: {SLUG}\n")
    after = _commit(
        root,
        {f"{SLUG}-design.yaml": None, f"{SLUG}.yaml": repaired},
        "chore(fr): migrate acceptance fragments",
    )
    return root, before, after


@pytest.mark.parametrize("merge_into_existing", [False, True], ids=["rename", "merge"])
def test_the_repair_commit_keeps_each_amendments_original_position(
    tmp_path: Path, merge_into_existing: bool
) -> None:
    root, before, after = _history(tmp_path, merge_into_existing=merge_into_existing)
    then = _fold_at(root, before)
    now = _fold_at(root, after)
    assert then.contested == frozenset()
    assert now.contested == frozenset(), now.contested
    assert now.revisions == then.revisions
    assert {r.id: r for r in now.matrix.rows} == {r.id: r for r in then.matrix.rows}
    assert now.owners["r"] == SLUG


def test_an_unrepaired_default_ref_folds_as_before(tmp_path: Path) -> None:
    """A tip holding only `<slug>-design.yaml`, folded with an empty working set, keeps
    the `-design` feature as the owner and its rows in their order."""
    root = _repo(tmp_path)
    design = _frag(f"{SLUG}-design", _row("r") + _row("s"), _amend("r", "a's note", 0))
    sha = _commit(root, {f"{SLUG}-design.yaml": design}, "feat: alpha")
    got = _fold_at(root, sha)
    assert got.owners == {"r": f"{SLUG}-design", "s": f"{SLUG}-design"}
    assert [r.id for r in got.matrix.rows] == ["r", "s"]
    assert got.revisions["r"] == 1
