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
    """One agent file this function looked at and acted on — so a caller can
    report what happened rather than claim silently that a binding took
    effect.

    `problem` is set when the file could NOT be rewritten, in which case
    nothing was written and `new_model` is None (review r-p1/f3). It exists
    because the first version appended a Change unconditionally: when the
    `mode: subagent` anchor was absent the rewrite inserted nothing, yet the
    report still named the model — a materialiser claiming success while
    doing nothing, which is the exact defect class this spec was written to
    fix, one level in."""

    path: Path
    tier: str
    old_model: str | None
    new_model: str | None
    problem: str | None = None


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


def _split_frontmatter(lines: list[str]) -> tuple[list[str], list[str]] | None:
    """``(frontmatter_lines, rest)`` including both ``---`` fences in the
    first part, or None when the file has no closing fence.

    The rewrite MUST be scoped to the frontmatter (review r-p1/f1). The
    first version ran over the whole file, so a markdown BODY line beginning
    ``model:`` — a future agent documenting its own frontmatter, say — was
    silently deleted. install.sh's awk had the same flaw (``/^model:/
    { next }``) and no way to know where the frontmatter ended; in Python
    there is no excuse for not knowing."""
    if not lines or lines[0].rstrip("\n") != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].rstrip("\n") == "---":
            return lines[: index + 1], lines[index + 1 :]
    return None


def _existing_model(frontmatter: list[str]) -> str | None:
    for line in frontmatter:
        if line.startswith("model:"):
            return line[len("model:") :].strip()
    return None


def _rewrite(lines: list[str], *, model: str | None) -> list[str] | None:
    """The file's lines with its frontmatter ``model:`` key set to `model`,
    or None when the file's shape makes that impossible.

    Drops every ``model:`` line in the FRONTMATTER ONLY, then inserts the
    resolved one directly after the ``mode: subagent`` anchor. Unresolved
    means no key at all — never an empty one, which OpenCode would try to
    resolve. Returns None (rather than a file with the key silently missing)
    when there is no closing ``---`` fence, or when a model is wanted and the
    anchor is absent: an unwritable file must be reported, not
    half-written."""
    split = _split_frontmatter(lines)
    if split is None:
        return None
    frontmatter, rest = split

    kept = [line for line in frontmatter if not line.startswith("model:")]
    if model is None:
        return kept + rest

    anchors = [i for i, line in enumerate(kept) if line.rstrip("\n") == _MODE_ANCHOR]
    if not anchors:
        return None
    at = anchors[0]
    return kept[: at + 1] + [f"model: {model}\n"] + kept[at + 1 :] + rest


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
        current = agent_file.read_text()
        lines = current.splitlines(keepends=True)
        split = _split_frontmatter(lines)
        old_model = _existing_model(split[0]) if split else None

        rewritten = _rewrite(lines, model=model)
        if rewritten is None:
            # Unwritable shape — report it, write nothing. Never an exception:
            # an operator with one hand-edited agent file must still be able to
            # run `fr models set` (spec §3.A).
            changes.append(
                Change(
                    path=agent_file,
                    tier=tier,
                    old_model=old_model,
                    new_model=None,
                    problem=(
                        "no `---` frontmatter fence"
                        if split is None
                        else "no `mode: subagent` anchor to insert `model:` after"
                    ),
                )
            )
            continue

        desired = "".join(rewritten)
        if desired == current:
            # Compare RENDERED content, not just the model value (review
            # r-p1/f2): a correct model in the wrong position used to compare
            # equal and be left misplaced, so the "immediately after the
            # anchor" invariant this module documents did not hold for every
            # file it had seen. Idempotence is preserved — an
            # already-correct file is still not rewritten.
            continue

        agent_file.write_text(desired)
        changes.append(Change(path=agent_file, tier=tier, old_model=old_model, new_model=model))
    return changes
