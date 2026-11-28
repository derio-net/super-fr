---
title: "fr-triage: Ranking a Backlog, and Learning Where Defects Come From"
date: 2026-11-11
draft: false
tldr: |
  A backlog is a pile until someone judges it. fr-triage keeps those judgements in a
  file the engine reads and writes around, so a re-run costs only what is new, and a
  group of related issues can be shipped as one reviewed pull request. fr-origins
  asks the sibling question: where did the recent bugs come from?
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-triage/SKILL.md
  - plugins/super-fr/skills/fr-origins/SKILL.md
  - packages/fr/src/fr/triage/**
  - packages/fr/src/fr/commands/triage_cmd.py
  - packages/fr/src/fr/commands/triage_batch_cmd.py
  - packages/fr/src/fr/commands/triage_origins_cmd.py
  - packages/fr/src/fr/commands/triage_kanban_cmd.py
  - packages/fr/src/fr/commands/triage_drive_loop.py
reviewed: 2026-11-28 still true after tester-gate-auto-pass (the driver's gate pass for pull requests outside a batch is fr-exit-gates' and fr-wave-driver's to say); 2026-11-28 triage-privacy, an admission pins outside comments (v2 marker, v1 admissions need a new admit), outside PR titles are withheld, and the privacy guard scans every carried file; 2026-11-28 still true; a state mover that loses the race to another mover's tombstone now resolves to the cache instead of refusing, which this page does not detail; 2026-11-28 still true; the rows-walked pass now reads a row as walked only when its latest walk passed (ops-gate-truth R10), which this page does not detail; 2026-11-27 board-session-state lens review, an unusable ledger is kept as dwell.json.bad (which never rides on the state branch) before the writer starts over, a ledger that cannot be stored is a page note and never stops the render, and each ignored lane_owners item is worded for its cause; 2026-11-27 still true, module split only; 2026-11-27 export-drift, an export records what it wrote (exported-files) and refuses a file changed in the repo since (export --force overrides), and import --only takes in named paths only; 2026-11-27 still true after queue-followups phase 2 (the approval lifecycle, ended labels, waiting on a real conflict and the void comment, is fr-wave-driver's to say); 2026-11-27 still true after queue-followups phase 1 (plan overlap compares repo names case-insensitively; the close-out and probe changes are fr-wave-driver's to say); 2026-11-27 batch closeout-state adds the left-scope stage and `batch cancel --orphaned`, both named her; 2026-11-27 still true; shared-helper refactor (batch arch-shared-helpers), no behaviour change; 2026-11-27 still true, isolation/local.py split into modules (#1517), no reader-visible change; 2026-11-26 still true after landing-method (the merge method order and the push landing hold are the fr-triage skill's and fr-wave-driver's to say); 2026-11-25 the state lives in the host cache `~/.cache/fr/triage/<scope>/`, its own git repository; an older clone's `.fr/triage-state/<scope>/` moves there on first use, leaving a tombstone; a one-repo scope may name its state repo in `.fr/settings.yaml` (S1 R17-R20); 2026-11-25 still true after ci-economy (the queue settles stamp and generated conflicts, cancelled checks read pending; the fr-triage skill and fr-wave-driver say so); 2026-11-25 still true after batch merge-readiness phase 1 (facts schema 19 records whether the run cursor was read; the merge rule is fr-wave-driver's to say); 2026-11-25 plan overlap set of check (wave-plan-file-overlap); 2026-11-25 wave-queue-gaps phase 3 review, suggest also prints the overlapping pairs of one wave (never across repos); 2026-11-25 still true after ci-economy (the queue settles stamp and generated conflicts, cancelled checks read pending; the fr-triage skill and fr-wave-driver say so); 2026-11-24 still true after wave-queue-gaps phase 1 (judgements schema 14 reads every older stamp, so the example still loads; the hand-back changes are fr-wave-driver's to say); 2026-11-24 still true after batch closeout-truth (the close-out re-record, approval, session close and migration wait are the fr-triage skill's and fr-wave-driver's to say); 2026-11-23 still true; the Python 3.14 floor reformats covered code (unparenthesised `except A, B:`, PEP 695 generics), syntax only (#1589); 2026-11-23 pr-readiness-wait phase 1, every driver brief gains one sentence (the driver owns the PR's mergeability and CI, so the session runs no `fr pr settle` loop); still true; 2026-11-22 check lists ignored claims, obsolete batches and stale members; untrusted issues lose their titles, and an operator admits one with fr triage admit, since the label alone no longer admits (triage-hardening); gate names, runner status and timestamp refactors preserve this interface; 2026-11-20 batch train-truth R21 cancel of a never-dispatched batch needs no clone, R24 the driver's failure boundary, supervisor, drive status/log/failures, the Activity panel and the early red and conflict hand-backs; 2026-11-19 batch docs-wording changes help text and docstrings only (bracketed help renders, first lines shortened for STE, `fr ops gate` hint names the full scaffold command); still true; 2026-11-17 the untrusted set of check, and the intake rule (batch triage-intake, facts schema 15 on top of main's 14); collect only reads the forge (it reports repos without approved-fr, and the first dispatch creates the label); scope retire settles closed issues. 2026-11-15 still true, the gate ledger now also reads archived run cursors (batch gate-truth); 2026-11-19 a full PR list warns (may show not collected); Batches columns fold and the wave cutoff; Origins groups, state filter and merged PRs. 2026-11-18 one name per page (fr triage backlog writes backlog.html and issues.html, fr triage batches writes batches.html; render and board stay as aliases). 2026-11-17 the untrusted set of check, and the intake rule (batch triage-intake, facts schema 15 on top of main's 14); collect only reads the forge (it reports repos without approved-fr, and the first dispatch creates the label); scope retire settles closed issues. 2026-11-15 still true, the gate ledger now also reads archived run cursors (batch gate-truth); 2026-11-21 wave-merge-queue lens fixes, defer, requeue and queue-retry are named, a moved block voids an approval; 2026-11-20 wave-merge-queue phase 5 fixes, the merge train is gone (one queue per repo; a repo with no queue block merges nothing); wave-merge-queue phase 1 fixes, a moved identical change counts as the same diff; wave-merge-queue phase 1, judgements schema 13 and an approval pinned to the pull request's diff
---

## Why keep the judgement in a file, with an engine around it?

Triage is two jobs. One is mechanical: fetch the issues, notice what changed, draw the
page. The other needs judgement: which issue costs most if ignored, which two are the same
bug, which five belong in one change. fr splits them cleanly. The **engine**, `fr triage`,
does the mechanical job and is the same on every harness. The **skill** holds only the
discipline for the judging, and you write your judgements to a file the engine reads.

The consequence is cheap sync. A second triage is the same loop, and `check` names only
what arrived, shipped or went missing since your last pass, so nothing is re-judged.

You reach for it when someone asks you to triage, rank or organise the open issues of a
repo or a whole organisation. You also reach for it to get a board of "what next", or to
refresh a triage you did before. You reach for **fr-origins** when the question is where recent bugs came from and
which process change would have prevented them.

## What does a worked example look like?

```bash
fr triage collect --repo example-org/example-repo
fr triage check   --repo example-org/example-repo
```

`collect` reads the forge and writes `facts.json`. `check` prints the sets you act on. The
important one is **unranked**: open issues with no judgement yet. You read each one and the
code it names, then add an entry to `judgements.yaml`. It sits beside `facts.json` in the
scope's state directory (`~/.cache/fr/triage/example-org--example-repo/`; `collect` prints
the path), and you create it on the first run:

```yaml
schema: 12
ranked_at: 2026-11-11
tiers:
  - {n: 1, title: "Data loss", description: "Work destroyed with no prompt or salvage."}
issues:
  "example-repo#435":
    tier: 1
    theme: isolation
    severity: high
    cx: S
    verified: true
    detail: "`gc()` trusts the merged state and tears down locally. Still live on main."
```

`tier` is the priority group, `severity` is `low`, `med` or `high` (`check` lists a judged
issue that has none), and `cx` is your size estimate of the fix: `XS`, `S`, `S-M`, `M` or `L`.

Then draw the pages:

```bash
fr triage backlog --repo example-org/example-repo --open
```

You get two pages. `backlog.html` holds the decisions: what changed since the last report,
what needs you right now, the driver's order for what is next, the waves and the batches.
`issues.html` holds the lists: the backlog by tier, ranked features, parked issues, debt and
open pull requests. (`fr triage render` is the old name of this command and still works.) When several judged issues share a
subsystem, propose them as a batch:

```bash
fr triage batch create merged-trust --repo example-org/example-repo --title "Stop trusting merged state" \
    --issue "example-repo#435" --issue "example-repo#469"
```

## Which files hold the state, and who writes them?

Everything lives in the scope's state directory, `~/.cache/fr/triage/<scope>/` (`--dir`
picks another). A scope is `owner--repo` for `--repo`, or the owner for `--org`;
`--repo A/B,C/D` is a group. The directory is its own git repository. It holds the objects
of the scope's state branch and the remote it pushes to, so fr syncs the state with no
product clone. A repo's `.fr/` holds configuration only, never triage state.

| File | Written by | Holds |
|---|---|---|
| `facts.json` | `fr triage collect` | forge data: issues, labels, PRs (it only reads the forge) |
| `judgements.yaml` | **you**, plus the `batch` verbs | tiers, rankings, kinds, patterns, batches |
| `backlog.html`, `issues.html`, `batches.html` | `backlog`, `batches` | the pages |
| `dwell.json` | the Batches page's render (one writer, below) | how long each batch has been in its column and its wait |

Never write the facts yourself. fr does not commit the state by default; its durable copy
is an orphan branch, `refs/heads/fr-triage/<scope-id>`, which fr fetches before reading and pushes after
every change. `fr triage state export --to <dir>` and `import --from <dir>` copy it to and
from a repo.

The state directory is the source, and only an export writes the repo copy. Each export also
writes `exported-files` there, a record of each file the repo copy then holds and its hash. If someone then
edits, deletes or adds a file in the repo copy, the next export stops before it writes
anything, so it cannot undo that edit, and it names each file. To keep the edit, take it into
the state first: `fr triage state import --from <dir> --only <path>` moves only the paths you
name, even over a newer state file, and removes one the repo deleted. To keep the state's
version instead, run `fr triage state export --force`. With no record yet, the export goes
ahead and writes the first one. A damaged record (not JSON, the wrong shape, a link, or a
name that is not a durable file) also stops the export, with no import to offer: mend or
remove it in the repo, or run the `--force` export, which rewrites it.

The state branch lives in a repo that fr picks once per scope. A scope first collected from a
stealth workspace uses its tracking repo. Otherwise a scope of one repo uses that repo, and fr
asks for any other scope. A one-repo scope can name its own: `triage.state_repo:
<owner>/<repo>` in that repo's `.fr/settings.yaml`, which then declares `schema: 2`. fr uses
it only when the scope records no state repo yet. When the two differ, `fr triage check`
lists the mismatch. The privacy guard still refuses to push a private issue to a public repo. When the state
repo is public and a repo of the scope is not, the guard also reads every file the push or
export carries. It refuses a file that names the non-public repo as `owner/name` or as
`name#<number>`, in its text or in its path. It also finds the name when zero-width
characters split it or a URL escapes its slash. A push scans the commit it is about to
push, so a file changed after the scan cannot slip past. The refusal names the file and
the repo, never the matched text. A file it cannot read also refuses.

**Upgrading from an older fr.** Older versions kept the state in a clone, under
`.fr/triage-state/<scope>/`. The first fr command that uses the scope from that clone moves
the state into the cache. It refuses while a live `drive.lock` names a running driver: stop
the driver first. A cache that already held an older copy is set aside as `<scope>.pre-s1`.
In the clone fr leaves a small tombstone file that names the new place. An older fr fails on
it instead of quietly starting a second copy. After you upgrade, restart any running
`fr triage batch drive` with the new fr, and run no older fr on that host.

## What does `check` tell you?

It always exits 0 and prints sets, not verdicts:

- **unranked**, issues and PRs: your work queue;
- **settled**: judged, now closed. Report what shipped and keep the judgement;
- **orphaned**: the key names a repo collect did not read, a typo or a rename. The only
  set safe to act on without the forge;
- **unreachable**: collect could not settle it (rate limit, lost access). Never prune on
  this;
- **untrusted**: open issues whose author is an outside account that no operator admitted,
  each with its reason. Collect does not store their title or body. You never judge, rank
  or batch one. An operator admits one with `fr triage admit <key>`. It adds the `ready-fr`
  label and a comment that fixes the issue's current text, and every comment on it by an
  account that is neither an owner, member or collaborator nor listed in `pr_authors`. If
  the author edits the issue later, or such an account adds or edits a comment, the
  admission no longer counts. An admission made before this check
  covered comments needs a new `fr triage admit`. A pull request by an outside author keeps
  its title out of the facts;
- **ignored claims**: claim markers written by an account that is not trusted. They hold
  nothing, so check prints each one. When the account is one of your own hosts running as
  another forge user, list it in `pr_authors`; that also lets it admit issues, so never list
  an account you do not run;
- **obsolete batches**: batches never dispatched whose members are all closed. They no longer
  hold up a wave or a batch that waits on them. Retire one with
  `fr triage batch cancel <id> --yes`, which closes nothing;
- **stale members**: closed members of a batch still proposed, listed by batch, so you can
  edit them out before you dispatch it;
- **plan overlap**: two unmerged batches whose plans name the same file. Each plan lists the
  files its phases will touch, and that list is on the batch's branch long before its pull
  request is ready. `check` compares the lists of every batch that is dispatched or has an open
  pull request. A file one plan names exactly and the other names by a pattern counts as
  shared. Two patterns never count, because they would flag almost every pair. Files the repo
  generates, files every batch bumps, and batches ordered with `after` are left out. It is
  advice only: it reads the branches your local clone already has, never fetches, and changes
  nothing. `check` reads only the clone you run it in, so it compares only the batches of that
  clone's repo. The Batches page does the same when you run `fr triage batches` yourself, and
  reads every clone the driver was given when the driver writes it. A batch it
  could not read is listed with the reason, so an empty set means nothing overlaps, not that
  nothing was read. To fix an overlap, merge the
  two batches, or run `fr triage batch edit <id> --after <other>`, or give one a later wave;
- **stale dispatch**, **awaiting live**, **unplaced**, **duplicate candidates**: batches
  that went quiet, issues waiting on a post-merge walk, issues in no batch, and pairs the
  engine proposes as duplicates. A proposal is not a verdict: you judge every group.

You triage open pull requests in the same loop. Each carries an intent anchor, the thing
that says what the PR is for: the issue it closes, a spec, a debug journal, or none. You mark
it `delivers`, `partial`, `drift` or `unanchored` with one line. It is shallow by design: never a code review.

## How do you judge?

1. **Tier by what the failure costs**: lost work first, then a failure that looks like
   success, then friction. Never by age, label, reporter or how loud the issue is.
2. **Verify against current main.** Before `verified: true`, re-read the cited line. At forty
   issues a fixed bug stays ranked as live. If you did not re-read it, write
   `verified: false`.
3. **Record line drift** in `detail`. A bug already fixed is a close recommendation, not a
   ranking.
4. **Hunt duplicates and batches.** Record a duplicate in `duplicate_of` (or `distinct_from`
   for a pair that only looks alike), never as prose. Three or more issues with one root
   cause become a `patterns` entry.
5. **Forge actions are unrun commands.** A close, a dedupe or a relabel is the exact command
   in your report, for the operator to run. Never act on the forge unasked.

Quote every title and note in the YAML: an unquoted `: ` breaks the file.

## What are batches and the driver?

A **batch** is a group of judged issues delivered as one [fr-goal](01-fr-goal.md) run (an
fr-debugging run for a batch created or edited with `--skill debug`) and one pull request. The `fr triage batch` verbs are `list`, `create`, `edit`, `cancel`,
`suggest` (candidate groupings, and each pair of batches in one wave of one repo that expect to change the same file; input, never the answer), `dispatch`, `adopt`, `merge`,
`closeout`, `drive`, `replace`, `focus`, `defer`, `requeue` and `queue-retry`. `dispatch`, `merge` and `cancel` write to the
forge only with `--yes`; without it they print the plan. A `cancel` of a batch that was never
dispatched labels and comments nothing, needs no clone, and only releases the claims of this scope.

A batch can outlive its repo. When the repo is no longer in the facts of the scope, and the list
of repos was not cut short, the batch has the stage `left-scope`. It is closed out: it holds no
issue, owes no claim, the driver plans nothing for it, and `drive` asks for no clone of that
repo. The board shows it in Done with the words "repo left this scope", and `batch list` marks
its row. If the repo returns, the batch has its old stage again. `batch focus` refuses such a
batch. Retire it with `fr triage batch cancel <id> --orphaned`: that only writes the cancel
event, and nothing on the forge is touched. A `cancel` without `--orphaned` refuses, and so does
`--orphaned` on any other batch.

`fr triage batch drive` runs batches to completion in waves. A wave is a set of batches that
may run at the same time; a batch names the wave it belongs to, or the batch it must come
`after`. The driver merges ready pull requests through one merge queue per repo: it tests each
ready pull request on top of the ones ahead of it, in the order they became ready, and lands
the tested result. A repo needs a `queue:` block in `.fr/triage.yaml`; without one the driver
holds every merge and says so under Needs you now. The driver also closes out what has landed
and dispatches what may start. Merging a batch pull request needs the operator's `approved-fr`
label, which holds while the pull request's own diff stays the same. A block of changes moved
unchanged to another place in the same file counts as the same diff. The driver never writes
to a pull request's branch and never approves its own work.

A pass that fails because of a passing fault, such as a forge call that timed out,
ends and the next pass starts after a longer wait. A fault that only you can fix, such as a
second writer on the state ref, stops the driver and shows on the board under **Needs you
now**. Ten failed passes in a row also stop it. `fr triage batch drive --supervise --yes`
restarts a driver that crashes, and ends with the session that started it. `fr triage
drive status`, `fr triage drive log` and `fr triage drive failures` show what it holds, did
and failed at. The driver also hands failing checks and real merge conflicts back to a
batch's session while the pull request is still a draft.

`fr triage batches` draws `batches.html`, a Kanban of every batch by lifecycle column. It has
four "Needs you" lanes (developer, reviewer, tester, devops), which the board decides from
the run's cursor and the merged PR's gate labels, never from a session's status. Below the
columns, an **Activity** panel shows the newest lines of the driver's log. Every column
has a button in its header that folds it and opens it again. A column with no cards starts
folded, and on a wide screen a folded column is a narrow strip with its title turned on its
side, so the columns that hold cards get the room. The page remembers each column in your
browser, so the automatic reload keeps what you chose. A toggle, "last 30 days" by default,
hides every wave whose batches are all finished and have had no event in the last 30 days;
"all waves" shows them again, and the page remembers that choice too.

Each card names the one party it waits for, as a pill: `you` (with the lane's role), `agent`,
`background` (an idle session with background shells, monitors or subagents running, read from
the herdr runner), `ci`, `queue` (the driver or merge queue acts next) or `dependency`. Only a
Done card waits for no one. The wait never moves a card: the column comes first. A repo may
name who owns each Needs-you lane in `.fr/triage.yaml`:

```yaml
lane_owners: {developer: [alice], reviewer: [bob, carol], tester: [], devops: []}
```

The column header then reads `owner: @bob, @carol`, or `owner: unassigned`, and one line per
repo when the repos of a scope differ. The key is for display only. A lane name it does not
know is ignored, and the page says so. A card in a lane, and a Tester or DevOps gated
pull request, shows the short pill `waits for you · reviewer` and its owners on a line below,
or `(unassigned)`.

Under its hint each card has a dwell line: `in PR open 3h 12m · waits for ci 45m`. A Done
card, which waits for no one, shows its column time only. Times read `45m`, `3h 12m` or
`2d 4h`. A `≥` in front means the board first saw that state when it was already under way, so
the real time is at least that long. After the merge queue, the page has a "Time per wave"
section. It has one block for each wave, and one for the batches with no wave. Each block
lists the time the wave's batches spent in each column and waiting for each party, and the
batch that spent the longest in each column. The Done column is left out of Time per wave,
because its time only grows once a batch is finished.
The 30-day toggle hides the same waves there.

The times come from `dwell.json`, a ledger in the state directory that the state branch
carries. Each render compares the board with the ledger. When a batch changed its column or
its wait, the render closes the old interval and starts a new one. A batch keeps its last 200
intervals. Only one kind of process stores the ledger: the driver, or a render while no
driver runs anywhere. "No driver" means that no live driver holds the local `drive.lock` and
that `lease.yaml`, which the state branch carries from other hosts and cloud sessions, holds no
lease that is still valid. Any other render, such as `fr triage batches` beside a driver on this
host or on another one, works out the times in memory and writes nothing, so it pushes nothing.
This is not a lock: a driver that starts while such a render runs can lose at most one
observation, which the next render makes again. A fetch of the state branch takes the branch's `dwell.json` over the local one and
never refuses over it, because the file is observation, not your work. A file fr cannot read
starts the times over and puts one note on the page, naming the file and the first error. When the
process that stores the ledger finds such a file, it first moves it to `dwell.json.bad`, which
replaces an older copy and never rides on the state branch. A ledger that cannot be written is
one more note, and the page still renders. The times are only as precise as the
renders: the driver renders on each full pass, so a change is dated at the next render that
sees it, and a state shorter than the gap between two renders can go unseen.

Several scopes can work one repo, so a scope **claims** each issue it plans to act on with an
`fr:claimed` label and a marker comment. Another scope's claim is hands-off. Taking one over
(`fr triage claim take`) or releasing it is the operator's call, never yours. When a scope
has stopped for good, `fr triage scope retire <id>` releases all its claims. For a closed
issue it also removes both `fr:` labels, because that issue's work is over. The
[herdr guide](../herdr-control-sessions.md) and the [cloud guide](../cloud-setup.md) cover
runners, restarts and the cloud driver. [The wave driver](fr-wave-driver.md) walks through
what one pass does and where you act.

## fr-origins: where did the bugs come from?

You can read an issue and the code it names. A classification done in chat dies with the
session; `fr triage origins` keeps it, so a re-run costs only what arrived.

```bash
fr triage origins collect --repo example-org/example-repo --since 2026-10-01
fr triage origins check   --repo example-org/example-repo
fr triage origins render  --repo example-org/example-repo
```

`collect` writes `origins-facts.json`; you write `origins.yaml`, one classification per
issue; `render` builds `origins.html`. Collect refuses a window wider than one page, and
names a `--since` that the page does cover. It also keeps the pull requests merged since
that date, so the page can show each one's title and merge date. The "Every issue" section
has a filter for open, closed or all issues and one fold for each category below, each with
its count; the filter updates the counts. In the list of pull requests that left work
behind, each row opens to the issues that name it. The PR list is read once per repo,
newest created first. When it comes back full, collect warns: a PR created before the
oldest one read but merged inside the window can lie beyond it, and then shows
"not collected". A pull request the file does not hold
(merged before the window, or collected by an older fr) shows "not collected". The categories describe what the defect *is*, not who noticed it:

- **latent**: always there, nothing changed it;
- **regression**: a change broke something that worked, and you can name the pull request;
- **new-feature**: a defect in something recently added;
- **leftover**: work a PR should have finished and did not;
- **gap**: a missing capability or test nobody claimed;
- **duplicate**: the same defect as another issue; name it.

Each entry also carries a source (`pipeline`, `recording` or `hand`) and a severity. A
regression with no `pr:` is invalid, and one bad entry makes every verb that reads the file
exit 2. Read the body and the code; a title is a hypothesis. The page ends with `causes:`,
each linked to the batch that addresses it and a one-line process change.

## What does triage not do?

- The engine ranks nothing. Every tier is your judgement.
- `check` is as current as the last `collect`.
- Each render rewrites the pages; hand-written analysis goes in the fragments listed in
  each page's `manifest.yaml`, never in an edited page.
- Keep state and pages local for any repo that is not yours. A privacy guard refuses to
  batch a private repo's issue into a scope whose state repo is public, and refuses to push
  or export a file that names such a repo.

## Where do you go next?

- [fr-goal](01-fr-goal.md) is the run a batch becomes (fr-debugging for a batch created
  with the debug skill).
- [fr-audit](fr-audit.md) draws the architecture page and the cost of a run.
- [fr-acceptance](fr-acceptance.md) covers the post-merge walks that keep an issue open.
