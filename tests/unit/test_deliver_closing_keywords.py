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


# --- review p2-r4: a REAL acceptance hold, through render and both gates -----------


HELD_REF = "t/t#7"
"""An issue in the fixture's own repo (`t/t`, the identity its legacy fragment names)."""


def _really_held(tmp_path: Path, row_id: str) -> Path:
    """`_at_deliver`'s workspace, its origin configured as github.com/t/t
    (served from the local bare through `insteadOf`), where the branch files an owed
    entry as HELD_REF and discharges it, and an acceptance row `row_id` (walk-owed)
    names HELD_REF in its `issues:` — the hold, read from the real matrix."""
    import subprocess

    from fr.journal.model import (
        JournalEntry,
        append_journal_entry,
        archived_journal_path,
        owed_body,
        resolution_entry,
    )

    from tests.unit.acceptance_helpers import write_matrix_fragments
    from tests.unit.record_support import commit_all

    root = _at_deliver(tmp_path)

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    url = "https://github.com/t/t.git"
    git("config", "remote.origin.url", url)
    git("config", f"url.{tmp_path / 'origin.git'}.insteadOf", url)
    slug = "2026-10-01-old-plan"
    owed = JournalEntry(
        kind="owed",
        scope="plan",
        id="owed-phase-2",
        created="2026-10-01T10:00:00+00:00",
        title="phase 2 owed",
        body=owed_body(what="do it", why="manual", how="resolve it", key=f"plan:{slug}#p2"),
    )
    path = archived_journal_path(root, "plan", slug)
    for entry in (
        owed,
        resolution_entry(
            target=owed, scope="plan", taken={owed.id}, created="2026-10-01T11:00:00+00:00",
            state="open", body="filed", filed_as=HELD_REF,
        ),
        resolution_entry(
            target=owed, scope="plan", taken={owed.id, f"{owed.id}-resolved"},
            created="2026-11-15T11:00:00+00:00", state="fixed", body="done by hand",
        ),
    ):  # fmt: skip
        append_journal_entry(path, slug, entry)
    write_matrix_fragments(
        root,
        "schema_version: 5\norg: t\nrepo: t\nrows:\n"
        f"  - id: {row_id}\n    capability: c\n    acceptance: a\n"
        "    origin: ['spec:2026-10-01-old#R1']\n"
        f"    levels: {{}}\n    status: walk-owed\n    issues: ['{HELD_REF}']\n",
    )
    commit_all(root, "an owed entry filed and discharged, and the row that holds it")
    return root


def test_a_really_held_owed_issue_renders_refs_and_passes_both_gates(
    tmp_path: Path, live: dict[str, str]
) -> None:
    from fr.record.pr_body import discharged_owed

    row_id = "owed-close-at-merge"  # carries `close`: must not read as a closing keyword
    root = _really_held(tmp_path, row_id)
    assert [d.ref for d in discharged_owed(root)] == [HELD_REF]
    body = _rendered(root, live)
    section = body.split("## Owed actions discharged\n\n")[1].split("\n\n")[0]
    assert section.startswith(f"Refs {HELD_REF} — held: ") and f"`{row_id}`" in section
    assert f"Closes {HELD_REF}" not in body
    live["body"] = body
    _rec, out = _deliver(root)
    assert out.exit_code == 0, out.output


def test_a_really_held_owed_issue_closed_by_hand_is_still_a_premature_close(
    tmp_path: Path, live: dict[str, str]
) -> None:
    root = _really_held(tmp_path, "owed-close-at-merge")
    body = _rendered(root, live)
    live["body"] = f"Closes {HELD_REF}\n\n{body}"
    _rec, out = _deliver(root)
    assert out.exit_code == 2, out.output
    assert "Refs" in out.output and HELD_REF in out.output


# --- review p2-r2, p2-r5: what cannot be read refuses, by name ---------------------


def test_deliver_refuses_when_the_discharges_cannot_be_told(
    tmp_path: Path, live: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.record.pr_body as pr_body

    def unreadable(_root: Path) -> list[pr_body.DischargedOwed]:
        raise pr_body.UnreadableDischargeError("the default ref cannot be read (no remote)")

    monkeypatch.setattr(pr_body, "discharged_owed", unreadable)
    root = _at_deliver(tmp_path)
    live["body"] = _rendered(root, live)
    _rec, out = _deliver(root)
    assert out.exit_code == 2, out.output
    assert "cannot tell which owed actions" in out.output and "default ref" in out.output
    assert load_run_state(root, RUN).steps["deliver"].state == "running"


def test_deliver_refuses_when_the_holds_cannot_be_read(
    tmp_path: Path,
    live: dict[str, str],
    discharged: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fr.record.pr_body as pr_body
    from fr.acceptance.model import AcceptanceError

    root = _at_deliver(tmp_path)
    body = _rendered(root, live)

    def broken(_root: Path, _state: object) -> dict[str, str]:
        raise AcceptanceError("fragments disagree on `repo:`")

    monkeypatch.setattr(pr_body, "run_held_issues", broken)
    live["body"] = body
    _rec, out = _deliver(root)
    assert out.exit_code == 2, out.output
    assert "held open" in out.output and "fragments disagree" in out.output


def test_an_unexpected_error_reading_the_holds_is_not_swallowed(
    tmp_path: Path, discharged: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """p2-r5: the gate catches only the unreadable-input errors; anything else is a
    bug and propagates, never read as "nothing holds it"."""
    import fr.record.pr_body as pr_body
    from fr.commands.run_cmd import _refuse_unclosed_owed

    root = _at_deliver(tmp_path)

    def bug(_root: Path, _state: object) -> dict[str, str]:
        raise RuntimeError("a bug, not an unreadable input")

    monkeypatch.setattr(pr_body, "run_held_issues", bug)
    with pytest.raises(RuntimeError, match="a bug"):
        _refuse_unclosed_owed(root, load_run_state(root, RUN), "no close", "1", "body.md")
