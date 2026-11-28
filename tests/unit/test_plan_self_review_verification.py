"""`fr plan self-review` reads the spec's `## Verification` (spec
2026-10-06-verification-strategies §B, R6/R10): a malformed section, a
post-merge or `none` row with no reason, and an agent pre-merge row with no
`scenario` are each refused by name; a spec with no section passes unchanged.
"""

from __future__ import annotations

from pathlib import Path

from fr.parser import parse as parse_plan
from fr.plan_ops import self_review

from tests.unit.acceptance_helpers import write_matrix_fragments
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


def _setup(
    tmp_path: Path, section: str | None, rows: list[str], *, install: bool = True
) -> list[str]:
    repo = _repo(tmp_path, matrix=True)
    if install:  # the repo can run `candidate` (R5 flags an explicit one it cannot)
        program = repo / ".fr" / "candidate-install"
        program.parent.mkdir(parents=True, exist_ok=True)
        program.write_text("#!/bin/sh\n")
        program.chmod(0o755)
    write_matrix_fragments(
        repo, "schema_version: 4\norg: derio-net\nrepo: own\nrows:\n" + "".join(rows)
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
    # no section and no row `verify:` — the world before strategies (a row with its
    # own `verify:` is checked even so: spec 2026-10-14 R24, test_row_verification_issues)
    assert _setup(tmp_path, None, [_row("a")]) == []


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


# --- ops-gate-truth R16: a gated row no step of its gate names -------------------------

import pytest  # noqa: E402


def _coverage(
    tmp_path: Path, section: str, test_plan: str, rows: list[str], *, ops: bool = False
) -> list[tuple[str, str]]:
    repo = _repo(tmp_path, matrix=True)
    write_matrix_fragments(
        repo, "schema_version: 4\norg: derio-net\nrepo: own\nrows:\n" + "".join(rows)
    )
    body = "# Toy\n\n## Requirements\n\nR1. x\n\n## Verification\n\n" + section + "\n"
    body += "## Test Plan\n\n" + test_plan + "\n"
    body += "## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|--|--|--|--|\n"
    (repo / SPEC_REL).write_text(body)
    plan_dir = _create_plan(repo)
    if ops:
        (plan_dir / "ops.yaml").write_text(
            "schema_version: 1\nops:\n  - id: k\n    summary: s\n    phase: post-merge\n"
        )
    return [
        (i.severity, i.message)
        for i in self_review(parse_plan(plan_dir))
        if "(rows:" in i.message
    ]


DEVOPS = "strategy: live\ngate: devops\n- a: live — walked after the merge\n"


def test_a_devops_row_no_devops_step_names_warns(tmp_path: Path) -> None:
    found = _coverage(tmp_path, DEVOPS, "1. [devops] walk it\n", [_row("a")])
    assert [s for s, _ in found] == ["warn"]
    assert "`a`" in found[0][1] and "devops" in found[0][1]


def test_a_devops_row_a_devops_step_names_is_quiet(tmp_path: Path) -> None:
    assert _coverage(tmp_path, DEVOPS, "1. [devops] (rows: a) walk it\n", [_row("a")]) == []


def test_a_plan_with_ops_counts_an_untagged_step_as_devops(tmp_path: Path) -> None:
    tester = "strategy: none\ngate: developer\n- t: live — walked by the tester\n"
    plan = "1. (rows: t) walk it\n"
    assert _coverage(tmp_path / "a", tester, plan, [_row("t")]) == []
    found = _coverage(tmp_path / "b", tester, plan, [_row("t")], ops=True)
    assert len(found) == 1 and "`t`" in found[0][1] and "tester" in found[0][1]


def test_an_unknown_rows_id_warns(tmp_path: Path) -> None:
    found = _coverage(tmp_path, DEVOPS, "1. [devops] (rows: a, zz) walk it\n", [_row("a")])
    assert [s for s, _ in found] == ["warn"] and "`zz`" in found[0][1]


@pytest.mark.parametrize("off", ["acceptance", "test_plan", "gates"])
def test_nothing_is_reported_with_a_feature_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, off: str
) -> None:
    import fr.settings

    real = fr.settings.disabled
    monkeypatch.setattr(fr.settings, "disabled", lambda r, f: f == off or real(r, f))
    found = _coverage(tmp_path, DEVOPS, "1. [devops] (rows: zz) walk it\n", [_row("a")])
    assert found == []


def test_nothing_is_reported_for_a_cross_repo_spec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("fr.plan_review.checks.is_cross_repo_spec", lambda s: True)
    assert _coverage(tmp_path, DEVOPS, "1. [devops] (rows: zz) walk it\n", [_row("a")]) == []
