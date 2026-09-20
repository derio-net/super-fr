"""`fr.types.PHASE_TIERS` — the tier vocabulary, derived not re-listed.

Review r-p2-f1: `_phase_tiers()` walked `get_args(annotation)` looking for a
member that was itself a `Literal`, which only holds while the annotation is a
UNION (`Literal[...] | None`). Drop the `| None` — a perfectly reasonable schema
change, making `tier` required — and `get_args` yields the tier STRINGS instead
of a Literal member, the loop finds nothing, and the module raises at IMPORT
time. `scripts/sync-opencode.py` imports this, so the whole sync script would
die with a message about a "Literal member" that says nothing about what to do.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

import pytest
from fr.types import PHASE_TIERS, PhaseHeader, phase_tiers


def test_the_shipped_vocabulary_matches_the_model() -> None:
    assert PHASE_TIERS == ("mechanical", "standard", "hard")
    for tier in PHASE_TIERS:
        assert PhaseHeader(number=1, title="t", tag="agentic", tier=tier).tier == tier


@pytest.mark.parametrize(
    "annotation",
    [
        # UP045/UP007 would rewrite these two to `X | None`, collapsing the
        # coverage: `typing.Optional[X]` / `typing.Union[X, None]` build a
        # `typing.Union` at runtime, while `X | None` builds a
        # `types.UnionType`. `get_args` reads both, but they are different
        # objects and pydantic may hand back either — which is precisely what
        # `phase_tiers` has to survive. Keep all three spellings.
        Optional[Literal["mechanical", "standard", "hard"]],  # noqa: UP045
        Union[Literal["mechanical", "standard", "hard"], None],  # noqa: UP007
        Literal["mechanical", "standard", "hard"],  # r-p2-f1: the bare form
        Literal["mechanical", "standard", "hard"] | None,
    ],
)
def test_the_tier_set_is_derived_from_optional_and_bare_literals_alike(annotation: object) -> None:
    assert phase_tiers(annotation) == ("mechanical", "standard", "hard")


def test_an_annotation_with_no_literal_is_refused_legibly() -> None:
    with pytest.raises(TypeError) as exc:
        phase_tiers(int)
    assert "tier" in str(exc.value).lower()
