"""The `record` kind's 6 -> 7 migration (spec
`2026-09-29-spec-is-the-contract-design.md` §C, R8).

`JournalItem.delegated` and the `unconfirmed` member of `ResolutionState` are
REMOVED from an `extra="forbid"` model, so per `.claude/rules/artifact-versioning.md`
the v6 shape is frozen as `fr.record.legacy.RecordV6`, every record hop reads
through it, and the rewrite is built in memory and written once. A v6 record
carrying `delegated` loses the key; one whose resolution is `unconfirmed` has no
honest v7 equivalent, so it is left byte-identical and reported.
"""

from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

import pytest
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.record import legacy
from fr.record.model import RECORD_SCHEMA_VERSION, RecordError, load_record, parse_record

_V6_DELEGATED = """\
schema_version: 6
run: r1
step: brainstorm
outcome: done
journal:
  - kind: decision
    id: d1
    title: layout
    body: Your call.
    delegated: true
  - kind: discovery
    id: operator-input
    title: operator input
    body: the brief
    input: true
"""

_V6_UNCONFIRMED = """\
schema_version: 6
run: r1
step: spec-review
outcome: done
resolves:
  - id: s1
    state: unconfirmed
    body: built as described
"""

_V6_PLAIN = """\
schema_version: 6
run: r1
step: implement-phase
item: phase/1
outcome: done
ticks: [P1.T1.S1]
"""


def _record_file(root: Path, text: str, stem: str) -> Path:
    path = root / "docs" / "superpowers" / "runs" / "r1.records" / f"{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_six_to_seven_hop_is_in_the_chain() -> None:
    """The chain's full span is `test_record_acceptance_v8`'s to pin."""
    chain = MIGRATIONS.chain("record", PRE_FRAMEWORK_VERSION)
    assert [s.to_version for s in chain][:6] == [2, 3, 4, 5, 6, 7]
    assert artifact_kind("record").current_version == RECORD_SCHEMA_VERSION


def test_a_v6_record_carrying_delegated_migrates_with_the_key_dropped(tmp_path: Path) -> None:
    path = _record_file(tmp_path, _V6_DELEGATED, "brainstorm")

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert "delegated" not in path.read_text()
    record = load_record(path)
    assert record.schema_version == RECORD_SCHEMA_VERSION
    assert [j.id for j in record.journal] == ["d1", "operator-input"]
    assert record.journal[1].input is True


def test_a_v6_record_resolving_unconfirmed_is_left_byte_identical(tmp_path: Path) -> None:
    stuck = _record_file(tmp_path, _V6_UNCONFIRMED, "spec-review")
    healthy = _record_file(tmp_path, _V6_PLAIN, "implement-phase__phase-1")
    before = stuck.read_bytes()

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [stuck]
    assert "unconfirmed" in str(report.failed[0])
    assert stuck.read_bytes() == before
    assert artifact_kind("record").read_version(healthy) == RECORD_SCHEMA_VERSION


def test_an_older_record_carrying_delegated_climbs_the_whole_chain(tmp_path: Path) -> None:
    """Hops 4 -> 5 and 5 -> 6 read through the FROZEN model: with the live one,
    a v5 record carrying `delegated` would be refused at its first hop."""
    path = _record_file(
        tmp_path, _V6_DELEGATED.replace("schema_version: 6", "schema_version: 5"), "brainstorm"
    )

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert load_record(path).schema_version == RECORD_SCHEMA_VERSION


def test_a_wholly_v7_body_under_a_v6_stamp_lets_the_runner_finish(tmp_path: Path) -> None:
    """The crash window: `fn` rewrote the body, the runner died before the
    stamp. The next run finds a v7 body under a v6 stamp and just stamps it."""
    path = _record_file(tmp_path, _V6_PLAIN, "implement-phase__phase-1")

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path.read_text() == _V6_PLAIN.replace(
        "schema_version: 6", f"schema_version: {RECORD_SCHEMA_VERSION}"
    )


def test_the_live_model_refuses_the_removed_fields() -> None:
    with pytest.raises(RecordError, match="delegated"):
        parse_record(
            _V6_DELEGATED.replace("schema_version: 6", f"schema_version: {RECORD_SCHEMA_VERSION}")
        )
    with pytest.raises(RecordError, match="state"):
        parse_record(
            _V6_UNCONFIRMED.replace("schema_version: 6", f"schema_version: {RECORD_SCHEMA_VERSION}")
        )


def test_the_frozen_v6_reader_reads_both_removed_fields() -> None:
    assert legacy.parse_record_v6(_V6_DELEGATED).journal[0].delegated is True
    assert legacy.parse_record_v6(_V6_UNCONFIRMED).resolves[0].state == "unconfirmed"


def test_the_frozen_v6_reader_has_not_been_edited() -> None:
    frozen = {
        name for name, obj in vars(legacy).items() if inspect.isclass(obj) and name.endswith("V6")
    }
    assert frozen == set(legacy.FROZEN_CLASS_SHA256)
    drifted = {
        name
        for name in frozen
        if hashlib.sha256(inspect.getsource(getattr(legacy, name)).encode()).hexdigest()
        != legacy.FROZEN_CLASS_SHA256[name]
    }
    assert not drifted, f"{sorted(drifted)} changed; freeze a `…V7` beside them instead"
