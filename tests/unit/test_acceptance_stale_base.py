"""Stale amendment bases (spec 2026-11-04 R17).

Before merge, `fr acceptance check` and `deliver` fetch the default ref and refuse a
branch amendment whose base another feature's merged amendment has passed. A stale
amendment that merged anyway marks its row contested, which is debt, until the next
amendment at the row's current revision clears it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.exceptions import Exit
from fr.acceptance.fold import clear_fold_cache, fold
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import FRAGMENTS_REL
from tests.unit.test_acceptance_amend import SLUG_B, fragment, git, invoke, merged_repo

runner = CliRunner()
SLUG_C = "2026-03-01-gamma"

B_FRAGMENT = f"""\
schema_version: 1
feature: {SLUG_B}
repo: acme/widget
rows:
amendments:
  - row: r
    op: reword
    base: 0
    acceptance: r works, as B says
    why: b
"""


def _clone(tmp_path: Path) -> Path:
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)],
        check=True,
        capture_output=True,
    )
    git(other, "config", "user.email", "o@example.com")
    git(other, "config", "user.name", "O")
    return other


def _merge_b(tmp_path: Path) -> None:
    """Feature B's amendment of r (base 0) lands on origin's main."""
    other = _clone(tmp_path)
    (other / FRAGMENTS_REL / f"{SLUG_B}.yaml").write_text(B_FRAGMENT)
    git(other, "add", "-A")
    git(other, "commit", "-qm", "feat: beta amends r")
    git(other, "push", "-q", "origin", "main")


def _stale_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Feature C amends r at base 0 on its branch; then B's amendment merges."""
    root = merged_repo(tmp_path, branch="feat/c")
    res = invoke(
        root, monkeypatch, "amend", "--id", "r", "--op", "set-status", "--status", "ci",
        "--notes", "wired", "--why", "c", "--feature", SLUG_C,
    )  # fmt: skip
    assert res.exit_code == 0, res.output
    _merge_b(tmp_path)
    return root


def test_check_fetches_the_default_ref_and_refuses_a_stale_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _stale_branch(tmp_path, monkeypatch)
    assert invoke(root, monkeypatch, "check", "--no-fetch").exit_code == 0  # not fetched yet

    res = invoke(root, monkeypatch, "check")

    assert res.exit_code == 2, res.output
    assert "row r" in res.output
    assert "based on revision 0" in res.output
    assert "at revision 1" in res.output
    assert "fr acceptance amend --rebase" in res.output


def test_rebase_moves_the_base_and_check_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _stale_branch(tmp_path, monkeypatch)
    git(root, "fetch", "-q", "origin")

    res = invoke(root, monkeypatch, "amend", "--rebase")

    assert res.exit_code == 0, res.output
    assert [a["base"] for a in fragment(root, SLUG_C)["amendments"]] == [1]
    assert git(root, "status", "--porcelain") == ""
    assert invoke(root, monkeypatch, "check", "--no-fetch").exit_code == 0


def test_deliver_refuses_a_stale_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.commands import run_cmd

    root = _stale_branch(tmp_path, monkeypatch)
    clear_fold_cache()

    with pytest.raises(Exit) as raised:
        run_cmd._deliver_acceptance_gate(root)

    assert raised.value.exit_code == 2


def test_deliver_passes_a_current_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.commands import run_cmd

    root = merged_repo(tmp_path)
    clear_fold_cache()

    run_cmd._deliver_acceptance_gate(root)  # no raise


def test_a_failed_fetch_in_ci_is_a_refusal_never_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.acceptance.amend import branch_refusals

    root = merged_repo(tmp_path)
    git(root, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    monkeypatch.setenv("CI", "true")

    found = branch_refusals(root)

    assert any("cannot fetch" in e for e in found.errors)
    monkeypatch.delenv("CI")
    for var in ("GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE", "TF_BUILD", "JENKINS_URL"):
        monkeypatch.delenv(var, raising=False)
    offline = branch_refusals(root)
    assert offline.errors == []
    assert any("cannot fetch" in w for w in offline.warnings)


def _merged_anyway(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """C's stale amendment merges after B's; a fresh branch from main sees it."""
    root = _stale_branch(tmp_path, monkeypatch)
    other = tmp_path / "other"
    git(other, "pull", "-q", "--ff-only")
    (other / FRAGMENTS_REL / f"{SLUG_C}.yaml").write_text(
        (root / FRAGMENTS_REL / f"{SLUG_C}.yaml").read_text()
    )
    git(other, "add", "-A")
    git(other, "commit", "-qm", "feat: gamma, merged without a re-base")
    git(other, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")
    git(root, "checkout", "-q", "-b", "feat/d", "origin/main")
    clear_fold_cache()
    return root


def test_a_stale_amendment_merged_anyway_makes_its_row_contested_debt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _merged_anyway(tmp_path, monkeypatch)
    assert fold(root).contested == frozenset({"r"})

    status = invoke(root, monkeypatch, "status")
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    debt = runner.invoke(app, ["debt", "--offline"])

    assert status.exit_code == 0, status.output
    assert "r [ci, contested]" in status.output
    assert debt.exit_code in (0, 1), debt.output
    assert "r [ci, contested]" in debt.output


def test_the_next_amendment_at_the_current_base_clears_contested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _merged_anyway(tmp_path, monkeypatch)

    res = invoke(
        root, monkeypatch, "amend", "--id", "r", "--op", "reword", "--acceptance",
        "r works, settled", "--why", "reconcile B and C", "--feature", "2026-04-01-delta",
    )  # fmt: skip

    assert res.exit_code == 0, res.output
    assert fragment(root, "2026-04-01-delta")["amendments"][0]["base"] == 2
    clear_fold_cache()
    assert fold(root).contested == frozenset()
    assert "no acceptance debt" in invoke(root, monkeypatch, "status").output
