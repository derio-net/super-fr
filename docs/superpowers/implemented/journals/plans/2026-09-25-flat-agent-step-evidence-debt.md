# Journal: 2026-09-25-flat-agent-step-evidence-debt

<!-- fr:journal kind=discovery scope=plan id=root-cause created=2026-09-24T22:58:18 phase=1 -->
### root-cause · discovery · Flat-step state is on StepRecord (phase 1)

`units.unit_state(record, "step/<id>")` returns None by design; flat agent completion lives on the parent StepRecord.state. Evidence remains stored on the unit.

<!-- fr:journal kind=review scope=plan id=phase-1-review created=2026-09-24T23:00:29 phase=1 -->
### phase-1-review · review · Phase 1 implementation review (phase 1)

Separate-context review found one in-scope test-fixture issue: the complete-evidence test used a fixed timestamp earlier than the step dispatch, so evidence verification correctly rejected it. Changed the review entry to use the step's recorded `at`; all focused evidence tests now pass (82 passed). No other findings.

<!-- fr:journal kind=review scope=plan id=phase-1-review-complete created=2026-09-24T23:04:06 phase=1 -->
### phase-1-review-complete · review · Phase 1 implementation review (phase 1)

Independent review and receiving review completed. Reviewer confirmed the parent StepRecord state source for flat units, unit-local state for grouped members, and regression coverage for status/check debt and satisfied evidence. The timestamp fixture finding was fixed; no remaining findings.
