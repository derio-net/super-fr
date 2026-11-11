"""The site build's pure parts (spec 2026-11-11-docs-currency §C, R12-R17).

`scripts/build-site.py` runs without `fr`, so it is loaded by path. Rendering is a
subprocess and is not exercised here; the page set, routes, link rewrite and index
list are pure and need no renderer.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from fr.docs.globs import match as fr_match

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("build_site", REPO / "scripts" / "build-site.py")
assert _spec is not None and _spec.loader is not None
bs = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("build_site", bs)
_spec.loader.exec_module(bs)

REF = "0123456789abcdef0123456789abcdef01234567"
BLOB = f"https://github.com/derio-net/super-fr/blob/{REF}"
TREE = f"https://github.com/derio-net/super-fr/tree/{REF}"

TRACKED = [
    "README.md",
    "docs/explainers/index.md",
    "docs/explainers/01-fr-goal.md",
    "docs/explainers/fr-isolation.md",
    "docs/ops.md",
    "docs/reference/cli.md",
    "docs/superpowers/specs/x.md",
    "packages/fr/src/fr/docs/check.py",
    "scripts/build-site.py",
]
PATTERNS = ["docs/explainers/*.md", "docs/*.md", "docs/reference/*.md"]

GLOB_TABLE = [
    ("docs/*.md", "docs/ops.md"),
    ("docs/*.md", "docs/superpowers/x.md"),
    ("docs/**", "docs/superpowers/x.md"),
    ("docs/**/x.md", "docs/x.md"),
    ("docs/**/x.md", "docs/a/b/x.md"),
    ("**/x.md", "x.md"),
    ("a?.md", "ab.md"),
    ("a?.md", "a/.md"),
    ("docs/explainers/*.md", "docs/explainers/a/b.md"),
    ("*.md", "docs/ops.md"),
]


@pytest.mark.parametrize(("pattern", "path"), GLOB_TABLE)
def test_the_matcher_agrees_with_fr_docs(pattern: str, path: str) -> None:
    assert bs.match(pattern, path) is fr_match(pattern, path)


def test_the_page_set_is_the_tracked_files_the_globs_select() -> None:
    assert bs.select_pages(PATTERNS, TRACKED) == [
        "docs/explainers/01-fr-goal.md",
        "docs/explainers/fr-isolation.md",
        "docs/explainers/index.md",
        "docs/ops.md",
        "docs/reference/cli.md",
    ]


@pytest.mark.parametrize(
    ("path", "route"),
    [
        ("docs/explainers/index.md", "index.html"),
        ("docs/explainers/01-fr-goal.md", "01-fr-goal.html"),
        ("docs/explainers/fr-isolation.md", "fr-isolation.html"),
        ("docs/ops.md", "guides/ops.html"),
        ("docs/reference/cli.md", "reference/cli.html"),
    ],
)
def test_routes(path: str, route: str) -> None:
    assert bs.route(path) == route


def test_this_repos_published_urls_keep_working() -> None:
    config = bs.load_config(REPO / ".fr" / "docs.yaml")
    routes = {bs.route(p) for p in bs.select_pages(config, bs.tracked_files(REPO))}
    assert {"index.html", "01-fr-goal.html", "fr-isolation.html"} <= routes
    assert "guides/ops.html" in routes


def _rewrite(href: str, page: str = "docs/explainers/index.md") -> str:
    return bs.rewrite_href(href, page, PATTERNS, TRACKED, REF)


def test_a_page_source_becomes_its_route_relative_to_the_linking_page() -> None:
    assert _rewrite("fr-isolation.md") == "fr-isolation.html"
    assert _rewrite("./01-fr-goal.md#why") == "01-fr-goal.html#why"
    assert _rewrite("../ops.md") == "guides/ops.html"
    assert _rewrite("explainers/index.md", "docs/ops.md") == "../index.html"
    assert _rewrite("../ops.md", "docs/reference/cli.md") == "../guides/ops.html"


def test_a_tracked_non_page_becomes_a_blob_url_at_the_ref() -> None:
    assert _rewrite("../../README.md") == f"{BLOB}/README.md"
    assert _rewrite("../../packages/fr/src/fr/docs/check.py#L3") == (
        f"{BLOB}/packages/fr/src/fr/docs/check.py#L3"
    )


def test_a_tracked_directory_becomes_a_tree_url() -> None:
    assert _rewrite("../../packages/fr/src/fr/docs/") == f"{TREE}/packages/fr/src/fr/docs"
    assert _rewrite("../superpowers") == f"{TREE}/docs/superpowers"


def test_an_untracked_relative_path_fails_the_build() -> None:
    with pytest.raises(bs.BuildError, match="nope.md"):
        _rewrite("nope.md")
    with pytest.raises(bs.BuildError):
        _rewrite("../../../outside.md")


@pytest.mark.parametrize(
    "href",
    [
        "https://example.com/x",
        "http://example.com",
        "mailto:a@example.com",
        "#section",
        "./acceptance/",
        "../acceptance/",
        "acceptance/",
    ],
)
def test_absolute_urls_fragments_and_site_routes_are_untouched(href: str) -> None:
    assert _rewrite(href) == href


def test_links_in_code_are_not_rewritten() -> None:
    text = "see [x](fr-isolation.md) and `[y](nope.md)`\n\n```md\n[z](nope.md)\n```\n"
    out = bs.rewrite_markdown(text, "docs/explainers/index.md", PATTERNS, TRACKED, REF)
    assert "[x](fr-isolation.html)" in out
    assert "`[y](nope.md)`" in out
    assert "[z](nope.md)" in out


def test_a_leading_h1_repeating_the_title_is_dropped() -> None:
    page = "---\ntitle: T\n---\n\n# T\n\nBody\n\n# Later\n"
    out = bs.drop_leading_h1(page)
    assert "# T\n" not in out
    assert "# Later" in out and "Body" in out and out.startswith("---\ntitle: T\n---")
    assert bs.drop_leading_h1("---\ntitle: T\n---\n\n## Sub\n") == "---\ntitle: T\n---\n\n## Sub\n"
    assert bs.drop_leading_h1("no front\n# T\n") == "no front\n# T\n"


def test_the_first_sentence_of_a_tldr() -> None:
    assert bs.first_sentence("One two.\n  Three four. Five.") == "One two."
    assert bs.first_sentence("no stop") == "no stop"
    assert bs.first_sentence("Use v1.2 now. Done.") == "Use v1.2 now."


def test_the_pages_marker_becomes_a_list_grouped_by_section() -> None:
    entries = [
        bs.Entry("docs/explainers/index.md", "Home", "Welcome. More."),
        bs.Entry("docs/explainers/fr-isolation.md", "Isolation", "The box. Detail."),
        bs.Entry("docs/ops.md", "Ops", "Manual operations."),
        bs.Entry("docs/reference/cli.md", "CLI", "Every command."),
    ]
    text = "intro\n\n<!-- site:pages -->\n\noutro\n"
    out = bs.fill_pages(text, "docs/explainers/index.md", entries)
    assert "<!-- site:pages -->" not in out
    assert out.index("### Explainers") < out.index("### Guides") < out.index("### Reference")
    assert "- [Isolation](fr-isolation.md): The box." in out
    assert "- [Ops](../ops.md): Manual operations." in out
    assert "- [CLI](../reference/cli.md): Every command." in out
    assert "[Home]" not in out
    assert "Detail" not in out
    assert out.startswith("intro\n") and out.rstrip().endswith("outro")


def test_a_text_without_the_marker_is_unchanged() -> None:
    assert bs.fill_pages("plain\n", "docs/explainers/index.md", []) == "plain\n"


def test_a_rendered_page_without_embedded_fonts_fails() -> None:
    with pytest.raises(bs.BuildError, match="@font-face"):
        bs.check_rendered("<html>no fonts</html>", "x.html")
    bs.check_rendered("@font-face{src:url(data:font/woff2;base64,AAAA)}", "x.html")


def test_the_cli_refuses_a_missing_renderer(tmp_path: Path) -> None:
    done = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "build-site.py"),
            str(tmp_path / "out"),
            "--blog-craft",
            str(tmp_path / "absent"),
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert done.returncode != 0
    assert "render_explainer.py" in done.stderr
