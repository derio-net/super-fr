"""Validator for bridge-compatible Issue bodies.

Fail-loud: any missing required section or malformed dependency line
raises BodyValidationError with an actionable message.
"""

from __future__ import annotations


class BodyValidationError(ValueError):
    """Raised when a generated Issue body fails the bridge contract."""


_REQUIRED_SECTIONS = ("## Instruction", "## Workspace", "## Dependencies")
_NONE_LITERAL = "None — no blocking phases."


def validate_issue_body(body: str, phase_number: int) -> None:
    """Raise BodyValidationError if body is not bridge-compatible.

    The ## Dependencies section must contain EITHER the
    'None — no blocking phases.' literal OR one or more '- Blocked by #N'
    dash-prefixed lines. Any non-dash-prefixed 'Blocked by #N' line is a
    hard fail (the bridge's dep-gating regex requires the dash).

    ``phase_number`` is included in error messages to help locate the
    offending phase. Pass 0 for ad-hoc issues.
    """
    for section in _REQUIRED_SECTIONS:
        if section not in body:
            raise BodyValidationError(
                f"Generated body missing required section '{section}'. "
                f"The VK Issue Bridge will fail to parse this Issue."
            )

    deps_idx = body.index("## Dependencies")
    deps_block = body[deps_idx:]
    section_body = deps_block.split("\n", 1)[1] if "\n" in deps_block else ""

    for ln in section_body.splitlines():
        stripped = ln.strip()
        if stripped.startswith("Blocked by #") and not stripped.startswith("- Blocked by #"):
            raise BodyValidationError(
                f"Phase {phase_number}: '## Dependencies' contains a non-dash-prefixed "
                f"'Blocked by #N' line: {ln!r}. The bridge's dep-gating regex requires "
                f"the dash (i.e. '- Blocked by #N')."
            )

    if _NONE_LITERAL in deps_block:
        return

    dash_lines = [ln for ln in section_body.splitlines() if ln.startswith("- Blocked by #")]
    if not dash_lines:
        raise BodyValidationError(
            f"Phase {phase_number}: '## Dependencies' is empty or malformed. "
            f"It must contain either '{_NONE_LITERAL}' "
            f"or one or more '- Blocked by #N' lines."
        )
