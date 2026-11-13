"""`fr acceptance amend --op reword --origin` (PR #1437 review F2-F6, F9): a row still
pending on this branch has its origins corrected in place; a merged row's origins are
history and are refused, under `repo` and under quiet, where a merged row may be this
branch's own."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fr.acceptance.fold import clear_fold_cache
from fr.artifacts.paths import KIND_DIRS
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import FRAGMENTS_REL
from tests.unit.test_acceptance_amend import SLUG_A, committed, fragment, git, invoke, merged_repo
from tests.unit.test_placement_merged import ROW, Product, _row
from tests.unit.test_placement_merged import quiet as quiet  # noqa: F401  (fixture)


def _add_pending(root: Path, monkeypatch: pytest.MonkeyPatch, *extra: str) -> None:
    res = invoke(
        root, monkeypatch, "add", "--id", "p", "--capability", "W", "--acceptance", "p works",
        "--status", "not-implemented", "--notes", "n",
        *(extra or ("--origin", f"spec:{SLUG_A}#R1")),
    )  # fmt: skip
    assert res.exit_code == 0, res.output


# --- repo placement ------------------------------------------------------------------


def test_repo_a_merged_rows_origin_is_refused(tmp_path: Path, monkeypatch) -> None:
    root = merged_repo(tmp_path)
    head = git(root, "rev-parse", "HEAD")
    res = invoke(
        root, monkeypatch, "amend", "--id", "r", "--op", "reword",
        "--origin", f"spec:{SLUG_A}#R2", "--why", "w",
    )  # fmt: skip
    assert res.exit_code == 2, res.output
    assert "merged" in res.output
    assert git(root, "rev-parse", "HEAD") == head


def test_repo_a_pending_rows_origin_is_corrected_in_place(tmp_path: Path, monkeypatch) -> None:
    root = merged_repo(tmp_path)
    _add_pending(root, monkeypatch)
    res = invoke(
        root, monkeypatch, "amend", "--id", "p", "--op", "reword",
        "--origin", f"spec:{SLUG_A}#R2", "--why", "the requirement was mistyped",
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    rows = {r["id"]: r for r in fragment(root, SLUG_A)["rows"]}
    assert rows["p"]["origin"] == [f"spec:{SLUG_A}#R2"]
    assert not fragment(root, SLUG_A).get("amendments")
    assert committed(root) == [f"{FRAGMENTS_REL}/{SLUG_A}.yaml"]


# --- quiet: a merged row may be this branch's own ---------------------------------------


def _own_merged(q: Product) -> Path:
    from tests.unit.settings_repo import git as g

    q.feature("a", rows=[_row(ROW)])
    q.merge("a")
    g(q.root, "checkout", "-q", "feat/a")
    clear_fold_cache()
    return q.feature_root("a") / KIND_DIRS["acceptance-fragment"] / "a.yaml"


def _quiet_fr(q: Product, *args: str):
    clear_fold_cache()
    return CliRunner().invoke(app, list(args), env={**os.environ, "FR_REPO_ROOT": str(q.root)})


def test_quiet_an_own_merged_rows_origin_is_refused(quiet: Product) -> None:
    """F2: under quiet the branch's own merged rows were read as pending."""
    frag = _own_merged(quiet)
    before = frag.read_text()
    res = _quiet_fr(
        quiet, "acceptance", "amend", "--id", ROW, "--op", "reword",
        "--origin", "widgets:README.md", "--why", "w",
    )  # fmt: skip
    assert res.exit_code == 2, res.output
    assert "merged" in res.output
    assert frag.read_text() == before


def test_quiet_set_status_on_an_own_merged_row_writes_an_amendment(quiet: Product) -> None:
    """The same hole in `set-status` (pre-existing): a merged row changes only by
    amendment (R16), so the row's definition is left as merged and `check` is clean."""
    import yaml
    from fr.acceptance.amend import branch_refusals

    frag = _own_merged(quiet)
    res = _quiet_fr(
        quiet, "acceptance", "set-status", "--id", ROW, "--status", "unwired",
        "--notes", "its test landed after the merge", "--feature", "a",
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    data = yaml.safe_load(frag.read_text())
    assert next(r for r in data["rows"] if r["id"] == ROW)["status"] == "not-implemented"
    assert [(a["row"], a["op"]) for a in data["amendments"]] == [(ROW, "set-status")]
    clear_fold_cache()
    assert branch_refusals(quiet.root, fetch=False).errors == []
