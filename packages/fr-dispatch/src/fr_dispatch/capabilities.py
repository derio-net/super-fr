"""Capability negotiation — 2026-08-14 workflow-shapes spec §4.F.

Re-exports `fr.capabilities` unchanged. The closed `CAPABILITIES` set moved
to `fr` in Phase 6 so `fr.workflow.check` (`fr workflow check`) can validate
a manifest's `requires:` against the same vocabulary `Runner.capabilities`
draws from, without `fr` depending on `fr_dispatch` (dependencies only ever
point `fr_dispatch -> fr`). Every existing
`from fr_dispatch.capabilities import CAPABILITIES, missing_capabilities`
caller — and `fr_dispatch._capability_blocker`, which uses both — keeps
working unchanged.
"""

from __future__ import annotations

from fr.capabilities import CAPABILITIES, missing_capabilities

__all__ = ["CAPABILITIES", "missing_capabilities"]
