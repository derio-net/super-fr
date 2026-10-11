"""A strategy the repo cannot run (spec 2026-10-12-run-pipeline-failures §B,
R4-R6): the shape default does not apply to a repo without the strategy's
install program, an explicit one is flagged at self-review and at the
brainstorm resolve, and a malformed `strategy:` line shows the accepted form."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.verification.effective import effective_shape_default, install_problem
from fr.verification.model import StrategyManifest
from fr.verification.resolve import resolve_strategy
from fr.verification.rows import shape_default, unrunnable_strategies
from fr.verification.spec_section import Section, SectionError, parse_section

from tests.unit.record_support import RUN, commit_all, fr, write_record
from tests.unit.requirements_support import row, seed_requirements


def _manifest(install: list[str] | None) -> StrategyManifest:
    return resolve_strategy("candidate", None).model_copy(update={"install": install})


def _install(root: Path, executable: bool = True) -> None:
    path = root / ".fr" / "candidate-install"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755 if executable else 0o644)


# --- install_problem ----------------------------------------------------------


def test_install_problem_is_none_without_an_install_a_bare_command_or_an_absolute_path(
    tmp_path: Path,
) -> None:
    assert install_problem(_manifest(None), tmp_path) is None
    assert install_problem(_manifest(["sh", "-c", "x"]), tmp_path) is None
    assert install_problem(_manifest(["/bin/sh"]), tmp_path) is None


def test_install_problem_names_a_missing_and_a_non_executable_program(tmp_path: Path) -> None:
    manifest = _manifest([".fr/candidate-install", "{prefix}"])
    missing = install_problem(manifest, tmp_path)
    assert missing is not None and ".fr/candidate-install" in missing
    assert "does not exist" in missing
    _install(tmp_path, executable=False)
    not_exec = install_problem(manifest, tmp_path)
    assert not_exec is not None and "is not executable" in not_exec
    _install(tmp_path)
    assert install_problem(manifest, tmp_path) is None


# --- effective_shape_default (R4) ---------------------------------------------


def test_the_shape_default_is_dropped_without_the_install_program(tmp_path: Path) -> None:
    assert effective_shape_default("candidate", tmp_path) is None
    _install(tmp_path)
    assert effective_shape_default("candidate", tmp_path) == "candidate"


def test_an_unresolvable_shape_default_is_returned_unfiltered(tmp_path: Path) -> None:
    assert effective_shape_default("no-such-strategy", tmp_path) == "no-such-strategy"
    assert effective_shape_default(None, tmp_path) is None


def test_rows_shape_default_applies_the_filter(tmp_path: Path) -> None:
    from fr.run.model import RunState

    state = RunState(
        run="r1",
        workflow="fr-goal@1",
        branch="b",
        started="2026-10-12T00:00:00+00:00",
        cursor="spec",
        steps={},
    )
    assert shape_default(tmp_path, state) is None
    _install(tmp_path)
    assert shape_default(tmp_path, state) == "candidate"


def test_a_missing_install_program_is_what_the_walk_contract_said(tmp_path: Path) -> None:
    from fr.verification.walk import WalkError, _contract

    manifest = resolve_strategy("candidate", tmp_path)
    with pytest.raises(WalkError) as e:
        _contract(tmp_path, manifest)
    assert str(e.value) == (
        "strategy 'candidate' needs the repo's executable `.fr/candidate-install` "
        f"<prefix> <source> (the candidate-install contract, spec R8), and "
        f"{tmp_path / '.fr/candidate-install'} does not exist"
    )
    _install(tmp_path, executable=False)
    with pytest.raises(WalkError, match="is not executable"):
        _contract(tmp_path, manifest)
    nothing = manifest.model_copy(update={"install": None})
    with pytest.raises(WalkError, match="nothing to walk"):
        _contract(tmp_path, nothing)


# --- walk_owed -----------------------------------------------------------------


def _matrix(tmp_path: Path, spec_rel: str):
    from fr.acceptance.model import load_matrix

    seed_requirements(tmp_path, spec_rel)
    return load_matrix(tmp_path / "docs/acceptance/matrix.yaml")


def test_walk_owed_owes_nothing_from_the_default_when_every_row_says_none(
    tmp_path: Path,
) -> None:
    from fr.verification.rows import SpecVerification
    from fr.verification.walk import walk_owed

    spec_rel = "docs/spec.md"
    section = parse_section("## Verification\n\n- req-r1: none — covered by unit tests\n")
    matrix = _matrix(tmp_path, spec_rel)
    ref = f"t:{spec_rel}"

    def owed():
        default = effective_shape_default("candidate", tmp_path)
        return walk_owed(matrix, ref, SpecVerification(tmp_path, section, default), tmp_path)

    assert not owed().owed
    _install(tmp_path)
    assert owed().run_strategy == "candidate"


# --- unrunnable_strategies (R5) -------------------------------------------------


def test_unrunnable_strategies_names_each_explicit_strategy_once(tmp_path: Path) -> None:
    from fr.acceptance.model import Row

    section = parse_section(
        "## Verification\n\nstrategy: candidate\n- a: candidate — x\n- b: none — y\n"
    )
    assert isinstance(section, Section)
    rows = [Row.model_validate({**row("docs/spec.md", rid="c", verify="candidate")})]
    (msg,) = unrunnable_strategies(tmp_path, section, rows)
    assert "candidate" in msg and ".fr/candidate-install" in msg
    assert "strategy: none" in msg and "add the executable" in msg
    _install(tmp_path)
    assert unrunnable_strategies(tmp_path, section, rows) == []


def test_unrunnable_strategies_ignores_none_and_the_shape_default(tmp_path: Path) -> None:
    section = parse_section("## Verification\n\n- a: none — covered\n")
    assert section is not None
    assert unrunnable_strategies(tmp_path, section, []) == []


def test_self_review_errors_on_an_explicit_unrunnable_strategy(tmp_path: Path) -> None:
    from tests.unit.test_plan_self_review_verification import _row, _setup

    errors = _setup(
        tmp_path, "strategy: candidate\n", [_row("c", "    scenario: s.sh\n")], install=False
    )
    assert any(
        "candidate" in e and ".fr/candidate-install" in e and "strategy: none" in e for e in errors
    ), errors


def test_the_brainstorm_resolve_warns_and_still_resolves(tmp_path: Path) -> None:
    from tests.integration.test_fr_goal_shape import _workspace

    root = _workspace(tmp_path, "feat/unrun")
    spec_rel = "docs/spec.md"
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / spec_rel).write_text("# spec\n\n## Verification\n\nstrategy: candidate\n")
    seed_requirements(root, spec_rel)
    commit_all(root, "spec")
    for argv in (
        ["run", "start", "fr-goal", "--branch", "feat/unrun", "--run-id", RUN],
        ["run", "advance", RUN],
    ):
        out = fr(root, argv)
        assert out.exit_code == 0, (argv, out.output)
    record = write_record(
        root,
        {
            "schema_version": __import__("fr.record.model", fromlist=["x"]).RECORD_SCHEMA_VERSION,
            "run": RUN,
            "step": "brainstorm",
            "outcome": "done",
            "emitted": {"spec": spec_rel},
            "evidence": {"answered_by": "agent"},
        },
    )
    out = fr(root, ["run", "resolve", RUN, "--step", "brainstorm", "--record", str(record)])
    assert out.exit_code == 0, out.output
    assert "warning:" in out.output and "candidate" in out.output
    assert "strategy: none" in out.output


# --- R6 -------------------------------------------------------------------------


def test_a_malformed_strategy_line_shows_the_accepted_form() -> None:
    with pytest.raises(SectionError) as e:
        parse_section("## Verification\n\nstrategy: none — nothing deploys\n")
    msg = str(e.value)
    assert "strategy: <name>" in msg
    assert "- <row-id>: <strategy|none> — <reason>" in msg
    assert "line" in msg


# --- review findings (phase 2) ---------------------------------------------------


def test_p2_r1_a_per_row_line_alone_is_flagged_and_names_its_row(tmp_path: Path) -> None:
    section = parse_section("## Verification\n\n- a: candidate — x\n")
    assert isinstance(section, Section) and section.strategy is None
    (msg,) = unrunnable_strategies(tmp_path, section, [])
    assert "candidate" in msg and "`- a:` line" in msg
    assert "- <row-id>: none" in msg and "set-status" not in msg
    assert "`strategy: none`" not in msg


def test_p2_r1_a_rows_verify_alone_is_flagged_and_names_the_row_and_the_fix(
    tmp_path: Path,
) -> None:
    from fr.acceptance.model import Row

    section = parse_section("## Verification\n\n- b: none — covered\n")
    assert isinstance(section, Section) and section.strategy is None
    rows = [Row.model_validate({**row("docs/spec.md", rid="c", verify="candidate")})]
    (msg,) = unrunnable_strategies(tmp_path, section, rows)
    assert "row `c`'s own `verify:`" in msg
    assert "--verify none" in msg and "outranks" in msg
    assert "`strategy: none`" not in msg


def test_p2_r1_self_review_flags_a_per_row_line_with_no_strategy_line(tmp_path: Path) -> None:
    from tests.unit.test_plan_self_review_verification import _row, _setup

    errors = _setup(
        tmp_path,
        "- c: candidate — x\n",
        [_row("c", "    scenario: s.sh\n")],
        install=False,
    )
    assert any("candidate" in e and ".fr/candidate-install" in e for e in errors), errors


def _shape_default_plan(tmp_path: Path, install: bool):
    """A fr-goal plan whose spec section has no `strategy:` line and one row
    with neither a per-row line nor a scenario."""
    from fr.parser import parse as parse_plan

    from tests.unit.test_plan_acceptance_links import _create_plan, _repo
    from tests.unit.test_plan_self_review_verification import SPEC_REL, _row

    repo = _repo(tmp_path, matrix=True)
    if install:
        _install(repo)
    other = _row("other")
    (repo / "docs" / "acceptance" / "matrix.yaml").write_text(
        "schema_version: 4\norg: derio-net\nrepo: own\nrows:\n" + other + _row("c")
    )
    (repo / SPEC_REL).write_text(
        "# Toy\n\n## Requirements\n\nR1. x\n\n## Verification\n\n- other: none — covered\n\n"
        "## Implementation Plans\n\n| Plan | Repo | File | Depends on |\n|--|--|--|--|\n"
    )
    plan_dir = _create_plan(repo)
    with (plan_dir / "_meta.yaml").open("a") as f:
        f.write("workflow: fr-goal\n")
    return repo, parse_plan(plan_dir)


def test_p2_r3_self_review_binds_the_shape_default_only_when_the_repo_can_run_it(
    tmp_path: Path,
) -> None:
    from fr.plan_ops import self_review

    def scenario_errors(sub: str, install: bool) -> list[str]:
        _, plan = _shape_default_plan(tmp_path / sub, install)
        return [
            i.message
            for i in self_review(plan)
            if i.severity == "error" and "scenario" in i.message.lower()
        ]

    assert scenario_errors("no", install=False) == []
    assert any("row `c`" in m for m in scenario_errors("yes", install=True))


def test_p2_r3_visual_verification_binds_the_shape_default_like_self_review(
    tmp_path: Path,
) -> None:
    from fr.run.visual import _verification

    from tests.unit.test_plan_self_review_verification import SPEC_REL

    repo, plan = _shape_default_plan(tmp_path / "a", install=False)
    assert _verification(repo, SPEC_REL, plan).shape_default is None
    repo, plan = _shape_default_plan(tmp_path / "b", install=True)
    assert _verification(repo, SPEC_REL, plan).shape_default == "candidate"


def test_p2_r4_a_non_utf8_spec_never_fails_the_resolve(tmp_path: Path) -> None:
    from fr.commands.run_cmd import _unrunnable_spec_warnings

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/spec.md").write_bytes(b"# spec\n\n## Verification\n\n\xff\xfe\n")
    assert _unrunnable_spec_warnings(tmp_path, "docs/spec.md") == []


def _brainstorm_root(tmp_path: Path, spec_body: str):
    from tests.integration.test_fr_goal_shape import _workspace

    root = _workspace(tmp_path, "feat/unrun")
    spec_rel = "docs/spec.md"
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / spec_rel).write_bytes(spec_body.encode("utf-8", "surrogateescape"))
    seed_requirements(root, spec_rel)
    (root / spec_rel).write_bytes(spec_body.encode("utf-8", "surrogateescape"))
    commit_all(root, "spec")
    for argv in (
        ["run", "start", "fr-goal", "--branch", "feat/unrun", "--run-id", RUN],
        ["run", "advance", RUN],
    ):
        out = fr(root, argv)
        assert out.exit_code == 0, (argv, out.output)
    return root, spec_rel


def test_p2_r4_a_spec_that_cannot_be_decoded_still_resolves_and_advances(
    tmp_path: Path,
) -> None:
    root, spec_rel = _brainstorm_root(
        tmp_path, "# spec\n\n## Verification\n\nstrategy: candidate\n"
    )
    record = write_record(
        root,
        {
            "schema_version": __import__("fr.record.model", fromlist=["x"]).RECORD_SCHEMA_VERSION,
            "run": RUN,
            "step": "brainstorm",
            "outcome": "done",
            "emitted": {"spec": spec_rel},
            "evidence": {"answered_by": "agent"},
        },
    )
    import fr.verification.rows as rows_mod

    orig = rows_mod.spec_section_at

    def boom(*a, **k):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    rows_mod.spec_section_at = boom
    try:
        out = fr(root, ["run", "resolve", RUN, "--step", "brainstorm", "--record", str(record)])
    finally:
        rows_mod.spec_section_at = orig
    assert out.exit_code == 0, out.output
    assert "warning:" not in out.output
    status = fr(root, ["run", "status", RUN])
    assert "brainstorm" in status.output and status.exit_code == 0


def test_p2_r5_the_flag_form_resolve_prints_the_same_warning(tmp_path: Path) -> None:
    root, spec_rel = _brainstorm_root(
        tmp_path, "# spec\n\n## Verification\n\nstrategy: candidate\n"
    )
    out = fr(
        root,
        [
            "run",
            "resolve",
            RUN,
            "--step",
            "brainstorm",
            "--state",
            "done",
            "--emitted",
            f"spec={spec_rel}",
            "--answered-by",
            "agent",
        ],
    )
    assert out.exit_code == 0, out.output
    assert "warning:" in out.output and "candidate" in out.output
    assert "strategy: none" in out.output
