# `fr gate backfill` — bring pre-v6 owed work into the gate lanes — design

**Date:** 2026-11-01 · **Slug:** gate-backfill · **Run:** 2026-11-01-feat-gate-backfill

## 1. Goal

Work merged before v6 has no exit gates. Its owed live walks and manual operations
hide in closed issues, hand-made trackers, unticked plan phases and audit files.
`fr gate backfill` brings that debt into v6's own machinery. Afterwards every repo
has **one queue**: the triage board's *Needs you · Tester* and *Needs you · DevOps*
lanes, cleared through `fr gate pass`.

### Non-goals

- Changing the gate vocabulary or how a *new* run's exit is decided (`fr/verification/exit.py`).
- Any artifact migration. No kind's `current_version` moves, and nothing touches
  `fr/artifacts/registry.py` or `fr/artifacts/trigger.py` (a parallel run owns
  the migration gate, super-fr#1242). Pre-v5 `skipped` rows are `fr migrate
  artifacts --yes`'s job, which the per-repo chore runs first (Test Plan 1).
- Editing repo files (matrix rows, plan phases). Backfill prints those commands
  for the repo's own chore PR instead (R11).
- Fixing super-fr#1268 in `fr triage collect`. This change adopts that issue's
  rule for its own writes (R6); the collect fix stays separate.
- A dry run for `fr archive`. It is a follow-up, filed from this run's journal.

## 2. Background (read from the code)

- **What a repo owes is already folded.** `fr debt` (`fr/debt/engine.py:337`
  `compute`) builds one `DebtReport`. Its `owed` items come from `fold_owed`
  (`:120`), one item per key, with precedence journal > row > plan > issue.
  Keys, by shape:
  - `row:<id>` — a `walk-owed` row.
  - `plan:<name>#p<n>` — an open phase of a merged plan
    (`closeout.plan_sweep().merged_manual_open`, `closeout.py:192-198`). It
    holds **every** phase not locally complete, manual or agentic, despite the
    name.
  - `spec:<slug>#step<n>` — a Test Plan step recorded owed (`fr closeout outcome
    --owed`).
  - Journal `owed` entries, which carry one of these keys.
  - Open `fr:owed`/`fr:awaiting-live` issues — keyed by their `<!-- fr-owed:<key> -->`
    marker, else `issue:<owner/repo#n>` (`_issue_owed`, `:212-226`).

  `_run_branches` (`:281`) maps plan → run branch, from **live** cursors only.
- **The board's gate lanes see batch PRs only.** `fr/triage/lanes.py:32`
  `lane_of(batch, facts, …)` takes a triage `Batch`. It places a landed batch
  **whose close-out has not happened** (`:59`) in the lane its merged PR's held
  `gate:*` labels say (tester first, `:68`). `views.needs_you` (`:403`) and
  `kanban.column_of` (`kanban.py:380`) both call it. `collect._ledger_reads`
  (`collect.py:809`) reads labels only for PRs on a batch's head branch.
  **So a gate label on an old PR that no live batch holds puts nothing on the
  board.** R13 closes that gap.
- **The gate ledger is the merged PR's labels.** `fr gate pass`
  (`commands/gate_cmd.py:190`) requires `--notes`. It refuses unless the PR is
  merged and carries `gate:<g>` (`:239-241`). For `devops` it folds a run's op
  evidence, refusing when no cursor names the PR's head ref unless
  `--no-run-evidence` is given (`:103-147`). `verification/labels.py:171`
  `pass_gate` comments and swaps in `gate:<g>-passed`. The triage driver calls
  `pass_gate` too, when a batch's gated rows are walked
  (`triage_batch_cmd.py:5468-5473`). `labels.held_gates` is the one "held"
  predicate. `gate` is in `fr.artifacts.trigger.READ_ONLY_COMMANDS`: it writes
  only to the forge, with `--yes`.
- **Owed trackers, and who fr trusts.** `fr archive` files one `fr:owed` issue
  per owed action (`archive_followups.py:489` `file_owed_ends`, which calls
  `ensure_labels(FR_OWED)` before it knows whether it will create anything).
  Dedup goes through `_existing_owed` (`:454`) and `owned_owed_key` (`:425`).
  That predicate accepts an issue only when this account wrote it, it carries
  `fr:owed`, its number is numeric, and its **last line** is exactly
  `<!-- fr-owed:<key> -->`. The repo identity comes from the origin remote's
  configured URL only (`owed_identity`, `:378`). `labels.FR_AWAITING_LIVE`
  marks a merged issue whose only remaining ask is a live walk.
- **Tracking mode** is `fr.services.resolve_tracking(repo_root).type`
  (`services/resolve.py:239`), declared in `.devcontainer/fr-profiles.yaml`.
  `fr archive`'s `require_tracker` (`services/require.py:21`) reads it too.
- **Forge reads already present** (`fr/ghclient.py`): `list_linked_prs` (`:147`),
  `list_prs_by_head` (`:300`), `pr_view` (`:310`), `edit_pr_labels` (`:194`),
  `edit_issue_labels` (`:185`), `edit_issue_body` (`:215`), `comment_issue`
  (`:217`), `close_issue` (`:236`), `create_issue` (`:240`), `ensure_labels`
  (`:251`), `list_issue_comments` (`:288`), `list_issues` (`:453`),
  `viewer_login` (`:479`). **New here:** `prs_for_commit` and
  `list_merged_prs_by_label`.

### What the corpus shows (three org reconciliations and the 2026-10-13 batch audit, cited by shape only)

1. A closed issue whose `Closes` line fired on merge while its live ask was still
   unmet. All three reconciliations chose a **linked tracker** plus a link
   comment, never a reopen.
2. Unticked manual phases of merged plans with `tracking_issue: null`.
3. Walk rows that are `not-implemented` but describe a live walk (they should be
   `walk-owed`), and pre-v5 `skipped` rows.
4. Audit gaps nobody filed.
5. **Unmarked pre-v6 trackers.** A hand-made tracker exists for a phase, and
   `fr archive` filed a second, marked `fr:owed` issue for the same phase,
   because dedup cannot see a tracker without a marker.
6. **Stale unticked phases.** Several "manual pre-deployment" phases months old,
   probably done but never ticked. A naive backfill would file one noise issue
   for each.
7. **Parked areas.** Owed items in repos or areas the operator has parked must be
   recorded but not surfaced.
8. `fr archive --branch` sees only what that branch touched, so a repo-wide
   sweep is needed.

## Requirements

R1. `fr gate backfill` runs per repo from its checkout. Without `--yes` it makes no forge write of any kind, including label creation. It writes a backfill plan file outside the repo and prints a summary: every candidate on its own line, parked ones listed under their own heading.
R2. The candidates are every owed item `fr debt`'s fold yields for the whole repo, plus the entries of an optional operator manifest (`--from <yaml>`) for shapes fr cannot infer: a closed issue with an unmet ask, and an unfiled audit gap. The fold supplies walk-owed rows, open phases of merged plans, owed Test Plan steps, open journal `owed` entries and open owed issues. An `issue:` candidate that is another entry's tracker is not a candidate of its own.
R3. Each candidate's delivering PR is found by an evidence chain, first hit wins: a manifest `pr:` override; else the run cursor (live or archived) that emitted the item's plan or spec → its branch's merged PR; else the merge on the default branch of the commit that first added the item's plan or spec → the PR its subject names or the forge maps it to; else, for an issue, the merged PR linked to it. A PR is used only when the forge confirms it is merged. A hit that touched nothing outside `docs/` is a planning PR: its entry defaults to `review`. Several merged PRs at one step are an ambiguity, reported with every number. A candidate with no PR is reported and never acted on.
R4. Each candidate's gate is decided by its shape: a walk-owed row → `tester`; an open **manual** phase → `devops`; an owed Test Plan step → `devops` when its spec's run gate is `devops`, else `tester`; a journal `owed` entry by its key; a manifest entry by its `gate:`, which an ambiguous kind must state. An open agentic phase, or an `issue:` candidate without a manifest gate, has no gate: its entry defaults to `review` and `--yes` refuses it until a gate is set.
R5. The plan file holds one entry per candidate, keyed by its owed key, with a decision: `owed` (the default), `adopt <issue>`, `tick`, `na`, `park` or `review`. A manual phase older than the stale threshold defaults to `review` and shows its age and ticked-step counts. Re-running the dry run keeps the decisions already in the file for keys still owed.
R6. `--yes` applies the plan file's decisions through the forge adapter (`GhClient`) only, applying the PR and gate the operator reviewed. For an `owed` or `adopt` entry it adds `gate:<g>` to the delivering PR, files or reuses the owed tracker, links a closed issue to the tracker with a comment, and adds `fr:awaiting-live` to the tracker when only a walk remains. Every label is created only right before the first write that uses it. A PR that already carries `gate:<g>-passed` gets no write, and no tracker either.
R7. `--yes` is idempotent: a second run over the same plan file makes no forge write.
R8. fr reuses, edits and closes only trackers `owned_owed_key` accepts. Any other issue is touched only through an explicit `adopt`: fr comments on it and may add labels, never edits its body and never closes it.
R9. When an entry adopts an issue while an fr-owned tracker exists for the same key, `--yes` closes the fr-owned one as a duplicate of the adopted one, with a comment naming it.
R10. In a repo whose tracking is `none`, `--yes` writes only the PR gate labels: no tracker, no comment, no `fr:awaiting-live`. The plan file and summary still list every owed item.
R11. Backfill prints, for the repo's own chore PR, the exact repo-file commands its decisions and the repo's rows imply (§E's table): each `tick`/`na` decision's commands; each tracked row's `fr acceptance set-status --issue`; and each `not-implemented` row whose effective strategy is post-merge, moved to `walk-owed`. It never writes a repo file, and refuses a decision that has no command for its key's kind.
R12. When a post-merge gate passes on a PR, by `fr gate pass --yes` or by the triage driver, fr also closes, with a comment naming the pass, every open fr-owned owed tracker that names that PR and that gate, and prints each closed tracker's discharge command. An adopted tracker is listed with the command that closes it. `fr gate pass` on a PR that already carries `gate:<g>-passed` and no `gate:<g>` runs only this close, so a failed close can be retried.
R13. The board's Needs-you · Tester and Needs-you · DevOps lanes list every merged PR in a collected repo whose labels hold `gate:tester` or `gate:devops` unpassed, whether or not a batch delivered it. Each PR is listed once, in Tester while tester holds, else in DevOps. A batch PR is shown through its batch whenever its batch is in a lane. A repo whose gate-labelled PRs could not be read is reported on the board, never shown as an empty lane.
R14. `fr gate` stays forge-only and stays in `READ_ONLY_COMMANDS`. No artifact kind's version moves.
R15. `--yes` refuses before any write when the plan file is missing or names another repo. It skips an entry, with a line naming why, when that entry's PR or gate re-resolves differently from what the plan file recorded, when its adopt target is in another repo, does not exist, is closed or is an fr-owned tracker, or when its fr-owned tracker's PR marker names a different PR.

## 3. Design

### A. Command surface (`fr gate backfill`, in `commands/gate_cmd.py`)

```
fr gate backfill [--from <manifest.yaml>] [--plan <path>] [--stale-days N]
                 [--repo OWNER/REPO] [--host H] [--yes]
```

- The repo is `owed_identity(repo_root)`, the same trust rule `fr archive` uses.
  `--repo` must agree with it or the command is refused.
- **The dry run** (no `--yes`) computes the candidates (B–D), merges them with
  any existing plan file (E), writes the plan file and prints the summary plus
  the R11 commands. The forge is used for **reads only**. A failed read degrades
  one candidate ("PR unconfirmed: <why>"), never the whole run.
- **`--yes`** reads the plan file and re-computes the candidates. It applies
  only entries whose key is still a candidate, subject to R15's refusals and
  skips. A plan entry whose key is no longer owed is skipped with a line. A new
  candidate absent from the plan is reported, not acted on, until a dry run
  records a decision for it. **What is applied is what the operator reviewed:**
  the recorded `pr` and `gate`. A differing re-resolution skips the entry
  (R15) rather than silently switching PR.
- The default plan path is `$HOME/.cache/fr/gate-backfill/<owner--repo>/plan.yaml`.
  It is never in the repo, so `gate` remains forge-only (R14).
- The engine lives in a new package `fr/gatebackfill/`: `model.py` (Candidate,
  PlanEntry, PlanFile, Manifest, all strict), `candidates.py` (B), `delivery.py`
  (C), `trackers.py` (F), `apply.py` (G) and `render.py` (summary and R11
  commands). It is pure given a forge port, a git port and the clock, as
  `fr/debt` is.

### B. Candidates (R2)

- **From `fr debt`:** call `fr.debt.engine.compute(repo_root, forge=…, now=…)`
  and take `report.owed`. The fold is repo-wide (not per branch), so the
  corpus's `--branch` blind spot does not arise. Each `OwedItem` becomes a
  `Candidate(key, source, title, how, ref)`. For a `plan:` key the phase YAML
  is read too (`[manual]` header, age, ticked counts), which D and E use.
- **From the manifest** (`--from`, strict YAML, `schema: 1`):

  ```yaml
  schema: 1
  items:
    - key: issue:example-org/widgets#37     # unique; becomes the owed key
      kind: closed-issue | audit-gap | walk | op
      title: "deadman host death is noticed live"
      issue: 37            # closed-issue: the closed issue
      pr: 89               # optional delivering-PR override (R3)
      gate: tester         # required for audit-gap; else from kind (walk, closed-issue → tester; op → devops)
      walk_only: true      # optional: only a walk remains (→ fr:awaiting-live)
  ```

  A key the fold already holds is an error naming both sources. An unknown field
  is refused, as in every fr manifest.
- **`walk_only`** defaults to true for `row:` candidates and `walk` and
  `closed-issue` entries, and false for everything else.
- **Tracker issues are not candidates (R2).** An `issue:<ref>` candidate is
  dropped when its ref is another entry's `adopt` target (from the existing plan
  file), or when it is a backfill tracker (it carries a PR marker, §F). When it
  appears among another entry's `tracker.candidates` (§E), it stays an entry but
  defaults to `review` with the note "looks like the tracker of <key>". The
  operator then adopts it from that entry, and the next dry run drops it.

### C. The delivering PR (R3) — `delivery.py`

The steps run in order, and the first step with a hit wins. Each hit records
its `basis`, which the summary and the plan file show.

1. **`manifest`** — the entry's `pr:`.
2. **`run`** — every run cursor, live (`docs/superpowers/runs/`) and archived
   (`implemented/runs/`), read through one shared helper that `gate_cmd._cursors`
   is moved onto, whose emitted `plan` or `spec` is the candidate's. A `row:`
   or `spec:` candidate maps to its origin spec, and to the plans that spec's
   Implementation Plans table names. For each matching branch, take
   `list_prs_by_head(repo, branch)`'s merged PRs.
3. **`commit`** — for each of the candidate's plan dirs (else its spec file): the
   oldest commit on the default ref that added it
   (`git log --diff-filter=A --format=%H --reverse <ref> -- <path>`), then the
   first merge into the default ref that contains it
   (`git log --ancestry-path --first-parent --merges <sha>..<ref>`, oldest; the
   commit itself when it is on the first-parent line, e.g. a squash). Its
   subject's `(#N)` or `Merge pull request #N` names the PR (the pattern
   `scripts/release.py:391` uses). When the subject names none, ask the new
   `GhClient.prs_for_commit(repo, sha)` (GitHub
   `GET repos/{repo}/commits/{sha}/pulls`; glab and tea raise
   `UnsupportedForgeOperation`, so the step yields nothing on those forges).
4. **`issue`** — for a closed-issue entry or an `issue:` candidate,
   `list_linked_prs(repo, n)` filtered to merged.

At any step, several distinct merged PRs are an **ambiguity**: the entry records
every number, defaults to `review`, and stays unwritten until the operator sets
`pr:` in a manifest. Every hit is confirmed through `pr_view`, and a state other
than `MERGED` drops it with its reason.

**Planning PRs.** A plan merged before its code (the `fr apply`/VK dispatch
flows, where the plan must reach the default branch first) makes the `commit`
step name the plan's own PR. So for a `commit` or `run` hit, the merge commit's
diff against its first parent is read locally
(`git diff --name-only <merge>^1 <merge>`). A PR that touched nothing outside
`docs/` is recorded `planning: true`, and its entry defaults to `review` with the
note "planning PR; set pr: to the delivering one". It is never applied as
`owed` unless the operator, having checked, sets the decision.

An unresolved candidate is listed under "no delivering PR: add `pr:` in a
manifest" and is never written.

### D. Gate per candidate (R4)

`gate_for(candidate)` is pure and returns a post-merge gate, or `None`:

| Key / kind | Gate |
|---|---|
| `row:<id>` | `tester` |
| `plan:<name>#p<n>`, phase header `[manual]` | `devops` |
| `plan:<name>#p<n>`, agentic phase | `None` (unfinished work, not an operation) |
| `spec:<slug>#step<n>` | `devops` when `exit_for_spec(spec).run_gate == "devops"`, else `tester` |
| journal `owed` entry | by its key, as above |
| `issue:<ref>` | manifest `gate:`, else `None` |
| manifest `walk` / `closed-issue` | `gate:` if given, else `tester` |
| manifest `op` | `gate:` if given, else `devops` |
| manifest `audit-gap` | `gate:`, required (refused without) |

A `None` gate makes the entry default to `review` with its reason. `--yes`
refuses an `owed`/`adopt` entry whose gate is still `None`; the operator writes
one into the plan file's `gate:`. Only `POST_MERGE_GATES` are accepted.

### E. The plan file, its decisions and their commands (R5, R11)

```yaml
schema: 1
repo: example-org/widgets
generated_at: 2026-11-01T12:00:00Z
entries:
  - key: plan:2026-04-02-fleet#p3
    title: "fleet: manual phase 3 is not ticked"
    gate: devops
    pr: {number: 41, basis: commit, planning: false}
    tracker: {ref: null, candidates: ["example-org/widgets#56"]}   # unmarked look-alikes
    age_days: 212
    ticked: "0/4"
    note: ""
    decision: review          # owed | adopt <ref> | tick | na | park | review
```

- **Defaults:** `owed`, except: `review` for a manual phase whose plan's last
  commit is older than `--stale-days` (default: `fr debt`'s `stale_days`), with
  its `age_days` and `ticked` (from the plan's phase YAML); `review` for a `None`
  gate (D), an ambiguity or a planning PR (C), and a look-alike `issue:`
  candidate (B).
- **`tracker.candidates`** are open issues that look like an existing tracker
  for this item but that `owned_owed_key` does not accept: the body or title
  names the plan slug together with `phase <n>` / `p<n>`, or the row id, or the
  manifest's issue number. They are **suggestions only**. fr never adopts on a
  heuristic (corpus 5). The operator writes `decision: adopt example-org/widgets#56`.
- **Merge on re-run:** a dry run keeps an existing entry's `decision`, its
  `adopt` target and any `gate:` the operator wrote, when its key is still a
  candidate. It refreshes every other field and drops keys no longer owed.
- **Decisions and what they produce:**

| Key kind | `owed` / `adopt` | `tick` | `na` | `park` | `review` |
|---|---|---|---|---|---|
| `plan:` (live plan) | §G | one `fr plan edit <plan> --tick P<n>.T<t>.S<s>` per unticked step | `fr plan edit <plan> --tick …` per step, with `--note "n/a: <reason>"` | listed under *Parked* | skipped by `--yes` |
| `plan:` (archived plan) | §G | refused: an archived plan is frozen | refused | listed | skipped |
| `spec:` step | §G | refused (record it ran: `fr closeout outcome --ran`) | `fr closeout outcome --spec <spec> --step <n> --na --reason "<reason>"` | listed | skipped |
| `row:` | §G | refused | `fr acceptance set-status --id <row> --status manual --notes "<reason>"` | listed | skipped |
| `issue:` / manifest | §G | refused | refused (close it by hand: printed) | listed | skipped |

  A refused cell exits 2 for that entry during the dry run's validation, naming
  the decisions its kind accepts. `<reason>` comes from the entry's `note`,
  which `na` requires.
- **Row reconcile (R11, corpus 3), listed but never a plan entry:** each
  `not-implemented` row whose effective strategy
  (`fr.verification.effective.effective_strategy`) is post-merge prints
  `fr acceptance set-status --id <row> --status walk-owed --notes "post-merge walk owed (gate backfill)"`.
  After a `--yes`, each `row:` entry with a tracker prints
  `fr acceptance set-status --id <row> --issue <tracker> --notes "tracked by <tracker>"`.

### F. Trackers and markers (R6, R8, R9)

Backfill files its trackers itself (`trackers.py`), not through
`file_owed_ends`: the body differs, and the labels must stay lazy (R6).

- A **backfill tracker** is an `fr:owed` issue written by this account. Its body
  ends with two marker lines, the PR marker before the owed marker, so
  `owned_owed_key` (last-line rule) accepts it unchanged:

  ```
  Owed: <title>

  Delivered by #41 (merged). Held by gate:devops on that PR; clear it with the
  pass command below once done.

  `fr gate pass --pr 41 --gate devops --notes "<what you did>" --no-run-evidence`

  <!-- fr-gate:devops pr:41 -->
  <!-- fr-owed:plan:2026-04-02-fleet#p3 -->
  ```

  `fr_gate_marker(body) -> (gate, pr) | None` reads the second-to-last line,
  exact match only. It is one function, shared by B, F and H.
- **The pass command fr prints** (tracker body, board reason, summary) always
  carries `--notes "<what passed it>"`. For `devops` it adds `--run <id>` when a
  cursor names the PR's head ref, else `--no-run-evidence`. A pre-fr-ops run's
  cursor has no ops, so `devops_blockers` reads only its devops-gated Test Plan
  steps, which pre-v6 specs do not have. Where it does find blockers, the
  refusal stands, and the operator closes them through `fr ops gate`.
- **Reuse:** `_existing_owed` finds the key's fr-owned tracker. A reused tracker
  with no PR marker gets the backfill body rewritten (it is fr-owned, so its
  body is fr's to edit, R8). One already carrying this PR and gate is left
  alone (R7). One naming a different PR is skipped (R15).
- **Adopt:** the adopted issue is never edited and never closed by fr. `--yes`
  posts one comment ending with `<!-- fr-gate-adopt:<key> gate:<g> pr:<n> -->`,
  adds `fr:owed` (so §H can find it without reading every issue's comments),
  and adds `fr:awaiting-live` when `walk_only`. When this account's comment
  with that exact marker already exists, nothing is posted (R7). If an fr-owned
  tracker exists for the same key, it is closed with "Duplicate of <adopted
  ref>; tracking moved there." (R9).
- **Closed issue:** after its tracker is filed, reused or adopted, the closed
  issue gets one link comment ending with `<!-- fr-gate-link:<key> tracker:<ref> -->`.
  It is never reopened (corpus 1).

### G. Apply order and idempotency (R6, R7, R10)

For each `owed` / `adopt` entry with a confirmed PR and a gate, in key order:

1. **The PR.**
   - Already `gate:<g>-passed`: no write at all for this entry (steps 2–3
     skipped too). Report "PR #n already passed <g>" with the key's discharge
     command (H), so the stale debt is discharged rather than re-filed.
   - Already `gate:<g>`: no write.
   - Otherwise add `gate:<g>`. `ensure_labels` runs for that label only right
     before the first PR in this run that needs it (#1268's rule).
2. **The tracker**, unless tracking is `none`: per §F, then `fr:awaiting-live`
   when `walk_only` and absent, then the closed-issue link comment.
   `fr:owed` and `fr:awaiting-live` are each ensured just before the first
   create or label write that uses them.
3. **Errors.** Each forge error, including `UnsupportedForgeOperation` ("this
   forge cannot <op>"), is recorded on its entry and the run continues. The
   exit code is 1 when any entry failed, else 0.

An unreadable services declaration is a refusal before any write, as in
`fr archive`.

### H. Closing trackers when a gate passes (R12)

A new helper `close_gate_trackers(client, repo, pr, gate, notes) -> list[Closed]`
sits beside `pass_gate` in `fr/verification/labels.py`. **Both pass routes call
it after `pass_gate`:** `fr gate pass --yes`, and the triage driver's
rows-walked pass (`triage_batch_cmd.py:5468-5473`). Its steps:

1. List the repo's open issues labelled `fr:owed` (`OWED_ISSUE_FIELDS`; adopt
   adds the label, §F, so this bounds the read).
2. Close each issue that `owned_owed_key(issue, me)` accepts **and** whose
   `fr_gate_marker` names this PR and gate. The comment is "Gate <g> passed on
   #<pr>: <notes>".
3. For each other issue in that list carrying this account's
   `fr-gate-adopt:<key> gate:<g> pr:<n>` comment for this PR and gate (one
   `list_issue_comments` per such issue), print its `gh issue close` line.
4. For every closed or listed tracker, print its key's discharge command:
   `fr acceptance set-status --id <row> --walk … --status walked` for `row:`,
   `fr journal resolve --scope … --id … --state fixed` for a journal entry,
   `fr closeout outcome … --ran` for `spec:`, `fr plan edit --tick …` for
   `plan:`. Without that, the next backfill or `fr archive` would re-file the
   key.

A failure to list or close issues is reported and never reverses the pass.
**Retry:** `fr gate pass` on a merged PR that already carries `gate:<g>-passed`
and no `gate:<g>` no longer refuses. It prints "gate <g> already passed on
#<pr>; closing its trackers" and runs only this helper (a dry run without
`--yes`). A PR carrying neither label is still refused. The dry run of
`fr gate pass` lists what it would close.

### I. The board shows gate-labelled PRs (R13)

- **Read.** A new `GhClient.list_merged_prs_by_label(repo, label, limit) ->
  list[dict]`. On GitHub it is `gh pr list --repo <r> --state merged --label <l>
  --limit <n> --json <PR_LIST_FIELDS>,labels`; the REST path is
  `GET repos/{r}/issues?labels=<l>&state=closed`, filtered to merged pull
  requests. glab and tea raise `UnsupportedForgeOperation`. The triage `Forge`
  protocol gains the keyword-only `list_merged_prs_by_label(*, repo, label,
  limit)`, and `ClientForge` wraps it in `_forge_errors()` like every other read.
- **Collect.** Per collected repo, call it for `gate:tester` and for
  `gate:devops`, **dedupe by `(repo, number)`**, keep the PRs whose
  `held_gates(labels)` is non-empty, and store them in a new
  `Facts.gated_prs: list[PullRequest]`.
  - A list that returns exactly its limit adds a `Truncation` with a new
    `TruncatedList` value `gated-prs`.
  - A read that fails or is unsupported adds an entry to a new
    `Facts.gated_unread: list[GatedUnread]` (`repo`, `why`), whose `describe()`
    reads "gate-labelled PRs of <repo> not read: <why>".
  - A partial collect (`--only`) carries the previous facts' `gated_prs` and
    `gated_unread` for carried repos, as `_kept_links` does for links.
  - `FACTS_SCHEMA` moves to the next free number (13 today), and the reader
    keeps accepting older schemas, where both fields default to `[]`.
- **Lanes.** `lanes.gated_pr_lane(pr) -> LaneVerdict | None` holds the
  held-gate rule of `lane_of` (tester first, else devops). `lane_of`'s landed
  branch calls it, so both read one rule. `views.needs_you` and `kanban` add one
  Need/card per `gated_prs` entry, **unless its `(repo, number)` is the PR of a
  batch that `lane_of` placed in a lane, or whose ledger is unknown**
  (`ledger-unread`). A batch PR whose batch closed out long ago therefore still
  appears, through `gated_prs`. The ref is `PR #n`, the href the PR URL, and the
  reason "merged, held by gate:<g>" followed by §F's pass command.
- **Unread.** Each `gated_unread` entry is one Need of kind `gated-unread` ("Gate
  labels unread"), so a repo with no read never looks like an empty lane.

## 4. Decisions taken in this design (agent, from the corpus update; for spec review)

- **d10 (corpus 5):** an unmarked existing tracker is adopted only on an explicit
  `adopt` decision. Look-alikes are suggested, never auto-adopted. Adoption
  closes fr's own duplicate (R9).
- **d11 (corpus 3):** issues written by others are never reused, edited or
  closed. `adopt` limits fr to a comment and labels.
- **d12 (corpus 6):** the review step is the plan file itself (dry run → edit →
  `--yes`). A stale manual phase defaults to `review`, and `--yes` skips
  `review`.
- **d13 (corpus 7):** parked scope is a `park` decision. It persists across
  dry runs, writes nothing, and is listed under its own heading.
- **d14 (corpus 1):** `fr archive --dry-run` is filed as a follow-up, not built
  here. Backfill gives the sweep its preview.

## 5. Risks

- **Wrong delivering PR.** The chain never guesses (no "newest PR touching the
  path" fallback). Planning PRs and ambiguities default to `review`, every hit
  records its basis, the plan file shows it before any write, and `--yes`
  applies only the PR that was reviewed (R15).
- **Facts schema collision with a parallel PR** (a known trap). Renumber to
  main's next number at merge time; the fixtures pin the number in one place.
- **Mass labelling noise.** The dry run plus `review` defaults; `park` for
  parked areas.

## Verification

strategy: candidate
- gate-backfill-dry-run-plan: candidate — scenario runs a dry run over a fixture repo with a recording `gh` and checks the plan file, the summary and that no write was made
- gate-backfill-apply-ledger: candidate — scenario applies an edited plan file with `--yes` against the recording `gh`, then re-applies and checks no second write
- gate-backfill-delivering-pr: none — unit tests drive the evidence chain over fixture git histories (squash, merge commit, planning PR, ambiguity) and a fake forge; a scenario adds nothing the fixtures do not
- gate-backfill-tracker-trust: none — unit tests drive adopt, reuse, duplicate close and others' issues against a fake client
- gate-pass-closes-backfill-trackers: none — unit tests drive `fr gate pass`, its retry and the driver's pass against a fake client holding marked, unmarked, adopted and foreign trackers
- board-lanes-gated-prs: none — unit tests run collect over a fake forge and render the lanes from fixture facts, including a closed-out batch PR and a PR holding both gates
- gate-backfill-first-real-sweep: live — only a real repo's pre-v6 history and forge show the chain and the lanes working end to end
gate: tester

## 6. Test Plan (post-merge, operator-driven)

1. **First real sweep (walked on first real use).** In one repo of the corpus,
   during its planned per-repo chore (isolation → `fr migrate artifacts --yes`
   → archive → row reconcile → chore PR), run `fr gate backfill`, review the
   plan file (adopt the hand-made trackers, `review` → tick/na/owed), run
   `--yes`, then `fr triage collect` and open the board. Pass: every confirmed
   `owed`/`adopt` entry's PR carries its gate label and shows in the right
   Needs-you lane; re-running `--yes` writes nothing; one `fr gate pass` closes
   that PR's fr-owned trackers. Row: `gate-backfill-first-real-sweep`.
   **Cost:** none beyond the sweep itself (no rehearsal repo). It is walked on
   the first real sweep, and the tester gate stays held until then.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-11-01-gate-backfill | `derio-net/super-fr` | `2026-11-01-gate-backfill` | — |
