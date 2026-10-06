"""`fr models ...` CLI — tier→model bindings for subagent dispatch (spec §B.2).

- ``set``     persist a harness/tier → model binding to the user config, then
              materialize it into any on-disk OpenCode agent files it affects
              (spec 2026-09-20-opencode-tier-binding-reaches-dispatch §3.A) —
              a binding a caller answers must take effect in the run that
              made it, not wait for the next install. On OpenCode it first
              probes the model live (spec 2026-10-06-model-binding-churn R1);
              a model the provider no longer serves is refused, or on a
              terminal replaced by a proposal the operator accepts.
              ``--no-probe`` skips the probe and says so.
- ``check``   report every bound harness's bindings — live, dead, unknown or
              unprobed — with a proposed replacement for each dead one and any
              upgrade offer for a live one; on a terminal, ask whether to apply
              each (R5). Off a terminal it only reports, and exits 1 on a dead
              binding.
- ``get``     print the raw config (or one harness's tiers).
- ``resolve`` print the model for a harness+tier (repo override > user);
              prints nothing + exits 0 when unbound, so fr-goal can detect
              "ask the operator" without parsing an error.
- ``apply``   re-run the materialiser for one harness over the CURRENT
              resolved config. install.sh's OpenCode delivery step calls
              this instead of resolving per tier and rewriting frontmatter
              in bash (§3.A's second trigger).
"""

from __future__ import annotations

import typer
from rich.console import Console

import fr.bindings
from fr.artifacts import trigger
from fr.bindings.catalogue import SnapshotStore, models_cache_dir
from fr.bindings.choose import Choice, choose_replacement, is_autonomous
from fr.bindings.health import BindingHealth, check_bindings
from fr.bindings.probe import default_probe_cache
from fr.commands.common import resolve_repo_root
from fr.models import (
    REPO_MODELS_REL,
    ModelsConfig,
    default_models_path,
    load_models,
    resolved_config,
    set_binding,
)
from fr.opencode_agents import MaterializeResult, default_config_home, materialize_agents

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

models_app = typer.Typer(
    help="Tier→model bindings for fr-goal subagent dispatch (harness-keyed).",
    no_args_is_help=True,
)

__all__ = ["REPO_MODELS_REL", "models_app"]

# Harnesses `fr models apply` knows how to materialize. Checked up front so a
# typo'd --harness is refused rather than silently doing nothing — the exact
# failure class (a step that reports success while doing nothing) this whole
# spec exists to close one layer up.
_APPLY_HARNESSES = {"opencode"}


def _repo_cfg() -> ModelsConfig:
    try:
        root = resolve_repo_root()
    except Exception:
        return {}
    return load_models(root / REPO_MODELS_REL)


def _resolved_config() -> ModelsConfig:
    """This machine's repo-over-user model map.

    The layering rule itself lives in `fr.models.resolved_config`, which
    `fr.models.resolve` is also defined on — this function only supplies the
    two config files. Reimplementing the merge here left the rule written
    twice and the two disagreeing on a falsy repo binding (review r-p2-f2)."""
    return resolved_config(repo_cfg=_repo_cfg(), user_cfg=load_models(default_models_path()))


def _report_changes(result: MaterializeResult) -> None:
    """Print exactly what the materialiser did, or that there was nothing to
    do. A silent side effect on a path outside the repo, or a report that
    claims a write that never happened, are both the defect this spec fixes
    one layer in (review r-p1-f3) — this is the one place both `set` and
    `apply` print through, so neither can reintroduce it."""
    changes = result.changes
    if result.considered == 0:
        # No matching agent files found at all
        console.print("nothing to update (no OpenCode agent files found)")
        return
    if not changes:
        # Files were considered but none needed updating
        console.print(f"{result.considered} agent files already up to date")
        return
    # Files were changed or had problems
    for change in changes:
        if change.problem is not None:
            err_console.print(f"  WARNING: {change.path} not updated — {change.problem}")
        elif change.new_model is None:
            console.print(f"  {change.path}: unbound, model: key removed")
        else:
            console.print(f"  {change.path}: model: {change.new_model}")


def _substitution_line(
    harness: str, tier: str, old: str, new: str, *, reason: str, decider: str, rule: str
) -> str:
    """R11's one loud line, shared by every path that substitutes."""
    return (
        f"SUBSTITUTED {harness}/{tier}: {old} → {new} "
        f"(reason: {reason}, decider: {decider}, rule: {rule})"
    )


def _apply_binding(
    harness: str,
    tier: str,
    model: str,
    *,
    old: str | None = None,
    reason: str | None = None,
    rule: str | None = None,
) -> None:
    """THE one write path for an accepted binding: `set_binding`, then
    `materialize_agents`, then `_report_changes`, then — when this replaces
    ``old`` — R11's loud line. `set` and `check` both end here, so a binding
    the operator accepts always takes effect in the run that made it."""
    path = default_models_path()
    set_binding(path, harness, tier, model)
    console.print(f"set {harness}/{tier} → {model} ({path})")
    result = materialize_agents(default_config_home(), models_cfg=_resolved_config())
    _report_changes(result)
    if old is not None and reason is not None and rule is not None:
        err_console.print(
            _substitution_line(
                harness, tier, old, model, reason=reason, decider="operator", rule=rule
            ),
            style="bold yellow",
        )


def _ratio_text(choice: Choice) -> str:
    return "×?" if choice.price_ratio is None else f"×{choice.price_ratio:.1f}"


def _proposal_text(choice: Choice) -> str:
    """``prov/m (rule family, price ×1.0)``; an operator-only pick says so."""
    text = f"{choice.model} (rule {choice.rule}, price {_ratio_text(choice)}"
    if not is_autonomous(choice):
        text += ", operator-only"
    return text + ")"


@models_app.command("set")
def set_cmd(
    harness: str = typer.Option(..., "--harness", help="e.g. claude-code | opencode | hermes."),
    tier: str = typer.Option(
        ...,
        "--tier",
        help="mechanical | standard | hard — or `orchestrator`, the model the "
        "orchestrating session itself is expected to run on (compared by `fr run "
        "start`/`advance`, which warn on a mismatch; never dispatched to).",
    ),
    model: str = typer.Option(..., "--model", help="Concrete model id for this harness+tier."),
    no_probe: bool = typer.Option(
        False,
        "--no-probe",
        help="Persist without asking the provider whether it still serves the model.",
    ),
) -> None:
    """Persist a binding to ~/.config/fr/models.yaml, then materialize it
    into any on-disk OpenCode agent files it affects. On OpenCode the model
    is probed live first; a dead one is refused (or, on a terminal, offered a
    replacement)."""
    # A binding value reaches an argv (and can come from a tracked file), so an
    # option-shaped one is refused before anything is written. OpenCode ids must be
    # provider/model; other harnesses take bare names (`claude-opus-5-5`) and are
    # refused only for a leading '-' or whitespace.
    if harness == "opencode":
        ok, shape = fr.bindings.valid_model_id(model), "provider/model"
    else:
        ok = not model.startswith("-") and not any(c.isspace() for c in model) and bool(model)
        shape = "a name with no leading '-' and no whitespace"
    if not ok:
        err_console.print(f"error: {model!r} is not a valid model id (expected {shape})")
        raise typer.Exit(code=2)
    prober = None if no_probe else fr.bindings.prober_for(harness)
    if no_probe:
        err_console.print(f"probe skipped (--no-probe): {harness}/{tier} → {model} is unchecked")
    elif prober is None:
        console.print("not probed (live probing covers opencode only)")
    else:
        result = prober.probe(model)
        if result.verdict == "unknown":
            err_console.print(
                f"WARNING: probe inconclusive for {model} ({result.detail}); persisting anyway",
                style="yellow",
            )
        elif result.verdict == "dead":
            bound = {**_resolved_config().get(harness, {}), tier: model}
            provider = model.split("/", 1)[0]
            chosen = choose_replacement(
                tier,
                model,
                bound,
                prober.catalogue(provider),
                SnapshotStore(models_cache_dir() / "snapshots.json").get(model),
                result.hint,
                lambda m: prober.probe(m).verdict == "live",
            )
            err_console.print(f"error: the provider does not serve {model}: {result.detail}")
            proposal = chosen if isinstance(chosen, Choice) else None
            if proposal is None:
                err_console.print(f"no replacement found ({chosen.reason})")  # type: ignore[union-attr]
            else:
                err_console.print(f"proposed replacement: {_proposal_text(proposal)}")
            if proposal is None or not trigger.is_interactive():
                raise typer.Exit(code=2)
            if not typer.confirm(
                f"bind {harness}/{tier} to {proposal.model} instead?", default=True
            ):
                raise typer.Exit(code=2)
            _apply_binding(
                harness, tier, proposal.model, old=model, reason="retired", rule=proposal.rule
            )
            return
    _apply_binding(harness, tier, model)


def _bound_harnesses(only: str | None) -> list[str]:
    harnesses = sorted(_resolved_config())
    return [h for h in harnesses if only is None or h == only]


def _health_line(harness: str, h: BindingHealth) -> str:
    line = f"{harness}/{h.tier}: {h.model} — {h.verdict}"
    if h.verdict in ("unknown", "dead") and h.detail:
        line += f" ({h.detail})"
    if h.proposal is not None:
        line += f" → {_proposal_text(h.proposal)}"
    elif h.no_choice is not None:
        line += f" → no replacement ({h.no_choice.reason}; tried {len(h.no_choice.tried)})"
    for o in h.offers:
        line += f" — offer: {o.offer}"
    return line


@models_app.command("check")
def check_cmd(
    harness: str | None = typer.Option(None, "--harness", help="Limit to one harness."),
) -> None:
    """Report every binding's live state, with a replacement for each dead one
    and any upgrade offer. On a terminal, ask whether to apply each; off a
    terminal only report, and exit 1 when a binding is dead."""
    repo_cfg, user_cfg = _repo_cfg(), load_models(default_models_path())
    if not _bound_harnesses(harness):
        console.print("no bindings")
        return
    interactive = trigger.is_interactive()
    dead_left = False
    for name in _bound_harnesses(harness):
        prober = fr.bindings.prober_for(name)
        cache = default_probe_cache() if prober is not None else None
        for h in check_bindings(name, repo_cfg, user_cfg, prober, fresh=True, cache=cache):
            console.print(_health_line(name, h))
            if h.verdict not in ("dead", "live"):
                continue
            wants: tuple[str, str, str, bool] | None = None  # (new, reason, rule, default)
            if h.proposal is not None:
                wants = (h.proposal.model, "retired", h.proposal.rule, True)
            elif h.offers:
                wants = (h.offers[0].offer, "upgrade", "family", False)
            fixed = False
            if wants is not None and interactive:
                if h.layer == "repo":
                    err_console.print(
                        f"  {name}/{h.tier} comes from {REPO_MODELS_REL}, a tracked file fr "
                        "never rewrites; fix it there",
                        style="yellow",
                    )
                else:
                    new, reason, rule, default = wants
                    if typer.confirm(f"  bind {name}/{h.tier} to {new}?", default=default):
                        _apply_binding(name, h.tier, new, old=h.model, reason=reason, rule=rule)
                        fixed = True
            if h.verdict == "dead" and not fixed:
                dead_left = True
    if dead_left:
        raise typer.Exit(code=1)


@models_app.command("get")
def get_cmd(
    harness: str | None = typer.Option(None, "--harness", help="Limit to one harness."),
) -> None:
    """Print the user model config (optionally one harness)."""
    import yaml

    cfg = load_models(default_models_path())
    if harness is not None:
        cfg = {harness: cfg.get(harness, {})}
    console.print(yaml.safe_dump(cfg, sort_keys=True).rstrip() or "{}")


@models_app.command("resolve")
def resolve_cmd(
    harness: str = typer.Option(..., "--harness"),
    tier: str = typer.Option(..., "--tier"),
) -> None:
    """Print the bound model, or nothing (exit 0) when unbound."""
    model = _resolved_config().get(harness, {}).get(tier)
    if model:
        console.print(model)


@models_app.command("apply")
def apply_cmd(
    harness: str = typer.Option(..., "--harness", help="Harness to materialize bindings for."),
) -> None:
    """Re-run the materialiser for one harness over the current resolved
    config. This is what install.sh's OpenCode delivery step calls instead
    of resolving per tier and rewriting frontmatter in bash."""
    if harness not in _APPLY_HARNESSES:
        err_console.print(
            f"error: unknown harness {harness!r} for `fr models apply` "
            f"(known: {', '.join(sorted(_APPLY_HARNESSES))})"
        )
        raise typer.Exit(code=2)
    result = materialize_agents(default_config_home(), models_cfg=_resolved_config())
    _report_changes(result)
