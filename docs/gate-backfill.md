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
   tracker body prints.

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

## Markers

A tracker body ends with two lines, in this order:

```
<!-- fr-gate:devops pr:41 -->
<!-- fr-owed:plan:2026-04-02-fleet#p3 -->
```

Comments carry `<!-- fr-gate-adopt:<key> gate:<g> pr:<n> -->` (on an adopted issue) and
`<!-- fr-gate-link:<key> tracker:<ref> -->` (on a closed issue pointing at its tracker). They are
how a second `--yes` knows what is already done: it makes no forge write.

## Trust

fr reuses, rewrites and closes only trackers `owned_owed_key` accepts: written by the account fr
acts as, labelled `fr:owed`, last line an owed marker. Any other issue is touched only through an
explicit `adopt`, by one comment and labels (`fr:owed`, plus `fr:awaiting-live` when only a walk
remains); its body is never edited and it is never closed. Adopting while an fr-owned tracker holds
the key closes that one as a duplicate. A PR already carrying `gate:<g>-passed` gets no write and
no tracker; the run prints the command that discharges the stale debt.

Labels (`gate:<g>`, `fr:owed`, `fr:awaiting-live`) are created only right before the first write
that uses them. Forge errors, including a forge that cannot do an operation, are recorded on their
entry and the rest go on; the exit code is 1 when any entry failed.

## Tracking `none`

Under `tracking: {type: none}` in `.devcontainer/fr-profiles.yaml` `--yes` writes only the PR gate
labels: no tracker, no comment, no `fr:awaiting-live`. The plan file and summary still list every
owed item. An unreadable services declaration refuses before any write.
