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
reviewed: 2026-11-21 wave-merge-queue phase 7, the queue line, the marker comment, the wave report, defer, requeue and queue-retry; 2026-11-20 wave-merge-queue phase 6, one close-out per wave that migrates what it archives and a DevOps barrier through labels; wave-merge-queue phase 5, every merge is a queue entry and the train is gone; wave-merge-queue phase 1 fixes, a moved identical change keeps an approval (stated limit); wave-merge-queue phase 1, an approval is pinned to the pull request's diff (its patch-id), not its head; 2026-11-19 batch docs-wording changes help text and docstrings only (bracketed help renders, first lines shortened for STE, `fr ops gate` hint names the full scaffold command); still true; 2026-11-17 a batch with a member the intake rule rejects is blocked (batch triage-intake); batch release-truth, cloud-setup.md now says the doctor compares release candidates; 2026-11-19 the driver's page memory (drive-pages.json holds unfinished waves and an owed flag, no measurement) is kept across processes and carried by the state ref; the driver re-renders every page after the board and snapshots at a wave's finish (triage-pages-ux R6, R7). 2026-11-18 the pages have one name each (batches.html, fr triage batches; the Backlog holds Needs you now). 2026-11-17 a batch with a member the intake rule rejects is blocked (batch triage-intake); batch release-truth, cloud-setup.md now says the doctor compares release candidates
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
from an outside author that no operator admitted. The `ready-fr` label on that issue lifts
the block, and the next pass dispatches the batch.

Use waves for "these are independent, start them together" and `after` for "this one edits
what that one adds". A batch may have no wave. With no batch ids on the command line,
`drive` takes the batches that have a wave, and every batch when none has.

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
   request enters the queue only when it is open, its checks are green, and it carries
   **your** `approved-fr` label. The driver marks nothing ready for you before you approve it: it holds an
   unapproved pull request as awaiting approval, and the queue goes on without it. A pull
   request you approved that is still a draft is marked ready by the driver when the queue
   builds it. Your
   approval belongs to the pull request's own changes, not to one commit: a merge of the
   base branch or an empty commit keeps it. Other changes to its diff (even to spaces or to
   a binary file) void it and remove the label. One change does not: git compares the
   changed lines without their line numbers, so moving an unchanged block of changes to
   another place in the same file keeps the approval.

    The queue never changes a pull request's branch. It builds each ready pull request on
    the base branch and on the ones ahead of it, tests that combination on a branch of its
    own, and lands the longest green run with one atomic push. The collected close-out, an
    archive pull request, the state export and a DevOps housekeeping pull request are
    queue entries too. Each enters under its own rule: the close-out and the archive and
    export pull requests under the checks that let the driver merge them unreviewed, and the
    housekeeping one with your label. When the checks of a combination fail twice, or the
    pull request conflicts, it leaves the queue and the driver hands it back to the batch's
    session if that session is idle, at most twice per dispatch. If the session is gone, or
    after those two hand-backs, the pull request shows under **Needs you now**. A repo whose
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
    why, and what to do), or landed in a wave. No comment is written where `forge.comments` is
    `off`. Problems go to **Needs you now**, each with a command to paste. When a wave drains,
    a report lists the pull requests that landed, were ejected or were deferred. It shows the
    CI cycles, the wall time and the approvals of each, and the release the drain asked for.
    The report goes on the Batches page and into the close-out pull request's body.

    **When the queue halts.** A push the remote refuses, or a merge the forge refuses, halts
    the queue. It then builds and lands nothing, and **Needs you now** says why. Fix the
    cause and run `fr triage batch queue-retry <owner/repo> --yes`. Without `--yes` the
    command only prints what it would do. The next pass builds again. A refusal that
    persists halts the queue anew.

    **Leaving a wave.** A batch that cannot merge need not hold its wave. `fr triage batch
    defer <id>` takes it out of the wave's queue and drain. Its pull request stays open, and
    the wave's close-out leaves it out. `fr triage batch requeue <id> --wave N` puts it in
    wave N's queue, which must not be open yet. `fr triage batch requeue <id>` alone puts it
    in the next queue to open. The driver proposes these when one batch is all that holds a
    drain, because its hand-backs are spent or it made no progress for `queue.stall_hours`.
    It never runs them itself.

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
    when they are the repo's own, green, and touch only what an archive touches. It can also
    export a finished wave's state at this point.

4. **Dispatches what may start.** It counts the batches in flight (dispatched, or with an
   open pull request) over every batch in the state file. While that count is under the cap,
   it starts the next batch by wave, then merge order, then id. It skips any batch whose
   `after` batches have not all merged. A merge that landed earlier in the same pass frees
   its slot at once.
5. **Tidies.** The driver closes a finished batch's sessions. When it sees a wave go from
   unfinished to finished while duplicate candidates exist, it prints one `dedupe` line
   naming the `fr triage check` command to judge them.

Each action prints one line, in the same words whether the driver runs once or in a loop,
and a pass ends with a one-line summary.

## Why is there a cap?

`--max-inflight` (default 4) is the most batches that may be in flight, dispatched and
unmerged, at once. It counts every batch in the scope's state, not only the ones you gave
this run of `drive`. The cap exists because every in-flight batch is a live agent session
and an open pull request somebody may have to review; a wave of fifteen would bury you.

## When does it merge, and what does it refuse?

The driver refuses to merge any of these:

- an unapproved draft;
- a pull request whose checks are pending, failing or absent (a head it has only just
  pushed is pending, not green);
- a pull request without your label;
- a pull request from a fork or a foreign author;
- a batch another scope holds.

It refuses to guess. When you push a change that alters a batch's diff, fr removes the label,
and you label it again: you approved those changes, not a branch.

The driver hands a real merge conflict back to the batch's session when that session is
idle, or to a fresh session on the batch's branch. The brief says to merge the base without
rebasing, and to regenerate generated files rather than resolve them by hand. A batch gets
two hand-backs; after that it sits in the board's **Needs you now** until you resolve it.

A repo can set `merge_method` in `.fr/triage.yaml`. Without it the driver uses the forge's
default method. Where a repo allows several and fr reaches the forge through REST only, the
driver refuses every merge until you name one.

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
- **Unblock.** A blocked batch, a conflict past its hand-backs, a failed `post_merge` and
  failing CI on a batch each show under **Needs you now** on the Backlog page. It gives one
  row per item, each linking the pull request or issue.

`fr triage batches` writes the Batches page, `batches.html`: a Kanban of every batch by stage
with four "Needs you" lanes (developer, reviewer, tester, devops). While a driver runs with
`--yes` it re-renders that page on every pass. (`fr triage board` is the old name of the
command and still works.)

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
