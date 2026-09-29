"""What a reviewer returned, read back out of its final message (spec
2026-09-29-opencode-observe §D, R5 and R7).

A reviewer's return (`fr.run.observed.ChildDispatch.returned`) is the evidence
the orchestrator's record is checked against. Pure text in, text out: no I/O,
no harness. Two readers:

- `returned_coverage` — the `input-coverage` block of a spec reviewer's
  return, compared with the recorded review entry's by `coverage_divergence`;
- `parse_findings_block` — the trailing ```findings block a phase reviewer
  ends its return with, each line `id | in/out | summary`, or `none`.
"""

from __future__ import annotations

import re
import textwrap
from typing import Any

import yaml

_FENCED_COVERAGE_RE = re.compile(
    r"^([ \t]*)```input-coverage[ \t]*\r?\n.*?^\1```[ \t]*$", re.DOTALL | re.MULTILINE
)
_YAML_FENCE_RE = re.compile(r"^```ya?ml[ \t]*\r?\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)


def _review_body(document: Any) -> str | None:
    """The `body` of the `kind: review` journal entry of a parsed record."""
    if not isinstance(document, dict):
        return None
    journal = document.get("journal")
    if not isinstance(journal, list):
        return None
    for entry in journal:
        if isinstance(entry, dict) and entry.get("kind") == "review":
            body = entry.get("body")
            return body if isinstance(body, str) else None
    return None


def _parsed_review_body(text: str) -> str | None:
    """The review entry's body when `text` is a YAML record — as it stands, or
    inside a ```yaml fence."""
    candidates = [text, *(m.group(1) for m in _YAML_FENCE_RE.finditer(text))]
    for candidate in candidates:
        try:
            document = yaml.safe_load(candidate)
        except yaml.YAMLError:
            continue
        body = _review_body(document)
        if body is not None:
            return body
    return None


def _first_fenced_coverage(text: str) -> str | None:
    match = _FENCED_COVERAGE_RE.search(text)
    return textwrap.dedent(match.group(0)) if match is not None else None


def returned_coverage(text: str) -> str | None:
    """The fenced `input-coverage` block of a spec reviewer's return, fences
    included — or `None` when it carries none.

    The reviewer returns its step record as YAML (`fr-spec-reviewer.md` "What
    you return"), the block inside the `kind: review` entry's `body: |`
    literal, so the return is parsed and that body read: the same text the
    journal holds once the entry is recorded. A return that is not such a
    record falls back to the first fenced block found, dedented."""
    body = _parsed_review_body(text)
    if body is not None:
        return _first_fenced_coverage(body)
    return _first_fenced_coverage(text)


def _lines(block: str) -> list[str]:
    lines = [line.rstrip() for line in block.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def coverage_divergence(recorded: str, returned: str) -> str | None:
    """`None` when the two blocks are the same after normalising line endings
    and trailing whitespace; otherwise one line naming the first row where
    they differ, with both versions of it."""
    ours, theirs = _lines(recorded), _lines(returned)
    for n in range(max(len(ours), len(theirs))):
        a = ours[n] if n < len(ours) else None
        b = theirs[n] if n < len(theirs) else None
        if a != b:
            shown_a = "(no line)" if a is None else repr(a)
            shown_b = "(no line)" if b is None else repr(b)
            return f"line {n + 1} of the block: recorded {shown_a}, returned {shown_b}"
    return None


FINDING_ID_RE = re.compile(r"^p[1-9][0-9]*[a-z]?-r[1-9][0-9]*$")
"""The brief-prescribed id: `p<N>-r<k>`, or `p<N><letter>-r<k>` when several
reviewers share a phase (one letter each, assigned in the dispatch prompt)."""
_FINDINGS_BLOCK_RE = re.compile(
    r"^[ \t]*```findings[ \t]*\r?\n(.*?)^[ \t]*```[ \t]*$", re.DOTALL | re.MULTILINE
)


class FindingsBlockError(ValueError):
    """A findings block fr cannot read: a malformed line, or an id that is not
    the brief's `p<N>(<letter>)?-r<k>`."""


def parse_findings_block(text: str) -> list[tuple[str, str, str]] | None:
    """The `(id, scope, summary)` rows of the LAST ```findings block in `text`
    — `[]` for the single line `none`, `None` when the text carries no block.
    Raises `FindingsBlockError` naming the first line it cannot read."""
    blocks = list(_FINDINGS_BLOCK_RE.finditer(text))
    if not blocks:
        return None
    lines = [line.strip() for line in blocks[-1].group(1).splitlines() if line.strip()]
    if lines == ["none"]:
        return []
    rows: list[tuple[str, str, str]] = []
    for line in lines:
        parts = [part.strip() for part in line.split("|", 2)]
        if len(parts) != 3 or parts[1] not in ("in", "out") or not parts[2]:
            raise FindingsBlockError(
                f"findings block line {line!r} is not `<id> | in|out | <summary>`"
            )
        if FINDING_ID_RE.match(parts[0]) is None:
            raise FindingsBlockError(
                f"findings block id {parts[0]!r} is not the brief's p<N>-r<k> "
                "(or p<N><letter>-r<k> with several reviewers)"
            )
        rows.append((parts[0], parts[1], parts[2]))
    return rows


def findings_block_rule(phase: int) -> str:
    """What a review-phase brief tells its reviewer to end its return with
    (spec §D, R7): the block `parse_findings_block` reads, ids prescribed."""
    return (
        "End your return with a fenced findings block, one line per finding, "
        f"`<id> | in|out | <one-line summary>`, ids p{phase}-r<k> (k from 1) — or, "
        f"when the orchestrator dispatched several reviewers, p{phase}a-r<k>, "
        f"p{phase}b-r<k>, ... with the letter your dispatch prompt gives you — or the "
        "single line `none` when you raised nothing:\n"
        f"```findings\np{phase}-r1 | in | <summary>\n```\n"
        "fr refuses the review-phase resolve while any returned id is missing from the "
        "plan journal or carries another scope there."
    )
