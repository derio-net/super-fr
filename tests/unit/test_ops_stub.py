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


# --- review round 1 (p3-r1 .. p3-r7) ------------------------------------------------


def _reparse(text: str):
    from fr.spec import test_plan_steps

    return test_plan_steps(text)


def test_a_tag_alone_on_the_first_line_gets_the_pointer_after_the_tag() -> None:
    spec = "## Test Plan\n\n1. [devops]\n   converge with `pulumi up --yes`\n"
    _, edits = propose(spec, set(), {"devops"})
    out = apply_edits(spec, edits)
    assert out.splitlines()[2] == "1. [devops] (op: step-1)"
    (step,) = _reparse(out)
    assert (step.gate, step.op) == ("devops", "step-1")


def test_a_lazy_continuation_keeps_the_pointer_on_the_first_line() -> None:
    spec = "## Test Plan\n\n1. [devops] converge\nwith `pulumi up --yes`\n"
    _, edits = propose(spec, set(), {"devops"})
    (step,) = _reparse(apply_edits(spec, edits))
    assert (step.gate, step.op) == ("devops", "step-1")


FENCED = """\
## Test Plan

1. [devops] bring it up
   ```bash
   # deploy it

   helm upgrade x \\
     --install y
   kubectl rollout status deploy/x
   ```
"""


def test_apply_drops_comments_joins_continuations_and_summary_has_no_script() -> None:
    (op,), _ = propose(FENCED, set(), {"devops"})
    assert op["apply"] == "helm upgrade x --install y && kubectl rollout status deploy/x"
    assert op["summary"] == "bring it up"
    assert "```" not in str(op["summary"])


def test_a_duplicate_line_in_an_earlier_fence_is_not_the_one_edited() -> None:
    spec = (
        "## Test Plan\n\n"
        "```\n1. [devops] converge `pulumi up --yes`\n```\n\n"
        "1. [devops] converge `pulumi up --yes`\n"
    )
    _, edits = propose(spec, set(), {"devops"})
    out = apply_edits(spec, edits)
    assert out.splitlines()[3] == "1. [devops] converge `pulumi up --yes`"
    assert out.splitlines()[6] == "1. [devops] (op: step-1) converge `pulumi up --yes`"


def test_the_step_records_its_line_and_equality_ignores_it() -> None:
    from fr.spec import Step

    (step,) = _reparse("# X\n\n## Test Plan\n\n- a\n")
    assert step.line == 4 and step == Step(1, "a")


def test_crlf_survives_apply_edits() -> None:
    spec = "## Test Plan\r\n\r\n1. [devops] converge `pulumi up --yes`\r\n"
    _, edits = propose(spec, set(), {"devops"})
    out = apply_edits(spec, edits)
    assert out == "## Test Plan\r\n\r\n1. [devops] (op: step-1) converge `pulumi up --yes`\r\n"


OPS_EXISTING = """\
# runbook for the stack
schema_version: 2
ops:
  # the key
  - id: create-key   # café
    summary: créer la clé
    phase: pre-merge
    check: 'true'

# trailing note
"""


def _new_op() -> list[dict[str, object]]:
    return [{"id": "step-1", "summary": "naïve", "phase": "post-merge", "check": "TODO"}]


def test_append_keeps_comments_and_non_ascii_and_parses_with_the_loader() -> None:
    import yaml
    from fr.ops.stub import append_ops

    out = append_ops(OPS_EXISTING, _new_op())
    assert out.startswith(OPS_EXISTING.split("\n\n# trailing")[0])
    for kept in (
        "# runbook for the stack",
        "# the key",
        "# café",
        "créer la clé",
        "# trailing note",
    ):
        assert kept in out
    assert "naïve" in out
    data = yaml.safe_load(out)
    assert [o["id"] for o in data["ops"]] == ["create-key", "step-1"]
    assert out.index("step-1") < out.index("# trailing note")


def test_append_handles_an_empty_ops_list_a_missing_key_and_a_new_file() -> None:
    import yaml
    from fr.ops.stub import append_ops

    empty = append_ops("# keep\nschema_version: 1\nops: []  # none yet\n", _new_op())
    assert "# keep" in empty and "# none yet" in empty
    data = yaml.safe_load(empty)
    assert data["schema_version"] == 2 and [o["id"] for o in data["ops"]] == ["step-1"]
    missing = append_ops("# only a comment\nschema_version: 2\n", _new_op())
    assert "# only a comment" in missing
    assert yaml.safe_load(missing)["ops"][0]["id"] == "step-1"
    fresh = append_ops(None, _new_op())
    assert yaml.safe_load(fresh)["schema_version"] == 2 and "naïve" in fresh


def test_append_refuses_a_populated_flow_list() -> None:
    from fr.ops.stub import append_ops

    with pytest.raises(StubError):
        append_ops("schema_version: 2\nops: [{id: a, summary: s, phase: p, check: x}]\n", _new_op())


def test_a_stub_is_unverifiable_in_the_engine_and_never_probed() -> None:
    from fr.ops.model import Op

    from tests.unit.test_ops_engine import FakeRunner, _lo, _one

    (stub, _second), _ = propose(SPEC, set(), {"devops"})
    fields = {k: v for k, v in stub.items() if k not in ("id", "summary", "phase")}
    runner = FakeRunner({})
    row = _one(_lo(**fields), runner)  # type: ignore[arg-type]
    assert Op.model_validate(stub).check == TODO_CHECK
    assert row.state == "UNVERIFIABLE" and "a stub" in (row.reason or "")
    assert runner.calls == []
