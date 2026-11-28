"""The stale ops workspace (spec 2026-11-27-ops-gate-truth R1–R6, §A).

Stage 3 of `fr ops gate` is the only place the ops workspace used to move onto the default
branch. A later stage that failed and was rerun applied the ops as stage 3 saw them, even
after a fix to an op landed on the default branch (gh#1617). So before stages 4, 5, 6 and 7
act, `refresh` compares the workspace with `origin/<default>`:

- `drift` loads the run's ops on both sides (`fr.ops.load.load_ops`, compared op by op on
  the whole frozen definition) and the run's Test Plan steps (`fr.spec.test_plan_steps`).
  A side that cannot be read is a refusal, never "equal". Rows are left out on purpose:
  the ops branch writes row walks the default branch does not hold yet.
- `refresh` asks the operator (always, `--yes` or not), commits the workspace's records,
  merges `origin/<default>` with a merge commit (never a rebase: the pushed ops branch
  moves forward only), pushes it leased, reopens the changed and added ops in the host
  state and re-checks trust. A refresh after stage 4 that reopened anything sends the run
  back to stage 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from fr.ops.gate import MergeConflict, Restart, StageFailed

if TYPE_CHECKING:
    from collections.abc import Callable

    from fr.ops.gate import Gate, GateState, OpsTree
    from fr.ops.model import Op
    from fr.spec import Step


@dataclass(frozen=True)
class Drift:
    """What differs between the ops workspace and the default branch: op ids added on the
    default branch, removed from it, or changed, and whether the Test Plan changed."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]
    test_plan: bool

    @property
    def differs(self) -> bool:
        return bool(self.added or self.removed or self.changed or self.test_plan)


def _ops_of(root: Path, plan_rel: str, side: str) -> dict[str, Op]:
    """The run's ops on one side, by id (runbook ops the plan needs included); a carrier
    that does not load is a refusal, never an empty set."""
    from fr.ops.load import OpsLoadError, load_ops

    try:
        return {lo.op.id: lo.op for lo in load_ops(root / plan_rel, root).ops}
    except (OpsLoadError, OSError) as exc:
        raise StageFailed(f"the ops on {side} cannot be read: {exc}", code=2) from exc


def _steps_of(root: Path, spec_rel: str | None, side: str) -> list[Step] | None:
    """The run's Test Plan steps on one side; None when the spec is not there."""
    from fr.spec import TestPlanHeadingError, test_plan_steps

    if spec_rel is None:
        return []
    path = root / spec_rel
    try:
        if not path.is_file():
            return None
        return test_plan_steps(path.read_text(), source=f"{spec_rel} on {side}")
    except (OSError, UnicodeDecodeError, TestPlanHeadingError) as exc:
        raise StageFailed(f"the Test Plan on {side} cannot be read: {exc}", code=2) from exc


def drift(workspace_root: Path, default_root: Path, plan_rel: str, spec_rel: str | None) -> Drift:
    """The ops and the Test Plan of the ops workspace against the default branch (R1). A
    plan directory the default branch lacks is a refusal (R5), as is a side that cannot be
    read: unknown is never "equal"."""
    if not (default_root / plan_rel).is_dir():
        raise StageFailed(
            f"the run's plan directory {plan_rel} is not on the default branch; the ops "
            "workspace cannot be brought up to date",
            code=2,
        )
    mine = _ops_of(workspace_root, plan_rel, "the ops workspace")
    tip = _ops_of(default_root, plan_rel, "the default branch")
    return Drift(
        added=tuple(i for i in tip if i not in mine),
        removed=tuple(i for i in mine if i not in tip),
        changed=tuple(i for i in mine if i in tip and mine[i] != tip[i]),
        test_plan=_steps_of(workspace_root, spec_rel, "the ops workspace")
        != _steps_of(default_root, spec_rel, "the default branch"),
    )


def closure_exclusions(state: GateState, at_head: set[str]) -> Callable[[str], set[str]]:
    """Per op id, the plan-journal entries that do not close it: the PR head's own
    (*at_head*), and for an op a refresh reopened, also every entry present at that refresh.
    Only its live status, or evidence recorded after the refresh, closes it (R6)."""
    reopened, before = state.reopened()
    return lambda op_id: at_head | before if op_id in reopened else at_head


def _question(d: Drift, ref: str, branch: str) -> str:
    kinds = (("added", d.added), ("removed", d.removed), ("changed", d.changed))
    moved = [f"{what}: {', '.join(ids)}" for what, ids in kinds if ids]
    if d.test_plan:
        moved.append("Test Plan changed")
    return (
        f"REFRESH {branch} from {ref}? The ops workspace is behind it ({'; '.join(moved)}). "
        f"fr commits the workspace's records, merges {ref} with a merge commit (never a "
        "rebase), pushes the ops branch, reopens the changed and added ops and asks for "
        "trust again"
    )


def _entry_ids(tree: OpsTree, slug: str) -> set[str]:
    """The ids of the entries the ops workspace's plan journal holds now."""
    from fr.journal.model import JournalParseError, parse_journal, resolve_journal_read_path

    path = resolve_journal_read_path(tree.path, "plan", slug)
    try:
        return {e.id for e in parse_journal(path.read_text())} if path.is_file() else set()
    except (OSError, JournalParseError) as exc:  # never an empty `before`: a refusal
        raise StageFailed(f"the plan journal {path} cannot be read: {exc}", code=2) from exc


def _merge_by_hand(gate: Gate, tree: OpsTree, ref: str, paths: tuple[str, ...]) -> str:
    """*ref* is the pinned sha: the commit the operator confirmed, never a moved tip."""
    where = tree.path
    return (
        f"merging {ref} into {gate.target.ops_branch} conflicts on {', '.join(paths)}; the "
        "merge was aborted and nothing was pushed. Merge by hand, then re-run the stage: "
        f"`git -C {where} merge {ref}`, resolve each path, `git -C {where} add <path>`, "
        f"`git -C {where} commit --no-edit`, then `fr ops gate --run {gate.target.run.run} --yes`"
    )


def _runbook_rel(root: Path) -> list[str]:
    """The runbook `.fr/ops.yaml` names under *root*, as a path to materialise: a runbook
    op a plan op `needs` is part of the ops either side loads (l-tests-r4). An unreadable
    config names nothing here; `drift` reports it when it loads the ops."""
    from fr.ops.load import OpsLoadError, load_ops_config

    try:
        runbook = load_ops_config(root).runbook
    except OpsLoadError, OSError:
        return []
    return [runbook] if runbook else []


def _settle_pending_merge(gate: Gate, tree: OpsTree) -> None:
    """A refresh whose merge failed left the pinned commit for the operator to merge by
    hand (l-errors-r3). Whatever that commit's plan journal holds is the default branch's,
    so it joins the reopened ops' `before` even when the hand merge left no drift."""
    from fr.ops.gate import head_entry_ids

    pending = gate.state.pending_merge()
    if pending is None:
        return
    ops, before = gate.state.reopened()
    if ops:
        merged_in = head_entry_ids(tree, pending, "plan", gate.target.slug)
        gate.state.set_reopened(ops, before | merged_in)
    gate.state.set_pending_merge(None)


def refresh(gate: Gate, tree: OpsTree, stage: int) -> None:
    """Bring the ops workspace up to date with the default branch before stage *stage* acts
    (R1–R6); says nothing when nothing moved. Raises `Restart` when a refresh after stage 4
    reopened an op (back to stage 4, which applies it again), or after stage 5 changed only
    the Test Plan (back to stage 5, which walks it again)."""
    import shutil

    from fr.artifacts.paths import KIND_DIRS
    from fr.ops.gate import _head_paths, valid_sha
    from fr.requirements import run_spec

    t = gate.target
    try:
        gate.host.fetch(gate.default, strict=True)  # a stale tip is never diffed (l-errors-r1)
    except Exception as exc:  # noqa: BLE001 — git's own words
        raise StageFailed(
            f"cannot fetch origin/{gate.default} to bring {t.ops_branch} up to date: {exc}",
            code=2,
        ) from exc
    _settle_pending_merge(gate, tree)
    # Pinned once (review p1-sec-r1): the diff, the question and the merge name ONE commit,
    # so a default branch that moves while the operator reads the question merges nothing new.
    tip = f"origin/{gate.default}"
    sha = valid_sha(gate.host.rev_parse(tip) or "", f"{tip}'s tip")
    ref = f"{tip} at {sha[:12]}"
    spec_rel = run_spec(t.run)
    paths = _head_paths(t, spec_rel or f"{KIND_DIRS['spec']}/")
    scratch = gate.host.materialise(sha, [*paths, *_runbook_rel(tree.path)])
    try:
        if (more := _runbook_rel(scratch)) and not (scratch / more[0]).is_file():
            # the default branch names a runbook the workspace does not (l-tests-r4)
            shutil.rmtree(scratch, ignore_errors=True)
            scratch = gate.host.materialise(sha, [*paths, *more])
        d = drift(tree.path, scratch, t.plan_rel, spec_rel)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if not d.differs:
        return
    if tree.is_ancestor(sha):  # merging it again changes nothing (review p1-r5)
        plan = ["the Test Plan"] if d.test_plan else []
        moved = ", ".join([*d.added, *d.removed, *d.changed, *plan])
        raise StageFailed(
            f"the ops workspace still differs from {gate.default} at {sha[:12]} after merging "
            f"it ({moved}); resolve by hand in {tree.path}, then re-run `fr ops gate`"
        )
    if not gate.prompt.confirm(_question(d, ref, t.ops_branch)):  # asked under --yes too (R2)
        raise StageFailed(f"bringing {t.ops_branch} up to date with {ref} declined; nothing done")
    try:
        tree.commit_paths(["docs"], f"chore(ops): {t.slug} records before merging {ref}")
    except Exception as exc:  # noqa: BLE001 — git's own words
        raise StageFailed(f"cannot commit the records on {t.ops_branch}: {exc}") from exc
    # Reopened before the merge, so a conflict merged by hand still re-applies them (R6).
    reopen = {*d.changed, *d.added}
    before = _entry_ids(tree, t.slug)
    if reopen:
        ops, _ = gate.state.reopened()
        gate.state.set_reopened(ops | reopen, before)
    back_to = 4 if reopen else 5 if d.test_plan else None  # stage 5 walks the Test Plan
    if back_to is not None and stage > back_to:
        gate.state.forget(back_to)
    else:
        back_to = None
    try:
        tree.merge_commit(sha, f"chore(ops): merge {ref} into {t.ops_branch}")
    except MergeConflict as exc:
        gate.state.set_pending_merge(sha)  # the hand merge brings in sha's entries (l-errors-r3)
        raise StageFailed(_merge_by_hand(gate, tree, sha, exc.paths)) from exc
    except Exception as exc:  # noqa: BLE001 — git's own words
        gate.state.set_pending_merge(sha)
        raise StageFailed(
            f"cannot merge {ref} into {t.ops_branch}: {exc}; if a merge is still in progress, "
            f"`git -C {tree.path} merge --abort`, then re-run `fr ops gate --run {t.run.run} --yes`"
        ) from exc
    if reopen:  # what the merge brought in is the default branch's, never recorded here
        ops, _ = gate.state.reopened()
        gate.state.set_reopened(ops, before | _entry_ids(tree, t.slug))
    try:
        gate.publish(tree)
    except Exception as exc:  # noqa: BLE001 — git's own words
        raise StageFailed(f"cannot push {t.ops_branch}: {exc}") from exc
    gate.say(f"{t.ops_branch} brought up to date with {ref}")
    gate.trust(tree)  # R4: the merged content, before any probe or apply
    if back_to == 4:
        raise Restart(f"ops reopened ({', '.join(sorted(reopen))}); back to stage 4")
    if back_to == 5:
        raise Restart("the Test Plan changed; back to stage 5")
