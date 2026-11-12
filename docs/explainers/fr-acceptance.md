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
reviewed: 2026-11-12 acceptance-fragments phase 2 moves rows into per-feature fragments folded into the matrix and retires matrix.yaml and its committed reports
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

One command rewrites the row in place in the fragment that holds it, adds the test
reference that justifies the move, and commits only that fragment. `--notes` is required, because a status that
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

Reports are derived from the fold and never committed: `fr acceptance report` renders one
locally whenever you want to look. CI runs the gate on every pull request and push to the
default branch and keeps a weekly "Acceptance debt" issue up to date from
`fr acceptance digest`.

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
