# Journal: 2026-09-18-harness-parity-matrix

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-18T14:48:21 -->
### d1 · decision · Full scope: all six acceptance criteria land in this PR

Operator chose full scope over staging. Rationale accepted: a matrix without the derived tripwires is a stale doc (already demonstrated — the issue's own table lists Hermes as lacking `fr-acceptance-nag`, but `config.snippet.yaml` registers it on `pre_llm_call`), and the tool-name tripwire is what closes the AskUserQuestion leak.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-18T14:48:21 -->
### d2 · decision · Matrix lives in fr.harness with an `fr harness parity` CLI

packages/fr/src/fr/harness/parity.yaml, shipped in the wheel; `fr harness parity` renders, `--check` validates declared-vs-observed. Same reasoning that keeps workflow manifests un-mirrored: this is a CLI surface every harness drives identically, so it must work with no plugin installed. Rejected: docs/harness/parity.yaml test-only (invisible on a pod, cannot drive runtime degradation messages) and extending docs/acceptance/matrix.yaml (that registry is per-consumer-repo business claims, this is super-fr's own shipped wiring).

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-18T14:48:21 -->
### d3 · decision · Operator gate: provenance + loud degradation, not hard refusal

`fr run advance` prints a harness-aware notice when a `gate: operator` step blocks; `fr run resolve` records who cleared it; `fr run check` and the delivered PR body flag gates cleared without operator provenance. Explicitly honest: an agent can still clear a gate it never asked — the goal is that the clearing becomes visible and auditable rather than silent. Rejected hard refusal (TTY/FR_OPERATOR evidence) because it breaks every legitimate non-interactive dispatch — vibe-kanban, CI, pods — which is the same class of context the artifact-migration gate deliberately serves with one explicit step.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-09-18T14:48:21 -->
### d4 · decision · Tier bindings: mechanical+standard -> sonnet-5, hard -> opus-5

Operator declined haiku for mechanical phases. Written to ~/.config/fr/models.yaml under harness claude-code.
