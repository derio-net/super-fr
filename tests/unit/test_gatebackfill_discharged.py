"""`discharged_evidence`: positive evidence only (spec 2026-11-08-sweep-fixes R14)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.gatebackfill.close import EvidenceReader, discharged_evidence
from fr.journal.model import JournalEntry, append_journal_entry, journal_path, owed_body

from tests.unit.acceptance_helpers import write_matrix_fragments
from tests.unit.gatebackfill_fixtures import (
    SP,
    commit_at,
    git,
    make_repo,
    publish,
    row,
    write_matrix,
)
from tests.unit.test_merge_evidence import _write_plan

PLAN = "2026-10-20-ops"
SLUG = "2026-10-20-widget"
SPEC = f"{SP}/specs/{SLUG}-design.md"
CREATED = "2026-10-11T10:00:00+00:00"


@pytest.fixture(autouse=True)
def _hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def owed(root: Path, key: str, *, entry_id: str = "owed-1", slug: str = "some-slug") -> None:
    entry = JournalEntry(
        kind="owed", scope="spec", id=entry_id, created=CREATED, title="owed",
        body=owed_body(what="w", why="y", how="h", key=key),
    )  # fmt: skip
    append_journal_entry(journal_path(root, "spec", slug), slug, entry)


def resolve(root: Path, entry_id: str = "owed-1", *, state: str = "fixed") -> None:
    entry = JournalEntry(
        kind="finding", scope="spec", id=f"{entry_id}-resolved", created=CREATED,
        title="resolves", resolves=entry_id, state=state,  # type: ignore[arg-type]
    )  # fmt: skip
    append_journal_entry(journal_path(root, "spec", "some-slug"), "some-slug", entry)


def outcome(root: Path, entry_id: str, kind: str = "discovery", key: str | None = None) -> None:
    body = owed_body(what="w", why="y", how="h", key=key) if key else "Step: s\n\nEvidence: e"
    entry = JournalEntry(
        kind=kind, scope="spec", id=entry_id, created=CREATED,  # type: ignore[arg-type]
        title="Test Plan step", body=body,
    )  # fmt: skip
    append_journal_entry(journal_path(root, "spec", SLUG), SLUG, entry)


BROKEN_JOURNAL = "<!-- fr:journal kind=nonsense scope=spec id=x created=never -->\n### x\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = make_repo(tmp_path)
    spec = root / SPEC
    spec.parent.mkdir(parents=True)
    spec.write_text("# Widget\n\n## Test Plan\n\n1. one\n2. two\n")
    commit_at(root, "spec", "2026-10-30T00:00:00+00:00")
    publish(root)
    return root


# --- rows -----------------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["walked", "manual", "ci", "scheduled"])
def test_a_row_outside_the_debt_statuses_is_discharged(repo: Path, status: str) -> None:
    write_matrix(repo, [row("r1", status)])
    evidence = discharged_evidence(repo, "row:r1")
    assert evidence is not None and status in evidence and "r1" in evidence
    assert "\n" not in evidence


@pytest.mark.parametrize("status", ["walk-owed", "not-implemented", "unwired", "failing"])
def test_a_row_in_a_debt_status_is_not(repo: Path, status: str) -> None:
    write_matrix(repo, [row("r1", status)])
    assert discharged_evidence(repo, "row:r1") is None


def test_a_missing_row_is_not(repo: Path) -> None:
    write_matrix(repo, [row("r1", "walked")])
    assert discharged_evidence(repo, "row:gone") is None


def test_an_unreadable_matrix_discharges_nothing(repo: Path) -> None:
    _write_plan(repo, PLAN, [("manual", True)])
    owed(repo, "row:r1")
    resolve(repo)
    write_matrix_fragments(repo, "rows: [unclosed\n")
    assert discharged_evidence(repo, "row:r1") is None
    assert discharged_evidence(repo, f"plan:{PLAN}#p1") is None


# --- plan phases ----------------------------------------------------------------------------


def test_a_phase_with_every_step_ticked_or_na_is_discharged(repo: Path) -> None:
    plan_dir = _write_plan(repo, PLAN, [("manual", True), ("manual", False)])
    doc = yaml.safe_load((plan_dir / "02.yaml").read_text())
    doc["state"]["steps"]["P2.T1.S1"]["state"] = "-"
    (plan_dir / "02.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    first = discharged_evidence(repo, f"plan:{PLAN}#p1")
    assert first is not None and "1/1" in first
    assert discharged_evidence(repo, f"plan:{PLAN}#p2") is not None


def test_a_part_ticked_phase_is_not(repo: Path) -> None:
    plan_dir = _write_plan(repo, PLAN, [("manual", True)])
    doc = yaml.safe_load((plan_dir / "01.yaml").read_text())
    step = dict(doc["tasks"][0]["steps"][0], id="P1.T1.S2")
    doc["tasks"][0]["steps"].append(step)
    doc["state"]["steps"]["P1.T1.S2"] = {"state": " ", "ticked_at": None, "note": None}
    (plan_dir / "01.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))
    assert discharged_evidence(repo, f"plan:{PLAN}#p1") is None


def test_a_zero_step_phase_is_not(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_plan(repo, PLAN, [("manual", True)])
    monkeypatch.setattr("fr.gatebackfill.candidates._phase_facts", lambda *a: (True, "0/0", False))
    assert discharged_evidence(repo, f"plan:{PLAN}#p1") is None


def test_an_absent_or_unreadable_plan_is_not(repo: Path) -> None:
    plan_dir = _write_plan(repo, PLAN, [("manual", True)])
    assert discharged_evidence(repo, f"plan:{PLAN}#p9") is None
    assert discharged_evidence(repo, "plan:no-such-plan#p1") is None
    (plan_dir / "01.yaml").write_text("not: [a plan\n")
    assert discharged_evidence(repo, f"plan:{PLAN}#p1") is None


# --- spec steps -----------------------------------------------------------------------------


def test_a_step_with_a_ran_or_na_outcome_is_discharged(repo: Path) -> None:
    outcome(repo, "test-plan-step-1")
    evidence = discharged_evidence(repo, f"spec:{SLUG}#step1")
    assert evidence is not None and "step 1" in evidence


def test_a_step_with_no_outcome_is_not(repo: Path) -> None:
    outcome(repo, "test-plan-step-1")
    assert discharged_evidence(repo, f"spec:{SLUG}#step2") is None


def test_an_owed_outcome_is_not(repo: Path) -> None:
    outcome(repo, "test-plan-step-1", "owed", key=f"spec:{SLUG}#step1")
    assert discharged_evidence(repo, f"spec:{SLUG}#step1") is None


def test_an_outcome_superseded_to_owed_is_not(repo: Path) -> None:
    """The effective fold, never `archive.recorded_outcomes`, which counts both."""
    outcome(repo, "test-plan-step-1")
    outcome(repo, "test-plan-step-1-2", "owed", key=f"spec:{SLUG}#step1")
    assert discharged_evidence(repo, f"spec:{SLUG}#step1") is None


def test_an_open_owed_entry_superseded_to_ran_is_still_held_by_the_journal(repo: Path) -> None:
    """The effective outcome reads ran, but the fold's journal source still holds the key."""
    outcome(repo, "test-plan-step-1", "owed", key=f"spec:{SLUG}#step1")
    outcome(repo, "test-plan-step-1-2")
    assert discharged_evidence(repo, f"spec:{SLUG}#step1") is None


def test_a_step_of_a_spec_this_checkout_does_not_hold_is_not(repo: Path) -> None:
    assert discharged_evidence(repo, "spec:no-such-spec#step1") is None


def test_an_unreadable_spec_journal_is_not(repo: Path) -> None:
    outcome(repo, "test-plan-step-1")
    journal_path(repo, "spec", SLUG).write_text(BROKEN_JOURNAL)
    assert discharged_evidence(repo, f"spec:{SLUG}#step1") is None


# --- the journal route ----------------------------------------------------------------------


def test_a_journal_owed_entry_resolved_fixed_discharges_any_kind(repo: Path) -> None:
    owed(repo, "row:not-a-row")
    resolve(repo)
    evidence = discharged_evidence(repo, "row:not-a-row")
    assert evidence is not None and "fixed" in evidence


def test_an_open_journal_owed_entry_holds_the_key_over_a_walked_row(repo: Path) -> None:
    write_matrix(repo, [row("r1", "walked")])
    owed(repo, "row:r1")
    assert discharged_evidence(repo, "row:r1") is None


def test_a_second_journal_still_owing_the_key_holds_it(repo: Path) -> None:
    owed(repo, "row:not-a-row")
    resolve(repo)
    owed(repo, "row:not-a-row", entry_id="owed-2", slug="other-slug")
    assert discharged_evidence(repo, "row:not-a-row") is None


def test_an_owed_entry_closed_by_anything_but_fixed_is_not_evidence(repo: Path) -> None:
    owed(repo, "row:not-a-row")
    resolve(repo, state="refuted")
    assert discharged_evidence(repo, "row:not-a-row") is None


def test_a_walk_owed_row_holds_a_key_its_journal_entry_resolved(repo: Path) -> None:
    write_matrix(repo, [row("r1", "walk-owed")])
    owed(repo, "row:r1")
    resolve(repo)
    assert discharged_evidence(repo, "row:r1") is None


def test_an_unticked_merged_manual_phase_holds_a_key_its_journal_entry_resolved(
    repo: Path,
) -> None:
    _write_plan(repo, PLAN, [("agentic", True), ("manual", False)])
    commit_at(repo, "plan", "2026-10-30T00:00:00+00:00")
    publish(repo)
    owed(repo, f"plan:{PLAN}#p2")
    resolve(repo)
    assert discharged_evidence(repo, f"plan:{PLAN}#p2") is None


def test_any_unreadable_journal_discharges_nothing(repo: Path) -> None:
    write_matrix(repo, [row("r1", "walked")])
    path = journal_path(repo, "plan", "broken")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BROKEN_JOURNAL)
    assert discharged_evidence(repo, "row:r1") is None


# --- never ----------------------------------------------------------------------------------


def test_an_issue_key_is_never_discharged_even_with_a_fixed_journal_entry(repo: Path) -> None:
    owed(repo, "issue:example-org/widgets#5")
    resolve(repo)
    assert discharged_evidence(repo, "issue:example-org/widgets#5") is None


@pytest.mark.parametrize(
    "key", ["", "row:", "plan:..#p1", "plan:../../etc#p1", "spec:x", "nonsense:y", "row:a b"]
)
def test_a_malformed_key_is_never_discharged(repo: Path, key: str) -> None:
    assert discharged_evidence(repo, key) is None


def test_a_missing_checkout_discharges_nothing_and_never_raises() -> None:
    assert discharged_evidence(Path("/nonexistent"), "row:r1") is None
    assert discharged_evidence(Path("/nonexistent"), "plan:p#p1") is None


# --- the phase 4 review -----------------------------------------------------------------------


@pytest.mark.parametrize("status", ["failing", "not-implemented", "unwired", "walk-owed"])
def test_p4_r1_a_row_in_a_debt_status_is_never_discharged_by_its_journal(
    repo: Path, status: str
) -> None:
    write_matrix(repo, [row("r1", status)])
    owed(repo, "row:r1")
    resolve(repo)
    assert discharged_evidence(repo, "row:r1") is None


def test_p4_r1_a_non_debt_row_with_a_resolved_entry_stays_discharged(repo: Path) -> None:
    write_matrix(repo, [row("r1", "walked")])
    owed(repo, "row:r1")
    resolve(repo)
    assert discharged_evidence(repo, "row:r1") is not None


@pytest.mark.parametrize("kind", ["decision", "finding"])
def test_p4_r2_an_entry_of_another_kind_named_like_a_step_is_not_an_outcome(
    repo: Path, kind: str
) -> None:
    entry = JournalEntry(
        kind=kind, scope="spec", id="test-plan-step-1", created=CREATED,  # type: ignore[arg-type]
        title="not an outcome", state="open" if kind == "finding" else None,
    )  # fmt: skip
    append_journal_entry(journal_path(repo, "spec", SLUG), SLUG, entry)
    assert discharged_evidence(repo, f"spec:{SLUG}#step1") is None


@pytest.mark.parametrize(
    "flags", [["--ran", "--evidence", "it ran"], ["--na", "--reason", "does not apply"]]
)
def test_p4_r2_what_closeout_outcome_writes_reads_as_discharged(
    repo: Path, monkeypatch: pytest.MonkeyPatch, flags: list[str]
) -> None:
    from fr.cli import app
    from typer.testing import CliRunner

    monkeypatch.chdir(repo)
    git(repo, "checkout", "-q", "-b", "work")
    args = ["closeout", "outcome", "--spec", SPEC, "--step", "1", *flags]
    result = CliRunner().invoke(app, args, env={"FR_SKIP_MIGRATION": "1"})
    assert result.exit_code == 0, result.output
    assert discharged_evidence(repo, f"spec:{SLUG}#step1") is not None


def test_p4_r2_an_owed_step_resolved_fixed_reads_as_discharged(repo: Path) -> None:
    from fr.journal.model import JournalEntry as Entry

    outcome(repo, "test-plan-step-1", "owed", key=f"spec:{SLUG}#step1")
    record = Entry(
        kind="finding", scope="spec", id="r", created=CREATED, title="r",
        resolves="test-plan-step-1", state="fixed",
    )  # fmt: skip
    append_journal_entry(journal_path(repo, "spec", SLUG), SLUG, record)
    assert discharged_evidence(repo, f"spec:{SLUG}#step1") is not None


def test_p4_r11_one_reader_parses_each_journal_once(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.journal.model as journal_model

    outcome(repo, "test-plan-step-1")
    outcome(repo, "test-plan-step-2")
    owed(repo, "row:not-a-row")
    resolve(repo)
    real, parsed = journal_model.parse_journal, []

    def counting(text: str) -> list[JournalEntry]:
        parsed.append(text)
        return real(text)

    monkeypatch.setattr(journal_model, "parse_journal", counting)
    reader = EvidenceReader(repo)
    for key in (f"spec:{SLUG}#step1", f"spec:{SLUG}#step2", "row:not-a-row"):
        assert discharged_evidence(repo, key, reader=reader) is not None
    assert len(parsed) == len(set(parsed)) == 2, "a journal was parsed more than once"
