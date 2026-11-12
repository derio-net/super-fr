"""The `drop-vk-version` plan repair (spec 2026-11-12-remove-vk-compat R9-R13).

`PlanMeta` no longer has a `vk_version` field and is `extra="forbid"`, so a plan
still carrying the key stops parsing. This repair removes the one top-level line
and no other byte. It is the one migration that reaches the archive
(`Repair.extra_locators`), by the operator's decision.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from fr.artifacts import trigger
from fr.artifacts.fr_version import CEILING_REPAIR
from fr.artifacts.plan_vk_version import (
    ARCHIVE_LOCATOR,
    REPAIR_NAME,
    PlanVkVersionError,
    drop_vk_version,
    has_vk_version,
    rewritten_text,
)
from fr.artifacts.registry import artifact_kind, iter_paths_of
from fr.artifacts.runner import (
    MIGRATIONS,
    ArtifactMigrationError,
    Repair,
    inspection_failures,
    is_stale,
    plan_migrations,
    run_migrations,
)
from fr.artifacts.validate import validate_repo

BASE = "schema_version: 2\nplan: demo\nspec: demo-design.md\n"


def _write(tmp_path: Path, data: bytes, name: str = "_meta.yaml") -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


# --- the predicate ---------------------------------------------------------


def test_predicate_is_false_without_parsing_when_the_bytes_lack_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = _write(tmp_path, BASE.encode())

    def boom(*_a: object, **_k: object) -> object:
        raise AssertionError("parsed a file whose bytes cannot hold the key")

    monkeypatch.setattr(yaml, "safe_load", boom)
    assert has_vk_version(p) is False


@pytest.mark.parametrize(
    "text",
    [
        BASE + "notes: 'the old vk_version: 1 key'\n",
        BASE + "# vk_version: 1.0\n",
        BASE + "phases:\n  vk_version: nested\n",
    ],
)
def test_predicate_is_false_when_the_string_is_not_a_top_level_key(
    tmp_path: Path, text: str
) -> None:
    assert has_vk_version(_write(tmp_path, text.encode())) is False


def test_predicate_is_true_for_a_mapping_with_the_key(tmp_path: Path) -> None:
    assert has_vk_version(_write(tmp_path, (BASE + "vk_version: '1.2'\n").encode())) is True


# --- the rewrite -----------------------------------------------------------


@pytest.mark.parametrize(
    ("before", "after"),
    [
        # LF
        (
            b"schema_version: 2\nplan: demo\nvk_version: '1.2'\ncreated: x\n",
            b"schema_version: 2\nplan: demo\ncreated: x\n",
        ),
        # CRLF
        (
            b"schema_version: 2\r\nplan: demo\r\nvk_version: '1.2'\r\ncreated: x\r\n",
            b"schema_version: 2\r\nplan: demo\r\ncreated: x\r\n",
        ),
        # UTF-8 BOM
        (
            b"\xef\xbb\xbfschema_version: 2\nvk_version: 1.2\nplan: demo\n",
            b"\xef\xbb\xbfschema_version: 2\nplan: demo\n",
        ),
        # key on the last line, no final newline
        (
            b"schema_version: 2\nplan: demo\nvk_version: 1.2",
            b"schema_version: 2\nplan: demo\n",
        ),
        # double-quoted
        (
            b'schema_version: 2\nvk_version: "1.2"\nplan: demo\n',
            b"schema_version: 2\nplan: demo\n",
        ),
        # bare
        (
            b"schema_version: 2\nvk_version: 1.2.0\nplan: demo\n",
            b"schema_version: 2\nplan: demo\n",
        ),
        # trailing comment, comments and blank lines elsewhere kept
        (
            b"# head\nschema_version: 2\n\nvk_version: 1.2  # retired\nplan: demo # p\n",
            b"# head\nschema_version: 2\n\nplan: demo # p\n",
        ),
    ],
    ids=["lf", "crlf", "bom", "last-line", "double-quoted", "bare", "comment"],
)
def test_the_rewrite_removes_exactly_the_one_line(
    tmp_path: Path, before: bytes, after: bytes
) -> None:
    p = _write(tmp_path, before)
    drop_vk_version(p)
    assert p.read_bytes() == after
    assert has_vk_version(p) is False


@pytest.mark.parametrize(
    "text",
    [
        BASE + "vk_version: >-\n  1.2\n  and more\n",
        BASE + 'vk_version: "1.2\n  continued"\n',
        BASE + "vk_version: 1\nvk_version: 2\n",
        "{plan: x, vk_version: y}\n",
        BASE + "phases:\n  vk_version: nested\n",
    ],
    ids=["block-scalar", "multi-line-quoted", "duplicate", "flow-mapping", "nested-only"],
)
def test_a_file_it_cannot_rewrite_raises_and_is_left_byte_identical(
    tmp_path: Path, text: str
) -> None:
    p = _write(tmp_path, text.encode())
    before = p.read_bytes()
    with pytest.raises(PlanVkVersionError) as info:
        drop_vk_version(p)
    assert str(p) in str(info.value)
    assert p.read_bytes() == before
    with pytest.raises(PlanVkVersionError):
        rewritten_text(p)


def test_the_error_is_a_migration_error() -> None:
    assert issubclass(PlanVkVersionError, ArtifactMigrationError)


def test_a_second_run_is_a_no_op(tmp_path: Path) -> None:
    p = _write(tmp_path, (BASE + "vk_version: 1.2\n").encode())
    drop_vk_version(p)
    settled = p.read_bytes()
    assert has_vk_version(p) is False
    drop_vk_version(p)
    assert p.read_bytes() == settled


# --- registered, and reaching the archive through all four walks (R11, R12) ----

LIVE = "docs/superpowers/plans/{}/_meta.yaml"
ARCHIVED = "docs/superpowers/implemented/plans/{}/_meta.yaml"
CARRIER = "schema_version: 2\nplan: {slug}\nspec: {slug}-design.md\nvk_version: '1.0'\ncreated: x\n"
BLOCK = "schema_version: 2\nplan: bad\nspec: bad-design.md\nvk_version: >-\n  1.0\n  more\n"


def _put(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def _layout(tmp_path: Path) -> dict[str, Path]:
    """One live and two archived carriers, plus one archived block scalar."""
    paths = {
        "live": _put(tmp_path, LIVE.format("live"), CARRIER.format(slug="live")),
        "a1": _put(tmp_path, ARCHIVED.format("a1"), CARRIER.format(slug="a1")),
        "a2": _put(tmp_path, ARCHIVED.format("a2"), CARRIER.format(slug="a2")),
        "bad": _put(tmp_path, ARCHIVED.format("bad"), BLOCK),
    }
    paths["root"] = tmp_path
    return paths


@pytest.fixture
def repo(tmp_path: Path) -> dict[str, Path]:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return _layout(tmp_path)


def _repairs(actions: object) -> set[Path]:
    return {a.path for a in actions if a.repair == REPAIR_NAME}  # type: ignore[attr-defined]


def test_a_repair_accepts_extra_locators() -> None:
    r = Repair(
        kind="plan",
        name="x",
        applies=lambda p: False,
        fn=lambda p: None,
        extra_locators=("a/*.yaml",),
    )
    assert r.extra_locators == ("a/*.yaml",)


def test_the_shipped_registry_holds_the_repair_and_only_it_reaches_the_archive() -> None:
    named = {r.name: r for r in MIGRATIONS.repairs("plan")}
    assert named[REPAIR_NAME].extra_locators == (ARCHIVE_LOCATOR,)
    assert ARCHIVE_LOCATOR == "docs/superpowers/implemented/plans/*/_meta.yaml"
    assert CEILING_REPAIR.extra_locators == ()
    assert [r.name for r in MIGRATIONS.repairs("plan") if r.extra_locators] == [REPAIR_NAME]


def test_plan_migrations_lists_live_and_rewritable_archived_carriers(repo) -> None:
    assert _repairs(plan_migrations(repo["root"])) == {repo["live"], repo["a1"], repo["a2"]}


def test_the_preview_reports_the_unrewritable_archived_file(repo) -> None:
    before = repo["bad"].read_bytes()
    report = run_migrations(repo["root"], dry_run=True)
    assert _repairs(report.applied) == {repo["live"], repo["a1"], repo["a2"]}
    assert [f.path for f in report.unrepairable] == [repo["bad"]]
    assert report.failed == ()
    assert repo["bad"].read_bytes() == before


def test_apply_repairs_live_and_archived_and_leaves_the_unrewritable_one(repo) -> None:
    before = repo["bad"].read_bytes()
    report = run_migrations(repo["root"], dry_run=False)

    for slug in ("live", "a1", "a2"):
        assert repo[slug].read_bytes() == (
            f"schema_version: 2\nplan: {slug}\nspec: {slug}-design.md\ncreated: x\n".encode()
        )
    assert repo["bad"].read_bytes() == before
    assert set(report.changed_paths) == {repo["live"], repo["a1"], repo["a2"]}
    assert len(report.changed_paths) == 3
    assert [f.path for f in report.unrepairable] == [repo["bad"]]
    assert "PlanVkVersionError" in report.unrepairable[0].error
    assert report.failed == () and report.ok


def test_is_stale_with_only_an_archived_carrier(tmp_path: Path) -> None:
    _put(tmp_path, ARCHIVED.format("a1"), CARRIER.format(slug="a1"))
    assert is_stale(tmp_path) is True


def test_an_unrewritable_archived_file_never_makes_the_repo_stale(repo) -> None:
    run_migrations(repo["root"], dry_run=False)
    assert repo["bad"].exists()
    assert is_stale(repo["root"]) is False


def test_an_unreadable_archived_file_never_makes_the_repo_stale(tmp_path: Path) -> None:
    _put(tmp_path, ARCHIVED.format("broken"), "vk_version: [unclosed\n")
    assert is_stale(tmp_path) is False
    report = run_migrations(tmp_path, dry_run=True)
    assert [f.path for f in report.unrepairable] == [tmp_path / ARCHIVED.format("broken")]


def test_inspection_failures_never_names_an_archive_path(repo) -> None:
    _put(repo["root"], ARCHIVED.format("broken"), "vk_version: [unclosed\n")
    assert all("implemented" not in f.path.parts for f in inspection_failures(repo["root"]))


def test_iter_paths_of_still_skips_the_archive(repo) -> None:
    assert list(iter_paths_of(repo["root"], artifact_kind("plan"))) == [repo["live"]]


def test_the_ceiling_repair_still_skips_the_archive(tmp_path: Path) -> None:
    p = _put(
        tmp_path,
        ARCHIVED.format("old"),
        "schema_version: 2\nplan: old\nfr_version: '>=3.0.0,<4.0.0'\nvk_version: '1.0'\n",
    )
    run_migrations(tmp_path, dry_run=False)
    assert p.read_text() == "schema_version: 2\nplan: old\nfr_version: '>=3.0.0,<4.0.0'\n"


def test_validate_artifacts_neither_counts_nor_fails_the_archive(repo) -> None:
    report = validate_repo(repo["root"], kind_name="plan")
    assert report.checked == 1
    assert all("implemented" not in i.path.parts for i in report.issues)


def test_the_gate_migrates_past_an_unrewritable_archived_file(tmp_path: Path) -> None:
    # No git here: the gate's default-branch refusal is not the subject.
    repo = _layout(tmp_path)
    committed: list[object] = []
    lines: list[str] = []
    trigger.ensure_artifacts_current(
        argv=["apply"],
        invoked_subcommand="apply",
        env={},
        repo_root=repo["root"],
        context="interactive",
        commit=lambda root, report: committed.append(report),
        err=lines.append,
    )
    assert len(committed) == 1
    assert b"vk_version" not in repo["a1"].read_bytes()
    assert any("bad" in line for line in lines), lines


def test_a_held_archived_file_is_held_like_any_other(repo) -> None:
    report = run_migrations(
        repo["root"],
        dry_run=False,
        veto=lambda p: "editing" if p == repo["a1"] else None,
    )
    assert [f.path for f in report.failed] == [repo["a1"]]
    assert b"vk_version" in repo["a1"].read_bytes()
    assert repo["a2"] in report.changed_paths
