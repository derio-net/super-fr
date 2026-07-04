"""Phase 3 — fr acceptance report: LinkBuilder modes + HTML rendering.

Pins spec traps 1 (twin-following links), 2 (sibling-root `..`),
3 (fragments in URLs) and 5 (HTML escaping of YAML-sourced strings).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.model import load_matrix
from fr.acceptance.report import LinkBuilder, render
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import MATRIX_HEADER, make_repo, row

runner = CliRunner()


def _links(root: Path, mode: str, *, ref: str = "main", sibling_root: str = "..") -> LinkBuilder:
    return LinkBuilder(
        mode=mode,
        ref=ref,
        root=root,
        out_dir=root / "docs" / "acceptance",
        sibling_root=sibling_root,
        org="derio-net",
        own_repo="own",
    )


# ── T1: LinkBuilder ────────────────────────────────────────────────────────


def test_github_own_repo_uses_ref(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    url = _links(root, "github", ref="abc123").url("own:tests/test_a.py")
    assert url == "https://github.com/derio-net/own/blob/abc123/tests/test_a.py"


def test_github_sibling_pins_main(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    url = _links(root, "github", ref="abc123").url("sib:lib/f.py")
    assert url == "https://github.com/derio-net/sib/blob/main/lib/f.py"


def test_github_keeps_fragment(tmp_path: Path) -> None:
    """Trap 3: the fragment rides the URL even though checks strip it."""
    root = make_repo(tmp_path, row())
    url = _links(root, "github").url("own:tests/test_a.py#L7")
    assert url.endswith("/tests/test_a.py#L7")


def test_local_own_repo_relative_to_out_dir(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    url = _links(root, "local").url("own:tests/test_a.py")
    assert url == "../../tests/test_a.py"


def test_local_sibling_root_layout(tmp_path: Path) -> None:
    """Trap 2: default `..` means repos are siblings — from
    own/docs/acceptance/ the sibling file is ../../../sib/lib/f.py."""
    root = make_repo(tmp_path, row())
    sib = tmp_path / "sib"
    (sib / "lib").mkdir(parents=True)
    (sib / ".git").mkdir()
    (sib / "lib" / "f.py").write_text("x\n")
    url = _links(root, "local").url("sib:lib/f.py")
    assert url == "../../../sib/lib/f.py"


def test_links_follow_archive_twin(tmp_path: Path) -> None:
    """Trap 1: a ref to the pre-archive path links to the implemented/ twin."""
    root = make_repo(tmp_path, row())
    live = root / "docs" / "superpowers" / "specs" / "s.md"
    live.rename(root / "docs" / "superpowers" / "implemented" / "specs" / "s.md")
    url = _links(root, "github").url("own:docs/superpowers/specs/s.md")
    assert "/implemented/specs/s.md" in url


def test_twin_following_requires_git_for_siblings(tmp_path: Path) -> None:
    """Trap 4: no .git at the sibling → no twin probing, path used as-is."""
    root = make_repo(tmp_path, row())
    (tmp_path / "sib").mkdir()
    url = _links(root, "github").url("sib:docs/superpowers/specs/gone.md")
    assert "/specs/gone.md" in url
    assert "implemented" not in url


# ── T2: render ─────────────────────────────────────────────────────────────


def _render(root: Path, rows_text: str) -> str:
    (root / "docs" / "acceptance" / "matrix.yaml").write_text(MATRIX_HEADER + rows_text)
    matrix = load_matrix(root / "docs" / "acceptance" / "matrix.yaml")
    return render(matrix, _links(root, "local"), stamp="test-stamp")


def test_tiles_computed_from_rows(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    html = _render(
        root,
        row(id="a") + row(id="b") + row(id="c", status="skipped"),
    )
    (tiles_line,) = [ln for ln in html.splitlines() if '<div class="tiles">' in ln]
    values = [chunk.split("</div>")[0] for chunk in tiles_line.split('<div class="v">')[1:]]
    assert values == ["2", "0", "1", "0", "0"]  # ci, scheduled, skipped, not-impl, failing


def test_capabilities_first_seen_order(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    r_b = row(id="b").replace('"Cap"', '"Zeta"')
    r_a = row(id="a").replace('"Cap"', '"Alpha"')
    html = _render(root, r_b + r_a)
    assert html.index("Zeta") < html.index("Alpha")


def test_yaml_strings_are_escaped(tmp_path: Path) -> None:
    """Trap 5: every YAML-sourced string is quote-safe in HTML."""
    root = make_repo(tmp_path, row())
    evil = row(id="a").replace('"Operator can do X"', "'<script>alert(\"x\")</script>'")
    html = _render(root, evil)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_level_chips_on_off(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    html = _render(root, row(id="a"))
    assert 'class="on"' in html  # unit has a ref
    assert '<span class="off">API</span>' in html


def test_panels_only_when_status_present(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    all_ci = _render(root, row(id="a"))
    assert "FAILING" not in all_ci
    with_fail = _render(root, row(id="a") + row(id="f", status="failing"))
    assert "Failing" in with_fail


# ── T3: report verb ────────────────────────────────────────────────────────


def test_report_writes_default_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row())
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    result = runner.invoke(app, ["acceptance", "report"])
    assert result.exit_code == 0, result.output
    out = root / "docs" / "acceptance" / "report.html"
    assert out.exists()
    assert "links: local" in out.read_text()


def test_report_github_mode_embeds_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row())
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    result = runner.invoke(
        app, ["acceptance", "report", "--link-mode", "github", "--ref", "abc123"]
    )
    assert result.exit_code == 0, result.output
    text = (root / "docs" / "acceptance" / "report.html").read_text()
    assert "blob/abc123/" in text
    assert "links: github (ref abc123)" in text
