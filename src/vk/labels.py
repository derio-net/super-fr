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

import hashlib
import re
from dataclasses import dataclass

_HEX_COLOR_RE = re.compile(r"^[0-9A-Fa-f]{6}$")

# GitHub rejects label names longer than this with a 422 at create time (#249).
MAX_LABEL_NAME_LEN = 50


@dataclass(frozen=True)
class LabelDef:
    name: str  # the GitHub label string
    color: str  # 6-char hex without leading #
    description: str  # surfaces in the GitHub UI

    def __post_init__(self) -> None:
        if not _HEX_COLOR_RE.match(self.color):
            msg = f"LabelDef({self.name!r}): color {self.color!r} is not a 6-char hex string"
            raise ValueError(msg)
        # GitHub caps label names at 50 chars; a longer name 422s at
        # `gh label create`. Fail loud here rather than at dispatch (#249).
        # Slug-derived labels go through `_bounded_label_name`, so this guard
        # only trips on a bug that bypasses it.
        if len(self.name) > MAX_LABEL_NAME_LEN:
            msg = (
                f"LabelDef: name {self.name!r} is {len(self.name)} chars "
                f"(max {MAX_LABEL_NAME_LEN}). Use _bounded_label_name for slug-derived labels."
            )
            raise ValueError(msg)


def _bounded_label_name(prefix: str, value: str) -> str:
    """Return `<prefix><value>` capped at GitHub's 50-char label limit.

    When the full name fits, it's returned verbatim (no behavior change for
    short slugs). When it would overflow, the value is truncated and a short
    deterministic hash of the *full* value is appended so distinct long values
    don't collide. The label is an opaque routing key for the bridge, so a
    stable shortened form is fine — stable across runs because the hash is
    content-derived (#249).
    """
    name = f"{prefix}{value}"
    if len(name) <= MAX_LABEL_NAME_LEN:
        return name
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:6]
    # `max(0, …)` guards a pathologically long prefix making `keep` negative —
    # `value[:negative]` slices from the END, silently producing an over-length
    # label. Today only the 5-char `plan:`/`spec:` prefixes call this; the
    # LabelDef.__post_init__ length guard is the loud backstop otherwise.
    keep = max(0, MAX_LABEL_NAME_LEN - len(prefix) - 1 - len(digest))  # room for "-" + hash
    # Final clamp makes the ≤50 invariant hold for ANY prefix (a no-op for the
    # 5-char `plan:`/`spec:` callers, where the build is already exactly 50).
    return f"{prefix}{value[:keep]}-{digest}"[:MAX_LABEL_NAME_LEN]


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
    """Return the LabelDef for `spec:<slug>` (name capped at 50 chars; #249)."""
    return LabelDef(_bounded_label_name("spec:", slug), SPEC_LABEL_COLOR, f"Spec {slug}")


def plan_label(slug: str) -> LabelDef:
    """Return the LabelDef for `plan:<slug>` (name capped at 50 chars; #249)."""
    return LabelDef(_bounded_label_name("plan:", slug), PLAN_LABEL_COLOR, f"Part of plan {slug}")


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
