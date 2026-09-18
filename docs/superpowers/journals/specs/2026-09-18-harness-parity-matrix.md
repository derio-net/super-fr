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

<!-- fr:journal kind=review scope=spec id=r1 created=2026-09-18T14:52:56 -->
### r1 · review · Spec review: five claims corrected against the code

1. Dropped the 'six tripwires assert byte-identity' overclaim — only test_tripwire_{opencode,hermes}_skills_sync do; the hermes hooks tripwire checks script existence, not mirror identity.
2. `FR_HARNESS` does not exist today; the spec now says it introduces it.
3. `fr run check` is currently a narrow freshness gate ('non-zero when the cursor sits on a failed step'). Reporting agent-cleared gates must NOT change its exit code — doing so would turn every legitimate non-interactive dispatch red, i.e. re-introduce the hard-refusal option the operator rejected. Now stated.
4. `status-line` corrected from absent to partial on opencode/hermes: `fr-statusline-segment.sh` already accepts `--cwd` as well as Claude status-line JSON, so it is harness-neutral today; only the renderer and its settings.json registration are Claude-specific.
5. `subagent-dispatch` row semantics were conflating the dispatch capability with the fr-phase-executor guard. Split and documented.
Verified as stated: `fr acceptance check` outside a repo prints a message and exits 0 (the 'decline cleanly' precedent §3.F cites); `fr.hermes.snippet_entries` exists; RunState/StepRecord are frozen + extra=forbid; the fr-goal manifest's `implement` declares needs: [spec, plan]; AskUserQuestion appears 6x across canonical + both mirrors.

<!-- fr:journal kind=decision scope=spec id=d5 created=2026-09-18T14:52:56 -->
### d5 · decision · Tool names go neutral at the canonical source; mirrors stay byte-identical

Agent-made call, not operator-owned, recorded because it rejects the approach #436 itself suggested. The issue proposes translating tool names at sync time; both sync scripts are byte-for-byte copies with tripwires asserting that identity, so translation forks one prose into three. The canonical prose goes neutral instead and a tripwire pins it, with an existing scoped-clause shape (fr-goal §5's '**Harness — dispatch:**') as the sanctioned escape.
