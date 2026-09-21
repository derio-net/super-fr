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

<!-- fr:journal kind=review scope=spec id=v1 created=2026-09-20T21:42:14 -->
### v1 · review · Operator review: the cost design had no answer for stop, push, pick up on another host

gh#514's measure_unit locates the transcript from the CURRENT process environment, so measurement is session-local even on one host, and the agent-id lookup the spec proposed inherited that. Worse, the time-window fallback can mis-attribute across sessions: host B resolving host A's open attempt can find exactly one unrelated subagent of its own in the window. Fixed: Attempt.session, derived by fr at open; lookup by (session, agent) in the RECORDED session's directory; window fallback only when the attempt's session is the current one; otherwise 'not observable from here'. No hostname recorded — a missing session directory already says 'elsewhere'. New section 4.D.1 spells out what the second host sees and how it recovers.

<!-- fr:journal kind=review scope=spec id=v2 created=2026-09-20T21:42:15 -->
### v2 · review · Operator review: 'OpenCode and Hermes have no Stop hook' was asserted, not checked

The same error gh#494 documents — a parity row declared absent for a reason that did not survive the binary. The operator supplied a survey of stop-like hooks; treated as a lead, not a fact, and checked where possible on the authoring machine: OpenCode 1.18.31 has session.idle in its SDK types and a prompt_async endpoint (so: re-prompt tier, cannot block); Copilot CLI 1.0.84 has a hooks system with a user hook already installed (blocking semantics unverified); Codex, Hermes and Agy are not installed and stay unverified. Redesigned as one harness-neutral predicate (fr run check --idle) plus adapters as strong as each harness allows: block on Claude Code, re-prompt on OpenCode (partial until live-proven), absent-with-note on Hermes. The survey's note that one harness caps consecutive continuations exposed a missing loop breaker: the guard now acts at most once per cursor position.

<!-- fr:journal kind=decision scope=spec id=u6 created=2026-09-21T08:34:15 -->
### u6 · decision · u6: name both review skills and enforce a derived findings obligation; block literals in this PR

Operator review of PR #508, two inline comments, answered through a two-question batch.

1. On the shipped review-phase member: "I would expect another element here, invoking superpowers:receiving-code-review. Is it being left at the implementing agent's discretion?" It was. Offered three readings: (a) name both skills AND add an enforceable findings obligation, (b) a third member step, (c) only name the second skill. Operator chose (a). (b) was rejected for drift: a new member id strands every fr-goal cursor in flight. (c) was rejected as still discretionary.

2. On a run cursor's stdout scalar: "is this valid yaml?" It is, but it looks broken. Offered: block literals now, leave it, or a follow-up issue. Operator chose block literals in this PR.

Spec section 4.E.1 records the design.
