# Herdr control sessions

Configure a batch's `launch.harness` as `claude` or `opencode`; OpenCode's
`launch.model` is an explicit provider/model. Run dispatch/drive inside herdr.
The control session lives in the stable primary checkout, not the branch workspace
that close-out can remove. Branch work still uses fr isolation.

`post_merge_restart: idle` uses the same eligibility as `fr-herdr restart-idle
--yes`. Preview without `--yes` first. Claude resumes; managed OpenCode recovers
fresh from durable cursors, records and journals. Never restart the initial goal.
Delivered drafts HOLD; current handbacks require matching branch head and live
mergeability. Close-out pickup retains delivery/merge gates.

Drafts and command overlays can report idle, so status alone is insufficient.
OpenCode title-based readiness can precede its usable textarea. Initial dispatch,
restart and replacement wait boundedly for a rendered focused empty input region
under the expected foreground process/name/model/base-cwd identity before one prompt.
An ambiguous stalled submission is still never replayed or given an unverified Enter.
Caller/excluded panes and unknown layouts/processes are skipped; the runner never
clears drafts or answers dialogs. Failed restarts leave non-active descriptors and
recovery instructions. Inspect the pane before manually recovering it; never
blindly resend a brief with uncertain uptake. See
[`fr-herdr`](../packages/fr-herdr/README.md) for cache/observation limits.

## Audited replacement

`fr triage batch replace <id> --model <model> --reason <why>` previews a model-only
change. Add `--harness claude|opencode` to change clients, always with an explicit
target model. Add `--yes` after inspection; scope/checkout options work as in dispatch.
Ordinary batch edit remains frozen after dispatch.

Only an unmerged dispatched/pr-open herdr batch with one matching idle/done agent
can be replaced. A fresh forge branch-PR lookup is mandatory, not cached facts alone.
Replacement keeps original dispatch time, reservation, branch, workspace, PR,
tab, pane and fr-derived name. It launches fresh from the primary checkout and
reconstructs durable state, never the source transcript or initial goal.

Scope ownership precedes shared server/pane ownership; contention refuses without
input. Both OS locks are independently verified. Use reliable local
`FR_TRIAGE_LOCK_DIR` and `FR_HERDR_CACHE_DIR` when shared storage cannot enforce locks.
Judgements writers stamp schema 12 (read 1–12); engine-owned replacement
attempt/success/failure events are audit only, not dispatch/cancel transitions.

Partial failures return nonzero with pending descriptor/attempt and inspection
instructions. They never close the tab, delete transcripts/worktrees or restore the
source automatically. Inspect the surviving source, target or shell, then preview
`replace <id> --repair --reason <inspection>` and act with `--yes`. Repair sends no
prompt and launches nothing. Persisted uptake confirmation AND matching live target
are required to finalize success. An uncertain/pre-submission target must be
inspected/recovered, not blindly re-sent; returning it manually to the original
source or confirmed shell permits a failed/aborted attempt to be reconciled.
Repair promotes the descriptor after an already-saved batch success without a
duplicate success event. Restart skips unresolved descriptors.

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
A surviving item/name, reused original pane, incomplete/ambiguous observation,
caller-self target, live driver, lock contention or missing/unreadable/ambiguous
existing branch cursor refuses. Dirty work is preserved, never reset or cleaned.
Ordinary replacement still requires a matching live idle/done source; dispatch is
not recovery. Initially only an explicit OpenCode provider/model target is supported.

The fresh herdr-allocated pane starts from the stable primary checkout with `--auto`.
Its canonical item/name, existing branch/workspace, original dispatch/time/reservation,
members, dependencies, claims and PR gates remain unchanged. Only a successful
audited outcome changes effective pane ownership; a failed/pending target does not.
The observed new harness session id is attribution, not a claim on a running unit.

Every recovered session starts **HOLD: acknowledge/report-only**. It may inspect
cursor, records, journal and pending gates read-only, but may not mutate, abandon or
redispatch units, bind itself automatically, answer questions/gates, or approve/ready/
merge PRs. Release requires a **separate explicit operator instruction to that session**.
Managed reconstruction/restart begins in HOLD again, before conflict or unfinished/
delivered continuation. Recovery never restarts the org driver automatically.

Local durable recovery intent is keyed by server/socket, item and original source pane
in `FR_HERDR_CACHE_DIR` (`*.recovery.json`), **before allocation**. It retains the attempt,
branch and target model, then actual target ownership even if the first pane descriptor
or batch attempt write fails. Checkpoints include allocation-pending, prepared,
launch-started, target-ready, submission-started/uncertain and uptake-confirmed.
Inspect the error's pane/checkpoint and both stores; never delete a possibly-live target.
Preview/act `replace <id> --repair --reason <inspection> [--yes]` with the same scope/
checkout. Do not supply `--recover`, harness or model on repair. Repair discovers
uncertain allocation through fresh item-labelled rosters and launches/sends nothing.
Success needs persisted uptake AND the matching observed session id. Confirmed absent
allocation or a confirmed shell may be aborted; any later allocation requires a **new
explicit recovery act**, never an automatic retry. Unknown truth remains pending.

Automated candidate scenarios are fake-backed and prove persistence/CLI contracts,
not native terminal behavior. `bash tests/scenarios/herdr-closed-recovery-live.sh`
prints the **post-merge Tester** disposable operator walk; `--record-verdict` is for
an interactive operator with a nonempty redacted observation log. The live row stays
walk-owed until that walk passes. Never use real paused org batches for this walk.
Render/drive unification (#1216) is unrelated and outside this feature.

Run `bash tests/scenarios/herdr-opencode-live.sh` for the scoped pre-merge disposable-session walk;
use `--record-verdict` only after every check was observed and logged. Client-live
evidence remains owed before Ready, independently of installed-candidate evidence
(Refs #1089). Automated instruction tests do not claim a live pass.
Current-conflict selection/reconstruction may be checked read-only against an
existing conflicting PR: match its real head, inspect handback-before-HOLD and
obsolete-head suppression, without sending or executing its conflict instructions.
Actual merged-PR pickup/verify-merge/archive and session cleanup belong to
`herdr-opencode-closeout-live`, immediately post-merge. This split does not claim
conflict resolution or close-out was observed before merge.
