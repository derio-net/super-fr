"""Path rules in force (spec 2026-11-12-review-lenses R6): the default branch's rules
together with the branch's, so a branch can add a rule and never drop one."""

from __future__ import annotations

from fr.lenses.model import PathRule
from fr.lenses.rules import matched, rules_in_force

AUTH = "require:\n  - paths: ['src/auth/**']\n    lenses: [security]\n"
SQL = "require:\n  - paths: ['**/migrations/*.sql']\n    lenses: [security, errors]\n"


def test_the_rules_in_force_are_the_union_of_base_and_head() -> None:
    rules = rules_in_force(AUTH, SQL)
    assert [r.paths for r in rules] == [("src/auth/**",), ("**/migrations/*.sql",)]


def test_a_rule_both_hold_is_collapsed() -> None:
    assert rules_in_force(AUTH, AUTH + "disable: []\n") == (
        PathRule(paths=("src/auth/**",), lenses=("security",)),
    )


def test_a_head_that_drops_a_base_rule_still_has_it() -> None:
    rules = rules_in_force(AUTH, "disable: []\n")
    assert [r.lenses for r in rules] == [("security",)]
    assert rules_in_force(AUTH, None) == rules


def test_with_no_default_ref_the_rules_are_heads() -> None:
    assert [r.paths for r in rules_in_force(None, SQL)] == [("**/migrations/*.sql",)]
    assert rules_in_force(None, None) == ()


def test_matched_names_the_rule_and_the_first_matching_file_per_lens() -> None:
    rules = rules_in_force(AUTH, SQL)
    got = matched(
        rules, ["README.md", "src/auth/deep/x.py", "src/auth/y.py", "db/migrations/1.sql"]
    )
    assert set(got) == {"security", "errors"}
    assert got["security"].paths == ("src/auth/**",)
    assert got["security"].file == "src/auth/deep/x.py"
    assert got["errors"].paths == ("**/migrations/*.sql",)
    assert got["errors"].file == "db/migrations/1.sql"


def test_star_spans_slashes_as_in_proportionality() -> None:
    rules = rules_in_force(None, "require:\n  - paths: ['src/*.py']\n    lenses: [tests]\n")
    assert matched(rules, ["src/a/b/c.py"])["tests"].file == "src/a/b/c.py"


def test_nothing_matched_is_empty() -> None:
    assert matched(rules_in_force(AUTH, None), ["docs/readme.md"]) == {}
