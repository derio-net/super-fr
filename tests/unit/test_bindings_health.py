"""`check_bindings` — one report of a harness's bindings (spec
2026-10-06-model-binding-churn §A health.py), over a fake prober."""

from __future__ import annotations

from pathlib import Path

from fr.bindings.catalogue import CatalogueEntry, SnapshotStore
from fr.bindings.choose import Choice
from fr.bindings.health import check_bindings
from fr.bindings.probe import ProbeResult

P = "prov"


def ent(name: str, family: str, date: str, price: float = 10.0) -> CatalogueEntry:
    return CatalogueEntry(f"{P}/{name}", P, family, date, price, True)


class FakeProber:
    def __init__(self, entries: list[CatalogueEntry], dead: dict[str, str | None]) -> None:
        self.entries = entries
        self.dead = dead  # model -> hint
        self.probed: list[str] = []

    def probe(self, model: str) -> ProbeResult:
        self.probed.append(model)
        if model in self.dead:
            return ProbeResult("dead", "model not found", self.dead[model], 0.0)
        return ProbeResult("live", "", None, 0.0)

    def catalogue(self, provider: str) -> list[CatalogueEntry]:
        return [e for e in self.entries if e.provider == provider]


ENTRIES = [
    ent("orch", "o", "2026-01-01"),
    ent("std", "s", "2026-01-01"),
    ent("std2", "s", "2026-04-01"),
    ent("hard", "h", "2026-01-01", 20.0),
    ent("mech", "m", "2026-01-01", 5.0),
    ent("mech2", "m", "2026-05-01", 5.0),
]
USER = {
    "opencode": {
        "orchestrator": f"{P}/orch",
        "mechanical": f"{P}/mech",
        "standard": f"{P}/std",
        "hard": f"{P}/hard",
    }
}


def run(prober, repo=None, tiers=None, tmp=None):
    return check_bindings(
        "opencode",
        repo or {},
        USER,
        prober,
        tiers=tiers,
        fresh=True,
        snapshots=SnapshotStore(tmp / "snap.json"),
    )


def test_one_health_per_bound_tier_with_verdict_layer_proposal_and_offers(tmp_path: Path) -> None:
    prober = FakeProber(ENTRIES, dead={f"{P}/std": None})
    repo = {"opencode": {"hard": f"{P}/hard"}}
    got = {h.tier: h for h in run(prober, repo=repo, tmp=tmp_path)}
    assert list(got) == ["orchestrator", "mechanical", "standard", "hard"]
    assert got["standard"].verdict == "dead"
    assert got["standard"].layer == "user"
    assert got["standard"].proposal == Choice(f"{P}/std2", "family", 1.0)
    assert got["hard"].layer == "repo" and got["hard"].verdict == "live"
    assert got["mechanical"].verdict == "live"
    assert [o.offer for o in got["mechanical"].offers] == [f"{P}/mech2"]
    assert got["orchestrator"].offers == [] and got["orchestrator"].proposal is None


def test_tiers_narrows_the_report(tmp_path: Path) -> None:
    prober = FakeProber(ENTRIES, dead={})
    got = run(prober, tiers=["standard"], tmp=tmp_path)
    assert [h.tier for h in got] == ["standard"]
    assert prober.probed == [f"{P}/std", f"{P}/std2"]  # the binding, then its offer


def test_a_harness_with_no_prober_is_unprobed_with_no_proposals(tmp_path: Path) -> None:
    got = check_bindings(
        "claude-code",
        {},
        {"claude-code": {"standard": "claude-sonnet-5"}},
        None,
        fresh=False,
        snapshots=SnapshotStore(tmp_path / "snap.json"),
    )
    assert [(h.tier, h.verdict, h.proposal, h.offers) for h in got] == [
        ("standard", "unprobed", None, [])
    ]


def test_a_no_choice_is_kept_for_the_caller(tmp_path: Path) -> None:
    prober = FakeProber([ent("orch", "o", "2026-01-01")], dead={f"{P}/orch": None})
    (h,) = run(prober, tiers=["orchestrator"], tmp=tmp_path)
    assert h.verdict == "dead" and h.proposal is None and h.no_choice is not None


def test_the_provider_hint_reaches_the_chooser(tmp_path: Path) -> None:
    entries = [ent("sol-2", "sol", "2026-09-01")]
    prober = FakeProber(entries, dead={f"{P}/sol-1": "sol-2"})
    cfg = {"opencode": {"orchestrator": f"{P}/sol-1"}}
    (h,) = check_bindings(
        "opencode", {}, cfg, prober, fresh=True, snapshots=SnapshotStore(tmp_path / "s.json")
    )
    assert h.proposal == Choice(f"{P}/sol-2", "hint", None)
    assert h.hint == "sol-2"


def test_snapshots_are_written_for_every_bound_model_seen(tmp_path: Path) -> None:
    prober = FakeProber(ENTRIES, dead={})
    run(prober, tmp=tmp_path)
    store = SnapshotStore(tmp_path / "snap.json")
    assert store.get(f"{P}/std") is not None and store.get(f"{P}/hard") is not None
    assert store.get(f"{P}/std2") is None  # an offer candidate is not a bound model


def test_a_vanished_model_is_reasoned_about_from_its_snapshot(tmp_path: Path) -> None:
    snaps = SnapshotStore(tmp_path / "snap.json")
    snaps.remember([ent("gone", "g", "2026-01-01")])
    entries = [ent("g2", "g", "2026-06-01")]
    prober = FakeProber(entries, dead={f"{P}/gone": None})
    cfg = {"opencode": {"standard": f"{P}/gone"}}
    (h,) = check_bindings("opencode", {}, cfg, prober, fresh=True, snapshots=snaps)
    assert h.proposal == Choice(f"{P}/g2", "family", 1.0)


def test_two_dead_tiers_never_get_the_same_replacement(tmp_path: Path) -> None:
    # Both mechanical and standard are dead, and each one's best candidate is the
    # same `shared` model (different families, so no family successor): the second
    # choice must see the first one's pick as taken.
    entries = [
        ent("mech", "m", "2026-01-01", 5.0),
        ent("std", "s", "2026-01-01", 5.0),
        ent("hard", "h", "2026-01-01", 20.0),
        ent("orch", "o", "2026-01-01", 5.0),
        ent("shared", "x", "2026-03-01", 5.0),
        ent("second", "y", "2026-02-01", 5.0),
    ]
    prober = FakeProber(entries, dead={f"{P}/mech": None, f"{P}/std": None})
    got = {h.tier: h for h in run(prober, tmp=tmp_path)}
    picks = [got["mechanical"].proposal, got["standard"].proposal]
    assert all(isinstance(p, Choice) for p in picks)
    assert picks[0].model != picks[1].model  # type: ignore[union-attr]
    assert {p.model for p in picks} == {f"{P}/shared", f"{P}/second"}  # type: ignore[union-attr]


def test_propose_for_remembers_the_snapshot_and_chooses(tmp_path: Path) -> None:
    from fr.bindings.health import propose_for

    prober = FakeProber(ENTRIES, dead={})
    snaps = SnapshotStore(tmp_path / "snap.json")
    bound = {"standard": f"{P}/std"}
    chosen = propose_for("standard", f"{P}/std", None, bound, prober, snapshots=snaps)
    assert chosen == Choice(f"{P}/std2", "family", 1.0)
    assert snaps.get(f"{P}/std") is not None  # R3: the dead model's entry was kept
