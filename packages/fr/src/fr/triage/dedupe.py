"""Duplicate-candidate groups among the open issues (spec triage-dedupe §3.B).

Pure: facts and judgements in, groups out. No forge, no clock, no model (the
`no-claude-p-batch` rule): the engine PROPOSES, the fr-triage skill judges, and
the verdict is `duplicate_of` / `distinct_from` in `judgements.yaml`.

A pair is flagged when any one of four signals holds, each a small function that
returns its reason or None:

- **title**   - the Jaccard similarity of the title word sets is >= `TITLE_MATCH`;
- **identifiers** - two rare shared code identifiers, or one plus a title >= `TITLE_NEAR`;
- **finding** - the same journal finding id AND a shared `#<n>` reference;
- **theme**   - the same non-empty theme and a title >= `TITLE_NEAR`.

Flagged pairs are joined into groups by connectivity: #594 and #631 of the
calibration are joined only through #607.
"""

from __future__ import annotations

import itertools
import re
from collections import Counter
from dataclasses import dataclass

from fr.triage.batch import theme_key
from fr.triage.model import Facts, Issue, Judgements

TITLE_MATCH = 0.5  # title Jaccard that flags a pair on its own
TITLE_NEAR = 0.25  # title Jaccard that corroborates one identifier, or a shared theme
RARE = 3  # an identifier named by more open issues than this is not rare
MIN_IDENT = 8  # an identifier leaf is at least this long, and has an underscore

_STOP = frozenset(
    "a an the of to in on for and or is are be by with from at as it its not no when "
    "after before this that into via fr".split()
)
_WORD = re.compile(r"[a-z0-9_]+")
_TICK = re.compile(r"`([^`\n]{3,80})`")
_EXT = r"(?:py|md|ts|sh|ya?ml|json|toml|html)"
_BARE = re.compile(rf"\b[A-Za-z_][A-Za-z0-9]*_[A-Za-z0-9_]+(?:\.{_EXT}\b)?")
_FILE_LEAF = re.compile(rf"\.{_EXT}$")
_LINE_SUFFIX = re.compile(r":\d+(-\d+)?$")
_FINDING = re.compile(
    r"finding[s]?\s+[`*]*([a-z0-9]+(?:-[a-z0-9]+)+|[a-z0-9]*\d[a-z0-9]*)\b", re.IGNORECASE
)
_REF = re.compile(r"(?<![\w/])#(\d+)\b")


@dataclass(frozen=True)
class Pair:
    a: str  # keys, a < b
    b: str
    reasons: tuple[str, ...]  # e.g. "title 0.62", "identifiers verify_tests_log"


@dataclass(frozen=True)
class CandidateGroup:
    keys: tuple[str, ...]  # sorted
    pairs: tuple[Pair, ...]  # sorted by (a, b)


@dataclass(frozen=True)
class _Doc:
    key: str
    title: str
    words: frozenset[str]
    idents: frozenset[str]
    findings: frozenset[str]
    refs: frozenset[str]
    theme: str


def _words(text: str) -> frozenset[str]:
    return frozenset(
        w for w in _WORD.findall(text.lower()) if w not in _STOP and (len(w) > 2 or w.isdigit())
    )


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / max(1, len(a | b))


def _code_tokens(text: str) -> list[str]:
    """Every code-shaped token: a backticked one (no spaces; has `_ . / ( :` or
    camelCase) and every bare snake_case word."""
    out: list[str] = []
    for tok in _TICK.findall(text):
        if " " in tok.strip():
            continue
        if re.search(r"[_./(:]", tok) or re.search(r"[a-z][A-Z]", tok):
            out.append(tok)
    out.extend(_BARE.findall(text))
    return out


def _split(token: str) -> tuple[set[str], set[str]]:
    """`(identifier leaves, module names)` of one code-shaped token.

    The leaf is the last `::`, `/` or `.` segment, with a `:<line>` suffix and `()`
    removed. A file leaf is no identifier (its stem is a module name), and every
    non-last `::` or `/` segment, cut at its first `.`, is a module name.
    """
    tok = _LINE_SUFFIX.sub("", token.strip().rstrip("()")).lower()
    pieces = re.split(r"::|/", tok)
    modules = {p.split(".")[0] for p in pieces[:-1]}
    leaf = pieces[-1]
    if _FILE_LEAF.search(leaf):
        modules.add(leaf.rsplit(".", 1)[0])
        return set(), modules
    leaf = leaf.rsplit(".", 1)[-1]
    return ({leaf} if len(leaf) >= MIN_IDENT and "_" in leaf else set()), modules


def _text(issue: Issue) -> str:
    return f"{issue.title}\n{issue.body}"


# ------------------------------------------------------------------ signals


def _title(a: _Doc, b: _Doc) -> str | None:
    j = _jaccard(a.words, b.words)
    return f"title {j:.2f}" if j >= TITLE_MATCH else None


def _identifiers(a: _Doc, b: _Doc, df: Counter[str], modules: frozenset[str]) -> str | None:
    shared = {s for s in a.idents & b.idents if df[s] <= RARE and s not in modules}
    if len(shared) >= 2 or (shared and _jaccard(a.words, b.words) >= TITLE_NEAR):
        return "identifiers " + ", ".join(sorted(shared)[:3])
    return None


def _finding(a: _Doc, b: _Doc) -> str | None:
    ids, refs = a.findings & b.findings, a.refs & b.refs
    if ids and refs:
        return f"finding {', '.join(sorted(ids))} (#{', #'.join(sorted(refs, key=int))})"
    return None


def _theme(a: _Doc, b: _Doc) -> str | None:
    if a.theme and a.theme == b.theme and _jaccard(a.words, b.words) >= TITLE_NEAR:
        return f"theme {a.theme}, title {_jaccard(a.words, b.words):.2f}"
    return None


# ------------------------------------------------------------------- engine


def _distinct(judgements: Judgements) -> set[frozenset[str]]:
    """`distinct_from`, read symmetrically: either side's word silences the pair."""
    return {
        frozenset((key, other)) for key, j in judgements.issues.items() for other in j.distinct_from
    }


def _components(pairs: list[Pair]) -> list[CandidateGroup]:
    parent: dict[str, str] = {}

    def find(k: str) -> str:
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for p in pairs:
        parent[find(p.a)] = find(p.b)
    members: dict[str, list[Pair]] = {}
    for p in pairs:
        members.setdefault(find(p.a), []).append(p)
    groups = [
        CandidateGroup(
            keys=tuple(sorted({k for p in ps for k in (p.a, p.b)})),
            pairs=tuple(sorted(ps, key=lambda p: (p.a, p.b))),
        )
        for ps in members.values()
    ]
    return sorted(groups, key=lambda g: g.keys[0])


def candidates(facts: Facts, judgements: Judgements) -> list[CandidateGroup]:
    """Candidate duplicate groups among the open issues of *facts* (spec §3.B).

    The universe is the open issues minus every one judged `duplicate_of` anything;
    a pair either side lists in `distinct_from` is skipped.
    """
    universe = [
        i
        for i in facts.issues
        if i.state == "open"
        and not (judgements.issues.get(i.key) and judgements.issues[i.key].duplicate_of)
    ]
    modules: set[str] = set()
    parsed: dict[str, set[str]] = {}
    for issue in universe:
        idents: set[str] = set()
        for tok in _code_tokens(_text(issue)):
            leaves, mods = _split(tok)
            idents |= leaves
            modules |= mods
        parsed[issue.key] = idents
    df = Counter(s for ss in parsed.values() for s in ss)

    docs = []
    for issue in universe:
        judged = judgements.issues.get(issue.key)
        docs.append(
            _Doc(
                key=issue.key,
                title=issue.title,
                words=_words(issue.title),
                idents=frozenset(parsed[issue.key]),
                findings=frozenset(f.lower() for f in _FINDING.findall(issue.body)),
                refs=frozenset(_REF.findall(issue.body)),
                theme=theme_key(judged.theme) if judged else "",
            )
        )
    docs.sort(key=lambda d: d.key)

    skip = _distinct(judgements)
    known_modules = frozenset(modules)
    pairs: list[Pair] = []
    for a, b in itertools.combinations(docs, 2):
        if frozenset((a.key, b.key)) in skip:
            continue
        found = (_title(a, b), _identifiers(a, b, df, known_modules), _finding(a, b), _theme(a, b))
        reasons = tuple(r for r in found if r)
        if reasons:
            pairs.append(Pair(a.key, b.key, reasons))
    return _components(pairs)
