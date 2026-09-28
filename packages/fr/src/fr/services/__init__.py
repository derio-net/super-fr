"""The forge / ci / tracking services a repo declares in
`.devcontainer/fr-profiles.yaml` (spec 2026-09-28-fr-profiles-services).

`resolve.resolve_services` is the only reader of the three services;
`fr.isolation.types.profiles_config` stays the raw reader it is.
"""

from fr.services.model import ServicesError  # noqa: E402
from fr.services.require import TrackerRequiredError, require_tracker  # noqa: E402

__all__ = ["ServicesError", "TrackerRequiredError", "require_tracker"]
