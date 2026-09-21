"""The `run` kind's 4 -> 5 migration — the first one that REWRITES A BODY.

Spec `2026-09-20-unit-record-unification-design.md` §4.F. The pure rewrite is
`fr.run.legacy.v4_to_v5` and is tested on its own (`test_run_v4_to_v5.py`);
this file is about the thin module that puts it on disk, and the three
properties a body-rewriting migration has to have that a stamp-only one gets
for free:

1. it is built in memory and written ONCE, through the framework's atomic
   writer — a cursor it cannot convert is left byte-identical;
2. it reads with the FROZEN legacy model, never the live one — and so does
   every earlier hop, or the chain refuses every old cursor at its first hop;
3. it survives its own crash window — a v5 body still stamped 4 is not
   refused forever.

Inputs are the captured cursors of `tests/fixtures/run_cursors/`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml
from fr.artifacts import MIGRATIONS
from fr.artifacts.runner import ArtifactMigrationError

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "run_cursors"
ARTIFACTS_SRC = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "artifacts"

HOLDER = "v4/2026-09-20-feat-phase-holder-identity.yaml"
CLUSTER = "v4/2026-09-20-fix-fr-run-cursor-cluster.yaml"
INFLIGHT = "v2/2026-09-20-journal-require-reviews-v2.yaml"
MEASURED = "v3/2026-09-20-feat-bounded-executor-handoff.yaml"


def _copy(tmp_path: Path, name: str) -> Path:
    dest = tmp_path / Path(name).name
    dest.write_bytes((FIXTURES / name).read_bytes())
    return dest


def _freeze(path: Path) -> tuple[int, bytes]:
    os.utime(path, (1_000_000, 1_000_000))
    return path.stat().st_mtime_ns, path.read_bytes()


def _unchanged(path: Path, before: tuple[int, bytes]) -> bool:
    return (path.stat().st_mtime_ns, path.read_bytes()) == before


def _fn():
    from fr.artifacts.run_unit_record import rewrite_to_unit_records

    return rewrite_to_unit_records


# ------------------------------------------------------------- registration


def test_the_migration_is_registered_by_the_package_import() -> None:
    """A migration nobody imports never runs (`artifact-versioning.md`)."""
    hops = {(m.from_version, m.to_version) for m in MIGRATIONS.schema_migrations("run")}
    assert (4, 5) in hops


def test_it_says_it_rewrites_the_body() -> None:
    """Every earlier run migration's summary ends `stamp only, no body change`.
    `fr migrate artifacts` prints this line as the preview of what it is about
    to do to a file, so the first one that is NOT stamp-only must not read like
    the others."""
    (step,) = [m for m in MIGRATIONS.schema_migrations("run") if m.from_version == 4]
    assert "stamp only" not in step.summary
    assert "rewrites the body" in step.summary


# ---------------------------------------------------------------- the rewrite


@pytest.mark.parametrize("name", [HOLDER, CLUSTER, MEASURED, INFLIGHT])
def test_it_writes_exactly_what_the_pure_rewrite_returns(tmp_path: Path, name: str) -> None:
    from fr.run.legacy import v4_to_v5

    path = _copy(tmp_path, name)
    expected = v4_to_v5(yaml.safe_load(path.read_text()))

    _fn()(path)

    assert yaml.safe_load(path.read_text()) == expected


def test_a_body_with_no_unit_maps_is_left_byte_identical(tmp_path: Path) -> None:
    """A file fr does not need to change is a file fr does not touch: this is
    a byte-level replacement of something someone else authored, not a YAML
    normaliser. No capture is unit-less, so the case is induced from one by
    keeping its real header and one unit-less step."""
    lines = (FIXTURES / INFLIGHT).read_text().splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith("steps:"))
    body = "".join(lines[: start + 1]) + "  brainstorm:\n    state: done\n"
    body = re.sub(r"(?m)^cursor: .*$", "cursor: brainstorm", body)
    path = tmp_path / "noop.yaml"
    path.write_text(body)
    before = _freeze(path)

    _fn()(path)

    assert _unchanged(path, before)


def test_the_body_is_written_once_through_the_atomic_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fr.artifacts.run_unit_record as mod

    calls: list[Path] = []
    real = mod.write_text_atomic

    def spy(path: Path, text: str) -> None:
        calls.append(path)
        real(path, text)

    monkeypatch.setattr(mod, "write_text_atomic", spy)
    path = _copy(tmp_path, HOLDER)

    mod.rewrite_to_unit_records(path)

    assert calls == [path]
    assert list(tmp_path.glob(".*fr-tmp")) == [], "no temp file left behind"


def test_a_write_that_fails_leaves_the_cursor_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The half-write a stamp-only migration could never produce. `os.replace`
    is the last step of the atomic writer; failing THERE is the worst moment."""
    import fr.artifacts.atomic as atomic

    path = _copy(tmp_path, HOLDER)
    before = _freeze(path)

    def boom(*_: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(atomic.os, "replace", boom)

    with pytest.raises(OSError):
        _fn()(path)

    assert _unchanged(path, before)
    assert [p.name for p in tmp_path.iterdir()] == [path.name]


# ------------------------------------------------------------------ refusals


def test_a_partial_measurement_is_refused_and_the_file_is_byte_identical(tmp_path: Path) -> None:
    lines = (FIXTURES / MEASURED).read_text().splitlines(keepends=True)
    doomed = [i for i, line in enumerate(lines) if line.strip().startswith("input_tokens:")]
    assert doomed, "the capture carries no measurement — wrong fixture, not a pass"
    del lines[doomed[0]]
    path = tmp_path / "partial.yaml"
    path.write_text("".join(lines))
    before = _freeze(path)

    with pytest.raises(ArtifactMigrationError, match="input_tokens"):
        _fn()(path)

    assert _unchanged(path, before)


def test_an_unreadable_cursor_is_refused_not_certified(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("schema_version: 4\nrun: broken\ncursor: a\n")
    before = _freeze(path)

    with pytest.raises(ArtifactMigrationError, match="not a readable run cursor"):
        _fn()(path)

    assert _unchanged(path, before)


def test_a_v5_body_still_stamped_four_is_accepted_not_stranded(tmp_path: Path) -> None:
    """The crash window. `fn` writes the body, THEN the runner writes the
    stamp; a crash between the two leaves a v5 body under `schema_version: 4`.
    The frozen reader is `extra="forbid"` and does not know `units`, so a
    naive `fn` would refuse that file on every later run, forever — and it is
    exactly the cursor of a run that was in flight."""
    path = _copy(tmp_path, HOLDER)
    _fn()(path)
    assert "schema_version: 4" in path.read_text(), "fn never stamps; the runner does"
    before = _freeze(path)

    _fn()(path)  # second call: must neither raise nor rewrite

    assert _unchanged(path, before)


def test_a_body_that_is_neither_shape_is_still_refused(tmp_path: Path) -> None:
    """The crash-window tolerance must not become a back door: `units` beside
    a legacy map is a half-merged file, not an already-converted one."""
    path = _copy(tmp_path, HOLDER)
    _fn()(path)
    path.write_text(path.read_text() + "accounting:\n  phase/1/implement-phase:\n    at: x\n")
    before = _freeze(path)

    with pytest.raises(ArtifactMigrationError):
        _fn()(path)

    assert _unchanged(path, before)


# ------------------------------------- every hop reads with the legacy model


def test_no_run_migration_names_the_live_parser() -> None:
    """The rule in `.claude/rules/artifact-versioning.md`: no migration
    validates an old file against the live model. `parse_run_state_v4` is the
    frozen reader; a bare `parse_run_state` under `fr/artifacts/run_*.py` is
    the live one — allowed in exactly one place, the 4 -> 5 module's
    crash-window check of a body that is ALREADY v5."""
    live = re.compile(r"\bparse_run_state\b(?!_v4)")
    assert live.search("from fr.run.model import parse_run_state"), "the pattern is blind"
    assert not live.search("from fr.run.legacy import parse_run_state_v4")

    modules = sorted(ARTIFACTS_SRC.glob("run_*.py"))
    assert len(modules) >= 5, [m.name for m in modules]
    offenders = {
        m.name for m in modules if m.name != "run_unit_record.py" and live.search(m.read_text())
    }
    assert offenders == set()


@pytest.mark.parametrize("to_version", [2, 3, 4])
def test_each_stamp_only_hop_reads_a_cursor_the_live_model_may_no_longer_know(
    tmp_path: Path, to_version: int
) -> None:
    """Behavioural half of the rule above: each earlier hop's `fn` accepts a
    real cursor carrying `items` + `accounting` (and, for HOLDER, `dispatch`)."""
    (step,) = [m for m in MIGRATIONS.schema_migrations("run") if m.to_version == to_version]
    for name in (HOLDER, CLUSTER, MEASURED):
        step.fn(_copy(tmp_path, name))
