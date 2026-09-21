"""The `run` kind's version-2 migration — spec §3.D.2 plus the obligations
`.claude/rules/artifact-versioning.md` attaches to every shape change.

`StepRecord` gaining `answered_by` is a shape change because `RunState` is
`extra="forbid"`-closed: an fr that does not know the key raises rather than
ignoring it. The rule therefore requires three things in the same PR — a stamp
bump in `fr.artifacts.registry` and nowhere else, a **registered** migration
(a migration nobody imports never runs), and a structure validator reachable
as `ArtifactKind.validate`. These tests pin all three, and the one property
that makes the migration safe to run over a live cursor: it rewrites no body.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml
from fr.artifacts import MIGRATIONS, artifact_kind, run_migrations
from fr.artifacts.registry import PRE_FRAMEWORK_VERSION
from fr.run.model import parse_run_state

_V1_RUN = """\
run: r1
workflow: fr-goal@1
branch: feat/x
started: '2026-09-18T09:00:00Z'
cursor: implement
steps:
  brainstorm:
    state: done
    gate: cleared
  implement:
    state: pending
"""


def _run_file(root: Path, text: str = _V1_RUN, stem: str = "r1") -> Path:
    path = root / "docs" / "superpowers" / "runs" / f"{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_run_kind_moved_past_version_one() -> None:
    assert artifact_kind("run").current_version > PRE_FRAMEWORK_VERSION


def test_a_migration_off_version_one_is_registered_for_the_run_kind() -> None:
    kind = artifact_kind("run")
    chain = MIGRATIONS.chain("run", PRE_FRAMEWORK_VERSION)
    assert chain, "no registered migration moves a pre-framework run file"
    assert chain[-1].to_version == kind.current_version


def test_registration_rides_the_package_import_not_the_callers_memory() -> None:
    """A migration nobody imports never runs. The registration must happen on
    `import fr.artifacts` — the import the runner, the trigger and the CLI all
    already do — not on importing the migration's own module."""
    code = "import fr.artifacts as a;print(len(a.MIGRATIONS.chain('run', a.PRE_FRAMEWORK_VERSION)))"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()
    assert out != "0", "importing fr.artifacts did not register the run migration"


def test_the_run_kind_carries_a_structure_validator(tmp_path: Path) -> None:
    """Reached as `ArtifactKind.validate`, which is what `fr validate
    artifacts` calls — the rule's third obligation. It validates against
    `RunState` itself, so the new field is covered the moment the model has
    it: a cursor claiming an unknown provenance is a structural problem."""
    kind = artifact_kind("run")
    assert kind.validate(_run_file(tmp_path)) == []
    liar = _run_file(
        tmp_path,
        _V1_RUN.replace("    state: pending\n", "    state: pending\n    answered_by: the-cat\n"),
        stem="r3",
    )
    assert kind.validate(liar) != []


def test_migrating_a_v1_run_file_stamps_it_and_rewrites_no_body(tmp_path: Path) -> None:
    """The new field is optional and defaulted, so there is nothing in the
    body to change: the migration's whole job is to move the stamp, and every
    other byte of an operator's cursor is left alone."""
    path = _run_file(tmp_path)
    before = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.ok, report.failed
    assert path in report.changed_paths
    after = path.read_text()
    kind = artifact_kind("run")
    assert kind.read_version(path) == kind.current_version
    # everything except the added stamp line survives verbatim
    stripped = "\n".join(
        line for line in after.splitlines() if not line.startswith("schema_version:")
    )
    assert stripped.strip() == before.strip()
    state = parse_run_state(after)
    assert state.schema_version == kind.current_version
    assert state.steps["brainstorm"].gate == "cleared"
    assert state.steps["brainstorm"].answered_by is None


def test_migrating_is_idempotent(tmp_path: Path) -> None:
    path = _run_file(tmp_path)
    run_migrations(tmp_path, dry_run=False)
    once = path.read_text()

    report = run_migrations(tmp_path, dry_run=False)

    assert report.applied == ()
    assert path.read_text() == once


def test_a_run_file_that_is_not_run_state_is_reported_never_stamped(tmp_path: Path) -> None:
    """There is no body rewrite to get wrong, so the migration's one real
    decision is what to do with a file it cannot read as a run cursor:
    refuse it, name it, leave it unstamped so the next run retries it — and
    migrate every other run file regardless (runner invariant 3)."""
    broken = _run_file(tmp_path, "run: r2\ncursor: a\n", stem="r2")  # missing required fields
    healthy = _run_file(tmp_path)

    report = run_migrations(tmp_path, dry_run=False)

    assert [f.path for f in report.failed] == [broken]
    assert yaml.safe_load(broken.read_text()).get("schema_version") is None
    assert artifact_kind("run").read_version(healthy) == artifact_kind("run").current_version


def test_this_repos_own_run_cursors_are_current(repo_root: Path) -> None:
    """Dogfooding, per the rule: the moment `current_version` moved, this
    repo's own live cursors went stale — including the cursor of the very run
    that is doing the moving — and CI (`CI=true`, non-interactive) refuses
    rather than migrating. `fr migrate artifacts --yes` was run here and its
    result committed.

    ZERO LIVE CURSORS IS A PASS, and the `assert live, "this test would prove
    nothing"` guard that used to sit here was wrong. Its instinct was right — a
    test that can pass vacuously proves nothing — but it conflated two
    different states: *the repo has no live cursors*, which is the normal
    condition between runs and the exact condition one second after
    `fr archive` moves the last one to `implemented/`, and *the fixture is
    broken*, which is a problem. An empty set is not evidence of a broken
    fixture.

    It failed the archive PR of the very PR that introduced it (#482), on a
    repo in a perfectly correct state. The anti-vacuity concern is already
    carried by this file's synthetic-fixture siblings
    (`test_migrating_a_v1_run_file_stamps_it_and_rewrites_no_body`,
    `test_migrating_is_idempotent`,
    `test_a_run_file_that_is_not_run_state_is_reported_never_stamped`), which
    build their own cursors and cannot go vacuous. This test's job is narrower:
    whatever live cursors exist, none of them is stale."""
    kind = artifact_kind("run")
    from fr.artifacts import iter_artifact_paths

    for path in iter_artifact_paths(repo_root, "run"):
        assert kind.read_version(path) == kind.current_version, f"{path} is stale"
