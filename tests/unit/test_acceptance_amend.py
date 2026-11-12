"""`fr acceptance amend` and `set-status` on a merged row (spec 2026-11-04 R16).

A later feature changes a row another feature's merged fragment owns only by
appending an amendment to its own fragment. `set-status` on such a row writes the
amendments; on a row still pending on this branch it edits in place. `check`
refuses an in-place edit of a row as it stands on the default ref.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from fr.acceptance.fold import clear_fold_cache, fold
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import FRAGMENTS_REL

runner = CliRunner()
SLUG_A = "2026-01-01-alpha"
SLUG_B = "2026-02-01-beta"
SPEC_A = f"docs/superpowers/specs/{SLUG_A}-design.md"
UNIT = "widget:tests/test_w.py#test_w"
OTHER = "widget:tests/test_w.py#test_v"

FRAGMENT_A = f"""\
schema_version: 1
feature: {SLUG_A}
repo: acme/widget
rows:
  - id: r
    capability: Widget
    acceptance: r works
    origin:
    - spec:{SLUG_A}#R1
    levels:
      unit:
      - {UNIT}
    status: unwired
    notes: a test exists
"""


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


def merged_repo(tmp_path: Path, *, branch: str = "feat/b") -> Path:
    """A repo whose origin's `main` carries feature A's fragment (row `r`, revision
    0), checked out on *branch*."""
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    root = tmp_path / "widget"
    (root / "docs" / "superpowers" / "specs").mkdir(parents=True)
    (root / SPEC_A).write_text("# Alpha\n\nR1. r works.\n\n## Test Plan\n\n1. x\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_w.py").write_text(
        "def test_w():\n    pass\n\n\ndef test_v():\n    pass\n"
    )
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("on: push\n")
    (root / FRAGMENTS_REL).mkdir(parents=True)
    (root / FRAGMENTS_REL / f"{SLUG_A}.yaml").write_text(FRAGMENT_A)
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "T")
    git(root, "remote", "add", "origin", str(bare))
    git(root, "add", "-A")
    git(root, "commit", "-qm", "feat: alpha")
    git(root, "push", "-q", "-u", "origin", "main")
    git(root, "fetch", "-q", "origin")
    git(root, "checkout", "-q", "-b", branch)
    clear_fold_cache()
    return root


def invoke(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    clear_fold_cache()
    return runner.invoke(app, ["acceptance", *args])


def fragment(root: Path, feature: str) -> dict:
    return yaml.safe_load((root / FRAGMENTS_REL / f"{feature}.yaml").read_text())


def committed(root: Path) -> list[str]:
    return sorted(git(root, "show", "--name-only", "--format=", "HEAD").split())


def amend(root: Path, monkeypatch: pytest.MonkeyPatch, op: str, *extra: str):
    return invoke(
        root, monkeypatch, "amend", "--id", "r", "--op", op, "--why", "because",
        "--feature", SLUG_B, *extra,
    )  # fmt: skip


def test_amend_reword_appends_to_the_branch_fragment_and_folds_at_revision_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = merged_repo(tmp_path)
    before_a = (root / FRAGMENTS_REL / f"{SLUG_A}.yaml").read_text()

    res = amend(root, monkeypatch, "reword", "--acceptance", "r works, reworded")

    assert res.exit_code == 0, res.output
    frag = fragment(root, SLUG_B)
    assert frag["repo"] == "acme/widget"
    assert frag["amendments"] == [
        {"row": "r", "op": "reword", "base": 0, "acceptance": "r works, reworded", "why": "because"}
    ]
    assert (root / FRAGMENTS_REL / f"{SLUG_A}.yaml").read_text() == before_a
    assert committed(root) == [f"{FRAGMENTS_REL}/{SLUG_B}.yaml"]
    clear_fold_cache()
    eff = fold(root)
    (row,) = eff.matrix.rows
    assert row.acceptance == "r works, reworded"
    assert eff.revisions["r"] == 1


@pytest.mark.parametrize(
    ("op", "extra", "check"),
    [
        (
            "set-status",
            ("--status", "ci", "--notes", "wired"),
            lambda row: (row.status, row.notes) == ("ci", "wired"),
        ),
        ("add-level", ("--level", f"unit={OTHER}"), lambda row: OTHER in row.levels["unit"]),
        ("drop-level", ("--level", f"unit={UNIT}"), lambda row: UNIT not in row.levels["unit"]),
    ],
)
def test_each_op_appends_one_amendment_the_fold_applies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, op: str, extra: tuple[str, ...], check
) -> None:
    root = merged_repo(tmp_path)

    res = amend(root, monkeypatch, op, *extra)

    assert res.exit_code == 0, res.output
    (entry,) = fragment(root, SLUG_B)["amendments"]
    assert (entry["row"], entry["op"], entry["base"]) == ("r", op, 0)
    clear_fold_cache()
    (row,) = fold(root).matrix.rows
    assert check(row)


def test_amend_retire_moves_the_row_out_of_the_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = merged_repo(tmp_path)

    res = amend(root, monkeypatch, "retire", "--notes", "superseded")

    assert res.exit_code == 0, res.output
    clear_fold_cache()
    eff = fold(root)
    assert eff.matrix.rows == ()
    assert [r.id for r in eff.retired] == ["r"]


def test_two_amendments_on_one_row_take_consecutive_bases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = merged_repo(tmp_path)
    assert amend(root, monkeypatch, "reword", "--acceptance", "one").exit_code == 0

    res = amend(root, monkeypatch, "reword", "--acceptance", "two")

    assert res.exit_code == 0, res.output
    assert [a["base"] for a in fragment(root, SLUG_B)["amendments"]] == [0, 1]
    clear_fold_cache()
    assert fold(root).contested == frozenset()


def test_amend_refuses_an_unknown_row_and_an_op_missing_its_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = merged_repo(tmp_path)

    unknown = invoke(
        root, monkeypatch, "amend", "--id", "nope", "--op", "reword", "--acceptance", "x",
        "--why", "w", "--feature", SLUG_B,
    )  # fmt: skip
    empty = amend(root, monkeypatch, "reword")

    assert unknown.exit_code == 2
    assert "nope" in unknown.output
    assert empty.exit_code == 2
    assert not (root / FRAGMENTS_REL / f"{SLUG_B}.yaml").exists()


def test_amend_with_no_feature_and_no_run_is_refused_naming_feature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = merged_repo(tmp_path)

    res = invoke(
        root, monkeypatch, "amend", "--id", "r", "--op", "reword", "--acceptance", "x",
        "--why", "w",
    )  # fmt: skip

    assert res.exit_code == 2
    assert "--feature" in res.output


def test_the_feature_falls_back_to_the_branch_run_cursors_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.acceptance import amend as amend_mod

    root = merged_repo(tmp_path)
    monkeypatch.setattr(amend_mod, "_branch_run_specs", lambda _root, _branch: {
        f"docs/superpowers/specs/{SLUG_B}-design.md"
    })  # fmt: skip

    assert amend_mod.resolve_feature(root, None) == SLUG_B
    assert amend_mod.resolve_feature(root, "legacy") == "legacy"


def test_set_status_on_a_merged_row_appends_amendments_and_leaves_its_owner_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = merged_repo(tmp_path)
    before_a = (root / FRAGMENTS_REL / f"{SLUG_A}.yaml").read_text()

    res = invoke(
        root, monkeypatch, "set-status", "--id", "r", "--status", "ci", "--notes", "wired",
        "--level", f"int={OTHER}", "--drop-level", f"unit={UNIT}", "--feature", SLUG_B,
    )  # fmt: skip

    assert res.exit_code == 0, res.output
    assert (root / FRAGMENTS_REL / f"{SLUG_A}.yaml").read_text() == before_a
    ops = [(a["op"], a["base"]) for a in fragment(root, SLUG_B)["amendments"]]
    assert ops == [("set-status", 0), ("add-level", 1), ("drop-level", 2)]
    assert committed(root) == [f"{FRAGMENTS_REL}/{SLUG_B}.yaml"]
    clear_fold_cache()
    (row,) = fold(root).matrix.rows
    assert (row.status, row.notes) == ("ci", "wired")
    assert row.levels["int"] == (OTHER,)
    assert row.levels["unit"] == ()


def test_set_status_on_a_merged_row_with_no_feature_and_no_run_is_refused_naming_feature(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R16: a later feature appends an amendment to ITS OWN fragment. With no feature
    in play there is no such fragment, so `set-status` refuses like `amend` does,
    rather than writing into the row owner's merged fragment (review p3-r1)."""
    root = merged_repo(tmp_path, branch="closeout/a")
    before = (root / FRAGMENTS_REL / f"{SLUG_A}.yaml").read_text()

    res = invoke(root, monkeypatch, "set-status", "--id", "r", "--issue", "acme/widget#7")

    assert res.exit_code == 2, res.output
    assert "--feature <spec-slug>" in res.output
    assert (root / FRAGMENTS_REL / f"{SLUG_A}.yaml").read_text() == before
    assert not (root / FRAGMENTS_REL / f"{SLUG_B}.yaml").exists()


def test_set_status_on_a_merged_row_with_feature_appends_to_that_features_fragment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = merged_repo(tmp_path, branch="closeout/a")
    before = (root / FRAGMENTS_REL / f"{SLUG_A}.yaml").read_text()

    res = invoke(
        root, monkeypatch, "set-status", "--id", "r", "--issue", "acme/widget#7",
        "--feature", SLUG_B,
    )  # fmt: skip

    assert res.exit_code == 0, res.output
    assert (root / FRAGMENTS_REL / f"{SLUG_A}.yaml").read_text() == before
    (entry,) = fragment(root, SLUG_B)["amendments"]
    assert (entry["op"], entry["issues"]) == ("set-status", ["acme/widget#7"])


def test_feature_flag_names_the_spec_the_row_closes(tmp_path: Path) -> None:
    """The `--feature` a printed post-merge command carries: the run's spec when the
    printer knows it, else the spec the row's origin names, else a placeholder."""
    from fr.acceptance.amend import feature_flag

    root = merged_repo(tmp_path)

    assert feature_flag(root, spec=f"docs/superpowers/specs/{SLUG_B}-design.md") == (
        f"--feature {SLUG_B}"
    )
    assert feature_flag(root, "r") == f"--feature {SLUG_A}"
    assert feature_flag(root, "nope") == "--feature <spec-slug>"


def test_set_status_on_a_row_pending_on_this_branch_still_edits_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = merged_repo(tmp_path)
    added = invoke(
        root, monkeypatch, "add", "--id", "p", "--capability", "Widget", "--acceptance",
        "p works", "--origin", "widget:tests/test_w.py", "--feature", SLUG_B,
        "--level", f"unit={UNIT}", "--status", "unwired", "--notes", "n",
    )  # fmt: skip
    assert added.exit_code == 0, added.output

    res = invoke(root, monkeypatch, "set-status", "--id", "p", "--status", "ci", "--notes", "wired")

    assert res.exit_code == 0, res.output
    frag = fragment(root, SLUG_B)
    assert "amendments" not in frag
    assert [(r["id"], r["status"]) for r in frag["rows"]] == [("p", "ci")]


def test_check_refuses_an_in_place_edit_of_a_merged_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = merged_repo(tmp_path)
    path = root / FRAGMENTS_REL / f"{SLUG_A}.yaml"
    path.write_text(path.read_text().replace("status: unwired", "status: ci"))
    git(root, "commit", "-qam", "edit in place")

    res = invoke(root, monkeypatch, "check", "--no-fetch")

    assert res.exit_code != 0
    assert "rows merged on origin/main change only by amendment" in res.output
    assert "row r" in res.output


def test_check_passes_an_amendment_of_a_merged_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = merged_repo(tmp_path)
    assert amend(root, monkeypatch, "reword", "--acceptance", "r works, better").exit_code == 0

    res = invoke(root, monkeypatch, "check", "--no-fetch")

    assert res.exit_code == 0, res.output


SLUG_C = "2026-01-15-gamma"


def _contested_retired_repo(tmp_path: Path) -> Path:
    """Feature C merged a set-status and a stale retire of `r` (both base 0): `r` is
    retired AND contested on main (decision fold-retired-rows-keep-the-base-rule)."""
    root = merged_repo(tmp_path, branch="feat/c")
    (root / FRAGMENTS_REL / f"{SLUG_C}.yaml").write_text(
        f"schema_version: 1\nfeature: {SLUG_C}\nrepo: acme/widget\nrows: []\n"
        "amendments:\n"
        "  - {row: r, op: set-status, base: 0, status: ci, notes: wired, why: wired}\n"
        "  - {row: r, op: retire, base: 0, notes: superseded, why: superseded}\n"
    )
    git(root, "add", "-A")
    git(root, "commit", "-qm", "feat: gamma")
    git(root, "checkout", "-q", "main")
    git(root, "merge", "-q", "--no-ff", "feat/c", "-m", "Merge feat/c")
    git(root, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")
    git(root, "checkout", "-q", "-b", "feat/b")
    clear_fold_cache()
    eff = fold(root)
    assert [r.id for r in eff.retired] == ["r"] and eff.contested == {"r"}
    return root


def test_amend_clears_a_contested_retired_row_with_a_correctly_based_amendment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # pr1408-r1: the fold accepts the clearing amendment; the writer must let it be written.
    root = _contested_retired_repo(tmp_path)

    res = amend(root, monkeypatch, "reword", "--acceptance", "r is retired, on purpose")

    assert res.exit_code == 0, res.output
    (entry,) = fragment(root, SLUG_B)["amendments"]
    assert entry["base"] == 2
    clear_fold_cache()
    eff = fold(root)
    assert eff.contested == frozenset()
    assert [r.id for r in eff.retired] == ["r"]
    assert eff.matrix.rows == ()


def test_amend_still_refuses_a_retired_row_that_is_not_contested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = merged_repo(tmp_path)
    assert amend(root, monkeypatch, "retire", "--notes", "superseded").exit_code == 0

    res = amend(root, monkeypatch, "reword", "--acceptance", "again")

    assert res.exit_code == 2
    assert "retired" in res.output
