"""The write-path gate for tracking (spec 2026-09-28-fr-profiles-services R6).

`require_tracker` resolves STRICTLY: a write or refusal path must never fall
back to "has a tracker" because the `tracking:` block is malformed. (Lenient
resolution is only for the `fr._hosts` forge consumers that promise never to
raise.)
"""

from __future__ import annotations

from pathlib import Path

from fr.services.model import ServicesError
from fr.services.resolve import resolve_services


class TrackerRequiredError(ServicesError):
    """The repo declares `tracking: {type: none}`; the command files issues."""


def require_tracker(repo_root: Path) -> None:
    """Raise `TrackerRequiredError` when *repo_root* has no issue tracker, or
    `ServicesError` when its services declaration is unreadable/invalid."""
    if resolve_services(repo_root).tracking.type == "none":
        raise TrackerRequiredError(
            "this repo declares `tracking: {type: none}` in "
            ".devcontainer/fr-profiles.yaml — there is no issue tracker to write "
            "to. Declare a tracker there to use this command."
        )
