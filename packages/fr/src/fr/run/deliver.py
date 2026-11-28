"""The deliver gates: what `fr run resolve --step deliver` checks (spec 2026-11-27-run-verdict R5).

The cluster `fr/commands/run_cmd.py` used to hold between `_repo_relative` and
`_answered_by_or_exit`. A gate that stops `deliver` raises `RunRefusal` and a warning that does
not goes to the caller's `warn`; `run_cmd._resolve_body` runs them in its fixed order, each inside
`with _refusals():`, which prints the lines and exits as the gate did before it moved. A gate that
needs something still in `run_cmd` (a resume hint, the local-suite witness) takes it as a parameter.

Engine code: no `typer`, no `rich` beyond `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

from rich.markup import escape

from fr.artifacts.paths import artifact_root
from fr.run.historical import HISTORICAL_HEADING, historical_review_lines, historical_reviews
from fr.run.model import AnsweredBy, RunState
from fr.run.verdict import RunRefusal, Say, Warn
from fr.run.writes import note_record_write, now, remember
from fr.shape import shown_path

if TYPE_CHECKING:
    from fr.record.model import QuestionRounds

RECORD_ROWS: ContextVar[tuple[str, dict[str, str]] | None] = ContextVar(
    "fr_record_rows", default=None
)
"""gh#1456: the step record a resolve applies, by name, and the status its `acceptance:`
entries set per row — the record is applied before the gates read the fold, so a row it
sets wins over any fragment edit, and a refusal over that row has to say so."""

LocalWitness = Callable[[Path, str | None], "tuple[str, str] | str"]
"""`fr.run.evidence.suite.local_stamp_witness`: `(log, tree)` a `local` stamp records, or
why there is none."""


def repo_relative(repo_root: Path, value: str) -> str:
    """A `--emitted` path as repo-relative text (best effort, advisory use)."""
    try:
        root = repo_root.resolve()
        return str(Path(value).resolve().relative_to(root)) if Path(value).is_absolute() else value
    except OSError, ValueError:
        return value


def questions_from_flags(
    rounds: int | None, trigger: str | None, reason: str | None
) -> QuestionRounds | None:
    """The flag form of a record's `questions:` section — the SAME model, so
    both paths hand `gate_provenance` one value (spec 2026-09-26 §3.B)."""
    from pydantic import ValidationError

    from fr.record.model import QuestionRounds

    if rounds is None:
        if trigger is not None or reason is not None:
            raise RunRefusal(
                (
                    Say(
                        "--round-two-trigger/--round-two-reason describe a second round: pass "
                        "them with --question-rounds 2",
                        style="red",
                        markup=False,
                        soft_wrap=True,
                    ),
                ),
                2,
            )
        return None
    try:
        return QuestionRounds.model_validate(
            {"rounds": rounds, "trigger": trigger, "reason": reason}
        )
    except ValidationError as e:
        detail = "; ".join(str(err["msg"]) for err in e.errors())
        raise RunRefusal(
            (
                Say(
                    f"--question-rounds {rounds}: {detail}",
                    style="red",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            2,
        ) from e


def warn_ops_gap(repo_root: Path, state: RunState, warn: Warn) -> None:
    """Spec 2026-11-01-ops-gate-probes R3: the spec review resolved, so warn when the run
    has an ops gap — against its plan when it has one, else as steps that will need ops.
    Advisory: it never refuses, and an unreadable section, matrix, ops carrier or spec
    (an undecodable one is a `ValueError`, as `SectionError` is) is silent."""
    from fr.acceptance.model import AcceptanceError
    from fr.ops.gap import gap_message, ops_gap
    from fr.ops.load import OpsLoadError
    from fr.requirements import run_spec
    from fr.spec import TestPlanHeadingError
    from fr.verification.exit import run_exit, run_plan_dir

    spec_rel = run_spec(state)
    if spec_rel is None:
        return
    plan_dir = run_plan_dir(repo_root, state)
    try:
        gap = ops_gap(repo_root, spec_rel, plan_dir, run_exit(repo_root, state).gates)
    except TestPlanHeadingError as e:  # never silent: it hides every step (#1315)
        warn(Say(f"warning: {e}", markup=False, soft_wrap=True))
        return
    except ValueError, OSError, AcceptanceError, OpsLoadError:
        return
    if gap:
        message = gap_message(gap, has_plan=plan_dir is not None)
        warn(Say(f"warning: {message}", markup=False, soft_wrap=True))


def warn_label_sync(repo_root: Path, state: RunState, warn: Warn) -> None:
    """Exit-gates R7: a spec-bearing step resolved, so bring the run's PR labels to its
    exit (the PR is found by the run's branch). Advisory: a run with no PR yet is
    silent, any failure a warning — `deliver` is the one place the labels are required."""
    from fr.verification import labels as _labels

    try:
        outcome = _labels.sync_exit_labels(repo_root, state, None)
    except _labels.PrNotFound:
        return
    except Exception as e:  # noqa: BLE001 — advisory, after the step already resolved
        warn(Say(f"warning: PR labels not synced: {e}", markup=False, soft_wrap=True))
        return
    if outcome.warning:
        warn(Say(f"warning: {outcome.warning}", markup=False, soft_wrap=True))


def deliver_exit_guard(repo_root: Path, state: RunState) -> None:
    """Exit-gates R8: `deliver` refuses an exit lowered since the baseline that no
    operator-answered `exit-change-*` decision covers (a hand edit of the spec)."""
    from fr.verification.baseline import unaccounted_lowerings

    try:
        lowered = unaccounted_lowerings(repo_root, state)
    except Exception:  # noqa: BLE001 — an unreadable exit is the label sync's to report
        return
    if lowered:
        raise RunRefusal(
            (
                Say(
                    "refused: the spec's verification exit waits for less than when spec-review "
                    "resolved, and no operator-answered `fr verification set` covers it: "
                    + "; ".join(lowered)
                    + ". Restore it, or have the operator answer it with `fr verification set "
                    "... --answered-by operator`",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            2,
        )


def deliver_label_sync(
    repo_root: Path,
    state: RunState,
    pr: str | None,
    run_id: str,
    resume_hint: str,
    warn: Warn,
) -> None:
    """Exit-gates R7: `deliver` refuses a PR whose `verification:`/`gate:` labels it could
    not sync (printing the retry) — a failed write, no open PR, an unreadable exit — and
    only warns where there is no forge to ask or it cannot label a PR."""
    from fr.verification import labels as _labels

    def refuse(why: str) -> RunRefusal:
        line = Say(
            f"refused: could not sync the PR's verification/gate labels: {why}. Fix that, then "
            f"resolve again (`{resume_hint}`, with your --record "
            "if you resolve through one)",
            markup=False,
            soft_wrap=True,
        )
        return RunRefusal((line,), 2)

    try:
        outcome = _labels.sync_exit_labels(repo_root, state, pr)
    except _labels.ForgeUndeterminable as e:
        warn(Say(f"warning: PR labels not synced: {e}", markup=False, soft_wrap=True))
        return
    except _labels.LabelSyncError as e:
        raise refuse(str(e)) from e
    if outcome.unknown:
        raise refuse(outcome.warning or "the exit cannot be read")
    if outcome.warning:
        warn(Say(f"warning: {outcome.warning}", markup=False, soft_wrap=True))
    if outcome.off:
        warn(Say(f"PR labels not synced: {outcome.off}", markup=False, soft_wrap=True))


def same_pr(recorded: str, pr: str) -> bool:
    """*pr* (a url, `#n` or `n`) names the PR whose url the cursor recorded."""
    if pr == recorded:
        return True
    number = pr.removeprefix("#")
    return number.isdigit() and recorded.rstrip("/").rsplit("/", 1)[-1] == number


def deliver_pr_ask_gate(repo_root: Path, state: RunState, pr: str | None) -> None:
    """Under `git.pr: ask` (spec 2026-11-04-repo-feature-settings R12), `deliver`
    accepts only the PR `fr pr create` opened: the one the cursor recorded."""
    from fr.settings import load_settings

    if load_settings(repo_root).settings.git.pr != "ask":
        return
    if state.pr is None:
        raise RunRefusal(
            (
                Say(
                    "refused: under `git.pr: ask` deliver accepts only a PR `fr pr create` opened, "
                    "and this run's cursor records none. Open it with `fr pr create --title <t> "
                    "--body-file <f>` (it asks the operator first), then resolve again",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            2,
        )
    if pr is not None and not same_pr(state.pr, pr):
        raise RunRefusal(
            (
                Say(
                    f"refused: under `git.pr: ask` deliver accepts only the PR `fr pr create` "
                    f"opened ({state.pr}), not {pr}",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            2,
        )


def deliver_pr_gate(repo_root: Path, state: RunState, pr: str | None, warn: Warn) -> None:
    """Render the PR body fr owns, then refuse `deliver` until the LIVE PR
    carries every required section (spec 2026-09-25 §5.C.4). The render is
    the one file a refusal leaves behind: it is what the agent opens the PR
    with. On success the render is removed — it goes with the delivered step.

    Under `forge.pr_body: minimal` (spec 2026-11-04-repo-feature-settings R10) the
    live PR stays a plain summary: the render is kept durable at
    `runs/<run-id>.pr-body.md` (committed with this resolve, never removed), the live
    body is not asked for fr's sections but is refused any fr marker, and the
    closing-keyword checks hold either way.
    """
    from fr.artifacts.atomic import write_text_atomic
    from fr.hostclient import FORGE_ERRORS, client_for, pr_command
    from fr.record.model import records_dir
    from fr.record.pr_body import (
        PR_BODY_NAME,
        REQUIRED_SECTIONS,
        PrBodyRefused,
        durable_pr_body_path,
        fr_markers,
        missing_sections,
        render_pr_body,
        shared_closing_keywords,
    )
    from fr.settings import load_settings
    from fr.shape import deliver_shape_refusal

    if (shape := deliver_shape_refusal(repo_root, state)) is not None:  # show-me-visuals R11
        raise RunRefusal((Say(f"refused: {shape}", markup=False, soft_wrap=True),), 2)
    deliver_pr_ask_gate(repo_root, state, pr)
    pr = pr or state.pr
    minimal = load_settings(repo_root).settings.forge.pr_body == "minimal"
    if minimal:
        body_path = durable_pr_body_path(repo_root, state.run)
    else:
        body_path = records_dir(repo_root, state.run) / PR_BODY_NAME
    body_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        write_text_atomic(body_path, render_pr_body(repo_root, state))
    except PrBodyRefused as e:  # l-errors-r8
        raise RunRefusal((Say(f"refused: {e}", markup=False, soft_wrap=True),), 2) from e
    # Under quiet and stealth the render is under the artifact root, outside the checkout:
    # named by its full path there (lens-pr-body-quiet), committed by the same seam.
    rel = shown_path(body_path, repo_root)
    ref = pr or state.branch
    # Through the forge adapter, never `fr.gh`: on GitLab/Gitea `gh` cannot
    # read the PR, and a gate that cannot read it never passes (gh#742).
    try:
        live = client_for(repo_root).pr_body(ref, cwd=repo_root)
    except FORGE_ERRORS as e:
        # R12: fr's skills open every PR through `fr pr create` (always a draft).
        create = f"fr pr create --title <title> --body-file {rel}"
        raise RunRefusal(
            (
                Say(
                    f"refused: cannot read the PR {ref!r} ({e}). fr rendered its body to {rel}: "
                    f"open the PR with `{create}`, record its url (`emitted: "
                    "{pr: <url>}` in the record, or `--emitted pr=<url>`), and resolve again",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            2,
        ) from e
    refuse_unclosed_owed(repo_root, state, live, ref, rel)
    if minimal:
        markers = fr_markers(live)
        if markers:
            edit = pr_command(repo_root, "edit", ref=ref, body="<plain summary file>")
            raise RunRefusal(
                (
                    Say(
                        "refused: under `forge.pr_body: minimal` the live PR carries no fr marker, "
                        f"and it has: {'; '.join(markers)}. Replace the body with a plain summary "
                        f"(`{edit}`); the full render stays at {rel} — and resolve again",
                        markup=False,
                        soft_wrap=True,
                    ),
                ),
                2,
            )
        missing: list[str] = []
    else:
        required = (
            (*REQUIRED_SECTIONS, HISTORICAL_HEADING)
            if historical_reviews(state)
            else REQUIRED_SECTIONS
        )
        missing = missing_sections(live, required=required)
        # Review p2-r1: the heading alone is not the control — the operator's ok
        # is given against the LIST, so every historical review must be named.
        live_lines = {line.strip() for line in live.splitlines()}
        missing += [line for line in historical_review_lines(state) if line not in live_lines]
    if missing:
        edit = pr_command(repo_root, "edit", ref=ref, body=rel)
        raise RunRefusal(
            (
                Say(
                    f"refused: the PR body lacks required section(s): {', '.join(missing)}. Update "
                    f"it from fr's render — `{edit}` — and resolve again",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            2,
        )
    # gh#821: one keyword closes one reference, so `Closes #a and #b` would
    # leave #b open after its fix merges. Checked on the body already read.
    shared = shared_closing_keywords(live)
    if shared:
        fixes = "\n".join(
            f"  {bad!r} — write instead:\n" + "\n".join(f"    {f}" for f in fixed)
            for bad, fixed in shared
        )
        raise RunRefusal(
            (
                Say(
                    "refused: the PR body shares one closing keyword across several issues, "
                    "and only the first would close on merge. Give each reference its own "
                    "keyword, one per line (move a non-closing mention to a line with no "
                    f"keyword), then resolve again:\n{fixes}",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            2,
        )
    refuse_premature_closes(repo_root, state, live)
    if minimal:
        # Kept, and committed with this resolve: it is what the operator reviews.
        note_record_write(repo_root, body_path)
        warn(
            Say(
                f"PR body (forge.pr_body: minimal): review the full render at {rel} — its "
                "findings, owed rows and historical-review list; the live PR stays plain",
                markup=False,
                soft_wrap=True,
            )
        )
        return
    from fr.record.apply import _is_tracked

    tracked = _is_tracked(repo_root, body_path)
    remember(body_path)
    body_path.unlink()
    if tracked:
        note_record_write(repo_root, body_path)


def refuse_unclosed_owed(repo_root: Path, state: RunState, live: str, ref: str, rel: str) -> None:
    """Owed-archive R4: every issue `## Owed actions discharged` lists as `Closes`
    must be closed by the live body — any closing keyword, read as a merge reads
    it (`closing_refs(as_github=True)`) — under `forge.pr_body: full` and `minimal`
    alike. A held one (rendered `Refs`, R5) is not asked for. Under quiet and
    stealth (R15) the discharge never travels with the PR and resolve closed the
    issue at once, so nothing is asked. What cannot be read — the discharges
    (review p2-r2) or the holds (p2-r5) — refuses, naming it."""
    from fr.acceptance.model import AcceptanceError
    from fr.hostclient import pr_command
    from fr.owed_refs import discharge_travels
    from fr.record import pr_body

    if not discharge_travels(repo_root):
        return
    try:
        items = pr_body.discharged_owed(repo_root)
    except pr_body.UnreadableDischargeError as e:
        raise RunRefusal(
            (
                Say(
                    f"refused: cannot tell which owed actions this branch discharged — {e}. "
                    "Their issues must close when this PR merges; fix that, then resolve again",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            2,
        ) from e
    if not items:
        return
    try:
        held = pr_body.run_held_issues(repo_root, state)
    except (AcceptanceError, pr_body.UnreadableJournalError) as e:
        raise RunRefusal(
            (
                Say(
                    "refused: cannot tell whether a discharged owed issue is held open (the "
                    f"acceptance matrix or a run journal does not read: {e}); fix it, then resolve "
                    "again",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            2,
        ) from e
    from fr._hosts import origin_hostname

    owner, _, rest = items[0].ref.partition("/")
    identity = (owner, rest.partition("#")[0])
    host = origin_hostname(repo_root) or ""  # super-fr#1488: a URL closes only on the forge
    closed = {
        pr_body.normalize_issue_ref(written, identity, host=host)
        for _line, _keyword, written in pr_body.closing_refs(live, as_github=True)
    }
    missing = [i.ref for i in items if i.ref.lower() not in held and i.ref.lower() not in closed]
    if not missing:
        return
    edit = pr_command(repo_root, "edit", ref=ref, body=rel)
    lines = "\n".join(f"  Closes {m}" for m in missing)
    raise RunRefusal(
        (
            Say(
                "refused: this branch discharges owed action(s) whose issue the PR body does not "
                f"close on merge. Add each line to the body (`{edit}`, or by hand under "
                f"`forge.pr_body: minimal`), then resolve again:\n{lines}",
                markup=False,
                soft_wrap=True,
            ),
        ),
        2,
    )


def refuse_premature_closes(repo_root: Path, state: RunState, live: str) -> None:
    """R15: a live PR body that closes, fixes or resolves an issue a post-merge,
    not-walk-verified row cites would close it on merge, before the promise it
    carries has been verified. Printed with the `Refs <ref>` that mentions it
    without closing; exit 2. Exit-gates R11 widens it: a row gated by a post-merge
    gate holds its issues too, and so does a narrowing decision the operator did
    not answer. A repo whose matrix cites no issue and whose journals narrow none
    is never asked (the reference's repo identity needs a remote or matrix keys)."""
    from fr.acceptance.check import resolve_identity
    from fr.acceptance.fold import has_fragments, load_effective
    from fr.acceptance.model import AcceptanceError
    from fr.record.pr_body import (
        PrematureClose,
        holds_open_for_run,
        premature_closes,
        run_narrowings,
    )
    from fr.requirements import load_spec_matrix, run_spec
    from fr.verification.exit import run_exit

    narrowings = gate_journals(lambda: run_narrowings(repo_root, state))
    try:
        matrix = load_effective(repo_root)
        if not any(row.issues for row in matrix.rows) and not narrowings:
            return
        identity = resolve_identity(matrix, repo_root)
        spec_rel = run_spec(state)
        spec_ref = (
            load_spec_matrix(repo_root, spec_rel)[1]
            if spec_rel is not None and has_fragments(repo_root)
            else None
        )
    except AcceptanceError as e:
        raise RunRefusal(
            (
                Say(
                    f"[red]refused: cannot check the PR body's closing keywords against the "
                    f"acceptance matrix — {escape(str(e))}[/red]",
                    soft_wrap=True,
                ),
            ),
            2,
        ) from e
    try:
        exit_ = run_exit(repo_root, state)
    except Exception:  # noqa: BLE001 — an unreadable exit is the label sync's to refuse
        exit_ = None
    found = premature_closes(
        live,
        matrix,
        identity,
        holds_open_for_run(repo_root, state, matrix, spec_ref),
        exit=exit_,
        narrowings=narrowings,
    )
    if not found:
        return

    def why(p: PrematureClose) -> str:
        held = []
        if p.rows:
            held.append(
                f"row {', '.join(p.rows)} still holds open (post-merge or gated by a "
                "post-merge gate, and not yet walk-verified)"
            )
        if p.decisions:
            held.append(
                f"decision {', '.join(p.decisions)} narrows it and the operator did not "
                "answer it (`decided_by=operator`)"
            )
        if p.tracks:
            held.append(
                f"owed row {', '.join(p.tracks)} names it as the issue tracking what it still owes"
            )
        return " and ".join(held)

    lines = "\n".join(
        f"  {p.line!r} closes {p.ref}, which {why(p)} — write instead: {p.fix}" for p in found
    )
    raise RunRefusal(
        (
            Say(
                "refused: the PR body closes an issue whose promise is not verified until after "
                "merge, or that a decision narrowed. Mention it without closing (`Refs <ref>`); "
                "the close command is printed when the walk is recorded (`fr acceptance "
                f"set-status --walk`):\n{lines}",
                markup=False,
                soft_wrap=True,
            ),
        ),
        2,
    )


def gate_journals[T_JOURNALS](read: Callable[[], T_JOURNALS]) -> T_JOURNALS:
    """Run a `deliver` gate's journal read; a journal that does not parse
    refuses, naming it (review p3-r4) — never a gate judging a run with one
    of its journals silently dropped."""
    from fr.record.pr_body import UnreadableJournalError

    try:
        return read()
    except UnreadableJournalError as e:
        raise RunRefusal(
            (
                Say(
                    f"refused: {e}. Fix the journal (a hand edit, most likely), then resolve again",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            2,
        ) from e


def deliver_placement_gate(repo_root: Path) -> None:
    """Spec 2026-11-04 R28: `deliver` refuses a branch whose artifacts do not match the
    repo's placement, naming `fr placement migrate-branch`; it never migrates."""
    from fr.placement.drift import DriftError, refuse

    try:
        refuse(repo_root, "deliver")
    except DriftError as e:
        raise RunRefusal((Say(f"refused: {e}", markup=False, soft_wrap=True),), 2) from e


def deliver_acceptance_gate(repo_root: Path, warn: Warn) -> None:
    """Spec 2026-11-04 R16, R17: `deliver` fetches the default ref and refuses a
    branch amendment whose base is stale, and an in-place edit of a merged row —
    the same refusals `fr acceptance check` prints, from the one function."""
    from fr.acceptance.amend import branch_refusals
    from fr.settings import SettingsError, disabled

    try:
        if disabled(repo_root, "acceptance"):
            return
    except SettingsError:
        pass  # the settings' own gates refuse an unreadable file
    found = branch_refusals(repo_root)
    for w in found.warnings:
        warn(Say(f"warning: {w}", markup=False, soft_wrap=True))
    problems = [*found.errors, *found.stale]
    if not problems:
        return
    lines = "\n".join(f"  {p}" for p in problems)
    raise RunRefusal(
        (
            Say(
                f"refused: the branch's acceptance amendments cannot merge as they stand:\n{lines}",
                markup=False,
                soft_wrap=True,
            ),
        ),
        2,
    )


def deliver_leftovers_gate(repo_root: Path, state: RunState) -> None:
    """Exit-gates R9: `deliver` refuses while the run leaves anything unaccounted
    — an out-of-scope finding, an owed entry, an owed row citing the spec, a
    narrowing decision — printing each with the command that accounts for it.
    An unreadable exit judges no row here; the label sync refuses it."""
    from fr.record.pr_body import unaccounted
    from fr.verification.exit import run_exit

    try:
        exit_ = run_exit(repo_root, state)
    except Exception:  # noqa: BLE001 — the label sync refuses an unreadable exit
        exit_ = None
    leftovers = gate_journals(lambda: unaccounted(repo_root, state, exit_))
    if not leftovers:
        return
    held = RECORD_ROWS.get()
    if held is not None:
        import dataclasses

        name, statuses = held
        leftovers = [
            dataclasses.replace(
                left,
                fix=(
                    f"the record {name} sets this row {statuses[left.id]}, and the record "
                    "wins over the fragment: change or drop its `acceptance:` entry for "
                    f"{left.id} first. Then: {left.fix}"
                ),
            )
            if left.kind == "row" and left.id in statuses
            else left
            for left in leftovers
        ]
    lines = "\n".join(f"  {left.line()}" for left in leftovers)
    raise RunRefusal(
        (
            Say(
                "refused: the run leaves work unaccounted for. File each leftover, gate it, or "
                f"track it, then resolve again:\n{lines}",
                markup=False,
                soft_wrap=True,
            ),
        ),
        2,
    )


@dataclass(frozen=True)
class LocalStamps:
    """The feature's fragments (gh#1456: one per spelling of its slug) with every `local`
    stamp `deliver` owes written in, built in
    memory by `deliver_local_stamp_plan` and written by `deliver_local_stamp_write`."""

    files: tuple[tuple[Path, str], ...]
    rows: tuple[str, ...]


def deliver_local_stamp_plan(
    repo_root: Path, state: RunState, tests: str | None, witness: LocalWitness
) -> LocalStamps | None:
    """Spec 2026-11-14-acceptance-local-status R4, §D: the stamps for the `local` rows
    this run's feature added or set `local`, checked with `deliver`'s other refusals —
    exit 2 naming each row that cannot be stamped. Writes nothing."""
    from fr.acceptance.fragment import fragment_slug_for_spec
    from fr.requirements import run_spec

    spec = run_spec(state)
    if spec is None:
        return None
    return local_stamp_plan(
        repo_root, fragment_slug_for_spec(spec), tests, today=now()[:10], witness=witness
    )


def feature_local_ids(fragment: Any) -> list[str]:
    """The rows *fragment* (one feature's) sets `local`: the rows whose latest `set-status`
    amendment in it is to `local` — its own merged rows included, which change only by
    amendment (gh#1462) — and its own rows at `local` that no amendment in it re-sets."""
    latest: dict[str, str] = {}
    for a in fragment.amendments:
        if a.op == "set-status":
            latest[a.row] = a.status
    return [r.id for r in fragment.rows if r.status == "local" and r.id not in latest] + [
        rid for rid, status in latest.items() if status == "local"
    ]


LOCAL_STAMP_WHY = "deliver stamps the local suite run that covers this row (R4)"
"""The `why` of the amendment `deliver` writes to stamp a merged `local` row."""


def local_stamp_plan(
    repo_root: Path, feature: str, tests: str | None, *, today: str, witness: LocalWitness
) -> LocalStamps | None:
    """`deliver_local_stamp_plan` for *feature*'s fragment, read where the placement
    keeps it (the artifact root); the blobs come from the product checkout's HEAD."""
    from fr.acceptance.edit import append_amendment, local_stamp_target, stamp_local
    from fr.acceptance.fold import effective, merged_row_ids
    from fr.acceptance.fragment import FRAGMENTS_DIR, SetStatus, parse_fragment
    from fr.acceptance.local import head_blobs, level_ref_paths
    from fr.acceptance.model import AcceptanceError, LocalStamp, Row
    from fr.settings import SettingsError, disabled

    try:
        if disabled(repo_root, "acceptance"):
            return None
    except SettingsError:
        pass  # the settings' own gates refuse an unreadable file

    def refuse(lines: list[str]) -> NoReturn:
        shown = "\n".join(f"  {line}" for line in lines)
        raise RunRefusal(
            (
                Say(
                    "refused: deliver cannot stamp this feature's `local` rows (each needs a "
                    f"stamp of the suite run that covers it):\n{shown}",
                    markup=False,
                    soft_wrap=True,
                ),
            ),
            2,
        )

    # gh#1456: a fragment created before #1451 gave a spec slug one spelling may still be
    # named `<slug>-design.yaml`. The fold reads it either way, so deliver reads it either
    # way: a lookup that missed it passed deliver with its `local` rows unstamped.
    folder = artifact_root(repo_root) / FRAGMENTS_DIR
    texts: dict[Path, str] = {}
    wanted: dict[Path, list[str]] = {}
    own_rows: set[str] = set()
    for path in (folder / f"{feature}.yaml", folder / f"{feature}-design.yaml"):
        if not path.is_file():
            continue
        texts[path] = path.read_text(encoding="utf-8")
        try:
            fragment = parse_fragment(texts[path], source=path.name)
        except AcceptanceError as e:
            refuse([f"{path.name}: {e}"])
        own_rows |= {r.id for r in fragment.rows}
        ids = feature_local_ids(fragment)
        if ids:
            wanted[path] = ids
    if not wanted:
        return None  # review p2-r1: no `local` row, no fold, deliver as before
    try:
        current = effective(repo_root)
    except AcceptanceError as e:
        refuse([f"the acceptance matrix: {e}"])
    rows = {r.id: r for r in current.matrix.rows}
    merged: frozenset[str] | None = None

    def frozen(target: Row | SetStatus) -> bool:
        """gh#1462: is the block a stamp would land in history — a row merged on the
        default ref, or a set-status amendment that is not this branch's own? Such a
        block is never rewritten: the stamp goes in a new amendment."""
        nonlocal merged
        if isinstance(target, SetStatus):
            return target not in current.pending
        if merged is None:
            try:
                merged = merged_row_ids(repo_root, frozenset(own_rows), current=current)
            except AcceptanceError as e:
                refuse([f"the merged acceptance rows: {e}"])
        return target.id in merged

    by_path = {
        path: [
            r
            for r in (rows[rid] for rid in dict.fromkeys(ids) if rid in rows)
            if r.status == "local"
        ]
        for path, ids in wanted.items()
    }
    local = [r for rs in by_path.values() for r in rs]
    if not local:
        return None
    stamped = witness(repo_root, tests)
    if isinstance(stamped, str):
        refuse([f"row {r.id}: {stamped}" for r in local])
    log, tree = stamped
    blobs = head_blobs(repo_root, (p for r in local for p in level_ref_paths(r)))
    if blobs is None:
        refuse([f"row {r.id}: git cannot read HEAD of {repo_root}" for r in local])
    problems: list[str] = []
    files: list[tuple[Path, str]] = []
    for path, path_rows in by_path.items():
        text = texts[path]
        for r in path_rows:
            paths = level_ref_paths(r)
            missing = [p for p in paths if p not in blobs]
            if not paths:
                problems.append(f"row {r.id}: names no test path (add `--level unit=...`)")
                continue
            if missing:
                problems.append(f"row {r.id}: {missing[0]} is not committed at HEAD")
                continue
            stamp = LocalStamp(at=today, tree=tree, log=log, files={p: blobs[p] for p in paths})
            try:
                if frozen(local_stamp_target(text, r.id)):
                    amendment = SetStatus(
                        row=r.id,
                        op="set-status",
                        base=current.revisions.get(r.id, 0),
                        status="local",
                        notes=r.notes,
                        local=stamp,
                        why=LOCAL_STAMP_WHY,
                    )
                    text = append_amendment(text, amendment)
                else:
                    text = stamp_local(text, r.id, stamp)
            except AcceptanceError as e:
                problems.append(f"row {r.id}: {e}")
        if path_rows:
            files.append((path, text))
    if problems:
        refuse(problems)
    return LocalStamps(tuple(files), tuple(r.id for r in local))


def deliver_local_stamp_write(repo_root: Path, plan: LocalStamps | None) -> None:
    """Write `deliver_local_stamp_plan`'s fragment — called beside
    `flush_gate_decisions`, after `deliver`'s last refusal, so a refused resolve
    writes no stamp; remembered for a `--record` restore and committed with the
    resolve (in the artifact root's checkout under quiet or stealth)."""
    if plan is None:
        return
    from fr.artifacts.atomic import write_text_atomic

    for path, text in plan.files:
        remember(path)
        write_text_atomic(path, text)
        note_record_write(repo_root, path)


def narrow_answered_by(value: str | None) -> AnsweredBy | None:
    """Narrow an `answered_by` string where it ENTERS fr — the flag, or a
    record's evidence key — to the closed set (spec §F). Refused rather than
    coerced: a typo recorded as a third provenance would be read by nobody and
    would quietly weaken the one claim this field exists to make."""
    if value is None:
        return None
    if value == "operator":
        return "operator"
    if value == "agent":
        return "agent"
    raise RunRefusal(
        (Say(f"[red]--answered-by must be 'operator' or 'agent', got {value!r}[/red]"),), 2
    )
