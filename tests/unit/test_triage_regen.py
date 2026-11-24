"""The pure half of the queue's generated-file and stamp resolution (spec
2026-11-24-ci-economy R9, R10, R11; `fr.triage.regen`)."""

from __future__ import annotations

import pytest
from fr.triage.regen import REGULAR, classify_conflicts, outside_generated, resolve_hunks


def _hunk(ours: str, theirs: str, base: str | None = None) -> str:
    mid = f"||||||| base\n{base}" if base is not None else ""
    return f"<<<<<<< HEAD\n{ours}{mid}=======\n{theirs}>>>>>>> entry\n"


def _page(hunk: str) -> str:
    return f"---\ntitle: A page\n{hunk}covers: [a.py]\n---\n\nBody text.\n"


def _resolved(ours_date: str, theirs_date: str) -> str:
    return _page(_hunk(f"reviewed: {ours_date} ours note\n", f"reviewed: {theirs_date} entry\n"))


# ------------------------------------------------------------- stamp hunks (R10)


@pytest.mark.parametrize(
    ("ours", "theirs", "kept"),
    [
        ("2026-11-20", "2026-11-23", "reviewed: 2026-11-23 entry\n"),
        ("2026-11-23", "2026-11-20", "reviewed: 2026-11-23 ours note\n"),
        ("2026-11-23", "2026-11-23", "reviewed: 2026-11-23 entry\n"),  # equal: the entry's
    ],
)
def test_a_stamp_hunk_takes_the_later_date(ours: str, theirs: str, kept: str) -> None:
    assert resolve_hunks(_resolved(ours, theirs)) == _page(kept)


def test_a_diff3_stamp_hunk_resolves_the_same_way() -> None:
    text = _page(_hunk("reviewed: 2026-11-20 a\n", "reviewed: 2026-11-23 b\n",
                       base="reviewed: 2026-11-01 old\n"))  # fmt: skip
    assert resolve_hunks(text) == _page("reviewed: 2026-11-23 b\n")


def test_a_reviewed_line_outside_front_matter_is_not_a_stamp() -> None:
    text = "---\ntitle: x\n---\n\n" + _hunk("reviewed: 2026-11-20 a\n", "reviewed: 2026-11-23 b\n")
    assert resolve_hunks(text) is None


def test_a_file_without_front_matter_has_no_stamp() -> None:
    assert resolve_hunks(_hunk("reviewed: 2026-11-20 a\n", "reviewed: 2026-11-23 b\n")) is None


def test_two_lines_in_a_stamp_hunk_are_a_real_conflict() -> None:
    hunk = _hunk("reviewed: 2026-11-20 a\ntitle: y\n", "reviewed: 2026-11-23 b\n")
    assert resolve_hunks(_page(hunk)) is None


def test_a_prose_hunk_is_a_real_conflict() -> None:
    text = "---\ntitle: x\n---\n\n" + _hunk("one sentence\n", "another sentence\n")
    assert resolve_hunks(text) is None


# ----------------------------------------------------- generated blocks (R9, R10)


def _readme(hunk: str, name: str = "skills") -> str:
    return (
        f"# Title\n\nIntro.\n\n<!-- generated:{name} -->\n| a | b |\n{hunk}"
        f"| e | f |\n<!-- /generated:{name} -->\n\nOutro.\n"
    )


def test_a_hunk_inside_a_generated_block_takes_ours() -> None:
    text = _readme(_hunk("| ours | row |\n", "| entry | row |\n| more | rows |\n"))
    assert resolve_hunks(text) == _readme("| ours | row |\n")


def test_a_hunk_straddling_a_block_marker_is_a_real_conflict() -> None:
    text = "# T\n<!-- generated:x -->\n| a |\n" + _hunk(
        "| ours |\n<!-- /generated:x -->\nprose a\n", "| entry |\n<!-- /generated:x -->\nprose b\n"
    )
    assert resolve_hunks(text) is None


def test_a_hunk_after_a_closed_block_is_a_real_conflict() -> None:
    text = "<!-- generated:x -->\n| a |\n<!-- /generated:x -->\n" + _hunk("p\n", "q\n")
    assert resolve_hunks(text) is None


def test_a_file_mixing_a_stamp_and_a_block_hunk_resolves_both() -> None:
    text = (
        "---\n" + _hunk("reviewed: 2026-11-23 a\n", "reviewed: 2026-11-20 b\n") + "---\n\n"
        "<!-- generated:t -->\n" + _hunk("ours row\n", "entry row\n") + "<!-- /generated:t -->\n"
    )
    assert resolve_hunks(text) == (
        "---\nreviewed: 2026-11-23 a\n---\n\n"
        "<!-- generated:t -->\nours row\n<!-- /generated:t -->\n"
    )


def test_a_file_with_no_conflict_markers_is_returned_as_it_is() -> None:
    assert resolve_hunks("plain\n") == "plain\n"


def test_an_unterminated_hunk_is_a_real_conflict() -> None:
    assert resolve_hunks("<<<<<<< HEAD\na\n=======\nb\n") is None


# ------------------------------------------------------------ classification (R9)

_BOTH = {2: REGULAR[0], 3: REGULAR[0]}


def test_classify_sorts_paths_into_whole_hunk_and_real() -> None:
    files = {
        ".opencode/skills/x/SKILL.md": "<<<<<<< HEAD\na\n=======\nb\n>>>>>>> e\n",
        "docs/page.md": _resolved("2026-11-20", "2026-11-23"),
        "README.md": _readme(_hunk("ours\n", "entry\n")),
        "src/a.py": _hunk("x = 1\n", "x = 2\n"),
        "gone.md": None,
    }
    got = classify_conflicts(list(files), [".opencode/skills/**"], files.get, lambda p: _BOTH)
    assert got.whole == (".opencode/skills/x/SKILL.md",)
    assert set(got.hunks) == {"docs/page.md", "README.md"}
    assert got.hunks["docs/page.md"] == _page("reviewed: 2026-11-23 entry\n")
    assert got.regenerate == ("README.md",)  # a stamp alone needs no mirror
    assert got.real == ("src/a.py", "gone.md")


def test_a_glob_star_spans_slashes() -> None:
    got = classify_conflicts(["a/b/c.md"], ["a/*"], lambda p: None, lambda p: _BOTH)
    assert got.whole == ("a/b/c.md",) and got.real == ()


# ---------------------------------------------------------------- R11's limits


def test_outside_generated_allows_changes_to_matched_paths_and_inside_blocks() -> None:
    before = {"gen/a.md": "old\n", "README.md": _readme("| c |\n"), "src/x.py": "x\n"}
    after = {"gen/a.md": "new\n", "README.md": _readme("| d |\n"), "src/x.py": "x\n",
             "gen/new.md": "added\n"}  # fmt: skip
    assert outside_generated(before, after, ["gen/*"]) == []


def test_outside_generated_lists_other_changes_additions_and_removals() -> None:
    before = {"README.md": _readme("| c |\n"), "src/x.py": "x\n", "doc.md": "d\n"}
    after = {"README.md": _readme("| c |\n").replace("Outro.", "Changed."), "src/x.py": "y\n",
             "new.txt": "n\n"}  # fmt: skip
    assert outside_generated(before, after, ["gen/*"]) == [
        "README.md",
        "doc.md",
        "new.txt",
        "src/x.py",
    ]


def test_outside_generated_counts_a_block_renamed_or_added_as_outside() -> None:
    before = {"README.md": "<!-- generated:a -->\nx\n<!-- /generated:a -->\n"}
    after = {"README.md": "<!-- generated:b -->\nx\n<!-- /generated:b -->\n"}
    assert outside_generated(before, after, []) == ["README.md"]


# ------------------------------------- security review: what counts as hunk-resolved


def test_a_conflicted_path_with_no_marker_hunk_is_real() -> None:
    got = classify_conflicts(["a.md"], [], lambda p: "no markers here\n", lambda p: _BOTH)
    assert got.real == ("a.md",) and got.hunks == {}


@pytest.mark.parametrize(
    "stages",
    [
        {3: "100644"},  # modify/delete: ours deleted it
        {2: "100644"},  # modify/delete: the entry deleted it
        {2: "120000", 3: "100644"},  # a type change: a symlink on one side
        {2: "160000", 3: "160000"},  # a submodule
        {},  # no unmerged stages read at all
    ],
)
def test_a_path_whose_stages_are_not_two_regular_blobs_is_real(stages: dict[int, str]) -> None:
    text = _resolved("2026-11-20", "2026-11-23")
    got = classify_conflicts(["docs/p.md"], [], lambda p: text, lambda p: stages)
    assert got.real == ("docs/p.md",)


def test_a_whole_generated_path_ours_deleted_is_real() -> None:
    got = classify_conflicts(["gen/a"], ["gen/*"], lambda p: None, lambda p: {3: "100644"})
    assert got.real == ("gen/a",) and got.whole == ()
