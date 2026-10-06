"""Replacement rules for a dead binding, and upgrade offers (spec
2026-10-06-model-binding-churn §A, R4, R12).

Pure: no clock, no subprocess, no file I/O. ``probe`` is a callable
``model -> is_live`` the caller supplies, so candidates are probed lazily and at
most `MAX_PROBES` times per choice. Callers decide what to do with a `Choice`
through `is_autonomous` alone — the one predicate for "may fr apply this unasked".
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Literal

from fr.bindings.catalogue import CatalogueEntry

MAX_PROBES = 5
AUTONOMOUS_MAX_PRICE_RATIO = 2.0
PHASE_TIERS = ("mechanical", "standard", "hard")  # cheapest to dearest

Rule = Literal["family", "tier", "hint"]
Probe = Callable[[str], bool]


@dataclass(frozen=True)
class Choice:
    """``price_ratio`` is the new price over the dead one, ``None`` when either
    is unknown (or the dead one is free)."""

    model: str
    rule: Rule
    price_ratio: float | None
    # Every candidate probed on the way, this one last — what a refusal names
    # (R8). Not part of a choice's identity.
    tried: tuple[str, ...] = field(default=(), compare=False)


@dataclass(frozen=True)
class NoChoice:
    reason: str
    tried: tuple[str, ...]


@dataclass(frozen=True)
class Offer:
    tier: str
    model: str
    offer: str


def is_autonomous(choice: Choice) -> bool:
    """R4's bound: only the family and tier rules, and only with a KNOWN price
    ratio of at most 2. An unknown cost is never a licence to spend."""
    return (
        choice.rule in ("family", "tier")
        and choice.price_ratio is not None
        and choice.price_ratio <= AUTONOMOUS_MAX_PRICE_RATIO
    )


def _provider(model: str) -> str:
    return model.split("/", 1)[0]


def _newest_first(entries: Iterable[CatalogueEntry]) -> list[CatalogueEntry]:
    return sorted(entries, key=lambda x: (x.release_date or "", x.id), reverse=True)


def _candidates(
    entries: list[CatalogueEntry], provider: str, *, exclude: Iterable[str] = ()
) -> list[CatalogueEntry]:
    """Tool-calling models of ``provider``, minus ``exclude`` — the filter both
    rules and `offers` share."""
    skip = set(exclude)
    return [x for x in entries if x.provider == provider and x.toolcall and x.id not in skip]


def _ratio(new: float | None, old: float | None) -> float | None:
    if new is None or not old:
        return None
    return new / old


def _order_holds(
    tier: str, price: float | None, bindings: dict[str, str], by_id: dict[str, CatalogueEntry]
) -> bool:
    """After substitution mechanical <= standard <= hard, checked only against
    neighbours whose prices are known; an unknown one constrains nothing."""
    if price is None or tier not in PHASE_TIERS:
        return True
    rank = PHASE_TIERS.index(tier)
    for other in PHASE_TIERS:
        bound = by_id.get(bindings.get(other, ""))
        if other == tier or bound is None or bound.price is None:
            continue
        if PHASE_TIERS.index(other) < rank and bound.price > price:
            return False
        if PHASE_TIERS.index(other) > rank and price > bound.price:
            return False
    return True


def choose_replacement(
    tier: str,
    dead: str,
    bindings: dict[str, str],
    entries: list[CatalogueEntry],
    snapshot: CatalogueEntry | None,
    hint: str | None,
    probe: Probe,
) -> Choice | NoChoice:
    """R4's rules in order; the first that yields a live model wins.

    ``bindings`` is the harness's whole tier -> model map (``orchestrator``
    included); ``snapshot`` the dead model's last-known entry; ``hint`` the
    provider's bare ``Did you mean`` id. A dead model with neither a catalogue
    entry nor a snapshot gives the family and tier rules nothing to start from
    (no family, no price), so only the hint is tried for it."""
    provider = _provider(dead)
    by_id = {x.id: x for x in entries}
    known = by_id.get(dead) or snapshot
    tried: list[str] = []

    def live(model: str) -> bool:
        tried.append(model)
        return probe(model)

    def budget() -> bool:
        return len(tried) < MAX_PROBES

    if known is not None and known.family and known.release_date:
        newer = [
            x
            for x in _candidates(entries, provider, exclude=[dead])
            if x.family == known.family and (x.release_date or "") > known.release_date
        ]
        for cand in _newest_first(newer):
            if not budget():
                break
            if live(cand.id):
                return Choice(cand.id, "family", _ratio(cand.price, known.price), tuple(tried))

    if known is not None and tier != "orchestrator":
        pool = [
            x
            for x in _candidates(entries, provider, exclude=[dead, *bindings.values()])
            if _order_holds(tier, x.price, bindings, by_id)
        ]
        dead_price = known.price
        if dead_price is None:
            ordered = _newest_first(pool)
        else:
            ordered = sorted(
                _newest_first(pool),
                key=lambda x: (x.price is None, abs((x.price or 0.0) - dead_price)),
            )
        for cand in ordered:
            if not budget():
                break
            if live(cand.id):
                return Choice(cand.id, "tier", _ratio(cand.price, dead_price), tuple(tried))

    if known is None and hint:
        model = hint if "/" in hint else f"{provider}/{hint}"
        # A hint naming another provider is not this binding's to take.
        if _provider(model) == provider and model != dead and budget() and live(model):
            return Choice(model, "hint", None, tuple(tried))

    reason = (
        "no live same-family successor or tier candidate"
        if known is not None
        else "no catalogue entry or snapshot, and the provider named no live model"
    )
    return NoChoice(reason, tuple(tried))


def offers(bindings: dict[str, str], entries: list[CatalogueEntry], probe: Probe) -> list[Offer]:
    """R12: for each LIVE binding, the newest same-family model that is newer,
    tool-calling and live. Never applied by this module or by any caller
    without a yes. A model with no known family has no lineage to offer from."""
    by_id = {x.id: x for x in entries}
    out: list[Offer] = []
    for tier, model in bindings.items():
        bound = by_id.get(model)
        if bound is None or not bound.family or not bound.release_date:
            continue
        newer = [
            x
            for x in _candidates(entries, bound.provider, exclude=[model])
            if x.family == bound.family and (x.release_date or "") > bound.release_date
        ]
        for cand in _newest_first(newer)[:MAX_PROBES]:
            if probe(cand.id):
                out.append(Offer(tier, model, cand.id))
                break
    return out
