"""Resolution (spec §3.B)."""

from __future__ import annotations

from pathlib import Path

from fr.isolation.types import profiles_config
from fr.services.model import ResolvedService, Services


def resolve_services(repo_root: Path) -> Services:
    config = profiles_config(repo_root)
    return Services(
        forge=ResolvedService(type=config["backend"], host=config.get("host"), source="legacy")
    )
