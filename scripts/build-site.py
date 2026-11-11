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
import os
import posixpath
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REPO_URL = "https://github.com/derio-net/super-fr"
MARKER = "<!-- site:pages -->"
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


def fill_pages(text: str, page: str, entries: list[Entry]) -> str:
    """Replace the `<!-- site:pages -->` marker with the grouped list of pages."""
    if MARKER not in text:
        return text
    blocks: list[str] = []
    for key, heading in SECTIONS:
        rows = [
            f"- [{e.title}]({posixpath.relpath(e.path, posixpath.dirname(page))}): "
            f"{first_sentence(e.tldr)}"
            for e in sorted(entries, key=lambda e: e.path)
            if e.path != page and _section(e.path) == key
        ]
        if rows:
            blocks.append(f"### {heading}\n\n" + "\n".join(rows))
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


def check_rendered(html: str, route_name: str) -> None:
    """Fail a page the renderer emitted without its embedded fonts."""
    if not re.search(r"@font-face\s*\{[^}]*url\(\s*data:", html):
        raise BuildError(f"{route_name}: rendered with no embedded @font-face data URI")


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


def build(root: Path, out_dir: Path, blog_craft: Path, ref: str, repo_url: str) -> list[str]:
    """Render every configured page into `out_dir`; return the routes written."""
    renderer = blog_craft / "tools" / "render_explainer.py"
    if not renderer.is_file():
        raise BuildError(f"{renderer} not found: pass --blog-craft DIR (or set BLOG_CRAFT_DIR)")
    fonts = blog_craft / FONTS_SUBDIR
    if not fonts.is_dir():
        raise BuildError(f"{fonts} not found: the renderer would fall back to system fonts")
    patterns = load_config(root / ".fr" / "docs.yaml")
    tracked = tracked_files(root)
    pages = select_pages(patterns, tracked)
    if not pages:
        raise BuildError("the config selects no tracked page")
    texts = {p: (root / p).read_text(encoding="utf-8") for p in pages}
    entries = [
        Entry(p, str(fm.get("title") or p), str(fm.get("tldr") or ""))
        for p in pages
        for fm in [parse_front_matter(texts[p])]
    ]
    written: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for path in pages:
            text = fill_pages(drop_leading_h1(texts[path]), path, entries)
            text = rewrite_markdown(text, path, patterns, tracked, ref, repo_url)
            source = Path(tmp) / posixpath.basename(path)
            source.write_text(text, encoding="utf-8")
            target = out_dir / route(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            check_rendered(render_page(renderer, fonts, source, target), route(path))
            written.append(route(path))
    return written


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
