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

    Checks:
    - All required sections present.
    - Dependencies section contains either the 'None — no blocking phases.'
      literal (root phase) or one or more '- Blocked by #N' dash-prefixed lines.
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
    if _NONE_LITERAL in deps_block:
        return
    if "- Blocked by #" not in deps_block:
        raise BodyValidationError(
            f"Phase {phase_number} body's Dependencies section lacks "
            f"the required '- Blocked by #N' dash-prefixed line. "
            f"The bridge's dep-gating regex requires the dash. "
            f"Fix: investigate _build_issue_body in dispatch_cmd.py."
        )
