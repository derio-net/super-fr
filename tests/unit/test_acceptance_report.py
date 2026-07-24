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


def _links(
    root: Path,
    mode: str,
    *,
    ref: str = "main",
    sibling_root: str = "..",
    probe: bool = True,
) -> LinkBuilder:
    return LinkBuilder(
        mode=mode,
        ref=ref,
        root=root,
        out_dir=root / "docs" / "acceptance",
        sibling_root=sibling_root,
        org="derio-net",
        own_repo="own",
        probe=probe,
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


# ── Deterministic render (a pure function of matrix.yaml) ───────────────────


def test_probe_false_skips_archive_twin(tmp_path: Path) -> None:
    """probe=False → no filesystem lookup, the raw ref path is emitted whether
    or not an archived twin exists (determinism for a committed report)."""
    root = make_repo(tmp_path, row())
    det = _links(root, "github", probe=False)
    before = det.url("own:docs/superpowers/specs/s.md")
    # Archive the spec — with probing this would flip the link to the twin.
    (root / "docs" / "superpowers" / "specs" / "s.md").rename(
        root / "docs" / "superpowers" / "implemented" / "specs" / "s.md"
    )
    after = det.url("own:docs/superpowers/specs/s.md")
    assert before == after
    assert "implemented" not in after
    assert after.endswith("/specs/s.md")


def test_deterministic_report_reproducible_no_git_stamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--deterministic` yields byte-identical output across runs and a
    matrix-derived stamp with no git date/hash."""
    root = make_repo(tmp_path, row(id="a") + row(id="b"))
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    out = root / "docs" / "acceptance" / "report.html"

    r1 = runner.invoke(app, ["acceptance", "report", "--deterministic"])
    assert r1.exit_code == 0, r1.output
    first = out.read_text()
    r2 = runner.invoke(app, ["acceptance", "report", "--deterministic"])
    assert r2.exit_code == 0, r2.output
    second = out.read_text()

    assert first == second
    assert "2 rows · links: local" in first
    assert "matrix @" not in first


# ── the committed report SET (local + github) ───────────────────────────────


def test_render_committed_set_two_files(tmp_path: Path) -> None:
    from fr.acceptance.report import REPORT_SET, render_committed_set

    root = make_repo(tmp_path, row(id="a") + row(id="b"))
    files = render_committed_set(load_matrix(root / "docs" / "acceptance" / "matrix.yaml"), root)
    assert set(files) == set(REPORT_SET)
    assert set(files) == {
        "docs/acceptance/report.html",
        "docs/acceptance/report.github.html",
    }
    local = files["docs/acceptance/report.html"]
    github = files["docs/acceptance/report.github.html"]
    # local: relative links; github: github.com blob links pinned to main.
    assert "links: local" in local
    assert "blob/main/" not in local
    assert "links: github" in github
    assert "https://github.com/derio-net/own/blob/main/" in github


def test_render_committed_set_is_deterministic(tmp_path: Path) -> None:
    from fr.acceptance.report import render_committed_set

    root = make_repo(tmp_path, row(id="a") + row(id="b"))
    m = load_matrix(root / "docs" / "acceptance" / "matrix.yaml")
    assert render_committed_set(m, root) == render_committed_set(m, root)


def test_report_deterministic_writes_both_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    res = runner.invoke(app, ["acceptance", "report", "--deterministic"])
    assert res.exit_code == 0, res.output
    local = root / "docs" / "acceptance" / "report.html"
    github = root / "docs" / "acceptance" / "report.github.html"
    assert local.exists() and github.exists()
    assert "links: local" in local.read_text()
    assert "blob/main/" in github.read_text()


def test_report_deterministic_out_is_single_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--out keeps the single-file escape hatch (back-compat)."""
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    res = runner.invoke(
        app, ["acceptance", "report", "--deterministic", "--out", "docs/acceptance/only.html"]
    )
    assert res.exit_code == 0, res.output
    assert (root / "docs" / "acceptance" / "only.html").exists()
    assert not (root / "docs" / "acceptance" / "report.github.html").exists()


# ── report --check (drift gate) ─────────────────────────────────────────────


def test_report_check_detects_missing_github_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    assert runner.invoke(app, ["acceptance", "report", "--deterministic"]).exit_code == 0
    (root / "docs" / "acceptance" / "report.github.html").unlink()
    res = runner.invoke(app, ["acceptance", "report", "--check"])
    assert res.exit_code == 3, res.output
    assert "report.github.html" in res.output


def test_report_check_passes_when_in_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    assert runner.invoke(app, ["acceptance", "report", "--deterministic"]).exit_code == 0
    res = runner.invoke(app, ["acceptance", "report", "--check"])
    assert res.exit_code == 0, res.output
    assert "in sync" in res.output


def test_report_check_detects_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    assert runner.invoke(app, ["acceptance", "report", "--deterministic"]).exit_code == 0
    # Mutate the matrix WITHOUT regenerating (simulates a hand-edited status flip).
    matrix = root / "docs" / "acceptance" / "matrix.yaml"
    matrix.write_text(matrix.read_text() + row(id="b"))
    res = runner.invoke(app, ["acceptance", "report", "--check"])
    assert res.exit_code == 3, res.output
    assert "stale" in res.output
    assert "--deterministic" in res.output


def test_report_check_missing_report_is_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("VK_REPO_ROOT", str(root))
    res = runner.invoke(app, ["acceptance", "report", "--check"])
    assert res.exit_code == 3, res.output
    assert not (root / "docs" / "acceptance" / "report.html").exists()  # --check writes nothing


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
