"""Canonical label registry — single source of truth for label colors,
descriptions, and dynamic templates. Consumed by `vk apply` (which calls
`ensure_labels` on the target repo before it touches Issues).

Color scheme (lifecycle gradient, board reads visually as a progression):
  vk-ready     blue    queued for an agent to pick up
  in-progress  orange  agent is actively working
  pr-ready     green   PR is open, awaiting review

manual is gray (human-only). vk-synced is olive (system metadata, set by
the vk-issue-bridge). plan:<slug> is dark red (already in the wild,
preserved for compat). phase:<n> is yellow (attribute, not state).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEX_COLOR_RE = re.compile(r"^[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class LabelDef:
    name: str  # the GitHub label string
    color: str  # 6-char hex without leading #
    description: str  # surfaces in the GitHub UI

    def __post_init__(self) -> None:
        if not _HEX_COLOR_RE.match(self.color):
            msg = f"LabelDef({self.name!r}): color {self.color!r} is not a 6-char hex string"
            raise ValueError(msg)


# Lifecycle states (mutually exclusive — at most one on a given Issue)
VK_READY = LabelDef("vk-ready", "0E8AE6", "Queued for an agent to pick up")
VK_BLOCKED = LabelDef(
    "vk-blocked",
    "aaaaaa",
    "Blocked on dependency — waiting for predecessor phase(s) to complete",
)
MANUAL = LabelDef("manual", "BFBFBF", "Human-only; not routable to an agent")
IN_PROGRESS = LabelDef("in-progress", "D93F0B", "An agent is actively working on this")
PR_READY = LabelDef("pr-ready", "0E8A16", "PR is open; awaiting review")

# Bridge-managed (set by vk-issue-bridge after VK board sync)
VK_SYNCED = LabelDef("vk-synced", "6A630D", "Synced to VK board")

# Templated label colors (name is dynamic)
SPEC_LABEL_COLOR = "5319E7"
PLAN_LABEL_COLOR = "B60205"
PHASE_LABEL_COLOR = "FBCA04"


def spec_label(slug: str) -> LabelDef:
    """Return the LabelDef for `spec:<slug>`."""
    return LabelDef(f"spec:{slug}", SPEC_LABEL_COLOR, f"Spec {slug}")


def plan_label(slug: str) -> LabelDef:
    """Return the LabelDef for `plan:<slug>`."""
    return LabelDef(f"plan:{slug}", PLAN_LABEL_COLOR, f"Part of plan {slug}")


def phase_label(n: int) -> LabelDef:
    """Return the LabelDef for `phase:<n>`."""
    return LabelDef(f"phase:{n}", PHASE_LABEL_COLOR, f"Plan phase {n}")


# Role-name → LabelDef map. Keys are the lifecycle slot names (snake_case);
# `.name` on each LabelDef is the GitHub label string (kebab-case). The
# diff/render projection looks up entries by GitHub name when computing
# label transitions.
LIFECYCLE: dict[str, LabelDef] = {
    "vk_ready": VK_READY,
    "vk_blocked": VK_BLOCKED,
    "manual": MANUAL,
    "in_progress": IN_PROGRESS,
    "pr_ready": PR_READY,
}


def def_for_name(name: str, canonical: LabelDef) -> LabelDef:
    """Return *canonical* if *name* matches its registry name; otherwise
    return a default-gray LabelDef with empty description.

    Used by dispatch to handle operator-overridden label names (e.g.
    ``labels.agentic: "queued"`` in plan-config.yaml).  The fallback
    ensures ensure_labels always receives a valid LabelDef regardless of
    whether the configured name is in the registry.
    """
    if name == canonical.name:
        return canonical
    return LabelDef(name, "ededed", "")
