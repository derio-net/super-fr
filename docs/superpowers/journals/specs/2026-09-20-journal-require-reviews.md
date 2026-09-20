# Journal: 2026-09-20-journal-require-reviews

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-20T15:10:34 -->
### d1 · decision · The emit lives in super-fr skill prose, not a new wrapper skill or CLI verb

Operator-answered. `superpowers:requesting-code-review` is third-party and uneditable, so the issue's literal proposal has no target. `fr journal add --kind review --phase N` already writes the required entry; a `super-fr:fr-review` wrapper would add install.sh wiring, an OpenCode mirror, a parity row and a tool-neutrality scan to carry one sentence. Prose suffices BECAUSE d3 makes skipping it fail loudly.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-20T15:10:34 -->
### d2 · decision · --require-reviews is an opt-in flag, not default-on

Operator-answered, matching the issue's literal ask. This repo holds 35 review entries of which only 8 carry phase=, so default-on would fail live and archived plans over a convention never stated. The flag's weakness (someone must remember it) is closed by d3, not by breaking consumers.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-20T15:10:35 -->
### d3 · decision · The run cursor runs the gate: a kind:cli step in the shipped fr-goal manifest

Operator-answered. #430's thesis applied to its own fix — an obligation enforced by an instruction can be absorbed into the working context. Cost accepted: a new top-level step drifts every in-flight run via _check_step_drift (run_cmd.py:258), including the one delivering this change. Recovery is `fr run adopt <plan-dir> --run-id <fresh>`.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-09-20T15:10:35 -->
### d4 · decision · [manual] phases are exempt from the review requirement

Operator-answered. fr-goal back-loads manual work and ships it unimplemented for the operator to push; the operator is its reviewer. Requiring the orchestrator to review code it did not write is a gate that fails for the wrong reason. The exemption is named in the failure message so it is visible, not silent.
