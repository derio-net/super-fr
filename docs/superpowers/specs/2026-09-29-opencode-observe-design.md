# fr observes OpenCode sessions — the run's session, each dispatched child, and what the child returned

Batch `opencode-observe`: super-fr#823 (umbrella), #797, #809, #816. One run, one PR.

## Background

Every transcript gate `fr run resolve` applies reaches the harness through one
choke point, `fr.run.telemetry._this_session` (`packages/fr/src/fr/run/telemetry.py:573`),
which returns `None` on any harness but Claude Code. On OpenCode every gate
therefore degrades to "recorded as claimed, unverified": the operator gate
(`answered_rounds_since`, `:485`), the separate-context reviewer
(`subagent_dispatch_since`, `:585`), and the visual witness (`read_file_since`
`:842`, `shell_named_since` `:961`, via `run/visual.py:457`). The one gate that
does read OpenCode, `deliver`'s `tests=` (`_opencode_wrote_since`, `:1215`),
cannot pin THE run session either ("No OpenCode session id reaches fr's
environment", `:1227`), and `advance` records no session on an OpenCode attempt
by design (gh#537, `commands/run_cmd.py:2805`), so `fr.usage.capture.candidates`
(`usage/capture.py:96`) finds nothing and the PR's Cost table is all dashes.

Take 10 (#817, fr 4.35.0, OpenCode 1.18.32) showed what that lets through: a
re-cut coverage partition (#777), an invented reviewer id with `findings: none`
over six raised findings (#816), an operator gate recorded as `answered_by:
agent` although the operator answered through OpenCode's `question` tool (#809),
and every visual witness `unobserved` although opencode.db held the PNG reads (#797).

Verified on this host's live OpenCode 1.18.33 database (shapes only, read-only,
2026-09-29; no content copied):

- `session(id, parent_id, directory, agent, model, …)`; a `task` subagent is a
  child session (`parent_id` = its dispatcher).
- `part.data` of a `task` call: `state.input.{subagent_type, prompt, description}`,
  `state.metadata.{parentSessionId, sessionId, model}`, `state.time.{start,end}`,
  `state.status`, and `state.output` = `<task id="ses_…" state="completed"><task_result>…</task_result></task>`.
  The child's own last `text` part holds the same final message.
- `question`: `state.input.questions[].{question, header, options[].{label,description}}`;
  answered → `status: completed`, `state.metadata.answers: [[str]]`; declined →
  `status: error`, `error: "The user dismissed this question"`; a pending call
  is persisted as `status: running`.
- `read`: `state.input.filePath` (+ optional `offset`, `limit`).
- The OpenCode binary fires the plugin hook `shell.env` with
  `{cwd, sessionID, callID}` before every `bash` tool call and merges the
  returned `env` into the command's environment (present in the 1.18.33
  binary; typed in `@opencode-ai/plugin` 1.17.15's `Hooks`).

## Requirements

| id | requirement | source |
|---|---|---|
| R1 | On OpenCode, fr learns the run's session id from the super-fr plugin, which exports it into every shell command, and records it on the attempt `advance` opens. | input "On OpenCode, fr learns the run's session id and records it on the attempt at `advance`."<br>decision d-run-session |
| R2 | With the session known, `fr run cost`, the usage capture and the PR body's Cost table show the OpenCode run's real figures. | input "`fr run cost` and the PR's Cost table then show real numbers."<br>input "and cost (#636 discovery half) from opencode.db" |
| R3 | fr maps each dispatch to its child session through opencode.db's parent/child records, and records the child session id on the unit's attempt when no holder was claimed and exactly one matching child exists. | input "fr maps each agent dispatch to its child session through opencode.db's parent/child session records, and records the child's session id on the attempt." |
| R4 | Every transcript gate reads the harness through one harness-neutral session protocol, with a Claude Code backend and an OpenCode backend. | input "Readers already exist (_opencode_wrote_since, usage/readers/opencode.py)."<br>decision d-seam |
| R5 | At `spec-review`, fr reads the reviewer's own final message and refuses a recorded `input-coverage` block that differs from the one the reviewer returned, on every harness whose return fr can read. | input "At `spec-review`, fr reads the child's final assistant message and records its `input-coverage` block itself, or refuses a recorded block that differs from it."<br>decision d-coverage-refuse<br>decision d-every-harness |
| R6 | At `spec-review` and `review-phase`, a reviewer id that names no child session the run session dispatched since the unit opened is refused on OpenCode, as it already is on Claude Code. | input "fr supplies or verifies the reviewer identity (the dispatched child session in opencode.db), and refuses an id that matches no dispatched session."<br>input "At `review-phase`, the recorded reviewer id must be a dispatched child session" |
| R7 | The review-phase reviewer ends its return with a fenced `findings` block using ids fr's brief prescribes; fr refuses a review-phase resolve whose journal lacks any returned finding (for that phase, with the reviewer's scope tag), and refuses a missing block, wherever the return is observable. | input "and the record's findings must match what that session returned (#816)."<br>input "`findings: none` with a non-empty reviewer return is refused."<br>decision d-findings-block<br>decision d-finding-ids<br>decision d-every-harness |
| R8 | The PR body's findings sections list the review-phase findings and how each was resolved. | input "The PR body's Findings section includes the review-phase findings and how each was resolved." |
| R9 | fr reads answered `question` tool calls from opencode.db, grouped into rounds by the rule it applies to Claude Code, and the fr-goal skill and `parity.yaml` describe OpenCode's question tool. | input "fr reads answered `question` tool calls from opencode.db, the way it reads Claude Code transcripts."<br>input "The skill and `parity.yaml` describe the tool." |
| R10 | When fr cannot observe who answered an operator gate and neither the record nor the flags give `answered_by`, resolve refuses and names both values — on every harness; nothing defaults to `agent`. | input "When provenance can't be observed and the record gives no `answered_by`, resolve refuses instead of defaulting to `agent` (#809)."<br>decision d-answered-by-refuse |
| R11 | `fr run gates` and `fr run check` say a gate's provenance is claimed and unobserved, not "no operator answered it", when fr could not look. | input "`fr run gates` says "unobserved" rather than "no operator answered it" when it could not look." |
| R12 | On OpenCode the visual witness observes screenshot reads and capture-script runs, read from the session of whoever owes them (executor, reviewer or orchestrator), never from any other session. | input "`read_file_since` / `shell_named_since` gain an OpenCode branch, so visual-evidence checks 4 and 5 observe real screenshot reads (#797)."<br>input "So checks 4–5 must key on *which session* read the file, not just that some session did." |
| R13 | Each affected `parity.yaml` OpenCode cell moves to `partial` (fr reads it; the live path is unproven), backed by tests over a committed, fictional opencode.db fixture whose shapes follow a live capture; a `verify: post-merge` acceptance row re-runs take 10 run B's shape. | input "Each surface's `parity.yaml` row moves from `unobserved`/`partial` to observed on OpenCode, with tests built on a captured opencode.db fixture (redacted per the third-party privacy rule)."<br>input "That run's re-cut partition, invented reviewer and missing `answered_by` are each refused or corrected by fr, and its cost table has real numbers."<br>decision d-parity-partial |

## Deferred from input

| input | reason |
|---|---|
| "B edited the `shows:` labels in its visual record until the check passed." | A record-authoring discipline problem, not an observation gap: R12 makes the reads the check keys on real, but nothing here judges label edits. Left on #797's thread for a follow-up. |

## Design

### A. One session protocol — `fr.run.observed` (R4)

A new module `packages/fr/src/fr/run/observed.py` defines the protocol every
transcript gate calls, and the two backends:

```python
class ObservedSession(Protocol):
    harness: str
    session: str                      # the id this view reads
    def answered_rounds(self, since: datetime) -> list[Round] | None: ...
    def dispatches(self, since: datetime) -> list[ChildDispatch] | None: ...
    def child(self, agent_id: str) -> ObservedSession | Literal[False] | None: ...
    def first_read(self, path: Path, since: datetime, *, not_before: datetime | None) -> datetime | Literal[False] | None: ...
    def first_shell_executing(self, script: Path, since: datetime) -> datetime | Literal[False] | None: ...
    def wrote_windows(self, log: Path, since: datetime) -> list[tuple[datetime, datetime]] | None: ...

@dataclass(frozen=True)
class ChildDispatch:
    agent_id: str             # Claude Code: agentId; OpenCode: child session id
    agent_type: str | None
    started: datetime | None
    returned: str | None      # the child's final assistant text; None while running / unreadable
```

Every method keeps today's three-valued contract: `None` = could not read,
`False`/`[]` = read and found nothing. `observed_session(env, session=None)`
returns the backend for the detected harness, or `None` (Hermes, no harness, no
session id). `child(id)` is `False` for an id this session never dispatched —
what `witness_transcript` returns today.

- **`ClaudeCodeSession`** wraps today's code unchanged in behaviour: the
  existing functions in `run/telemetry.py` (`answered_rounds_since`,
  `attribute_dispatches`, `read_file_since`, `shell_named_since`,
  `orchestrator_wrote_since`'s JSONL half) become its implementation.
  `ChildDispatch.returned` is new: the last assistant `text` block of
  `subagents/agent-<id>.jsonl`.
- **`OpenCodeSession`** reads opencode.db through `fr.usage.readers.opencode.open_ro`
  (read-only), scoped to one session id: its own `part` rows for rounds,
  reads, shells and writes; its `task` parts for dispatches (§C). `child(id)`
  returns an `OpenCodeSession` for the child after checking the child's
  `session.parent_id` equals this session. `_opencode_wrote_since`
  (`telemetry.py:1215`) becomes `wrote_windows`, now scoped to the run session
  instead of "any top-level session active since" — the weakness its own
  docstring states (`:1227`) closes.

The gates in `commands/run_cmd.py` (`_verify_operator_gate` `:1147`,
`_verify_reviewer` `:2096`, `_verify_tests_log`), `journal/operator.py:42` and
`run/visual.py:_witness_file` call `observed_session` instead of
`_this_session`. The module-level telemetry functions stay importable (tests
and `fr.usage.readers.claude_code` use them) and the protocol is the only new
surface. Hermes remains `None` — one new backend class, later.

### B. The run session on OpenCode (R1, R2)

- **Plugin.** `packages/fr-opencode-plugin/src/session.ts` adds a `shell.env`
  hook: when `input.sessionID` is a non-empty string, set
  `output.env.FR_OPENCODE_SESSION_ID = input.sessionID`. Nothing else; never
  throws (an exception is swallowed, like the idle and claim handlers). Wired
  in `index.ts`. Delivered to consumers by the existing plugin delivery
  (`scripts/deliver-opencode-plugin.sh`).
- **fr.** `telemetry.SESSION_ID_ENV` becomes a per-harness table:
  `{"claude-code": "CLAUDE_CODE_SESSION_ID", "opencode": "FR_OPENCODE_SESSION_ID"}`.
  `current_session(env)` reads the key of the harness `detect_harness` names,
  so gh#537's guard (`run_cmd.py:2805`, "only when the harness fr runs under
  OWNS the session key") generalises rather than disappears: an OpenCode
  started from a Claude Code shell still never records the inherited Claude
  key, and now records its own.
- **Root session.** A command run from a child session (an executor's `fr
  journal add`) sees the CHILD's id. `observed_session` walks `parent_id` to
  the top-level session for gates that read the run; `advance` is only ever
  run by the orchestrator, so the attempt records the top-level id directly.
- **Cost.** Nothing new: `usage.sources.sessions_of` (`usage/sources.py:40`)
  already yields every attempt's `(harness, session)`, and
  `usage.readers.opencode.read` already sums a session with its children. R2
  is met by R1; the Test Plan proves it end to end.
- `isolation/sessions.py:53` reads `current_session` for its ambient binding,
  so an OpenCode session now binds its workspace on `fr run start` / `fr
  isolation up` as Claude Code's does. The `fr-session-bind` parity row (a
  Claude Code hook) is unchanged.

### C. Child sessions (R3, R6)

`OpenCodeSession.dispatches(since)` reads the session's `task` parts with
`state.time.start >= since`: `agent_id = state.metadata.sessionId`,
`agent_type = state.input.subagent_type`, `started = state.time.start`,
`returned` = the child session's last `text` part (falling back to the
`<task_result>` body of `state.output`), `None` while `status` is `running`.
A part whose `metadata.parentSessionId` differs from the session, or whose
child row's `parent_id` does not match, is skipped: both keys must agree.

- **Reviewer id (R6).** `_verify_reviewer` asks the protocol for the dispatch
  named by the reviewer id; on OpenCode an id that is no child dispatched since
  the unit opened now refuses (`observed is False`), exactly the Claude Code
  branch — #816's `opencode-gpt-6-luna` is refused. The implementer and
  wrong-agent-type refusals apply unchanged; `_same_agent` compares OpenCode's
  `subagent_type` spellings (`fr-spec-reviewer-<tier>` counts as
  `fr-spec-reviewer`: a tier suffix is stripped on the OpenCode side).
- **Holder (R3).** At resolve, a unit whose last attempt has an `agent_type`
  but no claimed `agent` gets one filled when the protocol shows exactly one
  child of that agent type dispatched since the attempt opened; zero or
  several → unchanged (the existing "unclaimed" handling stands). The plugin's
  own claim (`claim.ts`, `--open-unit`) keeps running; the two agree by
  construction since both name the child session id.

### D. What the reviewer returned (R5, R7, R8)

The reviewer's `ChildDispatch.returned` is the evidence. Both checks run on
every harness whose backend can read the return (Claude Code, OpenCode); where
it cannot (`None` from the protocol, Hermes), they are skipped with
`unobserved=reviewer-return` noted and a yellow warning — never silently.

- **spec-review coverage (R5).** `_coverage_witness` extracts the fenced
  `input-coverage` block from the recorded review entry (today) AND from the
  reviewer's return. The two must be equal after normalising line endings and
  trailing whitespace; the first differing table row is named in the refusal
  (row number, the recorded line, the returned line), which tells the
  orchestrator to record the return unedited or re-dispatch. A return with no
  block refuses as "the reviewer returned no input-coverage block". The
  orchestrator still writes the record (d-coverage-refuse); fr never authors
  the entry.
- **review-phase findings (R7).** The review-phase brief (`fr run advance`'s
  dispatch brief, and fr-goal §6 prose) tells the reviewer to end its return
  with:

  ````markdown
  ```findings
  p2-r1 | in | <one-line summary>
  p2-r2 | out | <one-line summary>
  ```
  ````

  ids `p<N>-r<k>` (N the phase, k from 1), or the single line `none`. The
  review-phase resolve (`done`) refuses when the block is missing or
  malformed, and when any block id is not a `kind=finding` plan-journal entry
  with `phase=N` whose `review_scope` equals the block's tag. The journal may
  hold MORE findings than the block (the orchestrator's own); never fewer.
  Reclassification stays what it is today: resolving the finding
  `out-of-scope` keeps the reviewer's tag and renders "reclassified by the
  orchestrator" (`commands/journal_cmd.py:490`). #816's run (six returned,
  none filed) is refused, naming the six ids.
- **PR body (R8).** `record/pr_body.py:_findings` (`:94`) already renders
  plan-journal findings with their resolution; R7 is what puts them in the
  journal. The Test Plan asserts the rendered sections carry review-phase
  findings.

### E. Operator answers (R9, R10, R11)

- **Reading (R9).** `OpenCodeSession.answered_rounds(since)` applies
  `answered_rounds_since`'s rule (`telemetry.py:485`) to the session's parts in
  `time.start` order: consecutive `question` calls form a round; `todowrite`
  (OpenCode's progress tool) is round-neutral like `ROUND_NEUTRAL_TOOLS`; any
  other tool closes the round; a round counts when any call is `completed` with
  a non-empty `metadata.answers`; a declined (`error`) call is not an answer.
  Question texts come from `input.questions[].{question, header}`, so the
  `a 2nd round may follow` announcement check works unchanged.
  `question_rounds_refusal` then applies as on Claude Code.
- **Refusing a missing claim (R10).** `_resolve_record_in_process`
  (`run_cmd.py:4994`) stops defaulting (`offered.pop("answered_by", None)`),
  and so does the flag form (`run_cmd.py:4524`, `answered_by or "agent"`). On
  a gated step, when the gate is unobserved and no `answered_by` was given,
  `_verify_operator_gate` exits 2: "could not verify who answered this gate —
  pass `answered_by: operator` (the operator answered) or `answered_by: agent`
  (cleared without asking) in the record's evidence". An observed gate still
  derives provenance and ignores the claim, as today; `--no-questions` still
  means `agent`. No new value: `AnsweredBy` stays `operator | agent`.
- **Wording (R11).** `fr run gates` (`run_cmd.py:5717`) and `fr run check`
  (`:5653`) read the step's `unobserved` evidence: a gate cleared `agent` whose
  step records `unobserved` containing `operator-gate` prints
  "operator gate cleared by the agent, as claimed — unobserved: fr could not
  read who answered"; an observed `agent` keeps "no operator answered it", and
  a claimed-unobserved `operator` prints "answered by the operator, as claimed —
  unobserved".
- **Prose.** fr-goal SKILL.md "Harness — questions" and §2 "Harness — spec
  reviewer": OpenCode uses its `question` tool (same labelling and sequencing
  rules as Claude Code's), and fr verifies both answers and reviewer ids there.
  Hermes keeps the end-the-turn wording. Mirrors regenerated
  (`sync-opencode.py`, `sync-hermes.py`).

### F. File reads (R12)

`OpenCodeSession.first_read` matches `read` parts whose absolute
`input.filePath` realpath equals the shot's, started at or after
`max(since, not_before)`; `first_shell_executing` applies `_executes`
(`telemetry.py:953`) to `bash` parts' `input.command`. The witness session is
chosen exactly as `_witness_file` chooses it today (`run/visual.py:446`): the
reviewer's child, the claimed holder's child, or the orchestrator's own
session (`main_thread` ≙ the top-level session's own parts, never a child's) —
so a PNG the orchestrator opened does not satisfy a reviewer's check (#797's
comment). `_unobservable` (`run/visual.py:418`) stops naming OpenCode.

### G. Parity and fixtures (R13)

- **Fixture.** `tests/fixtures/usage/opencode/build.py` gains a run tree: a
  top-level `ses_run` with answered, declined and pending `question` calls,
  `read`/`bash` parts, `task` dispatches to a `fr-spec-reviewer-hard` child and
  two `general` children (one returning a `findings` block, one not), and the
  children's own `text`/`read` parts. Shapes follow the live capture above;
  every id, path and text is fictional (`/work/example/…`), and `NOTE.md`
  records that and the capture date. The pinned sha256 in `NOTE.md` moves.
- **Parity rows** (`packages/fr/src/fr/harness/parity.yaml`), OpenCode cell →
  `partial` with a `scope_note` naming the fixture tests and the post-merge
  row: `operator-gate`, `out-of-scope-operator-guard`,
  `spec-review-independence`, `visual-evidence`, `dispatch-holder-identity`,
  `usage-capture`; `deliver-tests-provenance` stays `enforced` (now pinned to
  the run session). A new row `run-session-identity` covers the plugin's
  `shell.env` export: claude-code `enforced` (the harness sets its own key),
  opencode `partial`, hermes `absent`. `fr harness parity --check` must pass,
  so `fr.harness.observe` learns the plugin's new marker comment if it
  derives OpenCode cells from marker comments.
- **Acceptance rows** are listed in the brainstorm record; the live one is
  `opencode-observe-take10-rerun` (`verify: post-merge`). Per #822, #823 is
  meant to close when that row flips; the PR still carries all four `Closes`
  lines as the batch's delivery rules require, and the post-merge row keeps the
  live claim owed and visible.

### H. Artifact versioning

No artifact's shape changes: `UnitAttempt.session` already exists (OpenCode
now fills it), `AnsweredBy` keeps its two values, `unobserved` is existing
free-form evidence, and the `findings` block lives in a reviewer's return, not
in a record. No `current_version` moves. If implementation finds otherwise, the
number is not chosen in the plan: it is the next free one after `origin/main`'s
at the pre-ready merge, with every hop of the chain asserted (operator note,
2026-09-29).

## Non-goals

- Hermes: no reader; its cells stay as they are.
- Checking the spec reviewer's returned `finding` entries against the spec
  journal (the review-phase check in §D is #816's; the spec-review side of
  #777 is the coverage block).
- The orchestrator's model on OpenCode (`orchestrator_model` stays Claude Code only).
- Judging edits to a visual record's labels (Deferred from input).

## Test Plan

1. `tests/unit/test_run_observed_opencode.py` over the fixture: rounds (answered,
   declined, pending, `todowrite` neutral, a tool closing a round); dispatches
   (parent keys disagreeing are skipped; running child → `returned None`);
   `first_read`/`first_shell_executing` keyed per session; `wrote_windows`
   scoped to the run session (a sibling top-level session's write refused).
2. `tests/unit/test_run_observed_claude_code.py`: the Claude Code backend
   returns what the existing functions return on the existing transcript
   fixtures, plus `returned` from `claude-code-subagent.jsonl`.
3. Resolve-level tests (`FR_HARNESS=opencode`, `FR_OPENCODE_DB`=fixture,
   `FR_OPENCODE_SESSION_ID=ses_run`): take 10 B's shape — a re-cut coverage
   block, an invented reviewer id, a review-phase `findings: none` over a
   six-finding block, and a record with no `answered_by` on an unobservable
   gate — each refused; the honest record of the same run resolves.
4. `current_session` per harness, incl. an OpenCode process carrying a stale
   `CLAUDE_CODE_SESSION_ID` (gh#537); `advance` records the OpenCode session;
   `fr run cost` on the fixture run prints real figures.
5. `fr run gates` / `check` wording for observed-agent, claimed-agent-unobserved
   and claimed-operator-unobserved.
6. `bun test` in `packages/fr-opencode-plugin`: the `shell.env` handler sets the
   variable, ignores a missing session id, and never throws.
7. `fr harness parity --check`, the mirror tripwires, `fr acceptance check`.
8. **Post-merge — operator-driven:** re-run take 10 run B's shape on OpenCode
   with this release; confirm the four refusals/corrections and a Cost table
   with real numbers; flip `opencode-observe-take10-rerun`.

## Implementation Plans

- `docs/superpowers/plans/2026-09-29-opencode-observe/` (to be written by fr-plan).
