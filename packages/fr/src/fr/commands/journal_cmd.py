"""`fr journal ...` CLI — the scope-keyed durable run-state primitive.

Spec: docs/superpowers/specs/2026-07-22-fr-goal-subagent-execution-design.md §A.

Verbs:
  - ``add``     append one entry (create-only; duplicate ``--id`` is refused).
  - ``resolve`` append a RESOLUTION RECORD closing a finding (spec §3.G.1) —
                never a rewrite of the finding, which would erase that it was
                ever open.
  - ``render``  emit the Markdown a PR body embeds (fail-open on missing/bad file).
  - ``check``   freshness gate: non-zero on open findings or a parse error
                (fail-closed), so a stale journal cannot ride into a PR silently.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import get_args

import typer
from rich.console import Console

from fr.commands.common import resolve_repo_root
from fr.journal.model import (
    TRACKED_BY_RE,
    EffectiveFindingState,
    JournalEntry,
    JournalParseError,
    append_journal_entry,
    effective_finding_states,
    journal_path,
    journal_stamp_as_utc,
    open_finding_ids,
    parse_journal,
    resolve_journal_read_path,
    serialize_entry,
    unauthorized_fixes,
)
from fr.records_commit import commit_records
from fr.run.model import AnsweredBy

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

journal_app = typer.Typer(
    help="Scope-keyed durable run-state (spec|plan|debug): add / render / check.",
    no_args_is_help=True,
)


def _timestamp() -> str:
    """Wall-clock ISO stamp. Isolated so tests could monkeypatch if needed."""
    import datetime as _dt

    return _dt.datetime.now().replace(microsecond=0).isoformat()


def _load(path: Path) -> list[JournalEntry]:
    if not path.exists():
        return []
    return parse_journal(path.read_text())


def _validate_scope(scope: str) -> None:
    if scope not in {"spec", "plan", "debug"}:
        err_console.print(
            f"[red]invalid journal scope: {scope!r} (expected spec, plan, or debug)[/red]"
        )
        raise typer.Exit(2)


def _resolve_slug_and_plan_dir(slug: str | None, plan_dir: str | None) -> tuple[str, str]:
    """Resolve `check`'s `--slug`/`--plan-dir` pair, exit 2 if neither resolves.

    `check` is the one journal verb where `--slug` is optional, because a
    `kind: cli` manifest step (spec §C) can interpolate `{{ artifacts.plan }}`
    as `--plan-dir` but cannot compute that folder's basename itself — without
    this, `--require-reviews` is not expressible as a manifest step at all.
    `--plan-dir` defaults symmetrically from `--slug` (mirroring `fr journal
    handoff`'s existing default of `docs/superpowers/plans/<slug>`) so either
    option alone is sufficient.

    A plan dir with no final component (`.`, `""`, a bare `/`) derives an EMPTY
    slug, and an empty slug is not a harmless one: it resolves the journal
    `journals/plans/.md`, which does not exist, which `_load` reads as an empty
    journal, so the whole command — including the pre-existing open-findings
    rule — exits 0 having checked nothing. Review r-p1-f1 found this live:
    `--plan-dir .` exited 0 on a plan whose journal carries four open findings.
    A gate whose premise is failing closed cannot have a spelling of its own
    arguments that fails open, so the empty derivation is refused here.

    Structured as two early returns rather than one combined guard so that
    neither branch needs a `type: ignore` for `Path(None)` (review r-p1-f5): a
    guard that mypy can check is one a later edit cannot silently loosen.
    """
    if plan_dir is not None:
        resolved_slug = slug if slug is not None else Path(plan_dir).name
        # `.` and `..` are path-navigation tokens, not names: `Path("a/b/..").name`
        # is `".."`, which is non-empty and so survives an emptiness check while
        # resolving the journal `plans/...md` — the same fail-open by a
        # different spelling, caught by the test written for the empty case.
        if resolved_slug in ("", ".", ".."):
            err_console.print(
                f"[red]cannot derive a journal slug from --plan-dir {plan_dir!r}[/red] — "
                "pass --slug, or a plan dir whose last component is the plan slug"
            )
            raise typer.Exit(2)
        return resolved_slug, plan_dir
    if slug is not None:
        return slug, f"docs/superpowers/plans/{slug}"
    err_console.print("[red]give --slug or --plan-dir (at least one is required)[/red]")
    raise typer.Exit(2)


_ANSWERED_BY = get_args(AnsweredBy)

_ANSWERED_BY_HELP = (
    "who authorized this resolution: operator | agent. Moving an out-of-scope "
    "finding to fixed needs `operator` (else `fr journal check` reports an "
    "unauthorized fix); on Claude Code the claim is verified against the "
    "session transcript."
)


def _validate_answered_by(answered_by: str | None) -> None:
    if answered_by is not None and answered_by not in _ANSWERED_BY:
        err_console.print(
            f"[red]--answered-by must be one of {' | '.join(_ANSWERED_BY)} "
            f"(got {answered_by!r})[/red]"
        )
        raise typer.Exit(2)


def _verify_operator_claim(entries: list[JournalEntry], finding_id: str) -> None:
    """Check an `--answered-by operator` claim where fr can, before it is written.

    The window opens at the finding's LAST out-of-scope record (else the
    finding itself): an operator answer from before the orchestrator moved it
    out answered something else. Same observation the brainstorm gate makes
    (`fr.run.telemetry.operator_answered_since`) with the same three outcomes —
    observed and answered: record; observed and not: refuse, nothing written;
    not observable: record, and say so. OpenCode and Hermes have no question
    tool fr can read, so there the claim is recorded as stated.
    """
    from fr.harness.detect import detect_harness
    from fr.harness.model import HarnessError
    from fr.run.telemetry import operator_answered_since

    since = next(
        (
            e.created
            for e in reversed(entries)
            if e.id == finding_id or (e.resolves == finding_id and e.out_of_scope)
        ),
        None,
    )
    observed = operator_answered_since(os.environ, journal_stamp_as_utc(since)) if since else None
    if observed is True:
        return
    if observed is False:
        err_console.print(
            f"[red]{finding_id}: no answered question in this session's transcript since "
            f"{since} — `--answered-by operator` is a claim fr can check here, and it does "
            "not hold. Ask the operator with your harness's question tool, then resolve "
            "again.[/red] Nothing written.",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    try:
        harness = detect_harness(os.environ)
    except HarnessError as e:
        err_console.print(f"[red]{e}[/red]")
        raise typer.Exit(2) from e
    if harness == "claude-code":
        err_console.print(
            f"[yellow]{finding_id}: could not verify `--answered-by operator` — the "
            "session transcript is not readable here; recorded unverified.[/yellow]",
            soft_wrap=True,
        )
    else:
        from fr.harness import load_matrix

        # The reason is the parity row's own `scope_note`, never a second
        # hand-typed copy of it (the same rule the brainstorm gate follows).
        row = next(s for s in load_matrix().surfaces if s.id == "out-of-scope-operator-guard")
        cell = row.harnesses.get(harness) if harness is not None else None
        why = (cell.scope_note if cell else None) or "fr cannot read an operator answer here"
        err_console.print(
            f"{finding_id}: `--answered-by operator` recorded as stated — advisory on "
            f"{harness or 'an unrecognised harness'}: {why}",
            markup=False,
            soft_wrap=True,
        )


@journal_app.command("add")
def add(
    scope: str = typer.Option(..., "--scope", help="spec | plan | debug."),
    slug: str = typer.Option(..., "--slug", help="Journal slug (spec/plan/debug slug)."),
    kind: str = typer.Option(..., "--kind", help="Entry kind (see spec §A)."),
    title: str = typer.Option(..., "--title", help="One-line entry title."),
    body: str = typer.Option("", "--body", help="Entry body (Markdown)."),
    phase: int | None = typer.Option(
        None, "--phase", help="Phase number (--scope plan: required unless --global)."
    ),
    is_global: bool = typer.Option(
        False,
        "--global",
        help="--scope plan only: this entry genuinely applies to every phase — "
        "the explicit escape from tagging one with --phase.",
    ),
    state: str | None = typer.Option(None, "--state", help="finding only: fixed | refuted | open."),
    entry_id: str | None = typer.Option(
        None, "--id", help="Stable id; re-adding the same id is idempotent."
    ),
    resolves: str | None = typer.Option(
        None,
        "--resolves",
        help="finding only: this entry is a resolution record for that finding id "
        "(`fr journal resolve` is the ergonomic form; use this to RE-OPEN one).",
    ),
    review_scope: str | None = typer.Option(
        None,
        "--review-scope",
        help="finding only: the reviewer's tag — in | out. Copied from the review, "
        "so a finding later resolved out-of-scope against the reviewer's `in` "
        "renders as reclassified.",
    ),
    answered_by: str | None = typer.Option(
        None, "--answered-by", help="--resolves only: " + _ANSWERED_BY_HELP
    ),
) -> None:
    """Append one entry to ``docs/superpowers/journals/<slug>.md``."""
    _validate_scope(scope)
    # spec §5.A2: an untagged plan-scope entry hits `compose_handoff`'s
    # `e.phase is None` branch and renders in full at EVERY phase forever —
    # measured cost: 16 untagged discoveries / 13,281 chars at phase 6 of a
    # real journal. Spec and debug journals have no phases and are untouched.
    # Checked OUTSIDE the plan guard: on spec/debug `--global` used to be a
    # silent no-op, so `--phase 3 --global` on a spec journal wrote a
    # phase-3-tagged entry while the operator had asked for a global one.
    # Refusing a plan-only flag where it cannot apply beats honouring neither.
    if is_global and scope != "plan":
        err_console.print(
            "[red]--global applies to --scope plan only[/red] — spec and debug "
            "journals have no phases, so every entry in them is already global"
        )
        raise typer.Exit(2)
    if scope == "plan":
        if phase is None and not is_global:
            err_console.print(
                "[red]--scope plan needs --phase N or --global[/red] — an untagged "
                "entry renders in full in every handoff, at every phase; pass "
                "--phase N for a phase-scoped entry, or --global for one that "
                "genuinely applies everywhere"
            )
            raise typer.Exit(2)
        if phase is not None and is_global:
            err_console.print(
                "[red]--phase and --global are contradictory[/red] — an entry is "
                "either scoped to one phase or explicitly global, not both"
            )
            raise typer.Exit(2)
    if review_scope is not None and review_scope not in ("in", "out"):
        err_console.print(f"[red]--review-scope must be in | out (got {review_scope!r})[/red]")
        raise typer.Exit(2)
    _validate_answered_by(answered_by)
    root = resolve_repo_root()
    path = journal_path(root, scope, slug)  # type: ignore[arg-type]

    stamp = _timestamp()
    eid = (
        entry_id or hashlib.sha1(f"{kind}|{scope}|{slug}|{title}|{body}".encode()).hexdigest()[:12]
    )

    try:
        entry = JournalEntry(
            kind=kind,  # type: ignore[arg-type]
            scope=scope,  # type: ignore[arg-type]
            id=eid,
            created=stamp,
            phase=phase,
            title=title,
            body=body,
            state=state,  # type: ignore[arg-type]
            resolves=resolves,
            review_scope=review_scope,  # type: ignore[arg-type]
            answered_by=answered_by,  # type: ignore[arg-type]
        )
    except ValueError as e:
        err_console.print(f"[red]invalid entry:[/red] {e}")
        raise typer.Exit(2) from e

    existing = _load(path)
    if any(e.id == eid for e in existing):
        err_console.print(
            f"[red]journal entry {eid!r} already exists; use `fr journal resolve` "
            "to change a finding[/red]"
        )
        raise typer.Exit(2)
    # Review r7-m2: `resolve` refuses an unknown id, and so must `--resolves`.
    # `effective_finding_states` deliberately tolerates a record naming a
    # finding that is not there, so that a hand-spliced journal cannot crash the
    # gate — which means a typo'd id here would report as open FOREVER with
    # nothing in the file to explain it. A gate wedged by an unfindable id is
    # the silent-stall shape this PR exists to remove, so refuse it at the door.
    if resolves is not None and not any(e.id == resolves and e.kind == "finding" for e in existing):
        err_console.print(
            f"[red]no finding with id {resolves!r} in this journal[/red] — "
            "`--resolves` must name a finding that exists"
        )
        raise typer.Exit(2)
    if resolves is not None and answered_by == "operator":
        _verify_operator_claim(existing, resolves)
    append_journal_entry(path, slug, entry)
    commit_records(root, [path], f"chore(fr): journal {scope}/{slug} — {entry.kind} {entry.id}")


RESOLUTION_STATES = ("fixed", "refuted", "deferred", "out-of-scope")
"""What `resolve` may close a finding to. Re-opening is `add --resolves`:
`resolve` is the verb for "this is done with", and a re-open is new
information, which belongs in an entry with a body of its own."""


def _record_id(finding_id: str, taken: set[str]) -> str:
    """`<finding>-resolved`, then `-2`, `-3`… — predictable, and never a
    duplicate id (which `fr validate artifacts` fails a journal for)."""
    base = f"{finding_id}-resolved"
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


@journal_app.command("resolve")
def resolve(
    scope: str = typer.Option(..., "--scope", help="spec | plan | debug."),
    slug: str = typer.Option(..., "--slug", help="Journal slug (spec/plan/debug slug)."),
    entry_id: str = typer.Option(..., "--id", help="The FINDING id being resolved."),
    state: str = typer.Option(
        ...,
        "--state",
        help="fixed | refuted | deferred | out-of-scope. `deferred` = the finding is "
        "valid but not this change's to fix; requires --tracked-by. `out-of-scope` = "
        "true, but not caused by this change (--note says why); no issue needed yet.",
    ),
    note: str = typer.Option(
        ...,
        "--note",
        help="Why it is resolved (required — 'resolved' with no reason is the "
        "silent state change the rules forbid).",
    ),
    phase: int | None = typer.Option(None, "--phase", help="Phase doing the resolving, if any."),
    tracked_by: str | None = typer.Option(
        None,
        "--tracked-by",
        help="--state deferred only: the issue that now carries the work "
        "(#N, owner/repo#N, or an http(s) URL).",
    ),
    answered_by: str | None = typer.Option(None, "--answered-by", help=_ANSWERED_BY_HELP),
) -> None:
    """Append a resolution record closing one finding (spec §3.G.1).

    `--state deferred --tracked-by <issue>` closes a finding that is REAL but
    belongs to another change. Before it existed the only closing states were
    fixed and refuted, so such findings were recorded as refuted — a claim the
    finding was wrong. A deferral must name its issue: it is where the work
    went, not a softer way to drop it.

    `--state out-of-scope` is the step before a deferral: the finding is true
    but this change did not cause it, and no issue exists yet. The PR body
    lists it for the operator to file; the gate does not wait on it.

    Append-only on purpose: the finding keeps its own text and `state: open`,
    and `fr journal check` folds records into an EFFECTIVE state. A finding
    rewritten in place would erase that it was ever open, which is what later
    phases read the journal to learn.

    Fails, loudly and without writing, on an unknown id — a silent success here
    would leave the gate red with the operator believing it was cleared.
    """
    _validate_scope(scope)
    root = resolve_repo_root()
    # Resolve through the read path: a journal archived alongside its plan is
    # still the file the finding lives in, and a resolution record must land
    # there rather than conjure a new active journal holding only the record.
    # NAMING THE TRADE-OFF (review r7-m3): that means this command can append
    # under `docs/superpowers/implemented/`, which
    # `.claude/rules/artifact-versioning.md` otherwise treats as frozen. The
    # exception is deliberate and narrow — the rule freezes archived artifacts
    # against MIGRATION, i.e. against a tool rewriting history nobody asked it
    # to touch. This is an operator resolving a finding they can still see, and
    # the alternative writes a phantom journal the gate never reads.
    path = resolve_journal_read_path(root, scope, slug)  # type: ignore[arg-type]
    if state not in RESOLUTION_STATES:
        err_console.print(
            f"[red]--state must be one of {' | '.join(RESOLUTION_STATES)} (got {state!r})[/red] "
            "— re-open a finding with `fr journal add --resolves <id> --state open --phase N`"
        )
        raise typer.Exit(2)
    if state == "deferred" and not tracked_by:
        err_console.print(
            "[red]--state deferred needs --tracked-by <issue>[/red] — a deferral says "
            "where the work went (#N, owner/repo#N, or a URL)"
        )
        raise typer.Exit(2)
    if tracked_by is not None and state != "deferred":
        err_console.print(
            "[red]--tracked-by is only for --state deferred[/red] — a fixed or refuted "
            "finding has nowhere left to go"
        )
        raise typer.Exit(2)
    _validate_answered_by(answered_by)
    if tracked_by is not None and not TRACKED_BY_RE.match(tracked_by):
        err_console.print(
            f"[red]--tracked-by must name an issue (#N, owner/repo#N, or an http(s) "
            f"URL), got {tracked_by!r}[/red]"
        )
        raise typer.Exit(2)
    try:
        entries = _load(path)
    except JournalParseError as e:
        err_console.print(f"[red]journal parse error:[/red] {e}")
        raise typer.Exit(2) from e
    target = next((e for e in entries if e.id == entry_id), None)
    if target is None:
        err_console.print(
            f"[red]no journal entry `{entry_id}` in {path}[/red] — nothing resolved "
            "(`fr journal render` lists the ids this journal carries)"
        )
        raise typer.Exit(2)
    if target.kind != "finding":
        err_console.print(
            f"[red]entry `{entry_id}` is a `{target.kind}`, not a finding[/red] — only a "
            "finding has a state to resolve"
        )
        raise typer.Exit(2)
    if answered_by == "operator":
        _verify_operator_claim(entries, entry_id)

    record = JournalEntry(
        kind="finding",
        scope=scope,  # type: ignore[arg-type]
        id=_record_id(entry_id, {e.id for e in entries}),
        created=_timestamp(),
        phase=phase,
        title=f"resolves {entry_id}: {target.title}",
        body=note,
        # A deferral is WRITTEN as `open` + `tracked_by`: an older fr rejects an
        # unknown `state=` value (and with it the whole journal) but ignores an
        # unknown token, so it reads the finding as still open — fail closed.
        # Out-of-scope is written the same way, for the same reason.
        state="open" if state in ("deferred", "out-of-scope") else state,  # type: ignore[arg-type]
        resolves=entry_id,
        tracked_by=tracked_by,
        out_of_scope=state == "out-of-scope",
        answered_by=answered_by,  # type: ignore[arg-type]
    )
    append_journal_entry(path, slug, record)
    shown = f"deferred → {tracked_by}" if tracked_by else state
    typer.echo(f"{entry_id} → {shown} (record {record.id})")
    commit_records(root, [path], f"chore(fr): journal {scope}/{slug} — {record.kind} {record.id}")


def _deferrals(entries: list[JournalEntry]) -> list[tuple[str, str]]:
    """(finding id, tracked-by ref) for each finding whose EFFECTIVE state is
    deferred — the last deferral record naming it supplies the ref."""
    states = effective_finding_states(entries)
    refs: dict[str, str] = {}
    for e in entries:
        if e.resolves is not None and e.tracked_by is not None:
            refs[e.resolves] = e.tracked_by
    return [(fid, refs[fid]) for fid, st in states.items() if st == "deferred" and fid in refs]


def _group_findings(
    entries: list[JournalEntry], states: dict[str, EffectiveFindingState]
) -> tuple[list[str], list[str]]:
    """Serialized blocks split into (this change's, out-of-scope).

    A finding whose EFFECTIVE state is out-of-scope moves — with every record
    naming it — to its own section, so the PR body can ask the operator which
    to file as issues. `states` is the fold over the WHOLE journal, not the
    section-filtered slice, so the grouping cannot depend on `--section`.

    A finding the REVIEWER tagged in-scope that ended out-of-scope was moved by
    the orchestrator, and says so under its heading: that decision is the one
    the PR reader most needs to be able to question.
    """
    main: list[str] = []
    out: list[str] = []
    for e in entries:
        fid = e.resolves if e.resolves is not None else e.id
        block = serialize_entry(e)
        if e.kind != "finding" or states.get(fid) != "out-of-scope":
            main.append(block)
            continue
        if e.review_scope == "in":
            head, _, rest = block.partition("\n### ")
            heading, _, body = rest.partition("\n")
            block = (
                f"{head}\n### {heading}\n\n> reclassified by the orchestrator — the "
                f"reviewer tagged this in scope\n{body}"
            )
        out.append(block)
    return main, out


_SECTION_KINDS = {
    "findings": {"finding"},
    "decisions": {"decision"},
    "discoveries": {"discovery"},
    "reviews": {"review"},
}


@journal_app.command("render")
def render(
    scope: str = typer.Option(..., "--scope"),
    slug: str = typer.Option(..., "--slug"),
    section: str = typer.Option(
        "all", "--section", help="findings | decisions | discoveries | reviews | all."
    ),
) -> None:
    """Emit journal entries as Markdown (fail-open: missing/bad file → nothing)."""
    _validate_scope(scope)
    root = resolve_repo_root()
    # Read-resolve so a render still works after the spec/plan was archived.
    path = resolve_journal_read_path(root, scope, slug)  # type: ignore[arg-type]
    try:
        entries = _load(path)
    except JournalParseError:
        return  # fail-open: never block a render on a malformed file
    states = effective_finding_states(entries)
    keep = _SECTION_KINDS.get(section)
    if keep is not None:
        entries = [e for e in entries if e.kind in keep]
    if not entries:
        return
    main, out = _group_findings(entries, states)
    if out:
        main.append("## Out-of-scope findings\n\n" + "\n".join(out))
    # Emit RAW — this feeds a PR body. A Rich console would treat `[...]` in a
    # finding title/body (Markdown links, `[PR #12]`) as markup and drop it.
    typer.echo("\n".join(main))


@journal_app.command("check")
def check(
    scope: str = typer.Option(..., "--scope"),
    slug: str | None = typer.Option(
        None,
        "--slug",
        help="Journal slug. Required unless --plan-dir is given (then derived "
        "as the plan dir's basename).",
    ),
    require_reviews: bool = typer.Option(
        False,
        "--require-reviews",
        help="Also fail when a phase the plan claims is done has no recorded "
        "`review` journal entry naming it. --scope plan only.",
    ),
    plan_dir: str | None = typer.Option(
        None,
        "--plan-dir",
        help="Plan folder (default docs/superpowers/plans/<slug>) --require-reviews "
        "checks phases against. May be given instead of --slug, which is then "
        "derived as this folder's basename.",
    ),
) -> None:
    """Freshness gate. Non-zero on a parse error or any EFFECTIVELY open finding.

    Effective, not per-entry: a finding closed by a later `fr journal resolve`
    record no longer counts, and one re-opened by a later record counts again
    (spec §3.G.1). A journal with no resolution records — every journal written
    before that verb existed — gates exactly as it did before.

    `--require-reviews` additionally fails when a locally-complete, non-manual
    phase has no `kind=review` entry naming it — opt-in, so `fr journal check
    --scope plan` without the flag behaves exactly as it did before the flag
    existed.
    """
    _validate_scope(scope)
    # Scope refusals come FIRST, before any slug resolution (review r-p1-f3).
    # Both are unsatisfiable whatever slug is supplied, so reporting a missing
    # `--slug` here would send the operator to fix the wrong thing and learn
    # the real objection only on the next run.
    if require_reviews and scope != "plan":
        err_console.print(
            f"[red]--require-reviews needs --scope plan (got {scope!r}) — only "
            "plan journals have phases[/red]"
        )
        raise typer.Exit(2)
    if plan_dir is not None and scope != "plan":
        err_console.print(
            f"[red]--plan-dir needs --scope plan (got {scope!r})[/red] — it names a "
            "plan, and outside plan scope it would silently pick a "
            f"{scope} journal named after that folder"
        )
        raise typer.Exit(2)
    resolved_slug, resolved_plan_dir = _resolve_slug_and_plan_dir(slug, plan_dir)
    root = resolve_repo_root()
    # Read-resolve so a check still gates on an archived journal's findings.
    path = resolve_journal_read_path(root, scope, resolved_slug)  # type: ignore[arg-type]
    try:
        entries = _load(path)
    except JournalParseError as e:
        err_console.print(f"[red]journal parse error:[/red] {e}")
        raise typer.Exit(2) from e
    failed = False
    # Deferrals pass the gate, but are SAID, never silent: each names the
    # issue that now carries it, so a reader of the check (or the PR it feeds)
    # sees what this change chose not to fix.
    deferred = _deferrals(entries)
    if deferred:
        console.print(
            f"{len(deferred)} deferred finding(s): "
            + ", ".join(f"{fid} → {ref}" for fid, ref in deferred)
        )
    # Same for out-of-scope: passes, and is listed, so the operator can still
    # choose to file each as an issue.
    out_of_scope = [
        fid for fid, st in effective_finding_states(entries).items() if st == "out-of-scope"
    ]
    if out_of_scope:
        console.print(f"{len(out_of_scope)} out-of-scope finding(s): " + ", ".join(out_of_scope))
    unauthorized = unauthorized_fixes(entries)
    if unauthorized:
        err_console.print(
            f"[red]{len(unauthorized)} unauthorized fix(es):[/red] "
            + ", ".join(unauthorized)
            + " — fixed out of out-of-scope without `answered_by=operator`. Ask the "
            "operator, then `fr journal resolve --id <id> --state fixed --answered-by "
            "operator --note …`; or resolve it out-of-scope again.",
            soft_wrap=True,
        )
        failed = True
    still_open = open_finding_ids(entries)
    if still_open:
        # Output shape unchanged ("N open finding(s): <ids>") — things grep it.
        # Printed FIRST, and always, so composition with the reviews gate below
        # never reorders or swallows this line (spec §B, P2.T2.S1(f)).
        err_console.print(
            f"[yellow]{len(still_open)} open finding(s):[/yellow] " + ", ".join(still_open)
        )
        failed = True
    if require_reviews:
        # Imported here, not at module scope, so the cost of importing the
        # plan parser/renderer stays off every `fr journal` verb that never
        # touches a plan (the same convention `handoff` already uses below).
        from fr.journal.model import reviewed_phases
        from fr.parser import PlanSchemaError, parse
        from fr.render import plan_locally_complete

        plan_path = root / resolved_plan_dir
        try:
            plan = parse(plan_path)
        except (PlanSchemaError, OSError) as e:
            # `markup=False, soft_wrap=True`, not a bare print (review r-p2-f4):
            # pydantic's error text carries `[type=missing, input_value=...]`,
            # which Rich parses as a style tag and SILENTLY DROPS — the most
            # diagnostic half of the message vanishing from a fail-closed exit.
            # Wrapping likewise folds the absolute plan path mid-token.
            err_console.print(
                f"cannot check --require-reviews: plan {plan_path} is not parseable ({e})",
                markup=False,
                soft_wrap=True,
            )
            raise typer.Exit(2) from e
        # A plan that parses to ZERO phases must not read as "nothing owed"
        # (review r-p2-f1). `parse` silently ignores any file not matching
        # `NN.yaml`, so a phase file misnamed `1.yaml` or `02.yml` yields
        # `phases == ()` — and a plan with real, complete, unreviewed phases
        # would sail through green. That is the vacuous pass this gate exists
        # to abolish, so it is refused rather than reported as clean. Spec §B:
        # a gate that cannot read the plan does not know whether it passed.
        if not plan.phases:
            err_console.print(
                f"cannot check --require-reviews: plan {plan_path} has no phase files "
                "(NN.yaml, zero-padded) — refusing rather than reporting a vacuous pass",
                markup=False,
                soft_wrap=True,
            )
            raise typer.Exit(2)
        # Which completion predicate, and why it matters (spec §B): NOT
        # `_phase_complete` (needs an observed merged PR that never exists
        # during an fr-goal run — a gate built on it would pass every plan
        # forever). `plan_locally_complete` answers "does the plan ITSELF
        # claim this phase is done" — completion.at set OR every step ticked
        # — which is what this gate actually asks. Tag-agnostic by design, so
        # the [manual] exemption (spec D4) is applied here at the call site.
        owed = {
            p.phase.number
            for p in plan.phases
            if plan_locally_complete(p) and p.phase.tag != "manual"
        }
        missing = sorted(owed - reviewed_phases(entries))
        if missing:
            phases_str = ", ".join(str(n) for n in missing)
            err_console.print(
                f"[red]{len(missing)} phase(s) owed a review, none recorded: {phases_str}[/red]"
            )
            for n in missing:
                # `soft_wrap=True` is load-bearing, not cosmetic (review
                # r-p2-f2): this line ENDS IN A COMMAND the reader is meant to
                # paste. Rich folds at column 80 in any non-TTY — a pipe, CI,
                # or `fr run advance` executing the `kind: cli` step, which is
                # precisely the consumer spec D3 designed this for — turning
                # one command into three broken ones. Same convention and same
                # reason as `run_cmd.py`'s gate lines and `archive_cmd.py`.
                err_console.print(
                    f"  fr journal add --scope plan --slug {resolved_slug} --kind review "
                    f'--phase {n} --title "phase {n} review" '
                    "--body \"<findings raised, by id; or 'no findings'>\"",
                    markup=False,
                    soft_wrap=True,
                )
            err_console.print("(manual phases are exempt from --require-reviews — spec D4)")
            failed = True
    if failed:
        raise typer.Exit(1)


@journal_app.command("handoff")
def handoff(
    scope: str = typer.Option(..., "--scope", help="plan (only plan journals have phases)."),
    slug: str = typer.Option(..., "--slug", help="Journal slug (plan slug for scope=plan)."),
    phase: int = typer.Option(..., "--phase", help="Phase number to compose the handoff for."),
    plan_dir: str | None = typer.Option(
        None,
        "--plan-dir",
        help="Plan folder (default docs/superpowers/plans/<slug>); the phase's "
        "depends_on comes from here.",
    ),
) -> None:
    """Compose the curated executor handoff for one phase (fail-closed).

    Unlike `render` (PR-body feed, fail-open), the handoff feeds an executor
    brief — a silently-empty handoff makes the executor guess, so a missing
    plan, an unknown phase, or a malformed journal is exit 2 naming what is
    wrong. Only a journal that was never written is empty (exit 0, no output):
    there is nothing to curate yet.
    """
    from fr.journal.model import compose_handoff
    from fr.parser import PlanSchemaError, parse

    _validate_scope(scope)
    if scope != "plan":
        err_console.print(
            f"[red]handoff needs --scope plan (got {scope!r}) — only plan journals "
            "have phases to compose for[/red]"
        )
        raise typer.Exit(2)
    root = resolve_repo_root()
    # Read-resolve so a handoff still composes after the journal was archived
    # alongside its spec/plan.
    path = resolve_journal_read_path(root, scope, slug)  # type: ignore[arg-type]
    if not path.exists():
        return  # fail-open: nothing written yet, nothing to curate
    try:
        entries = _load(path)
    except JournalParseError as e:
        err_console.print(f"[red]journal parse error:[/red] {e}")
        raise typer.Exit(2) from e
    plan_path = root / plan_dir if plan_dir else root / "docs" / "superpowers" / "plans" / slug
    try:
        plan = parse(plan_path)
    except (PlanSchemaError, OSError) as e:
        err_console.print(
            f"[red]cannot compose a dependency-scoped handoff: plan {plan_path} "
            f"is not parseable ({e})[/red]"
        )
        raise typer.Exit(2) from e
    headers = [p.phase for p in plan.phases if p.phase.number == phase]
    if not headers:
        known = sorted(p.phase.number for p in plan.phases)
        err_console.print(
            f"[red]phase {phase} is not a phase of plan {slug} (phases: {known})[/red]"
        )
        raise typer.Exit(2)
    depends_on = tuple(headers[0].depends_on)
    # Emit RAW — this feeds a dispatch brief. A Rich console would treat `[...]`
    # in a title/body (Markdown links, `[PR #12]`) as markup and drop it, same
    # reason `render` echoes raw.
    typer.echo(compose_handoff(entries, phase=phase, scope=scope, slug=slug, depends_on=depends_on))
