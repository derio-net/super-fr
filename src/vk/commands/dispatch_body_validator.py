"""Validator for Issue bodies produced by vk dispatch.

Fail-loud: any missing required section or wrong dependency format
raises BodyValidationError with an actionable message.
"""

from __future__ import annotations


class BodyValidationError(ValueError):
    """Raised when a generated Issue body fails the dispatch contract."""


_REQUIRED_SECTIONS = ("## Instruction", "## Workspace", "## Dependencies")
_NONE_LITERAL = "None — no blocking phases."


def validate_issue_body(body: str, phase_number: int) -> None:
    """Raise BodyValidationError if body is not bridge-compatible.

    The ## Dependencies section must contain EITHER the 'None — no blocking phases.'
    literal OR one or more '- Blocked by #N' dash-prefixed lines. Any non-dash-prefixed
    'Blocked by #N' line is a hard fail (frank-hextra regression guard).
    """
    for section in _REQUIRED_SECTIONS:
        if section not in body:
            raise BodyValidationError(
                f"Generated body missing required section '{section}'. "
                f"The VK Issue Bridge will fail to parse this Issue. "
                f"Fix: investigate _build_issue_body in dispatch_cmd.py."
            )

    deps_idx = body.index("## Dependencies")
    deps_block = body[deps_idx:]
    # Lines strictly inside the section (after the '## Dependencies' header line).
    section_body = deps_block.split("\n", 1)[1] if "\n" in deps_block else ""

    # Hard guard: undashed 'Blocked by #N' lines are the Frank-hextra failure mode.
    for ln in section_body.splitlines():
        stripped = ln.strip()
        if stripped.startswith("Blocked by #") and not stripped.startswith("- Blocked by #"):
            raise BodyValidationError(
                f"Phase {phase_number}: '## Dependencies' contains a non-dash-prefixed "
                f"'Blocked by #N' line: {ln!r}. The bridge's dep-gating regex requires "
                f"the dash (i.e. '- Blocked by #N'). "
                f"Fix: investigate _build_issue_body in dispatch_cmd.py."
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
