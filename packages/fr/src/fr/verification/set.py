"""`fr verification set` — change a spec's `## Verification` section and keep the
exit honest about it (spec 2026-10-14 exit-gates R8, §B).

One engine function over `spec_section.rewrite_section`: rewrite one grammar line,
compare the run's exit before and after, and — once `spec-review` is done — refuse a
change that makes the exit wait less unless a verified operator answered it. The
decision, the commit and the label re-sync follow.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fr.gates import POST_MERGE_GATES
from fr.verification.exit import Exit, kind_rank

__all__ = ["SetRefusedError", "SetResult", "exit_change", "weakened"]


class SetRefusedError(Exception):
    """The change was refused; the spec and the journal are as they were."""


@dataclass(frozen=True)
class SetResult:
    spec_rel: str
    decision_id: str
    notices: tuple[str, ...]
    weakened: tuple[str, ...]


def weakened(before: Exit, after: Exit, repo_root: Path) -> list[str]:
    """What `after` waits for less than `before` (R8): the run, and each row, on its
    own — a post-merge gate that is gone, or a kind of lower rank. The exit's overall
    rank would hide a row lowered beside one that still holds the maximum."""
    out: list[str] = []

    def lowered(label: str, kind_b: str, kind_a: str, gate_b: str, gate_a: str) -> None:
        if gate_b in POST_MERGE_GATES and gate_a not in POST_MERGE_GATES:
            out.append(f"{label}: the `{gate_b}` gate is gone (now `{gate_a}`)")
        if kind_rank(kind_a, repo_root) < kind_rank(kind_b, repo_root):
            out.append(f"{label}: kind `{kind_b}` -> `{kind_a}` waits for less")

    lowered("the run", before.run_kind, after.run_kind, before.run_gate, after.run_gate)
    for rid, kind_b in before.row_kinds.items():
        lowered(
            f"row {rid}",
            kind_b,
            after.row_kinds.get(rid, "none"),
            before.row_gates.get(rid, "none"),
            after.row_gates.get(rid, "none"),
        )
    return out


def _decision_number(repo_root: Path, slug: str) -> int:
    from fr.journal.model import journal_path, parse_journal

    path = journal_path(repo_root, "spec", slug)
    taken = [
        e.id
        for e in (parse_journal(path.read_text()) if path.is_file() else [])
        if e.kind == "decision"
    ]
    nums = [
        int(i.rsplit("-", 1)[1]) for i in taken if i.startswith("exit-change-") and i[12:].isdigit()
    ]
    return max(nums, default=0) + 1


def exit_change(
    repo_root: Path,
    run_id: str,
    *,
    row: str | None,
    strategy: str,
    gate: str | None,
    reason: str,
    answered_by: str | None,
) -> SetResult:
    """Apply the change; `SetRefusedError` (nothing changed) when it cannot be."""
    from fr.acceptance.model import AcceptanceError
    from fr.artifacts.atomic import write_text_atomic
    from fr.journal.model import spec_journal_slug
    from fr.journal.operator import OperatorClaimRefusedError, verify_operator_answer
    from fr.record import apply as engine
    from fr.record.model import JournalItem, StepRecord
    from fr.records_commit import commit_records
    from fr.requirements import run_spec
    from fr.run.model import RunStateError, load_run_state
    from fr.verification.exit import run_exit
    from fr.verification.spec_section import SectionError, rewrite_section

    try:
        state = load_run_state(repo_root, run_id)
    except RunStateError as e:
        raise SetRefusedError(str(e)) from e
    spec_rel = run_spec(state)
    if spec_rel is None:
        raise SetRefusedError(f"run {run_id!r} has not emitted a spec yet")
    spec = repo_root / spec_rel
    if not spec.is_file():
        raise SetRefusedError(f"{spec_rel} is not in the working tree (archived?)")
    original = spec.read_text()
    try:
        new_text = rewrite_section(
            original, strategy=strategy, row=row, gate=gate, reason=reason if row else None
        )
        before = run_exit(repo_root, state)
    except (SectionError, AcceptanceError, OSError) as e:
        raise SetRefusedError(str(e)) from e
    if before.remap_problem:
        raise SetRefusedError(f"the exit is not known while {before.remap_problem}")
    if row is not None and row not in {r.id for r in before.rows}:
        raise SetRefusedError(f"no acceptance row `{row}` cites {spec_rel}")

    def restore() -> None:
        write_text_atomic(spec, original)

    write_text_atomic(spec, new_text)
    try:
        after = run_exit(repo_root, state)
        if after.remap_problem:
            raise SetRefusedError(f"the exit is not known after the change: {after.remap_problem}")
        lowered: list[str] = []
        notices: list[str] = []
        review = state.steps.get("spec-review")
        if review is not None and review.state == "done":
            lowered = weakened(before, after, repo_root)
            if lowered and answered_by != "operator":
                raise SetRefusedError(
                    "spec-review is done and this makes the exit wait less ("
                    + "; ".join(lowered)
                    + "): only the operator may lower it — ask them, then pass "
                    "`--answered-by operator`"
                )
            if lowered:
                since = review.at
                try:
                    advisory = verify_operator_answer(
                        "exit-change", since, _utc(since) if since else None
                    )
                except OperatorClaimRefusedError as e:
                    raise SetRefusedError(str(e)) from e
                if advisory:
                    notices.append(advisory)
        slug = spec_journal_slug(Path(spec_rel).stem)
        number = _decision_number(repo_root, slug)
        decision_id = f"exit-change-{number}"
        target = f"row {row}" if row else "the run"
        what = f"strategy {strategy}" + (f", gate {gate}" if gate else "")
        body = f"{reason}\n\nbefore: {_describe(before)}\nafter: {_describe(after)}"
        if lowered:
            body += "\nanswered_by: operator (lowered: " + "; ".join(lowered) + ")"
        try:
            engine.apply_record(
                repo_root,
                None,
                StepRecord(
                    journal=(
                        JournalItem.model_validate(
                            {
                                "kind": "decision",
                                "id": decision_id,
                                "title": f"exit change: {target} -> {what}",
                                "body": body,
                            }
                        ),
                    )
                ),
                target=engine.RecordTarget(
                    journal_scope="spec",
                    journal_slug=slug,
                    message=f"chore(fr): verification set — {decision_id} ({spec_rel})",
                ),
            )
        except engine.RecordRefusedError as e:
            raise SetRefusedError(str(e)) from e
    except BaseException:
        restore()
        raise
    outcome = commit_records(
        repo_root, [spec], f"chore(fr): verification set — {decision_id}: {target} -> {what}"
    )
    if not (outcome.committed or outcome.unchanged):
        notices.append(f"the spec change is written but NOT committed: {outcome.reason}")
    return SetResult(spec_rel, decision_id, tuple(notices), tuple(lowered))


def _utc(stamp: str) -> str:
    from fr.journal.model import journal_stamp_as_utc

    return journal_stamp_as_utc(stamp)


def _describe(ex: Exit) -> str:
    return f"kinds {sorted(ex.kinds)}, gates {sorted(ex.gates) or ['none']}"
