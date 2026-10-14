"""What still waits on a post-merge gate since the last final release (spec
2026-10-14-exit-gates R20, R21, §G).

The gate ledger is the merged PRs' labels (`fr.labels.held_gates`): a PR merged since
the last FINAL tag that carries `gate:tester` or `gate:devops` without the matching
`gate:<g>-passed` waits. `scripts/release.py` reads this module's JSON
(`fr release status --json`) and cuts a release candidate while anything waits, the
final once nothing does.

Pure given its inputs: the forge is a two-method protocol, the owed rows a callable,
and the tag and its date are passed in. `fr.commands.release_cmd` wires the real ones.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from fr.labels import held_gates

SCHEMA = 1
"""The `--json` document's version; `release.py` reads `waiting` from schema 1."""

FINAL_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
"""A final release tag. An RC tag (`vX.Y.Z-rc.N`) is never "the last final"."""

OwedRows = dict[str, tuple[str, ...]]


def last_final_tag(tags: Iterable[str]) -> str | None:
    """The highest `vX.Y.Z` among *tags*, by version; None when there is none."""
    finals = [(tuple(int(g) for g in m.groups()), t) for t in tags if (m := FINAL_TAG_RE.match(t))]
    return max(finals)[1] if finals else None


class ReleaseForge(Protocol):
    def merged_prs(self) -> list[dict[str, Any]]:
        """Merged PRs (`number, title, url, mergedAt, headRefName`), any order."""
        ...

    def labels(self, number: int) -> list[str]:
        """The label names of merged PR *number*."""
        ...


@dataclass(frozen=True)
class Waiting:
    """A merged PR an unpassed post-merge gate still holds. `owed_rows` maps each held
    gate to its rows not yet `walked`; None when the rows could not be read."""

    number: int
    title: str
    url: str
    merged_at: str
    gates: tuple[str, ...]
    owed_rows: OwedRows | None

    def to_json(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "title": self.title,
            "url": self.url,
            "merged_at": self.merged_at,
            "gates": list(self.gates),
            "owed_rows": (
                None
                if self.owed_rows is None
                else {g: list(rows) for g, rows in self.owed_rows.items()}
            ),
        }


@dataclass(frozen=True)
class ReleaseStatus:
    repo: str
    last_final: str | None
    since: str | None
    waiting: tuple[Waiting, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "repo": self.repo,
            "last_final": self.last_final,
            "since": self.since,
            "waiting": [w.to_json() for w in self.waiting],
        }


def _when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def release_status(
    *,
    repo: str,
    last_final: str | None,
    since: str | None,
    forge: ReleaseForge,
    owed_rows: Callable[[str], OwedRows | None],
) -> ReleaseStatus:
    """Every PR merged after *since* (the last final tag's commit time; None: every
    merged PR) whose labels hold a post-merge gate, oldest merge first. Only PRs merged
    after *since* have their labels read."""
    after = _when(since) if since else None
    recent = [
        p
        for p in forge.merged_prs()
        if p.get("mergedAt") and (after is None or _when(str(p["mergedAt"])) > after)
    ]
    waiting: list[Waiting] = []
    for pr in sorted(recent, key=lambda p: _when(str(p["mergedAt"]))):
        number = int(pr["number"])
        gates = tuple(sorted(held_gates(forge.labels(number))))
        if not gates:
            continue
        rows = owed_rows(str(pr.get("headRefName") or ""))
        waiting.append(
            Waiting(
                number=number,
                title=str(pr.get("title") or ""),
                url=str(pr.get("url") or ""),
                merged_at=str(pr["mergedAt"]),
                gates=gates,
                owed_rows=None if rows is None else {g: tuple(rows.get(g, ())) for g in gates},
            )
        )
    return ReleaseStatus(repo, last_final, since, tuple(waiting))
