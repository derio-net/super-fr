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


def _no_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE", "TF_BUILD", "JENKINS_URL"):
        monkeypatch.delenv(var, raising=False)


def test_a_failed_fetch_in_ci_reads_the_checkouts_local_default_ref_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # pr1408-r3: the scaffolded GitHub job checks out with `persist-credentials: false`
    # and `fetch-depth: 0`, so the default branch is already at the checkout while an
    # unauthenticated fetch of a private repo fails: read the local ref, and name it.
    from fr.acceptance.amend import branch_refusals

    root = merged_repo(tmp_path)
    sha = git(root, "rev-parse", "refs/remotes/origin/main").strip()
    git(root, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    monkeypatch.setenv("CI", "true")

    found = branch_refusals(root)

    assert found.errors == [], found.errors
    assert found.source == f"the local ref origin/main at {sha[:12]} (fetch failed)"
    assert any("cannot fetch" in w and sha[:12] in w for w in found.warnings), found.warnings
    _no_ci(monkeypatch)
    offline = branch_refusals(root)
    assert offline.errors == []
    assert any("cannot fetch" in w for w in offline.warnings)


def test_a_failed_fetch_in_ci_with_no_local_default_ref_is_still_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.acceptance.amend import branch_refusals

    root = merged_repo(tmp_path)
    git(root, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    git(root, "update-ref", "-d", "refs/remotes/origin/main")
    monkeypatch.setenv("CI", "true")

    found = branch_refusals(root)

    assert any("refused" in e for e in found.errors), found.errors


def test_a_fetched_default_ref_is_named_as_the_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.acceptance.amend import branch_refusals

    root = merged_repo(tmp_path)
    _no_ci(monkeypatch)
    sha = git(root, "rev-parse", "refs/remotes/origin/main").strip()

    found = branch_refusals(root)

    assert found.source == f"origin/main at {sha[:12]} (fetched)"
    res = invoke(root, monkeypatch, "check")
    assert f"default ref: origin/main at {sha[:12]} (fetched)" in res.output


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


B_TWO = f"""\
schema_version: 1
feature: {SLUG_B}
repo: acme/widget
rows:
amendments:
  - row: r
    op: set-status
    base: 0
    status: walk-owed
    notes: owed
    why: b1
  - row: r
    op: set-status
    base: 1
    status: unwired
    notes: wired
    why: b2
"""


def _two_merged(tmp_path: Path) -> Path:
    """B's two amendments of r are merged on origin's main; a branch from it is checked out."""
    root = merged_repo(tmp_path, branch="feat/c")
    other = _clone(tmp_path)
    (other / FRAGMENTS_REL / f"{SLUG_B}.yaml").write_text(B_TWO)
    git(other, "add", "-A")
    git(other, "commit", "-qm", "feat: beta amends r twice")
    git(other, "push", "-q", "origin", "main")
    git(root, "fetch", "-q", "origin")
    git(root, "checkout", "-q", "-B", "feat/c", "origin/main")
    clear_fold_cache()
    return root


def _blocks(text: str) -> tuple[str, list[str]]:
    head, _, body = text.partition("amendments:\n")
    items = ["  - " + b for b in body.split("  - ") if b]
    return head + "amendments:\n", items


def test_check_refuses_reordered_merged_amendments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p3-r2: the fold orders amendments by position, so a swap changes the post-merge
    result; the merged list must lead the working list unchanged."""
    root = _two_merged(tmp_path)
    path = root / FRAGMENTS_REL / f"{SLUG_B}.yaml"
    head, (first, second) = _blocks(path.read_text())
    path.write_text(head + second + first)
    git(root, "commit", "-qam", "swap")

    res = invoke(root, monkeypatch, "check", "--no-fetch")

    assert res.exit_code != 0, res.output
    assert "merged amendment" in res.output


def test_check_refuses_an_amendment_inserted_above_merged_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _two_merged(tmp_path)
    path = root / FRAGMENTS_REL / f"{SLUG_B}.yaml"
    head, items = _blocks(path.read_text())
    new = "  - row: r\n    op: reword\n    base: 2\n    acceptance: r works, new\n    why: b3\n"
    path.write_text(head + new + "".join(items))
    git(root, "commit", "-qam", "insert above")

    res = invoke(root, monkeypatch, "check", "--no-fetch")

    assert res.exit_code != 0, res.output
    assert "merged amendment" in res.output


def test_check_passes_an_amendment_appended_after_merged_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _two_merged(tmp_path)
    path = root / FRAGMENTS_REL / f"{SLUG_B}.yaml"
    new = "  - row: r\n    op: reword\n    base: 2\n    acceptance: r works, new\n    why: b3\n"
    path.write_text(path.read_text() + new)
    git(root, "commit", "-qam", "append")

    res = invoke(root, monkeypatch, "check", "--no-fetch")

    assert "merged amendment" not in res.output, res.output


def _no_default_ref(tmp_path: Path) -> Path:
    """A clone with a remote but no `origin/HEAD` and no `origin/{main,master,...}`."""
    root = merged_repo(tmp_path)
    git(root, "update-ref", "-d", "refs/remotes/origin/main")
    git(root, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
    clear_fold_cache()
    return root


def _clear_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    from fr.artifacts.trigger import CI_ENV_VARS

    for var in CI_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_a_remote_with_no_default_ref_in_ci_is_a_refusal_never_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p3-r3: with no default ref the fold falls back to HEAD and every check passes, so
    in CI a remote that names none is refused, with the fix."""
    from fr.acceptance.amend import branch_refusals

    root = _no_default_ref(tmp_path)
    monkeypatch.setenv("CI", "true")

    found = branch_refusals(root)

    assert any("no default ref" in e and "fetch-depth: 0" in e for e in found.errors), found
    assert any("no default ref" in e for e in branch_refusals(root, fetch=False).errors)


def test_a_remote_with_no_default_ref_outside_ci_is_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.acceptance.amend import branch_refusals

    root = _no_default_ref(tmp_path)
    _clear_ci(monkeypatch)

    found = branch_refusals(root)

    assert found.errors == []
    assert any("no default ref" in w for w in found.warnings), found


def test_a_repo_with_no_remote_keeps_no_refusal_and_no_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.acceptance.amend import branch_refusals

    root = _no_default_ref(tmp_path)
    git(root, "remote", "remove", "origin")
    monkeypatch.setenv("CI", "true")

    found = branch_refusals(root)

    assert (found.errors, found.warnings) == ([], [])


RETIRE_B = f"""\
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
  - row: r
    op: retire
    base: 1
    notes: superseded
    why: b retires r
"""


def _retired_and_contested(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """C amends r at base 0 on its branch; B rewords then retires r and merges; C merges
    anyway, so a merged amendment names a retired row (`fold-merged-stale-targets`)."""
    root = _stale_branch(tmp_path, monkeypatch)
    other = tmp_path / "other"
    (other / FRAGMENTS_REL / f"{SLUG_B}.yaml").write_text(RETIRE_B)
    git(other, "commit", "-qam", "feat: beta retires r")
    git(other, "push", "-q", "origin", "main")
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


def test_a_retired_contested_row_is_debt_everywhere_and_status_and_debt_agree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """p3-r4: one definition. A retired row a merged amendment still names is contested
    debt in `status`, `open_rows`, `fr debt` and the digest alike, shown as retired."""
    from fr.acceptance.check import open_rows
    from fr.acceptance.fold import effective
    from fr.debt.engine import acceptance_debt

    root = _retired_and_contested(tmp_path, monkeypatch)
    folded = effective(root)
    assert folded.contested == frozenset({"r"}) and folded.matrix.rows == ()

    assert [r.id for r in open_rows(folded.matrix, folded.contested, folded.retired)] == ["r"]
    acc, _, _ = acceptance_debt(root)
    assert acc.debt_count() == 1
    assert [(r.id, r.retired, r.contested) for r in acc.rows] == [("r", True, True)]

    status = invoke(root, monkeypatch, "status")
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    debt = runner.invoke(app, ["debt", "--offline"])
    digest = invoke(root, monkeypatch, "digest")

    assert "no acceptance debt" not in status.output, status.output
    for out in (status.output, debt.output, digest.output):
        assert "retired, contested" in out, out
