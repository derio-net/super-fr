"""Pushgateway metrics for the live bridge.

The bridge daemon emits three Prometheus metrics per tick:

  - `willikins_vk_bridge_sync_total` (counter, no labels) — one increment
    per VK card successfully synced (newly dispatched or dedup-stamped).
  - `willikins_vk_bridge_failure_total{reason="<reason>"}` (counter) —
    one increment per dispatch failure; `reason` is a short
    machine-readable token (`unknown_repo`, `mcp_error`, etc.).
  - `willikins_heartbeat_last_success_timestamp` (gauge) — Unix
    timestamp pushed at the end of every tick so external monitors
    can alert on staleness.

Pushgateway URL comes from `PUSHGATEWAY_URL`; default is the live
in-cluster endpoint. Every push uses `urllib.request` (stdlib — no
external dependency) and swallows network errors so a Pushgateway
outage cannot break a tick.
"""

from __future__ import annotations

import logging
import os
import time
import urllib.error
import urllib.request

__all__ = ["push_failure_total", "push_heartbeat", "push_sync_total"]

logger = logging.getLogger(__name__)

_DEFAULT_PUSHGATEWAY = "http://pushgateway.monitoring.svc.cluster.local:9091"
_JOB_NAME = "vk_issue_bridge"


def _pushgateway_url() -> str:
    """Read the gateway URL at call time so config changes propagate."""
    return os.environ.get("PUSHGATEWAY_URL", _DEFAULT_PUSHGATEWAY)


def _push(text: str) -> None:
    """POST raw Prometheus exposition text to Pushgateway under our job."""
    url = f"{_pushgateway_url()}/metrics/job/{_JOB_NAME}"
    try:
        req = urllib.request.Request(
            url,
            data=text.encode(),
            method="POST",
            headers={"Content-Type": "text/plain"},
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        # Network outages must not block dispatch. Logic bugs in our
        # exposition formatting (TypeError, ValueError) deliberately
        # propagate so tests catch them — they're not transient.
        logger.warning("pushgateway push failed: %s", e)


def push_sync_total() -> None:
    """One increment per successfully-synced VK card."""
    _push("# TYPE willikins_vk_bridge_sync_total counter\nwillikins_vk_bridge_sync_total 1\n")


def push_failure_total(*, reason: str) -> None:
    """One increment per dispatch failure, with a short reason token."""
    _push(
        "# TYPE willikins_vk_bridge_failure_total counter\n"
        f'willikins_vk_bridge_failure_total{{reason="{reason}"}} 1\n'
    )


def push_heartbeat() -> None:
    """End-of-tick liveness gauge — Unix epoch seconds."""
    ts = int(time.time())
    _push(
        "# TYPE willikins_heartbeat_last_success_timestamp gauge\n"
        "# HELP willikins_heartbeat_last_success_timestamp "
        "Unix timestamp of last successful run\n"
        f"willikins_heartbeat_last_success_timestamp {ts}\n"
    )
