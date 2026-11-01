"""Candidates and their gates (spec 2026-11-01-gate-backfill §B, §D, R2, R4, R5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.gatebackfill.candidates import collect_candidates, gate_for, split_key
from fr.gatebackfill.model import BackfillError, PlanEntry, PlanFile, parse_manifest

from tests.unit.gatebackfill_fixtures import (
    NOW,
    REPO,
    SP,
    STRANGER,
    FakeForge,
    commit_at,
    issue,
    make_repo,
    publish,
    row,
    write_matrix,
)
from tests.unit.test_merge_evidence import _write_plan


@pytest.fixture(autouse=True)
def _hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _collect(repo: Path, forge: FakeForge | None = None, **kw: object):  # type: ignore[no-untyped-def]
    cands, notes = collect_candidates(repo, forge=forge or FakeForge(), now=NOW, **kw)  # type: ignore[arg-type]
    return {c.key: c for c in cands}, notes


def _publish_at(repo: Path, iso: str) -> None:
    commit_at(repo, "seed", iso)
    publish(repo)


def _marker_issue(n: int, key: str) -> dict[str, object]:
    return issue(n, f"owed {key}", f"Owed.\n\n<!-- fr-owed:{key} -->")


def test_a_walk_owed_row_is_a_tester_walk_only_candidate(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_matrix(repo, [row("r1", "walk-owed"), row("r2", "ci")])
    _publish_at(repo, "2026-10-30T00:00:00+00:00")

    cands, _ = _collect(repo)

    assert list(cands) == ["row:r1"]
    assert cands["row:r1"].gate == "tester" and cands["row:r1"].walk_only
    assert cands["row:r1"].decision == "owed"


def test_manual_and_agentic_open_phases_get_devops_and_no_gate(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _write_plan(repo, "2026-10-20-ops", [("agentic", True), ("manual", False)])
    _write_plan(repo, "2026-10-21-code", [("agentic", True)])
    _publish_at(repo, "2026-10-30T00:00:00+00:00")
    forge = FakeForge()  # an agentic phase is owed only through a tracker or a journal entry
    forge.issues = [_marker_issue(7, "plan:2026-10-21-code#p1")]

    cands, _ = _collect(repo, forge)

    manual = cands["plan:2026-10-20-ops#p2"]
    assert manual.gate == "devops" and manual.decision == "owed" and manual.ticked == "0/1"
    agentic = cands["plan:2026-10-21-code#p1"]
    assert agentic.gate is None and agentic.decision == "review"
    assert "unfinished agentic phase" in agentic.why


def test_a_stale_manual_phase_defaults_to_review_with_its_age(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _write_plan(repo, "2026-04-02-fleet", [("manual", False)])
    _publish_at(repo, "2026-04-02T00:00:00+00:00")

    cands, _ = _collect(repo, stale_days=30)

    c = cands["plan:2026-04-02-fleet#p1"]
    assert c.decision == "review" and c.age_days == 213 and c.ticked == "0/1"
    assert "stale" in c.why and c.gate == "devops"


def _spec(repo: Path, slug: str, verification: str) -> None:
    d = repo / SP / "specs"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"2026-05-01-{slug}-design.md").write_text(
        f"# {slug}\n\n## Verification\n\n{verification}\n\n## Test Plan\n\n1. walk it\n"
    )


def test_an_owed_test_plan_step_is_devops_when_the_spec_gate_is_devops(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _spec(repo, "ops-thing", "strategy: candidate\ngate: devops")
    _spec(repo, "walk-thing", "strategy: candidate\ngate: tester")
    _publish_at(repo, "2026-10-30T00:00:00+00:00")
    forge = FakeForge()
    forge.issues = [
        _marker_issue(5, "spec:2026-05-01-ops-thing#step1"),
        _marker_issue(6, "spec:2026-05-01-walk-thing#step1"),
    ]

    cands, _ = _collect(repo, forge)

    assert cands["spec:2026-05-01-ops-thing#step1"].gate == "devops"
    assert cands["spec:2026-05-01-walk-thing#step1"].gate == "tester"
    assert cands["spec:2026-05-01-ops-thing#step1"].tracker_ref == f"{REPO}#5"


def test_an_issue_candidate_has_no_gate_unless_the_manifest_gives_one(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _publish_at(repo, "2026-10-30T00:00:00+00:00")
    forge = FakeForge()
    forge.issues = [issue(60, "an old ask", "do the thing")]

    cands, _ = _collect(repo, forge)

    c = cands[f"issue:{REPO}#60"]
    assert c.gate is None and c.decision == "review" and "no gate" in c.why


def test_a_manifest_adds_entries_and_a_fold_key_is_an_error(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_matrix(repo, [row("r1", "walk-owed")])
    _publish_at(repo, "2026-10-30T00:00:00+00:00")
    manifest = parse_manifest(
        "schema: 1\nitems:\n"
        f"  - {{key: 'issue:{REPO}#37', kind: closed-issue, title: t, issue: 37, pr: 89}}\n"
        "  - {key: 'row:gap', kind: audit-gap, title: u, gate: devops}\n"
        "  - {key: 'plan:2026-01-01-x#p1', kind: op, title: v}\n"
    )

    cands, _ = _collect(repo, manifest=manifest)

    closed = cands[f"issue:{REPO}#37"]
    assert closed.gate == "tester" and closed.walk_only and closed.manifest_pr == 89
    assert closed.issue_number == 37
    assert cands["row:gap"].gate == "devops" and not cands["row:gap"].walk_only
    assert cands["plan:2026-01-01-x#p1"].gate == "devops"

    clash = parse_manifest("schema: 1\nitems:\n  - {key: 'row:r1', kind: walk, title: t}\n")
    with pytest.raises(BackfillError, match="row:r1"):
        _collect(repo, manifest=clash)


def test_tracker_issues_are_not_candidates_of_their_own(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _write_plan(repo, "2026-10-20-fleet", [("agentic", True), ("agentic", True), ("manual", False)])
    _publish_at(repo, "2026-10-30T00:00:00+00:00")
    forge = FakeForge()
    forge.issues = [
        issue(61, "adopted one", "x"),
        issue(62, "fleet phase 3 manual run", "2026-10-20-fleet: phase 3"),
        issue(
            63, "backfill tracker", "Owed.\n<!-- fr-gate:devops pr:41 -->\n<!-- fr-owed:bad key -->"
        ),
        issue(64, "plain one", "unrelated"),
    ]
    previous = PlanFile(
        repo=REPO,
        entries=[PlanEntry(key="row:x", decision=f"adopt {REPO}#61")],
    )

    cands, notes = _collect(repo, forge, previous=previous)

    assert f"issue:{REPO}#61" not in cands  # another entry's adopt target
    assert f"issue:{REPO}#63" not in cands  # carries a PR marker
    assert any("63" in n for n in notes)
    looks = cands[f"issue:{REPO}#62"]
    assert looks.decision == "review"
    assert "looks like the tracker of plan:2026-10-20-fleet#p3" in looks.why
    assert cands["plan:2026-10-20-fleet#p3"].tracker_candidates == (f"{REPO}#62",)
    assert f"issue:{REPO}#64" in cands


def test_a_failed_issue_read_degrades_look_alikes_only(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_matrix(repo, [row("r1", "walk-owed")])
    _publish_at(repo, "2026-10-30T00:00:00+00:00")

    class Broken(FakeForge):
        def open_issues(self):  # type: ignore[no-untyped-def]
            raise RuntimeError("boom")

    cands, notes = _collect(repo, Broken())

    assert "row:r1" in cands
    assert any("open issues not read" in n for n in notes)


def test_gate_for_is_the_spec_table() -> None:
    assert gate_for("row:a") == "tester"
    assert gate_for("plan:p#p1", manual_phase=True) == "devops"
    assert gate_for("plan:p#p1", manual_phase=False) is None
    assert gate_for("spec:s#step1", spec_run_gate="devops") == "devops"
    assert gate_for("spec:s#step1", spec_run_gate="tester") == "tester"
    assert gate_for("spec:s#step1") is None
    assert gate_for(f"issue:{REPO}#3") is None
    assert split_key("plan:2026-01-01-x#p2") == ("plan", "2026-01-01-x", 2)
    assert split_key("spec:s#step4") == ("spec", "s", 4)
    assert split_key("row:a-b") == ("row", "a-b", None)


def test_only_our_own_labelled_issues_are_trackers_or_hide_a_candidate(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_matrix(repo, [row("r1", "walk-owed"), row("r2", "walk-owed"), row("r3", "walk-owed")])
    _publish_at(repo, "2026-10-30T00:00:00+00:00")
    forge = FakeForge()
    forge.issues = [
        issue(70, "foreign", "x\n\n<!-- fr-owed:row:r1 -->", author=STRANGER),
        issue(71, "unlabelled", "x\n\n<!-- fr-owed:row:r2 -->", labels=()),
        issue(72, "ours", "x\n\n<!-- fr-owed:row:r3 -->"),
        issue(
            73,
            "foreign gate marker",
            "y\n<!-- fr-gate:devops pr:41 -->\n<!-- fr-owed:no key -->",
            author=STRANGER,
        ),
    ]

    cands, notes = _collect(repo, forge)

    assert cands["row:r1"].tracker_ref is None
    assert cands["row:r2"].tracker_ref is None
    assert cands["row:r3"].tracker_ref == f"{REPO}#72"
    assert f"issue:{REPO}#73" in cands  # a stranger's marker hides nothing
    assert not any("73" in n for n in notes)


def test_p1_r5_a_full_open_issue_page_is_reported_as_possibly_capped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.gatebackfill import candidates

    monkeypatch.setattr(candidates, "OPEN_ISSUE_LIMIT", 2)
    repo = make_repo(tmp_path)
    write_matrix(repo, [row("r1", "walk-owed")])
    _publish_at(repo, "2026-10-30T00:00:00+00:00")
    forge = FakeForge()
    forge.issues = [issue(80, "a", "x"), issue(81, "b", "y")]

    _, notes = _collect(repo, forge)
    assert any("2 open issues" in n and "cap" in n for n in notes)

    forge.issues = forge.issues[:1]
    _, quiet = _collect(repo, forge)
    assert not any("cap" in n for n in quiet)


def test_p1_r11_a_look_alike_never_names_any_fr_owned_tracker(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    write_matrix(repo, [row("r1", "walk-owed"), row("r2", "walk-owed")])
    _publish_at(repo, "2026-10-30T00:00:00+00:00")
    forge = FakeForge()
    forge.issues = [
        issue(90, "owed r2", "mentions r1 too\n\n<!-- fr-owed:row:r2 -->"),
        issue(91, "a stranger's r1", "r1 is broken", author=STRANGER, labels=()),
    ]

    cands, _ = _collect(repo, forge)

    assert cands["row:r2"].tracker_ref == f"{REPO}#90"
    assert cands["row:r1"].tracker_candidates == (f"{REPO}#91",)  # not r2's own tracker


def test_p1_r13_a_marker_key_that_is_a_path_never_reaches_the_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.gatebackfill import candidates

    seen: list[str] = []
    real = candidates._plan_dir

    def spy(root: Path, name: str):  # type: ignore[no-untyped-def]
        seen.append(name)
        return real(root, name)

    monkeypatch.setattr(candidates, "_plan_dir", spy)
    repo = make_repo(tmp_path)
    _publish_at(repo, "2026-10-30T00:00:00+00:00")
    forge = FakeForge()
    forge.issues = [_marker_issue(95, "plan:../../x#p1")]

    cands, notes = _collect(repo, forge)

    assert not any(".." in k for k in cands) and not any(".." in n for n in seen)
    assert any("plan:../../x#p1" in n and "dropped" in n for n in notes)


def test_p2_r3_a_manifest_cannot_take_back_a_key_a_row_holds_even_with_a_tracker(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    write_matrix(repo, [row("r3", "walk-owed")])
    _publish_at(repo, "2026-10-30T00:00:00+00:00")
    forge = FakeForge()
    forge.issues = [issue(72, "ours", "x\n\n<!-- fr-owed:row:r3 -->")]
    manifest = parse_manifest("schema: 1\nitems:\n  - {key: 'row:r3', kind: walk, title: t}\n")

    cands, _ = _collect(repo, forge)
    assert cands["row:r3"].tracker_ref == f"{REPO}#72"
    with pytest.raises(BackfillError, match="row:r3"):
        _collect(repo, forge, manifest=manifest)


def test_p2_r3_a_manifest_takes_back_a_key_only_fr_s_tracker_holds(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _publish_at(repo, "2026-10-30T00:00:00+00:00")
    forge = FakeForge()
    forge.issues = [issue(72, "ours", "x\n\n<!-- fr-owed:row:gap -->")]
    manifest = parse_manifest(
        "schema: 1\nitems:\n  - {key: 'row:gap', kind: audit-gap, title: t, gate: devops}\n"
    )

    cands, _ = _collect(repo, forge, manifest=manifest)

    assert cands["row:gap"].source == "manifest" and cands["row:gap"].gate == "devops"
