# Journal: 2026-10-05-run-upgrade-midflight

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-05T21:01:53+00:00 input=true -->
### operator-brief · discovery · Operator brief: batch run-upgrade-midflight (super-fr#891)

Batch `run-upgrade-midflight` of derio-net/super-fr (goal: A run started on an older fr can be finished after an upgrade). Delivered as ONE PR on branch feat/batch-run-upgrade-midflight; draft PR body carries `Closes derio-net/super-fr#891`; no member issue as a phase tracking_issue.

## super-fr#891: An fr upgrade mid-run strands the cursor: shape-version refusal, adopt won't supersede, and the evidence gate can't accept a historical review

## Symptom

A long-running `fr-goal` run spanning an `fr` upgrade cannot be finished, and there is no
documented way out. Three gates close in sequence.

Setup: a six-phase run started on `fr 4.5.2`, all six phases implemented and reviewed,
cursor sitting on the last phase. Two weeks pass; `fr` is now `5.1.1`. `fr migrate
artifacts --yes` runs cleanly and the cursor survives it intact.

**1. The shape gained a step, so every cursor operation refuses.**

```
$ fr run resolve <run> --step review-phase --item phase/6 --state done
run '<run>' was started against a different version of 'fr-goal@1'
(added: journal-check). A run's cursor is a position in a step list;
start a new run rather than advancing this one against a list it was
never computed for.
```

`advance` and `gates` refuse identically. The refusal is correct in principle — but
`gates` is read-only, and it is the source `fr-goal`'s `deliver` step requires verbatim
for the PR body's "Operator gates" section. A read of recorded history should not be
gated on shape currency.

**2. `adopt` is the documented escape, and it will not run.**

The `fr-goal` skill says: *"Work already in flight when your `fr` changed under it? `fr run
adopt <plan-dir|spec>` rebuilds a cursor from disk, completed phases included, so the plan
joins the run model instead of being stranded."* But:

```
$ fr run adopt docs/superpowers/plans/<slug>
docs/superpowers/plans/<slug> already has a run: <run>.
Inspect it with `fr run status <run>`, or advance it with `fr run advance <run>`.
```

It points at the two commands that just refused. There is no `fr run retire` / `reset` /
`--force`, so the only way through is to delete the run file by hand and re-adopt — which
is what I did, and which silently loses recorded state (below).

**3. The evidence gate cannot accept a review done before the cursor existed.**

After re-adopting, every `review-phase` unit demands evidence, and:

```
$ fr run resolve <run> --step review-phase --item phase/1 --record <record>
phase/1/review-phase: --evidence reviewer=... names no subagent this session
dispatched since the review opened at 2026-10-03T18:47:04+00:00. The review
must be done by a dispatched reviewer (a separate context), and named by the
id its dispatch returned.
```

The six reviews genuinely happened — six dispatched reviewers, ~48 findings recorded in
the plan journal with ids, every one closed or deliberately deferred. But they happened
*before* the adopted cursor opened its units, so no honest record can satisfy the gate.
The only states available are a false `failed`, fabricated evidence, or re-running six
reviews of already-reviewed-and-fixed code purely for bookkeeping.

Note this is not only an upgrade problem: `adopt` exists precisely to take on work whose
phases are *already complete*, so for any adopted run the review evidence is necessarily
historical. The evidence gate and `adopt` are in direct tension by construction.

## What re-adopting silently lost

The pre-upgrade run recorded the operator's batched-Q&A gate:

```yaml
  brainstorm:
    state: done
    answered_by: operator
```

After `adopt`, `fr run gates` says:

```
brainstorm: cleared, but provenance not recorded (this cursor predates `answered_by`)
```

So the PR body's "Operator gates" section would *understate* what happened — the operator
did answer, and the derived record now says it is unknown. `adopt` reads phase completion
from disk; it does not read the superseded run file sitting next to it, which still has the
answer. (Worked around by citing the old run file's git blob and the spec journal's
`decision` entries in the PR body instead.)

## Suggested fixes, roughly in order of value

1. **Let `adopt` supersede a stale run** — `fr run adopt --supersede` (or have it offer,
   as `migrate artifacts` does), carrying forward what the old cursor recorded:
   `answered_by`, dispatch holders, per-step notes. The data is in the file it replaces.
2. **Ungate read-only commands.** `fr run gates` and `fr run status` should answer from a
   stale cursor, with a warning. `status` already does; `gates` does not, and `gates` is
   the one `deliver` needs.
3. **Give the evidence gate a documented honest escape for adopted units** — e.g.
   `--evidence historical=<journal ref>` recorded as such, or a `review-phase` state
   meaning "done before this cursor existed, evidence in the journal". Anything other than
   `failed`, which is false, or re-running the work, which is waste.
4. **Shape-version pinning on the run**: a run could record the shape it was computed
   against and keep operating on it, with `advance` warning that a newer shape exists.
   That would make case 1 unnecessary for in-flight work.

## Version

Started on `fr 4.5.2`, hit on `fr 5.1.1`. `fr-goal@1`, Claude Code harness. The run's
artifacts migrated cleanly — this is purely about the cursor.

<!-- fr:journal kind=decision scope=spec id=shape-drift-explicit-reshape created=2026-10-05T21:01:53+00:00 -->
### shape-drift-explicit-reshape · decision · Shape drift: explicit `fr run reshape`

Operator chose an explicit `fr run reshape <run>` (preview, `--yes` applies) that rebases the cursor onto the current shape keeping every recorded step/unit; added steps ahead of the cursor go in pending; refuses when an added step lands at/behind the cursor or a removed step had left pending. Rejected: auto-reshape inside advance/resolve (side-effect mutation), shape pinning (schema change, no rescue for stranded runs).

<!-- fr:journal kind=decision scope=spec id=adopt-supersede-carry-forward created=2026-10-05T21:01:53+00:00 -->
### adopt-supersede-carry-forward · decision · Adopt: `--supersede` with carry-forward, old file removed

Operator chose `fr run adopt --supersede`: replaces the old cursor (git history keeps it; commit names the superseded run), carrying forward gate provenance (answered_by), attempts and evidence of steps/units still in the current shape. Rejected: keeping a `.superseded.yaml` beside it; no supersede at all.

<!-- fr:journal kind=decision scope=spec id=historical-review-adopt-infers created=2026-10-05T21:01:53+00:00 -->
### historical-review-adopt-infers · decision · Historical reviews: adopt infers + manual `reviewer=historical`

Operator chose both: adopt marks a complete phase's review member done when the plan journal has a kind=review entry for it and no open finding, with evidence review=<id>, reviewer=historical; and by hand `reviewer=historical` is accepted iff the review entry predates the run's start. Rendered as a historical review in status/check and the PR body. Rejected: manual-only; unverified claimed reviewer ids.
