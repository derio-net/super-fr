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

**Canonical home.** This module lived in `fr_dispatch.capabilities` from
Phase 5 (before workflow manifests existed to consume it). Phase 6 moved
the definition here — `fr.workflow.check` (`fr workflow check`, spec §4.A)
also needs `CAPABILITIES` to validate a manifest's `requires:`, and
`fr_dispatch` depends on `fr`, never the reverse, so the closed set has to
live in `fr` for both callers to reach it without a cycle.
`fr_dispatch.capabilities` re-exports this module unchanged so every
existing `from fr_dispatch.capabilities import ...` caller keeps working.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["CAPABILITIES", "missing_capabilities"]

CAPABILITIES: frozenset[str] = frozenset(
    {"git", "tests", "scm", "browser", "network", "devcontainer"}
)
"""The closed capability set (spec §4.F). `fr workflow check` (Phase 6) is
what rejects a `requires:`/`capabilities` name outside this set; this module
only computes shortfalls."""


def missing_capabilities(required: Iterable[str], provided: Iterable[str]) -> tuple[str, ...]:
    """The sorted shortfall: capabilities `required` but not `provided`.

    Pure set difference — no I/O, no validation that either argument is
    drawn from `CAPABILITIES`. Sorted so callers get a deterministic
    message regardless of set iteration order.
    """
    return tuple(sorted(set(required) - set(provided)))
