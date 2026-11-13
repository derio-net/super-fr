"""The `fr` branch's bookkeeping is input from whoever can push to it (lens
l-security-r2): an OWNER that is no safe branch name is ignored, BASE/HEADS lines that
are no full commit sha are dropped, and a branch printed into a suggested shell command
is quoted. Local sandboxes only; no forge is reached.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fr.artifacts import paths
from fr.closeout import archive_branch_command
from fr.placement import merged
from fr.placement.quiet import owner_of

from tests.unit.settings_repo import git
from tests.unit.test_placement_merged import Product, _home, quiet
from tests.unit.test_placement_merged_archive import PLAN, _complete_plan, _seed

__all__ = ["_home", "quiet"]

SHA = "a" * 40
CRAFTED = [
    "feat/a $(touch pwned)",
    "feat/a\nrm -rf ~",
    "feat/a\x1b[2Jx",
    "-oProxyCommand=x",
    "feat/a\tid",
]


def _owner(tmp_path: Path, text: str) -> Path:
    froot = tmp_path / paths.FEATURES_DIR / "feat__a"
    froot.mkdir(parents=True, exist_ok=True)
    (froot / paths.FEATURE_OWNER).write_text(text)
    return froot


@pytest.mark.parametrize("text", CRAFTED)
def test_a_crafted_owner_is_ignored_with_a_notice_that_does_not_echo_it(
    tmp_path: Path, text: str, capsys: pytest.CaptureFixture[str]
) -> None:
    _owner(tmp_path, text + "\n")
    assert owner_of(tmp_path, "feat__a") is None
    err = capsys.readouterr().err
    assert "OWNER" in err and "feat__a" in err
    assert text.strip() not in err and "pwned" not in err and "rm -rf" not in err


def test_a_valid_owner_still_reads(tmp_path: Path) -> None:
    _owner(tmp_path, "feat/a;x\n")
    assert owner_of(tmp_path, "feat__a") == "feat/a;x"


def test_the_archive_command_quotes_the_branch() -> None:
    assert archive_branch_command("feat/a") == "fr archive --branch feat/a"
    assert archive_branch_command("feat/a;x") == "fr archive --branch 'feat/a;x'"
    # a backtick is legal in a git branch name: quoted, it is inert
    assert archive_branch_command("feat/a`id`") == "fr archive --branch 'feat/a`id`'"


def test_base_and_heads_keep_only_full_hex_shas(tmp_path: Path) -> None:
    froot = _owner(tmp_path, "feat/a\n")
    (froot / paths.FEATURE_BASE).write_text("--output=/tmp/x\n")
    (froot / paths.FEATURE_HEADS).write_text(f"HEAD\n{SHA}\n-x\n{'b' * 64}\nabc123\n")
    assert merged.base_of(froot) is None
    assert merged.recorded_heads(froot) == [SHA, "b" * 64]


def test_a_crafted_owner_never_reaches_the_sweep_or_debt(quiet: Product) -> None:
    from fr.archive import merge_evidence
    from fr.closeout import plan_sweep
    from fr.debt.engine import compute

    quiet.feature("a")
    _complete_plan(quiet.feature_root("a"))
    _seed(quiet, "a", quiet.space.root)
    quiet.merge("a")
    (quiet.feature_root("a") / paths.FEATURE_OWNER).write_text("feat/a $(touch pwned)\n")
    git(quiet.space.root, "add", "-A")
    sweep = plan_sweep(quiet.root, merge_evidence(quiet.root, fetch=False))
    assert all("pwned" not in c for c in sweep.commands.values())
    assert PLAN not in sweep.branches or "pwned" not in sweep.branches[PLAN]
    report = compute(quiet.root, forge=None, now=datetime.now(UTC))
    assert "pwned" not in repr(report)
