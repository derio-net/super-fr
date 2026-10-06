# PR #980: post-merge Test Plan, driven live (2026-10-06)

The three Test Plan items of the batch board
(`implemented/specs/2026-10-05-triage-batch-board-design.md`, "Test Plan (post-merge,
operator-driven)") were run against the **installed** `fr` built from `main` at #980, inside herdr.
The target was a real `fr triage batch drive --yes --repo derio-net/super-fr` over this repo's
101 batches.

**Redaction, stated rather than hidden** (`.claude/rules/third-party-privacy.md`): the home
directory is `~`. Every repo, batch and PR named here is in `derio-net`. Outputs are excerpts;
`[…]` marks a cut.

| item | result |
|---|---|
| 1 — cards sit in the right columns | PASS: 101/101 against an independent oracle |
| 1 — cards move as the drive acts, within one pass plus one refresh | PASS |
| 1 — expanded cards stay expanded across reloads | PASS: manual reload and the 30 s timer reload |
| 2 — the pasted jump command switches to the batch's tab | PASS |
| 3 — a session waiting on a prompt shows `blocked` | PASS: two sessions, observed unprompted |

## Setup note: the driver had to be restarted

The drive that was running had started on 2026-10-05 at 20:35 UTC, before #980 merged. It
therefore never re-rendered `board.html` (R11). It was stopped between passes and restarted on
the new `fr` with the same arguments. Until then the board was rendered with `fr triage board`
from the facts that drive collected. `fr triage board --watch` correctly refused (R12):

```
error: a drive (pid […], started 2026-10-05T20:35:28[…]) holds ~/.cache/fr/triage/derio-net--super-fr/drive.lock; it keeps the board fresh
```

## 1 — columns

The oracle does not reuse fr's code. It takes every PR and issue live from `gh pr list` and
`gh issue list` (`--state all`), applies R2's column table and the §3.A stage rules to
`judgements.yaml` directly, and compares the result with the `data-column` section each card
renders in:

```
per column (want): {'closing-out': 49, 'done': 42, 'proposed': 1, 'waiting': 5, 'pr-open': 4}
per column (page): {'proposed': 1, 'waiting': 5, 'pr-open': 4, 'closing-out': 49, 'done': 42}
mismatches: none | extra on page: none
```

The column header counts read `Proposed 1, Waiting 5, Running 0, PR open 4, Closing out 49, Done 42`.

The board was rendered and `herdr tab list` read back to back, three times. Session status
(R7/R9) matched every time, including a transient `done`:

```
herdr-before {'triage-pages-goal': 'working', 'triage-state-integrity': 'idle', 'run-upgrade-midflight': 'working', 'fr-binary-path': 'idle'}
board        {'triage-pages-goal': 'working', 'triage-state-integrity': 'idle', 'run-upgrade-midflight': 'done', 'fr-binary-path': 'idle'}
herdr-after  {'triage-pages-goal': 'working', 'triage-state-integrity': 'idle', 'run-upgrade-midflight': 'done', 'fr-binary-path': 'idle'}
```

## 1 — cards move as the drive acts

After the restart, the new drive re-rendered `board.html` at the end of every pass, acting or
not (R11):

- Non-acting pass: `rendered 2026-10-06 06:13 UTC · facts collected 2026-10-06 06:13 UTC`, with
  only the stopped merges in the log.
- `run-upgrade-midflight` moved **PR open → Closing out** once #977 merged. The oracle re-run on
  fresh `gh` data again matched 101/101.
- Acting pass at 06:20 UTC. The drive logged
  `closeout run-upgrade-midflight: started derio-net/super-fr/run/closeout-run-upgrade-midflight […]`,
  and the board written at the end of that same pass showed the card with hint
  `archive PR pending`, close-out session `working`, and a second jump button
  (`fr triage batch focus run-upgrade-midflight --repo derio-net/super-fr --closeout`, R4).

## 1 — expanded cards survive reloads

This was checked in headless Chrome, driven by Playwright:

```
refresh attr: 30
open before: ['card-triage-dedupe', 'card-fr-binary-path'] scrollY 600
open after manual reload: ['card-triage-dedupe', 'card-fr-binary-path'] scrollY 600
timer reloaded: True | open after timer reload: ['card-triage-dedupe', 'card-fr-binary-path'] scrollY 600
cmd shown: ['fr triage batch focus fr-binary-path --repo derio-net/super-fr']
```

## 2 — jump

The command shown on the card (and copied by its button) was run in herdr. The focused tab
moved to the batch's tab in its wave workspace. Focus was restored afterwards.

```
before: [('w2:t1W', '<operator tab>')]
focused derio-net/super-fr/run/batch-fr-binary-path
focus exit=0
after:  [('w2N:t2', 'derio-net/super-fr/run/batch-fr-binary-path')]
error: no batch 'no-such-batch' in judgements.yaml
unknown exit=2
error: no live session for derio-net/super-fr/run/batch-plan-table-header
no-session exit=2
```

## 3 — blocked

Two batches the drive dispatched at about 06:35 UTC (`triage-dedupe`, `forge-remainder`) stopped
on prompts. herdr and the board agreed:

```
w2J:t3 blocked derio-net/super-fr/run/batch-triage-dedupe
w2P:t1 blocked derio-net/super-fr/run/batch-forge-remainder
('card needs-you', 'triage-dedupe') ['blocked', 'blocked']
('card needs-you', 'forge-remainder') ['blocked', 'blocked']
```

Both cards sat in Running with the hint `needs you: session blocked`.

## Found along the way (filed, not defects of #980)

- #987: a batch whose merge the drive keeps stopping on (a conflict) still reads "merge ready".
- #990: merged batches without a wave are never adopted, so 49 already-archived batches read
  "close-out not recorded" until they were adopted by a drive pass that named them.
- #991: plan-mode `drive` turns an unreadable clone into phantom "close-out start" actions.
