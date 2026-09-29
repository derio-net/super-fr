"""`deliver` renders the PR body and refuses a PR missing a required section
(spec 2026-09-25-lean-cost-aware-process §5.C.4, §7 item 13) — so a PR like
#612, delivered with no out-of-scope section, cannot be delivered again."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run.model import load_run_state

from tests.unit.record_support import (
    RUN,
    commit_all,
    fr,
    implement_record,
    snapshot,
    started_run,
    write_record,
)

PR = "https://github.com/derio-net/super-fr/pull/1"


def _at_deliver(tmp_path: Path) -> Path:
    root = started_run(tmp_path)
    impl = implement_record(
        journal=[
            {"kind": "finding", "id": "p1-f1", "title": "edge case", "review_scope": "in"},
            {"kind": "finding", "id": "p1-f2", "title": "old debt", "review_scope": "out"},
        ],
        resolves=[
            {"id": "p1-f1", "state": "fixed", "body": "covered"},
            {"id": "p1-f2", "state": "out-of-scope", "body": "predates this change"},
        ],
    )
    step = ["run", "resolve", RUN, "--step"]
    rec = write_record(root, impl)
    assert (
        fr(root, [*step, "implement-phase", "--item", "phase/1", "--record", str(rec)]).exit_code
        == 0
    )
    assert fr(root, ["run", "advance", RUN]).exit_code == 0
    review = {
        "run": RUN, "step": "review-phase", "item": "phase/1", "outcome": "done",
        "journal": [{"kind": "review", "id": "r-p1", "title": "review", "body": "clean"}],
        "evidence": {"review": "r-p1", "reviewer": "reviewer-1"},
    }  # fmt: skip
    rec = write_record(root, review)
    out = fr(root, [*step, "review-phase", "--item", "phase/1", "--record", str(rec)])
    assert out.exit_code == 0, out.output
    for _ in range(3):  # journal-check executes, then deliver is briefed
        adv = fr(root, ["run", "advance", RUN])
        assert adv.exit_code == 0, adv.output
        if load_run_state(root, RUN).steps["deliver"].state == "running":
            break
    assert load_run_state(root, RUN).steps["deliver"].state == "running"
    commit_all(root, "at deliver")
    (root / "suite.log").write_text("n passed\n")
    return root


def _deliver(root: Path):
    data = {
        "run": RUN, "step": "deliver", "outcome": "done",
        "emitted": {"pr": PR}, "evidence": {"tests": "suite.log"},
    }  # fmt: skip
    rec = write_record(root, data)
    return rec, fr(root, ["run", "resolve", RUN, "--step", "deliver", "--record", str(rec)])


def _body(root: Path) -> Path:
    return root / "docs" / "superpowers" / "runs" / f"{RUN}.records" / "pr-body.md"


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    import fr.gh

    served: dict[str, str] = {}

    def view_pr_body(ref: str, *, cwd: Path | None = None) -> str:
        served["ref"] = ref
        return served["body"]

    monkeypatch.setattr(fr.gh, "view_pr_body", view_pr_body)
    return served


def test_deliver_renders_the_body_and_refuses_a_pr_missing_the_out_of_scope_section(
    tmp_path: Path, live: dict[str, str]
) -> None:
    root = _at_deliver(tmp_path)
    live["body"] = "## Summary\n\nshipped\n\n## Findings\n\n- p1-f1\n"

    rec, out = _deliver(root)

    assert out.exit_code == 2, out.output
    assert "Out-of-scope findings" in out.output
    assert live["ref"] == PR
    body = _body(root).read_text()
    for heading in ("## Findings", "## Out-of-scope findings", "## Proportionality", "## Cost"):
        assert heading in body, heading
    findings, out_of_scope = body.split("## Out-of-scope findings")
    assert "p1-f1" in findings.split("## Findings")[1]
    assert "p1-f2" in out_of_scope.split("## Proportionality")[0]
    assert load_run_state(root, RUN).steps["deliver"].state == "running"
    assert rec.exists()


def test_a_pr_with_every_section_delivers(tmp_path: Path, live: dict[str, str]) -> None:
    root = _at_deliver(tmp_path)
    live["body"] = "never read before the render"
    _deliver(root)  # renders pr-body.md, refused: the live body lacks every section
    live["body"] = _body(root).read_text()

    rec, out = _deliver(root)

    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"
    assert not rec.exists() and not _body(root).exists()


def test_no_out_of_scope_findings_renders_none(tmp_path: Path) -> None:
    from fr.record.pr_body import missing_sections, render_out_of_scope

    assert render_out_of_scope([]) == "None."
    assert missing_sections("## Findings\n## Out-of-scope findings\nNone.\n") == [
        "## Built without operator confirmation",
        "## Input coverage",
        "## Design inventory",
        "## Post-merge verification owed",
        "## Proportionality",
        "## Cost",
    ]


def test_an_unreadable_pr_refuses_and_changes_nothing_but_the_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.gh

    root = _at_deliver(tmp_path)

    def boom(ref: str, *, cwd: Path | None = None) -> str:
        raise fr.gh.GhError("no pull requests found")

    monkeypatch.setattr(fr.gh, "view_pr_body", boom)
    before = snapshot(root)

    _rec, out = _deliver(root)

    assert out.exit_code == 2, out.output
    assert "pr-body.md" in out.output
    after = snapshot(root)
    changed = {k for k in after if before.get(k) != after[k]} | (set(before) - set(after))
    assert changed <= {
        f"docs/superpowers/runs/{RUN}.records/pr-body.md",
        f"docs/superpowers/runs/{RUN}.records/deliver.yaml",
    }


# --- requirements traceability (spec 2026-09-28 §D, §F; Test Plan 11) -------


def test_the_three_traceability_sections_are_required_in_order() -> None:
    from fr.record.pr_body import REQUIRED_SECTIONS

    assert REQUIRED_SECTIONS == (
        "## Findings",
        "## Out-of-scope findings",
        "## Built without operator confirmation",
        "## Input coverage",
        "## Design inventory",
        "## Post-merge verification owed",
        "## Proportionality",
        "## Cost",
    )


@pytest.mark.parametrize(
    "dropped",
    [
        "## Built without operator confirmation",
        "## Input coverage",
        "## Design inventory",
        "## Post-merge verification owed",
    ],
)
def test_a_live_body_missing_a_traceability_section_is_refused(dropped: str) -> None:
    from fr.record.pr_body import REQUIRED_SECTIONS, missing_sections

    body = "\n\n".join(h for h in REQUIRED_SECTIONS if h != dropped)

    assert missing_sections(body) == [dropped]


def _traced_run_at_deliver(tmp_path: Path) -> Path:
    """The `traced` shape of test_run_evidence_requirements, walked to an open
    `deliver`: a spec-review whose review entry carries the coverage block,
    an unconfirmed spec finding, and a post-merge row."""
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path

    from tests.unit.requirements_support import COVERAGE_BLOCK, now, row, write_matrix
    from tests.unit.test_run_evidence_requirements import (
        _WITH_COVERAGE,
        SLUG,
        SPEC,
        _at_spec_review,
        _invoke,
        _review_entry,
        _spec_review,
    )

    repo, shipped = _at_spec_review(tmp_path, spec_review=_WITH_COVERAGE)
    journal = journal_path(repo, "spec", SLUG)
    for entry in (
        JournalEntry(
            kind="finding", scope="spec", id="s-inv", created=now(),
            title="invented hover state", body="the design adds a hover state",
            state="open", review_scope="in",  # type: ignore[arg-type]
        ),
        JournalEntry(
            kind="finding", scope="spec", id="s-inv-resolved", created=now(),
            title="resolves s-inv", body="builds a hover that lifts the card 2px",
            state="open", resolves="s-inv", unconfirmed=True,
        ),
    ):  # fmt: skip
        append_journal_entry(journal, SLUG, entry)
    _review_entry(repo, body="Traceability first.\n\n" + COVERAGE_BLOCK)
    assert _spec_review(repo, shipped).exit_code == 0
    write_matrix(
        repo,
        [
            row(SPEC, status="skipped"),
            row(SPEC, rid="live-run", status="not-implemented", verify="post-merge"),
        ],
    )
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    return repo


def test_the_body_renders_unconfirmed_coverage_and_post_merge_sections(tmp_path: Path) -> None:
    from fr.record.pr_body import REQUIRED_SECTIONS, render_pr_body

    repo = _traced_run_at_deliver(tmp_path)

    body = render_pr_body(repo, load_run_state(repo, "r1"))

    positions = [body.index(h) for h in REQUIRED_SECTIONS]
    assert positions == sorted(positions)
    findings = body.split("## Findings")[1].split("## Out-of-scope findings")[0]
    unconfirmed = body.split("## Built without operator confirmation")[1].split(
        "## Input coverage"
    )[0]
    coverage = body.split("## Input coverage")[1].split("## Design inventory")[0]
    owed = body.split("## Post-merge verification owed")[1].split("## Proportionality")[0]
    assert "s-inv" not in findings
    assert "`s-inv`" in unconfirmed
    assert "builds a hover that lifts the card 2px" in unconfirmed
    assert "<details>" in coverage and "</details>" in coverage
    assert '| "build the widget" | R1 |' in coverage
    assert "`live-run`" in owed and "live-run acceptance" in owed
    assert "req-r1" not in owed


def test_a_run_predating_the_gate_renders_the_predates_line_and_nones(tmp_path: Path) -> None:
    from fr.record.pr_body import render_pr_body

    from tests.unit.test_run_evidence_requirements import (
        SPEC,
        _brainstorm,
        _invoke,
        _review_entry,
        _spec,
        _spec_review,
        _started,
    )

    repo, shipped = _started(tmp_path, brainstorm="[]", spec_review="[review, reviewer]")
    _spec(repo, "\n## Design\n\nno requirements here\n")
    assert _brainstorm(repo, shipped).exit_code == 0
    assert _invoke(repo, shipped, ["run", "advance", "r1"]).exit_code == 0
    _review_entry(repo)
    assert _spec_review(repo, shipped).exit_code == 0
    assert SPEC  # the run's spec carries no Requirements and no rows cite it

    body = render_pr_body(repo, load_run_state(repo, "r1"))

    after = body.split("## Built without operator confirmation")[1]
    assert after.split("## Input coverage")[0].strip() == "None."
    coverage = after.split("## Input coverage")[1].split("## Design inventory")[0]
    assert coverage.strip() == "Not recorded (predates the requirements gate)."
    inventory = after.split("## Design inventory")[1].split("## Post-merge verification owed")[0]
    assert inventory.strip() == "Not recorded (predates the fidelity gate)."
    owed = after.split("## Post-merge verification owed")[1].split("## Proportionality")[0]
    assert owed.strip() == "None."


def _coverage_section(body: str) -> str:
    return body.split("## Input coverage")[1].split("## Design inventory")[0].strip()


def test_a_gated_run_whose_shape_records_no_coverage_is_not_available(tmp_path: Path) -> None:
    """e3: brainstorm carries `requirements`, so the run does NOT predate the
    gate — a missing `coverage` (a repo manifest that never declared it) is
    reported as unavailable, not as predating."""
    from fr.record.pr_body import render_pr_body

    from tests.unit.test_run_evidence_requirements import _at_deliver

    repo, _ = _at_deliver(tmp_path)

    coverage = _coverage_section(render_pr_body(repo, load_run_state(repo, "r1")))

    assert coverage.startswith("Not available:"), coverage
    assert "predates" not in coverage


def test_an_unreadable_spec_journal_is_not_available_not_predates(tmp_path: Path) -> None:
    from fr.journal.model import journal_path
    from fr.record.pr_body import render_pr_body

    from tests.unit.test_run_evidence_requirements import SLUG

    repo = _traced_run_at_deliver(tmp_path)
    journal_path(repo, "spec", SLUG).write_text("this is not a journal\n")

    coverage = _coverage_section(render_pr_body(repo, load_run_state(repo, "r1")))

    assert coverage.startswith("Not available:"), coverage
    assert "predates" not in coverage


# --- spec-fidelity §F (Test Plan 5-6) ---------------------------------------


def _section(body: str, heading: str, nxt: str) -> str:
    return body.split(heading)[1].split(nxt)[0].strip()


def _with_fidelity(repo: Path):
    """The traced run's state plus `fidelity` evidence naming a second review
    entry that carries all three blocks (a legacy `unconfirmed` finding cannot
    coexist with a live `fidelity` derivation, so the fixture is patched)."""
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path
    from fr.run import units

    from tests.unit.requirements_support import REVIEW_BLOCKS, now
    from tests.unit.test_run_evidence_requirements import SLUG

    append_journal_entry(
        journal_path(repo, "spec", SLUG),
        SLUG,
        JournalEntry(
            kind="review", scope="spec", id="sr-2", created=now(),
            title="spec review 2", body=REVIEW_BLOCKS,
        ),
    )  # fmt: skip
    state = load_run_state(repo, "r1")
    record = units.with_evidence(
        state.steps["spec-review"],
        "step/spec-review",
        {"fidelity": "1 requirements, 1 sections", "review": "sr-2"},
    )
    return state.model_copy(update={"steps": {**state.steps, "spec-review": record}})


def test_the_design_inventory_renders_the_reviews_table_inside_details(tmp_path: Path) -> None:
    from fr.record.pr_body import render_pr_body

    repo = _traced_run_at_deliver(tmp_path)

    body = render_pr_body(repo, _with_fidelity(repo))

    inventory = _section(body, "## Design inventory", "## Post-merge verification owed")
    assert inventory.startswith("<details>") and inventory.endswith("</details>")
    assert "```design-inventory" in inventory
    assert "| A. Widget | the widget counts | R1 |" in inventory


def test_a_run_whose_spec_review_has_no_fidelity_evidence_predates(tmp_path: Path) -> None:
    from fr.record.pr_body import render_pr_body

    from tests.unit.test_run_evidence_requirements import _at_deliver

    repo, _ = _at_deliver(tmp_path)  # a shape that records coverage-less spec review

    body = render_pr_body(repo, load_run_state(repo, "r1"))

    inventory = _section(body, "## Design inventory", "## Post-merge verification owed")
    assert inventory == "Not recorded (predates the fidelity gate)."


def test_a_stored_predates_line_for_fidelity_reads_as_predating(tmp_path: Path) -> None:
    from fr.record.pr_body import _predates_gate, render_pr_body
    from fr.requirements import REQUIREMENTS_PREDATES
    from fr.run import units

    repo = _traced_run_at_deliver(tmp_path)
    state = load_run_state(repo, "r1")
    assert _predates_gate(state) is False
    record = state.steps["spec-review"]
    stored = units.with_evidence(record, "step/spec-review", {"fidelity": REQUIREMENTS_PREDATES})
    state = state.model_copy(update={"steps": {**state.steps, "spec-review": stored}})

    assert _predates_gate(state) is True
    body = render_pr_body(repo, state)
    inventory = _section(body, "## Design inventory", "## Post-merge verification owed")
    assert inventory == "Not recorded (predates the fidelity gate)."


def test_an_unreadable_spec_journal_makes_the_inventory_not_available(tmp_path: Path) -> None:
    from fr.journal.model import journal_path
    from fr.record.pr_body import render_pr_body

    from tests.unit.test_run_evidence_requirements import SLUG

    repo = _traced_run_at_deliver(tmp_path)
    state = _with_fidelity(repo)
    journal_path(repo, "spec", SLUG).write_text("this is not a journal\n")

    inventory = _section(
        render_pr_body(repo, state), "## Design inventory", "## Post-merge verification owed"
    )
    assert inventory.startswith("Not available:"), inventory
    assert "predates" not in inventory


def test_a_recorded_review_missing_from_the_journal_makes_the_inventory_not_available(
    tmp_path: Path,
) -> None:
    from fr.record.pr_body import render_pr_body
    from fr.run import units

    repo = _traced_run_at_deliver(tmp_path)
    state = _with_fidelity(repo)
    record = units.with_evidence(
        state.steps["spec-review"], "step/spec-review", {"review": "sr-missing"}
    )
    state = state.model_copy(update={"steps": {**state.steps, "spec-review": record}})

    inventory = _section(
        render_pr_body(repo, state), "## Design inventory", "## Post-merge verification owed"
    )
    assert inventory.startswith("Not available:") and "sr-missing" in inventory, inventory


def test_delegated_decisions_list_with_the_requirements_citing_them(tmp_path: Path) -> None:
    from fr.journal.model import JournalEntry, append_journal_entry, journal_path
    from fr.record.pr_body import render_pr_body

    from tests.unit.requirements_support import now
    from tests.unit.test_run_evidence_requirements import SLUG, SPEC

    repo = _traced_run_at_deliver(tmp_path)
    append_journal_entry(
        journal_path(repo, "spec", SLUG),
        SLUG,
        JournalEntry(
            kind="decision", scope="spec", id="d-call", created=now(),
            title="Card style is the agent's call", body="chose flat cards", delegated=True,
        ),
    )  # fmt: skip
    spec = repo / SPEC
    spec.write_text(
        spec.read_text().rstrip("\n") + "\n| R9 | Cards are flat. | decision d-call |\n"
    )

    body = render_pr_body(repo, load_run_state(repo, "r1"))

    section = _section(body, "## Built without operator confirmation", "## Input coverage")
    assert "`d-call`" in section and "Card style is the agent's call" in section
    assert "R9" in section
    # legacy unconfirmed finding still listed after the delegated decisions
    assert section.index("`d-call`") < section.index("`s-inv`")
