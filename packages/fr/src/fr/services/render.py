"""The text of the three service blocks (spec 2026-09-28-fr-profiles-services
§3.A) — ONE renderer for every writer of the v2 shape: the 1 -> 2 migration
(`fr.artifacts.profiles_services`) and `fr init scaffold`.

Text, not `yaml.safe_dump`: both writers append to a file an operator owns,
keep every other byte of it, and must match its line endings.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

import yaml

SERVICE_ORDER: tuple[str, ...] = ("forge", "ci", "tracking")


def _scalar(value: str) -> str:
    """`value` as a YAML scalar — plain when YAML reads it back unchanged,
    else double-quoted (a JSON string is a valid YAML double-quoted scalar)."""
    plain = value and value == value.strip() and "#" not in value and ": " not in value
    if plain:
        try:
            if yaml.safe_load(value) == value:
                return value
        except yaml.YAMLError:
            pass
    return json.dumps(value)


def render_services(
    services: Mapping[str, Mapping[str, str]],
    *,
    newline: str = "\n",
) -> str:
    """The `forge:` / `ci:` / `tracking:` blocks, in that order, each key on its
    own two-space-indented line, `type` first. `services` maps a service name to
    its keys; a service it does not name is not written."""
    unknown = set(services) - set(SERVICE_ORDER)
    if unknown:
        raise ValueError(f"unknown service(s): {', '.join(sorted(unknown))}")
    lines: list[str] = []
    for name in SERVICE_ORDER:
        if name not in services:
            continue
        keys = services[name]
        lines.append(f"{name}:")
        ordered = (
            ["type", *sorted(k for k in keys if k != "type")] if "type" in keys else sorted(keys)
        )
        for key in ordered:
            lines.append(f"  {key}: {_scalar(keys[key])}")
    return "".join(line + newline for line in lines)
