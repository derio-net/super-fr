---
title: "fr-acceptance: A Ledger of What the Product Really Does"
date: 2026-11-11
draft: false
tldr: |
  Passing tests say the code does what the tests expect. The acceptance matrix says
  what a person can do with the product, and how well you have proven each of those
  claims. It is a registry you read, a gate CI enforces, and a scale that makes
  overclaiming awkward.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-acceptance/SKILL.md
  - packages/fr/src/fr/commands/acceptance_cmd.py
  - packages/fr/src/fr/acceptance/**
  - .claude/rules/acceptance-matrix.md
reviewed: 2026-11-12 placement-resolver phase 1, logical refs now resolve through the artifact path resolver; nothing this page describes changed
---

## What does the matrix record?

A green suite can sit on top of a product that does not do what anyone asked. The tests
can be about anything. The acceptance matrix is a different kind of list. Each **row** is
one business-level claim, written the way an operator would say it ("an operator can
resume a stopped workspace"). The row also names where the claim came from and the tests
that verify it at each level (unit, api, int, ui). Its **status** says how well you have
actually proven it.

The rows are kept per feature. Each spec that creates rows owns a **fragment**,
`docs/acceptance/features/<spec-slug>.yaml`. The matrix you read is a **fold** of every
fragment, never a stored file. So two branches that add rows for different features never
conflict: each edits its own fragment. A row cites its spec logically, as
`spec:<slug>#R<n>`, so archiving the spec moves nothing in the row. (If a repo still has
the old single `docs/acceptance/matrix.yaml`, `fr migrate artifacts --yes` splits it into
fragments.)

You reach for the matrix in three situations:

- A repo has behaviour, and nobody has written down what it promises (backfill).
- Work is shipping, and its claims need to move up the scale (flip statuses).
- Only a real system you are not on can prove a claim (live verification).

After that, the CI gate keeps all of it honest.

## How honest is each status?

Statuses move explicitly, with a reason, never silently:

| Status | Meaning |
|---|---|
| `ci`, `scheduled` | automated: the safe end |
| `walked` | proven live, dated by its latest passing walk |
| `manual` | a process that will never be automatable |
| `unwired` | a test exists, but not in CI (debt) |
| `walk-owed` | a live or post-merge run is owed (debt) |
| `not-implemented` | nothing exists yet (debt) |
| `failing` | known red; `fr acceptance check` exits 2 |

When you cannot decide between `ci` and `unwired`, choose `unwired`. The skill's own rule
is that you must not inflate coverage, because the operator audits the statuses at review.

## A worked example

A phase of your plan advances the row `webhook-rate-limit`. When the phase's tests land,
you move the row up:

```bash
fr acceptance set-status --id webhook-rate-limit --status ci \
    --notes "limiter tests run in the unit job" \
    --level unit=example-repo:tests/test_limiter.py#test_rejects_over_budget
```

One command moves the row, adds the test reference that justifies the move, and commits
only one fragment. fr rewrites a row in place when your own branch created it. When an
earlier feature already merged the row, fr amends it instead (next section). You must give
`--notes`, because a status that moved for no recorded reason is the silent change the
matrix forbids. fr refuses an unknown id rather than create it; `add` creates.

Then run the gate:

```bash
fr acceptance check
fr acceptance status
```

`check` verifies that references resolve, finds stale rows, and exits 2 on any `failing`
row. `status` is the terminal nag: counts by status plus the open debt, oldest first. A
`--brief` form exists for session start.

## How do you change a row another feature merged?

Once a feature merges, its rows are history. A later feature never edits them in place.
It appends an **amendment** to its own fragment, and the fold applies it. Every amendment
goes to the fragment of the feature that makes it, never to the row owner's. So two
branches that amend the same row touch two different files, and the order they merged in
decides the result.

```bash
fr acceptance amend --id webhook-rate-limit --op reword \
    --acceptance "Webhooks over budget are rejected with a 429" \
    --why "the response code is now part of the contract"
```

The five ops are `reword`, `set-status`, `add-level`, `drop-level` and `retire`.
`set-status` on a merged row writes the same amendments for you, so the worked example
above works either way.

The fragment is your branch's feature: `--feature <spec-slug>`, or
the spec of the run this branch carries. With neither, `set-status` refuses, as `amend`
does. A walk recorded after the merge belongs to the feature whose gate it closes. So the
commands fr prints for one (the walk close-out, `fr gate pass --keep`, deliver's issue
link) name that feature's `--feature` for you. An agent's step record says the same thing
with an `acceptance:` entry `{row, op, why, ...}`.

Each amendment records the **revision** of the row that it amends: how many
amendments the row had then. If another feature amends the row and merges first, your
amendment's base is stale. `fr acceptance check` and `deliver` fetch the default branch
and refuse it (exit 2), and name both revisions.

When the fetch fails but the checkout already holds the default branch, the check reads
that local ref and prints which one,
`default ref: the local ref origin/main at <sha> (fetch failed)`. That happens in a CI job
that checked out full history without credentials, or on a laptop offline. With no local
copy, CI refuses. Look at what the other feature changed, then run
`fr acceptance amend --rebase`.

A stale amendment that merges anyway still applies, but it marks the row **contested**.
That is debt in `fr acceptance status` and `fr debt`, whatever its status, until the next
amendment at the row's current revision settles it.

Retired rows keep the same rule. A
stale amendment can name a row another feature has since retired, or be a stale `retire`
itself. That is the same debt: the row stays listed, shown as `retired, contested`, though
it has left the matrix, until an amendment at its current revision settles it. Amendments
that land in one commit (a merge commit, a squash) apply in order of their base. So a
branch's own sequence on one row applies as written.

## How do you backfill a repo that has no matrix?

1. `fr acceptance init` creates the fragments directory, `docs/acceptance/features/`, the
   rule and the gitignore entry. It adds a CI workflow and a README badge only beside
   existing CI, or with `--with-ci`. It is idempotent.
2. `fr acceptance backfill` prints an inventory and the protocol to follow. The inventory
   lists specs with a Test Plan no row cites yet, plans with no linked rows, and hints
   from the test tree.
3. Draft **one row per business acceptance, not per test**:

   ```bash
   fr acceptance add --id resume-stopped-workspace --capability isolation \
       --acceptance "An operator can resume a stopped workspace" \
       --origin spec:some-spec#R3 \
       --level unit=example-repo:tests/test_up.py#test_resume \
       --status unwired --notes "test exists, not yet in CI"
   ```

   `add` validates the shape and inserts the row after its capability's last row. Never
   hand-edit the YAML.
4. Run `fr acceptance check` until only honest warnings remain.
5. Open a review PR. The operator audits every status.

Python references name the test, `#test_y` or `#TestX::test_y`, never a line number. A
line number slides onto whatever test lands there next, and nothing notices.

## Where do rows come from?

A row that comes from a spec's `## Requirements` list cites the requirement
(`--origin spec:<slug>#R<n>`). So you can trace a claim to the sentence that demanded it.
`fr-brainstorming` creates these rows and shows them to you at the end of the design. See
[fr-brainstorming-and-plan](fr-brainstorming-and-plan.md).

During planning or building, add a row the moment a real business need appears: a missed
edge case, a failure mode a review found. Do not widen or narrow scope silently. The PR
body lists every addition under "rows added since brainstorm"
(`fr acceptance check --added-since <base-ref>`), with a one-line defense.

## What if only a live run can prove a claim?

Some claims need a real run to prove them: a real binary, a real model, a real forge.
Mark such a row `--verify live`, or any strategy `fr verification list` shows. The pull
request body lists a row whose strategy runs after the merge (`live`) under "Post-merge
verification owed". It lists one whose strategy runs before the merge under "Pre-merge
verification owed". `fr acceptance status` lists the row only while its status is debt or
the fold marks the row contested. See [verification strategies](../verification-strategies.md).

To record the proof, use a walk:

```bash
fr acceptance set-status --id <row> --walk <log-or-note> \
    --harness <h> --model <m> --strategy <s> --status walked --notes "<what was proven>"
```

A row is **walk-verified** once it has a passing walk on every harness it names (or on any
one, if it names none). Until then, a post-merge row holds its issues open, and the PR says
`Refs` instead of `Closes`. When a walk completes the proof, `set-status` prints the
commands to close the issue. fr never closes one itself.

You can pay a live debt without being on the target harness. The session that does the
work steers a second session in a neighbouring terminal. The rules that matter:

- Build a scratch fixture from real archived artifacts, never from hand-made ones.
- **Clean the target's environment first.** fr detects the harness from environment keys.
  A key leaked from the driver makes it record the driver and go green on the wrong thing.
- Give the target a closed list of commands. Judge from the files on disk, never from its
  own summary.
- Record which harness and version. Say whether you proved the command, or that the agent
  followed the skill's prose over a long run. Those are different claims.

## Where do the reports go?

fr derives reports from the fold and never commits them. `fr acceptance report --open`
renders one locally whenever you want to look. It writes `docs/acceptance/report.html`,
which git ignores, and `--format md` writes Markdown. `fr acceptance check` fails if git
ever tracks a report file, because a committed copy is a second source that drifts.

CI publishes the same render where people already look. Every pull request gets the
summary in its job (GitHub and Gitea Actions) or an exposed artifact (GitLab CI). The HTML
goes to Pages from the default branch, but only where the site can be no more visible than
the repo: the repo is public, or the forge reports the Pages site as access-controlled.
`fr acceptance pages-check` makes that call and fails closed. Gitea, a missing token or
any failed read means no Pages job, and the README badge points at the latest CI run
instead.

The scaffolded job asks again before every deploy. When the answer is no, it fails the job
with an error that says how to unpublish. The re-check stops new deploys, but it cannot
unpublish a site that is already live. So a repo that later turns private keeps its
published site until you delete it by hand.

On GitHub, delete the Pages site in the repo
settings, or call `DELETE /repos/{owner}/{repo}/pages` as an admin. On GitLab, remove Pages
in the project settings. The job exists only where init allowed Pages, so a refusal means
the visibility changed, and it should be loud.

On GitLab the job reads the forge with a masked CI variable, `FR_PAGES_TOKEN`
(`read_api` scope), that you create yourself. A self-managed host also needs `glab`
authenticated in the image. With `forge.report_comment: on` (and comments on), CI also
keeps one PR comment with the Markdown report. CI finds the comment by its marker and edits
it in place only when this identity wrote it.

CI runs the gate on every pull request and every branch push. (super-fr's own workflow
narrows the push trigger to `main`.) A weekly run upserts one `<repo>: Technical debt`
issue (`fr debt issue`). That issue's Acceptance debt section is what
`fr acceptance digest` renders. The weekly run also refreshes a draft PR that archives
long-merged plans.

## What can the matrix not do?

- A row is a claim you wrote. The matrix makes it hard to overstate one, not impossible.
- It records business behaviour. A process directive ("delivered in one phase") is not a row.
- fr verifies sibling-repo references only where a checkout exists (`--sibling-root`).
- A repo can turn the matrix off with `artifacts.acceptance: off` in `.fr/settings.yaml`
  (`fr settings show`). Every acceptance surface then reports "disabled by repo setting",
  and `fr acceptance add`, `set-status` and `init` refuse. This is not the same as having no
  matrix yet, which is debt to backfill.

## Where do you go next?

- [fr-brainstorming-and-plan](fr-brainstorming-and-plan.md) creates the rows.
- [fr-devops-gate](fr-devops-gate.md) covers claims that hold a merge for an operator.
- [fr-progress](fr-progress.md) reports plan progress alongside acceptance debt.
