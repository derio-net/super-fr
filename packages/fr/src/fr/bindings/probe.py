"""The live probe: does the provider still serve this model? (spec
2026-10-06-model-binding-churn §A, R2, R3)

A verdict is ``live``, ``dead`` or ``unknown`` (``unprobed`` is the health
layer's word for a harness that has no prober at all). ``dead`` needs POSITIVE
provider evidence — model-not-found or not-supported. Every other failure (a
timeout, a missing CLI, an auth error, a server error) is ``unknown``: warn and
carry on, never substitute on a guess.

Every subprocess call goes through ``run_opencode``, so a test (or a scenario's
stub ``opencode`` on PATH) replaces exactly one thing.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Literal, Protocol

from fr.bindings.catalogue import CatalogueEntry, models_cache_dir, parse_catalogue

Verdict = Literal["live", "dead", "unknown", "unprobed"]

PROBE_TIMEOUT_SECONDS = 60
PROBE_PROMPT = "Reply with exactly: OK"
CACHE_TTL_SECONDS = 6 * 3600

# The two phrasings a provider uses to say "I do not serve this model":
# OpenCode's own ProviderModelNotFoundError (the model left the catalogue) and
# the provider's "not supported" (it stayed listed, `"status": "active"`, and
# stopped answering — #591). Pinned by the captured fixtures in
# tests/fixtures/bindings/; if a provider rewords either, a dead model reads as
# `unknown` (a warning), never as a silent dispatch.
DEAD_PHRASES = ("providermodelnotfounderror", "model is not supported")

_HINT = re.compile(r"Did you mean:\s*([^\s?\"\\]+)")
_NOT_FOUND = re.compile(r"ProviderModelNotFoundError:[^\"\\\n]*")


@dataclass(frozen=True)
class ProbeResult:
    """``hint`` is the provider's own ``Did you mean: <id>`` (bare id, no
    provider prefix), when it gave one. ``at`` is the epoch the verdict was
    reached, which the cache ages against."""

    verdict: Verdict
    detail: str
    hint: str | None
    at: float


class Prober(Protocol):
    def probe(self, model: str) -> ProbeResult: ...

    def catalogue(self, provider: str) -> list[CatalogueEntry]: ...


def run_opencode(argv: list[str], *, cwd: Path, timeout: float) -> subprocess.CompletedProcess[str]:
    """THE subprocess seam. Stdin is closed: with it left open `opencode run`
    waits on it forever (observed capturing the fixtures)."""
    return subprocess.run(  # noqa: S603
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def _has_text_event(stdout: str) -> bool:
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "text":
            return True
    return False


def classify(stdout: str, stderr: str, returncode: int) -> ProbeResult:
    """Read one `opencode run` outcome. ``returncode`` is not evidence either
    way: OpenCode has exited 0 on a failed model and 1 on a missing one. The
    catalogue's ``status`` is not an input."""
    if _has_text_event(stdout):
        return ProbeResult("live", "", None, 0.0)
    for line in (stderr + "\n" + stdout).splitlines():
        if any(phrase in line.lower() for phrase in DEAD_PHRASES):
            found = _NOT_FOUND.search(line)
            hint = _HINT.search(line)
            return ProbeResult(
                "dead",
                (found.group(0) if found else line.strip()),
                hint.group(1) if hint else None,
                0.0,
            )
    detail = (stderr.strip().splitlines() or stdout.strip().splitlines() or [""])[-1][:200]
    return ProbeResult("unknown", detail or f"no answer (exit {returncode})", None, 0.0)


class OpenCodeProber:
    """Probe and catalogue through the `opencode` CLI. ``run_opencode`` is the
    only thing a test replaces."""

    def __init__(
        self,
        run_opencode: Callable[..., subprocess.CompletedProcess[str]] = run_opencode,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._run = run_opencode
        self._clock = clock

    def probe(self, model: str) -> ProbeResult:
        argv = [
            "opencode", "run", "--pure", "--print-logs", "--log-level", "ERROR",
            "--format", "json", "-m", model, PROBE_PROMPT,
        ]  # fmt: skip
        # A fresh cwd, so `fr usage` never attributes the probe session to a run.
        with tempfile.TemporaryDirectory(prefix="fr-probe-") as tmp:
            try:
                done = self._run(argv, cwd=Path(tmp), timeout=PROBE_TIMEOUT_SECONDS)
            except FileNotFoundError:
                return ProbeResult("unknown", "opencode is not on PATH", None, self._clock())
            except subprocess.TimeoutExpired:
                return ProbeResult(
                    "unknown", f"no answer within {PROBE_TIMEOUT_SECONDS}s", None, self._clock()
                )
        return replace(
            classify(done.stdout or "", done.stderr or "", done.returncode), at=self._clock()
        )

    def catalogue(self, provider: str) -> list[CatalogueEntry]:
        """The provider's catalogue, or ``[]`` when it cannot be read."""
        with tempfile.TemporaryDirectory(prefix="fr-probe-") as tmp:
            try:
                done = self._run(
                    ["opencode", "models", provider, "--verbose"], cwd=Path(tmp), timeout=30
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                return []
        entries, _skipped = parse_catalogue(done.stdout or "")
        return entries


class ProbeCache:
    """Verdicts per (harness, model) for 6 hours, in one JSON file. The clock is
    passed in. ``unknown`` is never stored: a timeout is no reason to stop
    asking for six hours."""

    def __init__(
        self,
        path: Path,
        *,
        clock: Callable[[], float] = time.time,
        ttl: float = CACHE_TTL_SECONDS,
    ) -> None:
        self.path = path
        self._clock = clock
        self._ttl = ttl

    def _load(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def probe(
        self, prober: Prober, harness: str, model: str, *, fresh: bool = False
    ) -> ProbeResult:
        key = f"{harness}::{model}"
        data = self._load()
        if not fresh:
            raw = data.get(key)
            if isinstance(raw, dict):
                try:
                    cached = ProbeResult(**raw)
                except TypeError:
                    cached = None
                if cached is not None and 0 <= self._clock() - cached.at < self._ttl:
                    return cached
        result = prober.probe(model)
        if result.verdict in ("live", "dead"):
            data[key] = asdict(replace(result, at=self._clock()))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2, sort_keys=True))
        return result


def default_probe_cache() -> ProbeCache:
    return ProbeCache(models_cache_dir() / "probes.json")
