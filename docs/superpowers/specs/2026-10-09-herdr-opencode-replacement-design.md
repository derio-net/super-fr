# Herdr OpenCode sessions and audited batch replacement

**Status:** draft · **Run:** `2026-10-09-feat-1089`

## Background

The herdr runner supports run-unit dispatch through `fr_dispatch.protocols.Runner`.
`fr_herdr.runner.HARNESSES` currently contains only Claude, although the installed
herdr CLI supports `--kind opencode`; OpenCode accepts `--model provider/model`.
Status, focus, close and messaging already address stable item labels and agent names,
rather than harness kinds. `fr_herdr.restart` instead explicitly resumes Claude
sessions from their original directory. Starting a control session in an isolation
worktree ties its lifetime to a directory close-out legitimately removes.

`fr.commands.triage_batch_cmd.batch_edit_command` freezes launch fields after proposed.
`batch.last_dispatch`, `recorded_branch` and `of_dispatch` attribute existing PRs to the
original dispatch. Replacement must not reset that time or mint another dispatch.
The bridge audit read `fr_dispatch` and `fr_vk` end-to-end before this design.

## Requirements

R1. Herdr dispatch accepts OpenCode with an explicit provider/model and confirms the expected agent is ready and takes up its brief, using the same bounded startup/submission rules as Claude.
R2. Fr-created herdr control sessions start from the repo's stable primary checkout, including when dispatch, conflict recovery or close-out is invoked from a linked worktree; branch work is reached through fr isolation commands.
R3. OpenCode batch sessions retain existing status, messaging, focus, deduplication, conflict hand-back and close-out behavior under the same item identity.
R4. `fr triage batch replace <id>` supports Claude/OpenCode replacement in either direction and model-only replacement; preview is the default, `--yes` acts, `--reason` is required, and an explicit target model is required when changing harness.
R5. Replacement acts only on dispatched or pr-open, unmerged batches owned by a replacement-capable runner, with exactly one matching named source agent in idle/done state. Working, blocked, unknown, absent, ambiguous and caller-self sessions are refused before any input; a pending replacement is not silently retried.
R6. Replacement preserves the original dispatch event, branch, reservation, isolation workspace, PR, tab, pane/handle and fr-derived agent name. It starts a fresh target session from the stable primary checkout, reconstructing context from durable fr state rather than resuming the source transcript or restarting the initial goal.
R7. Replacement appends audited attempt/result events with timestamp, reason, old and requested launch settings and preserved identity. Effective batch launch harness/model change only after confirmed target startup; ordinary edit remains frozen. Replacement events never change batch stage, dispatch age, PR attribution or cancellation semantics.
R8. Partial replacement is a visible nonzero result. It never closes the tab or deletes the source transcript, branch or worktree, never claims successful metadata on failed startup, and reports whether the source remains, a target remains, or a shell is available, with concrete recovery instructions. No automatic source restart is attempted.
R9. An interrupted replacement or a successful target whose metadata save failed has an explicit repair path: confirm live target kind/model, pane and name before recording success, without exiting or launching another process. Failed or still-pending attempts remain visible and block an ordinary replacement until explicitly reconciled.
R10. `fr-herdr restart-idle` and the driver's post-install restart support fr-owned OpenCode batch, conflict and close-out sessions as fresh base-checkout sessions, preserving pane/name/model and reconstructing durable state. Unrelated OpenCode sessions are skipped. Existing Claude resume behavior remains as shipped.
R11. Fresh recovery never advances a delivered draft into merge or close-out: it instructs a finished deliver cursor to HOLD for operator review/ready/merge; a close-out item runs its existing pickup brief only after the delivery and merge gates permit it. A running unit from a dead source session is explicitly reconciled before redispatch, rather than dispatched twice.
R12. Operator documentation explains supported harnesses, replacement preview/act/repair, base-checkout control sessions, restart eligibility and failure recovery. Candidate scenarios and the scoped real herdr/read-only current-conflict walk verify before Ready; close-out against an actually merged PR is explicitly verified immediately post-merge.

## Design

### Runner seams and stable checkout (R1–R3)

Add OpenCode to the single `Harness` table (`kind=opencode`, `model_flag=--model`).
The command layer resolves `Checkout.main_worktree()` from the validated target clone
for dispatch/conflict/close-out payloads. Runner-side validation also normalizes a
real git checkout to its primary worktree through fr's existing isolation/git helpers,
so a direct runner caller cannot launch inside a linked worktree. Fail visibly when
the intended stable checkout is unavailable; never fall back to a disposable cwd.
Keep all herdr subprocesses in the existing `_herdr` seam. Preserve confirmation of
prompt pickup, duplicate protection, naming and cleanup for a NEW dispatch.
Replacement never uses that new-tab cleanup path.

### Optional replacement contract (R4–R9)

Add an optional runtime-checkable `SessionReplacer` protocol beside the existing
session protocols in `fr_dispatch.protocols`, implemented by herdr only. Its read-only
inspection returns source identity/status/kind/model and its operation returns a
structured success/failure with phase, observed surviving session and recovery text.
Fr uses the existing guarded soft-import seam; neither fr nor the runner imports the
other's triage implementation. Unsupported runners refuse explicitly.

The CLI accepts scope and checkout options, `--harness`, `--model`, `--reason`, `--yes`
and `--repair`. Resolve unchanged settings from batch/defaults/orchestrator as today,
but never inherit another harness's model on a harness change. Reject empty values,
unsupported harnesses, no-op requests and non-herdr runner changes. Inspect current
forge PR state (not just cached facts) before stopping a session; a merged/closed PR,
unreadable forge response, missing dispatch, or stale source identity refuses. A
no-PR dispatched batch is allowed if live branch PR lookup confirms that condition.

Write an attempt event BEFORE sending input, using compare-before-write and the
existing one batch writer. Re-inspect status and identity immediately before exit.
Before inspecting/writing the attempt, acquire an exclusive OS-backed lock keyed by
herdr server identity and pane; hold it through runner operations and final batch
and descriptor writes. A scope-state lock also serializes the batch writer's
read/compare/write sequence against other replacements in that scope. Contention
refuses rather than waits indefinitely. Acquire scope then pane, consistently;
restart acquires the same pane lock. A process crash releases OS locks but leaves
the durable pending marker for repair. Only the current owner may send input;
interleaved-caller tests must prove that a loser writes/sends nothing. Read/compare
alone is not a transaction claim.

Replacement applies the same harness-specific prompt/draft/background/dialog
eligibility checks as restart, and rechecks them immediately before exit. Idle/done
alone is insufficient. Unknown input layouts or unreadable observations refuse
replacement and skip restart, before any key is sent.
Use the source harness's graceful exit, bounded foreground-process polling and
confirmed interactive shell, change that shell to the stable checkout and confirm
its cwd before starting the target under the original name. Never answer an approval
or exit dialog; report it. `agent start` confirms ready kind/name/pane, followed by
process inspection confirming target model. Start from fresh-session flags only,
then submit the durable reconstruction brief with confirmed uptake.

Append success and update `batch.launch` in one compare-before-write. A failure appends
a failed result with diagnostic/recovery text and keeps launch settings unchanged.
If a write fails, the earlier attempt remains the durable reconciliation point.
`--repair --yes` handles the latest pending/failed attempt without re-launch: either
confirm the requested live target and finalize metadata, or confirm the original
source/shell and record the failed/aborted attempt. An unknown/working/blocked or
ambiguous observation refuses reconciliation. Preview sends no input and writes no
cache or batch state. Ordinary replace refuses an unreconciled attempt.

The runner's pending descriptor records durable checkpoints: prepared, source-exited,
target-ready, submission-started, uptake-confirmed, batch-committed and active. Write
submission-started before submitting and uptake-confirmed only after observed
working/blocked activity; a failed confirmation is submission-uncertain, never
success. Repair finalizes success ONLY with a persisted uptake-confirmed checkpoint
and matching live target. A pre-submission or uncertain target cannot be finalized
by its kind/model alone: refuse with instructions to inspect/recover it, without
blindly re-sending the brief. Once the operator returns it to the original source
or a confirmed shell, repair can close the failed attempt. Test each crash boundary.

The batch event/launch is authoritative for effective configuration; the descriptor
is authoritative only for observed runner-operation checkpoints. Order the writes:
pending descriptor, batch attempt, runner checkpoints, batch success plus launch,
descriptor active. Restart skips every unresolved/non-active descriptor, including
uptake-confirmed or batch-committed. Repair reconciles BOTH stores: if batch success
already landed, promote the matching confirmed descriptor without appending another
success or launching; if only uptake-confirmed landed, save success/launch then
promote it. Descriptor failure after a batch commit remains explicitly repair-owed.
No startup/submission error is converted to success by repair.

### Audit schema and readers (R7)

`fr.triage.model` adds a discriminated replacement event (attempt/success/failure,
attempt identifier, timestamp, old/new Launch values, original handle, pane/name,
reason and optional detail), gated behind judgements schema 7. Continue reading
schemas 1–6 unchanged; all writers stamp 7, using the existing model/save path.
Judgements are triage state, not a registered artifact kind: no artifact migration
or registry stamp change is appropriate. Update schema documentation and tests.

Keep `last_dispatch` as the sole original-dispatch selector. Fix readers that assume
the last event IS a dispatch (`dispatch --repair`) or cancellation (`derive_batch_stage`):
ignore replacement audit events for lifecycle derivation, while preserving the order
of real dispatch/cancel events. No forge labels, marker comments or claims are rewritten
by replacement. Driver close-out and any subsequent launch use the updated effective
launch configuration after a successful replacement.

### Durable fresh-session reconstruction and restart (R6, R10–R11)

Runner-owned local launch descriptors under a dedicated fr-herdr cache directory
(overrideable for tests) retain item id, role, branch, stable checkout, harness/model,
pane/name and reconstruction instructions. They are internal host-side runner state,
never repo artifacts or published evidence. Write atomically and validate reads.
Record new managed OpenCode dispatches and successful replacements, retaining an
attempt descriptor if startup may have happened; do not claim a completed launch
when target readiness/submission failed. Legacy sessions without descriptors can be
explicitly replaced using the validated batch input, but restart skips them with a
reason until managed metadata exists.

Batch recovery instructions enter/inspect the branch's existing isolation workspace,
locate its durable run cursor and inspect status/records/journals. They resume an
unfinished cursor according to its actual state and reconcile a former holder from
the dead session before redispatch. If deliver is done, HOLD; never invoke fr-goal on
the original issue text. Conflict recovery reuses the engine's conflict brief; close-out
reuses `fr pickup --run`/`--branch` and its merge checks. Do not resume OpenCode's old
session id. Names and descriptor roles distinguish batch/conflict/close-out items.
Conflict messages delivered to the ORIGINAL batch agent retain its batch identity:
`HerdrRunner.message` must update its managed reconstruction descriptor with the
hand-back head and brief, rather than relying on a separately named conflict item.
On recovery, compare that head with the current branch and live merge/conflict
state. An outstanding current hand-back takes precedence over delivered-draft HOLD;
reconstruct its existing six-step brief. A completed or obsolete conflict is not
replayed; inspect the current run/PR and HOLD or resume as appropriate. Test original
batch hand-back as well as separately launched conflict sessions.

OpenCode restart eligibility requires a validated managed descriptor matching live
pane/name/kind/model, fresh idle/done status, known foreground process, no unsent input
or background work, and caller/exclusion protection. Use harness-specific input-state
observation grounded in actual OpenCode surfaces; unreadable or unsupported layouts
skip, rather than assume safe. Recheck at mutation time. Preserve all existing Claude
restart rules and tests. Per-pane failures are reported and do not stop the next pane;
driver restarts still run once per opted-in post-merge pass.

The operator authorized a narrow disposable-session capture on 2026-10-09.
OpenCode 1.18.35 with herdr 0.9.0/protocol 22 was captured live: fresh-home
placeholder, session empty input, unsent draft, ctrl+p Commands overlay, active
shell turn, active subagent, completed subagent echo and plain `exit` returning
to the original base-checkout shell. Unsent drafts and the Commands overlay
both still report idle/done and interactive_ready: true. Inspect the final
input region and overlays separately from status; reject blank/unrendered or
unrecognized layouts. Completed task history is not background work; active
subagent/tool turns report working in these captures. OpenCode's graceful exit
is plain `exit`, corroborated by its version-matched Prompt.submitInner source;
Claude retains `/exit`. Capture provenance must state that permission/question
dialogs and independently detached children were not live-proven, and such
unsupported observations fail closed. The capture is grounding, not completion
of the operator's client-live acceptance walk.

### Documentation and verification (R12)

Update the runner README, triage operator documentation and the canonical fr-triage
skill (regenerate both OpenCode and Hermes mirrors). Update AGENTS.md's runner/schema
notes. Add a minor change fragment for the new replacement verb. Update any published
explainer whose wording would become false; record why unaffected pages need no change.

## Testing

- Runner contract and command tests cover OpenCode argv, ready identity, unchanged
  status/message/focus/dedup/close, stable checkout from linked worktrees and failed dispatch.
- Replacement tests cover both directions/model-only; preview sends no keys; busy,
  blocked, unknown, self, merged, ambiguous and unreadable states refuse; identity
  and original PR attribution survive attempt/result events and repeated repair.
- Failure injection at exit, shell-cwd confirmation, startup, model verification,
  prompt uptake and metadata writes proves no tab/worktree/transcript deletion and
  accurate metadata/recovery. Confirm crash-pending repair never launches twice.
- Restart tests exercise managed OpenCode batch/conflict/close-out reconstruction,
  draft/background/unknown skips, fresh source status, bounded polling and failure
  isolation; existing Claude behavior remains covered.
- Installed-build candidate scenarios drive the real fr/fr-herdr CLI against
  scripted herdr responses, plus schema round trips and lifecycle integration.
  Scripted responses are labelled synthetic unless actually captured; never claim
  fake runs prove interactive TUI safety.

## Verification

strategy: candidate
- herdr-opencode-launch: candidate
- herdr-batch-replace: candidate
- herdr-opencode-restart: candidate
- herdr-opencode-live: client-live
- herdr-opencode-closeout-live: live — requires an actually merged PR; the operator authorized merge followed immediately by real close-out rather than inventing a pre-merge merge prerequisite.

Candidate rows use `tests/scenarios/herdr-opencode.sh`,
`tests/scenarios/herdr-batch-replace.sh` and `tests/scenarios/herdr-opencode-restart.sh`.
The client-live row uses `tests/scenarios/herdr-opencode-live.sh`, an operator-led
walk against disposable named sessions in the real client, covering dispatch,
Claude→OpenCode replacement, reverse/model-only change, restart, messaging/focus,
read-only current-conflict hand-back selection/reconstruction, HOLD, busy refusal
and startup failure recovery. The current-conflict check may read existing
conflicting PR #1107 through the real forge adapter, match its actual head with
the local branch and inspect recovery selection. Never send its instructions to
the existing agent or mutate that PR; this proves selection/reconstruction, not
conflict resolution or a push. Native unsupported-provider/effective-UI-model
fallback is separately tracked in #1116; process-argv verification is the current
contract, and that native negative case is not a claimed startup-failure pass.
It prints instructions/verification checks and requires the operator's observed
verdict; it does not automatically mutate existing production batches.

The operator authorized Ready and merge with this honest split on 2026-10-10.
The pre-merge verdict covers exactly the checks above and the observed real
target-startup refusal/source-or-shell repair; it does not claim merged-PR
close-out or conflict resolution. Cite `Refs #1089` until the post-merge row is
walk-verified; the issue remains open for that obligation.

## Test Plan

- post-merge — operator-driven: in a new session immediately after #1115 merges,
  run `fr pickup --run 2026-10-09-feat-1089`, follow its real verify-merge and
  close-out brief, and observe the OpenCode control session remains in the stable
  primary checkout while the delivered workspace is archived/reaped. Verify
  pickup delivery/merge gates, archive PR and final session/tab cleanup; record
  the redacted live evidence on `herdr-opencode-closeout-live` before closing
  #1089. This requires an actually merged PR and is not pre-merge proof.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-09-herdr-opencode-replacement | `derio-net/super-fr` | `2026-10-09-herdr-opencode-replacement` | — |
