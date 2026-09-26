# Brainstorm questions: sized to the feature, with an optional announced second round

- **Date:** 2026-09-26
- **Status:** designed
- **Origin:** operator request, 2026-09-26: fr-goal's opening Q&A is capped at
  four questions, which is too few for large features and for fr-triage batches
- **Goal:** fr-goal's brainstorm asks as many questions as the feature has
  operator-owned decisions. When the first round's answers could reshape the
  design, it may ask a second round, but only one it announced beforehand (or
  one the operator asked for), and fr checks the declaration against the
  transcript.

## 1. Problem

1. **The cap is a number in prose, not a property of the feature.**
   `plugins/super-fr/skills/fr-goal/SKILL.md:49` says "ONE batch (max 4,
   recommended first)". The explainer repeats it
   (`docs/explainers/01-fr-goal.md:499`, "no more than four questions"), and so
   does the README (`README.md:118`, "operator answers ≤4 questions"). No code
   enforces it. The gate (`fr.commands.run_cmd._gate_provenance`,
   `run_cmd.py:938`) only checks that *some* question was answered after the
   gate blocked (`fr.run.telemetry.operator_answered_since`,
   `telemetry.py:450`). The limit exists to stop agents dripping questions out
   one at a time, but it also forces a large goal to leave real decisions
   unasked. An fr-triage batch (`fr triage batch dispatch`, whose brief is
   `/fr-goal <title>` plus N issues, `fr/triage/batch_dispatch.py:60`) has at
   least as many decisions as it has issues. With the cap, the agent defaults
   the rest, and the spec records the agent's guesses as if they were the
   operator's decisions.
2. **Nothing exists between "ask once" and "drip".** Sometimes a round-1
   answer changes the design enough that new operator-owned questions appear:
   the operator picks approach B, and B has two sub-decisions A never had.
   Today the agent either guesses those or breaks the single-batch rule without
   saying so. The gate lets the second batch through without recording it, so
   nobody knows a second round happened, least of all the operator, who was
   told there would be only one.

## 2. Decisions (operator, 2026-09-26)

| # | Question | Answer |
|---|---|---|
| D1 | Enforcement | **Prose + record check.** The brainstorm step record declares its question rounds, and `fr run resolve` verifies the declaration against the session transcript where it can read one. |
| D2 | Sizing | **One question per decision, with a soft ceiling.** No numeric cap. One question per real operator-owned decision, sized to the feature. Above about 10, the agent says why in the batch or proposes splitting the goal. |
| D3 | Round 2 content | **Only what round 1 opened.** A round-2 question exists only because of a round-1 answer, or because checking that answer against the code turned something up. Each round-2 question names that cause. There is never a round 3. |

The operator's request settles two more points:

- **Round 2 has two triggers.** (a) *design-risk*: before round 1, the agent
  judges that its answers may change the design significantly. (b)
  *operator-request*: during round 1, the operator asks for a second round in
  prose, either in an answer's notes or in "Other".
- **The operator knows before round 1 ends.** Under *design-risk*, round 1 is
  announced as "Round 1 of 2". Otherwise it is "Round 1 of 1", and the
  announcement tells the operator how to ask for a second round.

## 3. Design

### 3.A Prose: sizing and rounds (fr-goal §1, fr-brainstorming §1)

fr-goal §1 changes from "ONE batch (max 4, recommended first)" to the
following rules:

- **Size the batch to the decisions.** Ask one question per operator-owned
  decision, recommended option first, and leave out anything the code
  answers. For more than about 10 questions, say why in the batch text or
  propose splitting the goal. A long batch is a sign the goal should be
  split, not a limit to squeeze under.
- **Announce the round count up front.** Before the first question, decide
  whether round 1's answers could change the design significantly (a choice
  between approaches whose sub-decisions differ, or an unknown the code cannot
  settle). Every round-1 question text starts with `(Round 1 of 2)` or
  `(Round 1 of 1)`. With `of 1`, say that a second round is available on
  request.
- **Round 2 only asks what round 1 opened.** After round 1, check every answer
  against the code (the "cross-examination") before asking round 2. Each
  round-2 question starts `(Round 2 of 2)` and names the round-1 answer or the
  code finding behind it. There is never a round 3.
- **On Claude Code, a round can span several calls.** `AskUserQuestion` takes
  at most 4 questions per call, so a round of N questions is `ceil(N/4)`
  consecutive calls **with no other tool call between them**. A tool call
  between two question calls is what separates rounds (§3.C). Other harnesses
  number the whole round in one reply.

fr-brainstorming §1's "ask ONCE" becomes "one gate, at most two rounds, per
fr-goal §1". Its standalone mode stays fully interactive and is unchanged.

- **The hard gate holds for each round.** An unanswered round is a stop
  signal. After an answered round 1 of 2, do the cross-examination and ask
  round 2 in the same turn, then STOP again. Resolve `brainstorm` only after
  the last announced round is answered. An operator's prose request for a
  second round during round 1 turns a `1 of 1` into `rounds: 2`,
  `trigger: operator-request`.

### 3.A.1 The fr-goal contract changes, and every place that states it changes with it

fr-goal's promise used to be **one operator touchpoint = one batched Q&A of
at most four questions**. It becomes **one operator gate = one question
round sized to the feature, or two when the second is announced before
round 1 ends or the operator asks for it**. It is still one gate: the cursor
blocks once, and `brainstorm` resolves once. The explainer's "Yes, once" now
means the gate, not the number of question turns. Each surface below states
the old contract and is rewritten to the new one in this PR:

| Surface | Current wording |
|---|---|
| `fr-goal/SKILL.md:5` (frontmatter `description`, the trigger text) | "brainstorm, one batched Q&A, then …" |
| `fr-goal/SKILL.md:14` (opening sentence) | "One operator touchpoint — the batched Q&A —" |
| `fr-goal/SKILL.md:42` (interactive touchpoints) | "`brainstorm`'s batched Q&A" |
| `fr-goal/SKILL.md:46-62` (§1 heading, body and the "Harness — questions" clause at :58) | "batched Q&A", "ONE batch (max 4 …)", "one `AskUserQuestion` call" |
| `fr-brainstorming/SKILL.md:64` | "ask ONCE" |
| `docs/explainers/01-fr-goal.md:10,120,191,494,499,508,513,901,941` (+ `.html`) | "one round of questions", "ask once", "no more than four questions", "Yes, once", "One batched Q&A", "one consolidated question set" |
| `README.md:108,118,139` | "one batched round", "≤4 questions", "the batched Q&A" |

The trigger phrase "ask your questions once then build it" in
`plugins/super-fr/rules/fr-plan-override.md` stays. It is how an operator
asks for fr-goal, not a statement of the contract. The OpenCode and Hermes
mirrors follow the canonical skills through both sync scripts. A prose
tripwire (Test Plan 6) pins the new contract on the canonical skill and both
mirrors, so the old wording cannot come back unnoticed.

### 3.B The record declares its rounds: the `questions` section

`fr.record.model.StepRecord` gains one optional field:

```yaml
questions:
  rounds: 2                 # 1 | 2  (absent ≡ rounds: 1)
  trigger: design-risk      # design-risk | operator-request — required iff rounds: 2
  reason: "B vs C changes which store owns the cursor"   # required iff rounds: 2
```

- The model is `QuestionRounds`, frozen and `extra="forbid"`. `rounds` is
  `Literal[1, 2]`, so a round 3 cannot be written down at all. `trigger` and
  `reason` are required when `rounds == 2` and forbidden when `rounds == 1`.
- `questions` belongs to the `outcome` section in `_SECTION_FIELDS`, next to
  `no_questions`/`reason`. It is mutually exclusive with `no_questions: true`,
  and the model refuses both together. It applies only to a resolve that
  clears an operator gate: `run_cmd._clears_gate`, the same refusal
  `--no-questions` gets (`run_cmd.py:3956`).
- The flag form gets parity for humans and runners: `--question-rounds
  1|2`, `--round-two-trigger`, `--round-two-reason`. With `--record` they are
  refused, like the other record-carried flags (`run_cmd.py:3759`).
- **Threading the declaration to the gate** (review s1). Two classes are
  both called `StepRecord`. The new field lives on `fr.record.model.StepRecord`,
  the step-record *artifact*. `_gate_provenance`'s `record` parameter is
  `fr.run.model.StepRecord`, the *cursor's* per-step state
  (`run_cmd.py:66-73`), which never sees it. So the declaration goes in as an
  explicit `questions: QuestionRounds | None` parameter along the path
  `no_questions`/`reason` already use: `apply_record`
  (`record/apply.py:855-867`) → `run_cmd.resolve_in_process`
  (`run_cmd.py:4166`) → `_resolve_body` (`run_cmd.py:3843`) →
  `_gate_provenance` (`run_cmd.py:933`). The flag form builds the same
  `QuestionRounds` from its three flags, so both paths call the gate with one
  value.
- `fr.record.template.render_template` puts a commented `questions:` hint in
  the template of any gated step. It also stops hardcoding
  `"schema_version: 1"` (`template.py:54`) and writes
  `RECORD_SCHEMA_VERSION` (review s2). Otherwise the bump would make every
  freshly rendered template fail its own parse ("schema_version 1 — this fr
  reads record version 2") for every dispatched step of every run. Test Plan
  item 5 pins that a rendered template parses.
- **Artifact versioning** (`.claude/rules/artifact-versioning.md`): the new
  field changes the shape of the `record` kind, because fr 4.24.1 reads records
  and `StepRecord` is `extra="forbid"`. So: `record` goes from
  `current_version` 1 to 2 in `fr.artifacts.registry`; `RECORD_SCHEMA_VERSION`
  becomes 2; a **stamp-only** `SchemaMigration` 1 → 2 (`fr.artifacts.record_questions`,
  imported by `fr/artifacts/__init__.py`) parses first and refuses a record it
  cannot read, the same guard pattern as `run_provenance.py`. The existing
  `validate_record` structure validator covers the new field through the
  model. No field is removed or moved, so nothing needs freezing.

### 3.C fr checks the declaration against the transcript

`fr.run.telemetry` gains `answered_rounds_since(env, since) -> list[Round] |
None`, a sibling of `operator_answered_since` that reads the same records. It
returns `None` exactly where that function does (another harness, no session,
no transcript).

- **A round** is a maximal run of main-thread (non-sidechain) `QUESTION_TOOL`
  tool_uses stamped at or after `since`, with **no other tool_use between
  them**. Text-only assistant turns and the question calls' own tool_results do
  not break a round. A round **counts** when at least one of its calls was
  answered (`toolUseResult.answers` non-empty, the rule
  `operator_answered_since` already uses). A round that was only declined does
  not count.
- Each `Round` carries its question texts, so the announcement can be checked.

`_gate_provenance` (declared = `questions.rounds`, default 1) then works like
this:

| Observed | Declared | Verdict |
|---|---|---|
| 0 answered rounds | any | existing refusal (unchanged) |
| n == declared | 1 | `operator` |
| n == declared == 2, trigger `design-risk` | 2 | `operator` only if some round-1 question text contains `Round 1 of 2` (case-insensitive); otherwise refused: "the operator was not told a second round would follow" |
| n == declared == 2, trigger `operator-request` | 2 | `operator` (the request is in the operator's own answer, which fr does not parse) |
| n ≠ declared, n ≤ 2 | | **refused**, naming both numbers and the fix: declare `questions: {rounds: 2, …}`, or the transcript shows only one round |
| n > 2 | | **refused**: "there is never a round 3" |

- Every refusal happens **before** a byte moves, like the existing gate
  refusals.
- Not observable (OpenCode, Hermes, unreadable transcript): the declaration is
  recorded as claimed, and the existing unverified notice mentions it.
- A cleared gate with `rounds: 2` appends a spec-journal `decision`,
  `gate-question-rounds-<step>` ("Operator gate `<step>` took two question
  rounds", body = trigger + reason). It goes to the same journal and follows
  the same idempotence rule as the `gate-no-questions-<step>` entry
  (`run_cmd.py:1000`), so the PR body shows the second round without a change
  to the `run` kind. `rounds: 1` writes nothing, because it is the default.

### 3.D What does not change

- The shape of the `run` cursor (`answered_by` is still the only gate
  provenance field on it).
- The `fr-goal.yaml` manifest: no new step and no new evidence name, so
  in-flight cursors do not drift.
- The `--no-questions` bypass, and every harness's existing
  `operator_answered_since` semantics.

## 4. Rollout (the PR that ships this)

- A change fragment `.changes/feat-dynamic-brainstorm-questions.yaml`,
  `bump: minor` (a new mandatory behaviour on the gate).
- Regenerate the mirrors: `scripts/sync-opencode.py` **and**
  `scripts/sync-hermes.py`.
- Update `docs/explainers/01-fr-goal.md` and regenerate its `.html` with the
  documented `--isolated` render, after a byte-identical re-render of the
  unmodified page. Fix `README.md:108,118`.
- Run `fr migrate artifacts --yes` in this worktree after the stamp bump, and
  commit whatever it migrates (live records under `docs/superpowers/runs/*.records/`).
- Add the acceptance-matrix rows from the brainstorm record (§7).

## 5. Error handling

- A malformed `questions` block → `RecordError` at parse time, naming the
  field. Nothing is applied.
- `questions` on a resolve that clears no gate → exit 2, same wording family
  as `--no-questions`.
- An unreadable transcript never refuses; it degrades loudly, the posture
  the gate already has.

## 6. Non-goals

- Counting questions or enforcing the soft ceiling in code. D2 makes it
  prose only.
- Parsing the operator's answer text to verify an `operator-request` trigger.
- Changing standalone fr-brainstorming, fr-debugging, or any shape other
  than a step with `gate: operator`. The check is generic over gated steps,
  though, not specific to fr-goal.
- A round 3, ever.

## 7. Test Plan

Unit level (CI):

1. `answered_rounds_since` over captured-shape transcript fixtures: one round
   of one call; one round of two consecutive calls (a batch of more than 4);
   two rounds separated by a `Bash`/`Read` tool_use; a declined-only round
   (not counted); sidechain question calls (ignored); questions before `since`
   (ignored); a non-Claude harness (`None`).
2. `QuestionRounds` model: `rounds: 3` refused; `rounds: 2` without
   trigger/reason refused; `rounds: 1` with a trigger refused; together with
   `no_questions: true` refused.
3. The gate table in §3.C, row by row, through `fr run resolve --record`
   (the path fr-goal uses) and the flag form: each refusal leaves the cursor
   and the record byte-identical.
4. `rounds: 2` writes exactly one `gate-question-rounds-<step>` decision, and
   writes it only once on a retry.
5. Record kind migration 1 → 2: a v1 record is stamped 2; an unreadable one is
   refused and left untouched; the `record` kind reaches version 2
   (`fr validate artifacts` over this repo stays green); and a template from
   `render_template` for every step of the shipped fr-goal manifest parses
   under the live `RECORD_SCHEMA_VERSION` (review s2).
7. The declaration reaches the gate on BOTH paths: a `--record` resolve and a
   flag resolve that declare `rounds: 2` against a one-round transcript are
   each refused (review s1). A test that only exercises the flags would pass
   while the `--record` path, the one fr-goal uses, never saw the value.
6. Contract-prose tripwire: on every §3.A.1 surface, the old contract
   ("max 4", "≤4 questions", "ONE batch", "one batched Q&A") is gone. The
   canonical fr-goal skill and both generated mirrors state the new contract:
   one gate, sizing per decision, the `Round 1 of N` announcement, round 2
   only what round 1 opened, never a round 3. It is a small grep test in the
   style of the existing skill-prose tripwires.

Post-merge (operator-driven, not blocking): run `/fr-goal` on a goal that
has more than 4 decisions and confirm that one round spans several
`AskUserQuestion` calls and resolves. Then run one with a design-risk second
round and confirm that the brainstorm resolve records the
`gate-question-rounds-brainstorm` decision.
