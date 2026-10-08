"""The `run` kind's 8 -> 9 migration: `Attempt.tier` and `Attempt.bound`
(spec 2026-10-06-cost-evidence §D, R7).

Stamp-only, following the 7 -> 8 precedent (`fr.artifacts.run_driver`), never
`cursor_guard`, which reads with the frozen v1-v4 model and would refuse every
v8 cursor. A v8 body is unchanged (an attempt with neither field reads as "not
recorded"); a body that does not read as v8 under the live model is refused
and left byte-identical.
"""

from __future__ import annotations

from pathlib import Path

from fr.artifacts import MIGRATIONS, run_migrations
from fr.artifacts.registry import ARTIFACT_KINDS, read_version
from fr.run.model import parse_run_state

# The real nesting: phase units live under the group step `implement`,
# keyed `phase/<n>/<member>` (copied from this repo's own cursor shape).
V8 = (
    "schema_version: 8\nrun: r1\nworkflow: fr-goal@1\nbranch: b\n"
    "started: '2026-10-02T00:00:00Z'\ncursor: implement\n"
    "steps:\n"
    "  implement:\n"
    "    state: running\n"
    "    units:\n"
    "      phase/1/implement-phase:\n"
    "        state: done\n"
    "        attempts:\n"
    "        - dispatched: '2026-10-02T00:01:00Z'\n"
    "          agent: a1\n"
    "          agent_type: super-fr:fr-phase-executor\n"
    "          harness: claude-code\n"
    "          model: claude-opus-5\n"
    "          returned: '2026-10-02T00:30:00Z'\n"
    "          outcome: done\n"
)


def _seed(root: Path, text: str) -> Path:
    path = root / "docs" / "superpowers" / "runs" / "r1.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_run_kind_is_past_version_nine() -> None:
    assert ARTIFACT_KINDS["run"].current_version >= 9


def test_the_hop_is_registered_and_moves_eight_to_nine() -> None:
    chain = MIGRATIONS.chain("run", 8)
    # The chain carries on through 9 -> 10 (`run_fr_version`), stamp-only too.
    assert [(m.from_version, m.to_version) for m in chain] == [(8, 9), (9, 10)]


def test_a_v8_cursor_is_stamped_nine_and_its_body_is_untouched(tmp_path: Path) -> None:
    assert parse_run_state(V8).steps["implement"].units  # the fixture is a real v8 body
    cursor = _seed(tmp_path, V8)

    report = run_migrations(tmp_path, dry_run=False)

    assert report.failed == (), report.failed
    assert read_version("run", cursor) == 10
    assert cursor.read_text() == V8.replace("schema_version: 8", "schema_version: 10")
    attempt = (
        parse_run_state(cursor.read_text())
        .steps["implement"]
        .units["phase/1/implement-phase"]
        .attempts[0]
    )
    assert (attempt.tier, attempt.bound) == (None, None), "older attempts read as not recorded"


def test_a_cursor_that_does_not_read_as_v8_is_refused_unchanged(tmp_path: Path) -> None:
    broken = V8 + "nonsense_key: 1\n"
    cursor = _seed(tmp_path, broken)

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [cursor]
    assert "version-8" in report.failed[0].error
    assert cursor.read_text() == broken
