"""In-place materialiser for OpenCode's tier-bound agent files.

Spec ``2026-09-20-opencode-tier-binding-reaches-dispatch`` §3.A. Two callers
write through this one function — `fr models set` (a binding change must
take effect in the run that made it) and `fr models apply --harness opencode`
(install.sh's delivery step, wired in plan phase 2) — so a tier binding can
never again be baked into a file at install time and then silently outlive a
rebind (spec §1.1: unbound→bound AND the sharper bound→rebound case, where
the file keeps stating a model the operator explicitly moved away from).

Neither caller resolves a model here: both hand in an already-loaded
``models_cfg``, so the repo-overrides-user resolution order
(`fr.models.resolve`) stays the caller's decision, not this module's.

Layout contract this module depends on and must not silently violate:
`scripts/sync-opencode.py`'s ``_render_agent`` guarantees every generated
agent file has a single-line, double-quoted ``description:``, then
``mode: subagent`` on its own line — the anchor this module inserts
``model:`` directly after. That is the same anchor install.sh's (now
deleted, phase 2) awk block used; this module is that awk, moved into
Python and made the only copy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fr.models import ModelsConfig, xdg_config_home
from fr.types import PHASE_TIERS

_MODE_ANCHOR = "mode: subagent"


@dataclass(frozen=True)
class Change:
    """One rewritten agent file — so a caller can report what happened
    rather than claim silently that a binding took effect."""

    path: Path
    tier: str
    old_model: str | None
    new_model: str | None


def default_config_home() -> Path:
    """Base config dir OpenCode's own files live under — the SAME
    resolution `fr.models.default_models_path` uses
    (``$XDG_CONFIG_HOME``, else ``$HOME/.config``), factored into
    `fr.models.xdg_config_home` so the two never diverge."""
    return xdg_config_home()


def _tier_for_stem(stem: str) -> str | None:
    """Discover the tier from a filename stem rather than naming an agent
    (spec §3.A, spec-review r1): any ``<name>-<tier>.md`` for a tier in
    `fr.types.PHASE_TIERS` is a target, whatever ``<name>`` is. This module
    must never hardcode ``fr-phase-executor`` — it cannot read
    ``plugins/super-fr/agents/`` (no checkout is guaranteed when `fr models
    set` runs), so a literal stem would be a second, unreconciled source of
    truth for the agent set."""
    for tier in PHASE_TIERS:
        if stem.endswith(f"-{tier}"):
            return tier
    return None


def _existing_model(lines: list[str]) -> str | None:
    for line in lines:
        if line.startswith("model:"):
            return line[len("model:") :].strip()
    return None


def _rewrite(lines: list[str], *, model: str | None) -> list[str]:
    """Drop every top-level ``model:`` line, then insert the resolved one
    directly after the ``mode: subagent`` anchor line. Unresolved means no
    key at all is written — never an empty one, which OpenCode would try to
    resolve. Structurally, at most one ``model:`` line can ever land in the
    output: the only place one is appended is right after the one anchor
    line, and every existing ``model:`` line is filtered out first."""
    out: list[str] = []
    for line in lines:
        if line.startswith("model:"):
            continue
        out.append(line)
        if model and line.rstrip("\n") == _MODE_ANCHOR:
            out.append(f"model: {model}\n")
    return out


def materialize_agents(config_home: Path, *, models_cfg: ModelsConfig) -> list[Change]:
    """Rewrite every discovered OpenCode tier agent file in place so its
    ``model:`` key (or the deliberate absence of one) matches
    ``models_cfg``'s ``opencode`` bindings.

    Targets are discovered by globbing
    ``<config_home>/opencode/agent/*.md`` and matching the tier suffix —
    never named. A missing agent dir, or an agent dir with no matching
    files, is a reported no-op (an empty list), not an exception: an
    operator who never opted into OpenCode delivery must not have
    `fr models set` fail on them. Nothing outside
    ``<config_home>/opencode/agent/`` is ever written.
    """
    agent_dir = config_home / "opencode" / "agent"
    if not agent_dir.is_dir():
        return []

    bindings = models_cfg.get("opencode", {})
    changes: list[Change] = []
    for agent_file in sorted(agent_dir.glob("*.md")):
        tier = _tier_for_stem(agent_file.stem)
        if tier is None:
            continue
        model = bindings.get(tier)
        lines = agent_file.read_text().splitlines(keepends=True)
        old_model = _existing_model(lines)
        if old_model == model:
            continue
        agent_file.write_text("".join(_rewrite(lines, model=model)))
        changes.append(Change(path=agent_file, tier=tier, old_model=old_model, new_model=model))
    return changes
