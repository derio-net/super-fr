# Journal: 2026-09-27-resolve-gate-side-effects

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-27T09:43:46+00:00 -->
### repro · repro · resolve: done without declared emits; cli gate loses unobserved; gate journal entry orphaned on refusal

Three members of one surface (fr run resolve's flag path, commands/run_cmd.py). #587: `resolve --step brainstorm --state done` with no --emitted is accepted and records emitted: None although the step declares emits [spec, …]. #632: clearing a gate on a kind: cli step on an unobservable harness prints unobserved=operator-gate but the cli branch never calls _take_unobserved(), so the cursor never carries it. #690: _gate_provenance appends gate-no-questions-<step> / gate-question-rounds-<step> to the spec journal at decision time; a later refusal (_verified_evidence, _deliver_pr_gate) exits 2 and _commits_run_writes still commits the noted journal path (flag path has no ResolveGuard).

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-09-27T09:43:49+00:00 -->
### root-cause · root-cause · Gate side effects run at decision time, before every refusal point and outside each branch's persistence point

_gate_provenance both DECIDES provenance and WRITES its consequences (journal append; unobserved note consumed only by the agent branch's persistence). So a write lands before later refusals (#690), the cli branch — which persists on its own path — never picks up the note (#632), and adding the missing declared-emits refusal (#587) after the gate would create a fresh orphan. Operator decision (2026-09-27): three distinct mechanisms, one unified fix in one PR — the gate decides and validates only; its journal writes are deferred and flushed immediately before each branch saves the cursor; the declared-emits refusal runs before the gate; done requires every --emitted-able emit (not journal:*, plan:ticks, acceptance), supplied now or already recorded.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-09-27T10:15:50+00:00 state=fixed -->
### fix · finding [fixed] · Gate writes deferred to each branch's save point; declared emits required at done; cli gate persists unobserved

run_cmd.py: _queue_gate_decision (eager check, deferred write) + _flush_gate_decisions right before _save_run_state in the cli-gate and agent branches (#690); _refuse_missing_emits via fr.workflow.artifacts.emitted_artifacts, after deliver's PR gate and in _resolve_member before any write (#587); cli branch folds _take_unobserved() onto the step/<id> unit (#632). Failing-test-first: tests/unit/test_run_resolve_gate_side_effects.py (3 red before, 4 green after). Ten test_run_cli fixtures that resolved done without their declared emits now name them.
