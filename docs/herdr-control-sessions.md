---
title: "Herdr control sessions"
tldr: |
  Configure a batch's launch harness, run dispatch and drive inside herdr, and keep the control session in the stable primary checkout.
standalone_style: broadsheet
covers:
  - packages/fr-herdr/src/**
  - packages/fr/src/fr/triage/batch*.py
  - packages/fr/src/fr/commands/triage_batch_cmd.py
reviewed: 2026-11-12 placement-resolver phase 2, artifact directories now come from fr.artifacts.paths; the paths and behaviour this page describes are unchanged
---

# Herdr control sessions

Configure a batch's `launch.harness` as `claude` or `opencode`; OpenCode's
`launch.model` is an explicit provider/model. Run dispatch/drive inside herdr.
The control session lives in the stable primary checkout, not the branch workspace
that close-out can remove. Branch work still uses fr isolation.

`post_merge_restart: idle` uses the same eligibility as `fr-herdr restart-idle
--yes`. Preview without `--yes` first. Claude resumes; managed OpenCode recovers
fresh from durable cursors, records and journals. Never restart the initial goal.

Delivered drafts HOLD. A current handback needs a branch head that matches, and live
mergeability. Close-out pickup keeps the delivery/merge gates.

Drafts and command overlays can report idle, so status alone is not enough.
OpenCode title-based readiness can come before its usable textarea. Before one prompt,
initial dispatch, restart and replacement wait, for a bounded time, for a rendered focused
empty input region. That region must be under the expected foreground
process/name/model/base-cwd identity. An ambiguous stalled submission is still never
replayed or given an unverified Enter.

Caller/excluded panes and unknown layouts/processes are skipped. The runner never
clears drafts or answers dialogs. Failed restarts leave non-active descriptors and
recovery instructions. Inspect the pane before you recover it manually. Never
blindly resend a brief with uncertain uptake. See
[`fr-herdr`](../packages/fr-herdr/README.md) for cache/observation limits.

## Audited replacement

`fr triage batch replace <id> --model <model> --reason <why>` previews a model-only
change. Add `--harness claude|opencode` to change clients, always with an explicit
target model. Add `--yes` after inspection; scope/checkout options work as in dispatch.
Ordinary batch edit remains frozen after dispatch.

Only an unmerged dispatched/pr-open herdr batch with one idle/done agent that matches
can be replaced. A fresh forge branch-PR lookup is mandatory, not cached facts alone.
Replacement keeps original dispatch time, reservation, branch, workspace, PR,
tab, pane and fr-derived name. It launches fresh from the primary checkout and
reconstructs durable state, never the source transcript or initial goal.

Scope ownership comes before shared server/pane ownership. On contention, the command
stops without input. Both OS locks are independently verified. Use reliable local
`FR_TRIAGE_LOCK_DIR` and `FR_HERDR_CACHE_DIR` when shared storage cannot enforce locks.
Judgements writers stamp schema 12 (read 1–12); engine-owned replacement
attempt/success/failure events are audit only, not dispatch/cancel transitions.

Partial failures return nonzero with a pending descriptor/attempt and inspection
instructions. They never close the tab, delete transcripts/worktrees or restore the
source automatically. Inspect the source, target or shell that is still there. Then preview
`replace <id> --repair --reason <inspection>` and act with `--yes`. Repair sends no
prompt and launches nothing.

To finalize success, fr needs persisted uptake confirmation AND a live target that matches.
An uncertain/pre-submission target must be inspected/recovered, not blindly re-sent.
You can return it manually to the original source or to a confirmed shell. That lets fr
reconcile a failed/aborted attempt. Repair promotes the descriptor after an already-saved
batch success, without a duplicate success event. Restart skips unresolved descriptors.

## Closed-source recovery (explicit, held)

When a dispatched/pr-open unmerged herdr batch's control pane is **positively absent**,
preview `fr triage batch replace <id> --recover --harness opencode --model
openai/gpt-6.1-sol --reason <why> --repo <owner/repo> --checkout <primary-clone>`.
Use the exact scope's `--org` instead of `--repo` for an org scope, and its `--dir`
when state is stored explicitly. Do not accidentally select a similarly named batch
in another scope. Add `--yes` only as a separate operator approval after inspection.
The preview writes/sends nothing; same-model recovery is allowed.

Recovery observes complete fresh global **pane**, **tab** and **agent** rosters.
Shell panes count: tab labels join to panes by `tab_id`, never guessed pane ids.
Recovery stops on any of these: an item/name that still exists, a reused original pane,
an incomplete/ambiguous observation, or a caller-self target. It also stops on a live driver,
lock contention, or a branch cursor that is absent, unreadable or ambiguous.

Dirty work is preserved, never reset or cleaned.
Ordinary replacement still needs a live idle/done source that matches; dispatch is
not recovery. Initially only an explicit OpenCode provider/model target is supported.

The fresh herdr-allocated pane starts from the stable primary checkout with `--auto`.
These stay unchanged: its canonical item/name, its current branch/workspace, the original
dispatch/time/reservation, and the members, dependencies, claims and PR gates. Only a successful
audited outcome changes effective pane ownership; a failed/pending target does not.
The observed new harness session id is attribution, not a claim on a unit that runs.

Every recovered session starts **HOLD: acknowledge/report-only**. It may inspect the
cursor, records, journal and pending gates read-only. It may not mutate, abandon or
redispatch units, or bind itself automatically. It may not answer questions/gates, or approve/ready/
merge PRs.

Release needs a **separate explicit operator instruction to that session**.
Managed reconstruction/restart begins in HOLD again, before conflict or unfinished/
delivered continuation. Recovery never restarts the org driver automatically.

Local durable recovery intent is keyed by server/socket, item and original source pane
in `FR_HERDR_CACHE_DIR` (`*.recovery.json`), **before allocation**. It keeps the attempt,
branch and target model. Then it keeps actual target ownership, even if the first pane
descriptor or batch attempt write fails. Checkpoints include allocation-pending, prepared,
launch-started, target-ready, submission-started/uncertain and uptake-confirmed.

Inspect the error's pane/checkpoint and both stores. Never delete a possibly-live target.
Preview/act `replace <id> --repair --reason <inspection> [--yes]` with the same scope/
checkout. Do not supply `--recover`, harness or model on repair. Repair finds
uncertain allocation through fresh item-labelled rosters and launches/sends nothing.

Success needs persisted uptake AND the observed session id that matches. Confirmed absent
allocation or a confirmed shell may be aborted. Any later allocation needs a **new
explicit recovery act**, never an automatic retry. Unknown truth stays pending.

Automated candidate scenarios are fake-backed and prove persistence/CLI contracts,
not native terminal behavior. `bash tests/scenarios/herdr-closed-recovery-live.sh`
prints the **post-merge Tester** disposable operator walk; `--record-verdict` is for
an interactive operator with a nonempty redacted observation log. The live row stays
walk-owed until that walk passes. Never use real paused org batches for this walk.
Render/drive unification (#1216) is unrelated and outside this feature.

Run `bash tests/scenarios/herdr-opencode-live.sh` for the scoped pre-merge disposable-session walk;
use `--record-verdict` only after every check was observed and logged. Client-live
evidence stays owed before Ready, independently of installed-candidate evidence
(Refs #1089). Automated instruction tests do not claim a live pass.

Current-conflict selection/reconstruction may be checked read-only against a PR that
already has a conflict. Match its real head, and inspect handback-before-HOLD and
obsolete-head suppression. Do not send or execute its conflict instructions.
Actual merged-PR pickup/verify-merge/archive and session cleanup belong to
`herdr-opencode-closeout-live`, immediately post-merge. This split does not claim
conflict resolution or close-out was observed before merge.
