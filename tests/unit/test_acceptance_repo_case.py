"""gh#1237 — a ref prefix that differs from the matrix's `repo:` key only by
case still names the own repo.

The checkout here is deliberately NOT named like the prefix (`checkout/`, not
`OWN/`): that is the CI runner and fr-worktree layout, where the case-sensitive
comparison used to send every own-repo ref to `<checkout>/../OWN/` — refs went
unverified, `report_local.html` links depended on the directory name, and own
github links were pinned to `main`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.model import same_repo
from fr.acceptance.report import LinkBuilder
from fr.cli import app
from fr.requirements import origin_fragment
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import make_repo, row

runner = CliRunner()

UPPER = row(origin='"OWN:docs/superpowers/specs/s.md"', unit='"OWN:tests/test_a.py"')


def _check(root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    return runner.invoke(app, ["acceptance", "check"])


def _links(root: Path, mode: str, ref: str = "abc123") -> LinkBuilder:
    return LinkBuilder(
        mode=mode,
        ref=ref,
        root=root,
        out_dir=root / "docs" / "acceptance",
        sibling_root="..",
        org="derio-net",
        own_repo="own",
        probe=True,
    )


def test_same_repo_ignores_case_only() -> None:
    assert same_repo("OWN", "own")
    assert same_repo("own", "own")
    assert not same_repo("own", "sib")


def test_case_only_prefix_is_verified_not_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, UPPER, name="checkout")
    result = _check(root, monkeypatch)
    assert result.exit_code == 0, result.output
    assert "not checked out" not in result.output


def test_case_only_prefix_broken_ref_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of verifying: a broken own-repo path must fail the gate."""
    root = make_repo(tmp_path, row(unit='"OWN:tests/nope.py"'), name="checkout")
    result = _check(root, monkeypatch)
    assert result.exit_code == 1
    assert "does not resolve" in result.output


def test_case_only_prefix_is_named_with_both_spellings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Detection: tolerated, but never silent — the warning names both."""
    root = make_repo(tmp_path, UPPER, name="checkout")
    result = _check(root, monkeypatch)
    out = " ".join(result.output.split())
    assert "OWN" in out and "repo: own" in out


def test_exact_prefix_draws_no_case_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(), name="checkout")
    assert "differs" not in _check(root, monkeypatch).output


def test_local_link_does_not_depend_on_checkout_name(tmp_path: Path) -> None:
    root = make_repo(tmp_path, UPPER, name="checkout")
    assert _links(root, "local").url("OWN:tests/test_a.py") == "../../tests/test_a.py"


def test_github_link_pins_own_ref_not_main(tmp_path: Path) -> None:
    root = make_repo(tmp_path, UPPER, name="checkout")
    url = _links(root, "github").url("OWN:tests/test_a.py")
    assert url == "https://github.com/derio-net/own/blob/abc123/tests/test_a.py"


def test_origin_fragment_matches_case_only_prefix() -> None:
    assert origin_fragment("OWN:docs/s.md#R1", "own:docs/s.md") == "R1"
