"""Capability negotiation — 2026-08-14 workflow-shapes spec §4.F.

A workflow shape declares `requires` (capabilities the work needs); a
`Runner` declares `capabilities` (`Runner.capabilities`, what it can
provide). `CAPABILITIES` is the closed vocabulary both draw from — closed
so a typo in a manifest's `requires:` is a validation error (`fr workflow
check`, Phase 6) rather than a silent always-refuses.

`missing_capabilities` is the pure shortfall computation `fr_dispatch.tick`
uses to refuse a dispatch before `runner.preflight` runs, reusing the SAME
per-item failure-accumulation path a `preflight` blocker already uses (see
`fr_dispatch._capability_blocker`) rather than inventing a second refusal
mechanism — Phase 10's tracker-state refusals are expected to route through
that same path too.

**Phase 6 seam.** Nothing in this module (or in `tick`) reads a manifest.
`tick`'s `required_capabilities` keyword is empty by default and is where
Phase 6 wires a shape's resolved `requires:` through, once shape manifests
exist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["CAPABILITIES", "missing_capabilities"]

CAPABILITIES: frozenset[str] = frozenset(
    {"git", "tests", "scm", "browser", "network", "devcontainer"}
)
"""The closed capability set (spec §4.F). Not enforced here — `fr workflow
check` (Phase 6) is what rejects a `requires:`/`capabilities` name outside
this set; this module only computes shortfalls."""


def missing_capabilities(required: Iterable[str], provided: Iterable[str]) -> tuple[str, ...]:
    """The sorted shortfall: capabilities `required` but not `provided`.

    Pure set difference — no I/O, no validation that either argument is
    drawn from `CAPABILITIES`. Sorted so callers get a deterministic
    message regardless of set iteration order.
    """
    return tuple(sorted(set(required) - set(provided)))
