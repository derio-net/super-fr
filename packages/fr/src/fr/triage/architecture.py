"""The architecture page, `fr triage architecture render` (wave-driver R11, R12, R16, R20).

One page, ordered by R20: the **snapshot timeline** first (stepping through the stored
snapshots shows what the board showed then), then the **measured sections** the engine
generates, then the **authored fragments** the agent wrote. It reads, from the scope's
state directory: `facts.json`, `judgements.yaml`, `origins-facts.json` and `origins.yaml`
(both optional), `subsystems.yaml` (optional), `architecture/manifest.yaml` (optional)
and the fragments it names, and the snapshots.

Everything measured comes from a read: line counts from `git ls-tree` and `git grep` at
two refs (through `fr.triage.gitseam`, the one module that starts processes), each
measurement naming its commit; the operator actions are `views.needs_you`, the very
function the board uses. A figure that was not measured is an em dash, never a zero.
Lines are counted as `git grep -c ''` counts them (every `\\n`-terminated line, plus a
last unterminated one) over regular text files the subsystem's globs match; binary files,
symlinks and submodules are not counted.

Authored fragments are HTML files, inlined in manifest order inside the shared theme
shell. What `validate_fragment` checks, and all it checks: the fragment is well-formed
(every tag closed in order; a self-closing tag only on a void element or inside `<svg>`)
and it carries none of: `<script>`, `<style>`, `<link>`, `<iframe>`, `<object>`,
`<embed>`, `<meta>`, `<base>`, `<form>`, `<html>`, `<head>`, `<body>`, a page-level
`<title>` (a `<title>` inside `<svg>` is allowed), an event-handler attribute (`on*`),
or a `javascript:` / `data:text/html` URL in `href`, `src` or `xlink:href`. It is not a
sanitiser: a fragment must not carry untrusted text, and whoever writes one must
HTML-escape anything that came from an issue title or any other outside source.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fr.triage.batch import derive_batch_stage
from fr.triage.components import GUTTER_CSS, TABS_CSS, TABS_SCRIPT, TOKENS_CSS, tabs
from fr.triage.errors import TriageError
from fr.triage.gitseam import Checkout, GitError
from fr.triage.model import Batch, Facts, Issue, Judgements
from fr.triage.origins import Origins, OriginsFacts, filings_chart, origin_counts
from fr.triage.render import FONTS, esc, plural
from fr.triage.snapshot import Snapshot, diff_snapshots
from fr.triage.views import NEED_LABELS, UNWAVED, kind_counts, needs_you, preselected_wave, waves

DASH = "—"
OTHER = "Other"
PAGE_FILE = "architecture.html"
ARCHITECTURE_DIR = "architecture"
MANIFEST_FILE = "manifest.yaml"
SUBSYSTEMS_FILE = "subsystems.yaml"

# The measured sections, in the default order (R20: after the timeline, before authored).
GENERATED = (
    "summary",
    "waves",
    "subsystems",
    "size-table",
    "filings-per-day",
    "origin-counts",
    "operator-actions",
)


# ------------------------------------------------------------------ subsystems


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Subsystem(_Strict):
    name: str = Field(min_length=1)
    path: list[str] = Field(min_length=1)  # globs; `*` spans `/`
    then_ref: str = Field(min_length=1)  # the git ref "then" is measured at
    themes: list[str] = []  # judgement themes that place an open issue here


class Subsystems(_Strict):
    subsystems: list[Subsystem] = []


def load_subsystems(path: Path) -> Subsystems:
    """`subsystems.yaml`; absent is no subsystems, a bad one is refused with *path*."""
    if not path.exists():
        return Subsystems()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return Subsystems.model_validate(raw)
    except (yaml.YAMLError, ValidationError, OSError, UnicodeDecodeError) as exc:
        raise TriageError(f"{path}: not a valid subsystems.yaml: {exc}") from exc


@dataclass(frozen=True)
class Measure:
    """One measurement: *lines* across *files* at the commit *ref* names."""

    ref: str
    commit: str
    files: int
    lines: int


@dataclass(frozen=True)
class Measured:
    """A subsystem's two measurements; None is a figure that could not be taken."""

    then: Measure | None
    now: Measure | None


def _matches(name: str, globs: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(name, g) for g in globs)


def _measure(checkout: Checkout, ref: str, globs: Sequence[str]) -> Measure | None:
    commit = checkout.short_rev(ref)
    if commit is None:
        return None
    try:
        counts = checkout.text_line_counts(ref)
    except (GitError, UnicodeError):
        return None  # a figure git could not give us exactly is a dash, never a guess
    matched = [n for n in counts if _matches(n, globs)]
    if not matched:
        return None  # nothing measured at that ref: a dash, not a zero
    return Measure(
        ref=ref, commit=commit, files=len(matched), lines=sum(counts[n] for n in matched)
    )


def measure_subsystems(
    checkout: Checkout, subsystems: Subsystems, *, now_ref: str
) -> dict[str, Measured]:
    """Per subsystem: its lines at its own `then_ref` and at *now_ref*."""
    return {
        s.name: Measured(
            then=_measure(checkout, s.then_ref, s.path),
            now=_measure(checkout, now_ref, s.path),
        )
        for s in subsystems.subsystems
    }


# -------------------------------------------------------------------- fragments

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
class Resolved:
    """The manifest, resolved: *order* is its entries, *fragments* the files that exist
    (validated), *missing* the entries with no file."""

    order: list[str]
    fragments: dict[str, str] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    appended: list[str] = field(default_factory=list)  # generated sections the manifest omits


def resolve_manifest(arch_dir: Path) -> Resolved:
    """`architecture/manifest.yaml` and the fragments it names. No manifest means every
    generated section in the default order and no fragments. A generated section the
    manifest does not name is appended in the default order (it renders before the
    fragments, R20), never dropped; `appended` names them so the page can say so."""
    path = arch_dir / MANIFEST_FILE
    if not path.exists():
        return Resolved(order=list(GENERATED))
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries = raw["sections"] if isinstance(raw, dict) else None
    except (yaml.YAMLError, KeyError, OSError, UnicodeDecodeError) as exc:
        raise TriageError(f"{path}: not a valid manifest (a `sections:` list): {exc}") from exc
    if not isinstance(entries, list) or not all(isinstance(e, str) and e for e in entries):
        raise TriageError(f"{path}: `sections:` must be a list of section names or file names")
    order: list[str] = []
    fragments: dict[str, str] = {}
    missing: list[str] = []
    for entry in entries:
        if entry in order:
            continue
        order.append(entry)
        if entry in GENERATED:
            continue
        if "/" in entry or "\\" in entry or entry.startswith("."):
            raise TriageError(
                f"{path}: entry {entry!r} must be a generated section "
                f"({', '.join(GENERATED)}) or a file directly inside the {ARCHITECTURE_DIR}/ "
                "directory"
            )
        file = arch_dir / entry
        if not file.is_file():
            missing.append(entry)
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise TriageError(f"fragment {entry} cannot be read: {exc}") from exc
        validate_fragment(entry, text)
        fragments[entry] = text
    appended = [name for name in GENERATED if name not in order]
    return Resolved(
        order=[*order, *appended], fragments=fragments, missing=missing, appended=appended
    )


# ------------------------------------------------------------------------- page

CSS = (
    TOKENS_CSS
    + """
* { box-sizing: border-box; }
html, body { margin: 0; overflow-x: hidden; }
body { background: var(--ground); color: var(--ink); font: 15px/1.5 var(--sans); }
main { max-width: 1040px; margin: 0 auto; padding: 0 16px 48px; }
a { color: var(--accent); }
code { font-family: var(--mono); font-size: .92em; overflow-wrap: anywhere; }
header.mast { padding: 28px 0 16px; border-bottom: 2px solid var(--ink); }
header.mast h1 { margin: 0 0 6px; font-size: 1.6rem; font-weight: 600; overflow-wrap: anywhere; }
.meta { color: var(--muted); font-size: .88rem; display: flex; flex-wrap: wrap; gap: 4px 16px; }
.notes { margin: 12px 0 0; padding: 0; list-style: none; font-size: .85rem; color: var(--sev-2); }
section { margin-top: 28px; }
section > h2 { margin: 0 0 8px; font-size: 1.15rem; font-weight: 600; }
.lede, .src { color: var(--muted); font-size: .85rem; margin: 0 0 10px; }
.quiet { color: var(--muted); }
.figures { display: flex; flex-wrap: wrap; gap: 10px; }
.figure { flex: 1 1 150px; background: var(--surface); border: 1px solid var(--line);
  border-radius: 8px; padding: 8px 12px; }
.figure b { display: block; font: 500 1.5rem var(--mono); }
.figure small { display: block; color: var(--muted); font-size: .75rem; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 6px 0; }
.chip { background: var(--surface); border: 1px solid var(--line); border-radius: 999px;
  padding: 2px 10px; font-size: .85rem; }
.chip b { font-family: var(--mono); font-weight: 500; }
.scroll { overflow-x: auto; }
table { width: 100%; min-width: 560px; border-collapse: collapse; background: var(--surface);
  border: 1px solid var(--line); font-size: .88rem; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line);
  vertical-align: top; }
th { color: var(--muted); font-weight: 500; }
td.n, th.n { text-align: right; font-family: var(--mono); }
svg.chart { display: block; height: auto; }
svg.chart text { font-family: var(--mono); font-size: 10px; }
.cards { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.cards li { background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
  padding: 6px 12px; overflow-wrap: anywhere; }
.kind { font-size: .75rem; color: var(--surface); background: var(--sev-2);
  border-radius: 999px; padding: 1px 9px; margin-right: 8px; white-space: nowrap; }
.grid-cards { display: grid; gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
article.subsystem { background: var(--surface); border: 1px solid var(--line);
  border-radius: 8px; padding: 10px 14px; min-width: 0; }
article.subsystem h3 { margin: 0 0 4px; font-size: 1rem; }
article.subsystem ul { margin: 6px 0 0; padding-left: 18px; font-size: .85rem; }
.bar-row { display: grid; grid-template-columns: 7.5em 1fr 4em; gap: 8px; align-items: center;
  font-size: .8rem; margin: 3px 0; }
.bar-row .track { background: var(--ground); border-radius: 3px; height: 10px; }
.bar-row .fill { background: var(--accent); height: 10px; border-radius: 3px; }
.bar-row .fill.then { background: var(--sev-4); }
.bar-row .v { font-family: var(--mono); text-align: right; }
.stages { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: .85rem; }
.fragment { margin-top: 28px; }
"""
    + TABS_CSS
    + GUTTER_CSS
)


def _stamp(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _delta(a: int | None, b: int | None) -> str:
    return DASH if a is None or b is None else f"{b - a:+d}"


def _num(n: int | None) -> str:
    return DASH if n is None else str(n)


def _list(items: Sequence[str]) -> str:
    return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"


def _snapshot_panel(snap: Snapshot, previous: Snapshot | None) -> str:
    rows = []
    for name, value in snap.figures.items():
        before = previous.figures.get(name) if previous is not None else None
        change = DASH if before is None else f"{value - before:+d}"
        rows.append(
            f'<tr><td>{esc(name)}</td><td class="n">{value}</td><td class="n">{change}</td></tr>'
        )
    table = (
        '<div class="scroll"><table><thead><tr><th>Figure</th><th class="n">Then</th>'
        f'<th class="n">Change</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )
    stages = "".join(
        f"<span><code>{esc(b)}</code> {esc(s)}</span>" for b, s in sorted(snap.batches.items())
    )
    diff = diff_snapshots(previous, snap)
    parts = ['<p class="src">Measured then: the figures and batch stages this snapshot stored.</p>']
    parts.append(table)
    parts.append(f'<div class="stages">{stages or "no batches"}</div>')
    if diff is None:
        parts.append('<p class="lede">The earliest snapshot: nothing earlier to compare.</p>')
    elif diff.empty:
        parts.append('<p class="lede">Nothing changed since the snapshot before.</p>')
    else:
        for title, items in (
            ("Merged or closed", diff.merged_or_closed),
            ("Filed", diff.filed),
            ("Batch stage changes", diff.stage_changes),
            ("Acceptance rows moved", diff.acceptance_moved),
        ):
            if items:
                parts.append(f"<h4>{title}</h4>{_list(items)}")
    return "".join(parts)


def _timeline(snapshots: Sequence[tuple[datetime, Snapshot]]) -> str:
    head = '<section id="snapshot-timeline"><h2>Snapshot timeline</h2>'
    if not snapshots:
        return (
            f'{head}<p class="quiet">No snapshots yet: `fr triage render` stores one each '
            "time the board changes, and the timeline steps through them.</p></section>"
        )
    panels = [
        (f"s{i}", _stamp(when), _snapshot_panel(snap, snapshots[i - 1][1] if i else None))
        for i, (when, snap) in enumerate(snapshots)
    ]
    note = ""
    if len(snapshots) == 1:
        note = (
            '<p class="lede">Only one snapshot is stored, so there is nothing to step '
            "through yet; the next render that changes the board adds a step.</p>"
        )
    return f"{head}{note}{tabs('snapshot', 'Snapshots', panels, len(panels) - 1)}</section>"


def _summary(facts: Facts, judgements: Judgements, origins_facts: OriginsFacts | None) -> str:
    open_n = sum(1 for i in facts.issues if i.state == "open")
    defects = kind_counts(facts, judgements)["defect"]
    merged = sum(1 for b in judgements.batches if derive_batch_stage(b, facts) == "merged")
    filed = (
        (str(len(origins_facts.issues)), f"origins-facts.json, filed since {origins_facts.since}")
        if origins_facts is not None
        else (DASH, "origins-facts.json (not collected)")
    )
    figures = [
        ("open issues", str(open_n), f"facts.json, collected {facts.collected_at}"),
        ("defects", str(defects), "judgements.yaml: open issues with kind: defect"),
        ("issues filed", *filed),
        ("batches merged", str(merged), "judgements.yaml batches, stage from facts.json"),
    ]
    cells = "".join(
        f'<div class="figure" data-figure="{esc(name)}"><b>{esc(value)}</b>'
        f"<span>{esc(name)}</span><small>{esc(src)}</small></div>"
        for name, value, src in figures
    )
    return f'<section id="summary"><h2>Summary</h2><div class="figures">{cells}</div></section>'


def _wave_panel(batches: Sequence[Batch], facts: Facts) -> str:
    rows = [
        f'<tr data-batch="{esc(b.id)}"><td class="n">{position}</td>'
        f"<td><code>{esc(b.id)}</code> {esc(b.title)}</td><td>{esc(b.skill)}</td>"
        f"<td>{esc(', '.join(b.ids))}</td><td>{esc(', '.join(b.after) or DASH)}</td>"
        f"<td>{esc(derive_batch_stage(b, facts))}</td></tr>"
        for position, b in enumerate(batches, start=1)
    ]
    cols = ("Order", "Batch", "Skill", "Issues", "Depends on", "Stage")
    head = "".join(f"<th>{c}</th>" for c in cols)
    return (
        f'<div class="scroll"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _waves(facts: Facts, judgements: Judgements) -> str:
    head = '<section id="waves"><h2>Waves and batch order</h2>'
    grouped = waves(judgements)
    if not grouped:
        none = '<p class="quiet">No waves: no batch carries a <code>wave</code> yet.</p>'
        return f"{head}{none}</section>"
    picked = preselected_wave(facts, judgements)
    keys = list(grouped)
    selected = keys.index(str(picked)) if picked is not None else len(keys) - 1
    panels = [
        (key, "No wave" if key == UNWAVED else f"Wave {key}", _wave_panel(batches, facts))
        for key, batches in grouped.items()
    ]
    return f"{head}{tabs('wave', 'Waves', panels, selected)}</section>"


def _place(facts: Facts, judgements: Judgements, subsystems: Subsystems) -> dict[str, list[Issue]]:
    """Open issues by subsystem name; an issue whose theme maps to none (or that is not
    judged) is under `Other`. Never dropped."""
    by_theme = {t: s.name for s in reversed(subsystems.subsystems) for t in s.themes}
    placed: dict[str, list[Issue]] = {s.name: [] for s in subsystems.subsystems}
    placed[OTHER] = []
    for issue in facts.issues:
        if issue.state != "open":
            continue
        judged = judgements.issues.get(issue.key)
        placed[by_theme.get(judged.theme if judged else "", OTHER)].append(issue)
    return placed


def _bar(label: str, m: Measure | None, scale: int) -> str:
    if m is None:
        return (
            f'<div class="bar-row"><span>{esc(label)}</span><div class="track"></div>'
            f'<span class="v">{DASH}</span></div>'
        )
    width = 100.0 * m.lines / scale if scale else 0.0
    cls = "fill then" if label == "then" else "fill"
    return (
        f'<div class="bar-row"><span>{esc(label)} <code>{esc(m.commit)}</code></span>'
        f'<div class="track"><div class="{cls}" data-lines="{m.lines}" '
        f'style="width:{width:.1f}%"></div></div><span class="v">{m.lines}</span></div>'
    )


def _subsystems(
    facts: Facts,
    judgements: Judgements,
    subsystems: Subsystems,
    measured: Mapping[str, Measured],
) -> str:
    placed = _place(facts, judgements, subsystems)
    lines = [m.lines for ms in measured.values() for m in (ms.then, ms.now) if m is not None]
    scale = max(lines, default=0)
    cards = []
    for name in [*(s.name for s in subsystems.subsystems), OTHER]:
        issues = placed[name]
        if name == OTHER and not issues:
            continue
        sub = next((s for s in subsystems.subsystems if s.name == name), None)
        ms = measured.get(name)
        body = ""
        if sub is not None:
            body += f'<p class="src">{esc(", ".join(sub.path))}</p>'
            body += _bar("then", ms.then if ms else None, scale)
            body += _bar("now", ms.now if ms else None, scale)
        items = "".join(
            f'<li data-issue="{esc(i.key)}"><a href="{esc(i.url)}">{esc(i.key)}</a> '
            f"{esc(i.title)}</li>"
            for i in issues
        )
        cards.append(
            f'<article class="subsystem" data-subsystem="{esc(name)}"><h3>{esc(name)}</h3>'
            f'{body}<p class="src">{plural(len(issues), "open issue")}</p>'
            f"<ul>{items}</ul></article>"
        )
    lede = (
        ""
        if subsystems.subsystems
        else '<p class="lede">No subsystems.yaml: every open issue is under Other.</p>'
    )
    return (
        f'<section id="subsystems"><h2>Subsystems</h2>{lede}'
        f'<div class="grid-cards">{"".join(cards)}</div></section>'
    )


def _commits(ms: Measured | None) -> str:
    if ms is None:
        return DASH
    then = f"{ms.then.ref}@{ms.then.commit}" if ms.then else DASH
    now = f"{ms.now.ref}@{ms.now.commit}" if ms.now else DASH
    return f"{then} → {now}"


def _size_table(subsystems: Subsystems, measured: Mapping[str, Measured]) -> str:
    rows = []
    for s in subsystems.subsystems:
        ms = measured.get(s.name)
        then = ms.then if ms else None
        now = ms.now if ms else None
        rows.append(
            f'<tr data-subsystem="{esc(s.name)}"><td>{esc(s.name)}</td>'
            f'<td class="n">{_num(then.files if then else None)}</td>'
            f'<td class="n">{_num(now.files if now else None)}</td>'
            f'<td class="n">{_num(then.lines if then else None)}</td>'
            f'<td class="n">{_num(now.lines if now else None)}</td>'
            f'<td class="n">{_delta(then.lines if then else None, now.lines if now else None)}</td>'
            f"<td><code>{esc(_commits(ms))}</code></td></tr>"
        )
    cols = ("Subsystem", "Files then", "Files now", "Lines then", "Lines now", "Change", "Commits")
    head = "".join(
        f'<th class="n">{c}</th>' if 0 < i < 6 else f"<th>{c}</th>" for i, c in enumerate(cols)
    )
    body = "".join(rows) or f'<tr><td colspan="7">{DASH} no subsystems.yaml</td></tr>'
    return (
        '<section id="size-table"><h2>Size</h2><p class="src">Lines: every line of every text file '
        "matched by the subsystem's globs; binary files, symlinks and submodules are not "
        "counted; a moved file moves its lines between subsystems. Counted with "
        "<code>git ls-tree</code> and <code>git grep</code> at the commits named; "
        f"{DASH} is a figure that could not be measured.</p>"
        f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
        "</div></section>"
    )


def _operator_actions(facts: Facts, judgements: Judgements) -> str:
    head = '<section id="operator-actions"><h2>Operator actions</h2>'
    rows = needs_you(facts, judgements)
    if not rows:
        return f'{head}<p class="quiet">Nothing needs the operator now.</p></section>'
    items = "".join(
        f'<li class="need" data-need="{esc(r.kind)}" data-ref="{esc(r.ref)}">'
        f'<span class="kind">{esc(NEED_LABELS[r.kind])}</span>'
        + (
            f'<a href="{esc(r.href)}">{esc(r.text)}</a>'
            if r.href and r.href.startswith("https://")
            else esc(r.text)
        )
        + "</li>"
        for r in rows
    )
    return (
        f'{head}<p class="src">The board\'s Needs you now, computed by the same function.</p>'
        f'<ul class="cards">{items}</ul></section>'
    )


def render_architecture(
    facts: Facts,
    judgements: Judgements,
    *,
    origins_facts: OriginsFacts | None,
    origins: Origins | None,
    subsystems: Subsystems,
    measured: Mapping[str, Measured],
    order: Sequence[str],
    fragments: Mapping[str, str],
    snapshots: Sequence[tuple[datetime, Snapshot]],
    notes: Sequence[str] = (),
) -> str:
    """The page: same inputs, same bytes. R20: the timeline, then the measured sections
    in the manifest's order, then the authored fragments in the manifest's order."""
    generated = {
        "summary": lambda: _summary(facts, judgements, origins_facts),
        "waves": lambda: _waves(facts, judgements),
        "subsystems": lambda: _subsystems(facts, judgements, subsystems, measured),
        "size-table": lambda: _size_table(subsystems, measured),
        "filings-per-day": lambda: filings_chart(origins_facts) if origins_facts else "",
        "origin-counts": lambda: (
            origin_counts(origins_facts, origins) if origins_facts and origins else ""
        ),
        "operator-actions": lambda: _operator_actions(facts, judgements),
    }
    body = [_timeline(snapshots)]
    body += [generated[name]() for name in order if name in generated]
    for name in order:
        if name in fragments:
            body.append(
                f'<section class="fragment" data-fragment="{esc(name)}">'
                f'<div class="scroll">{fragments[name]}</div></section>'
            )
    title = f"Architecture · {facts.scope}"
    notes_html = "".join(f"<li>{esc(n)}</li>" for n in notes)
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n{FONTS}\n<style>{CSS}</style>\n</head>\n<body>\n<main>\n"
        f'<header class="mast"><h1>{esc(title)}</h1><div class="meta">'
        f"<span>collected {esc(facts.collected_at)}</span>"
        "<span>rendered by <code>fr triage architecture render</code></span></div>"
        f'<ul class="notes">{notes_html}</ul></header>\n'
        + "\n".join(body)
        + f"\n</main>\n<script>{TABS_SCRIPT}</script>\n</body>\n</html>\n"
    )
