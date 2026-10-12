"""`pacing.json`: what the drive remembers between passes about the quota (spec
2026-10-12-quota-pacing R15).

It lives in the local state dir beside `facts.json` and is deliberately NOT in
`state_ref.REF_FILES`: a fresh or re-homed cloud session starts without it, and
so makes a full pass. A file fr cannot read is an empty state and a warning,
never a crash: pacing is an optimisation, and the pass it guards must still run.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fr.artifacts.atomic import write_text_atomic

PACING_FILE = "pacing.json"

_TIMES = ("full_at", "wait_until", "next_pass_at")


@dataclass(frozen=True)
class PacingState:
    # {repo: {probe path: ETag}} — the ETags of the last successful collect (R11).
    etags: dict[str, dict[str, str]] = field(default_factory=dict)
    full_at: datetime | None = None
    wait_until: datetime | None = None
    backoff: int = 0  # R4: consecutive secondary-limit responses
    next_pass_at: datetime | None = None  # R7: the essential-only stretch
    judgements_digest: str | None = None  # R9: of the last planned pass's judgements.yaml
    budget: dict[str, Any] | None = None  # the last budget read (R14's footer)


def _stamp(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def _parsed(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    when = datetime.fromisoformat(value)
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def _from_json(data: object) -> PacingState:
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    etags = data.get("etags", {})
    if not isinstance(etags, dict) or not all(
        isinstance(v, dict) and all(isinstance(e, str) for e in v.values()) for v in etags.values()
    ):
        raise ValueError("etags: expected {repo: {path: etag}}")
    backoff = data.get("backoff", 0)
    if not isinstance(backoff, int) or isinstance(backoff, bool):
        raise ValueError("backoff: expected an integer")
    digest = data.get("judgements_digest")
    budget = data.get("budget")
    return PacingState(
        etags={r: dict(v) for r, v in etags.items()},
        full_at=_parsed(data.get("full_at")),
        wait_until=_parsed(data.get("wait_until")),
        backoff=backoff,
        next_pass_at=_parsed(data.get("next_pass_at")),
        judgements_digest=digest if isinstance(digest, str) else None,
        budget=budget if isinstance(budget, dict) else None,
    )


def load(state_dir: Path) -> tuple[PacingState, str | None]:
    """The state in *state_dir* and a warning when the file was there but unusable."""
    path = state_dir / PACING_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return PacingState(), None
    except OSError as exc:
        return PacingState(), f"{path}: unreadable, starting from an empty pacing state ({exc})"
    try:
        return _from_json(json.loads(text)), None
    except (ValueError, TypeError) as exc:
        return PacingState(), f"{path}: not usable, starting from an empty pacing state ({exc})"


def save(state_dir: Path, state: PacingState) -> None:
    data = asdict(state)
    for key in _TIMES:
        data[key] = _stamp(getattr(state, key))
    state_dir.mkdir(parents=True, exist_ok=True)
    write_text_atomic(state_dir / PACING_FILE, json.dumps(data, indent=2, sort_keys=True) + "\n")
