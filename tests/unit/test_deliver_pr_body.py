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
    )  # one call: the resolve also briefs review-phase (R4)
    review = {
        "run": RUN, "step": "review-phase", "item": "phase/1", "outcome": "done",
        "journal": [{"kind": "review", "id": "r-p1", "title": "review", "body": "clean"}],
        "evidence": {"review": "r-p1", "reviewer": "reviewer-1"},
    }  # fmt: skip
    rec = write_record(root, review)
    out = fr(root, [*step, "review-phase", "--item", "phase/1", "--record", str(rec)])
    assert out.exit_code == 0, out.output
    # One call (R4): the same resolve runs journal-check and briefs deliver.
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


# --- the spec is the contract (spec 2026-09-29 §A): no input sections ------


_REMOVED_SECTIONS = (
    "## Built without operator confirmation",
    "## Input coverage",
    "## Design inventory",
)


def test_the_required_sections_carry_no_input_section() -> None:
    from fr.record.pr_body import REQUIRED_SECTIONS

    assert REQUIRED_SECTIONS == (
        "## Findings",
        "## Out-of-scope findings",
        "## Post-merge verification owed",
        "## Proportionality",
        "## Cost",
    )


def test_a_live_body_missing_the_post_merge_section_is_refused() -> None:
    from fr.record.pr_body import REQUIRED_SECTIONS, missing_sections

    dropped = "## Post-merge verification owed"
    body = "\n\n".join(h for h in REQUIRED_SECTIONS if h != dropped)

    assert missing_sections(body) == [dropped]


def test_the_body_renders_post_merge_rows_and_tests_and_no_input_section(
    tmp_path: Path, live: dict[str, str]
) -> None:
    """R7: the Post-merge and Tests sections survive the input layer's removal."""
    from fr.record.pr_body import REQUIRED_SECTIONS, render_pr_body

    from tests.unit.requirements_support import row, write_matrix

    root = _at_deliver(tmp_path)
    write_matrix(
        root,
        [
            row("docs/spec.md", status="skipped"),
            row("docs/spec.md", rid="live-run", status="not-implemented", verify="post-merge"),
        ],
    )
    live["body"] = "never read before the render"
    _deliver(root)  # records `tests`, then refuses: the live body lacks every section

    body = render_pr_body(root, load_run_state(root, RUN))

    positions = [body.index(h) for h in REQUIRED_SECTIONS]
    assert positions == sorted(positions)
    for heading in _REMOVED_SECTIONS:
        assert heading not in body
    owed = body.split("## Post-merge verification owed")[1].split("## ")[0]
    assert "`live-run`" in owed and "live-run acceptance" in owed
    assert "req-r1" not in owed
    findings = body.split("## Findings")[1].split("## Out-of-scope findings")[0]
    assert "p1-f1" in findings


# --- R9: historical reviews are listed by name (spec 2026-10-05 §D) -----------


def _mark_historical(root: Path) -> None:
    """Phase 1's review as adoption infers one: `reviewer=historical`."""
    from fr.run import units
    from fr.run.model import save_run_state

    state = load_run_state(root, RUN)
    record = units.with_evidence(
        state.steps["implement"], "phase/1/review-phase", {"reviewer": "historical"}
    )
    save_run_state(root, state.model_copy(update={"steps": {**state.steps, "implement": record}}))
    commit_all(root, "historical review")


def test_the_body_lists_historical_reviews_when_a_unit_carries_one(tmp_path: Path) -> None:
    from fr.record.pr_body import render_pr_body

    root = _at_deliver(tmp_path)
    assert "## Historical reviews" not in render_pr_body(root, load_run_state(root, RUN))
    _mark_historical(root)

    body = render_pr_body(root, load_run_state(root, RUN))

    section = body.split("## Historical reviews")[1].split("## ")[0]
    assert "phase 1 — journal r-p1" in section


def test_missing_sections_reports_a_required_extra_heading() -> None:
    from fr.record.pr_body import REQUIRED_SECTIONS, missing_sections

    body = "\n\n".join(REQUIRED_SECTIONS)

    assert missing_sections(body) == []
    assert missing_sections(body, required=(*REQUIRED_SECTIONS, "## Historical reviews")) == [
        "## Historical reviews"
    ]


def test_deliver_refuses_a_live_body_lacking_the_historical_section(
    tmp_path: Path, live: dict[str, str]
) -> None:
    root = _at_deliver(tmp_path)
    _mark_historical(root)
    live["body"] = "never read before the render"
    _deliver(root)  # renders pr-body.md, refused
    rendered = _body(root).read_text()
    head, tail = rendered.split("## Historical reviews")
    live["body"] = head + "## " + tail.split("## ", 1)[1]

    _, out = _deliver(root)

    assert out.exit_code == 2, out.output
    assert "## Historical reviews" in out.output
    live["body"] = rendered

    _, out = _deliver(root)

    assert out.exit_code == 0, out.output


def test_deliver_refuses_a_live_body_that_keeps_the_heading_but_drops_the_list(
    tmp_path: Path, live: dict[str, str]
) -> None:
    # Review p2-r1: the operator's ok is given against the LIST of historical
    # reviews, so an emptied section is as much a refusal as a missing one.
    root = _at_deliver(tmp_path)
    _mark_historical(root)
    live["body"] = "never read before the render"
    _deliver(root)  # renders pr-body.md, refused
    rendered = _body(root).read_text()
    head, tail = rendered.split("## Historical reviews")
    live["body"] = head + "## Historical reviews\n\nNone.\n\n## " + tail.split("## ", 1)[1]

    _, out = _deliver(root)

    assert out.exit_code == 2, out.output
    assert "- phase 1 — journal" in " ".join(out.output.split())
