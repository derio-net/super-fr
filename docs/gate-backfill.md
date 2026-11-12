---
title: "fr gate backfill: bringing old owed work into the gate lanes"
tldr: |
  Work that merged before the post-merge gates existed left its asks scattered. fr gate backfill finds each one and puts it where the gate ledger and the triage board look.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/gatebackfill/**
  - packages/fr/src/fr/commands/gate_cmd.py
reviewed: 2026-11-12 acceptance-fragments phase 2, its readers now fold per-feature fragments instead of reading matrix.yaml; nothing this page describes changed
---

# `fr gate backfill` — bringing old owed work into the gate lanes

Work that merged before the post-merge gates existed (v6) left its asks scattered: a row that
still awaits a live walk, a manual phase nobody ticked, an owed Test Plan step, an issue closed
with its ask unmet. `fr gate backfill` finds them, finds the PR that delivered each, and puts them
where the gate ledger and the triage board look: a `gate:<g>` label on the merged PR and one
`fr:owed` tracker issue. It runs per repo, from that repo's checkout.

## The flow

1. **Dry run** — `fr gate backfill [--from manifest.yaml]`. It reads the forge, writes the plan
   file (default `$HOME/.cache/fr/gate-backfill/<owner--repo>/plan.yaml`, or `--plan`), prints every
   candidate on a line and the repo-file commands its decisions imply. It writes nothing to the
   forge, labels included, and nothing to the repo.
2. **Review the plan file** — one entry per owed key with its PR, gate and a `decision`. Edit the
   decisions; a re-run keeps the ones you made for keys still owed.
3. **Apply** — `fr gate backfill --yes`. It applies the plan file as reviewed.
4. **Collect and watch the board** — the triage driver's collect shows every merged PR whose
   `gate:tester` / `gate:devops` is held, in the Needs-you lanes.
5. **Pass** — when the work is done, run the `fr gate pass --pr <n> --gate <g> --notes "..."` the
   tracker body prints. If the pass does not finish every key, name each unfinished one with
   `--keep <key>`.
6. **Close** — once a tracked-only tracker's key is discharged, the next dry run lists it under
   `Trackers to close` and `--yes` closes it.

**Clearing.** `fr gate pass --yes` (and the triage driver's rows-walked pass) swaps the label and
then closes every open `fr:owed` tracker fr filed whose gate marker names that PR and gate, with the
comment "Gate <g> passed on #<pr>: <notes>". The comment then states the key's real position: the
evidence when the key is already discharged, the command still owed when it is not, and neither when
the pass ran with no checkout of the PR's repo to read it from (a checkout of another repo counts as
none). Evidence is stated only when HEAD is the default ref and the evidence trees are clean, the
condition closes below need; otherwise the comment names the command. It never closes an issue fr did not file: an adopted
issue is listed with a `gh issue close` line for you to run. For each tracker whose key is still
owed it also prints the command that discharges the key itself (the same one the backfill printed).
Without `--yes` it lists what it would close. A failure to list or close is reported and never reverses the pass; if a
PR already carries `gate:<g>-passed` and no `gate:<g>`, re-running `fr gate pass` prints "gate <g>
already passed on #<pr>; closing its trackers" and runs only the close, but only when fr passed it:
the PR must carry an `fr:gate-pass <g>` comment by the same account, else the retry refuses (exit 2).
The retry hint fr prints is a complete command (`--notes`, `--repo`, `--host`). The driver route
prints the same adopt `gh issue close` and discharge lines after its `gate-pass` line, when it has a
checkout of the repo. A PR carrying neither label still refuses.

**A partial pass: `--keep <key>`** (repeatable, gh#1323). A pass closes every tracker of its PR and
gate, and at that moment the key is normally still owed, so fr cannot tell a partial pass from a
normal one: you say so. `fr gate pass --keep <key>` converts that key's tracker to the tracked-only
form below instead of closing it, comment first, then the body, so a failure between the two leaves
it held and a retry finishes the job. On an adopted issue it posts the tracked-only adopt comment
once; that comment overrides the older adopt comment for the same gate and PR, so no `gh issue close`
line is printed, then or on any later pass. A `--keep` key that no tracker of this PR and gate holds
is refused before any write, on the first pass and on the retry alike. One already in the
tracked-only form counts as holding it, so a retry succeeds and writes nothing for that key, and the
printed retry line carries every `--keep`. `--keep` is refused with no checkout of the PR's repo, because the
tracked-only form names the key's discharge command. A kept key that already reads as discharged is
still converted, and the comment and output say the next backfill will close it unless that changes. The driver's rows-walked pass never keeps: its
rows are walked.

The repo-file commands the dry run prints (`fr plan edit --tick`, `fr closeout outcome`,
`fr acceptance set-status`) are for your own chore PR; backfill never writes a repo file.

## Decisions

| Decision | `--yes` does |
|---|---|
| `owed` (default) | adds `gate:<g>` to the delivering PR, files or reuses the tracker, links a closed issue to it |
| `adopt <owner/repo#n>` | adds `gate:<g>`, then comments on and labels your issue `n` instead of filing one |
| `tick`, `na` | nothing on the forge; the dry run prints the repo-file commands |
| `park` | nothing; listed under its own heading |
| `review` | nothing; a candidate fr could not settle (planning PR, several PRs, no gate, stale) |

An entry is applied with the PR and gate recorded in the plan file. It is skipped, with a line
naming why, when either re-resolves differently now, when its key is no longer owed, or when its
adopt target is in another repo, missing, closed or an fr-owned tracker. A new candidate absent
from the plan is reported and waits for a dry run. A missing plan file, or one naming another
repo, refuses before any write (exit 2).

**Settling a PR fr could not** (gh#1369). Several merged PRs (an ambiguity) or a planning PR leave
an entry in `review`. Pick the delivering one in a manifest **override**: an item for the key fr
already holds, with no `kind:` or `title:`, setting only `pr:` (and, if you need to, `gate:` or
`walk_only:`):

```yaml
schema: 1
items:
  - {key: "plan:2026-10-20-ops#p1", pr: 22}
```

Pass it to the dry run and to `--yes` alike (`--from m.yaml`): the PR is then found with basis
`manifest`, the entry defaults to `owed`, and `--yes` labels that PR and files the tracker. Setting
`pr:` in the plan file instead does not work, because `--yes` re-resolves every PR and skips an
entry whose PR moved; the skip line says so. A `kind:` item for a key fr already holds is still
refused, and an override for a key fr does not hold is refused as a new item missing its `kind:`.

## Markers

A tracker body ends with two lines, in this order:

```
<!-- fr-gate:devops pr:41 -->
<!-- fr-owed:plan:2026-04-02-fleet#p3 -->
```

Comments carry `<!-- fr-gate-adopt:<key> gate:<g> pr:<n> -->` (on an adopted issue),
`<!-- fr-gate-adopt-discharged:<key> pr:<n> -->` (the evidence comment on an adopted issue whose key
is discharged) and `<!-- fr-gate-link:<key> tracker:<ref> -->` (on a closed issue pointing at its
tracker). They are how a second `--yes` knows what is already done: it makes no forge write. Only
this account's comments count.

## Trust

fr reuses, rewrites and closes only trackers `owned_owed_key` accepts: written by the account fr
acts as, labelled `fr:owed`, last line an owed marker. Any other issue is touched only through an
explicit `adopt`, by its comments and labels (`fr:owed`, plus `fr:awaiting-live` when only a walk
remains); its body is never edited and it is never closed. Adopting while fr-owned trackers hold
the key closes every one of them as a duplicate. A bare `owed` on an `issue:` key that is itself an
open issue is refused at the dry run (it would file nothing and leave no marker): adopt it, or give
the manifest entry an `issue:`. An entry whose fr-owned tracker names another gate or PR than the
plan's is skipped, and the line says why: fix the plan entry's gate or close the tracker, then
re-run.

**A gate that already passed is never put back** (gh#1322). When the delivering PR already carries
`gate:<g>-passed`, the dry run says so on the entry's line ("gate:<g> already passed on PR #n:
tracked only, never re-gated") and records `gate_passed: true` in the plan file. The decision stays
`owed`, because the item really is still owed. `--yes` re-reads the PR's labels itself, so a stale
plan file cannot re-gate it. It never adds `gate:<g>` to that PR, because doing so would re-hold the
release and reverse the pass. (While a gate does hold the release, a run cuts a release candidate only
when something installable changed since the newest RC tag or, with no RC, the last final; a
housekeeping merge prints `nothing installable changed since <tag>: no release`. So landing this
page's repo-file commands cuts no RC.) It still files, reuses or adopts the item's tracker, in a "tracked
only" form. Its body ends with `<!-- fr-gate-passed:<g> pr:<n> -->` instead of the gate marker (an
adopt comment ends with `fr-gate-adopt-passed:`), and it shows the command that discharges the owed
key itself, never `fr gate pass`: `set-status --walk` for a row, `closeout outcome --ran` for a spec
step, the `--tick` lines for a plan phase, `journal resolve` for a journal entry, "close it by hand"
for an issue. Because it carries no gate marker, re-running `fr gate pass` on that PR never closes
it; the backfill does, once its key is discharged (below). Trackers filed before that existed keep
their older text, "Then close this issue.", and are closed the same way. Only the entry's own gate
counts: a PR that
passed `gate:devops` still gets `gate:tester` for an item owed under tester. A mismatch skip names
such a tracker in its passed form (`gate:<g>-passed pr:<n> (tracked only)`). An open fr tracker
filed before the gate passed is rewritten into this form, and back into the held form if the
`-passed` label is later removed. A re-run writes
nothing.

**Closing a discharged tracker** (gh#1328). The dry run reads the open issues, because a key resolved
in its journal has already left `fr debt`'s fold, and lists under `Trackers to close` each tracked-only
tracker fr owns whose key is discharged. It records them in the plan file's `closes:` list with their
issue and evidence. A discharged key leaves the plan's entries, so it is never both owed and closing,
and a decision you recorded on it is dropped with a note. A key counts as discharged only on positive
evidence, with no source but its own tracker holding it:

| Key | Evidence |
|---|---|
| `row:` | the row exists, with a status outside the debt statuses |
| `plan:` | the phase exists, with at least one step, and every step is ticked or n/a |
| `spec:` | the step's effective outcome is a recorded `discovery` (what `--ran` and `--na` write) |
| any but `issue:` | its journal `owed` entry was resolved fixed, unless a `row:` is in a debt status, which the journal never overrides |

An `issue:` key, a manifest-only key (one with no row, phase or outcome behind it) and anything
unreadable (one unreadable journal or matrix is enough) are never discharged. With `--from`, a dry run
and `--yes` both honour the manifest's claim on a key it names as a new item: that key does not close,
and a close the plan had recorded for it is dropped with a note. Without `--from`, nothing marks a key
as a manifest's, so one naming a real row, phase or step closes on that evidence, which the dry run
shows; if the registry wrongly says done, correct the registry (`set-status walk-owed`, which the fold
then holds). An open `owed` journal entry still holds its key: a step
recorded `--ran --supersede` over an open owed entry stays owed until that entry is resolved.

`--yes` re-checks each close against the forge and the checkout, and the plan file only names what to
look at. A key that became discharged after the dry run waits for the next dry run, and one no longer
discharged is skipped. Closes happen only when HEAD equals the default ref as last fetched and
`docs/acceptance/` and `docs/superpowers/` are clean, because the evidence is read from the working
tree; otherwise, or when no default ref resolves, a note says so and nothing closes. Under `tracking:
none` nothing closes. A second `--yes` writes nothing.

An adopted issue is still never closed by fr. When it carries this account's `fr-gate-adopt-passed:`
comment (an issue this account wrote by hand counts as adopted too) and its key is discharged, `--yes` posts one comment naming the evidence and prints a
`gh issue close` line for you to run; a re-run prints the line again and writes nothing.

Older `fr` versions refuse a plan file carrying `closes:`, on the dry run as well as on `--yes`. It is
a host-side cache: delete it and dry-run again.

Labels (`gate:<g>`, `fr:owed`, `fr:awaiting-live`) are created only right before the first write
that uses them. Forge errors, including a forge that cannot do an operation, are recorded on their
entry and the rest go on; the exit code is 1 when any entry failed.

## Tracking `none` and the repo's forge settings

Under `tracking: {type: none}` in `.devcontainer/fr-profiles.yaml` `--yes` writes only the PR gate
labels: no tracker, no comment, no `fr:awaiting-live`. The plan file and summary still list every
owed item. An unreadable services declaration refuses before any write.

The repo's `forge` settings (`fr settings show`) narrow the same writes. The labels are the gate
ledger, so only `forge.labels` decides them:

- **`forge.labels: off`**: there is no ledger to write. `fr gate backfill --yes` and `fr gate pass`
  both refuse (exit 2) before writing anything.
- **`forge.issues: off`**: acts as `tracking: none` does for trackers. None are filed, adopted or
  closed, and the PR labels are still written.
- **`forge.comments: off`**: stops every tracker close as well, because a close carries a comment.
  An adopted issue is labelled without the comment, a duplicate is left open, and a closed issue is
  not linked; each of these shows up as a note. `fr gate pass` swaps the label without leaving its
  `fr:gate-pass` comment, so the retry no longer asks for one.

`fr gate pass` reads these settings from the current checkout when its `origin` is the PR's repo,
and otherwise from that repo's `.fr/settings.yaml` on its default branch. A read that fails
refuses rather than falling back to the defaults.
