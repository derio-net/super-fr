"""The pure docs check (spec 2026-11-11-docs-currency R3, R4, R5)."""

from __future__ import annotations

from fr.docs.check import Finding, check
from fr.docs.model import Page, PageError

PAGE = Page("docs/a.md", ("src/*.py",), "2026-11-11 x")
TRACKED = ["docs/a.md", "src/x.py", "src/y.py", "other.txt"]


def kinds(findings: list[Finding]) -> list[str]:
    return [f.kind for f in findings]


def test_a_covered_change_without_the_page_is_stale() -> None:
    got = check([PAGE], [], TRACKED, ["src/x.py", "src/y.py", "other.txt"], [])
    assert kinds(got) == ["stale"]
    assert got[0].page == "docs/a.md"
    assert got[0].paths == ("src/x.py", "src/y.py")
    assert "docs/a.md" in got[0].message


def test_the_page_in_the_change_satisfies_it() -> None:
    assert check([PAGE], [], TRACKED, ["src/x.py", "docs/a.md"], []) == []


def test_a_page_never_counts_as_a_covered_change_against_itself() -> None:
    selfish = Page("docs/a.md", ("docs/*.md",), "2026-11-11 x")
    assert check([selfish], [], TRACKED, ["docs/a.md"], []) == []


def test_an_unrelated_change_is_clean() -> None:
    assert check([PAGE], [], TRACKED, ["other.txt"], []) == []


def test_a_glob_matching_no_tracked_file_is_dead() -> None:
    page = Page("docs/a.md", ("src/*.py", "gone/**"), "2026-11-11 x")
    got = check([page], [], TRACKED, None, [])
    assert kinds(got) == ["dead-glob"]
    assert got[0].paths == ("gone/**",)


def test_a_page_error_is_a_bad_page() -> None:
    got = check([], [PageError("docs/b.md", "lacks covers")], TRACKED, None, [])
    assert kinds(got) == ["bad-page"]
    assert got[0].page == "docs/b.md" and "lacks covers" in got[0].message


def test_an_uncovered_must_cover_file_is_named() -> None:
    got = check([PAGE], [], TRACKED, None, ["src/*.py", "other.txt"])
    assert kinds(got) == ["uncovered"]
    assert got[0].paths == ("other.txt",)


def test_changed_none_runs_only_the_structural_checks() -> None:
    assert check([PAGE], [], TRACKED, None, []) == []
    assert kinds(check([PAGE], [], TRACKED, None, ["other.txt"])) == ["uncovered"]
