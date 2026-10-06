"""Judgements schema 4's `exports:` and the `export:` config key
(spec 2026-10-05-triage-pages-goal, R13, §G, §I config).

`exports:` records the driver's per-wave state export; only a schema-4 file may carry
it, and the one writer replaces that section alone, refusing (byte-identical) anything
the loader would refuse.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from fr.triage.batch import save_exports
from fr.triage.errors import TriageError
from fr.triage.model import (
    JUDGEMENTS_READS,
    JUDGEMENTS_SCHEMA,
    Export,
    ExportConfig,
    Judgements,
    TriageConfig,
    load_judgements,
)
from pydantic import ValidationError

AT = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
EXPORT = {"wave": "3", "repo": "example-org/widgets", "at": "2026-10-05T12:00:00Z", "pr": 41}

HEAD = (
    "schema: 3\n"
    "# the agent's own comment survives\n"
    "tiers:\n  - {n: 1, title: Now}\n"
    "issues:\n  widgets#1: {tier: 1, note: 'keep: me'}\n"
)


def test_the_writer_writes_schema_5_and_the_reader_reads_1_to_5() -> None:
    assert JUDGEMENTS_SCHEMA == 6
    assert JUDGEMENTS_READS == (1, 2, 3, 4, 5, 6)
    assert Judgements.model_validate({"schema": 4}).schema_ == 4


def test_the_committed_judgements_load_under_the_current_fr() -> None:
    # The driver's wave export rewrites this file at whatever schema the exporting fr
    # writes (4 at #976, 5 since #995), so pin only that the current fr reads it, never
    # a version: a version pin turns every schema bump's first export PR red.
    path = Path(__file__).parents[2] / "docs/triage/derio-net--super-fr/judgements.yaml"
    got = load_judgements(path)
    assert got.schema_ in JUDGEMENTS_READS


def test_exports_load_on_schema_4() -> None:
    got = Judgements.model_validate({"schema": 4, "exports": [EXPORT]})
    assert got.exports == [Export(wave="3", repo="example-org/widgets", at=AT, pr=41, merged=False)]


@pytest.mark.parametrize("schema", [1, 2, 3])
def test_exports_need_schema_4(schema: int) -> None:
    with pytest.raises(ValidationError, match="`exports:` needs schema 4"):
        Judgements.model_validate({"schema": schema, "exports": [EXPORT]})


def test_an_export_wave_written_as_a_number_reads_as_its_key() -> None:
    assert Export.model_validate({**EXPORT, "wave": 3}).wave == "3"


def test_an_export_needs_an_aware_time() -> None:
    with pytest.raises(ValidationError):
        Export.model_validate({**EXPORT, "at": "2026-10-05T12:00:00"})


def test_save_exports_replaces_only_the_exports_section_and_stamps_5(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(HEAD, encoding="utf-8")
    one = Export(wave="3", repo="example-org/widgets", at=AT)

    got = save_exports(path, [one], read=[])

    text = path.read_text(encoding="utf-8")
    assert text.startswith("schema: 6\n" + HEAD.removeprefix("schema: 3\n"))
    assert yaml.safe_load(text[len("schema: 6\n" + HEAD.removeprefix("schema: 3\n")) :]).keys() == {
        "exports"
    }
    assert got.exports == [one]
    assert load_judgements(path).exports == [one]

    two = one.model_copy(update={"pr": 41, "merged": True})
    save_exports(path, [two], read=[one])
    text = path.read_text(encoding="utf-8")
    assert text.count("exports:") == 1
    assert load_judgements(path).exports == [two]
    assert "keep: me" in text


def test_save_exports_leaves_the_batches_section_alone(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    batches = "batches:\n- id: a\n  title: t\n  ids:\n  - widgets#1\n  wave: 2\n"
    path.write_text(HEAD + batches, encoding="utf-8")

    save_exports(path, [Export(wave="2", repo="example-org/widgets", at=AT)], read=[])

    text = path.read_text(encoding="utf-8")
    assert batches in text
    assert [b.id for b in load_judgements(path).batches] == ["a"]


def test_a_refused_export_write_leaves_the_file_byte_identical(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(HEAD, encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(TriageError, match="changed since it was read"):
        save_exports(path, [], read=[Export(wave="1", repo="example-org/widgets", at=AT)])
    assert path.read_bytes() == before

    path.write_text(HEAD + "issues_extra: 1\n", encoding="utf-8")  # a file the loader refuses
    before = path.read_bytes()
    with pytest.raises(TriageError):
        save_exports(path, [Export(wave="1", repo="example-org/widgets", at=AT)], read=[])
    assert path.read_bytes() == before


def test_the_export_config_key_loads() -> None:
    config = TriageConfig.model_validate({"export": {"path": "docs/triage"}})
    assert config.export == ExportConfig(path="docs/triage")
    assert TriageConfig().export is None


@pytest.mark.parametrize("bad", ["/abs/triage", "../triage", "docs/../../x", "", "docs\\..\\x"])
def test_an_export_path_outside_the_repo_is_refused(bad: str) -> None:
    with pytest.raises(ValidationError, match="export path"):
        TriageConfig.model_validate({"export": {"path": bad}})


@pytest.mark.parametrize(
    ("given", "normal"), [("docs/triage/", "docs/triage"), ("docs/triage", "docs/triage")]
)
def test_the_export_path_is_normalised_once_at_load(given: str, normal: str) -> None:
    """p4-r2: every reader uses the one normalised value."""
    assert TriageConfig.model_validate({"export": {"path": given}}).export == ExportConfig(
        path=normal
    )


@pytest.mark.parametrize("bad", ["./docs", "docs//t", "a/./b", "docs/.", "/", "docs/triage//"])
def test_an_export_path_contained_would_refuse_is_refused_at_load(bad: str) -> None:
    """p4-r2: refused at load, never by `contained()` on every pass."""
    with pytest.raises(ValidationError, match="export path"):
        TriageConfig.model_validate({"export": {"path": bad}})
