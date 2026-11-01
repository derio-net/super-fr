"""`fr ops stub` (spec 2026-11-01-ops-gate-probes R11, §D): the pure proposal."""

from __future__ import annotations

import pytest
from fr.ops.model import TODO_CHECK
from fr.ops.stub import StubError, apply_edits, propose

SPEC = """\
# X

- run `make x` in the intro (not a step)

## Test Plan

1. [devops] converge with `pulumi up --yes` then `make verify`
2. [tester] run `make check`
3. walk the page and look at it
4. (op: already) run `kubectl get pods -n x`
5. run
   ```bash
   ansible-playbook config/x.yml
   ```

## After
"""


def test_one_op_per_devops_command_step_without_a_pointer() -> None:
    ops, edits = propose(SPEC, set(), {"devops"})
    assert [o["id"] for o in ops] == ["step-1", "step-5"]
    first = ops[0]
    assert first["phase"] == "post-merge"
    assert first["apply"] == "pulumi up --yes && make verify"
    assert first["mutating"] is True
    assert first["check"] == TODO_CHECK
    assert str(first["summary"]).startswith("converge with")
    assert [e.n for e in edits] == [1, 5]


def test_the_summary_is_clipped() -> None:
    spec = "## Test Plan\n\n- run `make x` " + "word " * 50 + "\n"
    (op,), _ = propose(spec, set(), {"devops"})
    assert len(str(op["summary"])) <= 80 and str(op["summary"]).endswith("…")


def test_the_pointer_goes_after_the_tag() -> None:
    _, edits = propose(SPEC, set(), {"devops"})
    out = apply_edits(SPEC, edits)
    assert "1. [devops] (op: step-1) converge with" in out
    assert "5. (op: step-5) run" in out
    assert "- run `make x` in the intro" in out  # outside the Test Plan: untouched
    assert "2. [tester] run `make check`" in out


def test_a_second_proposal_over_the_edited_spec_finds_nothing() -> None:
    _, edits = propose(SPEC, set(), {"devops"})
    assert propose(apply_edits(SPEC, edits), set(), {"devops"}) == ([], [])


def test_a_declared_id_is_refused() -> None:
    with pytest.raises(StubError, match="step-1"):
        propose(SPEC, {"step-1"}, {"devops"})


def test_nothing_when_devops_does_not_own_the_steps() -> None:
    spec = "## Test Plan\n\n- run `make x --y`\n"
    assert propose(spec, set(), {"tester"}) == ([], [])
