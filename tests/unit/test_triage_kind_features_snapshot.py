"""Wave-driver phase 4: `kind`, `features`, the unplaced set and snapshots
(spec R9, R17; Test Plan 8 and 13). Every state directory is under tmp_path.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from fr.triage.check import classify
from fr.triage.errors import TriageError
from fr.triage.model import Judgements, load_judgements
from fr.triage.snapshot import (
    KEEP,
    Transition,
    diff_snapshots,
    latest_snapshot,
    store_snapshot,
    take_snapshot,
)

from tests.unit.triage_board_fixtures import busy, facts, healthy, issue, j, judgements, pr

T0 = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)

# ---------------------------------------------------------------- kind, features


@pytest.mark.parametrize("schema", [1, 2, 3])
def test_kind_and_features_load_on_any_schema(tmp_path: Path, schema: int) -> None:
    doc = {
        "schema": schema,
        "tiers": [{"n": 1, "title": "Now"}],
        "issues": {
            "widgets#1": {"tier": 1, "kind": "defect"},
            "widgets#2": {"tier": 1, "kind": "parked"},
            "widgets#3": {"tier": 1},
        },
        "features": [
            {"rank": 1, "title": "Big", "ids": ["Widgets#3"], "why": "w", "start": "/fr-goal x"}
        ],
    }
    path = tmp_path / "judgements.yaml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    loaded = load_judgements(path)
    assert [loaded.issues[k].kind for k in ("widgets#1", "widgets#2", "widgets#3")] == [
        "defect",
        "parked",
        None,
    ]
    (feature,) = loaded.features
    assert (feature.rank, feature.title, feature.why, feature.start) == (
        1,
        "Big",
        "w",
        "/fr-goal x",
    )
    assert feature.ids == ["widgets#3"], "ids are normalised like every other key"
    assert Judgements.model_validate(loaded.model_dump(mode="json", by_alias=True)) == loaded


def test_an_unknown_kind_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(
        yaml.safe_dump(
            {"tiers": [{"n": 1, "title": "t"}], "issues": {"widgets#1": {"tier": 1, "kind": "x"}}}
        ),
        encoding="utf-8",
    )
    with pytest.raises(TriageError):
        load_judgements(path)


def test_a_file_with_no_kind_or_features_loads_as_before() -> None:
    loaded = Judgements.model_validate({"schema": 1})
    assert loaded.features == []


# ------------------------------------------------------------------- unplaced


def test_unplaced_is_every_open_issue_in_no_open_batch_feature_or_parked() -> None:
    f, jd = busy()
    got = {i.key for i in classify(f, jd).unplaced}
    # 7: member of a CANCELLED batch; 8: judged, in nothing; 9: no judgement at all.
    assert got == {"widgets#7", "widgets#8", "widgets#9"}


def test_unplaced_json_and_command_name_them(tmp_path: Path) -> None:
    f, jd = busy()
    out = classify(f, jd).to_json()
    assert {r["key"] for r in out["unplaced"]} == {"widgets#7", "widgets#8", "widgets#9"}


def test_a_closed_issue_is_never_unplaced_and_a_merged_batch_with_an_open_member_is() -> None:
    merged = pr(10, "feat/batch-m", state="MERGED")
    f = facts([issue(1, state="closed", prs=[merged]), issue(2, prs=[merged])])
    jd = judgements(
        {"widgets#1": j(), "widgets#2": j()},
        [
            {
                "id": "m",
                "title": "m",
                "ids": ["widgets#1", "widgets#2"],
                "wave": 1,
                "events": [
                    {
                        "kind": "dispatch",
                        "at": "2026-10-01T10:00:00Z",
                        "runner": "r",
                        "handle": "h",
                        "branch": "feat/batch-m",
                    }
                ],
            }
        ],
    )
    # the batch is `partial` (a member is still open): closed out, so its open member
    # is in no OPEN batch.
    assert {i.key for i in classify(f, jd).unplaced} == {"widgets#2"}


def test_a_parked_issue_and_a_feature_member_are_placed_without_a_batch() -> None:
    f = facts([issue(1), issue(2), issue(3)])
    jd = judgements(
        {"widgets#1": j(kind="parked"), "widgets#2": j(kind="feature"), "widgets#3": j()},
        features=[{"rank": 1, "title": "F", "ids": ["widgets#2"]}],
    )
    assert {i.key for i in classify(f, jd).unplaced} == {"widgets#3"}


def test_a_feature_kind_issue_in_no_group_is_unplaced() -> None:
    f = facts([issue(1)])
    jd = judgements({"widgets#1": j(kind="feature")})
    assert {i.key for i in classify(f, jd).unplaced} == {"widgets#1"}


# ------------------------------------------------------------------ snapshots


def test_a_first_render_has_no_earlier_snapshot(tmp_path: Path) -> None:
    assert latest_snapshot(tmp_path) is None


def test_a_snapshot_is_stored_under_a_utc_timestamp_name_and_read_back(tmp_path: Path) -> None:
    f, jd = busy()
    snap = take_snapshot(f, jd, acceptance=None)
    path = store_snapshot(tmp_path, snap, T0)
    assert path.parent == tmp_path / "snapshots"
    assert path.name.endswith("Z.json") and path.name.startswith("20261002T120000")
    assert latest_snapshot(tmp_path) == snap


def test_a_corrupt_snapshot_is_treated_as_absent(tmp_path: Path) -> None:
    f, jd = busy()
    good = take_snapshot(f, jd, acceptance=None)
    store_snapshot(tmp_path, good, T0)
    bad = tmp_path / "snapshots" / "20261002T130000000000Z.json"
    bad.write_text("{ not json", encoding="utf-8")
    assert latest_snapshot(tmp_path) == good, "the newest READABLE snapshot is the previous one"
    for p in (tmp_path / "snapshots").glob("*.json"):
        p.write_text(json.dumps({"schema": 99}), encoding="utf-8")
    assert latest_snapshot(tmp_path) is None


def test_retention_keeps_the_latest_thirty(tmp_path: Path) -> None:
    f, jd = busy()
    snap = take_snapshot(f, jd, acceptance=None)
    for n in range(KEEP + 7):
        store_snapshot(tmp_path, snap, T0 + timedelta(minutes=n))
    names = sorted(p.name for p in (tmp_path / "snapshots").glob("*.json"))
    assert len(names) == KEEP == 30
    assert names[0].startswith("20261002T120700"), "the seven oldest were dropped"


def test_a_snapshot_records_stages_states_prs_acceptance_and_figures() -> None:
    f, jd = busy()
    snap = take_snapshot(f, jd, acceptance={"row-a": "ci", "row-b": "skipped"})
    assert snap.batches["a-merged"] == "merged"
    assert snap.batches["c-red"] == "pr-open"
    assert snap.issues["widgets#1"].state == "closed" and snap.issues["widgets#1"].tier == 1
    assert snap.prs["example-org/widgets#12"].state == "OPEN"
    assert snap.prs["example-org/widgets#12"].checks == {"pass": 1, "fail": 2, "pending": 0}
    assert snap.acceptance is not None and snap.acceptance.counts == {"ci": 1, "skipped": 1}
    assert snap.figures["unplaced"] == 3 and snap.figures["open"] == 11


def test_the_diff_lists_exactly_what_changed() -> None:
    f1, jd1 = busy()
    before = take_snapshot(f1, jd1, acceptance={"row-a": "skipped", "row-b": "ci"})

    # the draft PR is merged (issues 3 and 4 close), issue 14 is filed, the red PR
    # is closed, batch e-next is dispatched, one acceptance row moves.
    merged_draft = pr(11, "feat/batch-b-draft", state="MERGED")
    closed_red = pr(12, "feat/batch-c-red", state="CLOSED")
    issues = []
    for i in f1.issues:
        d = i.model_dump(mode="json")
        if i.number in (3, 4):
            d.update(state="closed", prs=[merged_draft])
        if i.number == 5:
            d.update(prs=[closed_red])
        issues.append(d)
    issues.append(issue(14))
    f2 = facts(issues, config={"example-org/widgets": {"post_merge": ["make", "deploy"]}})
    after = take_snapshot(f2, jd1, acceptance={"row-a": "ci", "row-b": "ci", "row-c": "ci"})

    d = diff_snapshots(before, after)
    assert d is not None
    assert sorted(d.merged_or_closed) == [
        "PR example-org/widgets#11 merged",
        "PR example-org/widgets#12 closed",
        "widgets#3 closed",
        "widgets#4 closed",
    ]
    assert d.filed == ["widgets#14"]
    assert d.stage_changes == ["b-draft: pr-open -> merged", "c-red: pr-open -> abandoned"]
    assert d.acceptance_moved == ["row-a: skipped -> ci", "row-c: added as ci"]
    assert ("open", before.figures["open"], after.figures["open"]) in d.figures_changed
    assert all(a != b for _, a, b in d.figures_changed)
    assert d.empty is False


def test_the_diff_also_holds_one_structured_transition_per_change() -> None:
    f1, jd1 = busy()
    before = take_snapshot(f1, jd1, acceptance={"row-a": "skipped", "row-b": "ci"})
    merged_draft = pr(11, "feat/batch-b-draft", state="MERGED")
    issues = []
    for i in f1.issues:
        d = i.model_dump(mode="json")
        if i.number in (3, 4):
            d.update(state="closed", prs=[merged_draft])
        issues.append(d)
    issues.append(issue(14))
    f2 = facts(issues, config={"example-org/widgets": {"post_merge": ["make", "deploy"]}})
    after = take_snapshot(f2, jd1, acceptance={"row-a": "ci", "row-b": "ci", "row-c": "ci"})
    d = diff_snapshots(before, after)
    assert d is not None
    by_change: dict[str, list[Transition]] = {}
    for t in d.transitions:
        by_change.setdefault(t.change, []).append(t)
    # same count per kind as the string groups
    assert len(by_change["merged-or-closed"]) == len(d.merged_or_closed)
    assert len(by_change["filed"]) == len(d.filed)
    assert len(by_change["batch-stage"]) == len(d.stage_changes)
    assert len(by_change["acceptance"]) == len(d.acceptance_moved)
    assert len(by_change["figure"]) == len(d.figures_changed)
    assert set(by_change) <= {"merged-or-closed", "filed", "batch-stage", "acceptance", "figure"}
    stage = by_change["batch-stage"][0]
    assert (stage.item, stage.batch, stage.before, stage.after) == (
        "b-draft",
        "b-draft",
        "pr-open",
        "merged",
    )
    assert by_change["filed"][0].item == "widgets#14" and by_change["filed"][0].batch is None
    assert {t.item for t in by_change["acceptance"]} == {"row-a", "row-c"}
    moved = next(t for t in by_change["acceptance"] if t.item == "row-a")
    assert (moved.before, moved.after) == ("skipped", "ci")
    assert d.acceptance_note is None


def test_an_identical_pair_has_an_empty_diff() -> None:
    f, jd = busy()
    snap = take_snapshot(f, jd, acceptance=None)
    d = diff_snapshots(snap, snap)
    assert d is not None and d.empty is True


def test_no_previous_means_no_diff() -> None:
    f, jd = healthy()
    assert diff_snapshots(None, take_snapshot(f, jd, acceptance=None)) is None


# ------------------------------------------------------------ the render command


def _state(tmp_path: Path) -> Path:
    f, jd = busy()
    (tmp_path / "facts.json").write_text(json.dumps(f.to_json()), encoding="utf-8")
    (tmp_path / "judgements.yaml").write_text(
        yaml.safe_dump(jd.model_dump(mode="json", by_alias=True, exclude_none=True)),
        encoding="utf-8",
    )
    return tmp_path


def _render(tmp_path: Path) -> str:
    from fr.cli import app
    from typer.testing import CliRunner

    result = CliRunner().invoke(
        app, ["triage", "render", "--repo", "example-org/widgets", "--dir", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    return (tmp_path / "triage.html").read_text(encoding="utf-8")


def test_every_render_stores_a_snapshot_and_the_second_diffs_against_the_first(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    first = _render(state)
    assert "No earlier snapshot" in first
    assert len(list((state / "snapshots").glob("*.json"))) == 1

    facts_doc = json.loads((state / "facts.json").read_text(encoding="utf-8"))
    facts_doc["issues"].append(issue(40))
    (state / "facts.json").write_text(json.dumps(facts_doc), encoding="utf-8")
    second = _render(state)
    assert "No earlier snapshot" not in second
    assert "<td>widgets#40</td>" in second
    assert len(list((state / "snapshots").glob("*.json"))) == 2


def test_the_check_command_prints_the_unplaced_set(tmp_path: Path) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    state = _state(tmp_path)
    result = CliRunner().invoke(
        app, ["triage", "check", "--repo", "example-org/widgets", "--dir", str(state)]
    )
    assert result.exit_code == 0
    assert "unplaced (3)" in result.output
    assert "widgets#9" in result.output
