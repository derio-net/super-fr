"""An in-flight run survives the `run` 4 -> 5 upgrade — end to end.

Spec `2026-09-20-unit-record-unification-design.md` §4.I, acceptance row
`run-upgrade-mid-run-keeps-holder`. This is the scenario the whole migration is
graded on: the plugin updates while a phase executor is mid-phase, the cursor on
disk is rewritten by `fr migrate artifacts --yes`, and the orchestrator's next
`fr run advance` must STILL refuse and STILL name the holder — or a second
writer is dispatched into a worktree that already has one.

The cursor is `tests/fixtures/run_cursors/v4/2026-09-20-unit-record-unification-r2.yaml`:
the real cursor of the run that built this feature, captured from git at the
moment its phase-3 executor held `phase/3/implement-phase` — a claimed, OPEN
attempt — immediately before that executor migrated it. Nothing here is typed.

What "equivalent" means, since the v4 CLI no longer exists to diff against: the
expectation is derived from the SAME capture through the FROZEN legacy reader
(`fr.run.legacy.parse_run_state_v4`), an independent path that shares no code
with the v5 model, the accessor layer or the rewrite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fr.artifacts import artifact_kind, run_migrations
from fr.run.legacy import RunStateV4, parse_run_state_v4
from fr.usage.file import load_usage, usage_path

from tests.unit.test_run_cli import _SHIPPED_FR_GOAL, _invoke, _repo, _squash

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "run_cursors"
HELD = "v4/2026-09-20-unit-record-unification-r2.yaml"
HOLDER = "v4/2026-09-20-feat-phase-holder-identity.yaml"
CLUSTER = "v4/2026-09-20-fix-fr-run-cursor-cluster.yaml"

HELD_KEY = "phase/3/implement-phase"


def _legacy(name: str) -> RunStateV4:
    return parse_run_state_v4((FIXTURES / name).read_text())


def _plan(repo: Path, plan_rel: str, *, phases: int) -> None:
    """A real plan at the path the captured cursor's `emitted.plan` names.

    `advance` reads the plan to learn which phases exist before it ever looks
    at a hold, so the cursor alone is not enough. Scaffolded with `fr`'s own
    `plan_ops.create` — the plan is scenery here, the cursor is the fixture.
    """
    from fr.plan_ops import PhaseSpec, create

    slug = Path(plan_rel).name
    spec_rel = f"docs/superpowers/specs/{slug}-design.md"
    (repo / spec_rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / spec_rel).write_text(
        "# Scenery\n\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n|------|------|------|------------|\n"
    )
    create(
        repo_root=repo,
        slug=slug,
        spec=spec_rel,
        target_repo="derio-net/test",
        fr_version=">=3.0.0,<5.0.0",
        phases=[
            PhaseSpec(
                number=n,
                title=f"Phase {n}",
                tag="agentic",
                depends_on=(),
                tasks=(
                    {
                        "number": 1,
                        "title": "t",
                        "steps": [{"id": f"P{n}.T1.S1", "text": "do the thing"}],
                    },
                ),
            )
            for n in range(1, phases + 1)
        ],
        prose="# scenery\n",
    )


def _in_flight(tmp_path: Path, name: str) -> tuple[Path, Path, str]:
    """A workspace on the captured cursor's own branch, holding that cursor —
    still v4, byte for byte — plus the shipped `fr-goal` shape and a plan."""
    legacy = _legacy(name)
    repo = _repo(tmp_path, branch=legacy.branch)
    shipped = tmp_path / "shipped"
    shipped.mkdir()
    # The shape the run was STARTED against: the real shipped `fr-goal`, less
    # any step added since (gh#517 added `journal-check` after two of these
    # captures began). `advance` refuses a cursor whose step list drifted from
    # its manifest, which is correct and is not what is under test here.
    manifest = yaml.safe_load(_SHIPPED_FR_GOAL.read_text())
    manifest["steps"] = [s for s in manifest["steps"] if s["id"] in legacy.steps]
    (shipped / "fr-goal.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    dest = repo / "docs" / "superpowers" / "runs" / Path(name).name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes((FIXTURES / name).read_bytes())
    plan_rel = legacy.steps["plan"].emitted["plan"]  # type: ignore[index]
    phases = max(int(key.split("/")[1]) for key in legacy.steps["implement"].items or {})
    _plan(repo, plan_rel, phases=phases)
    return repo, shipped, legacy.run


def _migrate(repo: Path) -> None:
    report = run_migrations(repo, dry_run=False)
    assert report.ok, [(f.path.name, f.error) for f in report.failed]
    kind = artifact_kind("run")
    for path in (repo / "docs" / "superpowers" / "runs").glob("*.yaml"):
        assert kind.read_version(path) == kind.current_version


# ------------------------------------------------------- the capture itself


def test_the_capture_really_is_a_held_unit_in_the_old_shape() -> None:
    """Everything below is vacuous if the fixture is not what it claims."""
    legacy = _legacy(HELD)
    assert legacy.schema_version == 4
    record = legacy.steps["implement"]
    assert (record.items or {})[HELD_KEY] == "running"
    (attempt,) = (record.dispatch or {})[HELD_KEY]
    assert attempt.returned is None and attempt.outcome is None
    assert attempt.agent and attempt.agent_type and attempt.harness and attempt.model


# --------------------------------------------------------------- the refusal


def test_a_held_unit_is_still_refused_and_still_names_its_holder_after_the_migration(
    tmp_path: Path,
) -> None:
    repo, shipped, run_id = _in_flight(tmp_path, HELD)
    (held,) = (_legacy(HELD).steps["implement"].dispatch or {})[HELD_KEY]
    _migrate(repo)
    cursor = repo / "docs" / "superpowers" / "runs" / f"{run_id}.yaml"
    before = cursor.read_bytes()

    result = _invoke(repo, shipped, ["run", "advance", run_id])

    assert result.exit_code == 2, result.output
    flat = _squash(result.output)
    assert f"{HELD_KEY} is ALREADY HELD by agent {held.agent}" in flat
    for fact in (held.agent_type, held.harness, held.model, held.dispatched):
        assert fact in flat, f"the refusal lost {fact!r}"
    assert "{" not in result.stdout, "a refusal must print no brief"
    assert cursor.read_bytes() == before, "a refusal writes nothing"


def test_the_holder_can_still_resolve_its_unit_after_the_migration(tmp_path: Path) -> None:
    """The other half of surviving: the executor that was holding the unit
    when the cursor moved under it finishes, and its `resolve` closes THE SAME
    attempt — it does not open a second, and the identity is not lost."""
    from fr.run import units
    from fr.run.model import load_run_state

    repo, shipped, run_id = _in_flight(tmp_path, HELD)
    (held,) = (_legacy(HELD).steps["implement"].dispatch or {})[HELD_KEY]
    _migrate(repo)

    result = _invoke(
        repo,
        shipped,
        ["run", "resolve", run_id, "--step", "implement-phase", "--item", "phase/3"]
        + ["--state", "done"],
    )

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, run_id).steps["implement"]
    (closed,) = units.attempts(record, HELD_KEY)
    assert (closed.agent, closed.dispatched) == (held.agent, held.dispatched)
    assert closed.outcome == "done" and closed.returned is not None
    # run 7: the cost did not ride along on the attempt — it moved to usage/
    usage = load_usage(usage_path(repo, run_id))
    assert usage is not None
    assert any(HELD_KEY in e.briefs for c in usage.captures for e in c.sessions)
    assert units.unit_state(record, HELD_KEY) == "done"


# ------------------------------------------------------------ status / check


def _v4_open_dispatches(legacy: RunStateV4) -> list[tuple[str, str]]:
    """`(step id, unit key)` of every OPEN dispatch, as the v4 shape meant it:
    the last record of a key's list, unreturned. Steps in file order, keys
    sorted — what `fr run check` printed."""
    found = []
    for step_id, record in legacy.steps.items():
        for key in sorted(record.dispatch or {}):
            attempts = (record.dispatch or {})[key]
            if attempts and attempts[-1].returned is None:
                found.append((step_id, key))
    return found


@pytest.mark.parametrize("name", [HELD, HOLDER, CLUSTER])
def test_check_reports_exactly_the_open_dispatches_the_v4_cursor_had(
    tmp_path: Path, name: str
) -> None:
    """`fr run check` is equivalent across the migration: same exit code, and
    an `is open` line for every dispatch that WAS open — and for nothing else.

    `CLUSTER` and `HOLDER` are the trap. Most of their units predate the
    dispatch record, so the rewrite SYNTHESIZES an attempt to carry their cost,
    and that attempt has no `returned`. Read as a hold, every finished unit of
    every older cursor shows up here as open."""
    repo, shipped, run_id = _in_flight(tmp_path, name)
    expected = _v4_open_dispatches(_legacy(name))
    _migrate(repo)

    result = _invoke(repo, shipped, ["run", "check", run_id])

    assert result.exit_code == 0, result.output
    open_lines = [line for line in _squash_lines(result.output) if " is open — " in line]
    assert [line.split(" is open — ")[0] for line in open_lines] == [
        f"{step_id}: {key}" for step_id, key in expected
    ]


def _squash_lines(output: str) -> list[str]:
    return [" ".join(line.split()) for line in output.splitlines() if line.strip()]


@pytest.mark.parametrize("name", [HELD, HOLDER, CLUSTER])
def test_status_still_shows_every_unit_state_and_every_prior_attempt(
    tmp_path: Path, name: str
) -> None:
    repo, shipped, run_id = _in_flight(tmp_path, name)
    legacy = _legacy(name)
    _migrate(repo)

    result = _invoke(repo, shipped, ["run", "status", run_id])

    assert result.exit_code == 0, result.output
    flat = _squash(result.output)
    for record in legacy.steps.values():
        for key, state in (record.items or {}).items():
            assert f"{key}: {state}" in flat
        for attempts in (record.dispatch or {}).values():
            for attempt in attempts:
                assert attempt.dispatched in flat, "a recorded attempt vanished from status"
                if attempt.agent:
                    assert f"agent {attempt.agent}" in flat
    # Since run 7 a cost is no longer rendered by `fr run status` at all: the
    # 6 -> 7 hop MOVED every snapshot into the run's usage file, keyed by the
    # same unit, so what must survive the upgrade is that file's figure.
    usage = load_usage(usage_path(repo, run_id))
    briefs = {
        k: v
        for c in (usage.captures if usage else ())
        for e in c.sessions
        for k, v in e.briefs.items()
    }
    for key, snap in (legacy.accounting or {}).items():
        assert briefs.get(key) == snap.handoff_chars, f"{key}'s estimate was not moved to usage/"


def _unit_block(output: str, key: str) -> str:
    """Everything `fr run status` printed UNDER `key`'s own line — its
    attempts and, since phase 4, each attempt's cost beneath it."""
    lines = output.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip().startswith(f"{key}:"))
    indent = len(lines[start]) - len(lines[start].lstrip())
    block = []
    for line in lines[start + 1 :]:
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        block.append(" ".join(line.split()))
    return " ".join(block)


def test_a_synthesized_attempt_is_not_rendered_as_the_orchestrators(tmp_path: Path) -> None:
    """An absent `agent_type` on a RECORDED attempt means the orchestrator ran
    the unit itself. On a synthesized one it means fr never recorded who did —
    and `CLUSTER`'s units were phase executors, so "held by the orchestrator"
    would be a false statement about a real run."""
    repo, shipped, run_id = _in_flight(tmp_path, CLUSTER)
    _migrate(repo)

    flat = _squash(_invoke(repo, shipped, ["run", "status", run_id]).output)

    assert "holder not recorded" in flat
    assert "orchestrator" not in flat
