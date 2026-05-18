"""Lifecycle hook — invokes `VK_LIFECYCLE_HOOK_SCRIPT` on phase transitions.

The bridge is observability-first: when a phase advances (e.g. `vk-ready`
→ `in-progress`), an operator-configured script is called with
`(issue_url, transition)`. Wire this to Slack / a status board / etc.

Failure modes:
  - Env var unset → no-op.
  - Script missing / not executable / non-zero exit / timeout → warn,
    swallow. The bridge survives even when the notification chain
    crumbles — dispatch is the load-bearing path, not lifecycle.

`lifecycle_hook` is kept as a back-compat alias for the Phase 3 stub
callers in `dispatch` / `pr_state`. New code should use
`invoke_lifecycle_hook` for clarity.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Literal

__all__ = ["LifecycleState", "invoke_lifecycle_hook", "lifecycle_hook"]

logger = logging.getLogger(__name__)


# Closed enum of the transitions a hook script will see. Pinned at the
# type level so a typo in a dispatch / pr_state call is a static error.
LifecycleState = Literal["in-progress", "in-review", "done"]

# Hard ceiling on hook duration. Operators wire lifecycle scripts to
# remote services (Slack, dashboards) — a hung HTTP call must not stall
# the bridge tick. 30 s is generous for any reasonable notifier.
_HOOK_TIMEOUT_SEC = 30


def invoke_lifecycle_hook(issue_url: str, transition: LifecycleState) -> None:
    """Run `$VK_LIFECYCLE_HOOK_SCRIPT issue_url transition` if configured.

    The call is synchronous (so cron-time logging stays linear) but
    bounded by `_HOOK_TIMEOUT_SEC`. Every plausible failure — missing
    env, missing script, non-zero exit, timeout — is logged at WARNING
    and swallowed: the bridge must survive a broken notifier.
    """
    script = os.environ.get("VK_LIFECYCLE_HOOK_SCRIPT")
    if not script:
        return
    try:
        result = subprocess.run(
            [script, issue_url, transition],
            check=False,
            timeout=_HOOK_TIMEOUT_SEC,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.warning(
                "lifecycle hook %s exited %d: %s",
                script,
                result.returncode,
                (result.stderr or "").strip(),
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError, OSError) as e:
        logger.warning("lifecycle hook %s failed: %s", script, e)


def lifecycle_hook(issue_url: str, state: LifecycleState) -> None:
    """Back-compat alias of `invoke_lifecycle_hook`.

    Phase 3 introduced this as a stub on a different signature noun
    (`state` vs `transition`). Phase 4 unifies the implementation but
    keeps both names so callers from the Phase 3 churn don't break.
    """
    invoke_lifecycle_hook(issue_url, state)
