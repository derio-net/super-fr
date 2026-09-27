# Journal: 2026-09-27-triage-batch-launch

<!-- fr:journal kind=decision scope=spec id=d1-no-subagent-override created=2026-09-27T09:03:06 -->
### d1-no-subagent-override · decision · No subagent-model override of any kind; the brief is silent on subagent models

Operator chose "No override" over an opt-in --subagent-model or a per-tier map. fr-goal/fr-debugging resolve each subagent's tier through `fr models` (repo override > user); a repo wanting other tier models sets docs/superpowers/models.yaml, not the batch.

<!-- fr:journal kind=decision scope=spec id=d2-harness-alias created=2026-09-27T09:03:06 -->
### d2-harness-alias · decision · Map the runner's harness name to fr's harness id; refuse only when no model resolves

Operator chose a fixed alias table (claude -> claude-code, others as-is) over accepting both spellings or making batches spell fr ids. Session model = batch --model, else defaults.launch.model, else the orchestrator binding; all unset -> dispatch refuses and names the `fr models set ... --tier orchestrator` line.

<!-- fr:journal kind=decision scope=spec id=d3-theme-warning created=2026-09-27T09:03:06 -->
### d3-theme-warning · decision · One-root-cause warning on create and edit, never a refusal

Operator chose create + edit over create-only or also-at-dispatch. Fires when the resulting batch is skill debug and its members carry two or more distinct non-empty themes.
