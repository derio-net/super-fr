# Journal: 2026-09-20-unit-record-unification

<!-- fr:journal kind=decision scope=spec id=u1 created=2026-09-20T19:51:55 -->
### u1 · decision · The dispatch record is what witnesses a held unit

gh#508 read the DispatchRecord; gh#519 read items/state. They disagree exactly where it matters: claim --abandoned closes the record and deliberately leaves items at running, so #519's refusal never lifts and a lost executor can never be re-briefed. Operator chose the record: a unit is held iff its last DispatchRecord is open. A cursor adopted from disk has no record, and there the refusal falls back to 'ALREADY RUNNING (dispatched <ts>)' — already built and tested. Consequence: run-dispatch-abandon survives; #519's run-advance-refuses-running is re-worded to the same claim rather than kept as a second row for one behaviour.

<!-- fr:journal kind=decision scope=spec id=u2 created=2026-09-20T19:51:55 -->
### u2 · decision · ALL of PhaseAccounting moves onto the DispatchRecord — estimate and measurement both per attempt

Operator chose the fuller option over 'measurement per attempt, estimate per unit'. Today dispatch[unit] APPENDS while accounting[unit] ASSIGNS, and gh#519's own test confirms a redispatch refreshes the snapshot — so a redispatched unit keeps the abandoned agent's identity and discards its cost. _with_measurement's docstring states the broken assumption outright ('serial dispatch makes that window hold exactly one dispatch'), which --redispatch violates. #464's goal, attributing spend to a dispatch, was defeated by a feature #508 added. Per-attempt for both halves is also the truer model: a re-dispatched unit re-assembles its context, so it has its own estimate too. RunState.accounting disappears.

<!-- fr:journal kind=decision scope=spec id=u3 created=2026-09-20T19:51:55 -->
### u3 · decision · Review folds into the unit record; gh#517 is folded in the way gh#519 was

The alternative was for the cursor to READ #517's journal reviews, preserving fr/run/model.py's documented control-log/content-log split. Operator chose full unification: the cursor records who held a unit, what it cost, and that it was reviewed. That crosses the documented split deliberately, so the spec restates the line: an obligation's SATISFACTION is control and lives on the cursor; its CONTENT stays in the journal. Means merging feat/journal-require-reviews into this branch and reconciling its journal-based --require-reviews gate with a cursor-based one — the third branch absorbed.

<!-- fr:journal kind=decision scope=spec id=u4 created=2026-09-20T19:51:56 -->
### u4 · decision · Go straight to the UnitRecord collapse — items, dispatch and accounting become one map

Rejected the staged option. One map, one home, one key space, no intermediate migration; everything that reads StepRecord.items is rewritten. The justification is the day's own drift record: three branches touched this structure and produced two schema_version 3s, two #499 refusals and two cost cardinalities. An intermediate shape is one more thing for a fourth branch to diverge from.

<!-- fr:journal kind=decision scope=spec id=u5 created=2026-09-20T19:51:56 -->
### u5 · decision · gh#518 is absorbed, but only its artifact half

It names the same witness — 'a run that stalled and a run that is working look identical from outside' is answered by an OPEN dispatch with a timestamp and nothing returned, which fr run check can report as 'held N minutes'. No new record, only a reading. NOT absorbed: #518's other two causes — the loop's cadence ending on a subagent report, and output style competing with the skill's autonomy contract. Those are prose in fr-goal sections 5-6, and the spec says so rather than implying a record fixes a reflex. Noted honestly: this session runs in explanatory style, #518's own cause 3, and stopped to report at checkpoints that were not all operator gates.
