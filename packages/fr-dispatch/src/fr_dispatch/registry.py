"""Runner registry — the `fr.runners` entry-point group.

Adapters register their Runner factory under a short name; `fr apply
--to <name>` resolves through here. The VK adapter registers `vk`; a
future GitHub-Actions runner registers `gha`. Names feed the
`runner:<name>` label template, so they pass through the same bounded
machinery as plan/spec slugs.
"""

from __future__ import annotations

from importlib.metadata import entry_points

GROUP = "fr.runners"


def available_runners() -> dict[str, object]:
    """Registered runner names → entry points (unloaded)."""
    return {ep.name: ep for ep in entry_points(group=GROUP)}


def runner_names() -> list[str]:
    return sorted(available_runners())
