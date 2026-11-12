"""Acceptance fragments (stub)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

FRAGMENTS_DIR = Path("docs/acceptance/features")


def parse_fragment(text: str, *, source: str) -> Any:
    raise NotImplementedError
