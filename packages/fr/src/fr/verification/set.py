"""`fr verification set` — change a spec's `## Verification` section and keep the
exit honest about it (spec 2026-10-14 exit-gates R8, §B).

One engine function over `spec_section.rewrite_section`: rewrite one grammar line,
compare the run's exit before and after, and — once the spec-reviewing step is done —
refuse a change that makes the exit wait less unless a verified operator answered it.
The decision (with a parseable block `deliver` reads back), the commit and the caller's
label re-sync follow.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path

from fr.verification.baseline import (
    Lowering,
    change_block,
    review_record,
    spec_entries,
    weakened,
)
from fr.verification.exit import Exit

__all__ = ["SetRefusedError", "SetResult", "exit_change", "weakened"]


class SetRefusedError(Exception):
    """The change was refused; the spec and the journal are as they were."""


@dataclass(frozen=True)
class SetResult:
    spec_rel: str
    decision_id: str | None
    """`None` when the change was a no-op (nothing written, nothing journalled)."""
    notices: tuple[str, ...]
    weakened: tuple[str, ...]


def _decision_number(entries: list) -> int:  # type: ignore[type-arg]
    nums = [
        int(e.id.rsplit("-", 1)[1])
        for e in entries
        if e.kind == "decision" and e.id.startswith("exit-change-") and e.id[12:].isdigit()
    ]
    return max(nums, default=0) + 1


def _window_start(entries: list, review_at: str | None) -> str | None:  # type: ignore[type-arg]
    """The later of the review's `at` and the latest `exit-change-*` decision's stamp:
    an operator answer from before either answered something else (p2-r4)."""
    from fr.journal.model import journal_stamp_as_utc

    stamps = [review_at] if review_at else []
    stamps += [e.created for e in entries if e.id.startswith("exit-change-") and e.created]
    parsed: list[tuple[_dt.datetime, str]] = []
    for raw in stamps:
        utc = journal_stamp_as_utc(raw)
        try:
            parsed.append((_dt.datetime.fromisoformat(utc), utc))
        except ValueError:
            continue
    return max(parsed)[1] if parsed else None


def exit_change(
    repo_root: Path,
    run_id: str,
    *,
    row: str | None,
    strategy: str | None,
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
    from fr.verification.model import RESERVED, StrategyError
    from fr.verification.resolve import resolve_strategy
    from fr.verification.spec_section import SectionError, rewrite_section

    if strategy is None and gate is None:
        raise SetRefusedError("give --strategy, --gate, or both")
    if strategy is not None and strategy != RESERVED:
        try:
            resolve_strategy(strategy, repo_root)
        except StrategyError as e:
            raise SetRefusedError(f"`{strategy}` is not a strategy: {e}") from e
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
    if new_text == original:
        return SetResult(spec_rel, None, (), ())

    def restore() -> None:
        write_text_atomic(spec, original)

    write_text_atomic(spec, new_text)
    try:
        after = run_exit(repo_root, state)
        if after.remap_problem:
            raise SetRefusedError(f"the exit is not known after the change: {after.remap_problem}")
        lowered: list[Lowering] = []
        notices: list[str] = []
        entries = spec_entries(repo_root, spec_rel)
        review = review_record(repo_root, state)
        advisory: str | None = None
        if review is not None:
            lowered = weakened(before, after, repo_root)
            if lowered and answered_by != "operator":
                raise SetRefusedError(
                    "spec-review is done and this makes the exit wait less ("
                    + "; ".join(x.text for x in lowered)
                    + "): only the operator may lower it — ask them, then pass "
                    "`--answered-by operator`"
                )
            if lowered:
                since = _window_start(entries, review.at)
                try:
                    advisory = verify_operator_answer("exit-change", since, since)
                except OperatorClaimRefusedError as e:
                    raise SetRefusedError(str(e)) from e
                if advisory:
                    notices.append(advisory)
        slug = spec_journal_slug(Path(spec_rel).stem)
        decision_id = f"exit-change-{_decision_number(entries)}"
        target = f"row {row}" if row else "the run"
        what = ", ".join(
            x
            for x in (f"strategy {strategy}" if strategy else "", f"gate {gate}" if gate else "")
            if x
        )
        body = f"{reason}\n\nbefore: {_describe(before)}\nafter: {_describe(after)}"
        if lowered:
            body += "\nlowered with an operator answer: " + "; ".join(x.text for x in lowered)
        if advisory:
            body += f"\nUNVERIFIED: {advisory}"
        body += "\n\n" + change_block(answered_by=answered_by, lowered=lowered)
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
    return SetResult(spec_rel, decision_id, tuple(notices), tuple(x.text for x in lowered))


def _describe(ex: Exit) -> str:
    return f"kinds {sorted(ex.kinds)}, gates {sorted(ex.gates) or ['none']}"
