"""`fr_dispatch.work_item` — the unit-agnostic dispatch value and its identity.

`item_id` / `parent_id` replace `build_card_title`-based dedup (spec
2026-08-14-workflow-shapes-and-workitem-dispatch §4.D): identity must be pure
string composition from an item's position in the graph — no I/O, no tracker
calls — because some items have no tracker artifact at creation time.

Four-level grammar (corrected in Phase 2 review — a run item has neither a
spec nor a plan slug at creation, both are its *outputs* per §4.E):

    run    <repo>/run/<run-id>                        unit: run
    spec   <repo>/<spec-slug>                         unit: spec
    plan   <repo>/<spec-slug>/<plan-slug>              (parent level only)
    phase  <repo>/<spec-slug>/<plan-slug>/phase/<n>    unit: phase
"""

from __future__ import annotations

import pytest

# --- item_id / parent_id -----------------------------------------------------


def test_item_id_repo_and_spec_only() -> None:
    from fr_dispatch.work_item import item_id

    assert item_id("owner/repo", "my-spec") == "owner/repo/my-spec"


def test_item_id_with_plan() -> None:
    from fr_dispatch.work_item import item_id

    assert item_id("owner/repo", "my-spec", plan_slug="my-plan") == "owner/repo/my-spec/my-plan"


def test_item_id_with_phase() -> None:
    from fr_dispatch.work_item import item_id

    assert (
        item_id("owner/repo", "my-spec", plan_slug="my-plan", phase=3)
        == "owner/repo/my-spec/my-plan/phase/3"
    )


def test_item_id_is_deterministic() -> None:
    from fr_dispatch.work_item import item_id

    a = item_id("owner/repo", "my-spec", plan_slug="my-plan", phase=3)
    b = item_id("owner/repo", "my-spec", plan_slug="my-plan", phase=3)
    assert a == b


def test_item_id_phase_without_plan_raises() -> None:
    from fr_dispatch.work_item import item_id

    with pytest.raises(ValueError, match="phase"):
        item_id("owner/repo", "my-spec", phase=3)


def test_parent_id_of_phase_is_the_plan_level() -> None:
    from fr_dispatch.work_item import item_id, parent_id

    phase_id = item_id("owner/repo", "my-spec", plan_slug="my-plan", phase=3)
    assert parent_id(phase_id) == item_id("owner/repo", "my-spec", plan_slug="my-plan")


def test_parent_id_of_plan_is_the_spec_level() -> None:
    from fr_dispatch.work_item import item_id, parent_id

    plan_id = item_id("owner/repo", "my-spec", plan_slug="my-plan")
    assert parent_id(plan_id) == item_id("owner/repo", "my-spec")


def test_parent_id_of_spec_level_is_none() -> None:
    from fr_dispatch.work_item import item_id, parent_id

    spec_id = item_id("owner/repo", "my-spec")
    assert parent_id(spec_id) is None


# --- run-item identity (corrected in Phase 2 review) -------------------------


def test_run_item_id_format() -> None:
    from fr_dispatch.work_item import run_item_id

    assert run_item_id("owner/repo", "2026-08-14-ticket-polling") == (
        "owner/repo/run/2026-08-14-ticket-polling"
    )


def test_run_item_id_is_deterministic() -> None:
    from fr_dispatch.work_item import run_item_id

    a = run_item_id("owner/repo", "my-run")
    b = run_item_id("owner/repo", "my-run")
    assert a == b


def test_item_id_rejects_run_as_spec_slug() -> None:
    from fr_dispatch.work_item import item_id

    # "run" is reserved for run-item identity (run_item_id) — a spec slug of
    # "run" would collide with the run-item form, both being <owner>/<repo>
    # plus two segments.
    with pytest.raises(ValueError, match="run"):
        item_id("owner/repo", "run")


def test_parent_id_of_run_item_is_none() -> None:
    from fr_dispatch.work_item import parent_id, run_item_id

    run_id = run_item_id("owner/repo", "my-run")
    # A run item is a root: it has no spec yet (and may never gain one — a
    # shape that emits only a document has no spec/plan at all, §6/Phase 8).
    assert parent_id(run_id) is None


def test_parent_id_of_plan_is_still_the_spec_level_not_confused_with_run() -> None:
    from fr_dispatch.work_item import item_id, parent_id

    # Both the run form and the plan form are "<owner>/<repo>" plus two
    # segments; the literal "run/" marker is what must disambiguate them.
    plan_id = item_id("owner/repo", "my-spec", plan_slug="my-plan")
    assert parent_id(plan_id) == item_id("owner/repo", "my-spec")


# --- ArtifactRef --------------------------------------------------------------


def test_artifact_ref_carries_kind_repo_path() -> None:
    from fr_dispatch.work_item import ArtifactRef

    ref = ArtifactRef(kind="plan", repo="owner/repo", path="docs/plans/x")
    assert (ref.kind, ref.repo, ref.path) == ("plan", "owner/repo", "docs/plans/x")


def test_artifact_ref_normalizes_leading_dot_slash() -> None:
    from fr_dispatch.work_item import ArtifactRef

    ref = ArtifactRef(kind="plan", repo="owner/repo", path="./docs/plans/x")
    assert ref.path == "docs/plans/x"


def test_artifact_ref_is_frozen() -> None:
    import dataclasses

    from fr_dispatch.work_item import ArtifactRef

    ref = ArtifactRef(kind="plan", repo="owner/repo", path="docs/plans/x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ref.path = "other"  # type: ignore[misc]


# --- WorkItem -------------------------------------------------------------


def _phase_id() -> str:
    from fr_dispatch.work_item import item_id

    return item_id("owner/repo", "my-spec", plan_slug="my-plan", phase=3)


def _make_item(**overrides: object) -> object:
    from fr_dispatch.work_item import WorkItem

    kwargs: dict[str, object] = dict(
        id=_phase_id(),
        unit="phase",
        workflow="default",
        repo="owner/repo",
        parent=None,
        inputs=(),
        payload={},
        tracking=None,
    )
    kwargs.update(overrides)
    return WorkItem(**kwargs)  # type: ignore[arg-type]


def test_work_item_is_hashable() -> None:
    item = _make_item()
    hash(item)


def test_work_item_equal_fields_are_equal() -> None:
    a = _make_item()
    b = _make_item()
    assert a == b


def test_work_item_tracking_defaults_to_none() -> None:
    from fr_dispatch.work_item import WorkItem

    item = WorkItem(
        id=_phase_id(),
        unit="phase",
        workflow="default",
        repo="owner/repo",
        parent=None,
        inputs=(),
        payload={},
    )
    assert item.tracking is None


def test_work_item_unit_and_id_must_agree() -> None:
    from fr_dispatch.work_item import item_id

    # unit="phase" but id has no phase segment — must raise.
    plan_level_id = item_id("owner/repo", "my-spec", plan_slug="my-plan")
    with pytest.raises(ValueError, match="unit"):
        _make_item(id=plan_level_id, unit="phase")


def test_work_item_run_unit_matches_run_form_id() -> None:
    from fr_dispatch.work_item import run_item_id

    item = _make_item(id=run_item_id("owner/repo", "my-run"), unit="run")
    assert item.unit == "run"


def test_work_item_rejects_plan_form_id_for_any_unit() -> None:
    from fr_dispatch.work_item import item_id

    # The plan level is a parent, not a dispatchable unit — no `unit` value
    # may pair with it, including "run".
    plan_level_id = item_id("owner/repo", "my-spec", plan_slug="my-plan")
    with pytest.raises(ValueError, match="unit"):
        _make_item(id=plan_level_id, unit="run")


# --- F5: identity IS the id (hash and eq must agree) -------------------------


def test_two_items_with_the_same_id_are_the_same_item_whatever_the_payload() -> None:
    """`__hash__` was id-only while `__eq__` was field-wise — including
    `payload`, which carries a `Plan` and a `PhaseDoc`.

    Hash-equal + compare-unequal means a set holds BOTH copies (`len == 2`)
    and every lookup pays a deep `Plan.__eq__` before answering "no". The
    docstring's claim — hashing on `id` keeps WorkItem usable as a set/dict
    key — was therefore false in exactly the case it was written for.
    Identity is the id; that is the whole premise of §4.D.
    """
    a = _make_item(payload={"plan": object(), "issue_number": 1})
    b = _make_item(payload={})

    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
    assert {a: "value"}[b] == "value"


def test_items_with_different_ids_are_not_equal() -> None:
    from fr_dispatch.work_item import item_id

    other = item_id("owner/repo", "my-spec", plan_slug="my-plan", phase=4)
    assert _make_item() != _make_item(id=other, parent=None)


def test_a_work_item_is_not_equal_to_a_non_work_item() -> None:
    """Comparing against a foreign type must be False, not an id match on a
    lookalike object with an `id` attribute."""

    class Lookalike:
        id = _phase_id()

    assert _make_item() != Lookalike()
    assert _make_item() != _phase_id()


# --- F6: id grammar is classified by shape, not by a bare marker test --------


def test_a_repo_literally_named_phase_is_not_a_phase_level_id() -> None:
    """`segments[-2] == "phase"` was tested before any length check.

    `owner/phase/my-spec` is a SPEC-level id in a repo called `phase`; it was
    classified `phase`, so `parent_id` walked two segments up to `"owner"`
    and a `unit="spec"` item with that id was rejected outright.
    """
    from fr_dispatch.work_item import _id_level, item_id, parent_id

    spec_id = item_id("owner/phase", "my-spec")
    assert spec_id == "owner/phase/my-spec"
    assert _id_level(spec_id) == "spec"
    assert parent_id(spec_id) is None
    assert _make_item(id=spec_id, unit="spec")  # constructible, was not


def test_the_phase_marker_still_classifies_a_real_phase_id_in_such_a_repo() -> None:
    from fr_dispatch.work_item import _id_level, item_id, parent_id

    phase_id = item_id("owner/phase", "my-spec", plan_slug="my-plan", phase=2)
    assert _id_level(phase_id) == "phase"
    assert parent_id(phase_id) == "owner/phase/my-spec/my-plan"


def test_id_level_rejects_ids_that_are_too_long_to_be_any_level() -> None:
    from fr_dispatch.work_item import _id_level

    with pytest.raises(ValueError, match="well-formed"):
        _id_level("owner/repo/spec/plan/phase/3/extra")
    with pytest.raises(ValueError, match="well-formed"):
        _id_level("owner/repo/spec/plan/extra")


def test_run_item_id_rejects_a_run_id_containing_a_slash() -> None:
    """Phase 7's `fr run start` assigns the run id; nothing constrained it.

    A `/` in it silently changes the id's segment count, so `_id_level`
    would reject (or worse, misclassify) an id the caller believed was a
    run item. Fail at construction, where the caller is.
    """
    from fr_dispatch.work_item import run_item_id

    with pytest.raises(ValueError, match="run_id"):
        run_item_id("owner/repo", "2026-08-14/ticket-polling")


def test_run_item_id_rejects_an_empty_run_id() -> None:
    from fr_dispatch.work_item import run_item_id

    with pytest.raises(ValueError, match="run_id"):
        run_item_id("owner/repo", "")


def test_item_id_rejects_slugs_that_would_forge_extra_segments() -> None:
    """Same hazard as `run_id`, same fail-closed answer."""
    from fr_dispatch.work_item import item_id

    with pytest.raises(ValueError, match="spec_slug"):
        item_id("owner/repo", "my/spec")
    with pytest.raises(ValueError, match="plan_slug"):
        item_id("owner/repo", "my-spec", plan_slug="my/plan")


def test_identity_functions_reject_a_repo_that_is_not_owner_slash_name() -> None:
    """The segment counts `_id_level` classifies by all assume a 2-segment
    repo. A repo that isn't one produces an id of the wrong level."""
    from fr_dispatch.work_item import item_id, run_item_id

    for bad in ("just-a-name", "a/b/c", ""):
        with pytest.raises(ValueError, match="repo"):
            item_id(bad, "my-spec")
        with pytest.raises(ValueError, match="repo"):
            run_item_id(bad, "my-run")
