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


# --- R18 from plan 3: logical refs resolve through R1's resolver ------------------------


def test_candidates_follow_the_resolver_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import MappingProxyType

    from fr.acceptance.logical import candidates
    from fr.artifacts import paths

    moved = dict(paths.KIND_DIRS, spec="elsewhere/specs", plan="elsewhere/plans")
    monkeypatch.setattr(paths, "KIND_DIRS", MappingProxyType(moved))
    assert candidates(parse_logical(f"spec:{SLUG}"))[0] == f"elsewhere/specs/{SLUG}-design.md"
    assert candidates(parse_logical(f"plan:{SLUG}"))[0] == f"elsewhere/plans/{SLUG}"
    _touch(tmp_path, f"elsewhere/specs/{SLUG}-design.md")
    assert resolve_logical(f"spec:{SLUG}", tmp_path) == Path(f"elsewhere/specs/{SLUG}-design.md")
    _touch(tmp_path, "elsewhere/plans/2026-01-01-p/_meta.yaml")
    assert resolve_logical("plan:2026-01-01-p", tmp_path) == Path("elsewhere/plans/2026-01-01-p")


def test_a_spec_in_another_quiet_feature_root_resolves_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.artifacts import paths

    fr_root = tmp_path / "fr-worktree"
    other = fr_root / "features" / "feat__other"
    _touch(other, f"docs/superpowers/specs/{SLUG}-design.md")
    (fr_root / "features" / "feat__mine").mkdir(parents=True)
    space = paths.ArtifactSpace("quiet", fr_root, "feat__mine")
    monkeypatch.setattr(paths, "space_for", lambda _root: space)
    found = resolve_logical(f"spec:{SLUG}#R1", tmp_path / "product")
    assert found == other / f"docs/superpowers/specs/{SLUG}-design.md"
    assert resolution_problem(f"spec:{SLUG}#R1", tmp_path / "product") is None
    assert resolve_logical("spec:2026-01-01-nope", tmp_path / "product") is None


def test_path_shaped_outputs_stay_relative_for_an_out_of_repo_feature_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.acceptance.logical import as_path_ref, origin_spec_path, resolve_logical_at
    from fr.artifacts import paths

    outside = tmp_path / "elsewhere" / "features" / "feat__other"
    _touch(outside, f"docs/superpowers/specs/{SLUG}-design.md")
    _touch(outside, "docs/superpowers/plans/2026-01-01-p/_meta.yaml")
    monkeypatch.setattr(paths, "feature_roots", lambda _space: iter([outside]))
    product = tmp_path / "product"
    product.mkdir()

    spec_ref = as_path_ref(f"spec:{SLUG}#R1", product, "o/r")
    plan_ref = as_path_ref("plan:2026-01-01-p", product, "o/r")
    origin = origin_spec_path(f"spec:{SLUG}#R1", product)
    assert spec_ref == f"o/r:docs/superpowers/specs/{SLUG}-design.md#R1"
    assert plan_ref == "o/r:docs/superpowers/plans/2026-01-01-p"
    assert origin == f"docs/superpowers/specs/{SLUG}-design.md"
    for out in (spec_ref, plan_ref, origin):
        assert str(tmp_path) not in out and ":/" not in out

    found = resolve_logical_at(f"spec:{SLUG}", product)
    assert found is not None
    assert found.feature_root == outside
    assert found.rel.as_posix() == f"docs/superpowers/specs/{SLUG}-design.md"
    assert found.path == outside / found.rel


def test_path_shaped_outputs_are_unchanged_under_repo(tmp_path: Path) -> None:
    from fr.acceptance.logical import as_path_ref, origin_spec_path, resolve_logical_at

    _touch(tmp_path, f"docs/superpowers/specs/{SLUG}-design.md")
    assert as_path_ref(f"spec:{SLUG}#R1", tmp_path, "o/r") == (
        f"o/r:docs/superpowers/specs/{SLUG}-design.md#R1"
    )
    assert origin_spec_path(f"spec:{SLUG}", tmp_path) == f"docs/superpowers/specs/{SLUG}-design.md"
    found = resolve_logical_at(f"spec:{SLUG}", tmp_path)
    assert found is not None and found.feature_root == tmp_path
    assert resolve_logical(f"spec:{SLUG}", tmp_path) == found.rel
