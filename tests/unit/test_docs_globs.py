"""Segment-aware globs for `fr docs` (spec 2026-11-11-docs-currency R2)."""

from __future__ import annotations

import pytest
from fr.docs.globs import match


def test_the_package_imports() -> None:
    import fr.docs

    assert fr.docs.__doc__


def test_a_star_stays_inside_one_segment() -> None:
    assert match("docs/*.md", "docs/ops.md")
    assert not match("docs/*.md", "docs/superpowers/x.md")
    assert not match("docs/*.md", "docs/explainers/a.md")


def test_a_double_star_spans_segments() -> None:
    assert match("plugins/**/SKILL.md", "plugins/super-fr/skills/fr-goal/SKILL.md")
    assert match("docs/**", "docs/a/b/c.md")
    assert match("docs/**", "docs/a.md")
    assert match("**/x.py", "x.py")
    assert match("**/x.py", "a/b/x.py")


def test_a_question_mark_stays_in_a_segment() -> None:
    assert match("docs/?.md", "docs/a.md")
    assert not match("docs/?.md", "docs/ab.md")
    assert not match("docs?a.md", "docs/a.md")


def test_a_literal_path_matches_itself() -> None:
    assert match("packages/fr/src/fr/cli.py", "packages/fr/src/fr/cli.py")
    assert not match("packages/fr/src/fr/cli.py", "packages/fr/src/fr/cli.pyc")


@pytest.mark.parametrize("path", ["a.b", "axb"])
def test_regex_metacharacters_in_a_pattern_are_literal(path: str) -> None:
    assert match("a.b", path) is (path == "a.b")
