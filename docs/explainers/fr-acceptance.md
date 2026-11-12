---
title: "fr-acceptance: A Ledger of What the Product Really Does"
date: 2026-11-11
draft: false
tldr: |
  Passing tests say the code does what the tests expect. The acceptance matrix says
  what a person can do with the product, and how well each of those claims has been
  proven. It is a registry you read, a gate CI enforces, and a scale that makes
  overclaiming awkward.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-acceptance/SKILL.md
  - packages/fr/src/fr/commands/acceptance_cmd.py
  - packages/fr/src/fr/acceptance/**
  - .claude/rules/acceptance-matrix.md
reviewed: 2026-11-12 pr1408 review fixes, retired rows keep the base rule, a failed fetch reads the local default ref, ties break by base
---

## Overview: claims, not tests

A green suite can sit on top of a product that does not do what anyone asked, because
the tests can be about anything. The acceptance matrix is a different kind of list. Each
**row** is one business-level claim, written the way an operator would say it ("an
operator can resume a stopped workspace"), together with where it came from, the tests
that verify it at each level (unit, api, int, ui), and a **status** saying how well it has
actually been proven.

The rows are kept per feature. Each spec that creates rows owns a **fragment**,
`docs/acceptance/features/<spec-slug>.yaml`, and the matrix you read is a **fold** of every
fragment, never a stored file. That is why two branches adding rows for different features
never conflict: each edits its own fragment. A row cites its spec logically, as
`spec:<slug>#R<n>`, so archiving the spec moves nothing in the row. (A repo that still has
the old single `docs/acceptance/matrix.yaml` is split into fragments by
`fr migrate artifacts --yes`.)

You reach for it in three situations: a repo has behaviour and nobody has written down
what it promises (backfill); work is shipping and its claims need to move up the scale
(flip statuses); or a claim can only be proven on a real system you are not on (live
verification). The CI gate keeps all of it honest after that.

## The honesty scale

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
is that coverage must not be inflated, because the operator audits the statuses at review.

## A worked example

A phase of your plan advances the row `webhook-rate-limit`, so when the phase's tests
land you move the row up:

```bash
fr acceptance set-status --id webhook-rate-limit --status ci \
    --notes "limiter tests run in the unit job" \
    --level unit=example-repo:tests/test_limiter.py#test_rejects_over_budget
```

One command moves the row, adds the test reference that justifies the move, and commits
only one fragment. A row your own branch created is rewritten in place; a row an earlier
feature already merged is amended instead (next section). `--notes` is required, because a status that
moved for no recorded reason is the silent change the matrix forbids. An unknown id is
refused rather than created; `add` creates.

Then run the gate:

```bash
fr acceptance check
fr acceptance status
```

`check` verifies references resolve, finds stale rows, and exits 2 on any `failing` row.
`status` is the terminal nag: counts by status plus the open debt, oldest first. A
`--brief` form exists for session start.

## Changing a row another feature merged

Once a feature merges, its rows are history. A later feature never edits them in place:
it appends an **amendment** to its own fragment, and the fold applies it. Every amendment
goes to the fragment of the feature making it, never to the row owner's, so two branches
amending the same row touch two different files, and the order they merged in decides the
result.

```bash
fr acceptance amend --id webhook-rate-limit --op reword \
    --acceptance "Webhooks over budget are rejected with a 429" \
    --why "the response code is now part of the contract"
```

The five ops are `reword`, `set-status`, `add-level`, `drop-level` and `retire`.
`set-status` on a merged row writes the same amendments for you, so the worked example
above works either way. The fragment is your branch's feature: `--feature <spec-slug>`, or
the spec of the run this branch carries. With neither, `set-status` refuses, as `amend`
does: a walk recorded after the merge belongs to the feature whose gate it closes, so the
commands fr prints for one (the walk close-out, `fr gate pass --keep`, deliver's issue
link) name that feature's `--feature` for you. An agent's step record says the same thing with
an `acceptance:` entry `{row, op, why, ...}`.

Each amendment records the row's **revision** it was written against: how many
amendments the row had then. If another feature amends the row and merges first, your
amendment's base is stale. `fr acceptance check` and `deliver` fetch the default branch
and refuse it (exit 2), naming both revisions. When the fetch fails but the checkout
already holds the default branch (a CI job that checked out full history without
credentials, a laptop offline), the check reads that local ref and prints which one,
`default ref: the local ref origin/main at <sha> (fetch failed)`; with no local copy,
CI refuses. Look at what the other feature changed, then run
`fr acceptance amend --rebase`. A stale amendment that merges anyway still applies, but
it marks the row **contested**: debt in `fr acceptance status` and `fr debt`, whatever
its status, until the next amendment at the row's current revision settles it. Retired
rows keep the same rule. A stale amendment that names a row another feature has since
retired, or a stale `retire` itself, is the same debt: the row stays listed, shown as
`retired, contested`, though it has left the matrix, until an amendment at its current
revision settles it. Amendments that land in one commit (a merge commit, a squash) apply
in order of their base, so a branch's own sequence on one row applies as written.

## Backfilling a repo that has no matrix

1. `fr acceptance init` creates the matrix, the rule and the gitignore entry. A CI
   workflow is added only beside existing CI, or with `--with-ci`. It is idempotent.
2. `fr acceptance backfill` prints an inventory (specs with a Test Plan not yet cited,
   plans with no linked rows, hints from the test tree) and the protocol to follow.
3. Draft **one row per business acceptance, not per test**:

   ```bash
   fr acceptance add --id resume-stopped-workspace --capability isolation \
       --acceptance "An operator can resume a stopped workspace" \
       --origin example-repo:docs/superpowers/specs/some-spec.md#R3 \
       --level unit=example-repo:tests/test_up.py#test_resume \
       --status unwired --notes "test exists, not yet in CI"
   ```

   `add` validates the shape and appends; never hand-edit the YAML.
4. Run `fr acceptance check` until only honest warnings remain.
5. Open a review PR. The operator audits every status.

Python references name the test, `#test_y` or `#TestX::test_y`, never a line number: a
line number slides onto whatever test lands there next, and nothing notices.

## Rows born from specs, and rows added mid-flight

A row that comes from a spec's `## Requirements` list cites the requirement
(`--origin <repo>:<spec-path>#R<n>`), so you can trace a claim to the sentence that
demanded it. `fr-brainstorming` creates these and presents them to you at the end of the
design. See [fr-brainstorming-and-plan](fr-brainstorming-and-plan.md).

During planning or building, add a row the moment a real business need appears: a missed
edge case, a failure mode a review found. Do not widen or narrow scope silently. Every
addition is listed in the PR body under "rows added since brainstorm"
(`fr acceptance check --added-since <base-ref>`) with a one-line defense.

## Live verification, and walks

Some claims can only be proven by a real run: a real binary, a real model, a real forge.
Mark such a row `--verify live`, or any strategy `fr verification list` shows. It then keeps
appearing in `fr acceptance status` whatever its status, and the pull request body lists it
under post-merge verification owed. See [verification strategies](../verification-strategies.md).

To record the proof, use a walk:

```bash
fr acceptance set-status --id <row> --walk <log-or-note> \
    --harness <h> --model <m> --strategy <s> --status walked --notes "<what was proven>"
```

A row is **walk-verified** once it has a passing walk on every harness it names (or any one
if it names none). Until then a post-merge row holds its issues open and the PR says `Refs`
instead of `Closes`. When a walk completes the proof, `set-status` prints the commands to
close the issue; fr never closes one itself.

You can pay a live debt without being on the target harness. The session doing the work
steers a second session in a neighbouring terminal. The rules that matter:

- build a scratch fixture from real archived artifacts, never hand-made ones;
- **clean the target's environment first**, because fr detects the harness from environment
  keys, and a key leaked from the driver makes it record the driver and go green on the
  wrong thing;
- give the target a closed list of commands and judge from the files on disk, never from
  its own summary;
- record which harness and version, and say whether you proved the command or the
  skill's prose being followed over a long run. Those are different claims.

## Reports and the gate

Reports are derived from the fold and never committed: `fr acceptance report --open`
renders one locally whenever you want to look (it writes `docs/acceptance/report.html`,
which git ignores, and `--format md` writes Markdown). `fr acceptance check` fails if a
report file is ever tracked, because a committed copy is a second source that drifts.

CI publishes the same render where people already look. Every pull request gets the
summary in its job (GitHub and Gitea Actions) or an exposed artifact (GitLab CI). The HTML
goes to Pages from the default branch, but only where the site can be no more visible than
the repo: the repo is public, or the forge reports the Pages site as access-controlled.
`fr acceptance pages-check` makes that call and fails closed: Gitea, a missing token or
any failed read means no Pages job, and the README badge points at the latest CI run
instead. The scaffolded job asks again before every deploy and, when the answer is no, fails the
job with an error that says how to unpublish. The re-check stops new deploys but cannot
unpublish a site that is already live, so a repo that later turns private keeps its
published site until you delete it by hand (GitHub: the Pages site in the repo settings, or
`DELETE /repos/{owner}/{repo}/pages` as an admin; GitLab: remove Pages in the project
settings). The job exists only where Pages were allowed at init, so a refusal means the
visibility changed and should be loud. On GitLab the job reads the forge with a masked CI
variable `FR_PAGES_TOKEN` (`read_api` scope) you create yourself; a self-managed host also
needs `glab` authenticated in the image. With
`forge.report_comment: on` (and comments on) CI also keeps one PR comment with the Markdown
report, found by its marker and edited in place only when this identity wrote it.

CI runs the gate on every pull request and push to the default branch and keeps a weekly
"Acceptance debt" issue up to date from `fr acceptance digest`.

## Limits

- A row is a claim you wrote. The matrix makes it hard to overstate one, not impossible.
- It records business behaviour. A process directive ("delivered in one phase") is not a row.
- Sibling-repo references are verified only where a checkout exists (`--sibling-root`).
- A repo can turn the matrix off with `artifacts.acceptance: off` in `.fr/settings.yaml`
  (`fr settings show`). Every acceptance surface then reports "disabled by repo setting",
  and `fr acceptance add`, `set-status` and `init` refuse. This is not the same as having no
  matrix yet, which is debt to backfill.

## Where to go next

- [fr-brainstorming-and-plan](fr-brainstorming-and-plan.md) creates the rows.
- [fr-devops-gate](fr-devops-gate.md) covers claims that hold a merge for an operator.
- [fr-progress](fr-progress.md) reports plan progress alongside acceptance debt.
