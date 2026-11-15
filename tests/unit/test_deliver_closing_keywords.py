"""`deliver` refuses a PR body that shares one closing keyword across several
issue references (gh#821): on GitHub `Closes #a and #b` closes only `#a`, so
`#b` stays open after its fix ships (#544 did)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.run.model import load_run_state

from tests.unit.test_deliver_pr_body import RUN, _at_deliver, _body, _deliver, live

__all__ = ["live"]  # the fixture, re-exported so pytest finds it here


@pytest.mark.parametrize(
    "line",
    [
        "Closes #1 and #2",
        "Closes #1, #2",
        "fixes: #1 #2",
        "Resolves derio-net/super-fr#1 and derio-net/super-fr#2",
        "Closes https://github.com/o/r/issues/1, https://github.com/o/r/issues/2",
        "Fixes #1 (follow-up to #2)",
    ],
)
def test_a_line_sharing_one_keyword_is_reported(line: str) -> None:
    from fr.record.pr_body import shared_closing_keywords

    assert [bad for bad, _fixed in shared_closing_keywords(f"## Summary\n\n{line}\n")] == [line]


@pytest.mark.parametrize(
    "body",
    [
        "Closes #1\nCloses #2\n",
        "Closes #1 and closes #2\n",
        "Fixes: #1, Resolves #2\n",
        "Fixed derio-net/super-fr#821\n",
        "See #1 and #2 for context\n",  # no closing keyword: mentions, not closes
        "The fix landed after the closed PR\n",  # keywords, but no reference
        "```\nCloses #1 and #2\n```\n",  # GitHub ignores keywords in code
        "Quoting the bug: `Closes #1 and #2` closes only the first\n",
        "Fixes the parser in docs/spec.md\n",
    ],
)
def test_one_keyword_per_reference_passes(body: str) -> None:
    from fr.record.pr_body import shared_closing_keywords

    assert shared_closing_keywords(body) == []


@pytest.mark.parametrize(
    "body",
    [
        "fix colour #123\n",
        "This fixes the regression from #12, reported in #34\n",
        "Fixed the race; see #12 and #34 for context\n",
        "- resolves the flake that #7 and #8 reported\n",
    ],
)
def test_a_keyword_that_closes_nothing_is_prose_not_a_shared_keyword(body: str) -> None:
    """gh#868: GitHub closes a reference only when the keyword sits directly
    before it. A line whose keyword is followed by no reference closes nothing,
    so it shares nothing: it is prose, and refusing it blocks a valid deliver."""
    from fr.record.pr_body import shared_closing_keywords

    assert shared_closing_keywords(body) == []


@pytest.mark.parametrize(
    ("line", "fixed"),
    [
        ("Closes GH-1 and #2", ["Closes GH-1", "Closes #2"]),
        ("Closes #1 and gh-2", ["Closes #1", "Closes gh-2"]),
    ],
)
def test_a_gh_reference_counts_as_the_close_it_is(line: str, fixed: list[str]) -> None:
    """Review r1, verified live on PR #1032: `Closes GH-869 and #868` closes
    only #869. Unread, `GH-1` hid the close that makes `#2` a shared keyword."""
    from fr.record.pr_body import shared_closing_keywords

    assert shared_closing_keywords(f"{line}\n") == [(line, fixed)]


@pytest.mark.parametrize(
    "body",
    [
        "Closes (#1) and (#2)\n",  # live: GitHub links nothing through a parenthesis
    ],
)
def test_a_reference_github_does_not_close_shares_nothing(body: str) -> None:
    from fr.record.pr_body import shared_closing_keywords

    assert shared_closing_keywords(body) == []


@pytest.mark.parametrize(
    ("body", "fixed"),
    [
        ("Closes #1,\n#2\n", ["Closes #1", "Closes #2"]),
        ("Closes GH-1,\nGH-2\n", ["Closes GH-1", "Closes GH-2"]),
        ("Closes #1 and\n#2\n", ["Closes #1", "Closes #2"]),
        ("Fixes #1\n#2, #3\n", ["Fixes #1", "Fixes #2", "Fixes #3"]),
        ("Resolves #1,\n#2,\n#3\n", ["Resolves #1", "Resolves #2", "Resolves #3"]),
    ],
)
def test_a_reference_list_wrapped_onto_the_next_line_is_still_shared(
    body: str, fixed: list[str]
) -> None:
    """gh#869, verified live on PR #1032: GitHub closes only `#869` for
    `Closes #869,\\n#868`. The list's tail is on a line with no keyword, so a
    line-at-a-time scan never saw it, and it stayed open after merge."""
    from fr.record.pr_body import shared_closing_keywords

    [(bad, got)] = shared_closing_keywords(body)

    assert bad == body.strip() and got == fixed


@pytest.mark.parametrize(
    "body",
    [
        "Closes\n#1, #2\n",  # live: GitHub links nothing across the break
        "Closes:\n#1\n",
        "Closes #1\nRefs #2\n",  # a new line that is not a reference continues nothing
        "Closes #1\n\n#2 is next\n",  # a blank line ends the paragraph
        "Closes #1,\n- #2\n",  # a list item is its own block
        "Closes #1,\n```\n#2\n```\n",
        "Closes #1\nCloses #2\n",
    ],
)
def test_a_line_break_continues_nothing_but_a_wrapped_list(body: str) -> None:
    """gh#869: a keyword split from its FIRST reference closes nothing on GitHub
    (verified live), so it shares nothing — line-scoped reading is right there."""
    from fr.record.pr_body import shared_closing_keywords

    assert shared_closing_keywords(body) == []


def test_the_fix_puts_every_reference_on_its_own_line_with_the_keyword_as_written() -> None:
    from fr.record.pr_body import shared_closing_keywords

    [(_, fixed)] = shared_closing_keywords("Closes #1, derio-net/super-fr#2 and #3\n")

    assert fixed == ["Closes #1", "Closes derio-net/super-fr#2", "Closes #3"]


def test_deliver_refuses_a_shared_keyword_and_prints_the_corrected_lines(
    tmp_path: Path, live: dict[str, str]
) -> None:
    root = _at_deliver(tmp_path)
    live["body"] = "never read before the render"
    _deliver(root)  # renders pr-body.md
    rendered = _body(root).read_text()
    live["body"] = f"Closes #821 and #822\n\n{rendered}"

    rec, out = _deliver(root)

    assert out.exit_code == 2, out.output
    assert "Closes #821 and #822" in out.output
    assert "Closes #821\n" in out.output and "Closes #822\n" in out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "running"
    assert rec.exists()

    live["body"] = f"Closes #821\nCloses #822\n\n{rendered}"
    rec, out = _deliver(root)

    assert out.exit_code == 0, out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "done"


@pytest.mark.parametrize(
    "body",
    [
        "Closes [#5](https://github.com/o/r/issues/5)\n",  # one link, one issue
        "Closes [the bug](https://github.com/o/r/issues/5)\n",
        "**Closes** #5\n",
        "Closes: **#5**\n",
        "```x``` and then\nCloses #1\n",  # a one-line span, not a fence
        "> ```\n> Closes #1 and #2\n> ```\n",
        "- ```\n  Closes #1 and #2\n  ```\n",
        "````\n```\nCloses #1 and #2\n````\n",  # an inner shorter fence does not close
    ],
)
def test_markdown_around_a_compliant_reference_passes(body: str) -> None:
    from fr.record.pr_body import shared_closing_keywords

    assert shared_closing_keywords(body) == []


def test_a_one_line_span_does_not_hide_the_rest_of_the_body() -> None:
    from fr.record.pr_body import shared_closing_keywords

    assert shared_closing_keywords("```x```\nCloses #1 and #2\n") != []


def test_the_fix_uses_the_keyword_nearest_each_reference() -> None:
    from fr.record.pr_body import shared_closing_keywords

    [(_, fixed)] = shared_closing_keywords("Fixes #5, and this resolves #6 and #7\n")

    assert fixed == ["Fixes #5", "resolves #6", "resolves #7"]


def test_frs_own_render_never_trips_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review r1: a finding line carries a free-text title, a state word that is
    a keyword (`fixed`) and `→ #N` — fr's own render must still deliver."""
    import fr.record.pr_body as pr_body
    from fr.journal.model import JournalEntry

    def entry(eid: str, title: str) -> JournalEntry:
        return JournalEntry.model_validate(
            {
                "kind": "finding",
                "scope": "plan",
                "id": eid,
                "created": "2026-10-02",
                "title": title,
                "state": "open",
            }
        )

    lines = (
        [pr_body._finding_line("spec", entry("f3", "Crash in #45 handler"), "fixed", None)],
        [pr_body._finding_line("plan", entry("f2", "Fix flaky retry"), "deferred", "#123")],
    )
    monkeypatch.setattr(pr_body, "_findings", lambda _root, _state: lines)
    root = _at_deliver(tmp_path)

    body = pr_body.render_pr_body(root, load_run_state(root, RUN))

    assert "#123" in body and "#45" in body
    assert pr_body.shared_closing_keywords(body) == []
    assert pr_body.shared_closing_keywords(f"Closes #1 and #2\n\n{body}") != []


# --- owed-archive-side-effects R4, R5: a discharged owed issue closes at merge ------

OWED_REF = "derio-net/super-fr#7"


@pytest.fixture
def discharged(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """The branch discharged one owed entry filed as OWED_REF; the returned map is
    `run_held_issues`'s answer (empty: nothing holds it)."""
    import fr.record.pr_body as pr_body

    held: dict[str, str] = {}
    item = pr_body.DischargedOwed(ref=OWED_REF, entry="owed-1")
    monkeypatch.setattr(pr_body, "discharged_owed", lambda _root: [item])
    monkeypatch.setattr(pr_body, "run_held_issues", lambda _root, _state: dict(held))
    return held


def _rendered(root: Path, live: dict[str, str]) -> str:
    live["body"] = "not yet"
    _deliver(root)  # refused: renders pr-body.md
    return _body(root).read_text()


def test_the_render_closes_the_discharged_owed_issue_and_delivers(
    tmp_path: Path, live: dict[str, str], discharged: dict[str, str]
) -> None:
    root = _at_deliver(tmp_path)
    body = _rendered(root, live)
    assert f"## Owed actions discharged\n\nCloses {OWED_REF}\n" in body
    live["body"] = body
    _rec, out = _deliver(root)
    assert out.exit_code == 0, out.output


@pytest.mark.parametrize("closing", [None, f"Fixes {OWED_REF}", "Resolves #7"])
def test_a_live_body_must_close_every_listed_owed_issue(
    tmp_path: Path, live: dict[str, str], discharged: dict[str, str], closing: str | None
) -> None:
    root = _at_deliver(tmp_path)
    body = _rendered(root, live).replace(f"Closes {OWED_REF}", closing or "None.")
    live["body"] = body
    _rec, out = _deliver(root)
    if closing is None:
        assert out.exit_code == 2, out.output
        assert OWED_REF in out.output and "Closes" in out.output
        assert load_run_state(root, RUN).steps["deliver"].state == "running"
    else:
        assert out.exit_code == 0, out.output


def test_a_held_owed_issue_is_rendered_refs_and_not_required(
    tmp_path: Path, live: dict[str, str], discharged: dict[str, str]
) -> None:
    discharged[OWED_REF] = "row r1 still holds it open"
    root = _at_deliver(tmp_path)
    body = _rendered(root, live)
    assert f"Refs {OWED_REF} — held: row r1 still holds it open" in body
    assert f"Closes {OWED_REF}" not in body
    live["body"] = body
    _rec, out = _deliver(root)
    assert out.exit_code == 0, out.output


def test_minimal_still_requires_the_closing_reference(
    tmp_path: Path, live: dict[str, str], discharged: dict[str, str]
) -> None:
    from tests.unit.test_forge_quiet_pr_body import PLAIN, _land_policy

    root = _at_deliver(tmp_path)
    _land_policy(root, "forge:\n  pr_body: minimal\n")
    live["body"] = PLAIN
    _rec, out = _deliver(root)
    assert out.exit_code == 2, out.output
    assert OWED_REF in out.output
    live["body"] = f"{PLAIN}\nCloses {OWED_REF}\n"
    _rec, out = _deliver(root)
    assert out.exit_code == 0, out.output


def test_minimal_a_held_owed_issue_is_not_required(
    tmp_path: Path, live: dict[str, str], discharged: dict[str, str]
) -> None:
    from tests.unit.test_forge_quiet_pr_body import PLAIN, _land_policy

    discharged[OWED_REF] = "row r1 still holds it open"
    root = _at_deliver(tmp_path)
    _land_policy(root, "forge:\n  pr_body: minimal\n")
    live["body"] = PLAIN
    _rec, out = _deliver(root)
    assert out.exit_code == 0, out.output
