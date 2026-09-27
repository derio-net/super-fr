# Journal: 2026-09-27-resolve-gate-side-effects

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-27T09:43:46+00:00 -->
### repro · repro · resolve: done without declared emits; cli gate loses unobserved; gate journal entry orphaned on refusal

Three members of one surface (fr run resolve's flag path, commands/run_cmd.py). #587: `resolve --step brainstorm --state done` with no --emitted is accepted and records emitted: None although the step declares emits [spec, …]. #632: clearing a gate on a kind: cli step on an unobservable harness prints unobserved=operator-gate but the cli branch never calls _take_unobserved(), so the cursor never carries it. #690: _gate_provenance appends gate-no-questions-<step> / gate-question-rounds-<step> to the spec journal at decision time; a later refusal (_verified_evidence, _deliver_pr_gate) exits 2 and _commits_run_writes still commits the noted journal path (flag path has no ResolveGuard).
