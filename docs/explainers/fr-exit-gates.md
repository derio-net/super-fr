---
title: "Exit gates: Merged Is Not the Same as Done"
date: 2026-11-12
draft: false
tldr: |
  Some changes cannot be proved before they merge. fr gives each run an exit: the gates that
  say who must act on it afterwards. A gate is a label on the merged pull request, passed by
  a person, and while one is held, releases stay release candidates.
standalone: true
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/verification/exit.py
  - packages/fr/src/fr/gates.py
  - packages/fr/src/fr/commands/gate_cmd.py
  - scripts/release.py
  - docs/verification-strategies.md
  - docs/exit-gates-release-walk.md
  - docs/gate-backfill.md
reviewed: 2026-11-14 quiet/stealth plans, deliver and close-out read artifacts where they live (debug 2026-11-13-placement-plan-paths)
---

## Overview: the work that cannot finish in the pull request

A reviewed, green pull request proves what CI and a reviewer can see. It cannot prove that
the new release installs on a clean machine, that a feature works against the real service,
or that the secret the change needs has been rotated. Those can only be checked **after**
the merge, by someone who is not the agent that wrote it.

fr makes that owed work visible instead of leaving it in a PR description. Every run has an
**exit**: the kinds of verification that apply to it, and the **gates** that name who must
act. While a gate is held, the merged pull request says so in its labels, the triage board
lists it, the run is not closed out, and the project does not publish a final release.

<!-- site:figure gate-ledger -->

## The six gates

A gate names a role. There are six: `developer`, `reviewer`, `tester`, `devops`, `owner` and
`security`. Only two of them hold anything after the merge:

| Gate | What it holds |
|---|---|
| `tester` | the merge's close-out, and the final release |
| `devops` | the same, and the merge itself when it goes through the triage merge path |
| the other four | nothing: they are recorded, never enforced |

`devops` is the stricter of the two because the work it guards, a key that must exist or a
service to restart, often has to be done before or around the merge, not only after it. The
triage merge path refuses a pull request that holds `gate:devops` without
`gate:devops-passed`. A merge made by hand in the forge's own UI is not blocked, which is why
the label is the ledger and not a lock.

## Which gate a run gets

You do not choose a gate at the end. It is decided from the spec, first match wins:

1. a `gate: <gate>` line in the spec's `## Verification` section sets the run's gate, and
   `gate: <row-id>=<gate>` sets one acceptance row's;
2. the repo's remap for the verification kind, `exit: {gates: {<kind>: <gate>}}` in
   `.fr/triage.yaml`;
3. the `gate:` in the verification strategy's own manifest (the shipped `live` strategy
   says `tester`; see [verification strategies](../verification-strategies.md));
4. `none`.

On top of that, a run whose plan carries manual operations gets `devops` added, whatever the
spec says. `fr verification exit --run <id>` prints the kinds and gates the rules give. A repo can switch the whole
thing off with `artifacts.gates: off`; then no gate is computed, labelled or held.

## The labels are the ledger

When the run is delivered, fr puts a `verification:<kind>` label and a `gate:<gate>` label
for each post-merge gate on the pull request. A gate is **held** while the pull request has
`gate:<g>` and no `gate:<g>-passed`. The passed label is the record of a pass and is never
removed. Nothing about a gate lives in a file in the repo, so passing one needs no commit.

## How a gate is passed

A person passes a gate, or the work that the gate guards is recorded as done.

- **Tester.** When the gate has acceptance rows and every one of them reads `walked` on the
  default branch, the triage driver passes the gate itself. It never does for a run-level gate
  that no row inherits, nor for a `devops` gate added because the plan has operations: those
  are passed explicitly. Otherwise you walk the rows
  ([fr-acceptance](fr-acceptance.md)) or record the pass by hand:

  ```bash
  fr gate pass --pr 123 --gate tester --notes "walked the install on a clean machine" --yes
  ```

- **DevOps.** The stage that does the operations, runs the probes and then passes the gate is
  its own command; [the DevOps gate](fr-devops-gate.md) covers it. `fr gate pass --gate devops`
  refuses while any recorded operation or devops test step is still open.

`fr gate pass` comments what passed the gate on the pull request and swaps `gate:<g>` for
`gate:<g>-passed`. Without `--yes` it prints what it would do. It also closes the `fr:owed`
tracker issues fr filed for that pull request and gate. When it was the pull request's last
gate it prints the command that cuts the final release.

## Release candidates while a gate waits

This is where the gates meet the release. On every push to `main`, and once a day because a
gate can pass with no push, the release script looks at every pull request merged since the
last **final** tag. If any still holds a post-merge gate:

- it cuts a **release candidate**, `vX.Y.Z-rc.N`, published as a pre-release. It consumes no
  change fragments, so the version the final will have is not spent;
- or it cuts nothing, when nothing installable changed since the newest candidate (or since
  the last final). Documentation, tests and a fragment on its own are not installable.

Once no pull request waits, the next run cuts the **final** release and consumes the
fragments. People who install candidates test what merged while the gates are open; people
who install finals only ever get what every gate passed.

Release candidates are the safe direction when fr is unsure. If the labels cannot be read, the
read of merged pull requests comes back at its limit, a pull request the git log names is missing
from it, or the decision itself fails, the state is **unknown**, and unknown cuts a
candidate, never a final and never an error. A token that cannot read labels therefore means
candidates only, until it is fixed. An explicit `--version` releases a final without asking the
ledger: it is the operator's override, not a way around a hold.

`fr release status` lists what is waiting.

## Old work, and the DevOps stage

Work that merged before gates existed has its asks scattered in rows, manual phases and
closed issues. `fr gate backfill` finds them and puts each where the ledger and the board look;
[its guide](../gate-backfill.md) has the flow. The DevOps stage, with its eight steps and the
trust model for probes, is on [its own page](fr-devops-gate.md).
