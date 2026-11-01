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
- Any artifact migration. No kind's `current_version` moves, nothing touches
  `fr/artifacts/registry.py` or `fr/artifacts/trigger.py` (a parallel run owns the
  migration gate, super-fr#1242).
- Editing repo files (matrix rows, plan phases). Backfill prints those commands
  for the repo's own chore PR instead (R11).
- Fixing super-fr#1268 in `fr triage collect`. This change adopts that issue's
  rule for its own writes (R6); the collect fix stays separate.
- A dry run for `fr archive`. It is a follow-up, filed from this run's journal.

## 2. Background (read from the code)

- **What a repo owes is already folded.** `fr debt` (`fr/debt/engine.py:337`
  `compute`) builds one `DebtReport`. Its `owed` items come from `fold_owed`
  (`:120`), one item per key, with precedence journal > row > plan > issue. The
  keys are `row:<id>` for `walk-owed` rows, `plan:<name>#p<n>` for an unticked
  manual phase of a merged plan (`closeout.plan_sweep().merged_manual_open`),
  journal `owed` entries, and open `fr:owed`/`fr:awaiting-live` issues (keyed by
  their `<!-- fr-owed:<key> -->` marker, else `issue:<ref>`). It also maps
  plan → run branch (`_run_branches`, `:281`).
- **The board's gate lanes see batch PRs only.** `fr/triage/lanes.py:32`
  `lane_of(batch, facts, …)` takes a triage `Batch`. A landed batch whose merged
  PR's labels hold `gate:tester`/`gate:devops` sits in the matching lane.
  `views.needs_you` and `kanban.column_of` (`kanban.py:371`) both call it.
  `collect._ledger_reads` (`collect.py:809`) reads labels only for PRs of a
  batch's head branch. **So adding a gate label to an old PR that was never in a
  batch puts nothing on the board.** R13 closes that gap.
- **The gate ledger is the merged PR's labels.** `fr gate pass`
  (`commands/gate_cmd.py:190`) refuses unless the PR is merged and carries
  `gate:<g>`, then `verification/labels.py:171` `pass_gate` comments and swaps
  in `gate:<g>-passed`. `labels.held_gates` is the one "held" predicate. `gate`
  is in `fr.artifacts.trigger.READ_ONLY_COMMANDS`: it writes only to the forge,
  with `--yes`.
- **Owed trackers, and who fr trusts.** `fr archive` files one `fr:owed` issue
  per owed action (`archive_followups.py:489` `file_owed_ends`), deduplicated by
  `_existing_owed` (`:454`) through `owned_owed_key` (`:425`). That predicate
  accepts an issue only when this account wrote it, it carries `fr:owed`, its
  number is numeric, and its **last line** is exactly `<!-- fr-owed:<key> -->`.
  The repo identity comes from the origin remote's configured URL only
  (`owed_identity`, `:378`). `labels.FR_AWAITING_LIVE` marks a merged issue
  whose only remaining ask is a live walk.
- **Forge reads already present.** `GhClient.list_linked_prs` (the PRs linked to
  an issue), `list_prs_by_head`, `pr_view` (state, labels, head ref),
  `edit_pr_labels`, `edit_issue_labels`, `comment_issue`, `create_issue`,
  `close_issue`, `ensure_labels`, `list_issues`, `viewer_login`. **Not present:**
  a commit → PR lookup and a list of merged PRs by label.

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

R1. `fr gate backfill` runs per repo from its checkout. Without `--yes` it makes no forge write of any kind, including label creation. It writes a backfill plan file outside the repo and prints a summary of every candidate.
R2. The candidates are every owed item `fr debt`'s fold yields for the whole repo (walk-owed rows, unticked manual phases of merged plans, open journal `owed` entries, open owed issues), plus the entries of an optional operator manifest (`--from <yaml>`) for shapes fr cannot infer: a closed issue with an unmet ask, and an unfiled audit gap.
R3. Each candidate's delivering PR is found by an evidence chain: a manifest `pr:` override, else the run cursor's branch → its merged PR, else the commit that first added the item's plan or spec on the default branch → the PR its subject names or the forge maps it to, else (for an issue) the merged PR linked to it. A PR is used only when the forge confirms it is merged. A candidate with no PR is reported and never acted on.
R4. Each candidate's gate is decided by its shape: a walk-owed row → `tester`; a manual phase → `devops`; a journal `owed` entry by its key (`row:` → `tester`, `plan:` → `devops`); a manifest entry by its `gate:`, which a manifest entry of an ambiguous kind must state.
R5. The plan file holds one entry per candidate, keyed by its owed key, with a decision: `owed` (the default), `adopt <issue>`, `tick`, `na`, `park` or `review`. A manual phase older than the stale threshold defaults to `review` and shows its age and ticked-step counts. Re-running the dry run keeps the decisions already in the file for keys still owed.
R6. `--yes` applies the plan file's decisions through the forge adapter (`GhClient`) only. For an `owed` or `adopt` entry it adds `gate:<g>` to the delivering PR, files or reuses the owed tracker, links a closed issue to the tracker with a comment, and adds `fr:awaiting-live` to the tracker when only a walk remains. A label is created only right before a write that uses it.
R7. `--yes` is idempotent: a second run over the same plan file makes no forge write.
R8. fr reuses, edits and closes only trackers `owned_owed_key` accepts. Any other issue is touched only through an explicit `adopt`: fr comments on it and may add labels, never edits its body and never closes it.
R9. When an entry adopts an issue while an fr-owned tracker exists for the same key, `--yes` closes the fr-owned one as a duplicate of the adopted one, with a comment naming it.
R10. In a repo whose tracking is `none`, `--yes` writes only the PR gate labels: no tracker, no comment, no `fr:awaiting-live`. The plan file and summary still list every owed item.
R11. Backfill prints, for the repo's own chore PR, the exact repo-file commands its decisions imply: a row's `fr acceptance set-status --issue`, a `not-implemented` row that names a live walk moving to `walk-owed`, `tick` and `na` decisions as their `fr plan edit --tick` / `fr closeout outcome --na` lines. It never writes a repo file.
R12. `fr gate pass --yes` on a PR also closes, with a comment naming the pass, every open fr-owned owed tracker that names that PR and that gate. An adopted tracker is listed with the command that closes it.
R13. The board's Needs-you · Tester and Needs-you · DevOps lanes list every merged PR in a collected repo whose labels hold `gate:tester` or `gate:devops` unpassed, whether or not a batch delivered it, and never list one PR twice. A forge that cannot list PRs by label leaves a collect warning, never an empty lane presented as complete.
R14. `fr gate` stays forge-only and stays in `READ_ONLY_COMMANDS`. No artifact kind's version moves.

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
- **`--yes`** re-computes the candidates, reads the plan file, and applies only
  entries whose key is still a candidate. A plan entry whose key is no longer
  owed is skipped with a line. A new candidate absent from the plan is reported,
  not acted on, until a dry run records a decision for it.
- The default plan path is `$HOME/.cache/fr/gate-backfill/<owner--repo>/plan.yaml`.
  It is never in the repo, so `gate` remains forge-only (R14).
- The engine lives in a new package `fr/gatebackfill/`: `model.py` (Candidate,
  PlanEntry, PlanFile, all strict), `candidates.py` (B), `delivery.py` (C),
  `trackers.py` (F), `apply.py` (G) and `render.py` (summary and R11 commands).
  It is pure given a forge port and the clock, as `fr/debt` is.

### B. Candidates (R2)

- **From `fr debt`:** call `fr.debt.engine.compute(repo_root, forge=…, now=…)`
  and take `report.owed`. The fold is repo-wide (not per branch), so the
  corpus's `--branch` blind spot does not arise. Each `OwedItem` becomes a
  `Candidate(key, source, title, how, ref)`.
- **From the manifest** (`--from`, strict YAML, `schema: 1`):

  ```yaml
  schema: 1
  items:
    - key: issue:example-org/widgets#37     # free, unique; becomes the owed key
      kind: closed-issue | audit-gap | walk | op
      title: "deadman host death is noticed live"
      issue: 37            # closed-issue: the closed issue
      pr: 89               # optional delivering-PR override (R3)
      gate: tester         # required for audit-gap; else from kind (walk→tester, op→devops)
      walk_only: true      # optional: only a walk remains (→ fr:awaiting-live)
  ```

  A key the fold already holds is an error naming both sources. An unknown field
  is refused, as in every fr manifest.
- **`walk_only`** defaults to true for `row:` candidates and `walk` entries, and
  false for manual phases and `op`.

### C. The delivering PR (R3) — `delivery.py`

The steps run in order, and the first hit wins. Each hit records its `basis`,
which the summary shows:

1. **`manifest`** — the entry's `pr:`.
2. **`run`** — the run cursor that emitted the item's plan (`_run_branches`,
   live and archived cursors), then `list_prs_by_head(repo, branch)` and its
   merged PR.
3. **`commit`** — the oldest commit on the default ref that added the item's plan
   dir (for a row, the plan(s) its origin spec's Implementation Plans table
   names, else the spec file itself). Take its first-parent merge into the
   default ref. A subject `(#N)` or `Merge pull request #N` names the PR (the
   pattern `scripts/release.py` uses). When the subject names none, ask a new
   read, `GhClient.prs_for_commit(repo, sha)` (GitHub
   `repos/{repo}/commits/{sha}/pulls`; other adapters raise
   `UnsupportedForgeOperation`, so the step is skipped).
4. **`issue`** — for a closed-issue entry or an issue-sourced candidate,
   `list_linked_prs(repo, n)` filtered to merged. Exactly one merged PR is
   required; several is an ambiguity, reported with every number.

Any hit is confirmed through `pr_view`. A state other than `MERGED` drops the hit
with its reason. An unresolved candidate is listed under "no delivering PR: add
`pr:` in a manifest" and is never written.

### D. Gate per candidate (R4)

`gate_for(candidate)` is pure. `row:` and `walk` → `tester`; `plan:` and `op` →
`devops`; a journal key by its prefix. `audit-gap` and `closed-issue` take the
manifest's `gate:`, else their kind's default (`closed-issue` → `tester`); an
`audit-gap` with no `gate:` is refused. Only `POST_MERGE_GATES` are allowed.

### E. The plan file and its decisions (R5)

```yaml
schema: 1
repo: example-org/widgets
generated_at: 2026-11-01T12:00:00Z
entries:
  - key: plan:2026-04-02-fleet#p3
    title: "fleet: manual phase 3 is not ticked"
    gate: devops
    pr: {number: 41, basis: commit}
    tracker: {ref: null, candidates: ["example-org/widgets#56"]}   # unmarked look-alikes
    age_days: 212
    ticked: "0/4"
    decision: review          # owed | adopt <ref> | tick | na | park | review
```

- **Defaults:** `owed`, except a manual phase whose plan's last commit is older
  than `--stale-days` (default `fr debt`'s `stale_days`), which defaults to
  `review`. It carries `age_days` and `ticked` (from the plan's phase YAML), the
  facts the operator needs for the call.
- **`tracker.candidates`** are open issues that look like an existing tracker
  for this item but that `owned_owed_key` does not accept: the body or title
  names the plan slug together with `phase <n>` / `p<n>`, or the row id, or the
  manifest's issue number. They are **suggestions only**. fr never adopts on a
  heuristic (corpus 5). The operator writes `decision: adopt example-org/widgets#56`.
- **Merge on re-run:** a dry run keeps an existing entry's `decision` (and an
  `adopt` target) when its key is still a candidate. It refreshes every other
  field and drops keys no longer owed.
- **Decisions:**
  - `owed` / `adopt <ref>` → written by `--yes` (G).
  - `tick` / `na` → nothing written to the forge; R11 prints the repo command.
  - `park` → nothing written, nothing printed but its count (corpus 7).
  - `review` → skipped by `--yes` with a line naming it. No item is filed
    without a person's call when it might be noise (corpus 6).

### F. Trackers and markers (R6, R8, R9)

- A **backfill tracker** is an `fr:owed` issue written by this account. Its body
  ends with two marker lines, the PR marker before the owed marker, so
  `owned_owed_key` (last-line rule) accepts it unchanged:

  ```
  Owed: <title>

  Delivered by #41 (merged). Held by gate:devops on that PR; clear it with
  `fr gate pass --pr 41 --gate devops --notes …`.

  <!-- fr-gate:devops pr:41 -->
  <!-- fr-owed:plan:2026-04-02-fleet#p3 -->
  ```

  `fr_gate_marker(body) -> (gate, pr) | None` reads the second-to-last line,
  exact match only. It is one function, shared by F and R12.
- **Reuse:** `_existing_owed` finds the key's fr-owned tracker. A reused tracker
  lacking the PR marker gets the backfill body rewritten (it is fr-owned, so its
  body is fr's to edit, R8). One already carrying it is left alone (R7).
- **Adopt:** the adopted issue is never edited and never closed by fr. `--yes`
  posts one comment ending with `<!-- fr-gate-backfill:<key> -->` that names
  the PR and gate, and adds `fr:awaiting-live` when `walk_only`. A comment by
  this account already ending with that marker means the comment is not posted
  again (R7). If an fr-owned tracker exists for the same key, it is closed with
  "Duplicate of <adopted ref>; tracking moved there." (R9).
- **Closed issue:** after its tracker is filed, reused or adopted, the closed
  issue gets one link comment ending with `<!-- fr-gate-backfill:<key> -->`. It
  is never reopened (corpus 1).

### G. Apply order and idempotency (R6, R7, R10)

For each `owed` / `adopt` entry with a confirmed PR, in key order:

1. `gate:<g>` on the PR, unless the PR already carries `gate:<g>` (no write) or
   `gate:<g>-passed`. In the passed case nothing is added and the entry is
   reported "PR already passed <g>: the owed item is stale or belongs to
   another PR". The label is ensured (`ensure_labels`) immediately before the
   first PR in the repo that needs it, once per run (#1268's rule).
2. Unless tracking is `none`: the tracker (F), then `fr:awaiting-live` when
   `walk_only` and absent, then the closed-issue link comment.
3. Each forge error is recorded on its entry and the run continues. The exit
   code is 1 when any entry failed, else 0.

The tracking mode is `fr.services.resolve_tracking(repo_root).type` (declared
in `.devcontainer/fr-profiles.yaml`, the source `fr archive`'s `require_tracker`
reads), so `none` behaves as R10 says. An unreadable services declaration is a
refusal before any write, as in `fr archive`.

### H. `fr gate pass` closes backfill trackers (R12)

After a successful `pass_gate` with `--yes`, list the repo's open issues
(`OWED_ISSUE_FIELDS`). Close each issue that satisfies both:

- `owned_owed_key(issue, me)` accepts it;
- `fr_gate_marker` names this PR and gate.

The close comment is "Gate <g> passed on #<pr>: <notes>". Each issue carrying
this account's `<!-- fr-gate-backfill:<key> -->` comment for that PR (an adopted
tracker) is printed with its `gh issue close` line instead. The dry run lists
what it would close. A failure to list or close issues is reported and never
reverses the pass.

### I. The board shows gate-labelled PRs (R13)

- **Read:** a new `Forge.list_merged_prs_by_label(repo, label, limit)` (GitHub:
  `gh pr list --state merged --label <l> --json …`; REST path:
  `issues?labels=<l>&state=closed` filtered to merged pull requests).
  `collect` calls it once per collected repo for `gate:tester` and once for
  `gate:devops`, keeps the PRs whose `held_gates(labels)` is non-empty, and
  stores them in a new `Facts.gated_prs: list[PullRequest]`. `FACTS_SCHEMA`
  moves to the next free number (13 today); the reader keeps accepting older
  schemas, where the field defaults to `[]`. An adapter raising
  `UnsupportedForgeOperation` adds a `Truncation`-style warning naming the
  repo, and a cap hit adds one too.
- **Lanes:** `lanes.gated_pr_lane(pr) -> LaneVerdict | None` holds the
  held-gate half of `lane_of`, so both read one rule. `views.needs_you` and
  `kanban` add one Need/card per `gated_prs` entry that no batch's ledger
  already covers (same `(repo, number)`). The ref is `PR #n`, the href is the
  PR URL, and the reason reads "merged, held by gate:<g> (`fr gate pass --pr <n>
  --gate <g>`)".
- **No double listing:** a batch PR is shown through its batch only, because
  `gated_prs` entries matching a batch ledger are dropped.

### J. Unsupported forges

Backfill's writes go through `client_for_url`, the same adapter selection
`fr gate pass` uses. An operation an adapter does not implement raises
`UnsupportedForgeOperation`. That is recorded on the entry ("this forge cannot
<op>") and the run continues (G.3).

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
  dry runs and writes nothing.
- **d14 (corpus 1):** `fr archive --dry-run` is filed as a follow-up, not built
  here. Backfill gives the sweep its preview.

## 5. Risks

- **Wrong delivering PR.** The chain never guesses (no "newest PR touching the
  path" fallback), every hit records its basis, and the plan file shows it
  before any write.
- **Facts schema collision with a parallel PR** (a known trap). Renumber to
  main's next number at merge time; the fixtures pin the number in one place.
- **Mass labelling noise.** The dry run plus `review` default for stale phases;
  `park` for parked areas.

## Verification

strategy: candidate
- gate-backfill-dry-run-plan: candidate — scenario runs a dry run over a fixture repo with a recording `gh` and checks the plan file, the summary and that no write was made
- gate-backfill-apply-ledger: candidate — scenario applies an edited plan file with `--yes` against the recording `gh`, then re-applies and checks no second write
- gate-backfill-delivering-pr: none — unit tests drive the evidence chain over fixture git histories and a fake forge; a scenario adds nothing the fixtures do not
- gate-backfill-tracker-trust: none — unit tests drive adopt, reuse, duplicate close and others' issues against a fake client
- gate-pass-closes-backfill-trackers: none — unit tests drive `fr gate pass` against a fake client holding marked, unmarked and foreign trackers
- board-lanes-gated-prs: none — unit tests run collect over a fake forge and render the lanes from fixture facts
- gate-backfill-first-real-sweep: live — only a real repo's pre-v6 history and forge show the chain and the lanes working end to end
gate: tester

## 6. Test Plan (post-merge, operator-driven)

1. **First real sweep (walked on first real use).** In one repo of the corpus,
   during its planned per-repo chore (isolation → migrate → archive → row
   reconcile → chore PR), run `fr gate backfill`, review the plan file (adopt
   the hand-made trackers, `review` → tick/na/owed), run `--yes`, then
   `fr triage collect` and open the board. Pass: every confirmed `owed`/`adopt`
   entry's PR carries its gate label and shows in the right Needs-you lane;
   re-running `--yes` writes nothing; one `fr gate pass` closes that PR's
   fr-owned trackers. Row: `gate-backfill-first-real-sweep`.
   **Cost:** none beyond the sweep itself (no rehearsal repo). It is walked on
   the first real sweep, and the tester gate stays held until then.

## Implementation Plans

| Plan | Status |
|---|---|
