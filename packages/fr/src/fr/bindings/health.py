"""One report of a harness's bindings (spec 2026-10-06-model-binding-churn §A).

`check_bindings` is the ONE function `fr models set/check`, `fr run start`, the
brief builder and the pre-dispatch guard all call: probe each requested binding,
choose a replacement for each dead one, collect upgrade offers for each live one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fr.bindings.catalogue import CatalogueEntry, SnapshotStore, models_cache_dir
from fr.bindings.choose import (
    PHASE_TIERS,
    Choice,
    NoChoice,
    Offer,
    choose_replacement,
    offers,
)
from fr.bindings.probe import ProbeCache, Prober, Verdict
from fr.models import ModelsConfig, binding_layer, resolved_config

ALL_TIERS = ("orchestrator", *PHASE_TIERS)


@dataclass
class BindingHealth:
    """One binding's state. ``proposal`` is set for a dead binding when a rule
    found a replacement (it may still be operator-only: see `is_autonomous`);
    ``no_choice`` carries the tried list when none did. ``hint`` is the
    provider's own `Did you mean` for a dead model."""

    tier: str
    model: str
    layer: str | None
    verdict: Verdict
    detail: str = ""
    hint: str | None = None
    proposal: Choice | None = None
    no_choice: NoChoice | None = None
    offers: list[Offer] = field(default_factory=list)


def check_bindings(
    harness: str,
    repo_cfg: ModelsConfig,
    user_cfg: ModelsConfig,
    prober: Prober | None,
    *,
    tiers: list[str] | None = None,
    fresh: bool = False,
    cache: ProbeCache | None = None,
    snapshots: SnapshotStore | None = None,
) -> list[BindingHealth]:
    """Probe the harness's bound tiers (``orchestrator`` first, then the phase
    tiers cheapest to dearest; ``tiers`` narrows). ``prober=None`` — a harness
    with no probe surface — reports every binding ``unprobed`` and proposes
    nothing (R10). ``fresh`` bypasses ``cache``; without a ``cache`` every probe
    is live."""
    bound = resolved_config(repo_cfg=repo_cfg, user_cfg=user_cfg).get(harness, {})
    wanted = [t for t in ALL_TIERS if t in bound and (tiers is None or t in tiers)]
    layer = {t: binding_layer(harness, t, repo_cfg=repo_cfg, user_cfg=user_cfg) for t in wanted}
    if prober is None:
        return [BindingHealth(t, bound[t], layer[t], "unprobed") for t in wanted]

    store = snapshots if snapshots is not None else SnapshotStore(models_cache_dir() / "snapshots.json")
    entries: list[CatalogueEntry] = []
    for provider in sorted({bound[t].split("/", 1)[0] for t in wanted if "/" in bound[t]}):
        entries.extend(prober.catalogue(provider))
    store.remember([x for x in entries if x.id in set(bound.values())])

    def verdict_of(model: str, *, force: bool) -> tuple[Verdict, str, str | None]:
        result = (
            cache.probe(prober, harness, model, fresh=force)
            if cache is not None
            else prober.probe(model)
        )
        return result.verdict, result.detail, result.hint

    def is_live(model: str) -> bool:
        return verdict_of(model, force=False)[0] == "live"

    report: list[BindingHealth] = []
    for tier in wanted:
        model = bound[tier]
        verdict, detail, hint = verdict_of(model, force=fresh)
        health = BindingHealth(tier, model, layer[tier], verdict, detail, hint)
        if verdict == "dead":
            chosen = choose_replacement(tier, model, bound, entries, store.get(model), hint, is_live)
            if isinstance(chosen, Choice):
                health.proposal = chosen
            else:
                health.no_choice = chosen
        elif verdict == "live":
            health.offers = offers({tier: model}, entries, is_live)
        report.append(health)
    return report
