"""The `drop-vk-version` plan repair (spec 2026-11-12-remove-vk-compat R9-R13).

`PlanMeta` no longer has a `vk_version` field and is `extra="forbid"`, so a plan
still carrying the key stops parsing. This repair removes the one top-level line
and no other byte. It is the one migration that reaches the archive
(`Repair.extra_locators`), by the operator's decision.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.artifacts.plan_vk_version import (
    PlanVkVersionError,
    drop_vk_version,
    has_vk_version,
    rewritten_text,
)
from fr.artifacts.runner import ArtifactMigrationError

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
