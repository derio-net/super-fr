# Merge train safety — a label gate, red-PR recovery, merge queues, and a protected `main`

**Slug:** merge-train-safety
**Issues:** super-fr#1062, super-fr#1082, super-fr#1076, super-fr#1129 (one batch, one PR)
**Date:** 2026-10-11

## Background

Four failures share a root: **what lands on a default branch is not what anybody
checked.**

- **super-fr#1062.** Two PRs that each passed CI broke `main` on 2026-10-07.
  CI tests a PR's merge ref as of its last push, and GitHub does not re-run it
  when `main` moves. #1041 moved the `run`/`usage` stamps; #1058 merged six
  minutes later at the old stamps, and the release refused to publish. The only
  ruleset on `main` (`protect main`, id 17365086) enforces `deletion` and
  `non_fast_forward`. There are no required checks, no up-to-date rule and no
  merge queue (`GET repos/derio-net/super-fr/rules/branches/main`, read
  2026-10-11).
- **super-fr#1082.** The driver's train updated batch PR #1052 from a
  momentarily broken `main` (`chore: update from main`). The PR went red, and
  the driver then stepped over it for three hours. It updates only a PR whose
  CI passes (`_walk_train`, `packages/fr/src/fr/triage/batch_drive.py:883-929`),
  and it records nothing about the merges it produces. The only trace is its
  stdout (`_update`, `packages/fr/src/fr/triage/batch_merge.py:498-536`). The
  `warn … CI failing at <sha>` dedup set is per process (`snap.warned`,
  `packages/fr/src/fr/commands/triage_batch_cmd.py:2591`). No session was told.
- **super-fr#1076.** `fr triage batch merge` with no ids calls `_refuse_held`
  for each queued batch (`triage_batch_cmd.py:275-283`, the call at
  `:2184-2185`). "Held" means another triage scope holds a claim on a member.
  So one held batch refuses the whole default merge.
- **super-fr#1129.** The merge rule `merge_ready` (`batch_merge.py:387-409`)
  merges any open, non-draft, green PR. Author trust is applied earlier, when
  the queue is built (`packages/fr/src/fr/triage/batch.py:182-199`). The
  operator, every agent session and the driver all use one forge identity, so
  an agent's `gh pr ready` is the operator's. On 2026-10-10 the driver merged
  a ~5,000-line PR 78 s after a session readied it. Nothing in
  `packages/fr/src/fr/triage` knows the word "approval" (grep, 2026-10-11). The
  dispatch brief (`packages/fr/src/fr/triage/batch_dispatch.py:98-170`) says
  nothing about ready or merge. The board's Needs-you item reads "ready it"
  (`packages/fr/src/fr/triage/views.py:178-189`).

The operator settled the design space in the question round. The record is in
the spec journal; the decisions are restated below as requirements.

- **#1129: a label, not a cryptographic gate.** "A proper design" (signed
  approvals, a second forge identity, credential injection by fr-isolation) is
  explicitly later work. Signed approvals are a placeholder and are not built.
- **No Bash guard.** Agents may legitimately mark a PR ready or merge outside
  fr, so the label is the whole gate.

## Requirements

R1. A repo label `approved-fr` (green) is fr's merge approval. Every fr merge path
    merges a PR only when it carries a valid `approved-fr` label: the driver's
    train, `fr triage batch merge` with or without ids, and the merge-queue
    enqueue. A PR without the label is not refused as an error. It is held, and the
    reason line names the label.

R2. An approval is bound to a head. The first time an fr merge path sees the label
    on a PR, it records the PR's current head as the approved head. The approval
    stays valid while every commit after that head is an update the driver itself
    produced (R8's `update` event). Any other new head voids it: fr removes the
    label, records the void, and the board asks the operator to re-label.

R3. With a valid approval and green checks, a draft PR merges too. fr marks it
    ready first (`gh pr ready`, or the REST ready route under `forge.api: rest`), so
    labelling is the operator's single act. A forge that cannot mark ready
    (glab/tea, `UnsupportedForgeOperation`) leaves the PR held, with a reason
    naming the step.

R4. fr creates the `approved-fr` label idempotently, with one warning line naming
    the repo the first time it creates it. It does so in `fr triage collect`,
    `fr triage batch dispatch`, `fr triage batch merge`, `fr triage drive` (each
    pass, for each repo it may merge in) and `fr init scaffold`. No other fr
    command makes a forge call for it.

R5. The board's Needs-you list shows "PR #n is green: label it `approved-fr` to
    merge" for a green batch PR, draft or not, with no valid approval. A voided
    approval shows "PR #n changed since you approved it at <sha>: re-label to
    merge". The old "ready it" item is gone.

R6. Every brief fr sends a batch session tells it never to add the
    `approved-fr` label: the batch dispatch brief, the conflict brief, the red
    hand-back brief (R10) and the adopt message. A tripwire test fails if any
    shipped brief, skill, agent or rule instructs a session to add that label.

R7. `fr triage batch merge` with no ids skips each queued batch that another
    scope holds, printing one `skipped <batch>: held by <scope>` line each, and
    merges the rest. Naming a held batch's id explicitly still refuses with exit 2.

R8. Every update the driver or `batch merge` pushes to a batch PR is recorded as an
    `update` event on that batch: PR number, head before, head after, and the base
    sha it merged. Approval and recovery decisions read these events. The
    judgements schema moves to 9 to carry `update`, `approval`, `red_handback` and
    `enqueue` events. fr reads 1–9 and writes 9.

R9. Red recovery, case 1. A batch PR whose checks fail at a head the driver
    produced (an `update` event's head after), and whose base has moved past that
    event's base sha, is updated again despite the red checks. This happens at most
    once per new base sha.

R10. Red recovery, case 2. A batch PR that is red at a head no `update` event
    produced, or still red at a driver head with an unmoved base, is handed back to
    its batch session. The hand-back sends the PR, the failing sha and the failing
    check names, and says to fix and push without touching the draft/ready state or
    the label. It is sent once per (PR, head), only while the session is idle;
    otherwise nothing is sent and the next pass retries. At most two red hand-backs
    are sent per dispatch.

R11. A red PR the driver has handed back stays "in progress" on the board. It moves
    to Needs-you only when hand-backs are exhausted, the session is gone (absent or
    done), or the forge cannot deliver. Repeated passes over the same red head send
    nothing new.

R12. The driver detects whether a repo's base branch requires a merge queue, by
    reading `GET repos/{repo}/rules/branches/{branch}` for a rule of type
    `merge_queue`. That goes through a `GhClient` method; glab and tea report "no
    queue". When a queue is required, the driver enqueues an approved, green PR
    (`gh pr merge --auto --match-head-commit`) instead of merging it. It does no
    update-from-base of its own for that repo. It records an `enqueue` event, and
    treats a queued PR as in flight across passes, so `--max-inflight` counts it as
    it counts any open batch PR. A repo whose base requires no queue keeps today's
    train.

R13. An enqueued PR that has left the queue unmerged is ejected. If its own checks
    are green, it is re-enqueued, once per new base sha. If they are red, it goes
    down R10's hand-back path. Under `forge.api: rest`, which cannot enqueue, a
    queue-required repo is held with a warning naming the limit.

R14. `ci.yml` and `acceptance-report.yml` also run on `merge_group`, so `ci-ok`
    reports for a queue's merge group. Every job that reads pull-request context
    has a merge-group equivalent.

R15. `release.yml` pushes the release commit and tag as the `derio-fr-automation`
    GitHub App when the repo variable `FR_AUTOMATION_APP_ID` is set, minting a
    token from secret `FR_AUTOMATION_APP_KEY` with `actions/create-github-app-token`.
    It falls back to `GITHUB_TOKEN` when the variable is unset. Its header,
    AGENTS.md's "Release / version bumping", and
    `tests/unit/test_release_workflow.py` describe both modes and the fact that an
    app-pushed release commit now runs CI.

R16. `scripts/configure-main-protection.sh` (idempotent, `set -euo pipefail`, reads
    nothing secret) brings `main`'s `protect main` ruleset to a declared state in
    two stages. `--stage bypass` sets the app-id variable and adds the app as a
    bypass actor. `--stage require` adds the required `ci-ok` status check with
    "require branches to be up to date". Each stage prints the resulting ruleset.
    A runbook in `docs/merge-protection.md` gives the order and how a consumer repo
    adopts it.

R17. super-fr's `main` ends this change requiring `ci-ok` and up-to-date branches,
    with the app as a bypass actor. A release published after that pushes as the
    app. This is a post-merge operator/agent step (Test Plan).

## Design

### A. The approval gate (R1–R6)

`fr/labels.py` gains `APPROVED_FR = LabelDef("approved-fr", "0E8A16",
"Operator approval: fr may merge this PR at its approved head")`.

**Facts.** `PullRequest` gains `labels: list[str] | None` (open PRs only,
`None` = never read, same rule as `checks`). It is filled by both the GraphQL
(`collect.py`) and REST (`real_ghrestclient.py`) collectors. `FACTS_SCHEMA`
goes 8 → 9 (`triage/model.py:55`). Reading facts at 8 is tolerated, since
facts are re-collected each pass; `labels: None` there reads as no approval.

**Approval check.** A new pure module, `fr/triage/approval.py`:

```python
def approval_verdict(batch: Batch, pr_number: int, head: str, labels: list[str] | None
                     ) -> ApprovalVerdict   # valid | missing | void(approved_head) | first(head)
```

- `missing`: no label.
- `first(head)`: the label is present and no unvoided `approval` event exists for
  this PR. The caller records `ApprovalEvent(pr, head)` and treats the approval
  as valid.
- `valid`: an `approval` event exists at head `A`, and walking `update` events
  from `A` (`head_before → head_after`) reaches the current `head`.
- `void(A)`: anything else. The caller removes the label
  (`edit_issue_labels`, existing), records `ApprovalEvent(pr, head=A,
  voided_at=head)`, and holds the PR.

A label re-added after a void is a `first` again.

**Where it runs.** `merge_ready` (`batch_merge.py:387`) gains the check after
`_open_head` and before `live_checks`. An invalid approval returns a new
`MergeAttempt` outcome, `unapproved`, which `_stops_train` treats as a step-over
(`triage_batch_cmd.py:2543-2548`). For a valid approval on a draft, the order
is checks green, then `pr_ready`, then `_land`. `merge_one`, the `batch merge`
path, goes through the same function, so R1 covers both. The pure
`_walk_train` sees approval in the `Snapshot` (facts `labels` plus batch
events), so the board and the train agree. An `unapproved` PR is never the
train's head, and never `waiting` either: it does not block the PRs behind it.

**Forge.** `GhClient` gains `pr_ready(repo, number)`.

- `RealGhClient`: `gh pr ready`.
- `RealGhRestClient`: the CCR ready route `hostclient.py:114` already names.
- `UnsupportedBatchOps`: raises.

The event writes reuse the one judgements writer (`batch.py`).

**Label creation (R4).** `ensure_approval_label(client, repo, say)` calls
`client.ensure_labels(repo, [APPROVED_FR])` once per repo per process. "First
time" is detected by listing first: `ensure_labels` is idempotent but silent,
so the helper checks existence via a new `label_exists` (GhClient), creates
the label, and warns only when it created it. On `UnsupportedForgeOperation`
it warns and carries on. `fr init scaffold` calls it when the repo's origin is
a forge fr knows; a failure there is a warning, never a scaffold failure.

**Board (R5).** `views.py`'s `ready-pr` need becomes `approve-pr`, with the
two texts above (the label `NEED_LABELS` updated). `kanban.py` shows
"awaiting approval" for an `unapproved` stop.

**Briefs (R6).** One constant, `NO_APPROVAL_LINE`, is used by
`render_brief`, `conflict_brief`, the new `red_brief` and `adopt_message`.
The tripwire `tests/unit/test_tripwire_approval_label_prose.py` scans shipped
skills, agents, rules and their OpenCode/Hermes mirrors, plus the brief
renderers' output, for `approved-fr` near an add verb (`--add-label`, `add
the … label`, `label it`) outside a negation. fr-goal's SKILL.md is not
changed (it already reserves ready/merge for the operator). The fr-triage
skill's driver section gains the gate.

### B. Recording what the driver did (R8)

`model.py` gains four event kinds, schema-gated like the existing eight
(`model.py:774-781, 987-1006`):

- `UpdateEvent{kind: update, at, pr, head_before, head_after, base}`, written
  by `_update` after a successful push. `_update` returns `(sha, base)`.
- `ApprovalEvent{kind: approval, at, pr, head, voided_at: str | None}`.
- `RedHandbackEvent{kind: red_handback, at, pr, head, checks: list[str],
  delivered: session|none}`.
- `EnqueueEvent{kind: enqueue, at, pr, head, base}` (R12).

That makes four kinds. The schema moves 8 → 9, and readers accept 1–9.
`Judgements` written at 9 are refused by an older fr in the usual way, which
the existing writer stamp already handles.

### C. Red recovery (R9–R11)

A pure function `red_decision(batch, pr, head, failing, base_now, events,
session_status) -> reupdate | handback | wait | needs_you | skip` lives in
`batch_drive.py` beside `conflict_decision`:

1. `head` is some `UpdateEvent.head_after`, and `base_now != that event.base`,
   and there is no `UpdateEvent` with `head_before == head` already: `reupdate`.
   The re-update's own event then dedups it.
2. A `RedHandbackEvent` already exists for (pr, head): `skip`.
3. Two `delivered: session` red hand-backs since the last `dispatch`:
   `needs_you`.
4. Session `idle`: `handback`. `absent`/`done`: `needs_you`. Any other
   status: `wait`, with the line "its session is <status>: nothing sent,
   retried next pass".

`_walk_train` already steps over a failing PR with a `warn`. It now also emits
a `recover` action carrying the decision. The command executes `reupdate`
through the existing `_update` path, skipping the green-checks precondition
for this call only, and `handback` through `runner.message(red_brief(...))`.
A `needs_you` decision becomes a `red-pr` Need: "PR #n is red at <sha>
(<checks>) and its session cannot take it". The `warn` line stays. Its dedup
moves from the in-memory `snap.warned` to the events: a warn is printed only
on a pass that sends or decides something new.

`red_brief` sits next to `conflict_brief` in `batch_dispatch.py`. It carries
the PR url, the failing sha, the failing check names, "fix on the branch,
commit, push; leave draft/ready state and labels alone", and
`NO_APPROVAL_LINE`.

### D. Merge queues (R12–R14)

`GhClient.merge_queue_required(repo, branch) -> bool`:

- REST `rules/branches/{branch}`, any `type == "merge_queue"`, in both GitHub
  backends.
- `UnsupportedBatchOps` returns `False`. A forge without the concept has no
  queue; that is not an error.

`GhClient.pr_enqueue(repo, number, *, head_sha)`:

- `RealGhClient`: `gh pr merge --auto --match-head-commit <sha> --<method>`.
- REST and unsupported backends: raise.

`pr_view` gains `in_merge_queue: bool | None` (GraphQL `isInMergeQueue`; REST
leaves it `None`).

The driver reads `merge_queue_required` once per repo per pass. In queue mode:

- `_walk_train` does not pick a single head. Every approved, green, unqueued
  member gets an `enqueue` action. A queued member is `in-queue`: neither a
  candidate nor a stop.
- `_land`'s behind-update is not used; the queue tests on top of base.
- **Ejection:** the last event for the PR is an `EnqueueEvent` at the current
  head, the PR is open, `in_merge_queue` is false, and it is not merged. Then:
  - checks green → re-enqueue if `base_now != event.base`, otherwise a
    `needs_you` "ejected from the merge queue";
  - checks red → `red_decision`, case 2.
- Under `forge.api: rest`, the `enqueue` action is replaced by a held line,
  "`<repo>` requires a merge queue and forge.api rest cannot enqueue", warned
  once per pass.
- `--max-inflight` is unchanged: a queued PR's batch is still at stage
  `pr-open`, which it already counts (`batch_drive.py:52`).
- Board: `kanban.py` shows "in merge queue".

**CI (R14).** `ci.yml` and `acceptance-report.yml` add `merge_group:` to `on:`.
Jobs that read `github.event.pull_request.*` or `github.base_ref` take the
merge-group equivalent (`github.event.merge_group.base_ref`/`base_sha`): in
particular `change-fragment`'s base ref and any `head_ref` use. A test pins
that both files carry the trigger. `ci-budget.yml` needs no change: it watches
workflow names, not events.

### E. `batch merge` and held batches (R7)

In the no-ids branch of `batch merge` (`triage_batch_cmd.py:2187-2272`), the
held batches are partitioned out before the plan prints. Each is printed as
`skipped <id>: held by <scope>`, the rest proceed, and an all-held queue exits
0 with "nothing to merge". The ids path keeps `_refuse_held`.

### F. Release identity and protection (R15–R17)

`release.yml`:

```yaml
- id: app-token
  if: vars.FR_AUTOMATION_APP_ID != ''
  uses: actions/create-github-app-token@<pinned v1 sha>
  with: {app-id: "${{ vars.FR_AUTOMATION_APP_ID }}", private-key: "${{ secrets.FR_AUTOMATION_APP_KEY }}"}
- uses: actions/checkout@…
  with: {token: "${{ steps.app-token.outputs.token || github.token }}", …}
```

Any later `gh` call in the job uses the same token. The header's "no CI runs
on the release commit" becomes two sentences, one per mode. With the app, CI
and release.yml run once more on the release commit; that release run is a
no-op, as `test_two_runs_back_to_back_are_safe` already covers.
`test_header_states_the_no_ci_property_and_the_bypass_actor` is rewritten to
pin both modes. `release.py`'s protection-refusal message names the app.

`scripts/configure-main-protection.sh` drives `gh api` against
`repos/{repo}/rulesets/{id}` (`PUT`, merged from a `GET`, never a blind
overwrite):

- **`--stage bypass`** adds `{actor_type: Integration, actor_id: <app id>,
  bypass_mode: always}` and sets `FR_AUTOMATION_APP_ID` via `gh variable
  set`. The app id is resolved from `gh api orgs/{org}/installations`.
- **`--stage require`** adds `required_status_checks` (`ci-ok`,
  `strict_required_status_checks_policy: true`). It refuses unless `--stage
  bypass` is already in place, and unless the newest release tag's commit was
  pushed by the app (`gh api repos/{repo}/commits/<sha>` committer/author
  login) or `--force` is given.
- `--dry-run` prints the PUT body.

The runbook `docs/merge-protection.md` covers:

- the operator's one UI step: generate the app key, then `gh secret set
  FR_AUTOMATION_APP_KEY < key.pem`;
- the two stages, in order;
- how a consumer repo adopts the same protection;
- that the driver needs no config for a merge queue.

## Out of scope

- Signed (`ssh-keygen -Y`) approvals, a second forge identity, credential
  injection by fr-isolation, and a Bash guard denying ready/merge. The label is
  a deliberate stop-gap. A future design replaces it, and this change files that
  as a follow-up issue at close-out.
- GitLab/Gitea merge trains (detection reports "no queue" there).
- Changing who may mark a PR ready outside fr.

## Verification

strategy: candidate
- merge-train-label-gate: candidate — scenario `tests/scenarios/merge-train-label-gate.sh` over the fake forge.
- merge-train-red-recovery: candidate — scenario `tests/scenarios/merge-train-red-recovery.sh`.
- merge-train-queue: candidate — scenario `tests/scenarios/merge-train-queue.sh`.
- batch-merge-skip-held: candidate — scenario `tests/scenarios/batch-merge-skip-held.sh`.
- approval-label-created: candidate — covered by the label-gate scenario's first pass.
- approval-board-and-briefs: candidate — the label-gate scenario renders the board; the prose tripwire runs in CI.
- ci-merge-group-trigger: none — a unit test over the workflow YAML is the whole claim; there is nothing to walk.
- release-pushes-as-app: live — only a real release on GitHub with the app's secret shows who pushed it.
- main-requires-ci-ok: live — only the real ruleset shows a behind PR blocked and the release bot bypassing it.

## Test Plan

Post-merge, operator plus agent (R17):

1. Operator: generate a `derio-fr-automation` private key in the GitHub UI and
   run `gh secret set FR_AUTOMATION_APP_KEY -R derio-net/super-fr < <key.pem>`.
2. Agent: `scripts/configure-main-protection.sh --stage bypass`. Confirm the
   variable and bypass actor in the printed ruleset.
3. The next release (any merged PR with a fragment): confirm the `release:`
   commit's pusher is the app, that CI ran on it, and that the second
   release.yml run was a no-op. This flips `release-pushes-as-app`.
4. Agent: `scripts/configure-main-protection.sh --stage require`. Then
   confirm on a real PR behind `main` that GitHub blocks merge until it is
   updated, and that the following release still pushes. This flips
   `main-requires-ci-ok`.
