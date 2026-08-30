"""The artifact registry: the ONE place that enumerates artifact kinds.

Spec: docs/superpowers/specs/2026-08-30-artifact-migration-framework-design.md
§3.A — every generated artifact declares the version it was written for, a
missing stamp means version 1 (the pre-framework era), and archived artifacts
under `implemented/` are frozen and never matched.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest
from fr.artifacts.registry import (
    ARTIFACT_KINDS,
    PRE_FRAMEWORK_VERSION,
    UnknownArtifactKindError,
    artifact_kind,
    iter_all_artifacts,
    iter_artifact_paths,
    read_version,
    write_version,
)

EXPECTED_KINDS = {"plan", "journal", "run", "matrix", "spec"}


# --- Task 1: the registry ------------------------------------------------


def test_registry_covers_every_stamped_kind() -> None:
    assert set(ARTIFACT_KINDS) == EXPECTED_KINDS


def test_each_entry_carries_version_locator_and_callables() -> None:
    for name, kind in ARTIFACT_KINDS.items():
        assert kind.name == name, "the mapping key must be the kind's own name"
        assert isinstance(kind.current_version, int) and kind.current_version >= 1
        assert isinstance(kind.locator, str) and kind.locator
        assert not Path(kind.locator).is_absolute(), "locator is relative to repo root"
        assert callable(kind.read_version)
        assert callable(kind.write_version)


def test_locators_never_reach_archived_artifacts() -> None:
    """`implemented/` records what shipped; rewriting it would falsify history."""
    for kind in ARTIFACT_KINDS.values():
        assert "implemented" not in kind.locator


def test_unknown_kind_raises() -> None:
    with pytest.raises(UnknownArtifactKindError):
        artifact_kind("brainstorm")


def test_pre_framework_version_is_one() -> None:
    assert PRE_FRAMEWORK_VERSION == 1


# --- Task 1: iteration skips the archive ---------------------------------


def _seed_repo(root: Path) -> dict[str, Path]:
    """A repo with one live artifact per kind and an archived twin of each."""
    live: dict[str, Path] = {}

    def w(rel: str, text: str) -> Path:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    live["plan"] = w("docs/superpowers/plans/2026-01-01-live/_meta.yaml", "schema_version: 2\n")
    w("docs/superpowers/implemented/plans/2026-01-01-done/_meta.yaml", "schema_version: 2\n")

    live["journal"] = w("docs/superpowers/journals/plans/2026-01-01-live.md", "# live\n")
    w("docs/superpowers/implemented/journals/plans/2026-01-01-done.md", "# done\n")

    live["run"] = w("docs/superpowers/runs/2026-01-01-live.yaml", "run: live\n")
    w("docs/superpowers/implemented/runs/2026-01-01-done.yaml", "run: done\n")

    live["matrix"] = w("docs/acceptance/matrix.yaml", "rows: []\n")

    live["spec"] = w("docs/superpowers/specs/2026-01-01-live-design.md", "# live\n")
    w("docs/superpowers/implemented/specs/2026-01-01-done-design.md", "# done\n")

    return live


def test_iter_artifact_paths_finds_live_and_skips_archived(tmp_path: Path) -> None:
    live = _seed_repo(tmp_path)
    for name in EXPECTED_KINDS:
        found = list(iter_artifact_paths(tmp_path, name))
        assert found == [live[name]], f"{name}: expected only the live artifact"


def test_iter_all_artifacts_covers_every_kind_once(tmp_path: Path) -> None:
    live = _seed_repo(tmp_path)
    found = {(kind.name, path) for kind, path in iter_all_artifacts(tmp_path)}
    assert found == {(name, path) for name, path in live.items()}


def test_iter_artifact_paths_rejects_unknown_kind(tmp_path: Path) -> None:
    with pytest.raises(UnknownArtifactKindError):
        list(iter_artifact_paths(tmp_path, "brainstorm"))


def test_iter_artifact_paths_on_an_empty_repo_is_empty(tmp_path: Path) -> None:
    for name in EXPECTED_KINDS:
        assert list(iter_artifact_paths(tmp_path, name)) == []


# --- Task 2: stamps, with ABSENT meaning version 1 -----------------------


def _diff(before: str, after: str) -> tuple[list[str], list[str]]:
    """`(removed, added)` lines between two texts, headers stripped."""
    body = list(
        difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True), n=0)
    )[2:]
    removed = [ln[1:] for ln in body if ln.startswith("-")]
    added = [ln[1:] for ln in body if ln.startswith("+")]
    return removed, added


# Deliberately messy carriers: comments, unusual key order, blank lines, and a
# trailing comment. A fixture emitted by the writer itself would pass against a
# reformatting implementation and prove nothing.
UNSTAMPED: dict[str, str] = {
    "plan": (
        "# hand-edited plan meta — key order is NOT the canonical one\n"
        "\n"
        "plan: 2026-01-01-live\n"
        "target_repo: derio-net/super-fr\n"
        "fr_version: '>=3.0.0,<4.0.0'   # the ceiling 4.0.0 must widen\n"
        "\n"
        "spec: docs/superpowers/specs/2026-01-01-live-design.md\n"
        "created: '2026-01-01'\n"
        "# trailing comment\n"
    ),
    "journal": (
        "# 2026-01-01-live\n"
        "\n"
        "<!-- fr:journal kind=discovery scope=plan id=d1 created=2026-01-01T00:00:00 -->\n"
        "### d1 · discovery · a thing\n"
        "\n"
        "body\n"
    ),
    "run": (
        "# a run an operator has open right now\n"
        "cursor: implement\n"
        "\n"
        "run: 2026-01-01-live\n"
        "workflow: fr-goal@1\n"
        "branch: feat/live\n"
        "started: '2026-01-01T00:00:00'\n"
        "steps:\n"
        "  implement:\n"
        "    state: running   # mid-flight\n"
        "\n"
        "# trailing comment\n"
    ),
    "matrix": (
        "# Acceptance matrix — the registry of business-level acceptance tests.\n"
        "\n"
        "repo: super-fr\n"
        "org: derio-net\n"
        "rows:\n"
        "- id: a-row\n"
        "  capability: Thing   # inline comment\n"
        "  acceptance: It works\n"
        "  status: ci\n"
        "\n"
        "# trailing comment\n"
    ),
    "spec": (
        "# A design spec\n"
        "\n"
        "Status: design\n"
        "\n"
        "---\n"
        "\n"
        "A horizontal rule above must NOT be mistaken for front matter.\n"
    ),
}

# The same carriers, already stamped at version 3 — the reader must return the
# declared stamp, and the writer must UPDATE it in place rather than adding a
# second one.
STAMPED_3: dict[str, str] = {
    "plan": "schema_version: 3\n" + UNSTAMPED["plan"],
    "journal": "<!-- fr:journal-schema=3 -->\n" + UNSTAMPED["journal"],
    "run": UNSTAMPED["run"].replace(
        "cursor: implement\n", "schema_version: 3\ncursor: implement\n"
    ),
    "matrix": UNSTAMPED["matrix"].replace(
        "repo: super-fr\n", "schema_version: 3\nrepo: super-fr\n"
    ),
    "spec": "---\nfr_schema: 3\n---\n" + UNSTAMPED["spec"],
}


def _artifact_path(root: Path, name: str) -> Path:
    return _seed_repo(root)[name]


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_absent_stamp_reads_as_version_one(tmp_path: Path, name: str) -> None:
    """No flag day: every artifact in the wild predates the framework."""
    path = _artifact_path(tmp_path, name)
    path.write_text(UNSTAMPED[name])
    assert read_version(name, path) == 1


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_declared_stamp_is_read_back(tmp_path: Path, name: str) -> None:
    path = _artifact_path(tmp_path, name)
    path.write_text(STAMPED_3[name])
    assert read_version(name, path) == 3


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_write_version_round_trips(tmp_path: Path, name: str) -> None:
    path = _artifact_path(tmp_path, name)
    path.write_text(UNSTAMPED[name])
    write_version(name, path, 7)
    assert read_version(name, path) == 7


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_stamping_an_unstamped_file_removes_nothing(tmp_path: Path, name: str) -> None:
    """Byte-stability: the only diff is the stamp being ADDED."""
    path = _artifact_path(tmp_path, name)
    before = UNSTAMPED[name]
    path.write_text(before)
    write_version(name, path, 7)
    removed, added = _diff(before, path.read_text())
    assert removed == [], f"{name}: writing a stamp must not remove or rewrite any line"
    # Exactly one added line carries the version. A carrier with no container
    # yet (an unstamped spec has no front matter) may also add its delimiters,
    # and nothing else.
    carriers = [i for i, ln in enumerate(added) if "7" in ln]
    assert len(carriers) == 1, f"{name}: expected one stamp line, got {added!r}"
    others = [ln for i, ln in enumerate(added) if i not in carriers]
    assert all(ln.strip() == "---" for ln in others), f"{name}: stray additions {others!r}"


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_restamping_replaces_the_stamp_in_place(tmp_path: Path, name: str) -> None:
    """Byte-stability again: exactly one line out, one line in — no duplicate stamp."""
    path = _artifact_path(tmp_path, name)
    before = STAMPED_3[name]
    path.write_text(before)
    write_version(name, path, 7)
    after = path.read_text()
    removed, added = _diff(before, after)
    assert len(removed) == 1 and "3" in removed[0], f"{name}: removed {removed!r}"
    assert len(added) == 1 and "7" in added[0], f"{name}: added {added!r}"
    assert read_version(name, path) == 7


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_writing_the_same_version_twice_is_byte_identical(tmp_path: Path, name: str) -> None:
    path = _artifact_path(tmp_path, name)
    path.write_text(UNSTAMPED[name])
    write_version(name, path, 7)
    once = path.read_text()
    write_version(name, path, 7)
    assert path.read_text() == once


def test_plan_stamp_is_the_existing_schema_version_field(tmp_path: Path) -> None:
    """Plans are already stamped — the framework reads that field, it does not
    add a second one (`PlanMeta` is `extra="forbid"`)."""
    path = _artifact_path(tmp_path, "plan")
    path.write_text("schema_version: 2\nplan: x\n")
    assert read_version("plan", path) == 2
    assert ARTIFACT_KINDS["plan"].current_version == 2


def test_journal_stamp_is_not_mistaken_for_an_entry_delimiter(tmp_path: Path) -> None:
    """`<!-- fr:journal ` is the ENTRY delimiter prefix; the stamp must not
    collide with it or every existing journal becomes unparseable."""
    from fr.journal.model import parse_journal

    path = _artifact_path(tmp_path, "journal")
    path.write_text(UNSTAMPED["journal"])
    before = parse_journal(path.read_text())
    write_version("journal", path, 7)
    after = parse_journal(path.read_text())
    assert [e.id for e in after] == [e.id for e in before] == ["d1"]


def test_spec_stamp_leaves_the_implementation_plans_table_parseable(tmp_path: Path) -> None:
    from fr.spec import parse_spec

    path = _artifact_path(tmp_path, "spec")
    path.write_text(
        "# A design spec\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n|---|---|---|---|\n"
        "| p | `derio-net/super-fr` | `p` | — |\n"
    )
    write_version("spec", path, 7)
    meta = parse_spec(path)
    assert meta.title == "A design spec"
    assert [p.name for p in meta.plans] == ["p"]


@pytest.mark.parametrize("name", sorted(EXPECTED_KINDS))
def test_stamp_helpers_reject_an_unknown_kind(tmp_path: Path, name: str) -> None:
    path = _artifact_path(tmp_path, name)
    with pytest.raises(UnknownArtifactKindError):
        read_version("brainstorm", path)
    with pytest.raises(UnknownArtifactKindError):
        write_version("brainstorm", path, 2)
