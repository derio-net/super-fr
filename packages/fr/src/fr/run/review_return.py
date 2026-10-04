"""What a phase reviewer returned, read back out of its final message (spec
2026-10-02-opencode-observe-2 §E, R7).

A reviewer's return (`fr.run.observed.ChildDispatch.returned`) is the evidence
the orchestrator's journal is checked against. Pure text in, text out: no I/O,
no harness.

The reviewer ends its return with a fenced ```review-findings block, each line
`id | in/out | summary`, or the single line `none`. The fence is named
`review-findings` so it is never confused with the step's DERIVED `findings`
evidence (the closed-finding ids fr records at resolve).
"""

from __future__ import annotations

import re

FENCE = "review-findings"

FINDING_ID_RE = re.compile(r"^p[1-9][0-9]*[a-z]?-r[1-9][0-9]*$")
"""The brief-prescribed id: `p<N>-r<k>`, or `p<N><letter>-r<k>` when several
reviewers share a phase (one letter each, assigned in the dispatch prompt)."""

_BLOCK_RE = re.compile(
    rf"^[ \t]*```{FENCE}[ \t]*\r?\n(.*?)^[ \t]*```[ \t]*$", re.DOTALL | re.MULTILINE
)


class ReviewFindingsBlockError(ValueError):
    """A review-findings block fr cannot read: empty, a malformed line, or an
    id that is not the brief's `p<N>(<letter>)?-r<k>`."""


def parse_review_findings(text: str) -> list[tuple[str, str, str]] | None:
    """The `(id, scope, summary)` rows of the LAST ```review-findings block in
    `text` — `[]` for the single line `none`, `None` when the text carries no
    block. Raises `ReviewFindingsBlockError` naming the first line it cannot
    read."""
    blocks = list(_BLOCK_RE.finditer(text))
    if not blocks:
        return None
    lines = [line.strip() for line in blocks[-1].group(1).splitlines() if line.strip()]
    if not lines:
        raise ReviewFindingsBlockError(
            f"{FENCE} block is empty — one line per finding, or the single line `none`"
        )
    if lines == ["none"]:
        return []
    rows: list[tuple[str, str, str]] = []
    for line in lines:
        parts = [part.strip() for part in line.split("|", 2)]
        if len(parts) != 3 or parts[1] not in ("in", "out") or not parts[2]:
            raise ReviewFindingsBlockError(
                f"{FENCE} block line {line!r} is not `<id> | in|out | <summary>`"
            )
        if FINDING_ID_RE.match(parts[0]) is None:
            raise ReviewFindingsBlockError(
                f"{FENCE} block id {parts[0]!r} is not the brief's p<N>-r<k> "
                "(or p<N><letter>-r<k> with several reviewers)"
            )
        if any(parts[0] == row[0] for row in rows):
            raise ReviewFindingsBlockError(
                f"{FENCE} block lists {parts[0]!r} more than once — one line per finding"
            )
        rows.append((parts[0], parts[1], parts[2]))
    return rows


def review_findings_rule(phase: int) -> str:
    """What a review-phase brief tells its reviewer to end its return with
    (spec §E, R7): the block `parse_review_findings` reads, ids prescribed.
    The orchestrator puts this text into the reviewer's prompt verbatim."""
    return (
        f"End your return with a fenced {FENCE} block, one line per finding, "
        f"`<id> | in|out | <one-line summary>`, ids p{phase}-r<k> (k from 1) — or, "
        f"when the orchestrator dispatched several reviewers, p{phase}a-r<k>, "
        f"p{phase}b-r<k>, ... with the letter your dispatch prompt gives you — or the "
        "single line `none` when you raised nothing. `in` = this change is wrong, "
        "incomplete or worse than it needs to be; `out` = true, but not caused by this "
        "change. fr refuses the review-phase resolve while any returned id is missing "
        f"from the plan journal for phase {phase} or a later phase, or carries another "
        "scope there:\n"
        f"```{FENCE}\np{phase}-r1 | in | <one-line summary>\n```"
    )
