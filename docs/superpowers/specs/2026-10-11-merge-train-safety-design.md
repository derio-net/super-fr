# Merge train safety — a label gate, red-PR recovery, merge queues, and a protected `main`

**Slug:** merge-train-safety
**Issues:** super-fr#1062, super-fr#1082, super-fr#1076, super-fr#1129 (one batch, one PR)
**Date:** 2026-10-11

## Background

Four failures share a root: **what lands on a default branch is not what anybody
checked.**

- **super-fr#1062.** Two PRs, each green on its own CI, broke `main` on
  2026-10-07.
  - CI tests a PR's merge ref as of its last push, and GitHub does not re-run it
    when `main` moves.
  - #1041 moved the `run`/`usage` stamps. #1058 merged six minutes later at the
    old stamps, and the release refused to publish.
  - The only ruleset on `main` (`protect main`, id 17365086) enforces
    `deletion` and `non_fast_forward`. There are no required checks, no
    up-to-date rule and no merge queue (`GET
    repos/derio-net/super-fr/rules/branches/main`, read 2026-10-11).
- **super-fr#1082.** The driver's train updated batch PR #1052 from a
  momentarily broken `main` (`chore: update from main`), and the PR went red.
  - The driver then stepped over it for three hours. It updates only a PR whose
    CI passes (`_walk_train`, `packages/fr/src/fr/triage/batch_drive.py:883-929`).
  - It records nothing about the merges it produces; the only trace is its
    stdout (`_update`, `packages/fr/src/fr/triage/batch_merge.py:498-536`).
  - The `warn … CI failing at <sha>` dedup set lives per process
    (`_Driver.warned`, `packages/fr/src/fr/commands/triage_batch_cmd.py:2591`).
  - No session was told.
- **super-fr#1076.** `fr triage batch merge` runs `_refuse_held`
  (`triage_batch_cmd.py:275-283`) over every batch it is about to merge
  (`:2220-2221`). That holds for both the ids and the no-ids path. "Held"
  means another triage scope holds a claim on a member, so one held batch
  refuses the whole default merge.
- **super-fr#1129.** The driver's merge rule merges any open, non-draft, green
  PR (`merge_ready`, `batch_merge.py:387-409`).
  - Author trust is applied earlier, when the queue is built
    (`packages/fr/src/fr/triage/batch.py:182-199`).
  - The operator, every agent session and the driver share one forge identity.
    So an agent's `gh pr ready` is the operator's. On 2026-10-10 the driver
    merged a ~5,000-line PR 78 s after a session readied it.
  - Nothing in `packages/fr/src/fr/triage` knows the word "approval".
  - The dispatch brief (`packages/fr/src/fr/triage/batch_dispatch.py:98-170`)
    says nothing about ready or merge.
  - The board's Needs-you item says "ready it"
    (`packages/fr/src/fr/triage/views.py:182-193`).

The operator settled the design space in the question round. The spec journal
holds the record; the requirements below restate it. Two decisions frame the
whole change:

- **#1129 gets a label, not a cryptographic gate.** A proper design (signed
  approvals, a second forge identity, credential injection by fr-isolation) is
  explicitly later work.
- **No Bash guard.** Agents may legitimately mark a PR ready or merge outside
  fr. The label is the whole gate.

## Requirements

R1. **The approval label.** A repo label `approved-fr` (green) is fr's merge
    approval.
    - Every fr merge path merges or enqueues a PR only when it carries a valid
      `approved-fr` label. The paths are the driver's train,
      `fr triage batch merge`, and the merge-queue enqueue.
    - In the driver and in a default (no ids) `batch merge`, an unapproved PR
      is held, not failed. Its line names the label, and it never stops the PRs
      behind it.
    - A `batch merge` that names an unapproved batch's id refuses with exit 2,
      naming the label.

R2. **An approval is bound to a head.**
    - On every pass, the driver records the current head of each open batch PR
      that carries the label and has no live approval. That head is the
      approved head. It does this whatever the PR's checks say.
    - `batch merge --yes` does the same for the PRs it is about to merge.
    - The approval stays valid while every commit after that head is an update
      fr itself produced (R8's `update` events).
    - Any other new head voids it. fr removes the label, records the void, and
      the board asks the operator to re-label.

R3. **A draft with a valid approval merges.**
    - Given a valid approval and green checks, a draft PR merges too. fr marks
      it ready first (`gh pr ready`, or the REST ready route under
      `forge.api: rest`), so labelling is the operator's single act.
    - A forge that cannot mark ready (glab/tea, `UnsupportedForgeOperation`)
      leaves the PR held, with a reason naming the step.

R4. **Label creation.** fr creates the `approved-fr` label when it is missing,
    idempotently.
    - It warns once, naming the repo, each time it creates the label.
    - It checks in `fr triage collect`, `fr triage batch dispatch` and
      `fr triage batch merge` (per target repo), on every `fr triage drive`
      pass (per repo the pass may merge in, at most once per pass), and in
      `fr init scaffold`.
    - A forge that cannot create labels gets a warning, never a failure.
    - No other fr command makes a forge call for it.

R5. **The board asks for the label.** Needs-you shows:
    - "PR #n is green: label it `approved-fr` to merge" for a green batch PR,
      draft or not, with no valid approval;
    - "PR #n changed since you approved it at <sha>: re-label to merge" for a
      voided approval.

    The old "ready it" item is gone. The kanban shows "awaiting approval" for
    an unapproved green train member.

R6. **Briefs never ask for the label.** Every brief fr sends a batch session
    tells it never to add the `approved-fr` label. That covers the batch
    dispatch brief, the conflict brief, the red hand-back brief (R10) and the
    adopt message.
    - A tripwire test fails if a shipped brief, skill, agent or rule (or one of
      their generated mirrors) instructs anyone to add that label, other than
      in a sentence whose subject is the operator.

R7. **`batch merge` skips held batches.** `fr triage batch merge` with no ids
    skips each queued batch that another scope holds.
    - It prints one `skipped <batch>: held by <scope>` line each and merges the
      rest.
    - When every queued batch is held it prints "nothing to merge" and exits 0.
    - Naming a held batch's id explicitly still refuses with exit 2.

R8. **fr records its own updates.**
    - Every update the driver or `batch merge` pushes to a batch PR is recorded
      as an `update` event on that batch: PR number, head before, head after,
      and the base sha fetched at the time of the update.
    - Approval and recovery decisions read these events.
    - The judgements schema moves from 8 to 9, adding the `update`, `approval`,
      `red_handback` and `enqueue` event kinds. fr reads 1–9 and writes 9.

R9. **Red recovery, case 1: the driver's own update went red.** The driver
    updates the PR again, despite the red checks, when all of these hold:
    - the PR's checks fail at a head fr produced (some `update` event's head
      after);
    - the base has moved past that event's base sha;
    - no later `update` already starts from that head.

    This happens at most once per new base sha.

R10. **Red recovery, case 2: hand back to the session.** The driver hands the PR
    back to its batch session when the PR is red at a head no `update` event
    produced, or is still red at an fr-made head with an unmoved base.
    - The hand-back sends the PR, the failing sha and the failing check names.
      It says to fix and push, leaving the draft/ready state and the labels
      alone.
    - It goes to the same session a conflict hand-back would reach.
    - It is sent at most once per (PR, head), and only while that session is
      idle. Otherwise nothing is sent and the next pass retries.
    - At most two red hand-backs go out per dispatch, counted apart from
      conflict hand-backs.

R11. **A handed-back red PR is in progress, not blocked.**
    - It stays "in progress" on the board. Its `failing-ci` Need is suppressed
      while a delivered red hand-back covers its current head.
    - It reaches Needs-you as a `red-pr` item only when red hand-backs are
      exhausted or its session is gone (absent or done).
    - Repeated passes over the same red head send nothing new.

R12. **Detecting the base branch's rules.** The driver reads them through one
    `GhClient` method from `GET repos/{repo}/rules/branches/{branch}`:
    - whether a `merge_queue` rule is present;
    - whether a `required_status_checks` rule is strict (up to date).

    glab and tea report neither. Merge queues configured only through classic
    branch protection are not detected (Out of scope).

R13. **Queue mode.** When a merge queue is required, the driver enqueues an
    approved, green PR instead of merging it
    (`gh pr merge --auto --match-head-commit`).
    - It does no update-from-base of its own for that repo.
    - It records an `enqueue` event, and treats a queued PR as in flight across
      passes. `--max-inflight` counts it as it counts any open batch PR.
    - An enqueued PR that is open, not in the queue, and no longer has
      auto-merge set has been ejected:
      - own checks green: re-enqueue once per new base sha, otherwise Needs-you;
      - own checks red: R10's path.
    - Holds, each with a warning:
      - a repo with a `version:` block (version reservation needs the serial
        train);
      - `forge.api: rest` (it cannot enqueue).
    - A repo whose base requires no queue keeps today's train.

R14. **Strict up-to-date checks.** When the base requires strict status checks,
    the train never merges a PR that is behind its base, even when the gap is
    only routine commits. It updates the PR first.

R15. **CI on merge groups.** `ci.yml` and `acceptance-report.yml` also run on
    `merge_group`, so `ci-ok` reports for a queue's merge group.
    `change-fragment` stays pull-request-only. It is skipped on a merge group,
    and `ci-ok` treats a skip as a pass.

R16. **The release pushes as the app.**
    - When the repo variable `FR_AUTOMATION_APP_ID` is set, `release.yml`
      pushes the release commit and tag as the `derio-fr-automation` GitHub
      App, minting a token from secret `FR_AUTOMATION_APP_KEY` with
      `actions/create-github-app-token`.
    - It falls back to `GITHUB_TOKEN` when the variable is unset.
    - Its header, AGENTS.md's "Release / version bumping" and
      `tests/unit/test_release_workflow.py` describe both modes, and that an
      app-pushed release commit now runs CI.

R17. **`scripts/configure-main-protection.sh`** is idempotent, `set -euo
    pipefail`, and reads nothing secret. It brings `main`'s `protect main`
    ruleset to a declared state in two stages.
    - `--stage bypass` sets the app-id variable and adds the app as a bypass
      actor.
    - `--stage require` adds the required `ci-ok` check with "require branches
      to be up to date". It refuses until the bypass is in place and the newest
      release commit was pushed by the app, unless `--force`.
    - Each stage merges into the existing ruleset, never overwriting it, and
      prints the result. `--dry-run` prints the request body instead.
    - A runbook, `docs/merge-protection.md`, gives the order and tells a
      consumer repo how to adopt it.

R18. **The end state of `main`.** super-fr's `main` ends this change requiring
    `ci-ok` and up-to-date branches, with the app as a bypass actor. A release
    published after that pushes as the app. This is a post-merge step (Test
    Plan).

## Design

### A. The approval gate (R1–R6)

#### Facts and the label

`fr/labels.py` gains:

```python
APPROVED_FR = LabelDef("approved-fr", "0E8A16",
                       "Operator approval: fr may merge this PR at its approved head")
```

`PullRequest` (`triage/model.py:273`) gains `labels: list[str] | None`. It is
filled for open PRs only, and `None` means never read, the same rule as
`checks`.
- Both collectors fill it: GraphQL (`collect.py:222-230` field list) and REST
  (`real_ghrestclient.py`).
- `FACTS_SCHEMA` goes 8 → 9 and `FACTS_READS` widens to 3–9
  (`model.py:55-65`). A facts file at 8 reads `labels` as `None`, which never
  approves.

`GhClient.pr_view` also returns labels:
- `RealGhClient`: `--json …,labels`, `real_ghclient.py:375-386`.
- `RealGhRestClient`: `pulls/{n}` `.labels[].name`.

The merge paths therefore read the label live, never from a possibly stale
facts file. `batch merge` does not re-collect facts.

#### The verdict (pure)

`fr/triage/approval.py`:

```python
def approval_verdict(events: Sequence[BatchEvent], pr: int, head: str,
                     labels: Sequence[str] | None) -> ApprovalVerdict
# Approved(approved_head) | Unlabelled | First(head) | Void(approved_head)
```

- **`Unlabelled`:** the label is absent. A recorded approval does not outlive
  its label.
- **`First(head)`:** the label is present, and there is no live
  `ApprovalEvent` for `pr` (none, or the last one is voided).
- **`Approved(A)`:** the label is present and the live approval is at `A`.
  Walking `UpdateEvent`s for `pr` from `A` (`head_before → head_after`, in
  order) reaches `head`.
- **`Void(A)`:** the label is present and the walk does not reach `head`.

#### Recording and voiding (impure, R2)

`settle_approvals(client, writer, repo, batches_with_open_prs, say)` lives in
`fr/triage/approval.py` and runs every drive pass, before the walk.
- For each open batch PR, it calls `pr_view` (labels and head).
- On `First`, it appends `ApprovalEvent(pr, head)`.
- On `Void(A)`, it removes the label with `edit_issue_labels(remove=…)`
  (existing) and appends `ApprovalEvent(pr, head=A, voided_at=head)`. It says
  "approval of PR #n at <A> voided: head moved to <head>".

`batch merge` calls the same function for the batches it is about to merge,
but only under `--yes`. The preview prints what it would record or void.

**Known limit of the stop-gap.** A push between the operator's labelling and
the next pass is approved, because no head was recorded before the push. Out of
scope says so.

#### The walk (pure)

`Snapshot` gains `approvals: Mapping[str, ApprovalVerdict]`, keyed by batch
id, computed from facts `labels` and the batch events. The board and `drive
--plan` compute it the same way with no forge call.

In `_walk_train` (`batch_drive.py:883-929`):
- **A draft is a member** when its verdict is `Approved` or `First`. Today
  every draft is skipped (`:900-901`). An unapproved draft stays a
  non-member, as today.
- **A member that is not `Approved`/`First` is held.** It never becomes a
  candidate, the head or `waiting`, and never stops the walk. It goes into a
  new `Train.awaiting` tuple.
- **Otherwise** the walk is unchanged: `failing` is stepped over, `pending`
  waits, and `green` becomes a candidate with a `merge` action.

`kanban.py` renders `Train.awaiting` as "awaiting approval" and `train_line`
lists it.

`views.needs_you` replaces `ready-pr` (`views.py:182-193`) with `approve-pr`
(the R5 texts). The trigger is an OPEN batch PR, draft or not, that is green
by `checks_verdict` and whose verdict is not `Approved`/`First`. A `Void`
verdict gets the re-label text. `NEED_LABELS` (`views.py:139-149`) gains
`approve-pr`, `red-pr` (§C) and `queue-ejected` (§D), and drops `ready-pr`.

#### Merging (R1, R3)

There is one shared gate, `_approved_and_ready(ctx, slot, pr) -> None |
MergeAttempt`, in `batch_merge.py`. Both `merge_ready` (`:387`) and
`merge_one` (`:265`) call it before `_open_head`'s draft refusal
(`:287-293`).
- It re-runs `approval_verdict` on the live `pr_view`.
- If the verdict is not `Approved`, it returns `MergeAttempt("unapproved")`.
  `MergeReadiness` (`:374`) gains that value.
- If the PR is a draft and the checks are green, it calls the new
  `GhClient.pr_ready`. An `UnsupportedForgeOperation` there returns
  `MergeAttempt("unready", reason)`.
- `_open_head` keeps its draft refusal for any path that bypasses the gate.

How each caller treats `unapproved`/`unready`:
- **The driver:** `_stops_train` (`triage_batch_cmd.py:2541-2548`) steps over
  both.
- **`batch merge` with no ids:** before the plan prints, it filters unapproved
  and held batches out using the live `pr_view` labels plus the events, and
  prints `held <id>: PR #n awaits the approved-fr label`. `run_queue` never
  sees them, so a `MergeStopError` can never stop the batches behind them.
- **`batch merge` with ids:** an unapproved named batch exits 2 naming the
  label.

`GhClient.pr_ready(repo, number)`:
- `RealGhClient`: `gh pr ready`.
- `RealGhRestClient`: `POST pulls/{n}/ccr/ready_for_review`, the route
  `hostclient.py:114` names.
- `UnsupportedBatchOps`: raises.

#### Label creation (R4)

`ensure_approval_label(client, repo, say, *, seen: set[str])`:
- calls the new `GhClient.label_exists(repo, name)`;
- if the label is missing, calls `client.ensure_labels(repo, [APPROVED_FR])`
  and says "created label approved-fr on <repo>";
- on `UnsupportedForgeOperation`, warns and returns;
- uses `seen` to cap the calls at one per repo per pass or command.

`label_exists`:
- `RealGhClient`/REST: `GET repos/{repo}/labels/{name}`, where 404 means
  false;
- `UnsupportedBatchOps`: raises.

`fr init scaffold` (`commands/init_cmd.py:27`) calls it when the origin is
GitHub. Any failure is a warning.

#### Briefs and the tripwire (R6)

One constant, `NO_APPROVAL_LINE` ("Never add the `approved-fr` label: it is
the operator's approval to merge, and fr voids it on your next push."). It is
appended by `render_brief` (`batch_dispatch.py:98`), `conflict_brief`
(`:173`), `red_brief` (§C) and `adopt_message`
(`triage_batch_cmd.py:1760`).

`tests/unit/test_tripwire_approval_label_prose.py` checks two things:
1. Each of the four renderers' output contains `NO_APPROVAL_LINE`.
2. No shipped canonical skill, agent or rule, nor its OpenCode/Hermes mirror,
   has a sentence matching `--add-label[ =]approved-fr` or
   `\b(add|apply|put|set)\b[^.]{0,40}approved-fr` unless that sentence also
   contains `never`, `do not`, `don't` or `operator`.

The fr-triage skill's driver section states the gate in operator-subject
sentences. fr-goal's SKILL.md is unchanged.

### B. Recording what fr did (R8)

`model.py` gains four event kinds, schema-gated like the existing eight
(`model.py:767-787, 987-1022`, a new `SCHEMA_9_EVENTS`):

```python
UpdateEvent       {kind: update, at, pr, head_before, head_after, base}
ApprovalEvent     {kind: approval, at, pr, head, voided_at: str | None}
RedHandbackEvent  {kind: red_handback, at, pr, head, checks: list[str], delivered: session|none}
EnqueueEvent      {kind: enqueue, at, pr, head, base}
```

`JUDGEMENTS_SCHEMA` goes 8 → 9 and the read range widens to 1–9.

**How an update is recorded.** `MergeContext` (`batch_merge.py:109-124`)
gains `on_update: Callable[[int, str, str, str], None] | None`, called as
`(pr, head_before, head_after, base)`. `_update` (`:498-536`) calls it after
`commit_all` and BEFORE the push (phase 1 review p1-r6). A crash or a
concurrent writer between the push and the record would otherwise leave an
fr-made head with no event, and the next settle would void a valid approval.
An event for a head whose push then failed is harmless, because an unpushed sha
never becomes the PR's head.
- `base` is `rev_parse(ctx.main)` in the scratch checkout at update time.
  `CheckoutSeam` (`:86-96`) gains `rev_parse`, backed by
  `gitseam.Checkout.rev_parse` (`gitseam.py:448`).
- A re-slot-only update merges no base, but records the fetched base sha all
  the same. A later base move then re-qualifies it under R9.
- The driver and `batch merge` each pass a callback that appends through the
  one judgements writer.

### C. Red recovery (R9–R11), decided in the command

The pure walk still steps over a failing PR and emits its `warn` action. The
recovery decision sits beside `_conflict` in the command, because it needs
impure inputs: the fetched base sha and the runner's live session statuses.

`batch_drive.red_decision(events, pr, head, failing, base_now, status) ->
Literal["reupdate", "handback", "wait", "needs_you", "skip"]` is pure and
unit-tested. It takes the first rule that applies:

1. A `RedHandbackEvent` exists for (pr, head) → `skip`.
2. `head` is some `UpdateEvent.head_after`, `base_now != that.base`, and no
   `UpdateEvent.head_before == head` → `reupdate`.
3. `RED_HANDBACKS_PER_DISPATCH = 2` delivered red hand-backs have gone out
   since the last `dispatch` → `needs_you`.
4. `status` decides:
   - `idle` → `handback`;
   - `absent`/`done` → `needs_you`;
   - anything else → `wait`.

`_Driver._recover(entry)` runs after the walk for every stepped-over failing
PR:
- **`reupdate`:** calls `_update` through `merge_one`'s machinery with the
  green-checks precondition waived for this call only. The new `UpdateEvent`
  dedups it.
- **`handback`:** sends `red_brief` to the target `_hand_back` already
  resolves (`triage_batch_cmd.py:3998-4008`: the latest fresh conflict
  session, else the batch's session). It records
  `RedHandbackEvent(delivered=session)`.
- **`needs_you`:** records `RedHandbackEvent(delivered=none)` once per
  (pr, head).
- **`wait`:** says "its session is <status>: nothing sent, retried next pass"
  and records nothing.

**Why `absent`/`done` is a Needs-you, not a fresh session as with
conflicts.** A conflict is mechanical: any session can resolve it. A red CI
needs the batch's own context. Starting a replacement session is already the
operator's tool (`fr triage batch replace`).

`views.needs_you` suppresses a PR's `failing-ci` need while a `delivered:
session` `RedHandbackEvent` covers its current head (R11). It raises `red-pr`
("PR #n is red at <sha> (<checks>) and no session can take it") for a
`delivered: none` event at the current head.

The `warn` line's dedup moves from `_Driver.warned` to the events. The line
is printed only on a pass whose `_recover` sends or decides something new, so
a restarted driver does not re-warn.

`red_brief(batch, pr_url, head, checks)` sits next to `conflict_brief` in
`batch_dispatch.py`. It tells the session:
- the PR is red at <sha>, and these checks failed;
- fix it on the branch, commit and push, with no force-push;
- leave the draft/ready state and the labels alone;
- plus `NO_APPROVAL_LINE`.

### D. Base rules and merge queues (R12–R15)

```python
GhClient.base_rules(repo, branch) -> BaseRules{merge_queue: bool, strict_checks: bool}
```

- **Both GitHub backends:** REST `rules/branches/{branch}`. `merge_queue` is
  any rule of `type == "merge_queue"`. `strict_checks` is any
  `required_status_checks` rule whose
  `parameters.strict_required_status_checks_policy` is true.
- **`strict_checks` also from classic protection.** Both backends also read
  `GET branches/{branch}/protection`'s `required_status_checks.strict` (404
  means false), because `required_check_names` (`real_ghrestclient.py:719-732`)
  already reads it.
- **`UnsupportedBatchOps`** returns `BaseRules(False, False)`. A forge without
  the concepts has neither, which is not an error.

The driver reads `base_rules` once per repo per pass, and `batch merge` reads
it once per command. Both store the result on `MergeContext`.

**Strict up-to-date (R14).** `_land` (`batch_merge.py:303-313`) skips the
routine-commit exemption `_behind_only_routinely` when `ctx.strict_checks` is
set. A behind PR is then always updated first.

**Queue mode (R13).** It is active only when the repo's `merge_queue` rule is
set.
- **The walk.** The pure walk gets `Snapshot.queue_repos`. For such a repo it
  picks no head. Every `Approved`, green member not already queued gets an
  `enqueue` action (a new `ActionKind`, phrase "enqueue PR #n"). A queued
  member goes into `Train.in_merge_queue`, rendered "in merge queue".
- **Holds.** A repo with a `version:` block is held with a `held` action:
  "<repo> requires a merge queue, and fr does not reserve versions through
  one". Under `forge.api: rest` the line reads "…forge.api rest cannot
  enqueue".
- **Enqueueing.** `GhClient.pr_enqueue(repo, number, *, head_sha, method)` is
  `gh pr merge --auto --match-head-commit <sha> --<method>` on
  `RealGhClient`. REST and unsupported backends raise. The driver records
  `EnqueueEvent(pr, head, base)`.
- **Queue state.** `GhClient.pr_queue_state(repo, number) ->
  QueueState{in_queue: bool | None, auto_merge: bool}`. On `RealGhClient` it
  is `gh api graphql` for `isInMergeQueue` and `autoMergeRequest`, since
  `gh pr view --json` exposes neither. On REST, `pulls/{n}.auto_merge` and
  `in_queue=None`. `UnsupportedBatchOps` returns `(None, False)`.
- **Ejection.** A PR is ejected when its last event is an `EnqueueEvent` at the
  current head, and it is open, not merged, not `in_queue`, and not
  `auto_merge`. Auto-merge is set from enqueue until GitHub merges the PR or
  clears it on ejection, so a PR waiting to enter the queue is never mistaken
  for ejected.
  - Own checks green and `base_now != event.base`: re-enqueue.
  - Own checks green and the base unmoved: a `queue-ejected` Need ("PR #n left
    the merge queue unmerged").
  - Own checks red: §C (`red_decision`). Rule 2 never applies, because a queue
    PR has no `UpdateEvent`.
- **`--max-inflight`** is unchanged. A queued batch is still at stage
  `pr-open`, which `IN_FLIGHT` already counts (`batch_drive.py:52`).
- **Additions from the phase 3 review:**
  - **Enqueue goes through the merge gate.** It passes through
    `_approved_and_ready`, so an approved draft is readied first (R3).
  - **Un-approval dequeues.** If a queued PR loses its approval (its label
    removed, or voided), `settle_approvals` takes it out of the queue with
    `GhClient.pr_dequeue` (`gh pr merge --disable-auto`).
  - **Unknown default branch holds the repo.** When fr cannot tell a repo's
    default branch, it holds the repo with a warning ("queue mode unknown"),
    rather than reading it as having no queue.
  - **Ejected and refused PRs reach the board.** An ejected PR whose base has
    not moved, and an enqueue that is refused again at the same head, are
    recorded. `needs_you` then raises the `queue-ejected` or `enqueue-refused`
    Need from events alone. A refusal fr cannot tell apart from a conflict
    becomes the Need, with the forge's words. `EnqueueEvent` carries `outcome`
    (enqueued | ejected | dequeued | refused) and `detail`.
  - **The kanban reads queue membership from events.** A PR whose last
    `EnqueueEvent` is at its current head shows as "in merge queue".
  - **Red recovery skips rule 2 in a queue repo.** fr never pushes an update
    from base in a queue repo.

**CI (R15).**
- `ci.yml` (`:4-7`) and `acceptance-report.yml` (`:17-23`) add
  `merge_group:` to `on:`.
- `change-fragment` keeps `if: github.event_name == 'pull_request'`
  (`ci.yml:161-170`). The PR already passed it, and `ci-ok` treats a skip as a
  pass.
- `acceptance-report.yml:48` already falls back to `github.sha`.
- `tests/unit/test_ci_merge_group.py` pins the trigger in both files and the
  `change-fragment` condition.

### E. `batch merge` and held batches (R7)

The loop at `triage_batch_cmd.py:2220-2221` runs for both paths. With
`batch_ids` empty, it partitions instead:
- held batches print `skipped <id>: held by <scope>`;
- the rest continue to the one-repo check (`:2222-2227`).

If none remain, the command prints "nothing to merge" and exits 0, before the
mixed-repo refusal. With ids, `_refuse_held` is unchanged.

### F. Release identity and protection (R16–R18)

`release.yml`:

```yaml
- id: app-token
  if: vars.FR_AUTOMATION_APP_ID != ''
  uses: actions/create-github-app-token@<pinned sha of a v1 release>
  with: {app-id: "${{ vars.FR_AUTOMATION_APP_ID }}", private-key: "${{ secrets.FR_AUTOMATION_APP_KEY }}"}
- uses: actions/checkout@…
  with: {token: "${{ steps.app-token.outputs.token || github.token }}", …}
```

- The job's `GH_TOKEN` env takes the same expression.
- The token is scoped: `owner`/`repositories` name this repo only, and
  `permission-contents: write` and `permission-issues: write` are the only
  permissions (push, tag and release; the floor issue).
- No credential is readable by the staged test run: checkout uses
  `persist-credentials: false`, `release.py` strips `GH_TOKEN`/`GITHUB_TOKEN`
  from that subprocess's env, and authenticates only its two `git push` calls
  (`-c credential.helper=!gh auth git-credential`).
- `release.py`'s git identity stays `github-actions[bot]`. Who pushed is a
  property of the token, not the commit.
- The header's "no CI runs on the release commit" becomes one sentence per
  mode.
- With the app, CI and release.yml run once more on the release commit. That
  second release run is a no-op, which `test_two_runs_back_to_back_are_safe`
  (`tests/unit/test_release_script.py:288`) already covers.
- `test_header_states_the_no_ci_property_and_the_bypass_actor`
  (`tests/unit/test_release_workflow.py:67-70`) is rewritten to pin both modes
  and the `if:`/fallback expression.
- `release.py`'s protection-refusal message (`:439-452`) names the app and
  the variable.

`scripts/configure-main-protection.sh [--repo O/R] --stage bypass|require
[--dry-run] [--force]`:
- **Common.** It resolves the ruleset by name (`protect main`) from `gh api
  repos/{repo}/rulesets`, and the app id from `gh api
  orgs/{org}/installations` (`app_slug == derio-fr-automation`). It builds the
  PUT body from a `GET` with `jq`, adding only what is missing.
- **`bypass`:** `{actor_type: Integration, actor_id: <app id>, bypass_mode:
  always}` plus `gh variable set FR_AUTOMATION_APP_ID`.
- **`require`:** a `required_status_checks` rule, `[{context: ci-ok}]`,
  `strict_required_status_checks_policy: true`; an existing
  `required_status_checks` rule keeps its other contexts and settings and gains
  only `ci-ok` and strict. It refuses unless the bypass
  actor is present and the newest `v*` tag's commit has a `push`-event Actions
  run whose `triggering_actor.login` is the app's bot login (`gh api
  "repos/{repo}/actions/runs?head_sha=<sha>&event=push"`). A `GITHUB_TOKEN`
  push triggers no run, so the run's existence and its actor prove the pusher.
  `--force` skips the release check, never the bypass check.
- **Tests.** `tests/unit/test_configure_main_protection.py` runs the script
  with a stub `gh` on PATH and covers the merge-not-overwrite body, both
  refusals, `--force`, `--dry-run` and idempotence.

`docs/merge-protection.md` covers:
- the operator's one UI step: generate the app key, then `gh secret set
  FR_AUTOMATION_APP_KEY < key.pem`;
- the two stages, in order;
- consumer-repo adoption;
- the driver's merge-queue and strict-check behaviour, which needs no config.

AGENTS.md "Release / version bumping" is updated to match.

## Out of scope

- **A proper merge gate.** That means signed (`ssh-keygen -Y`) approvals, a
  second forge identity, credential injection by fr-isolation, and a Bash guard
  denying ready/merge. The label is a deliberate stop-gap. Its known gaps:
  - any session can add the label, because the identity is shared;
  - a push between labelling and the driver's next pass is approved.

  Filed as a follow-up issue at close-out.
- **Merge queues required only by classic branch protection.** The driver does
  not detect them (R12).
- **GitLab/Gitea merge trains.**
- **Who may mark a PR ready outside fr.**

## Verification

strategy: candidate

The scenarios follow the existing shell-level fake-forge pattern:
`tests/scenarios/fixtures/<name>/bin/gh`, a `gh api` stub answering REST routes
(as `cloud-triage-driver/bin/gh` does), with `FR_FORGE_API=rest`, and a bare
git remote reached through `url.<base>.insteadOf` for the driver's update
pushes. Each stub logs its calls, so the scenario asserts on the writes
(label removal, merge, ready).

- merge-train-label-gate: candidate — scenario `tests/scenarios/merge-train-label-gate.sh`: an unlabelled green PR is held, a labelled draft is readied and merged, a session push voids the label, and a driver update keeps it.
- approval-label-created: candidate — the label-gate scenario's first pass creates the missing label and warns.
- approval-board-and-briefs: candidate — the label-gate scenario renders the board's Needs-you; the prose tripwire runs in CI.
- merge-train-red-recovery: candidate — scenario `tests/scenarios/merge-train-red-recovery.sh`.
- merge-train-queue: candidate — scenario `tests/scenarios/merge-train-queue.sh` covers detection and the REST-mode hold; the GraphQL enqueue/ejection path is unit-tested against the in-process fake forge (`tests/unit/triage_fixtures.py`), because the shell stub speaks REST only.
- batch-merge-skip-held: candidate — scenario `tests/scenarios/batch-merge-skip-held.sh`.
- merge-train-strict-up-to-date: candidate — the red-recovery scenario's base rules carry a strict check, so a PR behind only by a routine commit is updated before it merges.
- ci-merge-group-trigger: none — a unit test over the workflow YAML is the whole claim; there is nothing to walk.
- main-protection-script: none — the script's unit test with a stub `gh` is the pre-merge proof; its real run is the Test Plan.
- release-pushes-as-app: live — only a real release on GitHub with the app's secret shows who pushed it.
- main-requires-ci-ok: live — only the real ruleset shows a behind PR blocked and the release bot bypassing it.

## Test Plan

Post-merge, operator plus agent (R18):

1. **Operator:** generate a `derio-fr-automation` private key in the GitHub UI
   and run `gh secret set FR_AUTOMATION_APP_KEY -R derio-net/super-fr <
   <key.pem>`.
2. **Agent:** run `scripts/configure-main-protection.sh --stage bypass`, and
   confirm the variable and the bypass actor in the printed ruleset.
3. **The next release** (any merged PR with a fragment): confirm a `push`
   Actions run exists on the `release:` commit with the app as
   `triggering_actor`, and that the second release.yml run was a no-op. This
   flips `release-pushes-as-app`.
4. **Agent:** run `scripts/configure-main-protection.sh --stage require`. Then
   confirm on a real PR behind `main` that GitHub blocks the merge until the
   PR is updated, and that the following release still pushes. This flips
   `main-requires-ci-ok`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-11-merge-train-safety | `derio-net/super-fr` | `2026-10-11-merge-train-safety` | — |
