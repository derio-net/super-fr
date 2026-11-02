"""The ops gap (spec 2026-11-01-ops-gate-probes R1, R2, §A): a devops-gated run whose
plan declares no op while its Test Plan steps carry commands."""

from __future__ import annotations

from pathlib import Path

from fr.ops.gap import CommandStep, command_steps, gap_message, ops_gap, step_commands
from fr.spec import Step, test_plan_steps

SPEC_REL = "docs/superpowers/specs/2026-11-01-x-design.md"
PLAN_REL = "docs/superpowers/plans/x"


def _steps(*items: str) -> list[Step]:
    return test_plan_steps("# S\n\n## Test Plan\n\n" + "\n".join(items) + "\n")


def _one(*lines: str) -> tuple[str, ...]:
    (step,) = _steps(*lines)
    return step_commands(step)


# --- step_commands (R2) --------------------------------------------------------------


def test_an_inline_span_starting_with_a_shipped_tool_is_a_command() -> None:
    assert _one("- run `ansible-playbook config/x.yml` on the host") == (
        "ansible-playbook config/x.yml",
    )
    assert _one("- `pulumi up` converges") == ("pulumi up",)


def test_a_span_whose_first_word_is_a_path_is_a_command() -> None:
    assert _one("- run `./scripts/do x`") == ("./scripts/do x",)


def test_a_span_with_a_flag_is_a_command() -> None:
    assert _one("- run `foo --bar`") == ("foo --bar",)


def test_a_prose_span_or_a_lone_path_is_not_a_command() -> None:
    assert _one("- see `ops gap` and `config/x/vault.yml`") == ()


def test_every_non_blank_fenced_line_is_a_command_the_info_string_dropped() -> None:
    lines = [
        "- [devops] converge",
        "    ```bash",
        "    pulumi up --yes",
        "",
        "    make verify",
        "    ```",
    ]
    assert _one(*lines) == ("pulumi up --yes", "make verify")


def test_a_pointed_step_has_no_commands() -> None:
    assert _one("- (op: converge) run `pulumi up`") == ()


def test_command_steps_skips_a_tester_step() -> None:
    steps = _steps("- [tester] run `make check`", "- run `pulumi up`", "- walk the page")
    assert command_steps(steps, {"devops"}) == [CommandStep(2, "run `pulumi up`", ("pulumi up",))]


# --- ops_gap (R1) --------------------------------------------------------------------

SPEC = """\
# X

## Verification

strategy: none
gate: devops

## Test Plan

- run `pulumi up` on the stack
- walk the console by hand
"""


def _repo(tmp_path: Path, ops_yaml: str | None = None) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / SPEC_REL).parent.mkdir(parents=True)
    (root / SPEC_REL).write_text(SPEC)
    plan = root / PLAN_REL
    plan.mkdir(parents=True)
    if ops_yaml is not None:
        (plan / "ops.yaml").write_text(ops_yaml)
    return root, plan


def test_no_gap_without_the_devops_gate(tmp_path: Path) -> None:
    root, plan = _repo(tmp_path)
    assert ops_gap(root, SPEC_REL, plan, {"tester"}) == []


def test_no_gap_when_the_plan_has_an_op(tmp_path: Path) -> None:
    root, plan = _repo(
        tmp_path, "schema_version: 2\nops:\n  - {id: a, summary: s, phase: post-merge}\n"
    )
    assert ops_gap(root, SPEC_REL, plan, {"devops"}) == []


def test_no_gap_with_a_none_acknowledgement(tmp_path: Path) -> None:
    root, plan = _repo(tmp_path, "schema_version: 2\nnone: the stack is converged by hand\n")
    assert ops_gap(root, SPEC_REL, plan, {"devops"}) == []


def test_the_gap_is_the_command_steps(tmp_path: Path) -> None:
    root, plan = _repo(tmp_path)
    expected = [CommandStep(1, "run `pulumi up` on the stack", ("pulumi up",))]
    assert ops_gap(root, SPEC_REL, plan, {"devops"}) == expected
    assert ops_gap(root, SPEC_REL, None, {"devops"}) == expected


# --- gap_message (R3) ----------------------------------------------------------------


def test_the_message_names_each_step_its_commands_and_both_fixes() -> None:
    gap = [CommandStep(2, "t", ("pulumi up", "make verify")), CommandStep(5, "u", ("ssh h",))]
    msg = gap_message(gap, has_plan=True)
    for needle in ("step 2", "pulumi up", "make verify", "step 5", "ssh h", "fr ops stub", "none:"):
        assert needle in msg, (needle, msg)
    assert "will need ops" not in msg


def test_without_a_plan_the_message_says_the_steps_will_need_ops() -> None:
    msg = gap_message([CommandStep(1, "t", ("pulumi up",))], has_plan=False)
    assert "will need ops" in msg and "fr ops stub" in msg and "none:" in msg
