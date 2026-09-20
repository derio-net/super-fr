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

<!-- fr:journal kind=review scope=spec id=r1 created=2026-09-20T15:12:24 -->
### r1 · review · spec-review: the completion predicate, and two numbers that were wrong

Reviewed the spec against the Q&A answers and against the code it names.

**r1-f1 (would have shipped a no-op).** The spec said a phase is owed a review when `state.completion.at` is set — the issue's literal wording. `fr/render.py` already carries two completion predicates, and the richer one, `_phase_complete`, requires an observed MERGED PR for agentic phases. fr-goal opens one PR per plan at `deliver`, after this gate runs, so a gate built on that predicate would pass every plan forever while looking like it worked. Fixed: the gate reuses `plan_locally_complete` (completion.at set OR all steps ticked, no gh observation), which spec.py, diff.py and archive.py already share, and whose docstring names its purpose as the predicate for surfaces running before any Issue exists. Deliberately wider than the issue asked: a phase with every step ticked and no completion.at still claims to be done.

**r1-f2 (wrong numbers).** D2 cited '35 review entries, only 8 with phase=', conflating scopes — 35 counts spec- and plan-scope together while 8 counts plan-scope only. Actual: 13 plan-scope review entries, 8 of them phased. Fixed.

**Verified as stated:** `review` is already in JournalKind and `phase` already optional on JournalEntry (no schema change, no stamp bump owed); `fr journal handoff` already has --plan-dir with the default the spec reuses; PhaseHeader.tag is Literal[agentic,manual]; _check_step_drift is at run_cmd.py:258 and refuses on a changed step set; `needs` is legal on a kind:cli Step; `plan` is in REPO_TRACKED_ARTIFACTS so needs:[plan] is in-vocabulary; this repo has no docs/superpowers/workflows/ override, so the shipped manifest is the one that resolves; `fr run adopt --run-id` exists as the drift recovery.
