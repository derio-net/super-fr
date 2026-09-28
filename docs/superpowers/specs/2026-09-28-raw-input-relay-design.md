# Raw-input relay — implement-phase and review-phase see the verbatim input

**Status:** draft · **Issue:** super-fr#778 (batch `raw-input-relay-2`) ·
**Spec journal:** `docs/superpowers/journals/specs/2026-09-28-raw-input-relay.md`

## Background

The requirements-traceability change (#759, archived spec
`implemented/specs/2026-09-28-requirements-traceability-design.md`) made the
spec the carrier of requirements: the operator's raw input is recorded verbatim
as a spec-journal `input` entry, the spec's `## Requirements` table quotes it,
and spec review proves the input is partitioned into requirements. Its decision
`d0-spec-is-the-carrier` deliberately did **not** send the input any further
downstream.

Take 9 of the super-fr-3 feature-C recording (fr 4.29.2) measured what that
costs. The phase executor and the code reviewer saw the brief only through the
requirement text: 0 hits in their sessions for brief phrases such as "Business
rules", "680–720" or "same style". Coverage is checked; fidelity is not
(`check_coverage`'s own docstring, `packages/fr/src/fr/requirements.py:446`,
and #773). A clause that survives only inside a requirement's Source quote is
invisible to the two agents that build and check the feature, because they act
on the requirement text.

This change gives the last two hops a way to catch what the relay lost. It
reverses the *dispatch* half of `d0-spec-is-the-carrier` and keeps its core:
**the spec still governs.** The input rides along as a read-only reference, not
as a second source of truth. #773 (clause fidelity at spec review) is the fix
upstream of this one and stays a separate change.

## Requirements

| id | requirement | source |
|---|---|---|
| R1 | Every `implement-phase` and `review-phase` dispatch brief carries the spec journal's input entries, verbatim, as a read-only reference beside the spec and plan. | input "The dispatch briefs for `implement-phase` and `review-phase` attach that verbatim input entry"<br>input "as a read-only reference next to the spec and plan" |
| R2 | The same briefs carry the operator's recorded answers: every `decision` entry of the run's spec journal, verbatim. | input "(plus the operator's recorded answers)"<br>decision d2-all-spec-decisions |
| R3 | The briefs state one rule: the spec governs; where the raw input says something the spec does not, it is reported as a finding, never silently implemented or ignored. | input "the spec governs; when the raw input says something the spec doesn't, report it as a finding rather than silently implement or ignore it." |
| R4 | The per-phase journal handoff (`fr journal handoff --phase N`) carries the same input, answers and rule, so an executor that composes its own handoff reads them even when the orchestrator's relay drops them. | decision d1-brief-and-handoff |
| R5 | fr-goal relays the brief's input, answers and rule verbatim into both the phase executor's and the phase reviewer's prompts. | input "executor and reviewer see the brief only through the spec"<br>decision d1-brief-and-handoff |
| R6 | A statement of the input that neither the spec nor a recorded answer covers is an ordinary plan-journal finding against that phase, id prefixed `input-`, in scope, and gates that phase's review until resolved; an answer that overrides the input is not a finding. | decision d3-ordinary-gated-finding |

## Design

### A. One source: `fr.operator_input`

A new pure module `packages/fr/src/fr/operator_input.py` owns everything the
relay says, so the brief, the handoff and the prose cannot drift apart
(the `fr.harness.long_commands` precedent, gh#582):

- `OPERATOR_INPUT_RULE: str` — the rule, one constant:

  > Read-only reference: the operator's raw input and recorded answers,
  > verbatim. The spec governs — build and review against the spec, never
  > against this text. Where the raw input says something that neither the
  > spec nor a recorded answer covers, do not silently implement it or ignore
  > it: record a `finding` against this phase whose id starts `input-`, with
  > `review_scope: in`, quoting the input and naming what the spec says
  > instead. A recorded answer that overrides the input is the spec working as
  > intended, not a finding.

- `OperatorInput` — a frozen dataclass: `inputs` and `decisions`, each a tuple
  of `(id, title, body)`, in journal order.
- `from_entries(entries) -> OperatorInput | None` — pure: the entries with
  `is_input_entry` (`fr.requirements`) and the `kind == "decision"` entries;
  `None` when there is no input entry (a run whose spec predates the input
  gate — there is nothing to relay, and a dispatch is never refused for it).
- `load(repo_root, spec_rel) -> OperatorInput | None` — resolves the spec
  journal (`spec_journal_slug`, `resolve_journal_read_path`, so an archived
  journal still resolves); a missing journal is `None`; a journal that fails
  to parse raises (fail-closed — silently dropping the input is the defect).
- `to_brief(oi) -> dict` — `{"rule", "input": [{id, title, body}],
  "decisions": [{id, title, body}]}`.
- `to_markdown(oi) -> str` — a `## Operator input (read-only — the spec
  governs)` section: the rule, each input entry under `### <id> — <title>`
  with its body verbatim, then `### Recorded answers` with each decision under
  `#### <id> — <title>` and its body verbatim.

### B. The member brief (R1–R3)

`_build_member_brief` (`packages/fr/src/fr/commands/run_cmd.py:2854`) gains an
`operator_input` key, the `to_brief` payload or `null`. It stays pure: the
caller (`_advance_group`, via `_print_member_dispatch`) loads it once with
`run_spec(state)` and passes it in. It rides every member brief of the group —
in the shipped `fr-goal` shape those are exactly `implement-phase` and
`review-phase`; a repo-override shape with other members gets it too, which is
harmless and keeps one rule rather than a member-id list that drifts with the
manifest. The flat/group brief (`_build_brief`) is untouched: the phase hops
are the ones #778 names.

### C. The handoff (R4)

`fr journal handoff --scope plan --phase N` already parses the plan; the plan's
`spec_path` (resolved by `fr.parser.parse`) names the spec. The command loads
`operator_input.load(root, spec_path)` and passes the rendered section to
`compose_handoff` through a new keyword `operator_input: str | None = None`
(the function stays pure). The section renders **first**, before open
findings: it is the text take 9 showed nobody reading. No spec, a cross-repo
spec, or no input entry → no section, exactly as today. An unparseable spec
journal → exit 2, like every other handoff input.

### D. The prose (R5, R6)

- `plugins/super-fr/skills/fr-goal/SKILL.md` §5: copy the brief's
  `operator_input` VERBATIM into the executor's task prompt, beside the
  `long_commands` rule. §6: copy the same into the reviewer's prompt; the
  reviewer applies the rule and tags an input finding in scope; the
  orchestrator resolves an `input-` finding like any finding (fixed = spec
  amended and built, refuted = a recorded answer covers it, deferred =
  tracked). `null` → nothing to relay.
- `plugins/super-fr/agents/fr-phase-executor.md` "Inputs": the operator input
  and its rule, and that it is also the first section of the handoff.
- Regenerate the OpenCode and Hermes mirrors (`sync-opencode.py`,
  `sync-hermes.py`).

### E. The acceptance row this contradicts

`requirements-input-in-spec-journal` (ci) says the input "never reaches a phase
executor's handoff". No test pins that clause (it held because the handoff read
only the plan journal). This PR rewords the row to its surviving claim — the
input is recorded verbatim in the spec journal — and regenerates the reports.

### Non-goals

- **No relay verification** (`d4-no-relay-check`): fr does not read the
  dispatched agent's transcript to prove the input reached it.
- **No post-merge live row** (`d5-unit-tests-suffice`): unit tests on the brief,
  the handoff and the prose are the evidence.
- No journal schema change: an `input-` finding is an ordinary finding; the
  prefix is a naming convention, not a field. No artifact kind changes shape.
- Clause fidelity at spec review is #773.

## Test Plan

Unit, in CI:

1. A grouped advance prints `implement-phase` and `review-phase` briefs whose
   `operator_input` carries every input entry and every spec decision verbatim
   plus `OPERATOR_INPUT_RULE`; a spec journal with no input entry gives `null`.
2. `fr journal handoff` renders the operator-input section first, verbatim, for
   a plan whose spec journal has an input; omits it with no spec or no input;
   exits 2 on an unparseable spec journal.
3. `compose_handoff` with `operator_input=None` is byte-identical to today.
4. A prose tripwire: the fr-goal skill names `operator_input` in §5 and §6,
   and the phase-executor agent file carries the rule's load-bearing tokens
   (`the spec governs`, `input-`).
