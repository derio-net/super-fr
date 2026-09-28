"""Service model (spec §3.A)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Source = Literal["declared", "default", "legacy"]


@dataclass(frozen=True)
class ResolvedService:
    type: str
    host: str | None
    source: Source


@dataclass(frozen=True)
class Services:
    forge: ResolvedService
