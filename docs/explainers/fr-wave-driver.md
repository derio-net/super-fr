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
reviewed: 2026-11-13 writing-standards-docs phase 3, docs/cloud-setup.md was corrected and rewritten to ste; nothing this page describes changed
---

## Overview: why a loop and not a checklist

[fr-triage](fr-triage.md) ranks a backlog and groups related issues into **batches**. A batch
is delivered the way any goal is, by one [fr-goal](01-fr-goal.md) run that ends in one pull
request (a batch of defects runs fr-debugging instead). Twenty issues become five or six
runs, and then the work that is left is bookkeeping: start the runs in the right order, keep
only a few going at once, merge each pull request when it is ready, run the repo's install
step so your tools match what merged, archive each finished run.

That bookkeeping is mechanical and easy to get wrong when done by hand late in the evening.
`fr triage batch drive` is the loop that does it. It does not judge anything and it never
approves a pull request. Every decision that needs a person stays with you; the driver does
the rest, in the same order, every time.

<!-- site:figure wave-of-batches -->

## Batches, waves and `after`

A batch carries two optional fields:

- **`wave`**, a number. Batches of the same wave may run at the same time. Lower waves go first.
- **`after`**, a list of batch ids that must be **merged** before this one may start. A batch
  that is only dispatched, or only has an open pull request, does not meet an `after`.

You set them with `fr triage batch create` and `fr triage batch edit` (`--wave N`,
`--after ID`, the second repeatable). A batch id that does not exist, a batch that names
itself and a cycle are refused, and the file is left as it was. If a batch's dependency is
cancelled, abandoned or ends `partial`, the batch is reported as **blocked** and is never
dispatched; that one needs you.

Use waves for "these are independent, start them together" and `after` for "this one edits
what that one adds". A batch with no wave is allowed. With no batch ids on the command line,
`drive` takes the batches that have a wave, and every batch when none has.

## What one pass does

The driver runs in passes. Each pass starts by re-reading the forge, so it works from what
is true now, not from what it remembers. In order, a pass:

1. **Reports what it will not touch.** A batch holding an issue that another scope has
   claimed is left alone. So is a pull request on a batch branch that is not that batch's,
   or by an author the repo has not allowed (`pr_authors` in `.fr/triage.yaml`, by default
   you). They are named once, never merged.
2. **Merges what is ready.** Per repo it walks a merge train in order (wave, then merge
   order, then id) and merges the head of it. A pull request merges only when it is not a
   draft that you have not approved, its checks are green at that moment, and it carries
   **your** `approved-fr` label. An approved draft is marked ready first; an unapproved one is
   held as awaiting approval, and the train goes on past it. The merge is pinned to the head whose checks were judged, so a head that moved since is
   left for the next pass. A pull request that has fallen behind its base is updated and
   merged on a later pass, once CI is green again. A failing check is reported once per
   head. The driver never approves, and it never waits for CI inside a pass.
3. **Closes out what merged.** Once the release commit that followed the merge has landed
   (or ten minutes have passed with none, for a pull request that releases nothing), the
   driver fast-forwards its checkout and runs the repo's `post_merge` argument list, once
   per merge. Then the batch is closed out: its Test Plan outcomes are recorded and its
   run is archived, together with the other landed batches of that repo, in one housekeeping
   pull request. A batch held by an unpassed `gate:tester` or `gate:devops` waits; see
   [exit gates](fr-exit-gates.md). Closed-out archive pull requests are merged by the driver
   only when they are the repo's own, green, and touch only what an archive touches.
4. **Dispatches what may start.** It counts the batches that are dispatched or have an open
   pull request, over every batch in the state file, and while that count is under the cap
   it starts the next batch by wave, then merge order, then id, skipping any whose `after`
   batches are not all merged. A merge that landed earlier in the same pass frees its slot
   at once.
5. **Tidies.** A finished batch's sessions are closed, a finished wave's state can be
   exported, and when a wave finishes while duplicate candidates exist, the driver prints
   one `dedupe` line naming the `fr triage check` command to judge them.

Each action prints one line, in the same words whether the driver runs once or in a loop,
and a pass ends with a one-line summary.

## The cap

`--max-inflight` (default 4) is the most batches that may be dispatched and unmerged at
once. It counts every batch in the scope's state, not only the ones this run of `drive` was
given. The cap exists because every in-flight batch is a live agent session and an open
pull request somebody may have to review; a wave of fifteen would bury you.

## When it merges, and what it refuses

The driver refuses to merge an unapproved draft, a pull request whose checks are pending, failing or
absent (a head it has only just pushed is pending, not green), a pull request without your
label, a pull request from a fork or a foreign author, and a batch another scope holds. It
refuses to guess. When you push a commit to a batch branch, the label is removed, and you
label it again: you approved a head, not a branch.

A real merge conflict is handed back to the batch's session when that session is idle, or to
a fresh session on the batch's branch, with a brief that says to merge the base without
rebasing and to regenerate generated files rather than resolve them by hand. A batch gets
two hand-backs; after that it sits in the board's **Needs you now** until you resolve it.

A repo can set `merge_method` in `.fr/triage.yaml`. Without it the driver uses the forge's
default method, and where a repo allows several and the forge is reached through REST only,
it refuses every merge until one is named.

## No state, so it resumes

The driver keeps nothing of its own. What was dispatched, merged and closed out is read from
events recorded in the scope's `judgements.yaml` and from the forge. Kill it between any two
actions and run it again: it repeats nothing the files can show. The one thing that can run
twice is `post_merge`, which is at-least-once; a command that is safe to repeat is a good
`post_merge`.

In loop mode it waits `--interval` seconds (the flag's default applies when you give none) between passes, and reads the forge again at the start of each. A lock file in the scope's state directory refuses a second driver, so there is one driver per
scope. `--yes` is what makes it act: without it `drive` prints the plan one pass would follow
and exits, loop mode included. `--once` makes a single pass and exits 0 when it acted or
everything is done, 3 when it did nothing and work remains (a draft, CI, a dependency, a
blocked batch), and 2 when it refused. A forge write that fails exits 1. `--once --yes` on the
host refuses, with exit 2 and the looping command, when its pass would dispatch a batch, because
one pass leaves the rest of the wave undone; `--single-pass` says the one pass is deliberate.

## Where you act

The driver is built around the few moments that are yours:

- **Approve.** Label a green batch pull request `approved-fr`.
- **Pass a gate.** A merged pull request holding `gate:tester` or `gate:devops` waits for you
  to walk it or pass it ([exit gates](fr-exit-gates.md)).
- **Unblock.** A blocked batch, a conflict past its hand-backs, a failed `post_merge` and
  failing CI on a batch each show under **Needs you now** on the board, one row per item,
  each linking the pull request or issue.

`fr triage board` writes that board, a Kanban of every batch by stage with four "Needs you"
lanes (developer, reviewer, tester, devops). While a driver runs with `--yes` it re-renders on
every pass.

## Where it runs

On your machine the driver starts each batch's session through the `herdr` runner, so it
runs from inside a herdr pane. It can also run as a long-lived Claude Code cloud session that
runs `fr triage drive pass` on each wake; that driver runs no `post_merge`, because every
session it starts installs the current release first. The prerequisites for that mode are in
the [cloud guide](../cloud-setup.md).
