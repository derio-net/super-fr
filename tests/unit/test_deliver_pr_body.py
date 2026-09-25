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
