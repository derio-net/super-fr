"""The `local` acceptance status (spec 2026-11-14-acceptance-local-status)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError


def test_the_module_imports() -> None:
    import fr.acceptance.local as local

    assert "2026-11-14-acceptance-local-status" in (local.__doc__ or "")


# --- Task 2: the status, LocalStamp and the fold's stamp rules (R1, R5, §A) -------------

STAMP = {
    "at": "2026-11-14",
    "tree": "a" * 40,
    "log": "/tmp/suite.log",
    "files": {"tests/test_x.py": "b" * 40},
}


def _row(**over: object):
    from fr.acceptance.model import Row

    data: dict[str, object] = {
        "id": "r1",
        "capability": "widgets",
        "acceptance": "it works",
        "levels": {"unit": ["demo:tests/test_x.py#test_y"]},
        "status": "local",
    }
    data.update(over)
    return Row.model_validate(data)


def _set_status(status: str, **over: object):
    from fr.acceptance.fragment import SetStatus

    data: dict[str, object] = {
        "op": "set-status",
        "row": "r1",
        "base": 0,
        "why": "moved",
        "status": status,
        "notes": "n",
    }
    data.update(over)
    return SetStatus.model_validate(data)


def test_local_is_a_listed_status_and_never_debt() -> None:
    from fr.acceptance.model import DEBT_STATUSES, LISTED_STATUSES, is_debt

    assert _row().status == "local"
    assert "local" in LISTED_STATUSES
    assert "local" not in DEBT_STATUSES
    assert not is_debt("local")


def test_local_stamp_is_closed_and_needs_files() -> None:
    from fr.acceptance.model import LocalStamp

    assert LocalStamp.model_validate(STAMP).files == STAMP["files"]
    with pytest.raises(ValidationError):
        LocalStamp.model_validate({**STAMP, "extra": 1})
    with pytest.raises(ValidationError):
        LocalStamp.model_validate({**STAMP, "files": {}})
    for key in ("at", "tree", "log", "files"):
        with pytest.raises(ValidationError):
            LocalStamp.model_validate({k: v for k, v in STAMP.items() if k != key})


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("at", "not-a-date"),
        ("tree", ""),
        ("tree", "t"),
        ("log", ""),
        ("files", {"tests/test_x.py": "not-a-sha"}),
    ],
)
def test_a_malformed_stamp_is_refused(field: str, bad: object) -> None:
    """Lens errors r2: a stamp holds what `deliver` writes (an ISO date, a git tree, a
    log witness, git blobs), so a hand-made one cannot pass as fresh."""
    from fr.acceptance.model import LocalStamp
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LocalStamp.model_validate({**STAMP, field: bad})


def test_row_and_set_status_carry_a_stamp() -> None:
    assert _row(local=STAMP).local is not None
    assert _row().local is None
    assert _set_status("local", local=STAMP).local is not None


def test_set_status_to_local_with_a_stamp_puts_it_on_the_row() -> None:
    from fr.acceptance.fold import apply_amendment

    out = apply_amendment(_row(status="unwired"), _set_status("local", local=STAMP))
    assert out.status == "local"
    assert out.local is not None and out.local.tree == "a" * 40


def test_set_status_keeping_a_row_local_without_a_stamp_keeps_its_stamp() -> None:
    """Review p1-r1: a link or a note on a row that stays `local` keeps its stamp; R5's
    blob comparison, not the write, decides whether it is still fresh."""
    from fr.acceptance.fold import apply_amendment

    out = apply_amendment(_row(local=STAMP), _set_status("local"))
    assert out.status == "local"
    assert out.local == _row(local=STAMP).local


def test_set_status_moving_a_row_into_local_without_a_stamp_leaves_it_unstamped() -> None:
    from fr.acceptance.fold import apply_amendment

    out = apply_amendment(_row(status="unwired"), _set_status("local"))
    assert out.status == "local"
    assert out.local is None


def test_a_stamp_on_the_amendment_replaces_the_rows_own() -> None:
    from fr.acceptance.fold import apply_amendment

    newer = {**STAMP, "tree": "c" * 40}
    out = apply_amendment(_row(local=STAMP), _set_status("local", local=newer))
    assert out.local is not None and out.local.tree == "c" * 40


def test_set_status_to_another_status_drops_the_stamp() -> None:
    from fr.acceptance.fold import apply_amendment

    out = apply_amendment(_row(local=STAMP), _set_status("ci"))
    assert out.status == "ci"
    assert out.local is None


def test_a_stamped_amendment_is_hashable() -> None:
    """The fold counts a branch's amendments against the merged ones with a Counter keyed
    on the amendment, so a stamped `set-status` must hash (review of phase 1: the fold
    crashed on the first fragment `deliver` stamped)."""
    a, b = _set_status("local", local=STAMP), _set_status("local", local=dict(STAMP))
    assert hash(a) == hash(b) and a == b
    assert hash(_set_status("local", local={**STAMP, "files": {"x.py": "c" * 40}})) != hash(a)


def test_level_amendments_keep_the_stamp() -> None:
    from fr.acceptance.fold import apply_amendment
    from fr.acceptance.fragment import AddLevel, DropLevel

    row = _row(local=STAMP)
    add = AddLevel(op="add-level", row="r1", base=0, why="w", level="unit", ref="super-fr:t.py")
    drop = DropLevel(op="drop-level", row="r1", base=0, why="w", level="unit", ref="super-fr:t.py")
    assert apply_amendment(row, add).local == row.local
    assert apply_amendment(row, drop).local == row.local


# --- Task 3: local_debt and local_error (R2, R3, R5, §A, §C) ---------------------------


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return out.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo with no CI: a GitHub remote, no workflows, one committed test."""
    root = tmp_path / "demo"
    (root / "tests").mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "remote", "add", "origin", "https://github.com/derio-net/demo.git")
    (root / "tests" / "test_x.py").write_text("def test_y():\n    assert True\n")
    (root / "tests" / "test_z.py").write_text("def test_w():\n    assert True\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


def _blob(root: Path, path: str) -> str:
    return _git(root, "rev-parse", f"HEAD:{path}")


def _local_row(root: Path, row_id: str = "r1", *, stamp: bool = True, **over: object):
    levels = over.pop("levels", {"unit": ["demo:tests/test_x.py#test_y"]})
    paths = sorted({ref.split(":", 1)[1].split("#")[0] for refs in levels.values() for ref in refs})  # type: ignore[union-attr]
    local = (
        {"at": "2026-11-14", "tree": "a" * 40, "log": "suite.log@0123456789ab", "files": {p: _blob(root, p) for p in paths}}
        if stamp
        else None
    )
    return _row(id=row_id, levels=levels, local=local, **over)


def test_a_fresh_stamp_matching_head_is_no_debt(repo: Path) -> None:
    from fr.acceptance.local import local_debt

    assert local_debt([_local_row(repo)], repo, ci_active=False) == {}


def test_a_local_row_with_no_stamp_is_unstamped(repo: Path) -> None:
    from fr.acceptance.local import local_debt

    assert local_debt([_local_row(repo, stamp=False)], repo, ci_active=False) == {"r1": "unstamped"}


def test_a_checkout_git_cannot_read_makes_every_stamped_row_debt(
    repo: Path, tmp_path: Path
) -> None:
    """p1-r2: an unreadable HEAD is debt with its own reason, never fresh, and never
    blamed on a file that did not change."""
    from fr.acceptance.local import head_blobs, local_debt

    row = _local_row(repo)
    elsewhere = tmp_path / "not-a-repo"
    elsewhere.mkdir()
    assert head_blobs(elsewhere, ["tests/test_x.py"]) is None
    assert local_debt([row], elsewhere, ci_active=False) == {"r1": "stale: HEAD unreadable"}


def test_a_repo_with_no_commit_makes_every_stamped_row_debt(repo: Path, tmp_path: Path) -> None:
    from fr.acceptance.local import local_debt

    row = _local_row(repo)
    empty = tmp_path / "empty"
    empty.mkdir()
    _git(empty, "init", "-q")
    assert local_debt([row], empty, ci_active=False) == {"r1": "stale: HEAD unreadable"}


def test_rows_of_other_statuses_are_never_local_debt(repo: Path) -> None:
    from fr.acceptance.local import local_debt

    assert local_debt([_row(status="unwired")], repo, ci_active=True) == {}


def test_a_committed_edit_makes_it_stale(repo: Path) -> None:
    from fr.acceptance.local import local_debt

    row = _local_row(repo)
    (repo / "tests" / "test_x.py").write_text("def test_y():\n    assert 1\n")
    _git(repo, "commit", "-qam", "edit")
    assert local_debt([row], repo, ci_active=False) == {"r1": "stale: tests/test_x.py"}


def test_a_deleted_file_makes_it_stale(repo: Path) -> None:
    from fr.acceptance.local import local_debt

    row = _local_row(repo)
    _git(repo, "rm", "-q", "tests/test_x.py")
    _git(repo, "commit", "-qm", "rm")
    assert local_debt([row], repo, ci_active=False) == {"r1": "stale: tests/test_x.py"}


def test_a_level_ref_added_after_the_stamp_makes_it_stale(repo: Path) -> None:
    from fr.acceptance.local import local_debt

    row = _local_row(repo)
    levels = {"unit": ["demo:tests/test_x.py#test_y", "demo:tests/test_z.py#test_w"]}
    moved = row.model_copy(update={"levels": {**row.levels, **levels}})
    assert local_debt([moved], repo, ci_active=False) == {"r1": "stale: tests/test_z.py"}


def test_uncommitted_edits_do_not_make_it_stale(repo: Path) -> None:
    from fr.acceptance.local import local_debt

    row = _local_row(repo)
    (repo / "tests" / "test_x.py").write_text("def test_y():\n    assert 1\n")
    _git(repo, "add", "-A")  # staged, not committed: HEAD is the source
    assert local_debt([row], repo, ci_active=False) == {}


def test_a_local_row_in_a_repo_with_ci_is_promote_to_ci(repo: Path) -> None:
    from fr.acceptance.local import local_debt

    assert local_debt([_local_row(repo)], repo, ci_active=True) == {"r1": "promote to ci"}


def test_many_rows_cost_one_git_call(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import fr.acceptance.local as local

    rows = [_local_row(repo, f"r{i}") for i in range(5)]
    calls: list[object] = []
    real = local.subprocess.run

    def counting(*args: object, **kwargs: object):
        calls.append(args)
        return real(*args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(local.subprocess, "run", counting)
    assert local.local_debt(rows, repo, ci_active=False) == {}
    assert len(calls) == 1


def test_local_error_needs_a_level_ref(repo: Path) -> None:
    from fr.acceptance.local import local_error

    why = local_error(_row(levels={}), repo, own="demo")
    assert why is not None and "level ref" in why


def test_local_error_refuses_a_ref_into_another_repo(repo: Path) -> None:
    from fr.acceptance.local import local_error

    why = local_error(_row(levels={"unit": ["other:tests/test_x.py"]}), repo, own="demo")
    assert why is not None and "other:tests/test_x.py" in why


def test_local_error_refuses_a_missing_file(repo: Path) -> None:
    from fr.acceptance.local import local_error

    why = local_error(_row(levels={"unit": ["demo:tests/nope.py"]}), repo, own="demo")
    assert why is not None and "tests/nope.py" in why


def test_local_error_refuses_a_missing_test_name(repo: Path) -> None:
    from fr.acceptance.local import local_error

    why = local_error(_row(levels={"unit": ["demo:tests/test_x.py#test_gone"]}), repo, own="demo")
    assert why is not None and "test_gone" in why


def test_local_error_refuses_an_archived_twin(repo: Path) -> None:
    from fr.acceptance.local import local_error

    twin = repo / "docs" / "superpowers" / "implemented" / "specs" / "s.md"
    twin.parent.mkdir(parents=True)
    twin.write_text("# s\n")
    # an archived twin resolves only as a warning; a warning does not count (R2)
    why = local_error(_row(levels={"unit": ["demo:docs/superpowers/specs/s.md"]}), repo, own="demo")
    assert why is not None


def test_local_error_refuses_while_the_repo_has_ci(repo: Path) -> None:
    from fr.acceptance.local import local_error

    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("on: push\n")
    why = local_error(_row(), repo, own="demo")
    assert why is not None and "`ci`" in why and "unwired" in why


def test_local_error_accepts_a_resolving_own_repo_ref_under_ci_none(repo: Path) -> None:
    from fr.acceptance.local import local_error

    row = _row(levels={"unit": ["demo:tests/test_x.py#test_y"]})
    assert local_error(row, repo, own="demo") is None


def test_is_debt_counts_a_local_reason() -> None:
    from fr.acceptance.model import is_debt

    assert is_debt("local", local="unstamped")
    assert not is_debt("local", local=None)


# --- Task 5: renderers write `local` and the current fragment version (R7, §C, §E) -------

FRAG_ROW = """\
schema_version: 2
feature: f
repo: o/demo
rows:
  - id: other
    capability: C
    acceptance: a
    origin: []
    levels: {}
    status: unwired
    notes: 'keep me'

  - id: r1
    capability: C
    acceptance: a
    origin: []
    levels:
      unit:
      - demo:tests/test_x.py#test_y
    status: local
    notes: n
# trailing comment
"""

FRAG_AMEND = """\
schema_version: 2
feature: f
repo: o/demo
rows: []
amendments:
  - row: r1
    op: set-status
    base: 0
    status: local
    notes: first
    why: w
  - row: other
    op: reword
    base: 0
    acceptance: x
    why: w

  - row: r1
    op: set-status
    base: 1
    status: local
    notes: second
    why: w
  - row: r1
    op: add-level
    base: 2
    level: unit
    ref: demo:tests/test_z.py
    why: w
"""


def test_render_row_block_round_trips_a_stamp() -> None:
    from fr.acceptance.edit import render_fragment
    from fr.acceptance.fragment import parse_fragment

    row = _row(local=STAMP)
    text = render_fragment("f", "o/demo", [row])
    assert parse_fragment(text, source="f.yaml").rows[0] == row


def test_render_amendment_block_round_trips_a_stamp() -> None:
    from fr.acceptance.edit import append_amendment, render_fragment
    from fr.acceptance.fragment import parse_fragment

    amendment = _set_status("local", local=STAMP)
    text = append_amendment(render_fragment("f", "o/demo", []), amendment)
    assert parse_fragment(text, source="f.yaml").amendments[0] == amendment


def test_render_fragment_writes_the_current_fragment_version() -> None:
    import yaml
    from fr.acceptance.edit import render_fragment
    from fr.artifacts.registry import ARTIFACT_KINDS

    data = yaml.safe_load(render_fragment("f", "o/demo", []))
    assert data["schema_version"] == ARTIFACT_KINDS["acceptance-fragment"].current_version


def _stamp():
    from fr.acceptance.model import LocalStamp

    return LocalStamp.model_validate(STAMP)


def test_stamp_local_rewrites_a_pending_row_block_only() -> None:
    from fr.acceptance.edit import stamp_local
    from fr.acceptance.fragment import parse_fragment

    out = stamp_local(FRAG_ROW, "r1", _stamp())
    frag = parse_fragment(out, source="f.yaml")
    assert frag.rows[1].local == _stamp()
    head = FRAG_ROW[: FRAG_ROW.index("  - id: r1")]
    assert out.startswith(head)
    assert out.endswith("# trailing comment\n")
    assert frag.rows[0] == parse_fragment(FRAG_ROW, source="f.yaml").rows[0]


def test_stamp_local_rewrites_the_latest_set_status_amendment_only() -> None:
    from fr.acceptance.edit import stamp_local
    from fr.acceptance.fragment import parse_fragment

    out = stamp_local(FRAG_AMEND, "r1", _stamp())
    before = parse_fragment(FRAG_AMEND, source="f.yaml").amendments
    after = parse_fragment(out, source="f.yaml").amendments
    assert after[2].local == _stamp()  # type: ignore[union-attr]
    assert [a for i, a in enumerate(after) if i != 2] == [a for i, a in enumerate(before) if i != 2]
    cut = FRAG_AMEND.index("    notes: second")
    assert out.startswith(FRAG_AMEND[:cut])
    tail = FRAG_AMEND[FRAG_AMEND.index("  - row: r1\n    op: add-level") :]
    assert out.endswith(tail)


def test_stamp_local_refuses_a_row_the_fragment_neither_holds_nor_amends() -> None:
    from fr.acceptance.edit import stamp_local
    from fr.acceptance.model import AcceptanceError

    with pytest.raises(AcceptanceError):
        stamp_local(FRAG_ROW, "nope", _stamp())
    with pytest.raises(AcceptanceError):
        stamp_local(FRAG_ROW, "other", _stamp())  # held, but not local
