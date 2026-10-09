# Batch sweep status lanes — design

**Date:** 2026-10-08
**Slug:** `2026-10-08-batch-sweep-status-lanes`
**Status:** design (fr-goal, autonomous)
**Repo:** `derio-net/super-fr` (single-repo change)
**Issue:** `derio-net/super-fr#1086`
**Delivery:** draft PR for operator review; this run never marks it ready or merges it

## Background

The batch board currently puts every card in a lifecycle column derived only
from its batch stage (`fr.triage.kanban.column_of`). Operator attention is a
boolean decoration: `_card` raises `needs_you` for a blocked session, a recorded
merge stop, or a sufficiently old idle session. This loses two distinctions the
operator needs during a sweep:

- an early run waiting for an answer is different from a late run whose draft
  PR is complete and ready for review;
- a draft PR still being written is different from a draft whose `deliver` step
  is done;
- conflicts and red CI are agent work while a usable batch session exists, not
  operator work;
- `drive_pass` can currently emit `merge` from green checks without considering
  the PR's collected `mergeable` or `merge_state` values.

The required inputs and seams already exist:

- `PullRequest.mergeable` and `PullRequest.merge_state` are populated by
  `fr.triage.collect._pr` from GitHub's `mergeable` and `mergeStateStatus`.
- A batch PR's `files` and `head_oid` identify run cursor files introduced by
  that PR. `fr.triage.gitseam.Checkout.show(ref, file)` reads a cursor from the
  PR head without checking out the branch or consulting the host triage cache.
- `fr_dispatch.protocols.SessionMessenger.message` is the canonical optional
  prompt seam. The conflict hand-back in `_Driver._hand_back` already constructs
  the batch `WorkItem` and uses this seam.
- `fr.triage.batch_drive.Snapshot.warned` is the pass-local de-duplication set
  keyed by head OID. A successful relay adds its head; a changed head is eligible
  again.

## Requirements

R1. The board has nine ordered columns: **Proposed**, **Waiting**, **Running**,
**Needs you · start**, **PR open**, **Needs you · review**, **Closing out**,
**Partial**, and **Done**. Every batch still appears exactly once. Existing
lifecycle placement is unchanged unless R2 or R3 supplies a human-attention
lane.

R2. A pre-PR batch appears in **Needs you · start** when its run cursor at the
batch PR/head branch is blocked on an operator gate, or when its batch session is
idle/done past the existing `idle_session_minutes` threshold while an unfinished
run cursor remains before `deliver`. A merely working batch stays in Running.
Blocked permission/tool prompts remain operator-visible in this lane when no
more specific late-run state applies.

R3. A batch appears in **Needs you · review** when any of these operator-owned
late states holds: its draft PR's run cursor has `deliver.state: done`; its run
is waiting at a manual phase; a live non-agent merge stop remains after the
driver's automatic hand-back policy is exhausted; or its close-out explicitly
requires operator action. A draft PR whose `deliver` step is not done remains in
**PR open**. Answering the gate, marking the draft ready, or completing the
manual action returns the card to its ordinary lifecycle lane on the next
render.

R4. Run status comes from the run cursor committed on the batch's remote head,
never from the board process's checked-out files, a session transcript, or the
host triage cache. With a PR, the immutable source is its `head_oid` and
candidate cursor paths are its changed files matching
`docs/superpowers/runs/*.yaml`. Before a PR exists, the source is the freshly
fetched `origin/<recorded batch branch>` and cursor paths are listed under that
ref's `docs/superpowers/runs/` tree. Each candidate is read through
`Checkout.show(ref, path)`, parsed fail-soft, and accepted only when its
`branch` equals the batch's recorded branch. Missing, malformed, missing-remote,
or unmatched cursors provide no run signal and leave lifecycle/session behavior
as the fallback.

R5. The pure board model receives run signals as an input keyed by batch id. It
performs no git, YAML, forge, runner, or clock I/O. `fr triage board` accepts the
drive's repeatable `--checkout OWNER/REPO=PATH` option and uses the same mapping
rules: a repo scope defaults to the current git toplevel; org/group scopes need
a clone for every represented repo. The driver's board write passes its already
validated checkout map. Every checkout fetches before the cursor read. An
unreadable repo, fetch, branch, or cursor adds at most one page note per repo and
does not fail rendering.

R6. A card in either human lane carries a specific hint: an early operator gate,
an idle unfinished run, a completed draft awaiting review, the named manual
phase, the live merge stop, or the owed close-out action. The authoritative
operator-close-out indicator is an unarchived `CloseoutEvent` whose `runner` is
`hand`; it enters Needs you · review and says the hand close-out is pending.
Once `archived` is set, ordinary terminal placement wins. The existing session
status remains visible but is secondary to cursor state. Conflicting/dirty PRs
and failing CI do not enter a human lane merely because of that failure while
the batch session can be prompted.

R7. A batch PR is a `merge` candidate only when it is open, non-draft, still at
the collected head, required checks are green, and forge mergeability is clean.
`mergeable == CONFLICTING` or `merge_state == DIRTY` is never rendered as
`merge ready` and never emits a merge action. Unknown mergeability fails closed
to a pending/held hint rather than claiming readiness.

R8. For a conflicting/dirty PR or failing required checks, one drive pass emits
an agent-relay action containing the PR number, head OID, PR URL, and either the
conflicting state or failing check names. The command sends that text to the
batch's existing session with `SessionMessenger.message` and the canonical
batch `WorkItem`. The prompt repeats the standing boundaries: stay on the batch
branch, fix and push, never merge.

R9. A successful conflict/red-CI relay is sent once per head OID for the driver
process. Repeated passes at the same head do not send it again; a new head may
be prompted. A missing messenger, absent session, busy/blocked session, or send
failure is reported and retried on a later pass rather than marked delivered.
The existing structured merge-conflict hand-back and its finite fresh-session
budget remain intact; this requirement handles forge-visible conflicts before a
merge attempt and red checks before the train reaches one.

R10. Existing board behavior remains intact: cards sort as before within each
column, counts and responsive stacking include the two new columns, expanded
details and jump controls are unchanged, hostile content stays escaped, and the
board still renders with absent/unreadable run information.

## Design

### A. Run signal (`fr.triage.kanban`)

Add a small immutable value owned by `fr`, not by the workflow engine:

```python
HumanLane = Literal["start", "review"]

@dataclass(frozen=True)
class RunSignal:
    lane: HumanLane
    reason: str
```

`build_board(..., run_signals: Mapping[str, RunSignal] = {})` passes the
signal to `_card`. Column precedence is terminal stage first, then an applicable
review signal, then an applicable start signal, then `column_of`. Terminal
cancelled/abandoned/done batches cannot be resurrected by stale cursor bytes.
An unarchived hand close-out is derived directly from the batch events as a
review lane even when no cursor exists. The signal's reason wins the hint;
session status and merge stops remain fallbacks when no signal exists.

`Column`, `COLUMN_TITLES`, `_COLUMN_OF_STAGE`, the render CSS grid, fixture
counts, and phone stacking expand to nine columns. No persisted artifact shape
changes: these are derived view values.

### B. Cursor read (`fr.commands.triage_kanban_cmd`)

The command-side helper groups batches by repo, resolves each repo's `Checkout`
through an injected factory, fetches it, and inspects either the batch PR's
changed run files at `pr.head_oid` or, before a PR, run files listed at
`origin/<recorded branch>`. YAML is treated as untrusted view input: a mapping
with a matching non-empty `branch`, `cursor`, and `steps` is enough; it is not
loaded with the live `RunState` model because older cursor schemas on an
in-flight branch remain meaningful to the board.

The helper derives:

- `review / draft deliver done` when the PR is draft and `steps.deliver.state`
  is `done`;
- `review / manual phase` when the current step/unit identifies a pending or
  blocked manual plan phase;
- `start / operator gate` for a blocked pre-deliver cursor;
- `start / idle unfinished run` only when the caller also supplies the existing
  idle-session result.

`triage_kanban_cmd` reuses `DriveCheckoutOpt`'s grammar and `_checkout_map`'s
validation through a cycle-free shared helper in the command layer.
`board_command`, `_watch`, and `write_board` carry that map. A direct board
render opens each clone; `_Driver._write_board` passes `self.checkout_paths`, so
group/org drives need no second configuration. `write_board` combines cursor
signals with session states and merge stops. Tests inject the checkout factory.
Failures append one note and yield no signal. No code reads
`$HOME/.cache/fr/triage` except the command's already-selected state directory.

### C. Merge readiness (`fr.triage.batch_drive`, `fr.triage.views`)

Extend `LivePr` with `url`, `mergeable`, and `merge_state`, populated both by
the command's fresh `pr_view` and by `views.drive_snapshot` from collected
facts. A pure `merge_verdict(pr)` returns clean, conflicting, or unknown. The
merge train checks it before adding a candidate:

- conflicting (`CONFLICTING` or `DIRTY`) emits the relay action and steps over
  the member without a merge action;
- unknown/unclean holds the train member and never says `merge ready`;
- only clean continues through existing head/check ordering.

The board's driver-derived hint therefore cannot say `merge ready` for a state
the driver itself would refuse.

### D. Session relay (`fr.commands.triage_batch_cmd`)

Add an explicit relay action kind instead of overloading every `warn` (exports,
stale sessions, and claim warnings are not prompts). `_Driver._act` resolves the
batch and launch exactly as dispatch/conflict handling already does, constructs
the canonical batch `WorkItem`, checks `SessionInspector` and
`SessionMessenger`, and sends only to an idle session. A successful send adds
the head OID to `warned`; all other outcomes leave it eligible for retry.

Conflict and CI prompt construction is a pure helper so unit tests can pin the
PR URL, details, branch boundary, push instruction, and never-merge warning.
There is no new runner method and no direct `fr_herdr` import.

### E. Rendering and views

`kanban_render` uses the existing `card.column` classes; its CSS gains colours
for the two attention lanes and the grid remains horizontally scrollable above
720px and stacked below it. `views.needs_you` stops listing red CI and an
ordinary forge-visible conflict as operator work when they are relayable; a
held conflict whose hand-backs are exhausted remains operator work. The module
comment no longer claims run cursors are unavailable to the board.

## Non-goals

- No host-cache inspection beyond the selected triage state directory.
- No inference from transcript prose or harness-specific question formats.
- No new persisted facts, judgements, run, or acceptance artifact fields.
- No automatic readying, merging, rebasing, force-pushing, or conflict
  resolution by the driver.
- No message transport beside `fr_dispatch.protocols.SessionMessenger`.
- No guarantee across driver process restarts; de-duplication has the same
  process lifetime as existing CI warnings.

## Automated verification (CI)

- Board model tests pin all nine columns, precedence, sorting, counts, specific
  hints, terminal-stage protection, missing signals, the two required draft
  states, manual phase, exhausted merge stop, and unarchived/archived hand
  close-out states.
- Board command tests use a temporary git repository and fake checkout to prove
  cursor reads occur at the PR head or, before a PR, the freshly fetched remote
  batch branch; repo/group checkout mappings reach the reads; branch mismatches
  and malformed YAML fail soft; and one repo failure produces one note.
- Render tests and browser captures cover both human lanes in light, dark, and
  phone layouts, including a completed draft and an early gate.
- Driver tests pin that conflicting, dirty, unknown, pending, failing, and clean
  PRs produce the required action/hint and only a clean PR emits `merge`.
- Drive command tests use a fake runner implementing the optional protocols to
  prove conflict and red-CI prompts send once per head, retry failures, avoid
  busy/blocked/absent sessions, and carry the branch/push/never-merge boundary.
- Import-direction tests continue to permit `fr_dispatch` only at the command
  soft point; pure triage modules remain independent.
- Existing board acceptance remains pinned while its column statement is
  updated from seven to nine: card uniqueness, sorting/counts, expanded detail,
  escaping, jump controls, dark mode, and responsive stacking do not regress.
- `tests/scenarios/triage-batch-status-lanes.sh` exercises the installed
  candidate CLI over fixture state and a temporary git repo: render both human
  lanes, reject merge-ready for a conflicting PR, and run a fake-runner drive
  pass that de-duplicates the relay.

## Verification

This PR is verified by its own `candidate` walk at `deliver`
(`fr verification walk --run <run-id> --model <m>`). The walk runs the smoke and
`tests/scenarios/triage-batch-status-lanes.sh` for all four acceptance rows.

strategy: candidate

## Test Plan (post-merge, operator-driven)

None. The candidate scenario and visual evidence exercise every requirement
before merge without depending on production-only infrastructure.

## Delivery Boundary

The pipeline opens or refreshes one **draft** PR for this branch and stops after
hand-off. It does not mark the PR ready and never merges it; those remain the
operator's post-delivery acts.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-08-batch-sweep-status-lanes | `derio-net/super-fr` | `2026-10-08-batch-sweep-status-lanes` | — |
