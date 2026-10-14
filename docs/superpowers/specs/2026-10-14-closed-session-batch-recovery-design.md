# Explicit recovery of closed triage batch sessions

## Context

An already-dispatched batch can retain its branch, isolation worktree and durable
run after its control pane is closed. Ordinary replacement deliberately requires
a live source, while repair reconciles an existing attempt without launching.
Neither can recover this state. Redispatch would change the lifecycle and replay
the initial goal, and is therefore the wrong operation.

The operator chose fresh recovery in HOLD, automated verification before delivery,
and a disposable real-client walk after merge at the Tester gate.

## Requirements

R1. Provide an explicit, preview-first recovery operation for an unmerged dispatched or pr-open herdr batch whose effective source session is positively absent; require an audit reason, explicit OpenCode harness and provider/model, and `--yes` to act. Ordinary replacement and dispatch retain their current eligibility rules.
R2. Preserve batch id, members, ordering, dependency/wave metadata, original dispatch event/time/reservation, recorded branch, existing worktree, commits, uncommitted work and durable cursor/records/journals. Recovery never starts a new goal, creates another branch/worktree, migrates artifacts, or changes issue claims/labels/PR approval state.
R3. Prove source absence using fresh complete herdr tab/agent observations, including recorded pane, stable item label and fr-derived name. A surviving matching session, ambiguity, unknown observations, stale/reused source pane, unresolved attempt, running scope driver, caller-self target, or unreadable/ambiguous branch cursor refuses before launch. Recheck under ownership before effects.
R4. Launch a fresh managed OpenCode control session in a new pane from the stable primary checkout, using the supplied provider/model and `--auto`. Derive its name from the unchanged work-item identity and let herdr allocate its pane; never synthesize a live descriptor or name from operator guesses.
R5. Persist auditable attempt/outcome records linking old and new pane ownership, observed fresh harness session id, model/harness and reason. Original lifecycle events stay immutable. Subsequent replacement/repair and other handle readers use successful effective ownership without changing dispatch age or lifecycle derivation; failed attempts never become effective ownership.
R6. Submit at most one reconstruction brief after independently confirming target process/name/model/cwd and safe rendered input. Every recovered session starts in HOLD: acknowledge and report existing run and pending gates, but make no mutations, abandon/redispatch no units, answer no questions, and wait for separate operator go-ahead. HOLD survives managed reconstruction/restart and overrides conflict or unfinished-cursor continuation instructions.
R7. Persist recovery intent keyed by original item/source identity before pane allocation; checkpoint partial failures and make explicit repair discover the same attempt and allocated or uncertain pane. Repair launches nothing and sends no prompt; success requires persisted uptake confirmation and matching live ownership. Uncertain allocation/submission, startup/observation failure, or cross-store write failure never authorizes replay or an automatic second allocation/launch. Report exact checkpoint, surviving target/pane and inspection/repair action.
R8. Keep recovery operator-invoked only: no automatic wave-driver recovery, org loop restart or real-batch takeover is part of this feature. Document preview, act, repair, HOLD release by separate operator instruction, scope/state identity, and limitations. Ship meaningful fake-backed candidate scenarios plus a disposable operator-owned post-merge walk at the Tester gate.

## Design

### Smallest coherent API

Extend the existing audited replacement verb with explicit `--recover`:

`fr triage batch replace <id> --recover --harness opencode --model openai/gpt-6.1-sol --reason <why> --org <org> --checkout <clone>`

The default is a read-only preview: print source identity, existing branch/worktree,
target harness/model, fresh-pane allocation plan, HOLD policy and repair guidance;
create no tab, descriptor, audit event, state push or prompt. `--yes` is a separate
operator approval. Recovery allows same-model recovery (it is not a no-op), but
requires explicit target harness/model rather than silently inheriting Claude.
Initially the recovery target is OpenCode only; ordinary replacement continues to
support both existing harness directions. Reject `--recover --repair`: repair uses
the persisted attempt's mode and target and accepts neither new harness nor model.

Do not add a second initial-dispatch path or reuse `runner.dispatch(item)` to replay
the initial goal. Extend the optional replacement operation contract with recovery
intent and structured actual target ownership, leaving mandatory Runner methods
and other adapters unchanged.

### Existing seams and bridge audit

The full `packages/fr-dispatch/src/fr_dispatch/*.py` and
`packages/fr-vk/src/fr_vk/*.py` were read before this spec. `fr_dispatch.tick`
filters item graphs by tracker projections and dispatch stamps; `WorkItem` identity
is immutable and independent of payload. VK takes phase units, builds card/workspace
state through its own adapter and does not implement managed session replacement.
Recovery belongs at the optional herdr session operation seam, not the tick or VK
card lifecycle. Preserve the dependency direction (`fr_herdr -> fr_dispatch -> fr`);
fr's sanctioned optional import remains inside `triage_batch_cmd.py`.

Current implementation anchors:

- `packages/fr/src/fr/commands/triage_batch_cmd.py`: `_replacement_transaction`,
  `_replacement_live_gate`, `batch_replace_command` and scope locking own batch
  eligibility, live PR truth and the sole audit/launch settings writer.
- `packages/fr-dispatch/src/fr_dispatch/protocols.py`: `ReplacementRequest`,
  `ReplacementResult`, `ReplacementOperation`, `SessionReplacer` form the optional
  contract. Add defaulted fields or a small optional extension, retaining existing
  callers and adapter independence.
- `packages/fr-herdr/src/fr_herdr/replacement.py`: `Operation` owns inspection,
  preparation, checkpoints, target launch, single submission and reconciliation.
  Reuse these safety primitives; recovery skips source exit entirely.
- `packages/fr-herdr/src/fr_herdr/runner.py`: `agent_name`, `stable_checkout`,
  `_open_tab`, `replacement_pending` and existing roster helpers provide canonical
  identity/allocation/lookup. A new operation must distinguish a verified empty
  roster from a malformed or failed read.
- `packages/fr-herdr/src/fr_herdr/managed.py`: `Descriptor`, `pane_lock`,
  `branch_workspace`, `reconstruct` own durable local recovery. Add persisted
  recovery intent/HOLD/source ownership as needed; preserve old descriptors.
- `packages/fr-herdr/src/fr_herdr/opencode.py`: `launch_args` already includes
  `--auto`; `wait_ready` and model/process checks guard input. Recovery must
  positively verify the autonomous launch arguments as well as the model.
- `packages/fr/src/fr/triage/model.py`: `ReplacementEvent` is audit only;
  `packages/fr/src/fr/triage/batch.py`: `last_dispatch`, `recorded_branch` and
  `lifecycle_events` preserve lifecycle semantics. Add optional recovery ownership
  fields and one effective-owner derivation rather than rewriting dispatches.

### Ownership and persistence

Scope ownership must span absent-source recheck, allocation, descriptor preparation,
attempt write, launch/submission, outcome write and activation. Refuse a live driver
before changing its scope. Acquire the existing source identity lock to serialize
recovery/replacement, plus the new target pane's lock before any target input; locks
must remain held through both durable-store commits.

Persist durable recovery intent keyed by server and original batch/item/source
identity BEFORE calling herdr allocation. It carries attempt id, source ownership,
branch, target harness/model and an allocation-pending checkpoint. Do not rely on a
pane-keyed descriptor that cannot exist until the allocation response is parsed.
Fresh item-labelled tab observations must permit read-only discovery of an allocation
whose response was lost or whose target-descriptor write failed. A malformed, failed
or ambiguous roster remains unknown: never allocate again to resolve it. Repair may
record the one positively identified allocated target or report confirmed absence,
without allocating, launching or sending a prompt. After a confirmed failed/aborted
attempt, any subsequent allocation requires a new explicit operator recovery act.

Once allocation returns, persist the actual target pane before launch and before any
prompt; retain the source-keyed intent so pending lookup survives batch audit failure.
A target allocated but not launched is still reported and never silently replaced by
another pane. Cross-store repair covers allocation effects, lost/invalid response,
first target-descriptor save, batch attempt save, startup and uptake boundaries.
No automatic tab cleanup may destroy a possibly-live or uncertain target.

Record source ownership separately from actual target ownership. Defaults must keep
legacy same-pane replacement events/descriptors readable. If the durable audit schema
widens, advance its writer schema coherently and test old schema reads; do not edit
release versions. Derive effective successful owner after the latest dispatch so old
successes cannot capture a subsequently dispatched branch. A pending new owner is
used only to reconcile that attempt, not to claim a successful running session.

Capture the harness session id from fresh herdr observations; readiness without a
readable session id does not certify R5. Absent session must be established across
both roster and item-label views. A reused original pane refuses without sending
keys to its unrelated occupant. The existing branch workspace and exactly one
readable branch-matching durable run must exist. Dirty work is preserved and
reported, never cleaned; no cursor is created or advanced by recovery.

### HOLD and gates

Persist HOLD with the managed descriptor. The reconstruction brief begins with a
HOLD block stating acknowledge/report-only, including for a current conflict
handback or a finished/unfinished run. It names the existing workspace/run and asks
for read-only inspection of records, cursor and pending gates. It must not instruct
`fr run advance`, `claim --abandoned`, pipeline restart or automatic session binding
that would make an idle guard advance the run before operator go-ahead.

The operator releases work by a separate instruction to the recovered session;
recovery itself never records an operator gate as answered or changes PR approval.
Managed restarts of that recovery session begin in HOLD again. Session attribution
in the recovery audit is distinct from taking a running unit's claim.

### Verification and delivery

Fake-backed tests exercise the public CLI, runner observations/allocation/checkpoints,
real descriptor serialization and batch audit save/read. Scenarios run an installed
candidate in disposable local fixtures with fake herdr/forge, never the six org
batches. Cover source closure, same-model recovery, no-op previews, live/ambiguous/
reused-pane refusals, repeated recovery after success, driver/lock contention,
allocation effects followed by lost/invalid responses or first descriptor-save
failure, metadata/startup/uptake failures, explicit repair without input, ownership
after repair and subsequent replacement, old schema reads, HOLD and `--auto`.

Business-level acceptance rows:

| ID | Claim | Requirements | Verification |
| --- | --- | --- | --- |
| triage-closed-recovery | A stopped batch can obtain a fresh held session without losing its work or original dispatch history. | R1,R2,R4,R5,R6 | candidate |
| triage-closed-recovery-refusals | Recovery refuses unsafe/unknown ownership and read-only previews leave state and sessions untouched. | R1,R3 | candidate |
| triage-closed-recovery-repair | An interrupted recovery cannot duplicate launch/submission; explicit repair retains truthful ownership. | R5,R7 | candidate |
| triage-closed-recovery-live | A real closed disposable control pane recovers into autonomous OpenCode HOLD with operator gates intact. | R4,R6,R8 | live, Tester |

Update `docs/herdr-control-sessions.md`, `packages/fr-herdr/README.md`, canonical
fr-triage guidance and generated mirrors if changed. Explain why existing published
explainers need no update if they do not describe this recovery surface; update any
page that does. Add a minor change fragment. Required automated checks include full
pytest, ruff/mypy for touched code, schema/import/mirror guards, candidate walk and
acceptance consistency. Heavy suites run through the coordinator's test-slot wrapper.

## Verification

strategy: candidate
gate: tester
- triage-closed-recovery-live: live — Actual terminal readiness, fresh harness session identity and HOLD behavior require an operator-driven disposable herdr client walk after merge.

## Test Plan

- Post-merge — operator-driven: run the shipped disposable closed-session recovery
  walk against the merged release candidate in herdr. Create a fixture batch/run,
  close its source pane, preview recovery (zero effects), then explicitly recover
  into `opencode --auto --model openai/gpt-6.1-sol`; verify unchanged branch/worktree,
  cursor, history, observed fresh session ownership and acknowledge/report-only HOLD.
  Exercise the documented partial-failure/repair path and verify no second launch
  or uncertain prompt replay. Record the passing walk for
  `triage-closed-recovery-live` and pass the Tester gate. Use only disposable fixtures;
  never the six real paused batches or org driver.

## Plans

| Name | Repo | Plan | Depends on |
| --- | --- | --- | --- |
| closed-session-batch-recovery | derio-net/super-fr | 2026-10-14-closed-session-batch-recovery | — |
