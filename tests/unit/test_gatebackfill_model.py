"""The gate-backfill plan file, manifest and decisions (spec 2026-11-01-gate-backfill §B, §E)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.gatebackfill.model import (
    BackfillError,
    PlanEntry,
    PlanFile,
    PrHit,
    load_plan,
    merge_plan,
    parse_manifest,
    plan_path,
    split_decision,
    write_plan,
)
from pydantic import ValidationError

REPO = "example-org/widgets"


def _entry(key: str = "plan:2026-04-02-fleet#p3", **kw: object) -> PlanEntry:
    return PlanEntry.model_validate({"key": key, "title": "t", "gate": "devops", **kw})


@pytest.mark.parametrize("d", ["owed", "tick", "na", "park", "review"])
def test_the_simple_decisions_parse(d: str) -> None:
    assert split_decision(d) == (d, None)


def test_adopt_names_an_issue_and_anything_else_is_refused() -> None:
    assert split_decision("adopt example-org/widgets#56") == ("adopt", "example-org/widgets#56")
    for bad in ("adopt", "adopt 56", "adopt example-org/widgets", "fix", "OWED", ""):
        with pytest.raises(BackfillError):
            split_decision(bad)
    with pytest.raises(ValidationError):
        _entry(decision="maybe")


def test_the_models_are_strict() -> None:
    with pytest.raises(ValidationError):
        PlanEntry(key="row:a", surprise=1)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        PlanFile.model_validate({"schema": 2, "repo": REPO})
    with pytest.raises(ValidationError):
        PlanEntry(key="row:a", gate="pre-merge")


def test_merge_keeps_the_decision_adopt_target_note_and_an_operator_gate() -> None:
    old = PlanFile(
        repo=REPO,
        entries=[
            _entry(decision="adopt example-org/widgets#56", note="checked", gate="tester"),
            _entry("row:gone", decision="park"),
        ],
    )
    fresh = [_entry(title="refreshed", age_days=9, pr=PrHit(number=41, basis="commit"))]

    [kept] = merge_plan(old, fresh)

    assert kept.decision == "adopt example-org/widgets#56"
    assert kept.note == "checked"
    assert kept.gate == "tester"  # the operator's, not the computed devops
    assert kept.title == "refreshed" and kept.age_days == 9 and kept.pr is not None
    assert merge_plan(None, fresh) == fresh


def test_merge_fills_a_gate_the_operator_wrote_over_a_none() -> None:
    old = PlanFile(repo=REPO, entries=[PlanEntry(key="row:a", gate="tester", decision="owed")])
    [kept] = merge_plan(old, [PlanEntry(key="row:a", gate=None, decision="review")])
    assert kept.gate == "tester" and kept.decision == "owed"


def test_the_plan_round_trips_under_home_and_plan_overrides_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    path = plan_path(REPO, None)
    assert path == tmp_path / ".cache/fr/gate-backfill/example-org--widgets/plan.yaml"
    assert load_plan(path) is None

    plan = PlanFile(repo=REPO, generated_at="2026-11-01T12:00:00Z", entries=[_entry()])
    write_plan(path, plan)

    assert load_plan(path) == plan
    assert yaml.safe_load(path.read_text())["schema"] == 1
    other = tmp_path / "elsewhere.yaml"
    assert plan_path(REPO, other) == other


def test_an_unreadable_plan_file_is_a_named_error(tmp_path: Path) -> None:
    bad = tmp_path / "plan.yaml"
    bad.write_text("schema: 1\nrepo: x/y\nentries: [{key: row:a, decision: nope}]\n")
    with pytest.raises(BackfillError, match="plan.yaml"):
        load_plan(bad)


def test_a_manifest_parses_and_each_refusal_names_its_entry() -> None:
    ok = parse_manifest(
        "schema: 1\nitems:\n"
        "  - {key: 'issue:example-org/widgets#37', kind: closed-issue, title: t, issue: 37}\n"
        "  - {key: 'row:gap', kind: audit-gap, title: t, gate: devops}\n"
    )
    assert [i.key for i in ok.items] == ["issue:example-org/widgets#37", "row:gap"]

    with pytest.raises(BackfillError, match=r"row:gap.*gate"):
        parse_manifest("schema: 1\nitems:\n  - {key: 'row:gap', kind: audit-gap, title: t}\n")
    with pytest.raises(BackfillError, match="row:odd"):
        parse_manifest(
            "schema: 1\nitems:\n  - {key: 'row:odd', kind: walk, title: t, colour: red}\n"
        )
    with pytest.raises(BackfillError, match="row:twice.*twice"):
        parse_manifest(
            "schema: 1\nitems:\n  - {key: 'row:twice', kind: walk, title: t}\n"
            "  - {key: 'row:twice', kind: walk, title: u}\n"
        )
    with pytest.raises(BackfillError):
        parse_manifest("schema: 2\nitems: []\n")
