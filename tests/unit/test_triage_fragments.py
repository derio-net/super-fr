"""Shared page chrome and fragments (spec 2026-10-05-triage-pages-goal, §A, §C)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fr.triage.components import PAGES
from fr.triage.errors import TriageError
from fr.triage.fragments import Entry, Resolved, resolve_manifest, splice


def test_pages_registry_lists_the_four_pages() -> None:
    assert tuple(p.key for p in PAGES) == ("board", "origins", "architecture", "history")
    assert tuple(p.file for p in PAGES) == (
        "triage.html",
        "origins.html",
        "architecture.html",
        "history.html",
    )
    assert all(p.goal.endswith("?") and p.title for p in PAGES)


def test_page_header_marks_the_current_page_and_states_the_goal() -> None:
    from fr.triage.components import page_header

    h = page_header("origins")
    assert "<nav" in h
    for p in PAGES:
        assert f'href="{p.file}"' in h
    assert h.count('aria-current="page"') == 1
    assert re.search(r'<a [^>]*href="origins.html"[^>]*aria-current="page"', h) or re.search(
        r'<a [^>]*aria-current="page"[^>]*href="origins.html"', h
    )
    assert re.search(r'class="goal"[^>]*>[^<]*Where do defects come from', h)


def test_collapsed_renders_a_closed_fold_with_title_and_count() -> None:
    from fr.triage.components import collapsed

    h = collapsed("x", "A <Title>", 3, "<p>b</p>")
    assert h.startswith('<details id="x" class="fold">')
    assert " open" not in h.split(">")[0]
    assert "<summary>A &lt;Title&gt;" in h and '<span class="count">3</span>' in h
    assert "<p>b</p>" in h
    assert 'class="count"' not in collapsed("y", "T", None, "")


# ---------------------------------------------------------------------- manifest

GEN = ("summary", "subsystems", "size-table")


def _arch(tmp_path: Path, manifest: str, **files: str) -> Path:
    d = tmp_path / "architecture"
    d.mkdir()
    (d / "manifest.yaml").write_text(manifest, encoding="utf-8")
    for name, text in files.items():
        (d / name.replace("__", ".")).write_text(text, encoding="utf-8")
    return d


def test_manifest_resolves_generated_names_and_fragment_files_in_order(tmp_path: Path) -> None:
    d = _arch(
        tmp_path,
        "sections:\n  - subsystems\n  - overview.html\n  - size-table\n  - second.html\n",
        overview__html="<p>one</p>",
        second__html="<p>two</p>",
    )
    resolved = resolve_manifest(d, GEN)
    named = ["subsystems", "overview.html", "size-table", "second.html"]
    assert [e.name for e in resolved.order] == [*named, *(g for g in GEN if g not in named)]
    assert resolved.fragments == {"overview.html": "<p>one</p>", "second.html": "<p>two</p>"}
    assert resolved.missing == []


def test_a_manifest_entry_with_no_file_is_reported(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - summary\n  - gone.html\n")
    resolved = resolve_manifest(d, GEN)
    assert resolved.missing == ["gone.html"]
    assert "gone.html" not in resolved.fragments


def test_a_malformed_fragment_is_refused_and_named(tmp_path: Path) -> None:
    d = _arch(
        tmp_path, "sections:\n  - ok.html\n  - bad.html\n",
        ok__html="<p>fine</p>", bad__html="<div><p>never closed</div>",
    )  # fmt: skip
    with pytest.raises(TriageError, match=r"bad\.html"):
        resolve_manifest(d, GEN)


@pytest.mark.parametrize(
    "text",
    ["<div>open", "</p>", "<ul><li>x</ul>", "<svg><g></svg>", "<html><body>x</body></html>",
     "<script>alert(1)</script>"],
)  # fmt: skip
def test_malformed_or_document_level_fragments_are_refused(tmp_path: Path, text: str) -> None:
    d = _arch(tmp_path, "sections:\n  - f.html\n", f__html=text)
    with pytest.raises(TriageError, match=r"f\.html"):
        resolve_manifest(d, GEN)


def test_well_formed_fragments_with_void_and_self_closing_tags_pass(tmp_path: Path) -> None:
    d = _arch(
        tmp_path,
        "sections:\n  - f.html\n",
        f__html=(
            '<p>a<br>b</p><img src="x.png" alt=""><svg viewBox="0 0 4 4"><path d="M0 0"/></svg>'
        ),
    )
    assert "f.html" in resolve_manifest(d, GEN).fragments


@pytest.mark.parametrize(
    "text",
    [
        "<style>p{color:red}</style>",
        '<link rel="stylesheet" href="x.css">',
        '<iframe src="https://example.com"></iframe>',
        '<object data="x.swf"></object>',
        '<embed src="x.swf">',
        '<meta http-equiv="refresh" content="0">',
        '<base href="https://example.com/">',
        '<form action="/x"><p>x</p></form>',
        "<head><p>x</p></head>",
        "<body><p>x</p></body>",
        "<title>Page</title>",
        '<p onclick="go()">x</p>',
        '<svg><g onload="go()"></g></svg>',
        '<a href="javascript:alert(1)">x</a>',
        '<a href="  JaVa\tScript:alert(1)">x</a>',
        '<img src="data:text/html;base64,AAAA" alt="">',
        '<svg><a xlink:href="javascript:alert(1)"><text>x</text></a></svg>',
    ],
)
def test_forbidden_constructs_are_each_refused(tmp_path: Path, text: str) -> None:
    d = _arch(tmp_path, "sections:\n  - f.html\n", f__html=text)
    with pytest.raises(TriageError, match=r"f\.html"):
        resolve_manifest(d, GEN)


def test_a_title_inside_an_svg_is_an_accessible_name_and_allowed(tmp_path: Path) -> None:
    d = _arch(
        tmp_path,
        "sections:\n  - f.html\n",
        f__html='<svg viewBox="0 0 4 4"><title>Flow of work</title><rect/></svg>',
    )
    assert "f.html" in resolve_manifest(d, GEN).fragments


def test_ordinary_links_and_https_urls_are_allowed(tmp_path: Path) -> None:
    d = _arch(
        tmp_path,
        "sections:\n  - f.html\n",
        f__html=(
            '<p><a href="https://example.com/x">x</a> '
            '<img src="data:image/png;base64,AA" alt=""></p>'
        ),
    )
    assert "f.html" in resolve_manifest(d, GEN).fragments


def test_a_self_closing_non_void_html_tag_is_refused_with_line_and_tag(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - f.html\n", f__html="<p>a</p>\n<div/>\n")
    with pytest.raises(TriageError, match=r"<div/>.*line 2|line 2.*<div/>"):
        resolve_manifest(d, GEN)


def test_self_closing_is_fine_on_svg_shapes(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - f.html\n", f__html="<svg><g/><circle/></svg><br/>")
    assert "f.html" in resolve_manifest(d, GEN).fragments


def test_a_fragment_path_may_not_leave_the_architecture_directory(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - ../secret.html\n")
    with pytest.raises(TriageError, match="architecture"):
        resolve_manifest(d, GEN)


def test_no_manifest_means_every_generated_section_and_no_fragments(tmp_path: Path) -> None:
    resolved = resolve_manifest(tmp_path / "architecture", GEN)
    assert [e.name for e in resolved.order] == list(GEN)
    assert resolved.fragments == {} and resolved.missing == []


def test_a_manifest_naming_only_fragments_appends_the_generated_names(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - one.html\n", one__html="<p>1</p>")
    resolved = resolve_manifest(d, GEN)
    assert [e.name for e in resolved.order] == ["one.html", *GEN]
    assert resolved.appended == list(GEN)


def test_order_is_a_list_of_entries_and_a_mapping_entry_parses(tmp_path: Path) -> None:
    d = _arch(
        tmp_path,
        "sections:\n  - summary\n  - fragment: a.html\n    title: Hist\n    collapsed: true\n",
        a__html="<p>a</p>",
    )
    resolved = resolve_manifest(d, GEN)
    assert resolved.order[0] == Entry("summary", None, False)
    assert resolved.order[1] == Entry("a.html", "Hist", True)
    assert resolved.fragments == {"a.html": "<p>a</p>"}


@pytest.mark.parametrize(
    "entry",
    [
        "- fragment: a.html\n    colapsed: true",
        "- fragment: summary",
        "- title: nothing",
        "- fragment: a.html\n    collapsed: sure",
    ],
)
def test_a_bad_mapping_entry_is_refused(tmp_path: Path, entry: str) -> None:
    d = _arch(tmp_path, f"sections:\n  {entry}\n", a__html="<p>a</p>")
    with pytest.raises(TriageError):
        resolve_manifest(d, GEN)


def test_a_moved_name_lands_in_moved_not_missing(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - waves\n  - summary\n")
    resolved = resolve_manifest(d, GEN, {"waves": "board"})
    assert resolved.moved == {"waves": "board"}
    assert resolved.missing == []
    assert "waves" not in [e.name for e in resolved.order]


def test_a_fragment_between_two_generated_sections_renders_there() -> None:
    resolved = Resolved(
        order=[
            Entry("gen-a", None, False),
            Entry("f.html", None, False),
            Entry("gen-b", None, False),
        ],
        fragments={"f.html": "<p>FRAG</p>"},
    )
    out = splice(resolved, {"gen-a": lambda: "<i>A</i>", "gen-b": lambda: "<i>B</i>"})
    assert [("<i>A</i>" in o, "FRAG" in o, "<i>B</i>" in o) for o in out] == [
        (True, False, False),
        (False, True, False),
        (False, False, True),
    ]
    assert 'data-fragment="f.html"' in out[1]


def test_a_collapsed_entry_renders_closed_with_its_title() -> None:
    resolved = Resolved(
        order=[Entry("f.html", "Dated <history>", True)], fragments={"f.html": "<p>FRAG</p>"}
    )
    (out,) = splice(resolved, {})
    assert out.startswith("<details")
    assert 'class="fold"' in out and " open" not in out.split(">")[0]
    assert "Dated &lt;history&gt;" in out and "<p>FRAG</p>" in out


def test_collapsed_fragments_whose_names_slug_alike_get_distinct_ids() -> None:
    resolved = Resolved(
        order=[Entry("a_b.html", "One", True), Entry("a-b.html", "Two", True)],
        fragments={"a_b.html": "<p>1</p>", "a-b.html": "<p>2</p>"},
    )
    ids = [m.group(1) for out in splice(resolved, {}) if (m := re.search(r'id="([^"]+)"', out))]
    assert len(ids) == 2 and len(set(ids)) == 2


def test_a_missing_entry_renders_nothing(tmp_path: Path) -> None:
    d = _arch(tmp_path, "sections:\n  - gone.html\n")
    resolved = resolve_manifest(d, GEN)
    assert splice(resolved, {g: (lambda: "x") for g in GEN})[:1] != [""]
    assert all("gone" not in o for o in splice(resolved, {}))
