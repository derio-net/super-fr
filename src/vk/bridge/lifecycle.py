"""Lifecycle hook integration point.

Phase 3 adds the stub so dispatch / pr_state can call through without
worrying about the env-var branching. Phase 4 fleshes out the actual
subprocess invocation per spec §D5.

The hook script is invoked with `(issue_url, state)` where `state` is
one of `"in-progress"`, `"in-review"`, `"done"` — operators wire this
to external systems (Slack notifications, dashboards, etc.).
"""

from __future__ import annotations

import logging
import os

__all__ = ["lifecycle_hook"]

logger = logging.getLogger(__name__)


def lifecycle_hook(issue_url: str, state: str) -> None:
    """Invoke the lifecycle hook script if VK_LIFECYCLE_HOOK_SCRIPT is set.

    No-op when the env var is unset. Phase 4 implements the actual
    subprocess call + error handling per D5.
    """
    script = os.environ.get("VK_LIFECYCLE_HOOK_SCRIPT")
    if not script:
        return
    # Phase 4 fleshes this out. Logging the call now keeps the hook
    # discoverable in cron logs even before the implementation lands.
    logger.debug(
        "lifecycle_hook: stub (Phase 4 wires script=%s, issue=%s, state=%s)",
        script,
        issue_url,
        state,
    )
