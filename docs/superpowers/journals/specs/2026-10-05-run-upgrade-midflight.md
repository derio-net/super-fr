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

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-10-05T21:09:29+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · carry-forward's 'unit key present in both' drops every review-phase and step/* unit

build_run_state writes only phase/N/<first member> keys and no step/<id> units (adopt.py:370-384, :393-403), so 'present in both' never matched a reviewed member, spec-review's evidence or deliver's. Contradicts decision adopt-supersede-carry-forward. Fix: carry every old unit whose step and member still exist; state at/driver.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-10-05T21:09:29+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · --supersede says nothing about open attempts or units held by a live session

Attempts copied verbatim carry an open hold (e.g. #891's phase/6 review) into the new cursor; advance would refuse it or a dead session holds it forever. Pick: refuse while held, or close as abandoned.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-10-05T21:09:29+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · --supersede orphans the old run's usage file and records directory

usage/<old>.yaml loses its cursor (archive.py:521-555 keys on run id), PR body ## Cost and fr run cost undercount; a live <old>.records/ step record is stranded.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-10-05T21:09:29+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · reshape rules 2 and 4 decide on state == pending, but a pending record can carry data

An adopted pending group carries done units keyed on old members; a pending removed step can hold gate/answered_by, emitted (plan = archive key) or units. Check content, not lifecycle.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-10-05T21:09:29+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · reshape alone does not finish #891 case 3 when the review ran in an earlier session

A review dispatched in an earlier session after start fails both the dispatch check and the before-started bound after reshape; only --supersede works. Widen R7 or state it plainly.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-10-05T21:09:29+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · reviewer=historical's before-state.started bound can be gamed

Write entry then --supersede passes; an entry from an abandoned earlier attempt passes for a phase this cursor implements later. Bound against the implement member's last return; state the residual trust model.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-10-05T21:09:29+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · historical review leaves visual and the reviewer-return check undefined

review-phase also owes visual (fr-goal.yaml:181), whose witness needs observed screenshots; reviewer-return check would note unobserved. Specify both.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-10-05T21:09:29+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · ## Historical reviews 'required on the live PR' has no mechanism; missing_sections is static

pr_body.missing_sections takes no state (pr_body.py:44-61); caller run_cmd.py:5201. Name the change.

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-10-05T21:09:29+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · R8 inference fold omits unauthorized fixes and cannot call the gate

_closed_findings_witness also refuses unauthorized fixes and exits rather than returns; name phase_finding_states + unauthorized_fixes.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-10-05T21:09:29+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · smaller inaccuracies in §A/§C

adopt_run at :552 not :595; step-state rule is a no-op; rule 5 vs rule 4; write path is _save_run_state inside _commits_run_writes; same-day overwrite vs adopt.py:634; --supersede with no run unspecified.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-10-05T21:09:29+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · Test Plan does not cover several designed behaviours

Missing: member-change rule, data-holding pending removal, unparseable old cursor, same-day overwrite + commit subject, unbuilt-unit carry-forward, open attempts, R3 message, live PR lacking ## Historical reviews.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-10-05T21:09:29+00:00 state=open review_scope=out -->
### sr-12 · finding [open] (reviewer: out of scope) · fr pickup resolves the manifest strictly and fails on a drifted cursor

pickup_cmd.py:247 has no lenient path; pre-existing, outside the fr run read-only set; reshape removes the drift.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-10-05T21:09:29+00:00 -->
### spec-review-1 · review · independent spec review: 12 findings (sr-1..sr-11 in scope, sr-12 out)

Dispatched fr-spec-reviewer raised sr-1..sr-11 (in scope) and sr-12 (out of scope). Confirmed: #891's reshape case (journal-check after implement) passes; no artifact shape change owed (reviewer: historical is a value in UnitRecord.evidence).

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-10-05T21:09:29+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: carry-forward's 'unit key present in both' drops every review-phase and step/* unit

Fixed in §C: every old unit whose step and member still exist is carried (created when adoption did not build it) with attempts and evidence, done state kept; driver and at carried. R6 restated.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-10-05T21:09:29+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: --supersede says nothing about open attempts or units held by a live session

Fixed in §C/R6: open attempts are carried closed `abandoned` (what claim --abandoned writes), and the preview lists each hold with agent/session before --yes. Tested.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-10-05T21:09:29+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: --supersede orphans the old run's usage file and records directory

Fixed in §C/R6: usage/<old>.yaml renamed to <new>.yaml in the supersede commit; refuses while <old>.records/ holds a step record (pr-body.md excepted), naming each file. Tested.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-10-05T21:09:29+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: reshape rules 2 and 4 decide on state == pending, but a pending record can carry data

Fixed in §A/R1/R2: 'holds something' (units, gate, answered_by, emitted) is the test for removal and member rewrite, not lifecycle.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-10-05T21:09:29+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: reshape alone does not finish #891 case 3 when the review ran in an earlier session

Fixed by stating it: §A 'What reshape does not cover' names the cross-session case and routes it to --supersede, which §D then treats as historical; R10 prose carries it.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-10-05T21:09:29+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: reviewer=historical's before-state.started bound can be gamed

Fixed in §D: the bound adds 'postdates the implement member's latest returned attempt in this cursor'; the residual (author-written timestamps) is stated as the trust model, with the PR-body listing as the human control. Applied to R8 too.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-10-05T21:09:29+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: historical review leaves visual and the reviewer-return check undefined

Fixed in §D: a phase owing visual evidence cannot take a historical review (re-reviewed; adoption notes it); historical skips the reviewer-return check and writes no unobserved note.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-10-05T21:09:29+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: ## Historical reviews 'required on the live PR' has no mechanism; missing_sections is static

Fixed in §D: missing_sections gains a `required` argument; run_cmd.py:5201 passes the static set plus ## Historical reviews when present. Tested.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-10-05T21:09:29+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: R8 inference fold omits unauthorized fixes and cannot call the gate

Fixed in §D: R8 uses phase_finding_states and unauthorized_fixes directly, and writes the same findings witness string.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-10-05T21:09:29+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: smaller inaccuracies in §A/§C

Fixed: line refs corrected; step-state rule dropped; rule 5 carves out rule 4; write path named; same-day overwrite bypasses :634 explicitly; --supersede with no run behaves as plain adopt.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-10-05T21:09:29+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: Test Plan does not cover several designed behaviours

Fixed: Test Plan now lists every one of the named behaviours per requirement.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-10-05T21:09:29+00:00 state=open resolves=sr-12 out_of_scope=true -->
### sr-12-resolved · finding [out-of-scope] · resolves sr-12: fr pickup resolves the manifest strictly and fails on a drifted cursor

Out of scope: pre-existing in fr pickup (not an `fr run` read-only command), and reshape removes the drift it trips on; listed in Non-goals.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-05-run-upgrade-midflight-p2 created=2026-10-05T21:11:34+00:00 -->
### phase-split-2026-10-05-run-upgrade-midflight-p2 · decision · ask: historical review evidence (R7-R9) is its own reviewable ask, and changes the review gate

Phase 2 serves R7-R9, an ask independent of reshape.
