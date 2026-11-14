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


def test_row_and_set_status_carry_a_stamp() -> None:
    assert _row(local=STAMP).local is not None
    assert _row().local is None
    assert _set_status("local", local=STAMP).local is not None


def test_set_status_to_local_with_a_stamp_puts_it_on_the_row() -> None:
    from fr.acceptance.fold import apply_amendment

    out = apply_amendment(_row(status="unwired"), _set_status("local", local=STAMP))
    assert out.status == "local"
    assert out.local is not None and out.local.tree == "a" * 40


def test_set_status_to_local_without_a_stamp_clears_an_older_one() -> None:
    from fr.acceptance.fold import apply_amendment

    out = apply_amendment(_row(local=STAMP), _set_status("local"))
    assert out.status == "local"
    assert out.local is None


def test_set_status_to_another_status_drops_the_stamp() -> None:
    from fr.acceptance.fold import apply_amendment

    out = apply_amendment(_row(local=STAMP), _set_status("ci"))
    assert out.status == "ci"
    assert out.local is None


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
        {"at": "2026-11-14", "tree": "t", "log": "l", "files": {p: _blob(root, p) for p in paths}}
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
