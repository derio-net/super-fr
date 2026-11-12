#!/usr/bin/env python3
"""Build the published site from Markdown sources (spec 2026-11-11-docs-currency §C).

    uv run --isolated --no-project --with markdown --with pyyaml python \\
        scripts/build-site.py <out-dir> [--ref SHA] [--blog-craft DIR] [--repo-url URL]

Reads `.fr/docs.yaml` (it shares no code with `fr`, so the deploy needs no `fr`
to build pages), renders every page it names with the blog-craft renderer at
`<blog-craft>/tools/render_explainer.py` (`--style broadsheet --embed-fonts`) and
writes `<out-dir>/<route>.html`. Routes: a page under `docs/explainers/` keeps its
basename at the site root; `docs/x.md` goes to `guides/x.html` and
`docs/reference/x.md` to `reference/x.html`.

The front page (`layout: landing` on the page routed to `index.html`) is rendered
here, not by blog-craft, from `scripts/site/` (spec 2026-11-12-landing-front-page);
its fonts and dark palette are copied from a page blog-craft rendered in the same
build. Every page, the landing included, gets the top bar of `scripts/site/bar.css`,
and no page is written until every page has rendered, passed `check_rendered` and
taken the bar.

Relative links are rewritten by one rule: a link to another page's source becomes
that page's route, relative to the linking page; a link to any other tracked file
or directory becomes a github.com blob (or tree) URL at `--ref` (default `HEAD`);
a relative link to a path git does not track fails the build. Absolute URLs,
fragments and links that already point at a site route (`./acceptance/`) are left
alone. The marker `<!-- site:pages -->` is replaced by a list of every page,
grouped by section, from their front matter.

The renderer exits 0 and carries on without fonts when it cannot find them, so the
build checks the fonts directory itself and fails a page with no embedded
`@font-face` data URI. The pure functions (page set, routes, links, index list)
are kept apart from the subprocess so the tests need no renderer. Exit codes: 0
built, 1 a build failure.
"""

from __future__ import annotations

import argparse
import html
import os
import posixpath
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REPO_URL = "https://github.com/derio-net/super-fr"
MARKER = "<!-- site:pages -->"
INDEX_SOURCE = "docs/explainers/index.md"
FONTS_SUBDIR = Path("templates/content-type-explainers/shared/fonts/broadsheet")
SECTIONS = (("explainers", "Explainers"), ("guides", "Guides"), ("reference", "Reference"))

_SCHEME = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//)")
_SITE_ROUTE = re.compile(r"^(?:\.{1,2}/)*acceptance/")
_LINK = re.compile(r"(\]\()([^)\s]+)((?:\s+\"[^\"]*\")?\))")
_CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
_FRONT = re.compile(r"\A---[ \t]*\r?\n(.*?\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_SENTENCE = re.compile(r"^(.+?[.!?])(?=\s|$)")


class BuildError(Exception):
    """The site cannot be built as asked (exit 1)."""


@dataclass(frozen=True)
class Entry:
    """A page as the index lists it: its source path, title and full `tldr`."""

    path: str
    title: str
    tldr: str


# -- the glob matcher (a copy of fr.docs.globs; tests keep the two equal) -------------


@cache
def _compile(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i, n = 0, len(pattern)
    while i < n:
        ch = pattern[i]
        if pattern.startswith("**", i):
            i += 2
            if pattern.startswith("/", i):
                out.append("(?:.*/)?")
                i += 1
            else:
                out.append(".*")
        elif ch == "*":
            out.append("[^/]*")
            i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("".join(out) + r"\Z")


def match(pattern: str, path: str) -> bool:
    """Whether `path` matches `pattern`; `*` stays in one segment, `**` spans."""
    return _compile(pattern).match(path) is not None


# -- pure parts -----------------------------------------------------------------------


def select_pages(patterns: list[str], tracked: list[str]) -> list[str]:
    """The tracked files any pattern selects, sorted."""
    return sorted(p for p in tracked if any(match(g, p) for g in patterns))


def route(path: str) -> str:
    """The site route of a page source."""
    stem = posixpath.splitext(path)[0]
    if path.startswith("docs/explainers/"):
        return posixpath.basename(stem) + ".html"
    if path.startswith("docs/reference/"):
        return "reference/" + posixpath.basename(stem) + ".html"
    return "guides/" + posixpath.basename(stem) + ".html"


def _section(path: str) -> str:
    return route(path).split("/", 1)[0] if "/" in route(path) else "explainers"


def rewrite_href(
    href: str,
    page: str,
    patterns: list[str],
    tracked: list[str],
    ref: str,
    repo_url: str = DEFAULT_REPO_URL,
) -> str:
    """One relative link of `page`, rewritten by the build's single rule."""
    if not href or href.startswith("#") or _SCHEME.match(href) or _SITE_ROUTE.match(href):
        return href
    m = re.match(r"^([^#?]*)((?:[#?].*)?)$", href)
    assert m is not None
    target, suffix = m.group(1), m.group(2)
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(page), target))
    if resolved.startswith("../") or resolved == "..":
        raise BuildError(f"{page}: link {href!r} leaves the repository")
    if resolved in select_pages(patterns, tracked):
        here = posixpath.dirname(route(page)) or "."
        return posixpath.relpath(route(resolved), here) + suffix
    if resolved in tracked:
        return f"{repo_url}/blob/{ref}/{resolved}{suffix}"
    if any(t.startswith(resolved + "/") for t in tracked):
        return f"{repo_url}/tree/{ref}/{resolved}{suffix}"
    raise BuildError(f"{page}: link {href!r} points at {resolved}, which git does not track")


def rewrite_markdown(
    text: str,
    page: str,
    patterns: list[str],
    tracked: list[str],
    ref: str,
    repo_url: str = DEFAULT_REPO_URL,
) -> str:
    """`text` with every inline Markdown link outside code rewritten.

    Fenced code and backtick spans are skipped. Three shapes the rewrite cannot
    carry are refused when they are relative, so none ships broken: a
    reference-style definition (`[x]: path`), an image (`![alt](path)`) and a raw
    HTML `href=`/`src=`. Use an inline link, or an absolute URL. An indented
    (four-space) code block is NOT recognised: fence code that holds a link.
    """

    def line(raw: str) -> str:
        out: list[str] = []
        last = 0
        for span in _CODE_SPAN.finditer(raw):
            out.append(_links(raw[last : span.start()]))
            out.append(span.group(0))
            last = span.end()
        out.append(_links(raw[last:]))
        return "".join(out)

    def _links(chunk: str) -> str:
        return _LINK.sub(
            lambda m: (
                m.group(1)
                + rewrite_href(m.group(2), page, patterns, tracked, ref, repo_url)
                + m.group(3)
            ),
            chunk,
        )

    fenced = False
    result: list[str] = []
    for raw in text.splitlines(keepends=True):
        if raw.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            result.append(raw)
        else:
            if not fenced:
                _refuse_unsupported(raw, page)
            result.append(raw if fenced else line(raw))
    return "".join(result)


_REF_DEF = re.compile(r"^ {0,3}\[[^\]]+\]:\s+<?([^\s>]+)")
_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
_RAW_ATTR = re.compile(r"""\b(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def _relative(href: str) -> bool:
    return bool(href) and not (
        href.startswith("#") or _SCHEME.match(href) or _SITE_ROUTE.match(href)
    )


def _refuse_unsupported(raw: str, page: str) -> None:
    """Refuse a relative link in a shape `rewrite_markdown` does not rewrite."""
    bare = _CODE_SPAN.sub("", raw)
    found = _REF_DEF.match(bare)
    shapes = [
        ("reference-style link definition", [found.group(1)] if found else []),
        ("image", _IMAGE.findall(bare)),
        ("raw HTML link", _RAW_ATTR.findall(bare)),
    ]
    for shape, hrefs in shapes:
        for href in hrefs:
            if _relative(href):
                raise BuildError(
                    f"{page}: relative {shape} {href!r} is not rewritten by the build; "
                    "use an inline Markdown link or an absolute URL"
                )


def first_sentence(tldr: str) -> str:
    """The first sentence of `tldr`, whitespace collapsed."""
    flat = " ".join(str(tldr).split())
    found = _SENTENCE.match(flat)
    return found.group(1) if found else flat


def page_groups(page: str, entries: list[Entry]) -> list[tuple[str, str, list[Entry]]]:
    """The pages other than `page`, grouped `(key, heading, entries)` in section order.

    The one place the page list is sorted, grouped and filtered: `fill_pages` writes
    it as Markdown, the landing renderer as HTML, so the two cannot drift.
    """
    groups = []
    for key, heading in SECTIONS:
        rows = [
            e
            for e in sorted(entries, key=lambda e: e.path)
            if e.path != page and _section(e.path) == key
        ]
        if rows:
            groups.append((key, heading, rows))
    return groups


def fill_pages(text: str, page: str, entries: list[Entry]) -> str:
    """Replace the `<!-- site:pages -->` marker with the grouped list of pages."""
    if MARKER not in text:
        return text
    blocks = [
        f"### {heading}\n\n"
        + "\n".join(
            f"- [{e.title}]({posixpath.relpath(e.path, posixpath.dirname(page))}): "
            f"{first_sentence(e.tldr)}"
            for e in rows
        )
        for _key, heading, rows in page_groups(page, entries)
    ]
    return text.replace(MARKER, "\n\n".join(blocks))


def parse_front_matter(text: str) -> dict:
    """The page's front matter as a dict (empty when it has none)."""
    found = _FRONT.match(text)
    data = yaml.safe_load(found.group(1) or "") if found else None
    return data if isinstance(data, dict) else {}


def drop_leading_h1(text: str) -> str:
    """Remove the body's first line when it is an H1: the renderer prints the title itself."""
    found = _FRONT.match(text)
    if not found:
        return text
    head, body = text[: found.end()], text[found.end() :]
    m = re.match(r"\s*# [^\n]*\n", body)
    if m is None:
        return text
    return head + "\n" + body[m.end() :].lstrip("\n")


# -- the landing source (spec 2026-11-12-landing-front-page R1, R3, R4, R9) -----------

SECTION_KINDS = ("prose", "flow", "guarantee", "act", "grid", "pages", "cta")
TERMINAL_KINDS = ("prompt", "out", "you", "ok")
CARDS = (3, 8)
_NO_FIGURE = ("act", "grid", "pages", "cta")
GUARANTEES = (6, 8)
_KIND = re.compile(r"^<!--\s*landing:([A-Za-z0-9_-]*)\s*-->\s*$")
_ONE_LINK = re.compile(r"^\[([^\]]+)\]\(([^)\s]+)\)$")
_ORDERED = re.compile(r"^\d+[.)]\s+")
_FENCE = re.compile(r"^\s*(```|~~~)")
_FIGURE_MARKER = re.compile(r"^<!--\s*site:figure\s+(\S+)\s*-->\s*$")
_FIGURE_NAME = re.compile(r"^[a-z0-9-]+$")
_BULLET = re.compile(r"^\s{0,3}[-*+]\s+")
_CARD = re.compile(r"^\*\*(.+?)\*\*\s*(.*)$", re.DOTALL)
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


@dataclass(frozen=True)
class Link:
    label: str
    href: str


@dataclass(frozen=True)
class Fact:
    figure: str
    caption: str


@dataclass(frozen=True)
class TerminalLine:
    """One line of the hero's terminal: a typed command, output, an operator point or a success."""

    kind: str
    text: str


@dataclass(frozen=True)
class Card:
    """One card of the "also included" grid: a title, one sentence and exactly one link."""

    title: str
    text: str
    link: Link


@dataclass(frozen=True)
class Hero:
    eyebrow: str
    headline: str
    subline: str
    command: str
    primary: Link
    secondary: tuple[Link, ...]
    terminal: tuple[TerminalLine, ...] = ()


@dataclass(frozen=True)
class Step:
    """One item of the run strip; `yours` when the operator does it (`{you}`)."""

    text: str
    yours: bool


@dataclass(frozen=True)
class Section:
    """A `## ` section: its kind, headline and Markdown body.

    `problem`, `link` (guarantee), `steps` (flow) and `cards` (grid) are set only for their
    kind; for a guarantee `body` is the gain and how, without the problem and the link. `act`
    is an act's number, or for a guarantee the act it belongs to (0: none). `figure` is the
    name of the figure placed in the section, lifted out of its body.
    """

    kind: str
    heading: str
    body: str
    problem: str = ""
    link: Link | None = None
    steps: tuple[Step, ...] = ()
    cards: tuple[Card, ...] = ()
    act: int = 0
    figure: str = ""


@dataclass(frozen=True)
class Landing:
    hero: Hero
    facts: tuple[Fact, ...]
    sections: tuple[Section, ...]


def is_landing(front_matter: dict) -> bool:
    """Whether a page's front matter asks for the landing layout."""
    return front_matter.get("layout") == "landing"


def split_blocks(text: str) -> list[str]:
    """`text` as top-level blocks: blank-line separated, a fenced block kept whole."""
    blocks: list[list[str]] = []
    cur: list[str] = []
    fenced = False
    for raw in text.splitlines():
        if _FENCE.match(raw):
            fenced = not fenced
        if not fenced and not raw.strip() and not _FENCE.match(raw):
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append(raw)
    if cur:
        blocks.append(cur)
    return ["\n".join(b) for b in blocks]


def _split_sections(body: str, page: str) -> list[tuple[str, str]]:
    heads: list[tuple[str, list[str]]] = []
    fenced = False
    for raw in body.splitlines():
        if _FENCE.match(raw):
            fenced = not fenced
        if not fenced and raw.startswith("## "):
            heads.append((raw[3:].strip(), []))
        elif heads:
            heads[-1][1].append(raw)
        elif raw.strip() and not raw.startswith("# "):
            raise BuildError(f"{page}: text before the first '## ' heading of a landing page")
    return [(h, "\n".join(lines)) for h, lines in heads]


def _link(value: object, where: str, page: str) -> Link:
    if not isinstance(value, dict) or not value.get("label") or not value.get("href"):
        raise BuildError(f"{page}: {where} needs a label and an href")
    return Link(str(value["label"]), str(value["href"]))


def _parse_hero(fm: dict, page: str) -> Hero:
    hero = fm.get("hero")
    if not isinstance(hero, dict):
        raise BuildError(f"{page}: landing front matter lacks hero")
    for key in ("headline", "subline"):
        if not str(hero.get(key) or "").strip():
            raise BuildError(f"{page}: landing front matter lacks hero.{key}")
    primary = hero.get("primary")
    if not isinstance(primary, dict) or not str(primary.get("label") or "").strip():
        raise BuildError(f"{page}: landing front matter lacks hero.primary.label")
    if not str(primary.get("href") or "").strip():
        raise BuildError(f"{page}: landing front matter lacks hero.primary.href")
    secondary = hero.get("secondary") or []
    if not isinstance(secondary, list):
        raise BuildError(f"{page}: hero.secondary must be a list")
    return Hero(
        eyebrow=str(hero.get("eyebrow") or ""),
        headline=str(hero["headline"]).strip(),
        subline=str(hero["subline"]).strip(),
        command=str(hero.get("command") or ""),
        primary=Link(str(primary["label"]), str(primary["href"])),
        secondary=tuple(_link(item, "hero.secondary[]", page) for item in secondary),
        terminal=_parse_terminal(hero.get("terminal"), page),
    )


def _parse_terminal(value: object, page: str) -> tuple[TerminalLine, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise BuildError(f"{page}: hero.terminal must be a list of {{kind, text}}")
    out = []
    for item in value:
        kind = item.get("kind") if isinstance(item, dict) else None
        text = item.get("text") if isinstance(item, dict) else None
        if kind not in TERMINAL_KINDS:
            raise BuildError(
                f"{page}: hero.terminal has a line of kind {kind!r} "
                f"(known: {', '.join(TERMINAL_KINDS)})"
            )
        if not isinstance(text, str) or not text.strip():
            raise BuildError(f"{page}: a hero.terminal {kind} line has no text")
        out.append(TerminalLine(kind, text.strip()))
    return tuple(out)


def _parse_facts(fm: dict, page: str) -> tuple[Fact, ...]:
    facts = fm.get("facts") or []
    if not isinstance(facts, list):
        raise BuildError(f"{page}: facts must be a list")
    out = []
    for item in facts:
        if not isinstance(item, dict) or "figure" not in item or "caption" not in item:
            raise BuildError(f"{page}: each fact needs a figure and a caption")
        out.append(Fact(str(item["figure"]), str(item["caption"])))
    return tuple(out)


def _parse_flow(heading: str, body: str, page: str) -> tuple[Step, ...]:
    blocks = split_blocks(body)
    if not blocks or not all(_ORDERED.match(b) for b in blocks):
        raise BuildError(f"{page}: the flow section {heading!r} must be exactly one ordered list")
    items: list[list[str]] = []
    for line in "\n".join(blocks).splitlines():
        if _ORDERED.match(line):
            items.append([_ORDERED.sub("", line, count=1)])
        else:
            items[-1].append(line.strip())
    steps = []
    for lines in items:
        text = " ".join(x for x in lines if x)
        yours = text.startswith("{you}")
        steps.append(Step(text.removeprefix("{you}").strip() if yours else text, yours))
    return tuple(steps)


def _parse_guarantee(heading: str, body: str, page: str) -> Section:
    blocks = split_blocks(body)
    quote = next((i for i, b in enumerate(blocks) if b.lstrip().startswith(">")), None)
    if quote is None:
        raise BuildError(f"{page}: the section {heading!r} has no problem (a blockquote)")
    last = " ".join(blocks[-1].split()) if blocks else ""
    found = _ONE_LINK.match(last)
    if found is None or len(blocks) - 1 == quote:
        raise BuildError(
            f"{page}: the section {heading!r} must end with a paragraph holding exactly one link"
        )
    problem = "\n".join(re.sub(r"^\s*>\s?", "", ln) for ln in blocks[quote].splitlines())
    rest = [b for i, b in enumerate(blocks[:-1]) if i != quote]
    return Section(
        "guarantee",
        heading,
        "\n\n".join(rest),
        problem=problem.strip(),
        link=Link(found.group(1), found.group(2)),
    )


def _lift_figure(heading: str, kind: str, raw: str, page: str) -> tuple[str, str]:
    """`raw` without its figure-marker blocks, and the one figure name they held ("" if none)."""
    keep: list[str] = []
    names: list[str] = []
    for block in split_blocks(raw):
        found = _FIGURE_MARKER.match(block.strip())
        if found is None:
            keep.append(block)
        else:
            names.append(found.group(1))
    if not names:
        return raw, ""
    if kind in _NO_FIGURE:
        raise BuildError(f"{page}: the {kind} section {heading!r} cannot hold a figure")
    if len(names) > 1:
        raise BuildError(f"{page}: the section {heading!r} holds more than one figure marker")
    if not _FIGURE_NAME.match(names[0]):
        raise BuildError(f"{page}: figure name {names[0]!r} is not [a-z0-9-]+")
    return "\n\n".join(keep), names[0]


def _parse_card(item: str, heading: str, page: str) -> Card:
    found = _CARD.match(item)
    if found is None:
        raise BuildError(
            f"{page}: a card of the grid {heading!r} must read '**Title.** sentence [label](href)'"
        )
    title, rest = found.group(1).strip().rstrip("."), found.group(2)
    links = _MD_LINK.findall(rest)
    if len(links) != 1:
        raise BuildError(
            f"{page}: the card {title!r} of the grid {heading!r} needs exactly one link, "
            f"found {len(links)}"
        )
    text = " ".join(_MD_LINK.sub("", rest).split())
    return Card(title, text, Link(links[0][0], links[0][1]))


def _parse_grid(heading: str, body: str, page: str) -> Section:
    blocks = split_blocks(body)
    if not blocks or not _BULLET.match(blocks[-1]) or any(_BULLET.match(b) for b in blocks[:-1]):
        raise BuildError(f"{page}: the grid {heading!r} must be optional prose, then one list")
    items: list[list[str]] = []
    for line in blocks[-1].splitlines():
        if _BULLET.match(line):
            items.append([_BULLET.sub("", line, count=1)])
        else:
            items[-1].append(line.strip())
    cards = tuple(_parse_card(" ".join(x for x in lines if x), heading, page) for lines in items)
    if not CARDS[0] <= len(cards) <= CARDS[1]:
        raise BuildError(
            f"{page}: the grid {heading!r} has three to eight cards, found {len(cards)}"
        )
    return Section("grid", heading, "\n\n".join(blocks[:-1]), cards=cards)


def _check_acts(sections: list[Section], page: str) -> None:
    for i, sec in enumerate(sections):
        if sec.kind != "act":
            continue
        after = sections[i + 1 :]
        until = next((j for j, x in enumerate(after) if x.kind == "act"), len(after))
        if not any(x.kind == "guarantee" for x in after[:until]):
            raise BuildError(f"{page}: the act {sec.heading!r} has no numbered section")


def parse_landing(text: str, page: str) -> Landing:
    """The landing page source as data; every R9 defect raises a `BuildError`.

    Pure: no filesystem. Spec 2026-11-12-landing-front-page R4 (a numbered section
    has its problem, its gain and one link; six to eight of them) and R9.
    """
    fm = parse_front_matter(text)
    found = _FRONT.match(text)
    body = text[found.end() :] if found else text
    sections: list[Section] = []
    acts = 0
    for heading, raw in _split_sections(body, page):
        lines = raw.splitlines()
        first = next((i for i, ln in enumerate(lines) if ln.strip()), None)
        kind = "prose"
        if first is not None and (m := _KIND.match(lines[first])):
            kind = m.group(1)
            raw = "\n".join(lines[:first] + lines[first + 1 :])
        if kind not in SECTION_KINDS:
            raise BuildError(
                f"{page}: the section {heading!r} names an unknown kind {kind!r} "
                f"(known: {', '.join(SECTION_KINDS)})"
            )
        raw, figure = _lift_figure(heading, kind, raw, page)
        if kind == "flow":
            sec = Section(kind, heading, raw, steps=_parse_flow(heading, raw, page))
        elif kind == "guarantee":
            sec = _parse_guarantee(heading, raw, page)
        elif kind == "grid":
            sec = _parse_grid(heading, raw, page)
        elif kind == "pages" and MARKER not in raw:
            raise BuildError(f"{page}: the pages section {heading!r} lacks {MARKER}")
        else:
            sec = Section(kind, heading, raw)
        if kind == "act":
            acts += 1
            sec = replace(sec, act=acts)
        elif kind == "guarantee":
            sec = replace(sec, act=acts)
        sections.append(replace(sec, figure=figure) if figure else sec)
    _check_acts(sections, page)
    hero = _parse_hero(fm, page)
    count = sum(s.kind == "guarantee" for s in sections)
    if not GUARANTEES[0] <= count <= GUARANTEES[1]:
        raise BuildError(
            f"{page}: a landing page has six to eight numbered sections, found {count}"
        )
    return Landing(hero, _parse_facts(fm, page), tuple(sections))


# -- rendering the landing (spec 2026-11-12-front-page-second-pass A, C) -----------------

SITE_DIR = Path(__file__).resolve().parent / "site"
_LINKS_ONLY = re.compile(r"^(?:\[[^\]]+\]\([^)\s]+\)\s*)+$")
_ANY_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_ORDINALS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
#: Seconds a typed prompt line takes, and an output line's gap, in the terminal's timeline.
_TYPE_SECONDS, _LINE_SECONDS = 1.6, 0.7


def site_file(name: str) -> str:
    """A file of `scripts/site/` (the landing skeleton and the stylesheets)."""
    return (SITE_DIR / name).read_text(encoding="utf-8")


def _fill(template: str, values: dict[str, str]) -> str:
    """Substitute `{{name}}` placeholders in one pass (inserted text is never rescanned)."""
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values[m.group(1)], template)


def _inline(to_html: Callable[[str], str], text: str) -> str:
    out = to_html(text).strip()
    m = re.fullmatch(r"<p>(.*)</p>", out, re.DOTALL)
    return m.group(1) if m else out


def _headline_html(headline: str) -> str:
    """The headline escaped; the text after its first sentence is wrapped in the accent gradient."""
    first = _SENTENCE.match(headline)
    if first is None or first.group(1) == headline:
        return html.escape(headline)
    rest = headline[first.end() :].strip()
    return f'{html.escape(first.group(1))} <span class="accent">{html.escape(rest)}</span>'


def _terminal_html(lines: tuple[TerminalLine, ...]) -> str:
    """The hero's terminal panel: window chrome, then one line element per entry.

    A `prompt` line carries its character count (`--chars`, the width its typing animation
    steps over); every line carries its start time (`--d`) in the transcript's timeline.
    """
    last_prompt = max((i for i, t in enumerate(lines) if t.kind == "prompt"), default=-1)
    rows: list[str] = []
    at = 0.4
    for i, line in enumerate(lines):
        text = html.escape(line.text)
        if line.kind == "prompt":
            caret = " caret" if i == last_prompt else ""
            rows.append(
                f'<p class="tl tl-prompt{caret}" style="--chars:{len(line.text)};--d:{at:.1f}s">'
                f'<span class="typed">{text}</span></p>'
            )
            at += _TYPE_SECONDS
        else:
            rows.append(
                f'<p class="tl tl-{line.kind}" style="--d:{at:.1f}s"><span>{text}</span></p>'
            )
            at += _LINE_SECONDS
    return (
        '<div class="terminal" role="group" aria-label="An example run, as a terminal transcript">'
        '<div class="term-bar" aria-hidden="true"><i></i><i></i><i></i><span>fr run</span></div>'
        f'<div class="term-body">{"".join(rows)}</div></div>'
    )


class _LandingRenderer:
    """Renders each section kind of one landing; every link goes through the build's one rule."""

    def __init__(
        self,
        *,
        entries: list[Entry],
        patterns: list[str],
        tracked: list[str],
        ref: str,
        repo_url: str,
        to_html: Callable[[str], str],
        page: str,
        total: int,
    ) -> None:
        self.entries, self.patterns, self.tracked = entries, patterns, tracked
        self.ref, self.repo_url, self.to_html = ref, repo_url, to_html
        self.page, self.total = page, total
        self.number = 0
        self.inserted: list[str] = []

    def href(self, h: str) -> str:
        return html.escape(
            rewrite_href(h, self.page, self.patterns, self.tracked, self.ref, self.repo_url),
            quote=True,
        )

    def rewrite(self, text: str) -> str:
        return rewrite_markdown(
            text, self.page, self.patterns, self.tracked, self.ref, self.repo_url
        )

    def md(self, text: str) -> str:
        return self.to_html(self.rewrite(text))

    def figure(self, sec: Section) -> str:
        if not sec.figure:
            return ""
        try:
            block = load_figure(sec.figure)
        except BuildError as e:
            raise BuildError(f"{self.page}: {e}") from e
        self.inserted += re.findall(r"<svg\b.*?</svg>", block, re.DOTALL)
        return block

    def hero(self, hero: Hero, facts: tuple[Fact, ...]) -> str:
        esc = html.escape
        copy = []
        if hero.eyebrow:
            copy.append(f'<p class="eyebrow">{esc(hero.eyebrow)}</p>')
        copy.append(f"<h1>{_headline_html(hero.headline)}</h1>")
        copy.append(f'<p class="subline">{esc(hero.subline)}</p>')
        if hero.command and not hero.terminal:
            copy.append(f'<code class="command">{esc(hero.command)}</code>')
        actions = [
            f'<a class="btn" href="{self.href(hero.primary.href)}">{esc(hero.primary.label)}</a>'
        ]
        actions += [
            f'<a class="link" href="{self.href(x.href)}">{esc(x.label)}</a>' for x in hero.secondary
        ]
        copy.append('<p class="actions">' + "".join(actions) + "</p>")
        parts = [f'<div class="hero-copy">{"".join(copy)}</div>']
        if hero.terminal:
            parts.append(
                f'<div class="hero-term"><div class="glow" aria-hidden="true"></div>'
                f"{_terminal_html(hero.terminal)}</div>"
            )
        if facts:
            items = "".join(
                f"<li><strong>{esc(f.figure)}</strong><span>{esc(f.caption)}</span></li>"
                for f in facts
            )
            parts.append(f'<ul class="facts">{items}</ul>')
        solo = "" if hero.terminal else " solo"
        return f'<div class="wrap hero-grid{solo}">{"".join(parts)}</div>'

    def flow(self, sec: Section) -> str:
        items = "".join(
            f'<li class="step{" yours" if st.yours else ""}">'
            + ('<span class="you-tag">You</span>' if st.yours else "")
            + _inline(self.to_html, self.rewrite(st.text))
            + "</li>"
            for st in sec.steps
        )
        legend = (
            '<p class="legend">The steps marked You are yours; the rest the agent does.</p>'
            if any(st.yours for st in sec.steps)
            else ""
        )
        return (
            f'<section class="band flow"><div class="wrap"><h2>{html.escape(sec.heading)}</h2>'
            f'{self.figure(sec)}<ol class="steps">{items}</ol>{legend}</div></section>'
        )

    def act(self, sec: Section) -> str:
        word = _ORDINALS[sec.act - 1] if 0 < sec.act <= len(_ORDINALS) else str(sec.act)
        return (
            f'<section class="act" id="act-{sec.act}"><div class="wrap">'
            f'<p class="act-label">Act {word}</p><h2>{html.escape(sec.heading)}</h2>'
            f'<div class="act-intro">{self.md(sec.body)}</div></div></section>'
        )

    def guarantee(self, sec: Section) -> str:
        assert sec.link is not None
        self.number += 1
        return (
            f'<section class="band guarantee" id="section-{self.number}"><div class="wrap">'
            f'<article class="card"><div class="g-head">'
            f'<p class="kicker"><span class="num">{self.number:02d}</span>'
            f'<span class="of"> / {self.total:02d}</span></p>'
            f"<h2>{html.escape(sec.heading)}</h2>"
            f'<div class="problem">{self.md(sec.problem)}</div></div>'
            f'<div class="g-body">{self.md(sec.body)}</div>{self.figure(sec)}'
            f'<a class="more" href="{self.href(sec.link.href)}">{html.escape(sec.link.label)}</a>'
            "</article></div></section>"
        )

    def grid(self, sec: Section) -> str:
        esc = html.escape
        cards = "".join(
            f'<li class="card"><h3>{esc(c.title)}</h3><p>{_inline(self.to_html, c.text)}</p>'
            f'<a class="more" href="{self.href(c.link.href)}">{esc(c.link.label)}</a></li>'
            for c in sec.cards
        )
        intro = self.md(sec.body) if sec.body.strip() else ""
        return (
            f'<section class="band grid"><div class="wrap"><h2>{esc(sec.heading)}</h2>{intro}'
            f'<ul class="cards">{cards}</ul></div></section>'
        )

    def pages(self, sec: Section) -> str:
        esc = html.escape
        lists = []
        here = posixpath.dirname(route(self.page)) or "."
        for key, heading, rows in page_groups(self.page, self.entries):
            lis = "".join(
                f'<li><a href="{esc(posixpath.relpath(route(e.path), here))}">'
                f"{esc(e.title)}</a><span>{esc(first_sentence(e.tldr))}</span></li>"
                for e in rows
            )
            lists.append(f'<h3 id="{key}">{esc(heading)}</h3><ul>{lis}</ul>')
        before, _, after = sec.body.partition(MARKER)
        return (
            f'<section class="band pages"><div class="wrap"><h2>{esc(sec.heading)}</h2>'
            f"{self.md(before) if before.strip() else ''}{''.join(lists)}"
            f"{self.md(after) if after.strip() else ''}</div></section>"
        )

    def cta(self, sec: Section) -> str:
        esc = html.escape
        blocks = []
        for block in split_blocks(self.rewrite(sec.body)):
            flat = " ".join(block.split())
            if _LINKS_ONLY.match(flat):
                btns = "".join(
                    f'<a class="btn" href="{esc(h, quote=True)}">{esc(lab)}</a>'
                    if i == 0
                    else f'<a href="{esc(h, quote=True)}">{esc(lab)}</a>'
                    for i, (lab, h) in enumerate(_ANY_LINK.findall(flat))
                )
                blocks.append(f'<p class="buttons">{btns}</p>')
            else:
                blocks.append(self.to_html(block))
        return (
            f'<section class="band cta"><div class="wrap narrow"><h2>{esc(sec.heading)}</h2>'
            f"{''.join(blocks)}</div></section>"
        )

    def prose(self, sec: Section) -> str:
        return (
            f'<section class="band prose"><div class="wrap narrow">'
            f"<h2>{html.escape(sec.heading)}</h2>{self.md(sec.body)}{self.figure(sec)}"
            "</div></section>"
        )


def render_landing(
    landing: Landing,
    *,
    title: str,
    entries: list[Entry],
    patterns: list[str],
    tracked: list[str],
    ref: str,
    repo_url: str = DEFAULT_REPO_URL,
    to_html: Callable[[str], str],
    description: str = "",
    page: str = INDEX_SOURCE,
) -> str:
    """The landing page's HTML. Pure given its inputs (no filesystem but `scripts/site/`).

    Every relative link, in the front matter and in the bodies, goes through the
    build's one link rule with `page` as the linking page. `to_html` is the Markdown
    converter; the build passes python-markdown's, tests a stand-in. The page embeds no
    font and takes nothing from a renderer-produced page; a figure it inlines must
    survive into the output, as on an article page.
    """
    r = _LandingRenderer(
        entries=entries,
        patterns=patterns,
        tracked=tracked,
        ref=ref,
        repo_url=repo_url,
        to_html=to_html,
        page=page,
        total=sum(sec.kind == "guarantee" for sec in landing.sections),
    )
    hero_html = r.hero(landing.hero, landing.facts)
    out = [getattr(r, sec.kind)(sec) for sec in landing.sections]
    css = site_file("landing.css")
    if r.inserted:
        css = site_file("figures.css") + "\n" + css
    page_html = _fill(
        site_file("landing.html"),
        {
            "title": html.escape(title),
            "description": html.escape(" ".join(description.split()), quote=True),
            "css": css,
            "hero": hero_html,
            "sections": "\n".join(out),
        },
    )
    check_figures_survived(page_html, r.inserted, route(page))
    return page_html


def check_rendered(html: str, route_name: str) -> None:
    """Fail a page the renderer emitted without its embedded fonts."""
    if not re.search(r"@font-face\s*\{[^}]*url\(\s*data:", html):
        raise BuildError(f"{route_name}: rendered with no embedded @font-face data URI")


# -- figures (spec 2026-11-12-front-page-second-pass B, R6, R10) -------------------------

FIGURES_DIR = SITE_DIR / "figures"
_SVG_OPEN = re.compile(r"<svg\b[^>]*>")
_PAINT_PROPS = frozenset({"fill", "stroke", "stop-color", "flood-color", "color"})
_CSS_DECL = re.compile(r"(?<![\w-])([\w-]+)\s*:\s*([^;}]*)")
_URL_REF = re.compile(r"url\(\s*[\"']?([^)\"']*)[\"']?\s*\)", re.IGNORECASE)
_SAME_DOC = re.compile(r"#[^\s#]+")
_ALLOWED_PAINT = {"none", "currentcolor", "inherit", "transparent"}
_REFUSED_ELEMENTS = {
    "script": "contains a <script> element",
    "image": "contains an <image> element, which would be a reference outside the page",
    "foreignobject": "contains a <foreignObject> element",
}
_SMIL = {"animate", "set", "animatetransform", "animatemotion"}
_XLINK = 'xmlns:xlink="http://www.w3.org/1999/xlink"'


def _local(name: str) -> str:
    """The local part of an ElementTree tag or attribute name, lower-cased."""
    return name.rsplit("}", 1)[-1].lower()


def _allowed_paint(value: str) -> bool:
    v = re.sub(r"!\s*important\s*$", "", value.strip(), flags=re.IGNORECASE).strip()
    low = v.lower()
    return (
        low in _ALLOWED_PAINT
        or low.startswith("var(")
        or re.fullmatch(r"url\(\s*#[^)\s]+\s*\)", v, re.IGNORECASE) is not None
    )


def check_figure(svg_text: str, name: str) -> None:
    """Refuse a figure file that breaks a rule of spec 2026-11-12-front-page-second-pass B / R10.

    `name` is the file's stem: `<name>` or `<name>.narrow`. The file is parsed as XML and
    its elements and attributes are checked, never raw text, so a value cannot hide a
    construct. Every refusal names the figure and the defect, so a bad file never reaches
    a page. Motion is CSS in figures.css, so SMIL elements are refused outright.
    """
    import xml.etree.ElementTree as ET  # noqa: N817 - stdlib alias, local to the one user

    def refuse(defect: str) -> BuildError:
        return BuildError(f"figure {name}: {defect}")

    text = svg_text if "xmlns:xlink" in svg_text else svg_text.replace("<svg", f"<svg {_XLINK}", 1)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise refuse(f"is not well-formed XML ({e})") from e
    if _local(root.tag) != "svg":
        raise refuse("the root element is not <svg>")
    if root.get("role") != "img":
        raise refuse('the root <svg> has no role="img"')
    children = list(root)
    first = children[0] if children else None
    if first is None or _local(first.tag) != "title" or not (first.text or "").strip():
        raise refuse("the first child of the root <svg> is not a non-empty <title>")
    prefix = f"{name.partition('.')[0]}-{name.partition('.')[2]}--" if "." in name else f"{name}--"

    def paint(prop: str, value: str) -> None:
        if not _allowed_paint(value):
            raise refuse(
                f"{prop.lower()} is {value.strip()!r}, not a class-driven paint; use a class "
                "from figures.css (allowed values: none, currentColor, inherit, transparent, "
                "url(#id), var(...))"
            )

    def css(source: str) -> None:
        for prop, value in _CSS_DECL.findall(source):
            if prop.lower() in _PAINT_PROPS:
                paint(prop, value)

    def urls(source: str) -> None:
        for ref in _URL_REF.findall(source):
            if not _SAME_DOC.fullmatch(ref):
                raise refuse(f"url({ref}) is not a same-document #id")

    for el in root.iter():
        tag = _local(el.tag)
        if tag in _REFUSED_ELEMENTS:
            raise refuse(_REFUSED_ELEMENTS[tag])
        if tag in _SMIL:
            raise refuse(f"contains the SMIL animation element <{tag}>; motion is CSS")
        if tag == "style":
            body = el.text or ""
            if re.search(r"@import", body, re.IGNORECASE):
                raise refuse("a <style> element uses @import")
            urls(body)
            css(body)
        for key, value in el.attrib.items():
            attr = _local(key)
            if attr.startswith("on"):
                raise refuse(f"carries the event attribute {attr}")
            if attr == "href" and not _SAME_DOC.fullmatch(value):
                raise refuse(f"href {value!r} is not a same-document #id")
            if attr == "id" and not value.startswith(prefix):
                raise refuse(f"id {value!r} does not start with {prefix!r}")
            urls(value)
            if attr == "style":
                css(value)
            elif attr in _PAINT_PROPS:
                paint(attr, value)


def _compact(svg_text: str) -> str:
    """The SVG with no blank lines and no indentation, so Markdown keeps it one block."""
    return "\n".join(line.strip() for line in svg_text.splitlines() if line.strip())


def _with_class(svg: str, cls: str, name: str) -> str:
    root = _SVG_OPEN.search(svg)
    assert root is not None  # check_figure ran first
    if re.search(r"(?<![\w-])class\s*=", root.group(0)):
        raise BuildError(f"figure {name}: the root <svg> carries a class; the build adds one")
    return svg.replace("<svg", f'<svg class="{cls}"', 1)


def figure_svgs(name: str) -> list[str]:
    """The checked, inlined `<svg>` texts of figure `name`: the wide one, then any narrow one.

    The `fig-wide` / `fig-narrow` classes (which figures.css shows by width) are added only
    when a narrow file exists, so a lone figure carries neither and is always shown.
    """
    wide = FIGURES_DIR / f"{name}.svg"
    if not wide.is_file():
        raise BuildError(f"figure {name}: {wide} does not exist")
    narrow = FIGURES_DIR / f"{name}.narrow.svg"
    files = [(name, wide)] + ([(f"{name}.narrow", narrow)] if narrow.is_file() else [])
    out: list[str] = []
    for stem, path in files:
        text = path.read_text(encoding="utf-8")
        check_figure(text, stem)
        svg = _compact(text.strip())
        if len(files) == 2:
            svg = _with_class(svg, "fig-narrow" if stem.endswith(".narrow") else "fig-wide", stem)
        out.append(svg)
    return out


def load_figure(name: str) -> str:
    """`<figure class="site-figure">` holding figure `name`'s wide and narrow `<svg>`."""
    return '<figure class="site-figure">' + "\n".join(figure_svgs(name)) + "</figure>"


def fill_figures(text: str, page: str) -> tuple[str, list[str]]:
    """Replace each `<!-- site:figure NAME -->` line outside fenced code with its figure.

    Returns the new text and the exact `<svg>` strings inserted, which the survival check
    looks for in the rendered page. The figure is `load_figure`'s markup, padded by a blank
    line each side so python-markdown treats it as a block of its own.
    """
    lines: list[str] = []
    inserted: list[str] = []
    fence = ""
    for line in text.split("\n"):
        f = _FENCE.match(line)
        if f:
            fence = "" if fence == f.group(1) else (fence or f.group(1))
        found = None if fence or f else _FIGURE_MARKER.match(line)
        if found is None:
            lines.append(line)
            continue
        name = found.group(1)
        if not _FIGURE_NAME.match(name):
            raise BuildError(f"{page}: figure name {name!r} is not [a-z0-9-]+")
        try:
            html_block = load_figure(name)
        except BuildError as e:
            raise BuildError(f"{page}: {e}") from e
        inserted += re.findall(r"<svg\b.*?</svg>", html_block, re.DOTALL)
        lines += ["", html_block, ""]
    return "\n".join(lines), inserted


def check_figures_survived(rendered_html: str, inserted: list[str], route_name: str) -> None:
    """Fail a page whose rendering altered or dropped a figure the build inserted."""
    for svg in inserted:
        if svg not in rendered_html:
            title = re.search(r"<title>([^<]*)</title>", svg)
            what = title.group(1) if title else svg[:40]
            raise BuildError(f"{route_name}: the figure {what!r} did not survive rendering intact")


# -- the top bar (R8, R9) --------------------------------------------------------------

_BODY_OPEN = re.compile(r"<body\b[^>]*>")


def insert_bar(page_html: str, route_name: str, repo_url: str, bar_css: str) -> str:
    """`page_html` with the site's top bar: its style before `</head>`, its nav after `<body>`.

    Both anchors must occur exactly once, so a renderer change cannot silently drop
    the bar (R9). Links are relative to `route_name`.
    """
    bodies = _BODY_OPEN.findall(page_html)
    if len(bodies) != 1:
        raise BuildError(
            f"{route_name}: expected one <body> to insert the top bar, found {len(bodies)}"
        )
    if page_html.count("</head>") != 1:
        raise BuildError(
            f"{route_name}: expected one </head> to insert the top bar, "
            f"found {page_html.count('</head>')}"
        )
    home = "../" * route_name.count("/") + "index.html"
    links = "".join(
        f'<a href="{html.escape(h, quote=True)}">{label}</a>'
        for label, h in (
            ("Explainers", f"{home}#explainers"),
            ("Guides", f"{home}#guides"),
            ("Reference", f"{home}#reference"),
            ("GitHub", repo_url),
        )
    )
    nav = (
        f'<nav class="site-bar" aria-label="Site"><a class="site-name" href="{home}">super-fr</a>'
        f"{links}</nav>"
    )
    with_style = page_html.replace("</head>", f"<style>{bar_css}</style></head>", 1)
    return _BODY_OPEN.sub(lambda m: m.group(0) + "\n" + nav, with_style, count=1)


def insert_figure_css(page_html: str, route_name: str, figure_css: str) -> str:
    """`page_html` with the figure stylesheet before `</head>` (only pages with a figure get it)."""
    if page_html.count("</head>") != 1:
        raise BuildError(f"{route_name}: expected one </head> to insert the figure styles")
    return page_html.replace("</head>", f"<style>{figure_css}</style></head>", 1)


def load_config(path: Path) -> list[str]:
    """The `pages` globs of `.fr/docs.yaml`."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        raise BuildError(f"{path} is unusable: {e}") from e
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list) or not pages:
        raise BuildError(f"{path} names no pages")
    return [str(p) for p in pages]


# -- git and the renderer -------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if done.returncode != 0:
        raise BuildError(f"`git {' '.join(args)}` failed: {done.stderr.strip()}")
    return done.stdout


def tracked_files(root: Path) -> list[str]:
    """Every tracked path, repo-relative."""
    return sorted(p for p in _git(root, "ls-files", "-z").split("\0") if p)


def render_page(renderer: Path, fonts: Path, source: Path, out: Path) -> str:
    """Run the renderer on `source`; return the HTML it wrote to `out`."""
    done = subprocess.run(
        [
            sys.executable,
            str(renderer),
            str(source),
            "--style",
            "broadsheet",
            "--embed-fonts",
            "--fonts-dir",
            str(fonts),
            "-o",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise BuildError(f"renderer failed on {source.name}: {done.stderr.strip()}")
    return out.read_text(encoding="utf-8")


def _markdown_converter() -> Callable[[str], str]:
    """python-markdown with the renderer's extensions, imported only when a landing needs it."""
    try:
        import markdown
    except ImportError as e:
        raise BuildError("the landing page needs `markdown` (run with --with markdown)") from e
    return lambda text: markdown.markdown(
        text, extensions=["fenced_code", "codehilite", "tables", "sane_lists"]
    )


def _render_article(
    path: str,
    raw: str,
    entries: list[Entry],
    patterns: list[str],
    tracked: list[str],
    ref: str,
    repo_url: str,
    renderer_env: tuple[Path, Path, str],
) -> tuple[str, list[str]]:
    """Render one article page: rewrite its links and markers, then run the renderer.

    Figures are filled after the link rewrite, so `rewrite_markdown` never scans an SVG.
    Returns the page's HTML and the `<svg>` strings the build inserted into it.
    """
    renderer, fonts, tmp = renderer_env
    text = fill_pages(drop_leading_h1(raw), path, entries)
    text = rewrite_markdown(text, path, patterns, tracked, ref, repo_url)
    text, inserted = fill_figures(text, path)
    source = Path(tmp) / posixpath.basename(path)
    source.write_text(text, encoding="utf-8")
    target = Path(tmp) / "out" / route(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return render_page(renderer, fonts, source, target), inserted


def build(root: Path, out_dir: Path, blog_craft: Path, ref: str, repo_url: str) -> list[str]:
    """Render every configured page into `out_dir`; return the routes written.

    Three passes: select and parse (every source-level refusal), render into a
    temporary directory and check and decorate in memory, and only then write. No
    page reaches `out_dir` while a refusal for any page can still fire.
    """
    renderer = blog_craft / "tools" / "render_explainer.py"
    if not renderer.is_file():
        raise BuildError(f"{renderer} not found: pass --blog-craft DIR (or set BLOG_CRAFT_DIR)")
    fonts = blog_craft / FONTS_SUBDIR
    if not fonts.is_dir():
        raise BuildError(f"{fonts} not found: the renderer would fall back to system fonts")
    # 1. select and parse
    patterns = load_config(root / ".fr" / "docs.yaml")
    tracked = tracked_files(root)
    pages = select_pages(patterns, tracked)
    if not pages:
        raise BuildError("the config selects no tracked page")
    texts = {p: (root / p).read_text(encoding="utf-8") for p in pages}
    fronts = {p: parse_front_matter(texts[p]) for p in pages}
    entries = [
        Entry(p, str(fronts[p].get("title") or p), str(fronts[p].get("tldr") or "")) for p in pages
    ]
    landing_pages = [p for p in pages if is_landing(fronts[p])]
    for p in landing_pages:
        if route(p) != "index.html":
            raise BuildError(f"{p}: layout: landing is only for the page routed to index.html")
    landing = parse_landing(texts[landing_pages[0]], landing_pages[0]) if landing_pages else None
    # 2. render
    pages_html: dict[str, str] = {}
    figures: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for path in pages:
            if path in landing_pages:
                continue
            pages_html[route(path)], figures[route(path)] = _render_article(
                path, texts[path], entries, patterns, tracked, ref, repo_url, (renderer, fonts, tmp)
            )
    landed: set[str] = set()
    if landing is not None:
        front = fronts[landing_pages[0]]
        pages_html["index.html"] = render_landing(
            landing,
            title=str(front.get("title") or landing_pages[0]),
            description=str(front.get("tldr") or ""),
            entries=entries,
            patterns=patterns,
            tracked=tracked,
            ref=ref,
            repo_url=repo_url,
            to_html=_markdown_converter(),
            page=landing_pages[0],
        )
        landed.add("index.html")
    # 3. decorate, then write
    bar_css = site_file("bar.css")
    final: dict[str, str] = {}
    figure_css = site_file("figures.css")
    for route_name, page_html in pages_html.items():
        if route_name in landed:  # embeds no font, and checked its own figures
            final[route_name] = insert_bar(page_html, route_name, repo_url, bar_css)
            continue
        check_rendered(page_html, route_name)
        inserted = figures.get(route_name, [])
        check_figures_survived(page_html, inserted, route_name)
        if inserted:
            page_html = insert_figure_css(page_html, route_name, figure_css)
        final[route_name] = insert_bar(page_html, route_name, repo_url, bar_css)
    for route_name, page_html in final.items():
        target = out_dir / route_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page_html, encoding="utf-8")
    return sorted(final)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Build the published site from Markdown sources")
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--ref", default=None, help="commit the blob links name (default HEAD)")
    ap.add_argument("--blog-craft", type=Path, default=os.environ.get("BLOG_CRAFT_DIR"))
    ap.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    a = ap.parse_args(argv)
    try:
        if a.blog_craft is None:
            raise BuildError("no renderer: pass --blog-craft DIR (or set BLOG_CRAFT_DIR)")
        ref = a.ref or _git(REPO, "rev-parse", "HEAD").strip()
        written = build(REPO, a.out_dir, Path(a.blog_craft), ref, a.repo_url)
    except BuildError as e:
        print(f"build-site: {e}", file=sys.stderr)
        return 1
    print(f"built {len(written)} pages into {a.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
