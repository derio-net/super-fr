"""The architecture page, `fr triage architecture render` (spec 2026-10-05-triage-pages-goal,
R6, §E; wave-driver R11, R16).

The page answers "What is the system, and where does it hurt?": a **summary** (source
lines then and now, and the three subsystems with the most open defects), the
**subsystem cards**, the **size table**, then the authored fragments the manifest places
(`fr.triage.fragments`, shared by all four pages). It reads, from the scope's state
directory: `facts.json`, `judgements.yaml`, `subsystems.yaml` (optional),
`architecture/manifest.yaml` (optional) and the fragments it names.

Everything measured comes from a read: line counts from `git ls-tree` and `git grep` at
two refs (through `fr.triage.gitseam`, the one module that starts processes), each
measurement naming its commit. A figure that was not measured is an em dash, never a zero.
Lines are counted as `git grep -c ''` counts them (every `\\n`-terminated line, plus a
last unterminated one) over regular text files the subsystem's globs match; binary files,
symlinks and submodules are not counted.

The waves, the operator actions, filings per day, where the issues came from and the
snapshot timeline are not here: `MOVED` names the page that owns each now.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fr.triage.components import (
    BASE_CSS,
    CHROME_CSS,
    GUTTER_CSS,
    TOKENS_CSS,
    page_header,
)
from fr.triage.errors import TriageError
from fr.triage.fragments import Resolved, splice
from fr.triage.gitseam import Checkout, GitError
from fr.triage.model import Facts, Issue, Judgements
from fr.triage.render import FONTS, esc, plural
from fr.triage.views import kind_counts

DASH = "—"
OTHER = "Other"
PAGE_FILE = "architecture.html"
ARCHITECTURE_DIR = "architecture"
SUBSYSTEMS_FILE = "subsystems.yaml"

# The generated sections, in the default order; fragments interleave where the manifest says.
GENERATED = ("summary", "subsystems", "size-table")

# Sections an older manifest may still name that another page owns now (R6).
MOVED = {
    "waves": "board",
    "operator-actions": "board",
    "filings-per-day": "origins",
    "origin-counts": "origins",
    "timeline": "history",
}


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


# ------------------------------------------------------------------------- page

CSS = (
    TOKENS_CSS
    + BASE_CSS
    + """
.figures { display: flex; flex-wrap: wrap; gap: 10px; }
.figure { flex: 1 1 150px; background: var(--surface); border: 1px solid var(--line);
  border-radius: 8px; padding: 8px 12px; }
.figure b { display: block; font: 500 1.5rem var(--mono); }
.figure small { display: block; color: var(--muted); font-size: .75rem; }
.hurts { margin: 12px 0 0; padding-left: 20px; }
.hurts li { margin: 2px 0; }
.grid-cards { display: grid; gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
article.subsystem { background: var(--surface); border: 1px solid var(--line);
  border-radius: 8px; padding: 10px 14px; min-width: 0; overflow-wrap: anywhere; }
article.subsystem h3 { margin: 0 0 4px; font-size: 1rem; }
article.subsystem ul { margin: 6px 0 0; padding-left: 18px; font-size: .85rem; }
.bar-row { display: grid; grid-template-columns: 7.5em 1fr 4em; gap: 8px; align-items: center;
  font-size: .8rem; margin: 3px 0; }
.bar-row .track { background: var(--ground); border-radius: 3px; height: 10px; }
.bar-row .fill { background: var(--accent); height: 10px; border-radius: 3px; }
.bar-row .fill.then { background: var(--sev-4); }
.bar-row .v { font-family: var(--mono); text-align: right; }
"""
    + CHROME_CSS
    + GUTTER_CSS
)


def _delta(a: int | None, b: int | None) -> str:
    return DASH if a is None or b is None else f"{b - a:+d}"


def _num(n: int | None) -> str:
    return DASH if n is None else str(n)


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
            f'<article class="subsystem" id="subsystem-{esc(_slug(name))}" '
            f'data-subsystem="{esc(name)}"><h3>{esc(name)}</h3>'
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


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _defects(issues: Sequence[Issue], judgements: Judgements) -> int:
    return sum(1 for i in issues if (j := judgements.issues.get(i.key)) and j.kind == "defect")


def _hurts(placed: Mapping[str, Sequence[Issue]], judgements: Judgements) -> list[str]:
    """The three subsystems with the most open `kind: defect` issues (ties: most open
    issues, then name); a subsystem with no open defect is not listed."""
    ranked = sorted(
        ((_defects(v, judgements), len(v), k) for k, v in placed.items()),
        key=lambda t: (-t[0], -t[1], t[2]),
    )
    return [k for n, _, k in ranked if n][:3]


def _summary(
    facts: Facts,
    judgements: Judgements,
    subsystems: Subsystems,
    measured: Mapping[str, Measured],
) -> str:
    then = [m.then.lines for m in measured.values() if m.then is not None]
    now = [m.now.lines for m in measured.values() if m.now is not None]
    open_n = sum(1 for i in facts.issues if i.state == "open")
    figures = [
        ("lines then", _num(sum(then) if then else None), "git, at each subsystem's then_ref"),
        ("lines now", _num(sum(now) if now else None), "git, at the now ref"),
        ("open issues", str(open_n), f"facts.json, collected {facts.collected_at}"),
        (
            "defects",
            str(kind_counts(facts, judgements)["defect"]),
            "judgements.yaml: open issues with kind: defect",
        ),
    ]
    cells = "".join(
        f'<div class="figure" data-figure="{esc(name)}"><b>{esc(value)}</b>'
        f"<span>{esc(name)}</span><small>{esc(src)}</small></div>"
        for name, value, src in figures
    )
    placed = _place(facts, judgements, subsystems)
    worst = _hurts(placed, judgements)
    if worst:
        items = "".join(
            f'<li><a href="#subsystem-{esc(_slug(name))}">{esc(name)}</a> '
            f"{plural(_defects(placed[name], judgements), 'open defect')}</li>"
            for name in worst
        )
        hurts = f'<h3>Where it hurts</h3><ol class="hurts">{items}</ol>'
    else:
        hurts = (
            '<h3>Where it hurts</h3><p class="quiet">No open defect is placed in a subsystem.</p>'
        )
    return (
        f'<section id="summary"><h2>Summary</h2><div class="figures">{cells}</div>{hurts}</section>'
    )


def render_architecture(
    facts: Facts,
    judgements: Judgements,
    *,
    subsystems: Subsystems,
    measured: Mapping[str, Measured],
    resolved: Resolved,
    notes: Sequence[str] = (),
) -> str:
    """The page: same inputs, same bytes. The generated sections and the authored fragments
    in the order *resolved* (the manifest) gives, a fragment exactly where it is listed."""
    generated = {
        "summary": lambda: _summary(facts, judgements, subsystems, measured),
        "subsystems": lambda: _subsystems(facts, judgements, subsystems, measured),
        "size-table": lambda: _size_table(subsystems, measured),
    }
    body = splice(resolved, generated)
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
        f"{page_header('architecture')}\n" + "\n".join(body) + "\n</main>\n</body>\n</html>\n"
    )
