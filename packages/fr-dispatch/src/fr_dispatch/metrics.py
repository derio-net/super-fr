"""Pushgateway metrics for the dispatch tick.

The daemon emits three Prometheus metrics per tick, under
adapter-supplied names (`MetricsPusher(namespace=..., job=...)`):

- `<namespace>_sync_total` (counter, no labels) — one increment per
  phase successfully handed to the runner.
- `<namespace>_failure_total{reason="<reason>"}` (counter) — one per
  accumulated failure; generic reason kinds may be aliased to an
  adapter's historical wire values via `reason_aliases`.
- the heartbeat gauge (default `<namespace>_heartbeat_last_success_timestamp`)
  — Unix timestamp stamped at end of tick, the liveness signal.

Network outages never block dispatch — pushes log-and-swallow transport
errors; exposition formatting bugs propagate so tests catch them.
"""

from __future__ import annotations

import logging
import os
import time
import urllib.error
import urllib.request

__all__ = ["MetricsPusher", "NullMetrics"]

logger = logging.getLogger(__name__)

_DEFAULT_PUSHGATEWAY = "http://pushgateway.monitoring.svc.cluster.local:9091"


def _pushgateway_url() -> str:
    """Read the gateway URL at call time so config changes propagate."""
    return os.environ.get("PUSHGATEWAY_URL", _DEFAULT_PUSHGATEWAY)


def _push(text: str, job: str) -> None:
    """POST raw Prometheus exposition text to Pushgateway under `job`."""
    url = f"{_pushgateway_url()}/metrics/job/{job}"
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


class MetricsPusher:
    """Adapter-named Pushgateway emitter (2026-06-06 split design).

    The metric namespace and job name are runner-supplied so this
    framework carries no adapter strings; an adapter constructs the
    pusher with its historical names (see `fr_vk.runner` for the
    constants that preserve the legacy wire format byte-for-byte).
    """

    def __init__(
        self,
        *,
        namespace: str,
        job: str,
        heartbeat_metric: str | None = None,
        reason_aliases: dict[str, str] | None = None,
    ) -> None:
        self.namespace = namespace
        self.job = job
        self.heartbeat_metric = heartbeat_metric or f"{namespace}_heartbeat_last_success_timestamp"
        # tick emits GENERIC reason kinds (backend_error, preflight, …);
        # adapters may alias them to their historical wire values so
        # existing dashboards/alerts keep matching.
        self.reason_aliases = reason_aliases or {}

    def push_sync_total(self) -> None:
        m = f"{self.namespace}_sync_total"
        _push(f"# TYPE {m} counter\n{m} 1\n", self.job)

    def push_failure_total(self, *, reason: str) -> None:
        reason = self.reason_aliases.get(reason, reason)
        m = f"{self.namespace}_failure_total"
        _push(
            f"# TYPE {m} counter\n" + f'{m}{{reason="{reason}"}} 1\n',
            self.job,
        )

    def push_heartbeat(self) -> None:
        m = self.heartbeat_metric
        _push(
            f"# TYPE {m} gauge\n"
            f"# HELP {m} Unix timestamp of last successful run\n"
            f"{m} {int(time.time())}\n",
            self.job,
        )


class NullMetrics(MetricsPusher):
    """No-op sink — tick's default when the runner supplies no metrics."""

    def __init__(self) -> None:  # noqa: D107
        super().__init__(namespace="null", job="null")

    def push_sync_total(self) -> None:  # pragma: no cover - trivial
        pass

    def push_failure_total(self, *, reason: str) -> None:  # pragma: no cover
        pass

    def push_heartbeat(self) -> None:  # pragma: no cover
        pass
