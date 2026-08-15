# Journal: 2026-08-14-workflow-shapes-and-workitem-dispatch

<!-- fr:journal kind=finding scope=plan id=pr1 created=2026-08-15T17:03:10 state=fixed -->
### pr1 · finding [fixed] · Plan omitted the spec's no-PR-shape mitigation

Spec section 6 lists 'shapes that emit no PR' as a risk with the mitigation 'pinned by a test shape that emits only a document'. The 11-phase plan covered sections 4.A-4.H and 5 but implemented no such test. Added Phase 8 task 3 (P8.T3.S1/S2): a fixture manifest emitting only a report, asserted through check_workflow, build_items and tick, kept permanently under tests/fixtures/workflows/. Found by reading the phases back against the spec, not by self-review - self-review validates acceptance-id linkage and agentic purity, not spec coverage.
