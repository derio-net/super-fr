"""The site build's pure parts (spec 2026-11-11-docs-currency §C, R12-R17).

`scripts/build-site.py` runs without `fr`, so it is loaded by path. Rendering is a
subprocess and is not exercised here; the page set, routes, link rewrite and index
list are pure and need no renderer.
"""

from __future__ import annotations

import importlib.util
import re
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


@pytest.mark.parametrize(
    "line",
    [
        "[x]: fr-isolation.md\n",
        "![shot](img/shot.png)\n",
        '<a href="fr-isolation.md">x</a>\n',
        '<img src="img/shot.png">\n',
    ],
)
def test_a_relative_link_in_a_shape_the_build_does_not_rewrite_is_refused(line: str) -> None:
    with pytest.raises(bs.BuildError, match="not rewritten"):
        bs.rewrite_markdown(line, "docs/explainers/index.md", PATTERNS, TRACKED, REF)


def test_absolute_links_in_those_shapes_and_code_samples_pass() -> None:
    text = (
        "[x]: https://example.org/a\n"
        "![shot](https://example.org/s.png)\n"
        '<a href="#top">x</a> and `<a href="nope.md">`\n'
        '```html\n<a href="nope.md">x</a>\n```\n'
    )
    assert bs.rewrite_markdown(text, "docs/explainers/index.md", PATTERNS, TRACKED, REF) == text


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


# -- the landing source (spec 2026-11-12-landing-front-page R1, R3, R4, R9) -----------

FRONT = """---
title: "T"
tldr: "A tldr."
layout: landing
hero:
  eyebrow: "super-fr"
  headline: "A headline"
  subline: "A subline."
  command: "/fr-goal do a thing"
  primary: {label: "Go", href: "01-fr-goal.md"}
  secondary:
    - {label: "Install", href: "../reference/cli.md"}
    - {label: "GitHub", href: "https://github.com/derio-net/super-fr"}
facts:
  - {figure: "1", caption: "round"}
---
"""

FLOW = (
    "## How a run goes\n<!-- landing:flow -->\n\n"
    "1. {you} Answer the round.\n2. The agent builds.\n3. {you} You merge.\n\n"
)
PAGES = "## Every page\n<!-- landing:pages -->\n\nIntro.\n\n<!-- site:pages -->\n\n"
CTA = "## Try it\n<!-- landing:cta -->\n\n[Go](01-fr-goal.md)\n"


def guarantee(n: int, *, problem: bool = True, link: bool = True) -> str:
    out = f"## Headline {n}\n<!-- landing:guarantee -->\n\n"
    if problem:
        out += f"> Problem {n}.\n\n"
    out += f"**What you gain.** Gain {n}.\n\n- how one\n- how two\n\n"
    if link:
        out += f"[Read more {n}](fr-isolation.md)\n\n"
    return out


def landing_text(n: int = 7, front: str = FRONT, extra: str = "") -> str:
    return (
        front + "\n" + FLOW + "".join(guarantee(i) for i in range(1, n + 1)) + PAGES + extra + CTA
    )


def parse(text: str):
    return bs.parse_landing(text, "docs/explainers/index.md")


def test_only_layout_landing_is_a_landing() -> None:
    assert bs.is_landing({"layout": "landing"}) is True
    assert bs.is_landing({"layout": "other"}) is False
    assert bs.is_landing({}) is False


def test_a_landing_parses_into_hero_facts_and_ordered_sections() -> None:
    land = parse(landing_text())
    assert land.hero.eyebrow == "super-fr"
    assert land.hero.headline == "A headline"
    assert land.hero.subline == "A subline."
    assert land.hero.command == "/fr-goal do a thing"
    assert (land.hero.primary.label, land.hero.primary.href) == ("Go", "01-fr-goal.md")
    assert [(s.label, s.href) for s in land.hero.secondary] == [
        ("Install", "../reference/cli.md"),
        ("GitHub", "https://github.com/derio-net/super-fr"),
    ]
    assert [(f.figure, f.caption) for f in land.facts] == [("1", "round")]
    assert [s.kind for s in land.sections] == ["flow"] + ["guarantee"] * 7 + ["pages", "cta"]
    assert land.sections[1].heading == "Headline 1"


def test_the_optional_hero_keys_may_be_absent() -> None:
    front = (
        "---\ntitle: T\nlayout: landing\nhero:\n  headline: H\n  subline: S\n"
        "  primary: {label: Go, href: x.md}\n---\n"
    )
    land = parse(landing_text(front=front))
    assert land.hero.eyebrow == "" and land.hero.command == ""
    assert land.hero.secondary == () and land.facts == ()


def test_a_guarantee_section_exposes_problem_link_and_body() -> None:
    sec = parse(landing_text()).sections[1]
    assert sec.problem == "Problem 1."
    assert (sec.link.label, sec.link.href) == ("Read more 1", "fr-isolation.md")
    assert "Gain 1." in sec.body and "how two" in sec.body
    assert "Problem 1" not in sec.body and "Read more" not in sec.body


def test_a_flow_section_marks_the_operators_steps() -> None:
    sec = parse(landing_text()).sections[0]
    assert [(s.text, s.yours) for s in sec.steps] == [
        ("Answer the round.", True),
        ("The agent builds.", False),
        ("You merge.", True),
    ]


def test_a_section_without_a_marker_is_prose_and_a_heading_inside_a_fence_is_not_one() -> None:
    text = landing_text(extra="## Long read\n\n```md\n## not a heading\n```\n\nText.\n\n")
    secs = parse(text).sections
    prose = [s for s in secs if s.kind == "prose"]
    assert len(prose) == 1 and prose[0].heading == "Long read"
    assert "## not a heading" in prose[0].body
    assert len(secs) == 11


def _refused(text: str, match: str) -> None:
    with pytest.raises(bs.BuildError, match=match) as err:
        parse(text)
    assert "docs/explainers/index.md" in str(err.value)


@pytest.mark.parametrize(
    ("old", "new", "match"),
    [
        ("hero:\n", "nothero:\n", "hero"),
        ('  headline: "A headline"\n', "", "hero.headline"),
        ('  subline: "A subline."\n', "", "hero.subline"),
        ('{label: "Go", href: "01-fr-goal.md"}', '{href: "01-fr-goal.md"}', "primary.label"),
        ('{label: "Go", href: "01-fr-goal.md"}', '{label: "Go"}', "primary.href"),
    ],
)
def test_a_missing_hero_key_is_refused_naming_the_key(old: str, new: str, match: str) -> None:
    assert old in FRONT
    _refused(landing_text(front=FRONT.replace(old, new)), match)


def test_an_unknown_section_kind_is_refused() -> None:
    _refused(landing_text(extra="## X\n<!-- landing:carousel -->\n\ntext\n\n"), "carousel")


def test_a_guarantee_without_its_problem_or_its_link_is_refused() -> None:
    base = FRONT + "\n" + FLOW + "".join(guarantee(i) for i in range(2, 8))
    tail = PAGES + CTA
    _refused(base + guarantee(1, problem=False) + tail, "problem")
    _refused(base + guarantee(1, link=False) + tail, "link")


def test_a_guarantee_whose_last_paragraph_is_not_exactly_one_link_is_refused() -> None:
    bad = guarantee(1).replace(
        "[Read more 1](fr-isolation.md)", "See [Read more 1](fr-isolation.md) now"
    )
    base = FRONT + "\n" + FLOW + "".join(guarantee(i) for i in range(2, 8))
    _refused(base + bad + PAGES + CTA, "link")


@pytest.mark.parametrize("n", [0, 5, 9])
def test_fewer_than_six_or_more_than_eight_guarantees_is_refused(n: int) -> None:
    _refused(landing_text(n), "six to eight")


@pytest.mark.parametrize("n", [6, 8])
def test_six_and_eight_guarantees_are_accepted(n: int) -> None:
    assert len([s for s in parse(landing_text(n)).sections if s.kind == "guarantee"]) == n


@pytest.mark.parametrize(
    "body",
    [
        "- a\n- b\n",
        "1. a\n\nProse after.\n",
        "Prose first.\n\n1. a\n",
        "",
    ],
)
def test_a_flow_that_is_not_exactly_one_ordered_list_is_refused(body: str) -> None:
    bad = f"## Flow\n<!-- landing:flow -->\n\n{body}\n"
    text = FRONT + "\n" + bad + "".join(guarantee(i) for i in range(1, 7)) + PAGES + CTA
    _refused(text, "ordered list")


def test_a_pages_section_without_the_marker_is_refused() -> None:
    text = landing_text().replace("<!-- site:pages -->", "")
    _refused(text, "site:pages")


# -- rendering the landing (R1-R6, R10) -----------------------------------------------

LANDING_TRACKED = [
    *TRACKED,
    "docs/explainers/fr-isolation.md",
    "docs/reference/install.md",
    "README.md",
]
LANDING_ENTRIES = [
    bs.Entry("docs/explainers/index.md", "Home", "Welcome. More."),
    bs.Entry("docs/explainers/fr-isolation.md", "Isolation", "The box. Detail."),
    bs.Entry("docs/explainers/01-fr-goal.md", "The goal", "One run. Detail."),
    bs.Entry("docs/ops.md", "Ops", "Manual operations."),
    bs.Entry("docs/reference/cli.md", "CLI", "Every command."),
]
FONT_CSS = "@font-face{src:url(data:font/woff2;base64,AAAA)}"
THEME_CSS = ":root{--ink:#000;--paper:#fff}"


def fake_html(md: str) -> str:
    """A stand-in for python-markdown: structure only, never converted markup."""
    return "".join(f"<p>{b}</p>" for b in bs.split_blocks(md))


def render_landing(text: str | None = None, **kw) -> str:
    land = bs.parse_landing(text or landing_text(), "docs/explainers/index.md")
    args = {
        "title": "Front <page>",
        "entries": LANDING_ENTRIES,
        "font_css": FONT_CSS,
        "patterns": PATTERNS,
        "tracked": LANDING_TRACKED,
        "ref": REF,
        "repo_url": bs.DEFAULT_REPO_URL,
        "theme_css": THEME_CSS,
        "to_html": fake_html,
    }
    args.update(kw)
    return bs.render_landing(land, **args)


def test_the_hero_headline_is_the_only_h1_and_the_title_is_escaped() -> None:
    html = render_landing()
    assert html.count("<h1") == 1
    assert "A headline" in html.split("</h1>")[0]
    assert "<title>Front &lt;page&gt;</title>" in html
    assert "/fr-goal do a thing" in html


def test_hero_links_go_through_the_one_link_rule() -> None:
    front = FRONT.replace("../reference/cli.md", "../reference/install.md")
    html = render_landing(landing_text(front=front))
    assert 'href="01-fr-goal.html"' in html
    assert 'href="reference/install.html"' in html
    assert 'href="https://github.com/derio-net/super-fr"' in html


def test_an_untracked_front_matter_href_fails_the_build() -> None:
    front = FRONT.replace("../reference/cli.md", "../nope.md")
    with pytest.raises(bs.BuildError, match="nope.md"):
        render_landing(landing_text(front=front))


def test_guarantee_sections_are_numbered_in_order() -> None:
    html = render_landing()
    nums = re.findall(r"0\d / 07", html)
    assert nums == [f"0{i} / 07" for i in range(1, 8)]
    assert html.index("Headline 1") < html.index("Headline 7")
    assert 'href="fr-isolation.html"' in html


def test_a_you_flow_step_carries_the_class_yours() -> None:
    html = render_landing()
    items = re.findall(r'<li class="([^"]*)">', html)
    steps = [c for c in items if c.startswith("step")]
    assert [("yours" in c.split()) for c in steps] == [True, False, True]


def test_the_page_list_has_anchored_groups_and_every_entry_but_the_index() -> None:
    html = render_landing()
    for anchor in ("explainers", "guides", "reference"):
        assert f'id="{anchor}"' in html
    assert html.index('id="explainers"') < html.index('id="guides"') < html.index('id="reference"')
    assert 'href="fr-isolation.html"' in html and "The box." in html
    assert "Detail." not in html
    assert 'href="guides/ops.html"' in html and 'href="reference/cli.html"' in html
    assert ">Home<" not in html


def test_body_links_are_rewritten_like_any_other_page() -> None:
    extra = "## Read\n\nSee [iso](fr-isolation.md) and [the report](./acceptance/).\n\n"
    html = render_landing(landing_text(extra=extra))
    assert "iso](fr-isolation.html)" in html or 'href="fr-isolation.html">iso' in html
    assert "(./acceptance/)" in html or 'href="./acceptance/"' in html
    with pytest.raises(bs.BuildError, match="nope.md"):
        render_landing(landing_text(extra="## R\n\n[x](nope.md)\n\n"))


def test_a_cta_paragraph_of_links_becomes_buttons() -> None:
    html = render_landing()
    tail = html[html.rindex("cta") :]
    assert 'class="btn' in tail and 'href="01-fr-goal.html"' in tail


def test_the_page_embeds_the_given_css_and_carries_no_script_or_foreign_request() -> None:
    html = render_landing()
    assert FONT_CSS in html and THEME_CSS in html
    assert html.index(THEME_CSS) < html.index("prefers-color-scheme: light")
    assert 'name="color-scheme" content="dark light"' in html
    assert "<script" not in html
    assert not re.search(r"(?:src=|url\()\s*[\"']?https?:", html)
    assert not re.search(r"<link[^>]*href=[\"']?https?:", html)
    assert re.search(r"@media \(prefers-color-scheme: light\)", html)


def test_font_css_is_every_font_face_rule_of_a_rendered_page() -> None:
    page = "<style>@font-face{a:1}@font-face{b:url(data:x)}body{}</style>"
    assert bs.extract_font_css(page) == "@font-face{a:1}\n@font-face{b:url(data:x)}"
    with pytest.raises(bs.BuildError, match="font"):
        bs.extract_font_css("<style>body{}</style>")


def test_theme_css_is_the_rendered_pages_root_block() -> None:
    block = ":root{\n" + ";".join(f"{name}:#0b0c10" for name in bs.THEME_PROPERTIES) + "}"
    page = f"<style>{block}\nbody{{color:red}}</style>"
    assert bs.extract_theme_css(page) == block
    with pytest.raises(bs.BuildError, match=":root"):
        bs.extract_theme_css("<style>body{}</style>")
    with pytest.raises(bs.BuildError, match="--ink"):
        bs.extract_theme_css("<style>:root{--bg:#fff}</style>")


@pytest.mark.parametrize("missing", ["--paper", "--ink-2", "--brass", "--display", "--mono"])
def test_a_theme_missing_a_property_the_landing_uses_is_refused(missing: str) -> None:
    """A renamed renderer property must fail the build, not ship an unstyled landing."""
    names = [n for n in bs.THEME_PROPERTIES if n != missing]
    page = "<style>:root{" + ";".join(f"{n}:#0b0c10" for n in names) + "}</style>"
    with pytest.raises(bs.BuildError, match=re.escape(missing) + r"\b"):
        bs.extract_theme_css(page)


def test_every_property_the_site_stylesheets_use_is_a_required_theme_property() -> None:
    used: set[str] = set()
    for sheet in bs.SITE_DIR.glob("*.css"):
        if sheet.name == "figures.css":  # its own --fig-* vocabulary, tested below
            continue
        used |= set(re.findall(r"var\((--[a-z0-9-]+)", sheet.read_text(encoding="utf-8")))
    assert used == set(bs.THEME_PROPERTIES)


# -- the top bar (R8, R9, R11) ---------------------------------------------------------

PAGE_HTML = "<html><head><title>x</title></head><body>\n<article>a</article></body></html>"


@pytest.mark.parametrize(
    ("route_name", "home"),
    [
        ("index.html", "index.html"),
        ("x.html", "index.html"),
        ("guides/x.html", "../index.html"),
        ("reference/x.html", "../index.html"),
    ],
)
def test_the_bar_links_are_right_from_every_route_depth(route_name: str, home: str) -> None:
    out = bs.insert_bar(PAGE_HTML, route_name, "https://github.com/o/r", "/*bar*/")
    nav = re.search(r'<nav class="site-bar".*?</nav>', out, re.DOTALL)
    assert nav is not None
    hrefs = re.findall(r'href="([^"]+)"', nav.group(0))
    assert hrefs == [
        home,
        f"{home}#explainers",
        f"{home}#guides",
        f"{home}#reference",
        "https://github.com/o/r",
    ]
    assert "super-fr" in nav.group(0)


def test_the_bar_sits_right_after_the_body_tag_and_its_style_before_the_head_closes() -> None:
    out = bs.insert_bar(PAGE_HTML, "x.html", "https://github.com/o/r", "/*bar*/")
    assert re.search(r'<body>\s*<nav class="site-bar"', out)
    assert "<style>/*bar*/</style></head>" in out
    assert out.count('site-bar"') == 1
    out2 = bs.insert_bar(
        PAGE_HTML.replace("<body>", '<body class="a">'), "x.html", "https://x/y", "/**/"
    )
    assert re.search(r'<body class="a">\s*<nav class="site-bar"', out2)


@pytest.mark.parametrize(
    "html",
    [
        "<html><head></head><p>no body</p></html>",
        "<html><head></head><body><body></body></html>",
        "<html><body>no head close</body></html>",
        "<html><head></head><head></head><body></body></html>",
    ],
)
def test_a_page_that_cannot_take_the_bar_exactly_once_is_refused(html: str) -> None:
    with pytest.raises(bs.BuildError, match="y/x.html"):
        bs.insert_bar(html, "y/x.html", "https://github.com/o/r", "/**/")


def _mini_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / ".fr").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / ".fr" / "docs.yaml").write_text("pages:\n  - docs/*.md\n")
    for name in ("a", "b"):
        (root / "docs" / f"{name}.md").write_text(f"---\ntitle: {name}\n---\n\nBody {name}\n")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    craft = tmp_path / "craft"
    (craft / "tools").mkdir(parents=True)
    (craft / "tools" / "render_explainer.py").write_text("")
    (craft / bs.FONTS_SUBDIR).mkdir(parents=True)
    return root, craft


def _fake_renderer(bad: str | None):
    good = (
        "<html><head><style>@font-face{src:url(data:font/woff2;base64,AA)}</style></head>"
        "<body><article>x</article></body></html>"
    )

    def render(renderer, fonts, source, out):
        html = good
        if bad and source.name == f"{bad}.md":
            html = "<html><head></head><p>no body at all</p></html>"
        out.write_text(html, encoding="utf-8")
        return html

    return render


def test_a_page_that_cannot_take_the_bar_leaves_no_file_in_the_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, craft = _mini_repo(tmp_path)
    out = tmp_path / "out"
    monkeypatch.setattr(bs, "render_page", _fake_renderer("b"))
    with pytest.raises(bs.BuildError, match="guides/b.html"):
        bs.build(root, out, craft, REF, "https://github.com/o/r")
    assert not (out / "guides" / "b.html").exists()
    assert not list(out.rglob("*.html"))


def test_a_page_with_no_embedded_font_leaves_no_file_in_the_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, craft = _mini_repo(tmp_path)
    out = tmp_path / "out"

    def render(renderer, fonts, source, target):
        html = "<html><head></head><body>x</body></html>"
        target.write_text(html, encoding="utf-8")
        return html

    monkeypatch.setattr(bs, "render_page", render)
    with pytest.raises(bs.BuildError, match="@font-face"):
        bs.build(root, out, craft, REF, "https://github.com/o/r")
    assert not list(out.rglob("*.html"))


def test_a_good_build_writes_every_page_with_its_bar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, craft = _mini_repo(tmp_path)
    out = tmp_path / "out"
    monkeypatch.setattr(bs, "render_page", _fake_renderer(None))
    written = bs.build(root, out, craft, REF, "https://github.com/o/r")
    assert sorted(written) == ["guides/a.html", "guides/b.html"]
    assert 'href="../index.html"' in (out / "guides" / "a.html").read_text()


def test_layout_landing_on_a_page_not_routed_to_index_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, craft = _mini_repo(tmp_path)
    (root / "docs" / "a.md").write_text("---\ntitle: a\nlayout: landing\n---\n\nBody\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    monkeypatch.setattr(bs, "render_page", _fake_renderer(None))
    out = tmp_path / "out"
    with pytest.raises(bs.BuildError, match=r"docs/a.md.*landing"):
        bs.build(root, out, craft, REF, "https://github.com/o/r")
    assert not list(out.rglob("*.html"))


def test_this_repos_front_page_is_a_valid_landing_whose_links_all_resolve() -> None:
    page = "docs/explainers/index.md"
    text = (REPO / page).read_text(encoding="utf-8")
    assert bs.is_landing(bs.parse_front_matter(text))
    land = bs.parse_landing(text, page)
    guarantees = [s for s in land.sections if s.kind == "guarantee"]
    assert 6 <= len(guarantees) <= 8
    assert len(land.hero.headline.split()) <= 10
    tracked = bs.tracked_files(REPO)
    patterns = bs.load_config(REPO / ".fr" / "docs.yaml")
    hrefs = [land.hero.primary.href, *(x.href for x in land.hero.secondary)]
    hrefs += [s.link.href for s in guarantees if s.link]
    for h in hrefs:
        bs.rewrite_href(h, page, patterns, tracked, REF)
    for sec in land.sections:
        bs.rewrite_markdown(sec.body, page, patterns, tracked, REF)
    assert bs.rewrite_href("01-fr-goal.md", page, patterns, tracked, REF) == "01-fr-goal.html"


# -- figures (spec 2026-11-12-front-page-second-pass B, R6, R10) ---------------------------

FIGURES = REPO / "scripts" / "site" / "figures"

GOOD_FIGURE = (
    '<svg viewBox="0 0 10 10" role="img">\n'
    "<title>A box</title>\n"
    '<defs><linearGradient id="box--fade"><stop offset="0" class="fig-accent"/>'
    "</linearGradient></defs>\n"
    '<rect id="box--r" class="fig-panel" fill="url(#box--fade)" stroke="currentColor"/>\n'
    '<use href="#box--r"/>\n'
    "</svg>"
)


def test_the_figures_directory_exists() -> None:
    assert FIGURES.is_dir()


def test_a_valid_figure_passes() -> None:
    bs.check_figure(GOOD_FIGURE, "box")


@pytest.mark.parametrize(
    ("old", "new", "match"),
    [
        (' role="img"', "", "role"),
        ("<title>A box</title>", "<title> </title>", "title"),
        ("<title>A box</title>\n", "<g/><title>A box</title>\n", "title"),
        ("<rect", "<script>1</script><rect", "script"),
        ("<rect", '<rect onclick="x()"', "on"),
        ("<rect", '<image href="#a"/><rect', "image"),
        ("<rect", "<foreignObject/><rect", "foreignObject"),
        ('href="#box--r"', 'href="https://example.com/a.svg"', "href"),
        ('href="#box--r"', 'xlink:href="a.svg"', "href"),
        ("url(#box--fade)", "url(https://example.com/x)", "url"),
        ('stroke="currentColor"', 'stroke="#fff"', "colour"),
        ('stroke="currentColor"', 'stroke="rgb(1,2,3)"', "colour"),
        ('stroke="currentColor"', 'stroke="hsl(1,2%,3%)"', "colour"),
        ('stroke="currentColor"', 'stroke="red"', "colour"),
        ('stroke="currentColor"', 'style="stop-color:#000"', "colour"),
        ("<rect", "<style>.a{fill:#123456}</style><rect", "colour"),
        ('id="box--r"', 'id="r"', "id"),
        ('id="box--fade"', 'id="fade"', "id"),
    ],
)
def test_a_defective_figure_is_refused_naming_it_and_the_defect(
    old: str, new: str, match: str
) -> None:
    with pytest.raises(bs.BuildError, match=rf"box.*{match}"):
        bs.check_figure(GOOD_FIGURE.replace(old, new, 1), "box")


@pytest.mark.parametrize("value", ["none", "currentColor", "inherit", "transparent", "var(--x)"])
def test_the_allowed_paint_keywords_pass(value: str) -> None:
    bs.check_figure(GOOD_FIGURE.replace('stroke="currentColor"', f'stroke="{value}"'), "box")


def test_a_narrow_figure_prefixes_its_ids_with_the_narrow_name() -> None:
    narrow = GOOD_FIGURE.replace("box--", "box-narrow--")
    bs.check_figure(narrow, "box.narrow")
    with pytest.raises(bs.BuildError, match="id"):
        bs.check_figure(GOOD_FIGURE, "box.narrow")


def _figure_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "figures"
    d.mkdir()
    monkeypatch.setattr(bs, "FIGURES_DIR", d)
    return d


def test_load_figure_inlines_the_wide_and_narrow_forms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = _figure_dir(tmp_path, monkeypatch)
    (d / "box.svg").write_text(GOOD_FIGURE)
    (d / "box.narrow.svg").write_text(GOOD_FIGURE.replace("box--", "box-narrow--"))
    out = bs.load_figure("box")
    assert out.startswith('<figure class="site-figure">') and out.endswith("</figure>")
    assert out.count("<svg") == 2
    assert 'class="fig-wide"' in out and 'class="fig-narrow"' in out


def test_load_figure_without_a_narrow_form_has_only_the_wide_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = _figure_dir(tmp_path, monkeypatch)
    (d / "box.svg").write_text(GOOD_FIGURE)
    out = bs.load_figure("box")
    assert out.count("<svg") == 1 and "fig-narrow" not in out


def test_a_missing_figure_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _figure_dir(tmp_path, monkeypatch)
    with pytest.raises(bs.BuildError, match="nope"):
        bs.load_figure("nope")


def test_a_defective_figure_file_is_refused_on_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = _figure_dir(tmp_path, monkeypatch)
    (d / "box.svg").write_text(GOOD_FIGURE.replace(' role="img"', ""))
    with pytest.raises(bs.BuildError, match="box"):
        bs.load_figure("box")


def test_blank_lines_inside_a_figure_are_removed_so_markdown_keeps_one_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = _figure_dir(tmp_path, monkeypatch)
    (d / "box.svg").write_text(GOOD_FIGURE.replace("\n", "\n\n"))
    assert "\n\n" not in bs.load_figure("box")


# -- the marker (P1.T2) ---------------------------------------------------------------------


def test_a_marker_line_becomes_the_figure_padded_by_blank_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = _figure_dir(tmp_path, monkeypatch)
    (d / "box.svg").write_text(GOOD_FIGURE)
    text, inserted = bs.fill_figures("a\n\n<!-- site:figure box -->\nb\n", "x.md")
    assert text.startswith("a\n\n\n<figure")
    assert text.endswith("</figure>\n\nb\n")
    assert len(inserted) == 1 and inserted[0].startswith("<svg") and inserted[0] in text
    assert inserted[0].endswith("</svg>")


def test_a_marker_naming_a_missing_figure_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _figure_dir(tmp_path, monkeypatch)
    with pytest.raises(bs.BuildError, match=r"x\.md.*nope"):
        bs.fill_figures("<!-- site:figure nope -->\n", "x.md")


def test_a_marker_inside_a_fenced_block_is_left_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _figure_dir(tmp_path, monkeypatch)
    src = "```\n<!-- site:figure nope -->\n```\n"
    assert bs.fill_figures(src, "x.md") == (src, [])


def test_a_text_without_a_marker_is_unchanged_by_fill_figures() -> None:
    assert bs.fill_figures("plain\n", "x.md") == ("plain\n", [])


def test_a_marker_with_an_invalid_name_is_refused() -> None:
    with pytest.raises(bs.BuildError, match="Bad_Name"):
        bs.fill_figures("<!-- site:figure Bad_Name -->\n", "x.md")


def test_a_figure_that_survives_rendering_passes() -> None:
    svg = '<svg role="img"><title>t</title></svg>'
    bs.check_figures_survived(f"<body><figure>{svg}</figure></body>", [svg], "x.html")


def test_a_figure_the_renderer_altered_is_refused() -> None:
    svg = '<svg role="img"><title>t</title></svg>'
    with pytest.raises(bs.BuildError, match="x.html"):
        bs.check_figures_survived("<body><p>&lt;svg</p></body>", [svg], "x.html")


def test_the_figure_stylesheet_is_added_only_to_a_page_with_a_figure() -> None:
    with_css = bs.insert_figure_css(PAGE_HTML, "x.html", "/*fig*/")
    assert "<style>/*fig*/</style></head>" in with_css
    barred = bs.insert_bar(PAGE_HTML, "x.html", "https://github.com/o/r", "/*bar*/")
    assert 'class="site-bar"' in barred and "/*fig*/" not in barred


def test_an_article_page_without_a_figure_is_built_with_the_bar_and_no_figure_css(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, craft = _mini_repo(tmp_path)
    out = tmp_path / "out"
    monkeypatch.setattr(bs, "render_page", _fake_renderer(None))
    bs.build(root, out, craft, REF, "https://github.com/o/r")
    page = (out / "guides" / "a.html").read_text()
    assert 'class="site-bar"' in page and "site-figure" not in page
    assert ".fig-ink" not in page


def test_a_built_page_with_a_figure_carries_it_and_the_figure_css(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, craft = _mini_repo(tmp_path)
    (root / "docs" / "a.md").write_text(
        "---\ntitle: a\n---\n\nBody\n\n<!-- site:figure gate-ledger -->\n"
    )
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    svg = bs.load_figure("gate-ledger")

    def render(renderer, fonts, source, out):
        body = source.read_text(encoding="utf-8")
        html = (
            "<html><head><style>@font-face{src:url(data:font/woff2;base64,AA)}</style></head>"
            f"<body><article>{body}</article></body></html>"
        )
        out.write_text(html, encoding="utf-8")
        return html

    monkeypatch.setattr(bs, "render_page", render)
    out = tmp_path / "out"
    bs.build(root, out, craft, REF, "https://github.com/o/r")
    a = (out / "guides" / "a.html").read_text()
    assert svg in a and ".fig-ink" in a
    assert ".fig-ink" not in (out / "guides" / "b.html").read_text()


def test_a_figure_the_renderer_drops_fails_the_build_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, craft = _mini_repo(tmp_path)
    (root / "docs" / "a.md").write_text("---\ntitle: a\n---\n\n<!-- site:figure gate-ledger -->\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    monkeypatch.setattr(bs, "render_page", _fake_renderer(None))
    out = tmp_path / "out"
    with pytest.raises(bs.BuildError, match="guides/a.html"):
        bs.build(root, out, craft, REF, "https://github.com/o/r")
    assert not list(out.rglob("*.html"))


def _strip_media(css: str, query: str) -> str:
    """`css` with every `@media (<query>) { … }` block removed (balanced braces)."""
    pattern = re.compile(rf"@media\s*\(\s*{query}\s*\)\s*\{{")
    while (m := pattern.search(css)) is not None:
        depth, i = 1, m.end()
        while depth and i < len(css):
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        css = css[: m.start()] + css[i:]
    return css


def test_every_animation_in_figures_css_sits_under_no_preference_with_a_reduce_block() -> None:
    css = (REPO / "scripts" / "site" / "figures.css").read_text()
    reduce_blocks = re.findall(
        r"@media\s*\(\s*prefers-reduced-motion:\s*reduce\s*\)\s*\{(.*)", css, re.DOTALL
    )
    assert reduce_blocks, "figures.css needs a prefers-reduced-motion: reduce block"
    assert "animation:none" in reduce_blocks[0].replace(" ", "")
    outside = _strip_media(
        _strip_media(css, r"prefers-reduced-motion:\s*no-preference"),
        r"prefers-reduced-motion:\s*reduce",
    )
    assert "animation" not in outside, outside


def test_every_shipped_figure_passes_the_checks_and_the_two_new_ones_exist() -> None:
    files = sorted(FIGURES.glob("*.svg"))
    names = {f.name for f in files}
    assert {"gate-ledger.svg", "wave-of-batches.svg"} <= names
    for f in files:
        bs.check_figure(f.read_text(encoding="utf-8"), f.name.removesuffix(".svg"))
        bs.load_figure(f.name.removesuffix(".svg").removesuffix(".narrow"))


@pytest.mark.parametrize("name", ["fr-wave-driver", "fr-exit-gates"])
def test_each_new_explainer_has_exactly_one_figure_marker_naming_a_real_figure(
    name: str,
) -> None:
    text = (REPO / "docs" / "explainers" / f"{name}.md").read_text(encoding="utf-8")
    markers = re.findall(r"^<!-- site:figure ([a-z0-9-]+) -->$", text, re.MULTILINE)
    assert len(markers) == 1
    assert (FIGURES / f"{markers[0]}.svg").is_file()
