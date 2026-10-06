"""Replacement rules and offers (spec 2026-10-06-model-binding-churn §A, R4, R12).

Pure: a fake probe callable and in-memory catalogue entries. No clock, no I/O."""

from __future__ import annotations

from fr.bindings.catalogue import CatalogueEntry
from fr.bindings.choose import (
    Choice,
    NoChoice,
    Offer,
    choose_replacement,
    is_autonomous,
    offers,
)

P = "prov"


def e(
    name: str,
    family: str | None = "fam",
    date: str | None = "2026-01-01",
    price: float | None = 10.0,
    toolcall: bool = True,
) -> CatalogueEntry:
    return CatalogueEntry(f"{P}/{name}", P, family, date, price, toolcall)


class Probe:
    """Live unless named in ``dead``; counts and records every call."""

    def __init__(self, dead: set[str] = frozenset()) -> None:  # type: ignore[assignment]
        self.dead = dead
        self.calls: list[str] = []

    def __call__(self, model: str) -> bool:
        self.calls.append(model)
        return model not in self.dead


BOUND = {
    "orchestrator": f"{P}/orch",
    "mechanical": f"{P}/mech",
    "standard": f"{P}/std",
    "hard": f"{P}/hard",
}


def choose(tier, dead, entries, *, probe=None, snapshot=None, hint=None, bindings=None):
    return choose_replacement(
        tier,
        f"{P}/{dead}",
        bindings or BOUND,
        entries,
        snapshot,
        hint,
        probe or Probe(),
    )


def test_the_family_successor_is_taken_newest_first() -> None:
    entries = [
        e("old", date="2026-01-01"),
        e("mid", date="2026-03-01"),
        e("new", date="2026-05-01"),
        e("other-family", family="x", date="2026-06-01"),
    ]
    got = choose("standard", "old", entries)
    assert got == Choice(f"{P}/new", "family", 1.0)


def test_a_retired_successor_is_skipped_for_the_next() -> None:
    entries = [e("old"), e("mid", date="2026-03-01"), e("new", date="2026-05-01")]
    probe = Probe(dead={f"{P}/new"})
    got = choose("standard", "old", entries, probe=probe)
    assert isinstance(got, Choice) and got.model == f"{P}/mid"
    assert probe.calls == [f"{P}/new", f"{P}/mid"]


def test_a_family_candidate_must_be_newer_and_toolcalling() -> None:
    entries = [
        e("old", date="2026-03-01"),
        e("older", date="2026-01-01"),
        e("notools", date="2026-05-01", toolcall=False),
    ]
    got = choose("orchestrator", "old", entries)
    assert isinstance(got, NoChoice)


def test_the_family_comes_from_the_snapshot_when_the_catalogue_dropped_the_model() -> None:
    entries = [e("new", date="2026-05-01")]
    snap = e("gone", date="2026-01-01")
    got = choose("hard", "gone", entries, snapshot=snap)
    assert isinstance(got, Choice) and got.rule == "family" and got.model == f"{P}/new"


def test_the_tier_rule_when_no_family_successor() -> None:
    # `std` is dead and alone in its family; two foreign-family candidates differ in price.
    entries = [
        e("mech", family="m", price=1.0),
        e("std", family="s", price=10.0),
        e("hard", family="h", price=40.0),
        e("orch", family="o", price=30.0),
        e("near", family="n", price=12.0, date="2026-02-01"),
        e("far", family="f", price=30.0, date="2026-02-01"),
    ]
    got = choose("standard", "std", entries)
    # "near" is nearest the dead price; "far" > hard? no: 30 <= 40 passes but is farther.
    assert got == Choice(f"{P}/near", "tier", 1.2)


def test_the_tier_rule_is_distinct_from_every_other_bound_model() -> None:
    entries = [
        e("std", family="s", price=10.0),
        e("mech", family="m", price=10.0),  # bound to mechanical: excluded
        e("orch", family="o", price=10.0),  # the orchestrator's: excluded
        e("free", family="f", price=11.0),
    ]
    got = choose("standard", "std", entries)
    assert isinstance(got, Choice) and got.model == f"{P}/free"


def test_the_tier_rule_keeps_known_price_order() -> None:
    entries = [
        e("mech", family="m", price=5.0),
        e("std", family="s", price=10.0),
        e("hard", family="h", price=20.0),
        e("too-cheap", family="a", price=1.0),  # < mechanical's 5
        e("too-dear", family="b", price=50.0),  # > hard's 20
        e("fits", family="c", price=18.0),
    ]
    got = choose("standard", "std", entries)
    assert isinstance(got, Choice) and got.model == f"{P}/fits"


def test_an_unknown_price_neighbour_constrains_nothing() -> None:
    entries = [
        e("std", family="s", price=10.0),
        e("cand", family="c", price=500.0),
    ]
    # mech/hard/orch are not in the catalogue: no known price, no constraint.
    got = choose("standard", "std", entries)
    assert isinstance(got, Choice) and got.model == f"{P}/cand"
    assert got.price_ratio == 50.0


def test_the_tier_rule_takes_the_newest_when_the_dead_price_is_unknown() -> None:
    entries = [
        e("std", family="s", price=None),
        e("a", family="a", price=1.0, date="2026-02-01"),
        e("b", family="b", price=9.0, date="2026-04-01"),
    ]
    got = choose("standard", "std", entries)
    assert got == Choice(f"{P}/b", "tier", None)


def test_the_tier_rule_is_never_used_for_the_orchestrator() -> None:
    entries = [e("orch", family="o"), e("x", family="x")]
    got = choose("orchestrator", "orch", entries)
    assert isinstance(got, NoChoice)


def test_the_provider_hint_only_for_a_model_with_no_entry_and_no_snapshot() -> None:
    entries = [e("sol-2", family="sol", date="2026-09-01")]
    got = choose("orchestrator", "sol-1", entries, hint="sol-2")
    assert got == Choice(f"{P}/sol-2", "hint", None)
    # Not used when the model is known: the family rule has inputs.
    got2 = choose("orchestrator", "known", [e("known"), e("new", date="2026-09-01")], hint="x")
    assert isinstance(got2, Choice) and got2.rule == "family"
    # A dead hint is no replacement.
    assert isinstance(
        choose("orchestrator", "sol-1", entries, hint="sol-2", probe=Probe({f"{P}/sol-2"})),
        NoChoice,
    )
    assert isinstance(choose("orchestrator", "sol-1", entries, hint=None), NoChoice)


def test_at_most_five_probes_per_choice() -> None:
    entries = [e("old")] + [e(f"n{i}", date=f"2026-0{i + 2}-01") for i in range(1, 8)]
    probe = Probe(dead={x.id for x in entries})
    got = choose("hard", "old", entries, probe=probe)
    assert isinstance(got, NoChoice)
    assert len(probe.calls) == 5
    assert len(got.tried) == 5


def test_no_choice_says_why() -> None:
    got = choose("standard", "old", [e("old")])
    assert isinstance(got, NoChoice) and got.reason and got.tried == ()


def test_the_autonomous_bound() -> None:
    assert is_autonomous(Choice("p/m", "family", 1.0))
    assert is_autonomous(Choice("p/m", "tier", 2.0))
    assert not is_autonomous(Choice("p/m", "tier", 2.5))
    assert not is_autonomous(Choice("p/m", "family", None))
    assert not is_autonomous(Choice("p/m", "hint", 1.0))


def test_offers_a_newer_live_same_family_toolcall_model() -> None:
    entries = [
        e("std"),
        e("std2", date="2026-06-01"),
        e("nope", date="2026-07-01", toolcall=False),
    ]
    got = offers({"standard": f"{P}/std"}, entries, Probe())
    assert got == [Offer("standard", f"{P}/std", f"{P}/std2")]


def test_no_offer_for_an_unknown_family_or_a_retired_newer_model() -> None:
    assert (
        offers({"standard": f"{P}/std"}, [e("std", family=None), e("n", family=None)], Probe())
        == []
    )
    assert offers({"standard": f"{P}/missing"}, [e("n")], Probe()) == []
    entries = [e("std"), e("std2", date="2026-06-01")]
    assert offers({"standard": f"{P}/std"}, entries, Probe({f"{P}/std2"})) == []
