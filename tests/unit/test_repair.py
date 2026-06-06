"""vk.repair — idempotent stale-ref normalization (2026-06-06 design).

The repair walk rewrites spec-table File cells and plan `_meta.yaml`
refs (`parent_plan`, `prior_rework`, `spec`) to the canonical
lifecycle-independent form, preserving everything else byte-for-byte,
and warns loudly — never silently — about refs it cannot resolve.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.repair import repair_repo

SLUG = "2026-05-10-x"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    for d in ("plans", "implemented/plans", "specs", "implemented/specs"):
        (tmp_path / "docs/superpowers" / d).mkdir(parents=True)
    return tmp_path


def _spec_with_cell(repo: Path, cell: str, name: str = "2026-05-10-fixture.md") -> Path:
    spec = repo / "docs/superpowers/specs" / name
    spec.write_text(
        "# Fixture\n\nProse stays untouched.\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|---|---|---|---|\n"
        f"| Plan X | `derio-net/test` | {cell} | — |\n"
    )
    return spec


def test_repair_rewrites_legacy_cell_preserving_annotation(repo: Path) -> None:
    (repo / "docs/superpowers/implemented/plans" / SLUG).mkdir()
    spec = _spec_with_cell(
        repo,
        f"`docs/superpowers/archived-plans/{SLUG}/` (shipped via PR #146, archived 2026-05-17)",
    )
    result = repair_repo(repo, write=True)
    text = spec.read_text()
    assert f"| `{SLUG}` (shipped via PR #146, archived 2026-05-17) |" in text
    assert "archived-plans" not in text
    # other columns + prose untouched
    assert "| Plan X | `derio-net/test` |" in text
    assert "Prose stays untouched." in text
    assert len(result.rewrites) == 1
    assert not result.warnings


def test_repair_rewrites_meta_refs(repo: Path) -> None:
    plan = repo / "docs/superpowers/plans/2026-05-10-x-rework-1"
    plan.mkdir()
    (repo / "docs/superpowers/implemented/plans" / SLUG).mkdir()
    spec = _spec_with_cell(repo, f"`{SLUG}`")
    meta = plan / "_meta.yaml"
    meta.write_text(
        "schema_version: 2\n"
        "plan: 2026-05-10-x-rework-1\n"
        f"spec: docs/superpowers/specs/{spec.name}\n"
        "target_repo: derio-net/test\n"
        f"parent_plan: docs/superpowers/archived-plans/{SLUG}/\n"
        "origin_items: []\n"
    )
    result = repair_repo(repo, write=True)
    text = meta.read_text()
    assert f"parent_plan: {SLUG}\n" in text
    assert f"spec: {spec.name}\n" in text
    # untouched fields stay byte-identical
    assert "schema_version: 2\n" in text
    assert "origin_items: []\n" in text
    assert {(r.file.name, r.field) for r in result.rewrites} >= {
        ("_meta.yaml", "parent_plan"),
        ("_meta.yaml", "spec"),
    }


def test_repair_unresolvable_ref_warns_loudly_and_leaves_ref(repo: Path) -> None:
    spec = _spec_with_cell(repo, "`docs/superpowers/archived-plans/2026-05-10-gone/`")
    before = spec.read_text()
    result = repair_repo(repo, write=True)
    assert spec.read_text() == before  # untouched
    assert len(result.warnings) == 1
    w = result.warnings[0]
    assert spec.name in w
    assert "2026-05-10-gone" in w
    assert "docs/superpowers/plans/2026-05-10-gone" in w  # every tried path named
    assert "docs/superpowers/implemented/plans/2026-05-10-gone" in w
    assert "docs/superpowers/archived-plans/2026-05-10-gone" in w


def test_repair_idempotent(repo: Path) -> None:
    (repo / "docs/superpowers/implemented/plans" / SLUG).mkdir()
    spec = _spec_with_cell(repo, f"docs/superpowers/archived-plans/{SLUG}/")
    repair_repo(repo, write=True)
    after_first = spec.read_text()
    second = repair_repo(repo, write=True)
    assert spec.read_text() == after_first
    assert not second.rewrites  # fixed point


def test_repair_dry_run_writes_nothing(repo: Path) -> None:
    (repo / "docs/superpowers/implemented/plans" / SLUG).mkdir()
    spec = _spec_with_cell(repo, f"docs/superpowers/archived-plans/{SLUG}/")
    before = spec.read_text()
    result = repair_repo(repo, write=False)
    assert spec.read_text() == before
    assert len(result.rewrites) == 1  # planned, not applied


def test_repair_cross_repo_unresolved_mentions_per_repo_scope(repo: Path) -> None:
    """An unresolvable row may be cross-repo — the warning says so
    instead of guessing."""
    _spec_with_cell(repo, "`docs/superpowers/plans/2026-05-10-remote/`")
    result = repair_repo(repo, write=True)
    assert result.warnings
    assert "own repo" in result.warnings[0] or "cross-repo" in result.warnings[0]


def test_repair_walks_implemented_specs_too(repo: Path) -> None:
    (repo / "docs/superpowers/implemented/plans" / SLUG).mkdir()
    spec = repo / "docs/superpowers/implemented/specs/2026-05-10-done.md"
    spec.write_text(
        "# Done\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|---|---|---|---|\n"
        f"| Plan X | `derio-net/test` | `docs/superpowers/archived-plans/{SLUG}/` | — |\n"
    )
    result = repair_repo(repo, write=True)
    assert f"`{SLUG}`" in spec.read_text()
    assert len(result.rewrites) == 1


def test_repair_meta_null_and_tilde_are_placeholders(repo: Path) -> None:
    """`spec: null` / `~` / `none` are sentinels, not refs — no warning, no
    rewrite ('none' parity with self_review's placeholder list; spuriously
    warned in the 2026-06-06 fleet sweep on frank + willikins)."""
    plan = repo / "docs/superpowers/plans/2026-05-10-nullspec"
    plan.mkdir()
    meta = plan / "_meta.yaml"
    meta.write_text(
        "schema_version: 2\nplan: 2026-05-10-nullspec\n"
        "spec: none\nparent_plan: ~\nprior_rework: null\n"
    )
    result = repair_repo(repo, write=True)
    assert not result.warnings
    assert not result.rewrites


def test_repair_warns_on_ambiguous_slug_across_roots(repo: Path) -> None:
    """Spec promise: same slug under two roots → active wins AND a
    warning names both (review finding 1, 2026-06-06)."""
    (repo / "docs/superpowers/plans" / SLUG).mkdir()
    (repo / "docs/superpowers/implemented/plans" / SLUG).mkdir()
    _spec_with_cell(repo, f"docs/superpowers/archived-plans/{SLUG}/")
    result = repair_repo(repo, write=True)
    assert len(result.rewrites) == 1  # still rewrites (active wins)
    assert any(
        "ambiguous" in w
        and f"docs/superpowers/plans/{SLUG}" in w
        and f"docs/superpowers/implemented/plans/{SLUG}" in w
        for w in result.warnings
    ), result.warnings


def test_repair_never_touches_fenced_blocks_after_table(repo: Path) -> None:
    """A code fence abutting the table (no blank line) must not be
    rewritten even if it contains 4-column pipe rows (review finding 2)."""
    (repo / "docs/superpowers/implemented/plans" / SLUG).mkdir()
    spec = repo / "docs/superpowers/specs/2026-05-10-fenced.md"
    spec.write_text(
        "# F\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n"
        "|---|---|---|---|\n"
        f"| Plan X | `derio-net/test` | `docs/superpowers/archived-plans/{SLUG}/` | — |\n"
        "```\n"
        f"| fake | row | `docs/superpowers/archived-plans/{SLUG}/` | — |\n"
        "```\n"
    )
    repair_repo(repo, write=True)
    text = spec.read_text()
    assert f"| Plan X | `derio-net/test` | `{SLUG}` | — |" in text  # real row fixed
    assert (
        f"| fake | row | `docs/superpowers/archived-plans/{SLUG}/` | — |" in text
    )  # fence untouched
