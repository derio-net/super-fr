"""Authored fragments, one shared implementation for all four pages (spec
2026-10-05-triage-pages-goal, R9, §C).

A page's `<state>/<page>/manifest.yaml` lists, in order, the generated sections the page
has and the fragment files beside it; `resolve_manifest` reads it and `splice` renders it,
a fragment exactly at its manifest position, between generated sections if that is where it
is listed. An entry is a string, or a mapping `{fragment: <file>, title: <text>,
collapsed: true}` that renders the fragment as a closed section.

This module knows no page: each page passes its own generated section names (and the names
that moved to another page) in.

What `validate_fragment` checks, and all it checks: the fragment is well-formed
(every tag closed in order; a self-closing tag only on a void element or inside `<svg>`)
and it carries none of: `<script>`, `<style>`, `<link>`, `<iframe>`, `<object>`,
`<embed>`, `<meta>`, `<base>`, `<form>`, `<html>`, `<head>`, `<body>`, a page-level
`<title>` (a `<title>` inside `<svg>` is allowed), an event-handler attribute (`on*`),
or a `javascript:` / `data:text/html` URL in `href`, `src` or `xlink:href`. It is not a
sanitiser: a fragment must not carry untrusted text, and whoever writes one must
HTML-escape anything that came from an issue title or any other outside source.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

import yaml

from fr.triage.components import collapsed
from fr.triage.errors import TriageError

MANIFEST_FILE = "manifest.yaml"

_VOID = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)  # fmt: skip
_FORBIDDEN = frozenset(
    "script style link iframe object embed meta base form html head body".split()
)  # fmt: skip
_URL_ATTRS = frozenset({"href", "src", "xlink:href"})
_BAD_URL = ("javascript:", "vbscript:", "data:text/html")


def _bad_url(value: str) -> bool:
    squeezed = "".join(c for c in value if c.isprintable() and not c.isspace()).lower()
    return squeezed.startswith(_BAD_URL)


class _Checker(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.error: str | None = None

    def _fail(self, message: str) -> None:
        if self.error is None:
            self.error = f"{message} (line {self.getpos()[0]})"

    def _in_svg(self) -> bool:
        return any(t == "svg" for t, _ in self.stack)

    def _inspect(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _FORBIDDEN:
            self._fail(f"<{tag}> is not allowed in a fragment")
        elif tag == "title" and not self._in_svg():
            self._fail("<title> is only allowed inside <svg> in a fragment")
        for name, value in attrs:
            if name.startswith("on"):
                self._fail(f"the event-handler attribute {name} is not allowed on <{tag}>")
            elif name in _URL_ATTRS and value is not None and _bad_url(value):
                self._fail(f"a script or html URL in {name} on <{tag}> is not allowed")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect(tag, attrs)
        if tag not in _VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect(tag, attrs)
        if tag not in _VOID and tag != "svg" and not self._in_svg():
            self._fail(f"<{tag}/> is self-closing, which HTML ignores for a non-void tag")

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID:
            return
        if not self.stack:
            self._fail(f"</{tag}> closes nothing")
        elif self.stack[-1][0] != tag:
            opened, line = self.stack[-1]
            self._fail(f"</{tag}> where <{opened}> (opened on line {line}) is still open")
        else:
            self.stack.pop()


def validate_fragment(name: str, text: str) -> None:
    """Refuse a fragment that is not well-formed, naming it and the line."""
    checker = _Checker()
    checker.feed(text)
    checker.close()
    if checker.error is None and checker.stack:
        tag, line = checker.stack[-1]
        checker.error = f"<{tag}> opened on line {line} is never closed"
    if checker.error is not None:
        raise TriageError(f"fragment {name} is malformed: {checker.error}")


@dataclass(frozen=True)
class Entry:
    """One manifest entry: a generated-section name or a fragment file name; *title* and
    *collapsed* belong to mapping entries only."""

    name: str
    title: str | None = None
    collapsed: bool = False


@dataclass(frozen=True)
class Resolved:
    """The manifest, resolved: *order* is its entries, *fragments* the files that exist
    (validated), *missing* the entries with no file, *appended* the generated sections the
    manifest omits, *moved* the entries naming a section another page now owns."""

    order: list[Entry]
    fragments: dict[str, str] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    appended: list[str] = field(default_factory=list)
    moved: dict[str, str] = field(default_factory=dict)


_MAPPING_KEYS = frozenset({"fragment", "title", "collapsed"})


def _entry(path: Path, raw: object) -> Entry:
    if isinstance(raw, str) and raw:
        return Entry(raw)
    if isinstance(raw, dict):
        unknown = sorted(str(k) for k in raw if k not in _MAPPING_KEYS)
        if unknown:
            raise TriageError(
                f"{path}: unknown key {', '.join(unknown)} in a manifest entry "
                f"(allowed: {', '.join(sorted(_MAPPING_KEYS))})"
            )
        name, title, fold = raw.get("fragment"), raw.get("title"), raw.get("collapsed", False)
        if not isinstance(name, str) or not name:
            raise TriageError(f"{path}: a mapping entry needs a `fragment:` file name")
        if title is not None and not isinstance(title, str):
            raise TriageError(f"{path}: `title:` of {name} must be text")
        if not isinstance(fold, bool):
            raise TriageError(f"{path}: `collapsed:` of {name} must be true or false")
        return Entry(name, title, fold)
    raise TriageError(
        f"{path}: `sections:` must be a list of section names, file names or "
        "`{fragment: <file>}` mappings"
    )


def resolve_manifest(
    page_dir: Path, generated: Sequence[str], moved: Mapping[str, str] | None = None
) -> Resolved:
    """`<page_dir>/manifest.yaml` and the fragments it names. No manifest means every
    *generated* section in the default order and no fragments. A generated section the
    manifest does not name is appended after its entries in the default order, never
    dropped; `appended` names them so the page can say so. A name in *moved* (section name
    to the page that now owns it) lands in `Resolved.moved`, never in `missing`."""
    moved = moved or {}
    path = page_dir / MANIFEST_FILE
    if not path.exists():
        return Resolved(order=[Entry(g) for g in generated])
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries = raw["sections"] if isinstance(raw, dict) else None
    except (yaml.YAMLError, KeyError, OSError, UnicodeDecodeError) as exc:
        raise TriageError(f"{path}: not a valid manifest (a `sections:` list): {exc}") from exc
    if not isinstance(entries, list):
        raise TriageError(f"{path}: `sections:` must be a list of section names or file names")
    order: list[Entry] = []
    seen: set[str] = set()
    fragments: dict[str, str] = {}
    missing: list[str] = []
    moved_here: dict[str, str] = {}
    for item in entries:
        entry = _entry(path, item)
        if entry.name in seen:
            continue
        seen.add(entry.name)
        is_mapping = isinstance(item, dict)
        if entry.name in moved:
            if is_mapping:
                raise TriageError(f"{path}: {entry.name!r} is a section, not a fragment file")
            moved_here[entry.name] = moved[entry.name]
            continue
        if entry.name in generated:
            if is_mapping:
                raise TriageError(
                    f"{path}: {entry.name!r} is a generated section, not a fragment file"
                )
            order.append(entry)
            continue
        order.append(entry)
        if "/" in entry.name or "\\" in entry.name or entry.name.startswith("."):
            raise TriageError(
                f"{path}: entry {entry.name!r} must be a generated section "
                f"({', '.join(generated)}) or a file directly inside the {page_dir.name}/ "
                "directory"
            )
        file = page_dir / entry.name
        if not file.is_file():
            missing.append(entry.name)
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise TriageError(f"fragment {entry.name} cannot be read: {exc}") from exc
        validate_fragment(entry.name, text)
        fragments[entry.name] = text
    appended = [name for name in generated if name not in seen]
    return Resolved(
        order=[*order, *(Entry(a) for a in appended)],
        fragments=fragments,
        missing=missing,
        appended=appended,
        moved=moved_here,
    )


def _fragment(entry: Entry, text: str) -> str:
    section = (
        f'<section class="fragment" data-fragment="{html.escape(entry.name, quote=True)}">'
        f'<div class="scroll">{text}</div></section>'
    )
    if not entry.collapsed:
        return section
    slug = re.sub(r"[^A-Za-z0-9]+", "-", entry.name).strip("-").lower()
    return collapsed(f"fragment-{slug}", entry.title or entry.name, None, section)


def splice(resolved: Resolved, generated: Mapping[str, Callable[[], str]]) -> list[str]:
    """Walk `order` once: a generated entry becomes its builder's HTML, a fragment entry its
    wrapped file (closed, when the entry asks). An entry with no builder and no file (a
    missing fragment) renders nothing."""
    out: list[str] = []
    for entry in resolved.order:
        if entry.name in generated:
            out.append(generated[entry.name]())
        elif entry.name in resolved.fragments:
            out.append(_fragment(entry, resolved.fragments[entry.name]))
    return out
