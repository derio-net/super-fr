"""Phase 3 — fr acceptance report: LinkBuilder modes + HTML rendering.

Pins spec traps 1 (twin-following links), 2 (sibling-root `..`),
3 (fragments in URLs) and 5 (HTML escaping of YAML-sourced strings).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.fold import load_effective
from fr.acceptance.report import LinkBuilder, render
from fr.cli import app
from typer.testing import CliRunner

from tests.unit.acceptance_helpers import MATRIX_HEADER, make_repo, row, write_matrix_fragments

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
    """`render` is a pure function of a `Matrix` (the fold's, in use): rows in order."""
    from fr.acceptance.model import parse_matrix

    matrix = parse_matrix(MATRIX_HEADER + rows_text)
    return render(matrix, _links(root, "local"), stamp="test-stamp")


def test_tiles_computed_from_rows(tmp_path: Path) -> None:
    root = make_repo(tmp_path, row())
    html = _render(
        root,
        row(id="a") + row(id="b") + row(id="c", status="unwired"),
    )
    (tiles_line,) = [ln for ln in html.splitlines() if '<div class="tiles">' in ln]
    values = [chunk.split("</div>")[0] for chunk in tiles_line.split('<div class="v">')[1:]]
    # ci, scheduled, walked, manual, unwired, walk-owed, not-impl, failing
    assert values == ["2", "0", "0", "0", "1", "0", "0", "0"]


def test_both_renderings_name_the_folded_fragments_as_their_source(tmp_path: Path) -> None:
    # pr1408-r7: the report is rendered from the fold, not from matrix.yaml.
    from fr.acceptance.model import parse_matrix
    from fr.acceptance.report import render_markdown

    root = make_repo(tmp_path, row())
    matrix = parse_matrix(MATRIX_HEADER + row(id="a"))
    links = _links(root, "local")
    for out in (render(matrix, links, stamp="s"), render_markdown(matrix, links, stamp="s")):
        assert "matrix.yaml" not in out
        assert "docs/acceptance/features/" in out


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


def test_adhoc_report_keeps_row_count_and_tiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ad-hoc gitignored report.html is where a human reads counts: it
    keeps the `N rows` figure, the tiles and the sharp-line panels (§3.I)."""
    root = make_repo(tmp_path, row(id="a") + row(id="b", status="unwired"))
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    res = runner.invoke(app, ["acceptance", "report"])
    assert res.exit_code == 0, res.output
    adhoc = (root / "docs" / "acceptance" / "report.html").read_text()
    assert "(2 rows)" in adhoc
    assert '<div class="tiles">' in adhoc
    assert "The sharp line" in adhoc
    assert '<div class="panel' in adhoc


# ── derived reports: local, ignored, never committed (R20) ─────────────────


def test_render_markdown_is_github_flavored(tmp_path: Path) -> None:
    from fr.acceptance.report import render_markdown

    root = make_repo(tmp_path, row(id="a") + row(id="b", status="unwired"))
    matrix = load_effective(root)
    md = render_markdown(matrix, _links(root, "github"), stamp="links: github")
    assert md.startswith("# Acceptance coverage")
    assert "| Acceptance |" in md  # a GFM table header
    assert "| --- |" in md or "|---|" in md  # a delimiter row
    assert "## " in md  # per-capability section
    assert "[own:s.md](<https://github.com/derio-net/own/blob/main/" in md  # linked ref
    assert "links: github" in md


def test_markdown_escapes_pipe_in_cells(tmp_path: Path) -> None:
    from fr.acceptance.report import render_markdown

    root = make_repo(tmp_path, row(id="a"))
    evil = row(id="a").replace('"Operator can do X"', '"a | b\nc"')
    write_matrix_fragments(root, MATRIX_HEADER + evil)
    matrix = load_effective(root)
    md = render_markdown(matrix, _links(root, "github"), stamp="s")
    # the literal cell pipe is escaped and the newline flattened → table stays valid
    assert r"a \| b" in md
    assert "a | b\nc" not in md


def test_report_adhoc_writes_uncommitted_report_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`report` with no flags writes the ignored report.html honoring --link-mode."""
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    res = runner.invoke(app, ["acceptance", "report", "--link-mode", "github", "--ref", "abc123"])
    assert res.exit_code == 0, res.output
    report_html = root / "docs" / "acceptance" / "report.html"
    assert report_html.exists()
    assert "blob/abc123/" in report_html.read_text()
    assert str(report_html) in res.output  # the path is printed


def test_report_out_under_site_dir_is_sha_pinned_and_stamped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Pages workflow renders `--out _site/acceptance/index.html`: pinned to a
    commit SHA, git-stamped, and exit 0 even with a failing row (report, not gate)."""
    sha = "0123456789abcdef0123456789abcdef01234567"
    root = make_repo(tmp_path, row(id="a") + row(id="f", status="failing"))
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    res = runner.invoke(
        app,
        [
            "acceptance",
            "report",
            "--link-mode",
            "github",
            "--ref",
            sha,
            "--out",
            "_site/acceptance/index.html",
        ],
    )
    assert res.exit_code == 0, res.output
    out = root / "_site" / "acceptance" / "index.html"
    assert out.exists()
    html = out.read_text()
    assert f"blob/{sha}/" in html
    assert f"(ref {sha})" in html


def test_report_format_md_writes_report_md(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    res = runner.invoke(app, ["acceptance", "report", "--format", "md"])
    assert res.exit_code == 0, res.output
    md = root / "docs" / "acceptance" / "report.md"
    assert md.read_text().startswith("# Acceptance coverage")
    assert str(md) in res.output
    assert not (root / "docs" / "acceptance" / "report.html").exists()


def test_report_format_rejects_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    assert runner.invoke(app, ["acceptance", "report", "--format", "pdf"]).exit_code == 2


def test_report_open_goes_through_the_one_opener(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--open` opens what it wrote through one injectable opener — never a real browser."""
    opened: list[Path] = []
    monkeypatch.setattr("fr.commands.acceptance_cmd._open_report", opened.append)
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    res = runner.invoke(app, ["acceptance", "report", "--open"])
    assert res.exit_code == 0, res.output
    assert opened == [root / "docs" / "acceptance" / "report.html"]
    opened.clear()
    assert runner.invoke(app, ["acceptance", "report"]).exit_code == 0
    assert opened == []  # no flag, no open


@pytest.mark.parametrize("flag", ["--deterministic", "--check"])
def test_the_committed_report_flags_are_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    assert runner.invoke(app, ["acceptance", "report", flag]).exit_code == 2


def test_the_committed_report_machinery_is_gone() -> None:
    import fr.acceptance.report as report

    for name in (
        "REPORT_SET",
        "render_committed_set",
        "tracked_reports",
        "prune_stale_reports",
        "STALE_LEGACY_REPORTS",
        "ci_built_reports",
    ):
        assert not hasattr(report, name), name


def test_check_fails_on_a_tracked_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    tracked = root / "docs" / "acceptance" / "report_linked.md"
    tracked.write_text("# stale\n")
    for cmd in (
        ["init", "-q"],
        ["add", "-f", str(tracked)],
        ["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "a report"],
    ):
        subprocess.run(["git", "-C", str(root), *cmd], check=True, capture_output=True)
    res = runner.invoke(app, ["acceptance", "check"])
    assert res.exit_code != 0, res.output
    assert "reports are derived; remove docs/acceptance/report_linked.md" in res.output


def test_check_passes_with_an_untracked_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_repo(tmp_path, row(id="a"))
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    assert runner.invoke(app, ["acceptance", "report"]).exit_code == 0
    res = runner.invoke(app, ["acceptance", "check"])
    assert res.exit_code == 0, res.output


def test_fr_help_names_the_local_report() -> None:
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "fr acceptance report --open" in " ".join(res.output.split())


# ── T3: report verb ────────────────────────────────────────────────────────


def test_report_writes_default_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row())
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    result = runner.invoke(app, ["acceptance", "report"])
    assert result.exit_code == 0, result.output
    out = root / "docs" / "acceptance" / "report.html"
    assert out.exists()
    assert "links: local" in out.read_text()


def test_report_github_mode_embeds_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_repo(tmp_path, row())
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    result = runner.invoke(
        app, ["acceptance", "report", "--link-mode", "github", "--ref", "abc123"]
    )
    assert result.exit_code == 0, result.output
    text = (root / "docs" / "acceptance" / "report.html").read_text()
    assert "blob/abc123/" in text
    assert "links: github (ref abc123)" in text


# ── §3.I: committed reports are a pure per-row rendering ───────────────────

# One row of every status that has a sharp-line panel, so an aggregate that
# survives into the committed set cannot hide behind an empty section.
_EVERY_PANEL = (
    row(id="a")
    + row(id="s", status="unwired")
    + row(id="n", status="not-implemented", unit="")
    + row(id="f", status="failing")
)


def test_both_renderers_carry_the_aggregates(tmp_path: Path) -> None:
    from fr.acceptance.report import render_markdown

    root = make_repo(tmp_path, _EVERY_PANEL)
    m = load_effective(root)
    links = _links(root, "github")
    md = render_markdown(m, links, stamp="s")
    assert "| status | count |" in md and "sharp line" in md and "(4 rows)" in md
    page = render(m, links, stamp="s")
    assert '<div class="tiles">' in page and "sharp line" in page and "(4 rows)" in page


def test_summary_still_carries_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`fr acceptance summary` (the Actions job summary) and `status` keep the
    counts the committed reports dropped."""
    root = make_repo(tmp_path, _EVERY_PANEL)
    monkeypatch.setenv("FR_REPO_ROOT", str(root))
    summary = runner.invoke(app, ["acceptance", "summary"])
    assert summary.exit_code == 0, summary.output
    assert "| not-implemented | 1 |" in summary.output
    status = runner.invoke(app, ["acceptance", "status"])
    assert "not-implemented: 1" in status.output
