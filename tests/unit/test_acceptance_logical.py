"""Logical references (spec 2026-11-04-repo-feature-settings R18, interim repo-only resolution)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.acceptance.logical import (
    LOGICAL_KINDS,
    LogicalRef,
    is_logical,
    parse_logical,
    resolution_problem,
    resolve_logical,
    to_logical,
)
from fr.acceptance.model import AcceptanceError, Row

SLUG = "2026-07-04-acceptance-matrix"


def _touch(root: Path, rel: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x\n")


def test_the_logical_kinds_are_spec_and_plan_only() -> None:
    assert LOGICAL_KINDS == ("spec", "plan")


def test_spec_and_plan_refs_parse() -> None:
    assert parse_logical(f"spec:{SLUG}#R3") == LogicalRef("spec", SLUG, "R3")
    assert parse_logical(f"plan:{SLUG}") == LogicalRef("plan", SLUG, "")
    assert is_logical(f"spec:{SLUG}#R3") and is_logical(f"plan:{SLUG}")


@pytest.mark.parametrize("ref", ["spec:", "spec:a/b#R1", "plan:x#", "spec:#R1"])
def test_a_malformed_logical_ref_is_refused(ref: str) -> None:
    with pytest.raises(AcceptanceError):
        parse_logical(ref)


def test_code_refs_are_not_logical_and_pass_through() -> None:
    code = "super-fr:tests/unit/test_x.py#test_y"
    assert not is_logical(code)
    assert to_logical(code) == code


def test_a_live_spec_resolves(tmp_path: Path) -> None:
    _touch(tmp_path, f"docs/superpowers/specs/{SLUG}-design.md")
    assert resolve_logical(f"spec:{SLUG}#R3", tmp_path) == Path(
        f"docs/superpowers/specs/{SLUG}-design.md"
    )


def test_a_spec_without_the_design_suffix_resolves(tmp_path: Path) -> None:
    _touch(tmp_path, f"docs/superpowers/specs/{SLUG}.md")
    assert resolve_logical(f"spec:{SLUG}", tmp_path) == Path(f"docs/superpowers/specs/{SLUG}.md")


def test_an_archived_spec_resolves_to_its_twin(tmp_path: Path) -> None:
    _touch(tmp_path, f"docs/superpowers/implemented/specs/{SLUG}-design.md")
    assert resolve_logical(f"spec:{SLUG}#R3", tmp_path) == Path(
        f"docs/superpowers/implemented/specs/{SLUG}-design.md"
    )


def test_a_plan_folder_resolves_live_or_archived(tmp_path: Path) -> None:
    _touch(tmp_path, "docs/superpowers/plans/2026-01-01-live/_meta.yaml")
    _touch(tmp_path, "docs/superpowers/implemented/plans/2026-01-01-done/_meta.yaml")
    assert resolve_logical("plan:2026-01-01-live", tmp_path) == Path(
        "docs/superpowers/plans/2026-01-01-live"
    )
    assert resolve_logical("plan:2026-01-01-done", tmp_path) == Path(
        "docs/superpowers/implemented/plans/2026-01-01-done"
    )


def test_an_unknown_slug_resolves_to_none_with_a_reason(tmp_path: Path) -> None:
    assert resolve_logical("spec:2026-01-01-nope#R1", tmp_path) is None
    reason = resolution_problem("spec:2026-01-01-nope#R1", tmp_path)
    assert reason is not None and "2026-01-01-nope" in reason
    assert resolution_problem("plan:2026-01-01-nope", tmp_path) is not None


def test_a_resolvable_ref_has_no_problem(tmp_path: Path) -> None:
    _touch(tmp_path, f"docs/superpowers/specs/{SLUG}-design.md")
    assert resolution_problem(f"spec:{SLUG}#R3", tmp_path) is None


@pytest.mark.parametrize(
    "path",
    [
        f"docs/superpowers/implemented/specs/{SLUG}-design.md",
        f"docs/superpowers/specs/{SLUG}-design.md",
    ],
)
def test_a_spec_path_ref_converts_to_its_logical_form(path: str) -> None:
    assert to_logical(f"super-fr:{path}#R3") == f"spec:{SLUG}#R3"


def test_a_plan_folder_ref_converts_to_its_logical_form() -> None:
    assert to_logical("super-fr:docs/superpowers/plans/2026-01-01-live/") == "plan:2026-01-01-live"
    assert (
        to_logical("super-fr:docs/superpowers/implemented/plans/2026-01-01-done")
        == "plan:2026-01-01-done"
    )


def test_a_journal_path_has_no_logical_form() -> None:
    ref = "super-fr:docs/superpowers/implemented/journals/debug/2026-07-23-x.md"
    assert to_logical(ref) == ref


def test_another_repos_spec_keeps_its_path_when_the_own_repo_is_named() -> None:
    ref = f"other:docs/superpowers/specs/{SLUG}-design.md#R3"
    assert to_logical(ref, own_repo="super-fr") == ref
    assert to_logical(ref.replace("other:", "Super-FR:"), own_repo="super-fr") == f"spec:{SLUG}#R3"


def _row(origin: str) -> Row:
    return Row.model_validate(
        {"id": "r", "capability": "c", "acceptance": "a", "origin": [origin], "status": "ci"}
    )


def test_a_row_origin_may_be_logical() -> None:
    assert _row(f"spec:{SLUG}#R3").origin == (f"spec:{SLUG}#R3",)
    assert _row(f"plan:{SLUG}").origin == (f"plan:{SLUG}",)


def test_a_row_origin_that_looks_logical_but_is_malformed_is_refused() -> None:
    with pytest.raises(ValueError, match="spec:"):
        _row("spec:a/b#R1")
