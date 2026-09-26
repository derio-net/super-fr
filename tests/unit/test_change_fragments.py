"""Change fragments (spec 2026-09-26-version-bump-churn §3.A, §5, §7 item 2).

`scripts/changes.py` owns the fragment schema: `bump` (patch|minor|major) and a
non-empty single-line `summary`, nothing else. The CI gate, the release script
and this test all import it, so there is one definition of a valid fragment.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "changes.py"
spec = importlib.util.spec_from_file_location("changes", SCRIPT)
assert spec and spec.loader
changes = importlib.util.module_from_spec(spec)
sys.modules["changes"] = changes
spec.loader.exec_module(changes)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def test_a_valid_fragment_parses(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "feat-foo.yaml",
        "# .changes/feat-foo.yaml\n"
        "bump: minor            # patch | minor | major\n"
        "summary: fr triage batches — create, dispatch, merge in order\n",
    )
    fragment = changes.parse_fragment(path)
    assert fragment.bump == "minor"
    assert fragment.summary == "fr triage batches — create, dispatch, merge in order"
    assert fragment.path == path


@pytest.mark.parametrize("bump", ["patch", "minor", "major"])
def test_every_bump_level_is_accepted(tmp_path: Path, bump: str) -> None:
    path = _write(tmp_path, "x.yaml", f"bump: {bump}\nsummary: something\n")
    assert changes.parse_fragment(path).bump == bump


def test_a_quoted_summary_is_unquoted(tmp_path: Path) -> None:
    path = _write(tmp_path, "x.yaml", "bump: 'patch'\nsummary: \"fix: a colon # and a hash\"\n")
    fragment = changes.parse_fragment(path)
    assert (fragment.bump, fragment.summary) == ("patch", "fix: a colon # and a hash")


@pytest.mark.parametrize(
    ("text", "field"),
    [
        ("bump: huge\nsummary: s\n", "bump"),
        ("summary: s\n", "bump"),
        ("bump: patch\n", "summary"),
        ("bump: patch\nsummary:\n", "summary"),
        ("bump: patch\nsummary: '   '\n", "summary"),
        ("bump: patch\nsummary: |\n  line one\n  line two\n", "summary"),
        ("bump: patch\nsummary: >\n  folded\n", "summary"),
        ("bump: patch\nsummary: line one\n  line two\n", "summary"),
        ("bump: patch\nsummary: s\nissue: 12\n", "issue"),
        ("bump: patch\nbump: minor\nsummary: s\n", "bump"),
    ],
)
def test_an_invalid_fragment_is_refused_naming_field_and_file(
    tmp_path: Path, text: str, field: str
) -> None:
    path = _write(tmp_path, "bad-frag.yaml", text)
    with pytest.raises(changes.FragmentError) as err:
        changes.parse_fragment(path)
    message = str(err.value)
    assert "bad-frag.yaml" in message
    assert field in message


def test_an_empty_file_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, "empty.yaml", "")
    with pytest.raises(changes.FragmentError, match="empty.yaml"):
        changes.parse_fragment(path)


def test_aggregate_returns_the_highest_bump(tmp_path: Path) -> None:
    frags = [
        changes.Fragment(tmp_path / "a.yaml", "patch", "a"),
        changes.Fragment(tmp_path / "b.yaml", "major", "b"),
        changes.Fragment(tmp_path / "c.yaml", "minor", "c"),
    ]
    assert changes.aggregate(frags) == "major"
    assert changes.aggregate(frags[:1]) == "patch"
    assert changes.aggregate(frags[::2]) == "minor"


def test_aggregate_of_nothing_is_none() -> None:
    assert changes.aggregate([]) is None


@pytest.mark.parametrize(
    ("version", "bump", "expected"),
    [
        ("4.23.0", "patch", "4.23.1"),
        ("4.23.5", "minor", "4.24.0"),
        ("4.23.5", "major", "5.0.0"),
        ("4.23.5", None, "4.23.5"),
    ],
)
def test_bumped(version: str, bump: str | None, expected: str) -> None:
    assert changes.bumped(version, bump) == expected


def test_load_pending_skips_the_readme(tmp_path: Path) -> None:
    changes_dir = tmp_path / ".changes"
    changes_dir.mkdir()
    (changes_dir / "README.md").write_text("# not a fragment\n")
    (changes_dir / "feat-b.yaml").write_text("bump: minor\nsummary: b\n")
    (changes_dir / "fix-a.yaml").write_text("bump: patch\nsummary: a\n")
    pending = changes.load_pending(tmp_path)
    assert [f.path.name for f in pending] == ["feat-b.yaml", "fix-a.yaml"]


def test_load_pending_with_no_directory_is_empty(tmp_path: Path) -> None:
    assert changes.load_pending(tmp_path) == []


def test_load_pending_refuses_an_invalid_fragment(tmp_path: Path) -> None:
    changes_dir = tmp_path / ".changes"
    changes_dir.mkdir()
    (changes_dir / "bad.yaml").write_text("bump: tiny\nsummary: s\n")
    with pytest.raises(changes.FragmentError, match="bad.yaml"):
        changes.load_pending(tmp_path)


def test_this_repos_own_changes_directory_validates() -> None:
    assert (REPO / ".changes" / "README.md").is_file()
    for fragment in changes.load_pending(REPO):
        assert fragment.bump in changes.BUMPS
