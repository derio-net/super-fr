"""`fr settings init`'s text, generated from the model's field descriptions (spec R3).

Every key is present, commented out at its default, under a comment block stating the
allowed values, what the default does and what the non-default trades away. The prose
is each field's own `description=`, so the file cannot drift from the schema.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from fr.settings.model import PLACEHOLDERS, Settings

_PLAIN = re.compile(r"^[A-Za-z0-9_-]+$")


def _scalar(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    return str(value) if _PLAIN.match(str(value)) else json.dumps(str(value))


def _allowed(name: str, field: FieldInfo) -> str | None:
    extra = field.json_schema_extra
    if isinstance(extra, dict) and "allowed" in extra:
        return ", ".join(str(v) for v in extra["allowed"])  # type: ignore[union-attr]
    if name.endswith("_issue"):
        usable = PLACEHOLDERS if name == "with_issue" else PLACEHOLDERS - {"issue"}
        return "text using " + " ".join(f"{{{p}}}" for p in sorted(usable))
    if name == "schema_":
        return "1"
    return None


def _emit(model: type[BaseModel], instance: BaseModel, depth: int, out: list[str]) -> None:
    pad = "  " * depth
    for name, field in model.model_fields.items():
        value = getattr(instance, name)
        key = field.alias or name
        out.append("##")
        allowed = _allowed(name, field)
        if allowed is not None:
            out.append(f"## {pad}Allowed: {allowed}")
        for line in (field.description or "").splitlines():
            out.append(f"## {pad}{line}")
        if isinstance(value, BaseModel):
            out.append(f"#{pad}{key}:")
            _emit(type(value), value, depth + 1, out)
        else:
            out.append(f"#{pad}{key}: {_scalar(value)}")


QUIET_LIMITATION = (
    "Known limitation: a host whose fr predates quiet support (plan 3 of spec "
    "2026-11-04-repo-feature-settings) never looks for this switch, and writes its "
    "artifacts on the feature branch as under `repo`."
)
"""R23's known limitation, stated in the file and by `fr settings init --quiet`."""

QUIET_PROTECTION = (
    "The policy keys below are read from this branch (R2), so whoever can push `fr` can "
    "change them: give `fr` the same branch protection as the default branch."
)


def render_init(placement: str = "repo") -> str:
    """The commented defaults file: `.fr/settings.yaml`, or (quiet) the root
    `settings.yaml` of the `fr` branch, which says `placement: quiet` and nothing else."""
    if placement == "quiet":
        out = [
            "## fr settings for this repo's QUIET placement (spec "
            "2026-11-04-repo-feature-settings R2, R23).",
            "## This is the root settings.yaml of the orphan `fr` branch, read from origin/fr:",
            "## an edit has no effect until it is pushed there.",
            *(f"## {line}" for line in _wrap(QUIET_PROTECTION)),
            *(f"## {line}" for line in _wrap(QUIET_LIMITATION)),
            "## Every other key is commented out at its default; to change one, drop the single",
            "## leading `#` of its line (lines starting `##` are prose).",
        ]
    else:
        out = [
            "## fr settings for this repo (spec 2026-11-04-repo-feature-settings).",
            "## Read from the default branch: an edit has no effect until it lands there.",
            "## Every key is commented out at its default; to change one, drop the single leading",
            "## `#` of its line (lines starting `##` are prose).",
        ]
    _emit(Settings, Settings.model_validate({}), 0, out)
    if placement == "quiet":
        out = ["placement: quiet" if line == "#placement: repo" else line for line in out]
    return "\n".join(out) + "\n"


def _wrap(text: str, width: int = 84) -> list[str]:
    import textwrap

    return textwrap.wrap(text, width)
