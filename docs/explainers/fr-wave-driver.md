---
title: "The wave driver: Running a Backlog Without Babysitting It"
date: 2026-11-12
draft: false
tldr: |
  Triage turns a backlog into batches, each one run and one pull request. The wave driver
  is the loop that takes those batches through to merged: it dispatches them in waves up to
  a cap, merges what you approved, and closes out what landed. It keeps no state of its own,
  so you can stop it and start it again.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-triage/SKILL.md
  - packages/fr/src/fr/triage/batch_drive.py
  - packages/fr/src/fr/commands/triage_batch_cmd.py
  - docs/cloud-setup.md
reviewed: 2026-11-27 queue-followups phase 2, a removed label ends an approval, a label on a head with a real conflict waits and is recorded once the conflict is fixed, and the driver says on the pull request why it removed a label (R1-R3); queue-followups phase 1 review, a gated, held or already closing member and a batch with no wave hold no wave close-out; queue-followups phase 1, a queue-landed batch closes out at once, a wave close-out waits for every member and names them, a close-out deadline wakes a quiet paced pass, and the conflict probe sorts conflicts as the queue does (R4-R7); 2026-11-27 still true; shared-helper refactor (batch arch-shared-helpers), no behaviour change; 2026-11-26 landing-method, the configured merge_method wins over the forge's default, a push landing holds a squash or rebase method, and a rebase under queue.land merge warns once (R1-R4, R8); 2026-11-25 `generated` joins the guarded `.fr/triage.yaml` keys; under quiet and stealth the driver drops the guarded `.fr/triage.yaml` keys from an unprotected configuration branch; the state lives in the cache repository (S1 R7, R17); 2026-11-25 batch merge-readiness phase 2, each Batches card leads with its readiness verdict and facts (the merge-ready, in-queue and awaiting-approval hints are gone), close-out, archive and export pull requests carry one too; 2026-11-25 batch merge-readiness phase 1, a pull request enters the queue only once its run delivered (every cursor at its head naming its branch at `deliver` done), else it is held as approved, not delivered; 2026-11-25 still true after wave-plan-file-overlap (the driver's board shows plan overlaps; nothing the page describes changed); 2026-11-25 wave-queue-gaps lens review, the carry brief's push is leased on the head it names, every added pull request gets a Need naming queue remove, an unreadable commit becomes a Need after stall_hours, a preapproval re-checks the base, queue add needs a collected PR; wave-queue-gaps phase 3 adds the overlap report (batch suggest, create and edit --wave, the dispatch brief); wave-queue-gaps phase 2 review, the driver reads a repo with no batch, does not stop while an added pull request is unlanded, and records a preapproval before it labels; 2026-11-25 wave-queue-gaps phase 2, `fr triage queue add|remove` puts your own pull request in the queue, it opens or joins a queue, holds the wave's drain until it lands, and `--preapproved` lets the driver approve each green head; 2026-11-24 wave-queue-gaps phase 1, a conflict hand-back names the stack target, is re-issued free when it moves, and a carrying head is held and briefed; 2026-11-24 batch closeout-truth, approved-fr admits a held close-out to the queue, a stale artifact the close-out does not archive delays it, the close-out session closes; 2026-11-24 fix/install-stable-by-default, the cloud driver's self-update and the setup script install the release itself, never main (this repo's post_merge asks for --version main); still true; 2026-11-23 still true; the Python 3.14 floor reformats covered code (unparenthesised `except A, B:`, PEP 695 generics), syntax only (#1589); 2026-11-23 pr-readiness-wait phase 1, every driver brief gains one sentence (the driver owns the PR's mergeability and CI, so the session runs no `fr pr settle` loop); still true; 2026-11-22 an outside issue is admitted with fr triage admit, not the label alone (triage-hardening); gate names, runner status and timestamp refactors preserve this interface; 2026-11-20 batch train-truth R24 the driver sorts failures into transient and refusal (a push the remote refused is transient, a lost race on the state ref a refusal), keeps a failure ledger, can run under a supervisor (signalled or orphaned it exits 0, else with the driver's code), writes drive.log (drive status, drive log, the board's Activity panel and Driver stopped need) and hands red and conflicting drafts back early, one fetch per repo per pass, the merge queue's base read included; 2026-11-19 batch docs-wording changes help text and docstrings only (bracketed help renders, first lines shortened for STE, `fr ops gate` hint names the full scaffold command); still true; 2026-11-19 the driver's page memory (drive-pages.json holds unfinished waves and an owed flag, no measurement) is kept across processes and carried by the state ref; the driver re-renders every page after the board and snapshots at a wave's finish (triage-pages-ux R6, R7). 2026-11-18 the pages have one name each (batches.html, fr triage batches; the Backlog holds Needs you now). 2026-11-17 a batch with a member the intake rule rejects is blocked (batch triage-intake); batch release-truth, cloud-setup.md now says the doctor compares release candidates; 2026-11-21 wave-merge-queue phase 7 fixes, requeue targets, the marker comment's trust and scope, the close-out body written once; 2026-11-21 wave-merge-queue phase 7, the queue line, the marker comment, the wave report, defer, requeue and queue-retry; 2026-11-20 wave-merge-queue phase 6, one close-out per wave that migrates what it archives and a DevOps barrier through labels; wave-merge-queue phase 5, every merge is a queue entry and the train is gone; 2026-11-21 wave-merge-queue lens fixes, a moved block of changes, a hand-edited merge and a rewritten branch void an approval, and a pr-open batch waiting on a later queue takes no slot; wave-merge-queue phase 1 fixes, a moved identical change keeps an approval (stated limit, since replaced); wave-merge-queue phase 1, an approval is pinned to the pull request's diff (its patch-id), not its head; 2026-11-19 batch docs-wording changes help text and docstrings only (bracketed help renders, first lines shortened for STE, `fr ops gate` hint names the full scaffold command); still true; 2026-11-17 a batch with a member the intake rule rejects is blocked (batch triage-intake); batch release-truth, cloud-setup.md now says the doctor compares release candidates
---

## Why a loop and not a checklist?

[fr-triage](fr-triage.md) ranks a backlog and groups related issues into **batches**. A batch
goes the same way as any goal: one [fr-goal](01-fr-goal.md) run that ends in one pull
request. A batch created or edited with `--skill debug` runs fr-debugging instead.

Twenty issues become five or six runs, and then the work that is left is bookkeeping. You
start the runs in the right order and keep only a few going at once. You merge each pull
request when it is ready, and run the repo's install step so your tools match what merged.
You archive each finished run.

That bookkeeping is mechanical and easy to get wrong when done by hand late in the evening.
`fr triage batch drive` is the loop that does it. It does not judge anything and it never
approves a pull request. Every decision that needs a person stays with you; the driver does
the rest, in the same order, every time.

<!-- site:figure wave-of-batches -->

## What are batches, waves and `after`?

A batch carries two optional fields:

- **`wave`**, a number. Batches of the same wave may run at the same time. Lower waves go first.
- **`after`**, a list of batch ids that must be **merged** before this one may start. Only a
  merged batch meets an `after`: a dispatch, or an open pull request, is not enough.

You set them with `fr triage batch create` and `fr triage batch edit` (`--wave N`,
`--after ID`, the second repeatable). These verbs refuse a batch id that does not exist, a
batch that names itself and a cycle, and leave the file as it was. If a batch's dependency
ends up cancelled, abandoned or `partial`, the driver reports the batch as **blocked** and
never dispatches it; that one needs you. A batch is also blocked while one of its issues is
from an outside author that no operator admitted. `fr triage admit <key>` on that issue lifts
the block, and the next pass dispatches the batch. The label alone does not, and an edit to
the issue after admission blocks the batch again.

Use waves for "these are independent, start them together" and `after` for "this one edits
what that one adds". A batch may have no wave. With no batch ids on the command line,
`drive` takes the batches that have a wave, and every batch when none has.

Two batches of one wave that change the same file may conflict when the second one lands.
So `fr triage batch suggest`, and `batch create` or `batch edit` of a batch in a wave, print each
such pair: the wave, the shared files, and two ways out. You can merge the two batches into one, or
move one to the next wave. fr guesses a batch's files from its pull request, or else from the
paths its issues name. It leaves out generated files and the version files, because the queue
settles those itself. The verbs still write the batch, and the later dispatch brief tells the
session that whichever batch lands second gets the conflict hand-back.

## What does one pass do?

The driver runs in passes. Each pass starts by re-reading the forge, so it works from what
is true now, not from what it remembers. In order, a pass:

1. **Reports what it will not touch.** The driver leaves alone a batch holding an issue that
   another scope has claimed. It also leaves alone a pull request on a batch branch that is
   not that batch's, or one by an author the repo has not allowed (`pr_authors` in
   `.fr/triage.yaml`, by default you). It names a pull request that is not the batch's once,
   and never merges it. It reports a batch another scope holds as held on every pass.
2. **Merges what is ready, through one queue.** Every merge the driver makes goes
   through the wave merge queue. Per repo, the queue opens for the lowest wave that still
   has an unfinished batch, once the first pull request of that wave is ready. A pull
   request enters the queue only when it is open, its checks are green, it carries
   **your** `approved-fr` label, and its run has delivered: every run cursor at the pull
   request's head that names its branch records `deliver` done. The driver marks nothing ready for you before you approve it: it holds an
   unapproved pull request as awaiting approval, and the queue goes on without it. It holds
   an approved pull request whose run has not delivered as "approved, not delivered", and
   never marks it ready or merges it. A pull
   request you approved that is still a draft is marked ready by the driver when the queue
   builds it. Your
   approval belongs to the pull request's own changes, not to one commit: a merge of the
   base branch with no conflict to resolve, or an empty commit, keeps it. Other changes to
   its diff void it and remove the label: an edit (even to spaces or to a binary file), a
   block of changes moved to another place in the file, a merge you resolved by hand, and a
   branch rewritten. If git cannot read the diff in one pass, the approval is held for that
   pass and the label stays.

    Your label is the approval, so taking it off ends the approval. The driver records
    that and writes nothing to the pull request. To approve again, add the label again.
    If you add the label while the pull request has a conflict the queue cannot resolve,
    the driver waits: it keeps the label, records nothing, and says so once. When the
    conflict is fixed, it records your approval at the new head, so you do not need to
    approve a second time. Each time the driver removes the label itself, it writes one
    comment on the pull request that says why and what to do next. It writes it once per
    head, and not at all when the repo turns comments off.

    The queue never changes a pull request's branch. It builds each ready pull request on
    the base branch and on the ones ahead of it, tests that combination on a branch of its
    own, and lands the longest green run with one atomic push. The collected close-out, an
    archive pull request, the state export and a DevOps housekeeping pull request are
    queue entries too. Each enters under its own rule: the close-out and the archive and
    export pull requests under the checks that let the driver merge them unreviewed, and the
    housekeeping one with your label. When the checks of a combination fail twice, or the
    pull request conflicts, it leaves the queue and the driver hands it back to the batch's
    session if that session is idle, at most twice per dispatch. If the session is gone, or
    after those two hand-backs, the pull request shows under **Needs you now**. A cancelled
    check does not count as failed. CI cancels a run when a newer run replaces it, so the
    driver waits for the new run. If no new run comes within `queue.check_wait_minutes`, the
    check shows under **Needs you now**, the same as a check that never reported. Some
    conflicts are not real, and the queue settles them itself. Two pages that both moved
    their `reviewed:` date keep the later date. A generated file, or a generated block in a
    page, is written again by the commands the repo lists as `mirrors:` in
    `.fr/triage.yaml`, and the files those commands write in whole are listed as
    `generated:`. The commands come from the base branch, but the scripts they run come
    from the pull requests in the combination. The queue trusts that code as far as it
    tests it. The commands run in a copy of the files with no git folder, with no forge
    token, no SSH agent and an empty home folder, and the queue takes back only the
    generated files they wrote. This keeps a mistake small, but it is not a sandbox: the
    commands run as your user. If a command fails, or it changes any other file, the pull
    request goes back to its session. A repo whose
    base branch requires a forge merge queue, or that has not said how its checks run on the
    combinations (`queue.ci` in `.fr/triage.yaml`), is held, and the driver says what to add.
    A pull request that `gate:devops` holds before merge is a barrier. The DevOps stage
    adds the label `fr-queue:release` (see [fr-devops-gate](fr-devops-gate.md)). The driver
    admits it only with that release at its current diff, and lands it as the last entry of
    its push. Nothing lands behind it until the stage adds `fr-queue:postmerge-done`, but the
    queue builds and tests the entries behind it meanwhile. After it lands, **Needs you now**
    names `fr ops gate --run <id>`.

    **How you see the queue.** Each pass prints one line per repo: the wave, the base, each
    entry with its state (building, testing, green, ejected, waiting or barrier), what has
    landed and the state of the hold. The Batches page shows the same lines. Each queued pull
    request also carries one comment that starts with `<!-- fr-queue -->`. The driver edits it
    as the pull request moves: queued at a place, testing in a combination, ejected (with
    why, and what to do), landed in a wave, or left the queue (deferred or requeued). Only a
    pull request in the open queue has one: a pull request that waits for a later wave has
    none, and the place counts entries that are in testing. The driver trusts only a comment
    that a trusted author wrote. No comment is written where `forge.comments` is `off`. Problems go to **Needs you now**, each with a command to paste. When a wave drains,
    a report lists the pull requests that landed, were ejected or were deferred. It shows the
    CI cycles, the wall time and the approvals of each, and the release the drain asked for.
    The report goes on the Batches page. The close-out pull request's body is written when
    the close-out is built, before the drain, and the driver does not write it again. It
    carries the report as it stands then, with the close-out itself listed. What the drain
    asked of the release shows on the Batches page.

    **When the queue halts.** A push the remote refuses, or a merge the forge refuses, halts
    the queue. It then builds and lands nothing, and **Needs you now** says why. Fix the
    cause and run `fr triage batch queue-retry <owner/repo> --yes`. Without `--yes` the
    command only prints what it would do. The next pass builds again. A refusal that
    persists halts the queue anew.

    **Adding a pull request of your own.** `fr triage queue add --pr <n>` puts any open pull
    request of the repo into the queue, if it is based on the default branch and comes from
    the repo itself by an allowed author. `fr triage collect` must have read it since it
    opened, so run collect first. It lands like a housekeeping pull request: once you
    add `approved-fr` and its own checks are green. It joins the queue that is open, whatever
    the wave. If no queue is open, it opens one between waves at once, unless the lowest
    unfinished wave has a ready entry: then that wave opens and the pull request joins it.
    A wave does not drain while a pull request you added is still open and has not landed,
    so the wave's release includes it. If it has not landed after `queue.stall_hours`,
    counted from when you added it or from the queue's last landing, **Needs you now** names
    `fr triage queue remove --pr <n>`, which takes it out again. This holds whether or not a
    queue is open. A pull request the driver will not admit, for example one whose author is
    no longer allowed, goes there at once. This works in a repo with no batch too. The driver does not stop
    while a pull request you added is open and has not landed: it keeps running until it
    lands, you remove it, or it shows in **Needs you now**.
    With `--preapproved`, the driver adds `approved-fr` itself at each head whose checks are
    green and that does not conflict, while you are an allowed author and the pull request is
    still based on the default branch. It first comments the
    head and the change it approved, then records the approval at that head, and only then
    adds the label. So a push before the driver looks again does not slip in unchecked: it
    changes the diff and cancels the approval. Any later green push to the branch lands,
    so remove the pull request to stop it. While the repository's settings turn off forge
    comments or labels, the driver approves nothing: it writes no comment, label or record,
    and says so once.

    **Leaving a wave.** A batch that cannot merge need not hold its wave. `fr triage batch
    defer <id>` takes it out of the wave's queue and drain. Its pull request stays open, and
    the wave's close-out leaves it out. `fr triage batch requeue <id> --wave N` puts it in
    wave N's queue. N must be above the batch's wave, and that queue must never have opened
    (a queue that has drained has opened). `fr triage batch requeue <id>` alone puts it in
    the lowest wave whose queue has not opened yet. If every wave's queue has opened, it
    goes to the between-waves queue. The driver proposes these when one batch is all that holds a
    drain, because its hand-backs are spent or it made no progress for `queue.stall_hours`.
    It never runs them itself.

    When a batch pull request's checks fail, the driver hands it back to the batch's session
    if that session is idle, at most twice per dispatch. This holds for a draft as well as
    for a ready pull request, approved or not. A pull request with red checks is never shown
    as awaiting approval. If the session is gone, or after those two hand-backs, the pull
    request shows under **Needs you now**.
    The driver never approves, and it never waits for CI inside a pass.

    **When you upgrade:** the old driver merged a ready pull request in any repo. The queue
    does not. A repo with no `queue:` block merges nothing, and the driver says so under
    **Needs you now**. To restore merging, add `queue: {ci: push}` to `.fr/triage.yaml` and run
    every workflow that reports a required check on pushes to `fr-queue/**`. A repo with no
    CI at all takes `queue: {ci: none}`.

3. **Closes out what merged.** Each wave has one collected close-out. It starts after
   the last batch of the wave has landed and the repo's `post_merge` argument list has run
   for each landing. The driver fast-forwards its checkout, then closes the batches out:
   it records their Test Plan outcomes and archives their runs in one housekeeping pull
   request. That pull request is the last entry of the wave's queue. The queue does not
   drain, and the release does not start, until it has landed.

    A batch that the queue landed is ready for its close-out at once. A batch that merged
    outside the queue waits for its release commit, or for ten minutes. The close-out starts
    only when every landed batch of the wave is ready and the driver could read its state.
    A batch that is gated, held, or already has a close-out of its own does not count, and a
    batch with no wave stands alone. Until then the driver names the batches it waits for,
    and why. A paced pass that would
    otherwise read nothing still reads a repo whose ten minutes ran out since the last pass.

    Before it archives, the close-out migrates the artifacts it is about to archive. A run
    cursor written for an older version can be stale after a feature merges. The close-out
    runs `fr migrate artifacts --yes --path <file>` for exactly those files, as its own
    commit. Then it archives. The driver accepts that commit as part of the archive, as
    long as it changes only files the archive moves. A migration that rewrites the whole
    repository cannot run per file, and the close-out then stops there as it always did.

    A batch held by an unpassed `gate:tester` or `gate:devops` waits, and the wave's
    close-out leaves it out. Its own close-out follows once its gate passes, and it queues
    between waves; see [exit gates](fr-exit-gates.md). The driver merges closed-out archive
    pull requests only
    when they are the repo's own, green, and touch only what an archive touches. Any other
    one waits for your `approved-fr` label. The driver records the label, and drops it if a
    later push changes what the pull request changes. If the default branch holds a stale
    file that the close-out does not archive, the driver says so and starts the close-out
    only after a migration has moved that file. It can also export a finished wave's state
    at this point.

4. **Dispatches what may start.** It counts the batches in flight (dispatched, or with an
   open pull request) over every batch in the state file. A batch whose pull request is open
   but waits for a later queue (its wave has not opened) takes no slot, so later waves'
   finished work never starves a batch of the open wave. While that count is under the cap,
   it starts the next batch by wave, then merge order, then id. It skips any batch whose
   `after` batches have not all merged. A landing the queue made frees its slots on the next
   pass, not in the pass that made it.
5. **Tidies.** The driver closes a finished batch's sessions, and the close-out session
   once every batch it closed out is finished. When it sees a wave go from
   unfinished to finished while duplicate candidates exist, it prints one `dedupe` line
   naming the `fr triage check` command to judge them.

Each action prints one line, in the same words whether the driver runs once or in a loop,
and a pass ends with a one-line summary. A pass fetches each repo at most once. If that
fetch fails, every later read of that repo in the pass sees the same failure, and the pass
does not try again.

## What happens when a pass fails?

A looping driver sorts every failure into one of two kinds.

- A **transient failure** is one that another pass may heal: a forge call that timed out, a
  push that the remote refused (a permission or a hook), a git error. The pass ends and the
  driver waits. The wait starts at `--interval` and doubles after each failed pass in a row,
  up to 15 minutes (or `--interval`, if that is longer). The first pass that works resets it. After ten failed passes in a row,
  the driver stops, as if it had met a refusal.
- A **refusal** is one that only you can fix: another writer moved the state ref, another
  driver holds the scope, the forge cannot do what the driver asked, or a setting fr reads
  strictly is wrong. The driver stops with exit 2 and keeps its lease. It writes the
  cause, the message, the time, the fr version and the command to resume to the scope's
  `driver.yaml`. It also renders the Batches page once, so the stop shows there.
  Under **Needs you now** a **Driver stopped** row names the cause and the command to run,
  until the driver passes again.

`--once`, a run without `--yes` and the cloud entry `fr triage drive pass` keep their exit
codes for every failure.

Every refusal, every transient failure and every crash is counted by cause in a **failure
ledger**, `driver-failures.yaml`. The ledger and `driver.yaml` live on this host and never
travel in the state ref. A cause never holds message text, so a host name or a path cannot
leak through it. `fr triage drive failures` lists the causes, the most frequent first.
Add `--file --yes` to file one issue per cause that has none, in the scope's state repo
(or the scope's own repo). The command files each cause once, adds a comment when its count
grew, and files a new issue when the cause recurs after its issue was closed. It never
writes the message into the issue.

## How do you keep it running?

`fr triage batch drive --supervise --yes` runs a **supervisor**, and the supervisor runs the
driver as its child. It does not take the lock or the lease: the child does. It needs a
loop, so it does not combine with `--once`, and it needs `--yes`.

The supervisor restarts the driver when it ends in a way you did not ask for. An exit
with code 0, 2 or 3, or a clean stop on SIGINT, SIGTERM or SIGHUP, is deliberate: the
supervisor ends with the driver's code. After a stop on a signal, that code is 128 plus
the signal number (130 after an interrupt or a SIGTERM stop). Any other exit code, or a
death by another signal such as SIGKILL, is a crash.

The supervisor waits 5 seconds before the first restart and doubles the wait each time,
up to 5 minutes. If the driver crashes a sixth time within 30
minutes, the supervisor stops as a refusal with cause `crash-loop`, and the board shows it
as above. Each crash is counted in the ledger as `crash:<signal or code>`.

The supervisor never detaches. It stays in the session that started it. When that session's
process ends, or the supervisor receives SIGHUP, SIGINT or SIGTERM, it sends SIGTERM to the
driver and SIGKILL after 10 seconds if the driver is still alive, then exits 0. The driver also checks
that its supervisor is still its parent, between passes and during its waits, and stops
cleanly if it is not.

`fr triage drive status` tells you what holds the scope, and changes nothing. It shows the
driver's pid, whether it is alive on this host, which process supervises it, how many
restarts there were, when the last pass ran and the last refusal. It exits 0 when a live
driver holds the scope and 3 when none does. A lease that another host holds is reported
as held elsewhere and is not probed.

Everything a looping driver and its supervisor print also goes to `drive.log` in the scope's
state directory, one line each with a UTC time and a kind: `pass`, `action`, `transient`,
`refusal`, `restart` or `stop`. The file stays on this host. At 5 MB it moves to
`drive.log.1`, and the next file replaces the previous one, so two files at most remain.
`fr triage drive log` prints the last 50 lines, `-n N` changes the count, and `-f` keeps
printing new lines until you press Ctrl-C. The Batches page shows the newest 50 entries in
an **Activity** panel, newest first. With no log, the panel says no driver has run.

## Why is there a cap?

`--max-inflight` (default 4) is the most batches that may be in flight, dispatched and
unmerged, at once. It counts every batch in the scope's state, not only the ones you gave
this run of `drive`. The cap exists because every in-flight batch is a live agent session
and an open pull request somebody may have to review; a wave of fifteen would bury you.

## When does it merge, and what does it refuse?

The driver refuses to merge any of these:

- an unapproved draft;
- a pull request whose checks are pending, failing or absent;
- a pull request without your label;
- a pull request from a fork or a foreign author;
- a batch another scope holds.

It refuses to guess. When a push alters a batch's diff, fr removes the label, and you label
it again: you approved those changes, not a branch.

The driver hands a real merge conflict back to the batch's session when that session is
idle, or to a fresh session on the batch's branch. It does not wait for the queue to take a pull request. Each pass it tries every open batch
pull request that the forge shows as conflicting, draft or ready, approved or not. A pull
request that the queue holds in a slot is left to the queue, which rebases or ejects it. The try is a trial merge with the default
branch in a scratch checkout that the driver always removes. It uses the real merge's rules
for version files and lock files, so one that the driver would resolve is not a conflict. It
also sorts the conflicts as the queue's build does: a `reviewed:` stamp or a generated block
is not a conflict, and neither is a whole generated file when the repo declares `mirrors:`.
The try does not model a rebase or a mirrors run that fails.
The driver tries a given head against a given default-branch commit once for each process.
A pull request that has been handed back for its current head is not shown as awaiting
approval: its card says it is conflicting and handed back. The brief says to merge the base without
rebasing, and to regenerate generated files rather than resolve them by hand. A batch gets
two hand-backs; after that it sits in the board's **Needs you now** until you resolve it. A batch
with no session to take the conflict, because it has no dispatch and no named runner, goes there at once.

In a repo whose queue lands by push and squashes or merges, a conflict the queue meets does
not send the session to the base branch. The brief names the commit the pull request will sit
on when it comes back: the last combination still standing in the queue, by its slot branch
and commit, or the base branch when none stands. That commit is what the base branch becomes
once the pull requests ahead of it land, so a session that merges it does not conflict again
when they do. If the commit stops leading to the base branch, because a pull request ahead
left the queue or someone pushed to the base branch, the driver sends the brief again with the
new commit. That second brief is free: it does not use up one of the two hand-backs. A pull
request whose branch still holds a combination that left the queue is not built at all. Its
session gets one brief to rebuild the branch without that commit, the only brief that allows a
force-push. The push may only replace the head the brief names: if the branch moved since, git
refuses it, and the session waits for a new brief. If no head the queue handed back earlier is
free of it, the pull request goes to **Needs you now**. A pull request that is not a batch has no session, so its Need names the commit to
merge. When git cannot answer one of these questions, the driver holds the pull request for
that pass and says so. If git still cannot answer after `queue.stall_hours`, for example
because the commit is missing from the driver's clone, **Needs you now** names the commit.

A repo can set `merge_method` in `.fr/triage.yaml`. The driver uses it before the forge's
default method, because the default is only the default of the person who asks. Without
either, the driver uses the one method the repo allows. Under the quiet and stealth placements the file is on the configuration branch. There the driver ignores the keys that run commands or decide merges (`post_merge`, the version commands, `mirrors`, `generated`, `pr_authors`, `queue`, `exit`, `export`) unless the forge enforces a pull-request rule on that branch. It says so once per repo. Where a repo allows several and fr
reaches the forge through REST only, the driver refuses every merge until you name one.

When the queue lands by push, only a merge commit works. GitHub closes a pushed pull
request as unmerged if its commit is a squash or a rebase. So the driver holds the queue
of a repo that chooses one of those two methods, and its message names the fix: set
`merge_method: merge`, or set `queue.land: merge` to land through the forge's merge API.
With `queue.land: merge`, a rebase lands, but the driver warns once. A rebase puts the
branch's own commits on the default branch, and a release that finds pull requests in the
first-parent log cannot see them.

## Why can you stop it and start it again?

The driver keeps nothing of its own. It reads the dispatch, merge and close-out events
recorded in the scope's `judgements.yaml`, and the forge. Kill it between any two actions
and run it again: it repeats nothing the files can show. The one thing that can run twice is
`post_merge`, which is at-least-once; a command that is safe to repeat is a good
`post_merge`.

In loop mode it waits `--interval` seconds between passes (the flag's default applies when
you give none), and reads the forge again at the start of each. A lock file in the scope's
state directory refuses a second driver, so there is one driver per scope. `--yes` is what
makes it act: without it `drive` prints the plan one pass would follow and exits, loop mode
included.

`--once` makes a single pass. It exits 0 when it acted or everything is done, and 3 when it
did nothing and work remains (a draft, CI, a dependency, a blocked batch). It exits 2 when
it refused, and a forge write that fails exits 1. On the host, `--once --yes` refuses with
exit 2 and the looping command when its pass would dispatch a batch, because one pass
leaves the rest of the wave undone. `--single-pass` says the one pass is deliberate.

## Where do you act?

We built the driver around the few moments that are yours:

- **Approve.** Label a green batch pull request `approved-fr`.
- **Pass a gate.** A merged pull request holding `gate:tester` or `gate:devops` waits for you
  to walk it or pass it ([exit gates](fr-exit-gates.md)).
- **Unblock.** A stopped driver, a blocked batch, a conflict past its hand-backs, a failed
  `post_merge` and failing CI on a batch each show under **Needs you now** on the Backlog page. It gives one
  row per item, each linking the pull request or issue.

`fr triage batches` writes the Batches page, `batches.html`: a Kanban of every batch by stage
with four "Needs you" lanes (developer, reviewer, tester, devops). While a driver runs with
`--yes` it re-renders that page on every pass. (`fr triage board` is the old name of the
command and still works.)

Every card of a batch with an open pull request starts with one line, its verdict: for example
"Approved, merges next", "Not ready: CI running", "Approved, not delivered" or "Not ready:
queue held: <reason>". Under it, the card lists the facts that verdict came from: whether the
run delivered, the checks, the merge state, the approval, whose move it is (the session, the
driver or you) and the next action, with a link. The page and the driver read one function, so
the page never says "merge ready" for a pull request the driver would hold. The page works
from the facts it collected, and it shows when that was, because the checks, an approval's diff
and the base branch can have moved since. A close-out, archive or export pull request gets the
same lines, with its trust rule where a batch has "delivered": the rule admitted it, or this is
why it did not.

The driver keeps the other pages current too. After the Batches page, each pass that
collected re-renders the Backlog, the Issues page and History. It also
renders Origins when `origins-facts.json` exists, and Architecture when `subsystems.yaml`
exists. Each page states when it was rendered. A pass that only plans (no `--yes`), one that
stands quiet because nothing changed, and an essential-only one (the quota is low) render no
page. A page that cannot be written gives one warning for each distinct cause, and the pass
goes on.

Architecture counts lines with git, so the driver measures only on the first pass of a
process that writes pages (a restart, or each wake of the cloud driver) and on a pass in
which a wave finished. Within a process, every other pass reuses that measurement. When the
scope's repo has no usable clone, Architecture renders with no measurement and the driver
says so once. It never shows a remembered one.

The driver also stores a snapshot, the record that the Backlog's "Since last report" and the
History timeline read. It stores one on the first page-writing pass of a scope that has no
page memory yet, when the board differs from the last stored snapshot. After that it stores
one each time a wave finishes, and at no other time.

The driver keeps a small memory in the scope's state directory, in `drive-pages.json`: the
waves that were unfinished at its last page-writing pass, and whether a snapshot is still
owed. It holds no line counts. It travels in the state ref, so the rules are the same for the
host driver and for the cloud driver, which starts a new process on every wake. A wave that
finishes while no driver runs, or on a pass that writes no page, is snapshotted by the next
pass that writes pages. If the Backlog write fails on that pass, the snapshot stays owed
until a write succeeds. A file that is not exactly in that shape counts as no memory.
A snapshot taken by hand with `fr triage backlog` still
happens whenever the board changed.

## Where does it run?

On your machine the driver starts each batch's session through the `herdr` runner, so it
runs from inside a herdr pane. It can also run as a long-lived Claude Code cloud session that
runs `fr triage drive pass` on each wake. That driver runs no `post_merge`, because every
session it starts installs the current release first. The [cloud guide](../cloud-setup.md)
lists the prerequisites for that mode.
