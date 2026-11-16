"""Gate names have one definition (spec 2026-11-16 architecture-review-sweep, R9).

`fr.gates` owns the names. The remap value of `.fr/triage.yaml`'s `exit:`, the
strategy manifest's `gate:`, the step tag of a Test Plan line and the ops stub's
leading tag all derive from it. The pinned error lists and JSON schemas below were
captured from the hand-written literals BEFORE they were replaced; they keep the
derived annotations byte-compatible with what an author sees today.
"""

from __future__ import annotations

import re
from typing import Any, Literal, get_args, get_origin

import pytest
from fr.gates import GATES
from fr.ops.stub import _LEAD_RE
from fr.spec import _TAG_RE
from fr.triage.model import ExitBlock
from fr.verification.model import StrategyManifest
from pydantic import ValidationError


def _errors(exc: ValidationError) -> list[tuple[str, str]]:
    return [(e["type"], e["msg"]) for e in exc.errors()]


def accepted(annotation: Any) -> frozenset[str]:
    """Every string a (possibly nested) annotation admits."""
    if get_origin(annotation) is Literal:
        return frozenset(a for a in get_args(annotation) if isinstance(a, str))
    if get_origin(annotation) is dict:
        return accepted(get_args(annotation)[1])
    raise AssertionError(f"not a Literal or dict of one: {annotation!r}")


_EXIT_ERRORS = [
    (
        "literal_error",
        "Input should be 'none', 'developer', 'reviewer', 'tester', 'devops', "
        "'owner' or 'security'",
    )
]
_STRATEGY_ERRORS = [("literal_error", "Input should be 'none', 'tester' or 'devops'")]


def test_pinned_exit_block_error_list() -> None:
    with pytest.raises(ValidationError) as exc:
        ExitBlock(gates={"candidate": "x"})  # type: ignore[dict-item]
    assert _errors(exc.value) == _EXIT_ERRORS


def test_pinned_strategy_gate_error_list() -> None:
    with pytest.raises(ValidationError) as exc:
        StrategyManifest.model_validate(
            {
                "schema": 2,
                "name": "x",
                "kind": "candidate",
                "when": "always",
                "gate": "x",
            }
        )
    gate_errors = [(e["type"], e["msg"]) for e in exc.value.errors() if e["loc"] == ("gate",)]
    assert gate_errors == _STRATEGY_ERRORS


def test_pinned_json_schemas() -> None:
    gates_schema = ExitBlock.model_json_schema()["properties"]["gates"]
    assert gates_schema["additionalProperties"]["enum"] == [
        "none",
        "developer",
        "reviewer",
        "tester",
        "devops",
        "owner",
        "security",
    ]
    gate_schema = StrategyManifest.model_json_schema()["properties"]["gate"]
    assert gate_schema["enum"] == ["none", "tester", "devops"]
    assert gate_schema["default"] == "none"


def test_pinned_tag_patterns() -> None:
    for tag in ("devops", "tester"):
        assert _TAG_RE.match(f"[{tag}] x")
        assert _LEAD_RE.match(f"1. [{tag}] x").group("lead").endswith(f"[{tag}] ")  # type: ignore[union-attr]
    for other in sorted(GATES - {"devops", "tester"}):
        assert _TAG_RE.match(f"[{other}] x") is None
        lead = _LEAD_RE.match(f"1. [{other}] x")
        assert lead is not None and f"[{other}]" not in lead.group("lead")


def _step_tags(pattern: re.Pattern[str]) -> frozenset[str]:
    """Every gate name the Test Plan step-tag pattern accepts."""
    return frozenset(g for g in GATES if pattern.match(f"[{g}] x"))


def _lead_tags(pattern: re.Pattern[str]) -> frozenset[str]:
    """Every gate name the ops stub's leading-tag pattern takes into its lead."""
    out = set()
    for g in GATES:
        m = pattern.match(f"1. [{g}] x")
        if m is not None and f"[{g}]" in m.group("lead"):
            out.add(g)
    return frozenset(out)


def test_tag_patterns_match_exactly_the_post_merge_gates() -> None:
    from fr.gates import POST_MERGE_GATES

    assert _step_tags(_TAG_RE) == POST_MERGE_GATES
    assert _lead_tags(_LEAD_RE) == POST_MERGE_GATES


def test_a_one_sided_tag_pattern_is_reported() -> None:
    """The planted case: a pattern hand-written without one post-merge gate, the
    state a value added to `PostMergeGate` alone would leave behind."""
    from fr.gates import POST_MERGE_GATES

    assert _step_tags(re.compile(r"^\[(devops)\]\s+")) != POST_MERGE_GATES
    assert _lead_tags(re.compile(r"^(?P<lead>\d+\.\s+(?:\[(?:devops)\]\s+)?)")) != POST_MERGE_GATES


def test_post_merge_gate_type_is_the_set() -> None:
    from fr.gates import POST_MERGE_GATES, PostMergeGate

    assert POST_MERGE_GATES == frozenset(get_args(PostMergeGate))


def mismatch(annotation: Any, vocabulary: frozenset[str]) -> frozenset[str]:
    """The names an annotation and a vocabulary do not share (empty when equal)."""
    return accepted(annotation) ^ vocabulary


def test_annotations_derive_from_the_vocabulary() -> None:
    from fr.gates import POST_MERGE_GATES
    from fr.spec import StepGate

    exit_value = ExitBlock.model_fields["gates"].annotation
    assert mismatch(exit_value, GATES | {"none"}) == frozenset()
    strategy_gate = StrategyManifest.model_fields["gate"].annotation
    assert mismatch(strategy_gate, POST_MERGE_GATES | {"none"}) == frozenset()
    assert mismatch(StepGate, POST_MERGE_GATES) == frozenset()


def test_a_divergent_literal_is_reported() -> None:
    """The planted case: the comparison the real assertions use names the extra value
    of a hand-written literal, and the missing one of a short literal."""
    from fr.gates import POST_MERGE_GATES

    planted = Literal["none", "tester", "devops", "extra"]
    assert mismatch(planted, POST_MERGE_GATES | {"none"}) == {"extra"}
    assert mismatch(Literal["none", "tester"], POST_MERGE_GATES | {"none"}) == {"devops"}


def test_the_step_gate_is_the_post_merge_gate() -> None:
    from fr.gates import PostMergeGate
    from fr.spec import StepGate

    assert StepGate is PostMergeGate
