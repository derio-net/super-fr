"""`fr plan self-review` reads the spec's `## Verification` (spec
2026-10-06-verification-strategies §B, R6/R10): a malformed section, a
post-merge or `none` row with no reason, and an agent pre-merge row with no
`scenario` are each refused by name; a spec with no section passes unchanged.
"""

from __future__ import annotations

from pathlib import Path

from fr.parser import parse as parse_plan
from fr.plan_ops import self_review

from tests.unit.test_plan_acceptance_links import _create_plan, _repo

SPEC_REL = "docs/superpowers/specs/2026-07-04-toy.md"
ORIGIN = f"own:{SPEC_REL}#R1"


def _row(rid: str, extra: str = "") -> str:
    return (
        f"  - id: {rid}\n"
        '    capability: "Cap"\n'
        f'    acceptance: "{rid}"\n'
        f'    origin: ["{ORIGIN}"]\n'
        "    status: not-implemented\n"
        f"{extra}"
    )


def _setup(tmp_path: Path, section: str | None, rows: list[str]) -> list[str]:
    repo = _repo(tmp_path, matrix=True)
    (repo / "docs" / "acceptance" / "matrix.yaml").write_text(
        "schema_version: 4\norg: derio-net\nrepo: own\nrows:\n" + "".join(rows)
    )
    body = "# Toy\n\n## Requirements\n\nR1. x\n\n"
    if section is not None:
        body += "## Verification\n\n" + section + "\n"
    body += "## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|--|--|--|--|\n"
    (repo / SPEC_REL).write_text(body)
    plan_dir = _create_plan(repo)
    return [
        i.message
        for i in self_review(parse_plan(plan_dir))
        if i.severity == "error" and "verification" in i.message.lower()
    ]


def test_a_spec_with_no_section_passes_unchanged(tmp_path: Path) -> None:
    assert _setup(tmp_path, None, [_row("a", "    verify: live\n")]) == []


def test_a_malformed_section_fails_naming_the_line(tmp_path: Path) -> None:
    (msg,) = _setup(tmp_path, "strategy: candidate\n- a live no dash\n", [_row("a")])
    assert "line" in msg and "malformed" in msg


def test_a_post_merge_or_none_row_without_a_reason_fails(tmp_path: Path) -> None:
    errors = _setup(
        tmp_path,
        "strategy: candidate\n- b: none\n",
        [
            _row("a", "    verify: live\n    scenario: s.sh\n"),
            _row("b"),
            _row("c", "    scenario: s.sh\n"),
        ],
    )
    assert len(errors) == 2, errors
    assert any("`a`" in e and "live" in e and "reason" in e for e in errors)
    assert any("`b`" in e and "none" in e and "reason" in e for e in errors)


def test_reasons_in_the_section_satisfy_the_check(tmp_path: Path) -> None:
    errors = _setup(
        tmp_path,
        "strategy: candidate\n"
        "- a: live — needs the released build\n"
        "- b: none — unit tests cover it\n",
        [_row("a", "    verify: live\n"), _row("b"), _row("c", "    scenario: s.sh\n")],
    )
    assert errors == []


def test_an_agent_pre_merge_row_without_a_scenario_fails(tmp_path: Path) -> None:
    (msg,) = _setup(tmp_path, "strategy: candidate\n", [_row("c")])
    assert "`c`" in msg and "scenario" in msg and "candidate" in msg


def test_an_unresolvable_strategy_fails_by_name(tmp_path: Path) -> None:
    (msg,) = _setup(tmp_path, "strategy: bogus\n", [_row("c", "    scenario: s.sh\n")])
    assert "bogus" in msg
