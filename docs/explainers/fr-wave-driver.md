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
reviewed: 2026-11-20 batch train-truth R24 the driver sorts failures into transient and refusal, keeps a failure ledger, can run under a supervisor, writes drive.log (drive status, drive log, the board's Activity panel and Driver stopped need) and hands red and conflicting drafts back early, one fetch per repo per pass; 2026-11-19 batch docs-wording changes help text and docstrings only (bracketed help renders, first lines shortened for STE, `fr ops gate` hint names the full scaffold command); still true; 2026-11-17 a batch with a member the intake rule rejects is blocked (batch triage-intake); batch release-truth, cloud-setup.md now says the doctor compares release candidates; 2026-11-19 the driver's page memory (drive-pages.json holds unfinished waves and an owed flag, no measurement) is kept across processes and carried by the state ref; the driver re-renders every page after the board and snapshots at a wave's finish (triage-pages-ux R6, R7). 2026-11-18 the pages have one name each (batches.html, fr triage batches; the Backlog holds Needs you now). 2026-11-17 a batch with a member the intake rule rejects is blocked (batch triage-intake); batch release-truth, cloud-setup.md now says the doctor compares release candidates
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
2. **Merges what is ready.** Per repo it walks a merge train in order (wave, then merge
   order, then id). It merges the head of the train, then the next ready member in the same
   pass, and so on until one does not merge. A pull request merges only when it is not a
   draft that you have not approved, its checks are green at that moment, and it carries
   **your** `approved-fr` label. The driver marks an approved draft ready first; it holds an
   unapproved one as awaiting approval, and the train goes on past it.

    The driver pins the merge to the head whose checks it judged, so it leaves a head that
    moved since for the next pass. It updates a pull request that has fallen behind its base,
    and merges it on a later pass, once CI is green again. When a pull request's checks fail,
    the driver hands it back to the batch's session if that session is idle, at most twice
    per dispatch. This holds for a draft as well as for a ready pull request, approved or not:
    a draft with red checks is never shown as awaiting approval. When the base has moved past
    fr's own update, the driver first updates the pull request again. If the session is gone,
    or after those two hand-backs, the pull request shows under **Needs you now**.
    The driver never approves, and it never waits for CI inside a pass.

3. **Closes out what merged.** Once the release commit that followed the merge has landed
   (or ten minutes have passed with none, for a pull request that releases nothing), the
   driver fast-forwards its checkout. It then runs the repo's `post_merge` argument list,
   once per merge. Next it closes the batch out. It records the batch's Test
   Plan outcomes and archives its run, together with the other landed batches of that repo,
   in one housekeeping pull request.

    A batch held by an unpassed `gate:tester` or `gate:devops` waits; see
    [exit gates](fr-exit-gates.md). The driver merges closed-out archive pull requests only
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
and a pass ends with a one-line summary. A pass fetches each repo at most once. If that
fetch fails, every later read of that repo in the pass sees the same failure, and the pass
does not try again.

## What happens when a pass fails?

A looping driver sorts every failure into one of two kinds.

- A **transient failure** is one that another pass may heal: a forge call that timed out, a
  push that lost a race, a git error. The pass ends and the driver waits. The wait starts at
  `--interval` and doubles after each failed pass in a row, up to 15 minutes (or `--interval`,
  if that is longer). The first pass that works resets it. After ten failed passes in a row,
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
supervisor ends with that code. After a signal stop, the code is 128 plus the signal number. Any other exit code, or a death by another signal such
as SIGKILL, is a crash. The supervisor waits 5 seconds before the first restart and
doubles the wait each time, up to 5 minutes. If the driver crashes a sixth time within 30
minutes, the supervisor stops as a refusal with cause `crash-loop`, and the board shows it
as above. Each crash is counted in the ledger as `crash:<signal or code>`.

The supervisor never detaches. It stays in the session that started it. When that session's
process ends, or the supervisor receives SIGHUP, SIGINT or SIGTERM, it sends SIGTERM to the
driver and SIGKILL after 10 seconds if the driver is still alive. The driver also checks
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
- a pull request whose checks are pending, failing or absent (a head it has only just
  pushed is pending, not green);
- a pull request without your label;
- a pull request from a fork or a foreign author;
- a batch another scope holds.

It refuses to guess. When you push a commit to a batch branch, fr removes the label, and you
label it again: you approved a head, not a branch.

The driver hands a real merge conflict back to the batch's session when that session is
idle, or to a fresh session on the batch's branch. It does not wait for a pull request to be
the next in the train. Each pass it tries every open batch pull request that the forge shows
as conflicting, draft or ready, approved or not. The try is a trial merge with the default
branch in a scratch checkout that the driver always removes. It uses the same rules as the
real merge, so a version file or a lock file that the driver would resolve is not a conflict.
The driver tries a given head against a given default-branch commit once for each process.
A pull request that has been handed back for its current head is not shown as awaiting
approval: its card says it is conflicting and handed back. The brief says to merge the base without
rebasing, and to regenerate generated files rather than resolve them by hand. A batch gets
two hand-backs; after that it sits in the board's **Needs you now** until you resolve it. A batch
with no session to take the conflict, because it has no dispatch and no named runner, goes there at once.

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
- **Unblock.** A stopped driver, a blocked batch, a conflict past its hand-backs, a failed
  `post_merge` and failing CI on a batch each show under **Needs you now** on the Backlog page. It gives one
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
