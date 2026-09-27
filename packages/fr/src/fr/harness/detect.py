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

**A mixed environment is resolved by nearness, never by precedence**
(gh#537). Environment variables cross process boundaries: an OpenCode started
from a Claude Code shell inherits `CLAUDECODE=1`, so a marker says a harness
ran somewhere ABOVE fr, not that it is the one fr runs under. This module used
to settle that with a fixed order (claude-code first), which named Claude Code
as the holder of units OpenCode dispatched. Both harnesses export their own
pid (`CLAUDE_PID`, `OPENCODE_PID`, read off the installed binaries), so when
markers of more than one harness are present, the one whose pid is nearest fr
in its process ancestry wins. A harness that cannot be placed there (no pid
key, or a pid that is not an ancestor) is not named, and when none can be,
detection is inconclusive: a wrong holder reads as an answer, an absent one
reads as a gap. Hermes exports no pid fr knows of, so a Hermes nested in
another harness is not recognised in a mixed environment. An unambiguous
environment never reads the process tree.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping, Sequence

from fr.harness.model import HARNESSES, HarnessError

_PID_KEYS: dict[str, str] = {"claude-code": "CLAUDE_PID", "opencode": "OPENCODE_PID"}
"""The key each harness exports its OWN pid under, where one is known."""


def _markers_present(env: Mapping[str, str]) -> list[str]:
    present = []
    if env.get("CLAUDECODE") or env.get("CLAUDE_PLUGIN_ROOT"):
        present.append("claude-code")
    if any(key.startswith("OPENCODE") for key in env):
        present.append("opencode")
    if any(key.startswith("HERMES") for key in env):
        present.append("hermes")
    return present


def process_ancestry() -> list[int]:
    """This process's pid, then its parent's, and so on to the root; `[]`
    when the process table cannot be read. One `ps` call, which macOS and
    procps both answer with the same flags."""
    try:
        listing = subprocess.run(
            ["ps", "-A", "-o", "pid=,ppid="],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    parents: dict[int, int] = {}
    for line in listing.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0].isdigit() and fields[1].isdigit():
            parents[int(fields[0])] = int(fields[1])
    chain = [os.getpid()]
    while chain[-1] > 1 and chain[-1] in parents and parents[chain[-1]] not in chain:
        chain.append(parents[chain[-1]])
    return chain


def _nearest(present: Sequence[str], env: Mapping[str, str], ancestry: Sequence[int]) -> str | None:
    depth = {pid: index for index, pid in enumerate(ancestry)}
    placed: list[tuple[int, str]] = []
    for harness in present:
        raw = env.get(_PID_KEYS.get(harness, ""), "")
        if raw.isdigit() and int(raw) in depth:
            placed.append((depth[int(raw)], harness))
    return min(placed)[1] if placed else None


def detect_harness(
    env: Mapping[str, str], *, ancestors: Callable[[], Sequence[int]] | None = None
) -> str | None:
    """The detected harness key, or `None` if detection is inconclusive.

    `env` is passed in rather than read from `os.environ` here, so callers
    (and every test) control it explicitly — the same shape as
    `fr.harness.observe.observe`. `ancestors` is the same seam for the process
    tree, which is read only when `env` carries more than one harness's
    markers."""
    override = env.get("FR_HARNESS")
    if override is not None:
        if override not in HARNESSES:
            raise HarnessError(f"FR_HARNESS={override!r} is not one of {list(HARNESSES)}")
        return override
    present = _markers_present(env)
    if len(present) <= 1:
        return present[0] if present else None
    return _nearest(present, env, (ancestors or process_ancestry)())


__all__ = ["detect_harness", "process_ancestry"]
