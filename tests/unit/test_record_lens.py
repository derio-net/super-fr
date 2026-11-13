"""Record kind 12: a step record can add a review lens (spec 2026-11-12-review-lenses
R4, R5, §3.B).

A record's `journal:` item `{kind: lens, lens: <id>, title: <why>}` lands in the
step's journal as a `lens` entry: fr assigns its id (`lens-<id>-<n>`), stamps
`step=` from the record's own step and `phase=` from a phase unit (global in a plan
journal otherwise). The lens must be effective; an agent supplies neither the id nor
the step.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.journal.model import journal_path, parse_journal
from fr.record import apply as engine
from fr.record.model import RECORD_SCHEMA_VERSION, JournalItem, StepRecord, parse_record
from pydantic import ValidationError

from tests.unit.record_support import (
    RUN,
    SLUG,
    commit_all,
    fr,
    head,
    implement_record,
    snapshot,
    started_run,
    write_record,
)

LENS_ITEM = {"kind": "lens", "lens": "security", "title": "the retry path builds a shell command"}


def _resolve(root: Path, record: Path, step: str = "implement-phase", item: str | None = "phase/1"):
    argv = ["run", "resolve", RUN, "--step", step, "--record", str(record), "--no-advance"]
    if item is not None:
        argv += ["--item", item]
    return fr(root, argv)


def _lens_entries(root: Path, scope: str = "plan", slug: str = SLUG):
    return [
        e for e in parse_journal(journal_path(root, scope, slug).read_text()) if e.kind == "lens"
    ]  # type: ignore[arg-type]


# --- the model -------------------------------------------------------------------


def test_a_journal_item_takes_a_lens_on_a_lens_kind_only() -> None:
    item = JournalItem.model_validate(LENS_ITEM)
    assert item.lens == "security"
    with pytest.raises(ValidationError, match="lens"):
        JournalItem.model_validate({"kind": "decision", "title": "t", "lens": "security"})
    with pytest.raises(ValidationError, match="names its lens"):
        JournalItem.model_validate({"kind": "lens", "title": "t"})


def test_a_lens_item_refuses_an_agent_supplied_id_or_step() -> None:
    with pytest.raises(ValidationError, match="fr assigns"):
        JournalItem.model_validate({**LENS_ITEM, "id": "mine"})
    with pytest.raises(ValidationError, match="step"):
        JournalItem.model_validate({**LENS_ITEM, "step": "implement-phase"})


# --- applying it through a run record ---------------------------------------------


def test_a_run_record_adds_a_lens_entry_stamped_with_its_step_and_phase(tmp_path: Path) -> None:
    root = started_run(tmp_path)
    journal = [*implement_record()["journal"], LENS_ITEM]  # type: ignore[misc]
    record = write_record(root, implement_record(journal=journal))
    commit_all(root, "record")

    out = _resolve(root, record)

    assert out.exit_code == 0, out.output
    (entry,) = _lens_entries(root)
    assert entry.id == "lens-security-1"
    assert (entry.lens, entry.step, entry.phase) == ("security", "implement-phase", 1)
    assert entry.title == LENS_ITEM["title"]


def test_a_second_addition_of_the_same_lens_keeps_both(tmp_path: Path) -> None:
    root = started_run(tmp_path)
    again = {**LENS_ITEM, "title": "it also reads a token from the environment"}
    journal = [*implement_record()["journal"], LENS_ITEM, again]  # type: ignore[misc]
    record = write_record(root, implement_record(journal=journal))
    commit_all(root, "record")

    out = _resolve(root, record)

    assert out.exit_code == 0, out.output
    entries = _lens_entries(root)
    assert [e.id for e in entries] == ["lens-security-1", "lens-security-2"]
    assert [e.title for e in entries] == [LENS_ITEM["title"], again["title"]]


REFUSED = {
    "lens on another kind": ({"kind": "decision", "title": "t", "lens": "security"}, "lens"),
    "not effective": ({**LENS_ITEM, "lens": "no-such-lens"}, "no-such-lens"),
    "empty reason": ({**LENS_ITEM, "title": " "}, "reason"),
    "agent id": ({**LENS_ITEM, "id": "lens-security-9"}, "fr assigns"),
    "agent step": ({**LENS_ITEM, "step": "brainstorm"}, "step"),
}


@pytest.mark.parametrize("case", sorted(REFUSED))
def test_a_refused_lens_item_writes_nothing(tmp_path: Path, case: str) -> None:
    root = started_run(tmp_path)
    item, needle = REFUSED[case]
    record = write_record(root, implement_record(journal=[item]))
    commit_all(root, "record")
    before, files = head(root), snapshot(root)

    out = _resolve(root, record)

    assert out.exit_code == 2, out.output
    assert needle in out.output
    assert snapshot(root) == files
    assert head(root) == before


def test_a_disabled_lens_is_not_effective_and_is_refused(tmp_path: Path) -> None:
    root = started_run(tmp_path)
    (root / ".fr").mkdir(exist_ok=True)
    (root / ".fr" / "lenses.yaml").write_text("disable: [security]\n")
    record = write_record(root, implement_record(journal=[LENS_ITEM]))
    commit_all(root, "record")

    out = _resolve(root, record)

    assert out.exit_code == 2, out.output
    assert "security" in out.output


def test_a_plan_journal_lens_with_no_phase_unit_is_global(tmp_path: Path) -> None:
    root = started_run(tmp_path)
    outcome = engine.apply_record(
        root,
        None,
        StepRecord(journal=(JournalItem.model_validate(LENS_ITEM),)),
        target=engine.RecordTarget(journal_scope="plan", journal_slug=SLUG, message="m"),
    )
    assert outcome.committed
    (entry,) = _lens_entries(root)
    assert entry.phase is None and entry.step is None


# --- record version 12 ----------------------------------------------------------------

_V11 = """\
schema_version: 11
run: r1
step: implement-phase
item: phase/1
outcome: done
ticks: [P1.T1.S1]
journal:
  - {kind: decision, id: d1, title: kept it flat, phase: 1}
"""


def _record_file(root: Path, text: str = _V11) -> Path:
    path = root / "docs" / "superpowers" / "runs" / "r1.records" / "implement-phase__phase-1.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_record_kind_is_at_version_twelve() -> None:
    assert RECORD_SCHEMA_VERSION == 12
    assert artifact_kind("record").current_version == 12


def test_the_record_chain_from_one_reaches_twelve_hop_by_hop() -> None:
    chain = MIGRATIONS.chain("record", PRE_FRAMEWORK_VERSION)
    assert [s.to_version for s in chain] == [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    assert [s.from_version for s in chain] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    hop = MIGRATIONS.chain("record", 11)[0]
    assert (hop.from_version, hop.to_version) == (11, 12)
    assert hop.fn.__module__ == "fr.artifacts.record_lens"


def test_a_v11_record_is_stamped_with_no_body_rewrite(tmp_path: Path) -> None:
    path = _record_file(tmp_path)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path.read_text() == _V11.replace("schema_version: 11\n", "schema_version: 12\n")
    assert parse_record(path.read_text()).schema_version == 12


def test_a_v11_record_carrying_a_lens_item_is_not_a_v11_record_and_is_left_alone(
    tmp_path: Path,
) -> None:
    """The hop reads with version 11's shape: no fr at record 11 knew `kind: lens`, so
    a v11 record carrying one is refused rather than certified by the live model."""
    text = _V11 + "  - {kind: lens, lens: security, title: why}\n"
    path = _record_file(tmp_path, text)

    report = run_migrations(tmp_path, dry_run=False)

    assert not report.ok
    assert path.read_text() == text


def test_an_unreadable_v11_record_is_refused_and_left_alone(tmp_path: Path) -> None:
    bad = _V11.replace("outcome: done", "outcome: done\nnot_a_field: 1")
    path = _record_file(tmp_path, bad)

    report = run_migrations(tmp_path, dry_run=False)

    assert not report.ok
    assert path.read_text() == bad


def test_the_validator_accepts_a_lens_item(tmp_path: Path) -> None:
    data = yaml.safe_load(_V11)
    data["schema_version"] = 12
    data["journal"].append(LENS_ITEM)
    path = _record_file(tmp_path, yaml.safe_dump(data))
    assert artifact_kind("record").validate(path) == []


def test_the_template_shows_the_lens_line() -> None:
    from fr.record.template import render_template

    text = render_template(
        run="r", step="s", item=None, allowed=frozenset({"journal"}), tick_ids=[],
        refactor_tasks=[], evidence=[], emitted=[], resolve="fr run resolve r --step s",
    )  # fmt: skip

    assert "#   - {kind: lens, lens: <id>, title: <why, one line>}" in text
