"""The PR body's `## Review lenses` section (spec 2026-11-12-review-lenses R12, §3.D):
a table of the feature's lens set with why each is there, how many files its reviewer
examined and how its findings closed — or one line saying no lens was requested."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    journal_path,
    resolution_entry,
)
from fr.record.pr_body import REQUIRED_SECTIONS, missing_sections, render_pr_body
from fr.run.model import StepRecord, UnitRecord

from tests.unit.lens_repo import commit_all, lens_repo

AUTH_RULE = "require:\n  - paths: ['src/auth/**']\n    lenses: [security]\n"
PLAN = "2026-11-12-x"
NOW = "2026-11-12T00:00:00+00:00"
HEADING = "## Review lenses"


def _entry(root: Path, **kw: object) -> JournalEntry:
    entry = JournalEntry(scope="plan", created=NOW, **kw)  # type: ignore[arg-type]
    append_journal_entry(journal_path(root, "plan", PLAN), PLAN, entry)
    return entry


def _state(
    evidence: str | None, *, with_step: bool = True, step_state: str = "done"
) -> SimpleNamespace:
    steps = {
        "plan": SimpleNamespace(emitted={"plan": f"docs/superpowers/plans/{PLAN}"}, units=None),
    }
    if with_step:
        units = {"step/lens-review": UnitRecord(evidence={"lenses": evidence} if evidence else {})}
        steps["lens-review"] = StepRecord(state=step_state, units=units)  # type: ignore[assignment]
    return SimpleNamespace(run="r1", steps=steps, workflow="fr-goal@1")


def _section(root: Path, state: SimpleNamespace) -> str:
    body = render_pr_body(root, state)  # type: ignore[arg-type]
    assert HEADING in body, body
    return body.split(HEADING, 1)[1].split("\n## ", 1)[0].strip()


def _world(tmp_path: Path) -> Path:
    root = lens_repo(tmp_path, base_config=AUTH_RULE)
    (root / "src" / "auth").mkdir(parents=True)
    (root / "src" / "auth" / "session.py").write_text("x = 1\n")
    commit_all(root, "feature")
    return root


def test_a_rule_lens_and_an_agent_lens_render_a_table_with_states(tmp_path: Path) -> None:
    root = _world(tmp_path)
    _entry(
        root, kind="lens", id="lens-tests-1", phase=2, lens="tests", step="implement-phase",
        title="the retry path is only tested with a mock",
    )  # fmt: skip
    r1 = _entry(root, kind="finding", id="l-security-r1", title="token logged", state="open")
    r2 = _entry(root, kind="finding", id="l-security-r2", title="old debt", state="open")
    for target, state, extra in (
        (r1, "fixed", {}),
        (r2, "deferred", {"tracked_by": "derio-net/super-fr#1432"}),
    ):
        append_journal_entry(
            journal_path(root, "plan", PLAN),
            PLAN,
            resolution_entry(
                target=target,
                scope="plan",
                taken=set(),
                created=NOW,
                state=state,
                body="why",
                **extra,
            ),  # fmt: skip
        )

    section = _section(root, _state("security=2:l-security-r1,l-security-r2;tests=5:none"))

    assert "| Lens | Why | Files examined | Findings |" in section
    assert (
        "| security | rule `src/auth/**` (src/auth/session.py) | 2 | "
        "l-security-r1 fixed, l-security-r2 out of scope (derio-net/super-fr#1432) |"
    ) in section
    assert (
        '| tests | implement-phase phase 2: "the retry path is only tested with a mock" '
        "| 5 | none |"
    ) in section


def test_the_section_follows_the_findings_sections(tmp_path: Path) -> None:
    root = _world(tmp_path)
    body = render_pr_body(root, _state("security=1:none"))  # type: ignore[arg-type]
    assert body.index("## Out-of-scope findings") < body.index(HEADING)
    assert body.index(HEADING) < body.index("## Pre-merge verification owed")


def test_an_empty_set_says_no_lens_was_requested(tmp_path: Path) -> None:
    root = lens_repo(tmp_path)
    assert _section(root, _state("none")) == "No lens was requested for this change."


def test_a_command_line_addition_names_no_step(tmp_path: Path) -> None:
    root = lens_repo(tmp_path)
    _entry(root, kind="lens", id="lens-errors-1", lens="errors", title="swallowed exceptions")
    section = _section(root, _state("errors=3:none"))
    assert '| errors | command line: "swallowed exceptions" | 3 | none |' in section


def test_an_unreadable_return_is_not_observable(tmp_path: Path) -> None:
    root = lens_repo(tmp_path)
    _entry(root, kind="lens", id="lens-errors-1", lens="errors", title="why", step="plan")
    section = _section(root, _state("errors=unobserved:none"))
    assert "| not observable |" in section


def test_a_branch_changing_the_lens_config_says_so(tmp_path: Path) -> None:
    root = lens_repo(tmp_path)
    (root / ".fr").mkdir()
    (root / ".fr" / "lenses.yaml").write_text("disable: [tests]\n")
    commit_all(root, "config")
    section = _section(root, _state("none"))
    assert "This branch changed the repo's lens config (`.fr/lenses.yaml`)." in section


def test_a_run_with_no_lens_review_step_predates_lenses(tmp_path: Path) -> None:
    root = lens_repo(tmp_path)
    assert _section(root, _state(None, with_step=False)) == "This run predates review lenses."


def test_the_section_is_not_required_so_an_old_live_body_is_unchanged() -> None:
    assert HEADING not in REQUIRED_SECTIONS
    old = "\n\n".join(f"{h}\n\nx" for h in REQUIRED_SECTIONS)
    assert missing_sections(old) == []


def test_a_pipe_in_a_reason_stays_inside_its_cell(tmp_path: Path) -> None:
    root = lens_repo(tmp_path)
    _entry(root, kind="lens", id="lens-errors-1", lens="errors", title="a | b", step="plan")

    section = _section(root, _state("errors=3:none"))

    assert '| errors | plan: "a \\| b" | 3 | none |' in section


def test_a_cell_is_one_line() -> None:
    from fr.record.pr_body import _cell

    assert _cell("a | b\nc") == "a \\| b c"


def test_a_lens_review_that_has_not_run_is_not_called_unobservable(tmp_path: Path) -> None:
    root = lens_repo(tmp_path)
    _entry(root, kind="lens", id="lens-errors-1", lens="errors", title="why", step="plan")

    section = _section(root, _state(None, step_state="pending"))

    assert "| not reviewed yet |" in section
    assert "The lens review has not run yet." in section
    assert "not observable" not in section


def test_a_lens_that_joined_after_the_review_is_not_reviewed(tmp_path: Path) -> None:
    root = lens_repo(tmp_path)
    _entry(root, kind="lens", id="lens-errors-1", lens="errors", title="why", step="plan")
    _entry(root, kind="lens", id="lens-tests-1", lens="tests", title="late", step="deliver")

    section = _section(root, _state("errors=3:none"))

    assert "| 3 | none |" in section
    assert '| tests | deliver: "late" | not reviewed | none |' in section


def test_a_lens_the_repo_disabled_is_named_under_the_section(tmp_path: Path) -> None:
    root = lens_repo(tmp_path, base_config="disable: [errors]\n")
    _entry(root, kind="lens", id="lens-errors-1", lens="errors", title="why", step="plan")

    section = _section(root, _state(None))

    assert section.startswith("No lens was requested for this change.")
    assert "Note: " in section and "errors" in section
