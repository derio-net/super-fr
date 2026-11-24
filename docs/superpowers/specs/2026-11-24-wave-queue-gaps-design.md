# Wave merge queue — hand-backs onto the slot ahead, overlap-aware waves, operator entries

Issue: derio-net/super-fr#1677. Builds on #1602 (the wave merge queue, spec
`2026-11-19-wave-merge-queue-design.md`) and #1647 / PR #1669 (CI economy, spec
`2026-11-24-ci-economy-design.md`), whose `generated:` globs this spec reads.

## Background

The wave merge queue (`fr.triage.wave_queue`, executed by `fr.triage.queue_exec`) builds
one combination per entry on `fr-queue/<scope>/slot-<k>` and lands the green prefix by a
fast-forward of `main` (`queue.land: push`) or by forge merges (`queue.land: merge`).
Three gaps remain.

1. **A conflict hand-back names `origin/main`.** A real conflict met while building an
   entry (`queue_exec.build`, `queue_exec.py:270`, on `prev`: the queue's base or the
   combination ahead, `:304-335`) raises `MergeConflictError` (defined in
   `batch_merge.py:42`, built by `queue_exec._conflict`, `queue_exec.py:152`), which
   `QueueExecutor._build` turns into a `BuildConflict(head, paths, reason)`
   (`queue_exec.py:1269-1271`, `wave_queue.py:175`) and the planner into a `queue-eject`
   (`wave_queue.py:896-906`). For a batch, `_Driver._queue_hand_back`
   (`triage_batch_cmd.py:6966`) rebuilds the exception from the action (`:6979`) and goes
   through `_conflict` (`:6315`), `conflict_decision` (`batch_drive.py:919`) and
   `_hand_back` (`triage_batch_cmd.py:6602`), whose brief is
   `batch_dispatch.conflict_brief(..., base=ctx.main)` (`batch_dispatch.py:279`):
   "`git fetch origin && git merge origin/main`". A session that merges `main` while
   entries ahead are still queued conflicts again once they land. On 2026-11-24 merging
   the slot commit by hand (`24130aa17`, #1628 ahead of #1630) made #1630 land-ready the
   moment #1628 landed at that sha. `conflict_decision` skips any head that already has a
   `ConflictEvent` (`batch_drive.py:934`), so no brief is ever re-issued.
2. **Waves ignore file overlap.** `batch.suggest` (`batch.py:780`) groups free issues by
   cited path (`cited_paths`, `:770`; `_same_file`, `:775`), theme and pattern;
   `batch create --wave` and `batch edit --wave` (`triage_batch_cmd.py:914`, `:964`)
   write the wave with no look at what its other batches change. `batch.merge_order`
   (`batch.py:845`) already reads PR files for the old train.
3. **Only fr's own PRs enter the queue.** Batch PRs, and the R32 entries (`OtherEntry`,
   `wave_queue.py:187`; `QueueEntryKind`, `model.py:1109`) admitted in `drive_pass`'s
   step 3 (`batch_drive.py:2106-2109`). A housekeeping PR is admitted by
   `_Driver._housekeeping_reads` (`triage_batch_cmd.py:7241`): open, head ref `chore/ops-`,
   trusted author (`distrust`, `batch.py:250`), approval settled on the queue's own
   `approval` events (`approval.settle_entry_approval`, `approval.py:318`). Any other PR
   is merged by hand, which re-conflicts every queued PR.

PR #1669 adds `TriageConfig.generated` (the globs of files the repo's `mirrors:` write in
whole), `fr.triage.regen.outside_generated` and a `Regen` port to `queue_exec.build`. The
module line budgets (`tests/unit/test_tripwire_module_budget.py:22,25`) leave
`triage_batch_cmd.py` 14 lines and `batch_drive.py` 4, so this change moves code out of
both (§E) rather than raising a budget.

## Requirements

R1. In a repo whose queue lands by push (`queue.land: push`) with merge method `merge` or `squash`, the hand-back of an entry the queue ejected for a real conflict met while building it names its stack target: the commit the entry will be stacked on when it re-enters, which is the last standing combination of the queue after the ejection (its slot ref `fr-queue/<scope>/slot-<j>` and sha), or the default branch and its sha when no combination stands. The brief tells the session to fetch that ref and merge that sha, not `origin/main`, and to stop and wait for a re-issued brief if the fetched ref no longer contains the sha. Under `land: merge` or method `rebase` the brief names `origin/<default>` as today, because there the slot commit never becomes `main` or the merge commit would not be replayed.
R2. A commit leads to `main` when git reads it as an ancestor of the queue's last standing combination, or of the queue's base when none stands. The `conflict` event records the commit its brief named (`onto`). While the entry's head is unchanged and that commit no longer leads to `main` (an entry ahead was ejected, or `main` moved outside the queue), the driver re-issues the brief with the new stack target.
R3. A re-issued brief is recorded as a `conflict` event marked `reissue` at the same head and never counts against the hand-back budget. A head whose latest `conflict` event names a commit that still leads to `main`, or names none, is not briefed again.
R4. Under R1's land and method, an entry whose head reaches a commit the queue built (any `queue_built` sha of this scope's records for the repo) that no longer leads to `main` is never built, whatever its approval: it carries an ejected entry's change. The driver holds it and briefs its session once per head: reset the branch to the newest hand-back head that reaches no such commit, re-apply by cherry-pick its non-merge commits made since that head, merge the stack target, and push with `--force-with-lease`. This is the one brief that allows a force-push. When no hand-back head is free of such a commit, the entry is held with a Needs-you entry instead.
R5. When git cannot read what R2 or R4 needs (a missing object, a failed command), the entry is held for the pass with a warning, as an unreadable patch-id holds an approval; it is never read as leading to `main` or as carrying nothing.
R6. For an entry that is not a batch, the hand-back of R1, R2 and R4 is a Needs-you entry naming the commit to merge.
R7. A batch's expected change set is its PR's changed files when a PR exists, else the file paths its members' judgement details and issue bodies cite (`cited_paths`; an untrusted issue's body is skipped). Paths matching the repo's `generated:` globs or `version.files` are left out. Two cited paths name one file when one is a path suffix of the other.
R8. `fr triage batch suggest` lists each pair of open batches in one wave whose expected change sets overlap, with the wave, the shared paths and two remedies: merge them into one batch, or move one to another wave (naming the next wave number).
R9. `fr triage batch create --wave` and `batch edit --wave` write the batch, then print every overlapping pair the new or moved batch forms in its wave, in R8's form. They never refuse for an overlap.
R10. The dispatch brief of a batch that overlaps another open batch of its wave names that batch and the shared paths, and tells the session that whichever of the two lands second gets the queue's conflict hand-back, naming the commit to merge, and must resolve it then.
R11. `fr triage queue add --pr <n>` and `fr triage queue remove --pr <n>`, taking the scope options every triage command takes, write through the one judgements writer and the scope's state sync. Each records an event naming the PR and the forge login the command authenticates as; `add` also records `--preapproved`. `add` refuses a PR that is not open, whose base is not the default branch, whose branch is in another repository, whose author the repo does not allow, that is already added, or that is a close-out, export, archive or housekeeping entry. A batch PR of the scope is already an entry: `add` refuses it without `--preapproved` and with it records the preapproval alone. `remove` refuses a PR that is not added; for a batch PR it withdraws the preapproval. A write the state refuses (changed since read, or a refused push) exits 2 and says to run the command again.
R12. An added PR that is not a batch PR is a queue entry of kind `operator`, admitted only under a housekeeping PR's rules: open, same-repo branch, allowed author, a valid `approved-fr` settled on the queue's `approval` events and pinned to the patch-id (R12 of #1602), and its own head's checks green. It is stacked, tested, landed and reported like any other entry. A PR that is in a combination when it is removed is ejected with reason `operator`.
R13. For a preapproved PR (added, not removed), the driver adds the `approved-fr` label itself when the login that added it is an allowed author of the repo, the PR's own head checks are green, the forge does not read it as conflicting, and no queue conflict is recorded at that head. The usual settling then records the approval at that head and patch-id (the batch's `ApprovalEvent`, or the queue's `approval` for an operator entry), and a later void follows the usual rule. The driver approves again at each later head that meets the same conditions while the PR stays added, and comments on the PR naming each head and patch-id it approved. This is a deliberate widening: any push to that branch by someone with write access lands once green; `queue remove` ends it.
R14. An added PR joins whichever queue of its repo is open, whatever that queue's wave. When none is open, a ready added PR opens a one-entry between-waves queue at once, unless the lowest unfinished wave has a ready entry, in which case that wave's queue opens and the added PR joins it.
R15. A wave's open queue does not drain while an operator entry is pending: added, not removed, open and not landed. The drain, the hold's `drained` push and the release that follows therefore include it. A pending entry that has blocked the drain for `queue.stall_hours`, counted from the later of its add and the queue's last landing, is a Needs-you entry naming `fr triage queue remove --pr <n>`. A between-waves queue drains by its existing rule (its entry landed, gone, or ejected at its head).
R16. The `queue_add` and `queue_remove` events and the `conflict` event's `onto` and `reissue` fields are new shapes of the triage state. Judgements schema 14 holds them: fr reads 1–14 and writes 14, and a file stamped below 14 that carries any of them is refused.

## Design

### A. The stack target and the carry (R1–R6)

`MergeConflictError` (`batch_merge.py:42`) gains `onto` (the sha the entry was built on).
`BuildConflict`, the `queue-eject` action and `_queue_hand_back`'s rebuilt exception carry
it. The stack target, though, is computed after the ejection (R1), so it comes from the
planner, not from `prev`.

A new pure module, `fr.triage.queue_handback`, holds:

- `stack_target(rep) -> (sha, slot | None)`: the last standing combination of the replay
  after this pass's ejections, else its base;
- `brief_mode(config, method) -> "slot" | "main"`: R1's land and method rule;
- `reissue_due(events, head, leads) -> bool` and the lineage-aware skip rule that
  `conflict_decision` delegates to (R2, R3);
- the conflict, re-issue and carry briefs (`conflict_brief` moves here from
  `batch_dispatch`, re-exported there).

Git answers ancestry, so the command layer computes two new `QueueSnapshot` inputs
through `gitseam`, once per pass per entry:

- `leads: Mapping[str, bool | None]`: for each entry with a `conflict` event at its live
  head, whether that event's `onto` is an ancestor of the stack target; None when git
  cannot read it (R5);
- `carries: Mapping[str, tuple[str, ...] | None]`: for each candidate entry, the built
  shas (every `queue_built` sha of this scope's records for the repo) among
  `git rev-list <head> ^<stack target>`. That is one `rev-list` per entry head, and the
  result is intersected with the built set. A head's carry is fixed for a given target, so
  it is cached per `(head, target)` across passes. None means unreadable (R5).

`_plan_open` drops a carrying entry from the build window and emits `queue-carry`
(R4). It drops an unreadable one with a `queue-warn`, and emits `queue-reissue` for an
entry whose `onto` no longer leads (R2). `_Driver` delivers them through the existing
hand-back path (idle session, fresh conflict session, held), writing
`ConflictEvent(onto=…, reissue=True)` for a re-issue. `handbacks_since` counts no
`reissue` event. For R4 the command picks the reset head: the newest `conflict` event
head whose own carry is empty. A non-batch entry's hand-back is a `queue-need` with the
same words (R6).

### B. Overlap (R7–R10)

A new pure module, `fr.triage.wave_overlap`:

- `expected_paths(batch, judgements, facts) -> frozenset[str]` (R7);
- `wave_overlaps(batches, judgements, facts, *, only=None) -> list[Overlap]`. Each
  `Overlap(wave, a, b, paths)` names an unordered pair of open batches (`is_open`,
  `batch.py:352`). With `only`, it returns the pairs that batch forms;
- `overlap_line(o, next_wave)`, the R8 sentence, and `overlap_brief_lines(batch, …)`
  for R10.

`batch suggest` prints the lines after its groupings, `create`/`edit` print them after the
write, and the dispatch brief (`batch_dispatch`) appends the R10 lines.

### C. Operator entries (R11–R15)

**State.** `Judgements` gains `queue_requests: list[QueueAddEvent | QueueRemoveEvent]`.
Each event has `kind`, `at`, `repo`, `scope`, `pr`, `by`, and `preapproved` on the add.
The pure module `fr.triage.queue_requests` folds them: `added(requests, repo, scope)`
gives each PR whose latest event is an add, with its preapproval, add time and adder.
`QueueEntryKind` gains `operator`.

**Verb.** `fr triage queue add|remove` lives in a new `commands/triage_queue_cmd.py`
registered on the triage app. It takes the scope options and `_load_state` / `_write` as
`batch defer` does, reads the PR with `pr_view`, reads the allowed authors as
`_housekeeping_reads` does, and reads the login with `GhClient.viewer_login`
(`ghclient.py:469`, which both GitHub clients implement). It refuses the R11 cases
before it writes.

**Driver reads.** `_housekeeping_reads` moves to a new module,
`fr.triage.operator_entries`, beside the new `operator_reads`. For each added PR that is
not already an entry, `operator_reads` settles the approval with
`settle_entry_approval(..., QueueEntryRef(pr=n, kind="operator"))`. For each preapproved
PR, batch PRs included, it applies R13 with `--yes`: it adds the label, writes the audit
comment, and lets the next settle record the approval. It returns the admitted
`(LivePr, at)` pairs and the pending entries. `drive_pass` step 3 admits them as
`Admitted("operator", …)`.

**Planner.** `_cands` gives an `operator` entry the open queue's wave (R14), and
`_plan_idle_open` lets a ready one open a between-waves queue (R14). `_drained` refuses
a wave queue while `QueueSnapshot.pending_operator` names an entry. `_stall_need` gains
the R15 Need. An entry removed while in a combination gets a `queue-eject` with reason
`operator`.

### D. Schema (R16)

`JUDGEMENTS_SCHEMA` moves to 14 and the read literal widens to 1–14. `Judgements`'
validator refuses `queue_requests` below 14, and a `conflict` event with `onto` or
`reissue` below 14, beside the existing `queues:` and `patch_id` checks. The one writer
stamps 14. AGENTS.md's "reads 1–13 and writes 13" line moves to 14. Triage state is not
an artifact kind, so artifact-versioning's migration rule does not apply (as in #1602).

### E. Line budgets

`conflict_decision`, `handbacks_since` and `red_decision` move from `batch_drive.py` into
a new `fr.triage.handback_rules` (re-exported, so no import changes elsewhere), which
frees room for the snapshot fields and the step-3 wiring. `_housekeeping_reads` moves out
of `triage_batch_cmd.py` (§C), which frees room for the hand-back changes. No budget is
raised.

### F. Tests (CI)

1. The brief names `fr-queue/<scope>/slot-<j>` and its sha (and the default branch when no
   combination stands), and `origin/<default>` under `land: merge` and under `rebase`
   (R1).
2. An ejection ahead and a foreign move of `main` each re-issue once at the same head, with
   no budget spent. A third pass with nothing moved sends nothing (R2, R3).
3. Over bare git remotes: a head carrying an ejected entry's combination is not built and
   is briefed once with the right reset head. A head that merged a combination that
   landed mid-push, or was rebuilt fresh, is not held. An unreadable object holds the
   entry (R4, R5).
4. A non-batch entry's hand-back is a Need naming the commit (R6).
5. `expected_paths` covers PR files against cited paths, suffix matching, the
   generated/version exclusion and an untrusted body skipped (R7).
6. `suggest` and `create`/`edit --wave` print the pair and the remedies and still write;
   the later dispatch brief names the overlap (R8–R10).
7. `queue add` covers each refusal, the recorded login, a batch PR with and without
   `--preapproved`, and a state write refused (R11).
8. An operator entry is admitted under trust and approval, voided on a diff change,
   stacked and landed, and ejected on `remove` (R12).
9. Preapproval: the label is added only under all of R13's conditions, an adder who is
   not allowed gets nothing, the approval is renewed at the next green head, and each
   approval has its audit comment (R13).
10. An add while idle opens a between-waves queue, or joins wave N when wave N has a
    ready entry (R14). A wave queue waits for a pending entry and gives the stall Need;
    a between-waves queue does not stall (R15).
11. Stamp refusals below 14, and a round trip at 14 (R16).

## Out of scope

- Moving batches between waves automatically. fr reports overlaps and never edits a
  wave by itself.
- Red ejections (R13 of #1602) keep `red_decision` as today.
- Overlap across repos. Overlap is per repo, per wave.

## Verification

strategy: candidate
- wave-queue-handback-slot: none — proven by the CI suite (§F 1, 2, 4): the pure planner over queue records, and the hand-back over a fake forge and real bare git remotes.
- wave-queue-handback-carry: none — proven by the CI suite over real bare git remotes and the pure planner (§F 3).
- wave-queue-overlap-report: none — proven by the CI suite: the pure overlap module and the CLI over fixture facts (§F 5, 6).
- wave-queue-operator-entry: none — proven by the CI suite with the fake forge and the pure planner (§F 7, 8, 10, 11).
- wave-queue-operator-preapproval: none — proven by the CI suite with the fake forge: labels, checks, mergeable state and comments (§F 9).
- wave-queue-gaps-live: live — only a real wave on this repo shows a hand-back merged onto the slot commit landing without a second conflict, and an operator-added PR shipping in the wave's release.

gate: wave-queue-gaps-live=tester

## Test Plan

1. Post-merge, live: in the next wave on this repo, a conflict hand-back names `fr-queue/<scope>/slot-<j>`; after the session merges it, the PR lands with no second hand-back; a PR added with `fr triage queue add` lands in the same wave and is in the release the drain starts. (row `wave-queue-gaps-live`)
