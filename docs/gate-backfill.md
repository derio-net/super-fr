---
title: "fr gate backfill: bring old owed work into the gate lanes"
tldr: |
  Work that merged before the post-merge gates existed left its asks scattered. fr gate backfill finds each one and puts it where the gate ledger and the triage board look.
standalone_style: broadsheet
covers:
  - packages/fr/src/fr/gatebackfill/**
  - packages/fr/src/fr/commands/gate_cmd.py
reviewed: 2026-11-12 placement-resolver phase 2, artifact directories now come from fr.artifacts.paths; the paths and behaviour this page describes are unchanged
---

# `fr gate backfill` — bring old owed work into the gate lanes

Work that merged before the post-merge gates existed (v6) left its asks scattered. Here are
some examples: a row that still waits for a live walk, and a manual phase that nobody ticked.
Others are an owed Test Plan step, and an issue closed with its ask unmet. `fr gate backfill` finds them, and finds the
PR that delivered each one. It puts them where the gate ledger and the triage board look: a
`gate:<g>` label on the merged PR and one `fr:owed` tracker issue. It runs per repo, from that
repo's checkout.

## The flow

1. **Dry run** — `fr gate backfill [--from manifest.yaml]`. It reads the forge and writes the plan
   file (default `$HOME/.cache/fr/gate-backfill/<owner--repo>/plan.yaml`, or `--plan`).
   It prints every candidate on a line, and the repo-file commands that its decisions imply.
   It writes nothing to the forge, labels included, and nothing to the repo.
2. **Review the plan file** — one entry per owed key with its PR, gate and a `decision`.
   Edit the decisions. A re-run keeps the ones that you made for keys still owed.
3. **Apply** — `fr gate backfill --yes`. It applies the plan file as reviewed.
4. **Collect and watch the board** — the Needs-you lanes show each merged PR with a held
   `gate:tester` / `gate:devops`. The triage driver's collect puts them there.
5. **Pass** — when the work is done, run the `fr gate pass --pr <n> --gate <g> --notes "..."`
   that the tracker body prints. For `devops` it also has `--run <id>` or `--no-run-evidence`.
   The command shows a preview; add `--yes` to pass.
   If the pass does not finish every key, name each unfinished key with `--keep <key>`.
6. **Close** — after you discharge a tracked-only tracker's key, the next dry run lists it
   under `Trackers to close`, and `--yes` closes it.

**Clear the gate.** `fr gate pass --yes` swaps the label, and so does the rows-walked pass of the
triage driver. Then it closes every open `fr:owed` tracker that fr filed and whose gate marker
names that PR and gate. It closes each one with the comment "Gate <g> passed on #<pr>: <notes>".

The comment then states the key's real position:

- the evidence, when the key is already discharged;
- the command still owed, when it is not;
- neither, when the pass ran with no checkout of the PR's repo to read it from. A checkout of
  another repo counts as none.

The comment states evidence only when HEAD is the default ref and the evidence trees are clean.
The closes below need the same condition. Otherwise the comment names the command.

It never closes an issue that fr did not file. It lists an adopted issue with a
`gh issue close` line for you to run. For each tracker whose key is still owed, it also prints the command
that discharges the key itself (the same one that the backfill printed). Without `--yes` it lists
what it would close.

A failure to list or close is reported, and it never reverses the pass. A PR can already carry
`gate:<g>-passed` and no `gate:<g>`. Then a re-run of `fr gate pass` prints "gate <g>
already passed on #<pr>; closing its trackers" and does only the close. But it does this only when
fr passed the gate. The PR must carry an `fr:gate-pass <g>` comment by the same account. If not,
the retry does not accept the pass (exit 2).

The retry hint that fr prints is a complete command (`--notes`, `--repo`, `--host`). The driver
route prints the same adopt `gh issue close` and discharge lines after its `gate-pass` line, when
it has a checkout of the repo. A PR that carries neither label still does not pass.

**A partial pass: `--keep <key>`** (repeatable, gh#1323). A pass closes every tracker of its PR and
gate, and at that time the key is usually still owed. So fr cannot tell a partial pass from a
normal one: you tell it. `fr gate pass --keep <key>` converts that key's tracker to the tracked-only
form below, and does not close it. It writes the comment first, then the body. So a failure
between the two leaves the tracker held, and a retry finishes the job.

On an adopted issue, the pass posts the tracked-only adopt comment once. That comment overrides
the older adopt comment for the same gate and PR. So fr prints no `gh issue close` line, then or on
any later pass.

A `--keep` key that no tracker of this PR and gate holds is not accepted. The pass stops before any
write, on the first pass and on the retry alike. A tracker already in the tracked-only form counts
as one that holds the key. So a retry succeeds and writes nothing for that key, and the printed
retry line has every `--keep`.

A pass with no checkout of the PR's repo does not accept `--keep`, because the tracked-only form names
the key's discharge command. A kept key that already shows as discharged is still converted. The
comment and output then say that the next backfill will close it, unless that changes. The
driver's rows-walked pass never keeps keys, because its rows are walked.

The repo-file commands that the dry run prints (`fr plan edit --tick`, `fr closeout outcome`,
`fr acceptance set-status`) are for your own chore PR. Backfill never writes a repo file.

## Decisions

| Decision | `--yes` does |
|---|---|
| `owed` (default) | adds `gate:<g>` to the delivering PR, files or reuses the tracker, links a closed issue to it |
| `adopt <owner/repo#n>` | adds `gate:<g>`, then comments on and labels your issue `n` instead of a new one |
| `tick`, `na` | nothing on the forge; the dry run prints the repo-file commands |
| `park` | nothing; listed under its own heading |
| `review` | nothing; a candidate that fr could not settle (planning PR, several PRs, no gate, stale) |

The apply uses the PR and gate recorded in the plan file for an entry. It skips the entry, with a
line that says why, in these cases:

- the PR or the gate resolves differently now;
- the entry's key is no longer owed;
- its adopt target is in another repo, is not there, is closed or is an fr-owned tracker.

A new candidate that is not in the plan is reported, and it waits for a dry run. A plan
file that is not there, or one that names another repo, stops the command before any write (exit 2).

**Settle a PR that fr could not settle** (gh#1369). Several merged PRs (an ambiguity) or a planning
PR leave an entry in `review`. Pick the PR that delivered the work in a manifest **override**. The override is
an item for the key that fr already holds, with no `kind:` or `title:`. It sets only `pr:` (and,
if you need to, `gate:` or `walk_only:`):

```yaml
schema: 1
items:
  - {key: "plan:2026-10-20-ops#p1", pr: 22}
```

Give it to the dry run and to `--yes` alike (`--from m.yaml`). Then the PR is found with basis
`manifest`, and the entry defaults to `owed`. Then `--yes` labels that PR and files the tracker.
It does not work to set `pr:` in the plan file instead. `--yes` resolves every PR again and skips
an entry whose PR moved. The skip line says so.

A `kind:` item for a key that fr already holds is still not accepted. An override for a key that
fr does not hold is not accepted either. It is read as a new item without its `kind:`.

## Markers

A tracker body ends with two lines, in this order:

```
<!-- fr-gate:devops pr:41 -->
<!-- fr-owed:plan:2026-04-02-fleet#p3 -->
```

Comments carry these markers:

- `<!-- fr-gate-adopt:<key> gate:<g> pr:<n> -->`, on an adopted issue;
- `<!-- fr-gate-adopt-discharged:<key> pr:<n> -->`, the evidence comment on an adopted issue whose
  key is discharged;
- `<!-- fr-gate-link:<key> tracker:<ref> -->`, on a closed issue that points at its tracker.

A second `--yes` uses them to know what is already done, so it makes no forge write. Only the
comments of this account count.

## Trust

The backfill reuses, rewrites and closes only trackers that `owned_owed_key` accepts. The account
that fr acts as wrote such a tracker. It is labelled `fr:owed`, and its last line is an owed marker.

The backfill touches any other issue only through an explicit `adopt`. Even then it touches only
the comments and labels (`fr:owed`, plus `fr:awaiting-live` when only a walk remains). It never
edits the body of that issue and never closes it. An adopt while fr-owned trackers hold the key
closes every one of them as a duplicate.

The dry run does not accept a bare `owed` on an `issue:` key that is itself an open issue. It
would file nothing and leave no marker. Adopt the issue, or give the manifest entry an `issue:`.
The backfill skips an entry whose fr-owned tracker names a gate or PR other than the plan's. The
line says why. Fix the gate of the plan entry or close the tracker, then run again.

**A gate that already passed is never put back** (gh#1322). The PR that delivered the work can already carry
`gate:<g>-passed`. Then the dry run says so on the entry's line ("gate:<g> already passed on PR #n:
tracked only, never re-gated"). It also records `gate_passed: true` in the plan file. The decision stays
`owed`, because the item really is still owed.

`--yes` reads the PR's labels again itself, so a
stale plan file cannot gate the PR again. It never adds `gate:<g>` to that PR, because that would
hold the release again and reverse the pass.

(While a gate does hold the release, a run cuts a release candidate only when something
installable changed since the newest RC tag. With no RC, it compares with the last final. A
merge of only chores prints `nothing installable changed since <tag>: no release`. So a merge of this
page's repo-file commands cuts no RC.)

The backfill still files, reuses or adopts the item's tracker, in a "tracked only" form. Its body ends with
`<!-- fr-gate-passed:<g> pr:<n> -->` in place of the gate marker (an adopt comment ends with
`fr-gate-adopt-passed:`). It shows the command that discharges the owed key itself, never
`fr gate pass`:

- `set-status --walk` for a row;
- `closeout outcome --ran` for a spec step;
- the `--tick` lines for a plan phase;
- `journal resolve` for a journal entry;
- "close it by hand" for an issue.

Because it has no gate marker, a re-run of `fr gate pass` on that PR never closes it. The
backfill closes it when its key is discharged (below). Trackers filed before this form existed keep
their older text, "Then close this issue.", and fr closes them the same way.

Only the entry's own gate counts. A PR that passed `gate:devops` still gets `gate:tester` for an
item owed under tester. A mismatch skip names such a tracker in its passed form
(`gate:<g>-passed pr:<n> (tracked only)`). An open fr tracker that was filed before the gate passed
is rewritten into this form. It is rewritten back into the held form if someone later removes the `-passed` label.
A re-run writes nothing.

**Close a discharged tracker** (gh#1328). The dry run reads the open issues, because a key resolved
in its journal has already left the fold of `fr debt`. Under `Trackers to close` it lists each
tracked-only tracker that fr owns and whose key is discharged. It records them in the `closes:`
list of the plan file, with their issue and evidence. A discharged key leaves the plan's entries,
so it is never both owed and to be closed. A decision that you recorded on it is dropped, with a
note.

A key counts as discharged only on positive evidence, when no source but its own tracker holds it:

| Key | Evidence |
|---|---|
| `row:` | the row exists, with a status outside the debt statuses |
| `plan:` | the phase exists, with at least one step, and every step is ticked or n/a |
| `spec:` | the step's effective outcome is a recorded `discovery` (what `--ran` and `--na` write) |
| any but `issue:` | its journal `owed` entry was resolved fixed, unless a `row:` is in a debt status, which the journal never overrides |

These are never discharged:

- an `issue:` key;
- a manifest-only key (one with no row, phase or outcome behind it);
- anything unreadable (one unreadable journal or matrix is enough).

Sometimes the manifest names a key as a new item. With `--from`, a dry run and `--yes` both honour
that claim: the key does not close. A close that the plan had recorded for the key is dropped.
`--yes` prints a note for it. A dry run drops it from the rewritten plan file without a note.

Without `--from`, nothing marks a key as a manifest's. So a key that names a real row, phase or step
closes on that evidence, and the dry run shows this. If the registry says done by mistake, correct
the registry (`set-status walk-owed`, which the fold then holds). An open `owed` journal entry
still holds its key. A step recorded `--ran --supersede` over an open owed entry stays owed until
someone resolves that entry.

`--yes` checks each close again against the forge and the checkout. The plan file only names what
to look at. A key that became discharged after the dry run waits for the next dry run. A key that is no longer
discharged is skipped.

Closes happen only when HEAD equals the default ref as last fetched, and `docs/acceptance/` and
`docs/superpowers/` are clean. The reason is that the evidence comes from the working tree.
Otherwise, or when no default ref resolves, a note says so and nothing closes. Under `tracking:
none` nothing closes. A second `--yes` writes nothing.

An adopted issue is still never closed by fr. It can carry this account's `fr-gate-adopt-passed:`
comment (an issue that this account wrote by hand counts as adopted too), with its key
discharged. Then `--yes` posts one comment that names the evidence, and prints a `gh issue close`
line for you to run. A re-run prints the line again and writes nothing.

Older `fr` versions do not accept a plan file that has `closes:`, on the dry run and on `--yes`.
The plan file is a host-side cache: delete it and do a dry run again.

The labels (`gate:<g>`, `fr:owed`, `fr:awaiting-live`) are made only right before the first write
that uses them. A forge error is recorded on its entry, and the other entries go on. This includes
a forge that cannot do an operation. The exit code is 1 when any entry failed.

## Tracking `none` and the repo's forge settings

Under `tracking: {type: none}` in `.devcontainer/fr-profiles.yaml`, `--yes` writes only the PR gate
labels: no tracker, no comment, no `fr:awaiting-live`. The plan file and summary still list every
owed item. An unreadable services declaration stops the command before any write.

The repo's `forge` settings (`fr settings show`) narrow the same writes. The labels are the gate
ledger, so only `forge.labels` decides them:

- **`forge.labels: off`**: there is no ledger to write. `fr gate backfill --yes` and `fr gate pass`
  both stop (exit 2) before they write anything.
- **`forge.issues: off`**: acts as `tracking: none` does for trackers. No tracker is filed, adopted
  or closed, and the PR labels are still written.
- **`forge.comments: off`**: stops every tracker close as well, because a close has a comment.
  An adopted issue gets its labels without the comment. A duplicate stays open, and a closed issue
  is not linked. Each of these shows up as a note. `fr gate pass` swaps the label without its
  `fr:gate-pass` comment, so the retry no longer asks for one.

`fr gate pass` reads these settings from the current checkout when its `origin` is the PR's repo.
Otherwise it reads them from that repo's `.fr/settings.yaml` on its default branch. A read that
fails stops the command; it does not fall back to the defaults.
