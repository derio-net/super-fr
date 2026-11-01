"""Test Plan step tags and the effective step gate (spec 2026-10-22-fr-ops R12, §G)."""

from __future__ import annotations

from fr.ops.testplan import effective_step_gate
from fr.spec import Step, test_plan_steps


def _steps(*items: str) -> list[Step]:
    return test_plan_steps("# S\n\n## Test Plan\n\n" + "\n".join(items) + "\n")


def test_a_literal_devops_or_tester_tag_takes_the_gate_and_leaves_the_text() -> None:
    devops, tester = _steps("- [devops] walk the stage", "1. [tester] click the page")
    assert (devops.gate, devops.text) == ("devops", "walk the stage")
    assert (tester.gate, tester.text) == ("tester", "click the page")


def test_any_other_leading_bracket_stays_text() -> None:
    texts = ["[ ] an open box", "[x] a ticked box", "[link](https://example.com) then prose"]
    steps = _steps(*(f"- {t}" for t in texts))
    assert [(s.gate, s.text) for s in steps] == [(None, t) for t in texts]


def test_only_the_exact_lowercase_tag_counts() -> None:
    steps = _steps("- [DevOps] x", "- [devops]x", "- [operator] x", "- prose [devops] later")
    assert [s.gate for s in steps] == [None, None, None, None]
    assert steps[0].text == "[DevOps] x" and steps[3].text == "prose [devops] later"


def test_an_untagged_step_reads_byte_identically_to_before() -> None:
    (step,) = _steps("- Run `fr ops status` and\n  read the [x] box")
    assert step == Step(1, "Run `fr ops status` and read the [x] box")
    assert step.gate is None


def test_a_prose_only_section_is_one_untagged_step() -> None:
    (step,) = test_plan_steps("## Test Plan\n\n[devops] prose only.\n")
    assert step.gate is None and step.text == "[devops] prose only."


def test_effective_gate_tag_wins_then_devops_then_tester_then_none() -> None:
    tagged = Step(1, "x", "tester")
    plain = Step(2, "y")
    both = frozenset({"developer", "devops", "tester"})
    assert effective_step_gate(tagged, both) == "tester"
    assert effective_step_gate(Step(1, "x", "devops"), frozenset()) == "devops"
    assert effective_step_gate(plain, both) == "devops"
    assert effective_step_gate(plain, frozenset({"tester", "developer"})) == "tester"
    assert effective_step_gate(plain, frozenset({"developer"})) is None


# --- the op pointer and the raw lines (spec 2026-11-01-ops-gate-probes R6, R2) ---------


def test_a_pointer_after_the_tag_names_the_op_and_leaves_the_text() -> None:
    (step,) = _steps("- [devops] (op: guest-verify) Run it")
    assert step == Step(1, gate="devops", op="guest-verify", text="Run it")


def test_a_pointer_without_a_tag_still_names_the_op() -> None:
    (step,) = _steps("- (op: x) do")
    assert (step.gate, step.op, step.text) == (None, "x", "do")


def test_a_pointer_needs_whitespace_after_it() -> None:
    (step,) = _steps("- (op:x)do it")
    assert (step.op, step.text) == (None, "(op:x)do it")


def test_a_pointer_mid_text_is_not_one() -> None:
    (step,) = _steps("- run (op: x) later")
    assert (step.op, step.text) == (None, "run (op: x) later")


def test_raw_keeps_the_items_lines_as_written_fences_included() -> None:
    lines = ["- [devops] converge", "    ```bash", "    pulumi up --yes", "    ```"]
    first, second = _steps(*lines, "- next")
    assert first.raw == tuple(lines)
    assert second.raw == ("- next",)
    assert first.op is None
