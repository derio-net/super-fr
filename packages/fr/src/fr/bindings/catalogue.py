"""The provider catalogue: lineage and price, never availability (spec
2026-10-06-model-binding-churn §A, R3).

`opencode models <provider> --verbose` prints, per model, a ``provider/id``
header line and then a JSON object carrying ``family``, ``release_date``,
``cost`` and ``capabilities.toolcall``. Its ``status`` field is NOT read
anywhere in this package: a model can stay in the catalogue marked
``"status": "active"`` long after the provider stops serving it (#591), so
availability comes from a live probe (`fr.bindings.probe`) or not at all.

`SnapshotStore` keeps each bound model's last-known entry under
``$HOME/.cache/fr/models/``, so a model that later LEAVES the catalogue can
still be reasoned about (its family, its price).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


def models_cache_dir() -> Path:
    """``$HOME/.cache/fr/models`` — where snapshots and the probe cache live.

    HOME-based (not XDG) to match the spec's stated path; `fr.usage` and
    `fr.triage` keep their caches under ``$HOME/.cache/fr/`` the same way.
    ``FR_MODELS_CACHE_DIR`` overrides it, which the test suite sets so no test
    writes an operator's real cache."""
    override = os.environ.get("FR_MODELS_CACHE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "fr" / "models"


@dataclass(frozen=True)
class CatalogueEntry:
    """One model's lineage and price. ``price`` is ``cost.input + cost.output``,
    or ``None`` when the catalogue carries no cost."""

    id: str
    provider: str
    family: str | None
    release_date: str | None
    price: float | None
    toolcall: bool


_HEADER = re.compile(r"^([A-Za-z0-9._-]+)/(\S+)$")


def _entry(header: str, body: str) -> CatalogueEntry | None:
    match = _HEADER.match(header)
    if match is None:
        return None
    try:
        raw = json.loads(body)
    except ValueError:
        return None
    if not isinstance(raw, dict):
        return None
    cost = raw.get("cost")
    price: float | None = None
    if isinstance(cost, dict) and "input" in cost and "output" in cost:
        try:
            price = float(cost["input"]) + float(cost["output"])
        except (TypeError, ValueError):
            price = None
    caps = raw.get("capabilities")
    family = raw.get("family")
    released = raw.get("release_date")
    return CatalogueEntry(
        id=header,
        provider=match.group(1),
        family=family if isinstance(family, str) and family else None,
        release_date=released if isinstance(released, str) and released else None,
        price=price,
        toolcall=bool(isinstance(caps, dict) and caps.get("toolcall")),
    )


def parse_catalogue(text: str) -> tuple[list[CatalogueEntry], int]:
    """Parse ``opencode models <provider> --verbose`` output.

    Returns ``(entries, skipped)``. A block whose JSON does not parse is
    skipped and counted — the parse never raises, because OpenCode's CLI is
    not versioned for fr (spec Risks)."""
    blocks: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if _HEADER.match(line.strip()) and not line.startswith((" ", "\t", "{", "}")):
            blocks.append((line.strip(), []))
        elif blocks:
            blocks[-1][1].append(line)
    entries: list[CatalogueEntry] = []
    skipped = 0
    for header, body in blocks:
        entry = _entry(header, "\n".join(body))
        if entry is None:
            skipped += 1
        else:
            entries.append(entry)
    return entries, skipped


def write_json_atomic(path: Path, data: object) -> None:
    """Write ``data`` as JSON through a sibling temp file and `os.replace`. A cache
    is never worth a crash: a read-only or missing HOME is swallowed, and no temp
    file is left behind."""
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        os.replace(tmp, path)
    except OSError:
        with contextlib.suppress(OSError):
            tmp.unlink()


def _opt_str(value: object) -> bool:
    return value is None or isinstance(value, str)


class SnapshotStore:
    """Last-known catalogue entry per model id, in one JSON file.

    A corrupt or missing file reads as empty, a field of the wrong type makes
    that one entry absent, and a failed write is swallowed: a snapshot is a
    convenience for reasoning about a vanished model, never a prerequisite."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def get(self, model_id: str) -> CatalogueEntry | None:
        raw = self._load().get(model_id)
        if not isinstance(raw, dict) or set(raw) != {f.name for f in fields(CatalogueEntry)}:
            return None
        price = raw["price"]
        if (
            not isinstance(raw["id"], str)
            or not isinstance(raw["provider"], str)
            or not _opt_str(raw["family"])
            or not _opt_str(raw["release_date"])
            or not isinstance(raw["toolcall"], bool)
            or not (
                price is None or (isinstance(price, int | float) and not isinstance(price, bool))
            )
        ):
            return None
        return CatalogueEntry(
            raw["id"],
            raw["provider"],
            raw["family"],
            raw["release_date"],
            None if price is None else float(price),
            raw["toolcall"],
        )

    def remember(self, entries: list[CatalogueEntry]) -> None:
        """Merge ``entries`` over what is stored; an id absent from them keeps
        its older snapshot."""
        if not entries:
            return
        data = self._load()
        for entry in entries:
            data[entry.id] = asdict(entry)
        write_json_atomic(self.path, data)
