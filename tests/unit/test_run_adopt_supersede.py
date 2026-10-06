"""`fr run adopt --supersede` — carry-forward and the command around it
(spec 2026-10-05-run-upgrade-midflight §C, R5/R6, and §D's by-adoption
paragraph for the ordering of inference and carry).

Fixtures are the shipped `fr-goal` shape and `tests/unit/test_run_adopt.py`'s
repo builders, so adoption infers against the shape that actually ships.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml as _yaml
from fr.archive import find_run_for_plan
from fr.artifacts.structure import validate_run
from fr.run import units
from fr.run.adopt import (
    AdoptError,
    adopt_run,
    build_run_state,
    carry_forward,
    infer_adoption,
)
from fr.run.model import (
    Attempt,
    RunState,
    StepRecord,
    load_run_state,
    run_path,
    save_run_state,
)
from fr.workflow.resolve import resolve_workflow

from tests.unit.test_run_adopt import (
    BRANCH,
    PLAN_SLUG,
    SPEC_REL,
    _commit_all,
    _git,
    _invoke,
    _repo,
    _review_entry,
    _write_plan,
    _write_spec,
)

NOW = "2026-10-06T12:00:00+00:00"
OLD_RUN = "2019-03-04-feat-widget-machinery"


def _fresh(repo: Path, shipped: Path, plan_dir: Path, *, run_id: str = "new-run") -> RunState:
    """What adoption alone would infer for the plan, under `run_id` — the
    `new` side of a pure `carry_forward`."""
    from fr.parser import parse

    plan = parse(plan_dir)
    manifest = resolve_workflow("fr-goal", repo, shipped_root=shipped)
    adoption = infer_adoption(
        plan=plan,
        spec_rel=SPEC_REL,
        plan_rel=f"docs/superpowers/plans/{plan_dir.name}",
        pr_state=lambda _u: None,
    )
    return build_run_state(
        manifest,
        adoption,
        run_id=run_id,
        branch=BRANCH,
        started="2026-10-06T11:00:00+00:00",
    )


def _plan_repo(tmp_path: Path, repo_root: Path, *, complete: int = 1) -> tuple[Path, Path, Path]:
    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2, complete=complete)
    return repo, shipped, plan_dir


def _attempt(**kw: object) -> Attempt:
    return Attempt(dispatched="2026-10-01T10:00:00+00:00", **kw)  # type: ignore[arg-type]


# --- Task 1: carry_forward (pure) ----------------------------------------------


def test_carry_forward_copies_gate_provenance_and_missing_emitted_keys(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _plan_repo(tmp_path, repo_root)
    new = _fresh(repo, shipped, plan_dir)
    old = new.model_copy(update={"run": OLD_RUN})
    brainstorm = old.steps["brainstorm"].model_copy(
        update={
            "gate": "cleared",
            "answered_by": "operator",
            "emitted": {"spec": SPEC_REL, "extra": "kept-from-old"},
        }
    )
    old = old.model_copy(update={"steps": {**old.steps, "brainstorm": brainstorm}})

    out = carry_forward(old, new, now=NOW)

    carried = out.steps["brainstorm"]
    assert carried.gate == "cleared"
    assert carried.answered_by == "operator"
    # a key the inference set wins; one only the old cursor had is added
    assert carried.emitted == {"spec": SPEC_REL, "extra": "kept-from-old"}
    assert out.run == "new-run"


def test_carry_forward_carries_every_old_unit_with_attempts_and_evidence(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _plan_repo(tmp_path, repo_root)
    new = _fresh(repo, shipped, plan_dir)
    old = new.model_copy(update={"run": OLD_RUN})
    implement = old.steps["implement"]
    implement = units.with_unit_state(implement, "phase/1/review-phase", "done")
    implement = units.with_evidence(
        implement,
        "phase/1/review-phase",
        {"review": "rev-1", "reviewer": "super-fr:fr-reviewer", "findings": "none"},
    )
    implement = units.with_attempt_appended(
        implement,
        "phase/1/review-phase",
        _attempt(agent="a1", returned="2026-10-01T11:00:00+00:00", outcome="done"),
    )
    spec_review = units.with_attempt_appended(
        old.steps["spec-review"],
        "step/spec-review",
        _attempt(agent="a2", returned="2026-10-01T09:00:00+00:00", outcome="done"),
    )
    spec_review = units.with_evidence(spec_review, "step/spec-review", {"review": "s-1"})
    old = old.model_copy(
        update={"steps": {**old.steps, "implement": implement, "spec-review": spec_review}}
    )

    out = carry_forward(old, new, now=NOW)

    review = out.steps["implement"]
    assert units.unit_state(review, "phase/1/review-phase") == "done"
    assert units.evidence_of(review, "phase/1/review-phase")["reviewer"] == "super-fr:fr-reviewer"
    assert [a.agent for a in units.attempts(review, "phase/1/review-phase")] == ["a1"]
    # a unit adoption never builds (a flat step's) arrives too, still stateless
    flat = out.steps["spec-review"]
    assert units.unit_state(flat, "step/spec-review") is None
    assert units.evidence_of(flat, "step/spec-review") == {"review": "s-1"}
    assert [a.agent for a in units.attempts(flat, "step/spec-review")] == ["a2"]
    # the unit adoption did build keeps what adoption inferred
    assert units.unit_state(review, "phase/1/implement-phase") == "done"


def test_carry_forward_drops_units_of_removed_steps_and_members(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _plan_repo(tmp_path, repo_root)
    new = _fresh(repo, shipped, plan_dir)
    old = new.model_copy(update={"run": OLD_RUN})
    implement = units.with_unit_state(old.steps["implement"], "phase/1/retired-member", "done")
    old = old.model_copy(
        update={
            "steps": {
                **old.steps,
                "implement": implement,
                "retired-step": StepRecord(state="done", gate="cleared", answered_by="operator"),
            }
        }
    )

    out = carry_forward(old, new, now=NOW)

    assert "retired-step" not in out.steps
    assert "phase/1/retired-member" not in (out.steps["implement"].units or {})


def test_carry_forward_closes_an_open_attempt_as_abandoned(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped, plan_dir = _plan_repo(tmp_path, repo_root, complete=0)
    new = _fresh(repo, shipped, plan_dir)
    old = new.model_copy(update={"run": OLD_RUN})
    implement = units.with_unit_state(old.steps["implement"], "phase/1/implement-phase", "running")
    implement = units.with_attempt_appended(
        implement, "phase/1/implement-phase", _attempt(agent="held", session="s-9")
    )
    old = old.model_copy(update={"steps": {**old.steps, "implement": implement}})

    out = carry_forward(old, new, now=NOW)

    record = out.steps["implement"]
    (attempt,) = units.attempts(record, "phase/1/implement-phase")
    assert (attempt.returned, attempt.outcome, attempt.agent) == (NOW, "abandoned", "held")
    assert units.open_attempt(record, "phase/1/implement-phase") is None
    # a hold is no state the new cursor may keep: `advance` must re-brief it
    assert units.unit_state(record, "phase/1/implement-phase") == "pending"


def test_carry_forward_keeps_driver_and_the_at_of_carried_done_steps(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _plan_repo(tmp_path, repo_root)
    new = _fresh(repo, shipped, plan_dir)
    old = new.model_copy(update={"run": OLD_RUN, "driver": "standalone"})
    brainstorm = old.steps["brainstorm"].model_copy(update={"at": "2026-09-01T09:00:00+00:00"})
    old = old.model_copy(update={"steps": {**old.steps, "brainstorm": brainstorm}})

    out = carry_forward(old, new, now=NOW)

    assert out.driver == "standalone"
    assert out.steps["brainstorm"].at == "2026-09-01T09:00:00+00:00"


def test_a_carried_cursor_passes_the_structure_validator(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped, plan_dir = _plan_repo(tmp_path, repo_root)
    new = _fresh(repo, shipped, plan_dir)
    old = new.model_copy(update={"run": OLD_RUN})
    implement = units.with_unit_state(old.steps["implement"], "phase/1/review-phase", "done")
    implement = units.with_attempt_appended(
        implement, "phase/1/review-phase", _attempt(agent="held")
    )
    old = old.model_copy(update={"steps": {**old.steps, "implement": implement}})

    out = carry_forward(old, new, now=NOW)
    save_run_state(repo, out)

    assert validate_run(run_path(repo, out.run)) == []


# --- Task 2: adopt --supersede (R5, R6) ------------------------------------------


def _commit_count(repo: Path) -> int:
    return int(
        subprocess.run(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )


def _head_subject(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%s"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _squash(text: str) -> str:
    return " ".join(text.split())


def _old_run(tmp_path: Path, repo_root: Path, *, hold: bool = True) -> tuple[Path, Path, Path]:
    """A repo on a feature branch holding a committed run `old-run` for a
    two-phase plan: phase 1 ticked, the brainstorm gate cleared by the operator,
    and (with `hold`) phase 2's implement unit held by a live agent."""
    repo, shipped, plan_dir = _plan_repo(tmp_path, repo_root)
    _commit_all(repo)
    _git(repo, "checkout", "-q", "-b", "feat/old")
    first = _invoke(
        repo, shipped, ["run", "adopt", str(plan_dir), "--branch", BRANCH, "--run-id", "old-run"]
    )
    assert first.exit_code == 0, first.output
    state = load_run_state(repo, "old-run")
    brainstorm = state.steps["brainstorm"].model_copy(
        update={"gate": "cleared", "answered_by": "operator"}
    )
    implement = state.steps["implement"]
    if hold:
        implement = units.with_unit_state(implement, "phase/2/implement-phase", "running")
        implement = units.with_attempt_appended(
            implement, "phase/2/implement-phase", _attempt(agent="held-agent", session="sess-42")
        )
    save_run_state(
        repo,
        state.model_copy(
            update={"steps": {**state.steps, "brainstorm": brainstorm, "implement": implement}}
        ),
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "old cursor, history")
    return repo, shipped, plan_dir


def _supersede(repo: Path, shipped: Path, plan_dir: Path, *extra: str):
    return _invoke(
        repo,
        shipped,
        [
            "run",
            "adopt",
            str(plan_dir),
            "--supersede",
            "--branch",
            BRANCH,
            "--run-id",
            "new-run",
            *extra,
        ],
    )


def test_adopt_over_an_existing_run_names_reshape_and_supersede(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _old_run(tmp_path, repo_root)
    before = _commit_count(repo)

    result = _invoke(repo, shipped, ["run", "adopt", str(plan_dir), "--branch", BRANCH])

    out = _squash(result.output)
    assert result.exit_code == 2, result.output
    assert "fr run reshape old-run" in out
    assert "fr run adopt" in out and "--supersede" in out
    assert _commit_count(repo) == before


def test_supersede_with_no_existing_run_is_a_plain_adopt(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped, plan_dir = _plan_repo(tmp_path, repo_root)

    result = _supersede(repo, shipped, plan_dir)

    assert result.exit_code == 0, result.output
    assert run_path(repo, "new-run").is_file()
    assert find_run_for_plan(repo, Path("docs/superpowers/plans") / PLAN_SLUG) == "new-run"


def test_supersede_preview_lists_the_closed_holds_and_writes_nothing(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _old_run(tmp_path, repo_root)
    old_bytes, commits = run_path(repo, "old-run").read_bytes(), _commit_count(repo)

    result = _supersede(repo, shipped, plan_dir)

    out = _squash(result.output)
    assert result.exit_code == 0, result.output
    assert "held-agent" in out and "sess-42" in out and "abandoned" in out
    assert "--yes" in out
    assert run_path(repo, "old-run").read_bytes() == old_bytes
    assert not run_path(repo, "new-run").exists()
    assert _commit_count(repo) == commits


def test_supersede_yes_replaces_the_run_in_one_commit_and_carries_provenance(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _old_run(tmp_path, repo_root)
    usage = repo / "docs" / "superpowers" / "usage" / "old-run.yaml"
    usage.parent.mkdir(parents=True)
    usage.write_text("schema_version: 1\nrun: old-run\ncaptures: []\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "usage")
    commits = _commit_count(repo)

    result = _supersede(repo, shipped, plan_dir, "--yes")

    assert result.exit_code == 0, result.output
    assert not run_path(repo, "old-run").exists()
    new = load_run_state(repo, "new-run")
    # the open hold is carried closed, never open
    (attempt,) = units.attempts(new.steps["implement"], "phase/2/implement-phase")
    assert (attempt.outcome, attempt.agent) == ("abandoned", "held-agent")
    # the usage file moved with the run
    assert not usage.exists()
    assert (usage.parent / "new-run.yaml").is_file()
    # one commit, naming what it superseded; nothing left uncommitted
    assert _commit_count(repo) == commits + 1
    assert "supersedes old-run" in _head_subject(repo)
    assert _git_status(repo) == ""
    # the operator's answer survives, which the hand-delete used to lose
    gates = _invoke(repo, shipped, ["run", "gates", "new-run"])
    assert gates.exit_code == 0, gates.output
    assert "brainstorm" in gates.output and "operator" in _squash(gates.output)


def _git_status(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_supersede_refuses_an_old_cursor_the_current_model_cannot_parse(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _old_run(tmp_path, repo_root)
    path = run_path(repo, "old-run")
    # the v4 shape: `items` instead of `units`, stamped 4 — a cursor an older fr
    # wrote, which `find_run_for_plan` still recognises but this model refuses
    data = _yaml.safe_load(path.read_text())
    data["schema_version"] = 4
    for record in data["steps"].values():
        units_map = record.pop("units", None) or {}
        if units_map:
            record["items"] = {k: v["state"] for k, v in units_map.items() if v.get("state")}
    path.write_text(_yaml.safe_dump(data, sort_keys=False))
    _git(repo, "commit", "-qam", "stale shape")
    before, commits = path.read_bytes(), _commit_count(repo)

    result = _supersede(repo, shipped, plan_dir, "--yes")

    assert result.exit_code == 2, result.output
    assert "fr migrate artifacts --yes" in _squash(result.output)
    assert path.read_bytes() == before
    assert not run_path(repo, "new-run").exists()
    assert _commit_count(repo) == commits


def test_supersede_refuses_while_the_old_run_has_a_step_record(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _old_run(tmp_path, repo_root)
    records = repo / "docs" / "superpowers" / "runs" / "old-run.records"
    records.mkdir()
    (records / "implement-phase__phase-2.yaml").write_text("run: old-run\n")
    before = run_path(repo, "old-run").read_bytes()

    result = _supersede(repo, shipped, plan_dir, "--yes")

    assert result.exit_code == 2, result.output
    assert "implement-phase__phase-2.yaml" in result.output
    assert run_path(repo, "old-run").read_bytes() == before
    assert not run_path(repo, "new-run").exists()


def test_a_pr_body_rendering_alone_does_not_refuse_a_supersede(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _old_run(tmp_path, repo_root)
    records = repo / "docs" / "superpowers" / "runs" / "old-run.records"
    records.mkdir()
    (records / "pr-body.md").write_text("rendered\n")

    result = _supersede(repo, shipped, plan_dir, "--yes")

    assert result.exit_code == 0, result.output
    assert run_path(repo, "new-run").is_file()


def test_a_same_day_run_id_overwrites_in_place(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped, plan_dir = _old_run(tmp_path, repo_root)

    result = _invoke(
        repo,
        shipped,
        [
            "run", "adopt", str(plan_dir), "--supersede", "--yes",
            "--branch", BRANCH, "--run-id", "old-run",
        ],
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    state = load_run_state(repo, "old-run")
    assert state.steps["brainstorm"].answered_by == "operator"
    assert "supersedes old-run" in _head_subject(repo)


def test_a_different_existing_run_path_still_refuses(tmp_path: Path, repo_root: Path) -> None:
    repo, shipped, plan_dir = _old_run(tmp_path, repo_root)
    other = load_run_state(repo, "old-run")
    other = other.model_copy(
        update={
            "run": "new-run",
            "steps": {
                sid: record.model_copy(update={"emitted": None})
                for sid, record in other.steps.items()
            },
        }
    )
    save_run_state(repo, other)
    before = run_path(repo, "new-run").read_bytes()

    result = _supersede(repo, shipped, plan_dir, "--yes")

    assert result.exit_code == 2, result.output
    assert "already exists" in result.output
    assert run_path(repo, "new-run").read_bytes() == before
    assert run_path(repo, "old-run").is_file()


def test_python_adopt_run_refuses_over_an_existing_run_without_the_flag(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _plan_repo(tmp_path, repo_root)
    adopt_run(repo, plan_dir, branch=BRANCH, run_id="old-run", shipped_root=shipped)

    with pytest.raises(AdoptError) as e:
        adopt_run(repo, plan_dir, branch=BRANCH, run_id="new-run", shipped_root=shipped)
    assert "fr run reshape old-run" in str(e.value) and "--supersede" in str(e.value)


# --- review p2-r5: carried implement attempts are visible to the inference ---------


def _reimplemented_old_run(tmp_path: Path, repo_root: Path, *, reviewed_by_old: bool):
    """An all-complete plan whose OLD cursor re-implemented phase 1 AFTER the
    plan journal's review of it (phase 2's review still follows its work)."""
    from fr.test_support import build_plan_journal

    repo, shipped = _repo(tmp_path, repo_root)
    _write_spec(repo)
    plan_dir = _write_plan(repo, phases=2, complete=2)
    _commit_all(repo)
    _git(repo, "checkout", "-q", "-b", "feat/old")
    first = _invoke(
        repo, shipped, ["run", "adopt", str(plan_dir), "--branch", BRANCH, "--run-id", "old-run"]
    )
    assert first.exit_code == 0, first.output
    build_plan_journal(repo, PLAN_SLUG, [_review_entry(1), _review_entry(2)])
    state = load_run_state(repo, "old-run")
    implement = state.steps["implement"]
    implement = units.with_attempt_appended(
        implement,
        "phase/1/implement-phase",
        _attempt(agent="redo", returned="2026-03-01T00:00:00+00:00", outcome="done"),
    )
    if reviewed_by_old:
        implement = units.with_unit_state(implement, "phase/1/review-phase", "done")
        implement = units.with_evidence(
            implement,
            "phase/1/review-phase",
            {"review": "rev-1", "reviewer": "super-fr:fr-reviewer", "findings": "none"},
        )
    save_run_state(
        repo, state.model_copy(update={"steps": {**state.steps, "implement": implement}})
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "old cursor re-implemented phase 1")
    return repo, shipped, plan_dir


def test_a_journal_review_older_than_a_recorded_reimplementation_is_not_historical(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _reimplemented_old_run(tmp_path, repo_root, reviewed_by_old=False)

    result = _supersede(repo, shipped, plan_dir, "--yes")

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, "new-run").steps["implement"]
    assert units.unit_state(record, "phase/1/review-phase") in (None, "pending")
    assert units.evidence_of(record, "phase/1/review-phase") == {}
    assert "phase 1's review is not historical" in _squash(result.output)
    assert "reviews earlier work" in _squash(result.output)
    # a review that does follow its work is still inferred
    assert units.evidence_of(record, "phase/2/review-phase")["reviewer"] == "historical"


def test_a_review_the_old_cursor_resolved_keeps_its_real_evidence(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _reimplemented_old_run(tmp_path, repo_root, reviewed_by_old=True)

    result = _supersede(repo, shipped, plan_dir, "--yes")

    assert result.exit_code == 0, result.output
    record = load_run_state(repo, "new-run").steps["implement"]
    assert units.unit_state(record, "phase/1/review-phase") == "done"
    assert units.evidence_of(record, "phase/1/review-phase")["reviewer"] == "super-fr:fr-reviewer"


# --- reviews p3-r1 / p3-r2: the file superseded is the file that names the plan --


def _rewrite_old(repo: Path, *, to: str, run: str, plan: str | None = None) -> Path:
    """Move `old-run`'s cursor to `runs/<to>.yaml` with `run: <run>` (and,
    when given, `emitted.plan` repointed) — a name/content mismatch."""
    src = run_path(repo, "old-run")
    data = _yaml.safe_load(src.read_text())
    data["run"] = run
    if plan is not None:
        for record in data["steps"].values():
            if (record.get("emitted") or {}).get("plan"):
                record["emitted"]["plan"] = plan
    dst = src.parent / f"{to}.yaml"
    dst.write_text(_yaml.safe_dump(data, sort_keys=False))
    if dst != src:
        src.unlink()
    return dst


def _snapshot(repo: Path) -> dict[str, bytes]:
    root = repo / "docs" / "superpowers"
    return {str(p.relative_to(repo)): p.read_bytes() for p in root.rglob("*.yaml")}


def test_supersede_refuses_a_traversal_run_id_and_touches_nothing(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _old_run(tmp_path, repo_root)
    # An archived cursor the crafted `run:` points at, which must survive.
    victim = repo / "docs" / "superpowers" / "implemented" / "runs" / "victim.yaml"
    victim.parent.mkdir(parents=True)
    victim.write_text(run_path(repo, "old-run").read_text())
    _rewrite_old(repo, to="old-run", run="../implemented/runs/victim")
    _commit_all(repo)
    before, commits = _snapshot(repo), _commit_count(repo)

    result = _supersede(repo, shipped, plan_dir, "--yes")

    assert result.exit_code == 2, result.output
    assert "invalid run id" in _squash(result.output)
    assert _snapshot(repo) == before
    assert _commit_count(repo) == commits


def test_supersede_refuses_a_run_file_whose_name_disagrees_with_its_run_field(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _old_run(tmp_path, repo_root)
    # `a-copy.yaml` names the plan but says `run: other-run`; the real
    # `other-run.yaml` is a DIFFERENT run (another plan). Superseding onto the
    # derived id `other-run` must neither read, delete nor overwrite it.
    other = _rewrite_old(repo, to="other-run", run="other-run", plan="docs/superpowers/plans/x")
    _rewrite_old_copy = other.read_text()
    (other.parent / "a-copy.yaml").write_text(
        _rewrite_old_copy.replace("docs/superpowers/plans/x", str(plan_dir.relative_to(repo)))
    )
    _commit_all(repo)
    assert find_run_for_plan(repo, plan_dir.relative_to(repo)) == "other-run"
    before, commits = _snapshot(repo), _commit_count(repo)

    argv = ["run", "adopt", str(plan_dir), "--supersede", "--branch", BRANCH, "--yes"]
    result = _invoke(repo, shipped, [*argv, "--run-id", "other-run"])

    assert result.exit_code == 2, result.output
    assert "disagrees with its `run:` field" in _squash(result.output)
    assert _snapshot(repo) == before
    assert _commit_count(repo) == commits


def test_supersede_refuses_when_no_file_carries_the_named_run_id(
    tmp_path: Path, repo_root: Path
) -> None:
    repo, shipped, plan_dir = _old_run(tmp_path, repo_root)
    _rewrite_old(repo, to="renamed", run="old-run")
    _commit_all(repo)
    before = _snapshot(repo)

    result = _supersede(repo, shipped, plan_dir, "--yes")

    assert result.exit_code == 2, result.output
    assert "disagrees with its `run:` field" in _squash(result.output)
    assert _snapshot(repo) == before
