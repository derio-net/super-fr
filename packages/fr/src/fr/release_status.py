"""What still waits on a post-merge gate since the last final release (spec
2026-10-14-exit-gates R20, R21, §G).

The gate ledger is the merged PRs' labels (`fr.labels.held_gates`): a PR merged since
the last FINAL tag that carries `gate:tester` or `gate:devops` without the matching
`gate:<g>-passed` waits. `scripts/release.py` reads the forge itself and hands the
facts to `fr release status --from-json` (no credential), whose JSON says whether it cuts
a release candidate (anything waits, and something installable changed: `release.py`
checks that) or the final (nothing does).

A merge queue's hold (spec 2026-11-19-wave-merge-queue R17, R18) rides the same facts: a
repo is held while its hold is `open` and was refreshed within 24 hours (`hold_verdict`); an
older `open` hold is ignored with a warning, and `drained` and `cleared` holds never hold.

Pure given its inputs: the forge is a two-method protocol, the owed rows a callable,
and the tag and its date are passed in. `fr.commands.release_cmd` wires the real ones.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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


HOLD_FRESH = timedelta(hours=24)
"""R18: an `open` hold refreshed longer ago than this holds no release."""


@dataclass(frozen=True)
class Held:
    """A release held by a merge queue's `open` hold (R18): the scope and wave that hold it
    and when it was last refreshed (None: the hold names no time, which holds)."""

    scope: str
    wave: int | None
    refreshed: str | None

    def to_json(self) -> dict[str, Any]:
        return {"scope": self.scope, "wave": self.wave, "refreshed": self.refreshed}

    def line(self) -> str:
        wave = "between waves" if self.wave is None else f"wave {self.wave}"
        return (
            f"held: the merge queue of scope {self.scope} ({wave}) has the release held "
            f"(hold open, refreshed {self.refreshed or 'at an unknown time'}); it is released "
            "when the queue drains"
        )


@dataclass(frozen=True)
class ReleaseStatus:
    repo: str
    last_final: str | None
    since: str | None
    waiting: tuple[Waiting, ...]
    held: Held | None = None
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "repo": self.repo,
            "last_final": self.last_final,
            "since": self.since,
            "waiting": [w.to_json() for w in self.waiting],
            "held": None if self.held is None else self.held.to_json(),
            "warnings": list(self.warnings),
        }


def hold_verdict(
    hold: Mapping[str, Any] | None, now: datetime | None = None
) -> tuple[Held | None, tuple[str, ...]]:
    """R18: whether *hold* (`state`, `scope`, `wave`, `refreshed`, as `release.py` reads the
    ref) holds a release, and the warnings. Only `open` holds, and an `open` one refreshed
    more than 24 hours ago is ignored, warned and named. A missing or unreadable refresh
    time holds (fail closed); `drained`, `cleared` and no hold never do."""
    if not hold or hold.get("state") != "open":
        return None, ()
    now = now or datetime.now(UTC)
    scope = str(hold.get("scope") or "?")
    wave = hold.get("wave")
    refreshed = hold.get("refreshed")
    when: datetime | None = None
    if refreshed:
        try:
            when = _when(str(refreshed))
        except ValueError:
            when = None
    if when is not None and now - when > HOLD_FRESH:
        return None, (
            f"the merge queue hold of scope {scope} was last refreshed {refreshed}, more than "
            "24 hours ago: ignored, so it holds no release; clear it with "
            "`git push origin --delete fr-hold/queue`",
        )
    return Held(scope, wave if isinstance(wave, int) else None,
                str(refreshed) if refreshed else None), ()  # fmt: skip


def _when(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def release_status(
    *,
    repo: str,
    last_final: str | None,
    since: str | None,
    forge: ReleaseForge,
    owed_rows: Callable[[str], OwedRows | None],
    hold: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> ReleaseStatus:
    """Every PR merged after *since* (the last final tag's commit time; None: every
    merged PR) whose labels hold a post-merge gate, oldest merge first. Only PRs merged
    after *since* have their labels read. *hold* is the repo's merge queue hold, if any."""
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
    held, warnings = hold_verdict(hold, now)
    return ReleaseStatus(repo, last_final, since, tuple(waiting), held, warnings)
