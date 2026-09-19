"""Harness detection from the process environment — spec §3.D.1, Phase 5.

`FR_HARNESS` is a variable this spec INTRODUCES — no such convention
exists elsewhere in `fr` today. It wins outright when set: a typo must not
silently become an inference, so a value outside `HARNESSES` raises rather
than falling through to guesswork.

Absent an override, detection infers from marker env keys each harness
already sets: `CLAUDECODE`/`CLAUDE_PLUGIN_ROOT` -> claude-code (the same
pair `fr.commands.isolation_cmd` already reads), any `OPENCODE*` key ->
opencode, any `HERMES*` key -> hermes (mirrors `fr.hermes`'s own
`HERMES_HOME` convention). An unrecognised environment returns `None` —
the caller (`fr run advance`'s degradation notice) then treats that as
degraded too, matching the isolation gate's fail-closed posture: a wrong
notice costs a confusing paragraph, a missing one costs a silently skipped
gate.
"""

from __future__ import annotations

from collections.abc import Mapping

from fr.harness.model import HARNESSES, HarnessError


def detect_harness(env: Mapping[str, str]) -> str | None:
    """The detected harness key, or `None` if detection is inconclusive.

    `env` is passed in rather than read from `os.environ` here, so callers
    (and every test) control it explicitly — the same shape as
    `fr.harness.observe.observe`."""
    override = env.get("FR_HARNESS")
    if override is not None:
        if override not in HARNESSES:
            raise HarnessError(f"FR_HARNESS={override!r} is not one of {list(HARNESSES)}")
        return override
    if env.get("CLAUDECODE") or env.get("CLAUDE_PLUGIN_ROOT"):
        return "claude-code"
    if any(key.startswith("OPENCODE") for key in env):
        return "opencode"
    if any(key.startswith("HERMES") for key in env):
        return "hermes"
    return None


__all__ = ["detect_harness"]
