# fr observes OpenCode sessions — the run's session, each dispatched child, and what the child returned

Batch `opencode-observe-2`: super-fr#823 (umbrella), #797, #809, #816, #848,
#561. One run, one PR. It supersedes draft PR #837 (batch `opencode-observe`,
withdrawn when #851 removed the input gates), whose work this run ports.

## Background

Every transcript gate `fr run resolve` applies reaches the harness through one
choke point, `fr.run.telemetry._this_session`
(`packages/fr/src/fr/run/telemetry.py:601`), which returns `None` on any
harness but Claude Code. On OpenCode every gate therefore degrades to "recorded
as claimed, unverified": the operator gate (`answered_rounds_since`, `:513`),
the separate-context reviewer (`subagent_dispatch_since`, `:613`), and the
visual witness (`read_file_since` `:870`, `shell_named_since` `:989`, via
`run/visual.py`). The one gate that does read OpenCode, `deliver`'s `tests=`
(`_opencode_wrote_since`, `:1261`), cannot pin THE run session either, and
`advance` records no session on an OpenCode attempt (gh#537), so
`fr.usage.capture.candidates` (`usage/capture.py:103`) finds nothing and the
PR's Cost table is all dashes.

Take 10 (#817, fr 4.35.0, OpenCode 1.18.32) showed what that lets through: an
invented reviewer id with `findings: none` over six raised findings (#816), an
operator gate recorded as `answered_by: agent` although the operator answered
through OpenCode's `question` tool (#809), and every visual witness
`unobserved` although opencode.db held the PNG reads (#797). Take 11 found the
reverse error (#848): `fr run cost --recompute` attributed the operator's own
Claude Code session to an OpenCode run, because `candidates()` always appends
the session of the process running it (`usage/capture.py:120-127`) — right
when the caller is the run's orchestrator resolving a step, wrong post hoc.
`fr archive`'s capture (`archive.py:549`), run from a close-out session, has
the same flaw.

#561 is the declaration side of the same honesty: `parity.yaml` rates the
`fr-isolation-required` edit gate `partial` on OpenCode (bash ungated, #436)
but `enforced` on Hermes, whose `pre_tool_call` covers only
`write_file|patch` (`.hermes/config.snippet.yaml:13-14`) — the same shell-write
gap. `fr harness parity --check` maps `partial` and `enforced` both to
"present" (`harness/check.py:38-39`), so the observed side passes either way.

OpenCode shapes, verified on a live OpenCode 1.18.33 database (shapes only,
read-only, 2026-09-29, recorded in #837; no content copied):

- `session(id, parent_id, directory, agent, model, …)`; a `task` subagent is a
  child session (`parent_id` = its dispatcher).
- `part.data` of a `task` call: `state.input.{subagent_type, prompt,
  description}`, `state.metadata.{parentSessionId, sessionId, model}`,
  `state.time.{start,end}`, `state.status`, and `state.output` =
  `<task id="ses_…" state="completed"><task_result>…</task_result></task>`.
  The child's own last `text` part holds the same final message.
- `question`: `state.input.questions[].{question, header, options[]}`;
  answered → `status: completed`, `state.metadata.answers: [[str]]`; declined →
  `status: error`; a pending call is persisted as `status: running`.
- `read`: `state.input.filePath` (+ optional `offset`, `limit`).
- The OpenCode binary fires the plugin hook `shell.env` with
  `{cwd, sessionID, callID}` before every `bash` tool call and merges the
  returned `env` into the command's environment.

**What #837 left.** Phase 1 (the protocol, both backends, the run session,
the plugin export) was implemented and reviewed; phase 2 (agent-name
normaliser, holder fill, the reviewer-return checks) was implemented but its
review never closed, and it carried an `input-coverage` comparison whose block
#851 deleted; phase 3 (question tool, `answered_by`, visual witness, parity)
was never started. `main` has since moved about 1,100 lines under
`commands/run_cmd.py`. Decision d-salvage: port it — new modules and fixtures
come over verbatim, the `run_cmd.py`/`telemetry.py` hunks are re-applied by
hand onto current `main`, the coverage work is dropped, and everything is
reviewed afresh in this run.

## Requirements

R1. On OpenCode, the super-fr plugin exports the calling session's id into every shell command, and `advance` records the run's top-level session on the attempt it opens.
R2. With that session recorded, `fr run cost`, the usage capture and the PR body's Cost table show an OpenCode run's real figures.
R3. A session is attributed to a run only on positive evidence: a session recorded on one of the run's attempts, a session bound to the run's workspace, or the session issuing one of the run's own step resolves or advances. `fr run cost --recompute` and `fr archive`'s capture never add the session of whoever runs them, and with no evidence they report `unavailable: no session found`.
R4. Every transcript gate — including the phase `tests=` witness — reads the harness through one harness-neutral session protocol, with a Claude Code backend and an OpenCode backend; Hermes stays unobserved.
R5. fr maps each dispatch to its child session through opencode.db's parent/child records; at resolve, an attempt that names an agent type but no claimed holder gets the child's session id as its holder when exactly one child of that type was dispatched since the attempt opened, and stays unclaimed otherwise.
R6. At `spec-review` and `review-phase`, a reviewer id that names no child session the run session dispatched since the unit opened is refused on OpenCode, as it already is on Claude Code, and a tier-suffixed phase executor named as reviewer is refused on both.
R7. The review-phase reviewer ends its return with a fenced `review-findings` block of brief-prescribed ids; wherever fr can read the return, a review-phase `done` is refused when the block is missing or malformed, when an id repeats across reviewers, or when the plan journal lacks a returned finding, filed against that phase or a later one, with the reviewer's scope tag; where it cannot, the check is skipped visibly.
R8. The PR body's findings sections list the review-phase findings and how each was resolved.
R9. fr reads answered OpenCode `question` calls from opencode.db, grouped into rounds by the rule it applies to Claude Code, and the fr-goal skill and `parity.yaml` describe OpenCode's question tool.
R10. When fr cannot observe who answered an operator gate and neither the record nor the flags give `answered_by`, resolve refuses and names both values, on every harness; nothing defaults to `agent`.
R11. `fr run gates` and `fr run check` say a gate's provenance is claimed and unobserved, not "no operator answered it", when fr could not look.
R12. On OpenCode the visual witness observes screenshot reads and capture-script runs in the session of whoever owes them (executor, reviewer or orchestrator), never in another session.
R13. Each affected OpenCode `parity.yaml` cell is `partial` with a scope note naming what fr now reads, backed by tests over a committed fictional opencode.db fixture whose shapes follow the live capture, plus a new run-session-identity row; a post-merge acceptance row re-runs take 10 run B's shape.
R14. `parity.yaml` declares the `fr-isolation-required` edit gate `partial` on Hermes, with a scope note naming the `terminal`/`execute_code` write gap.

## Design

### A. One session protocol — `fr.run.observed` (R4)

`packages/fr/src/fr/run/observed.py` (ported from #837) defines the protocol
every transcript gate calls, and the two backends:

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
    returned: str | None      # what the parent received; None while running / unreadable
```

Every method keeps today's three-valued contract: `None` = could not read,
`False`/`[]` = read and found nothing. `observed_session(env, session=None)`
returns the backend for the detected harness, or `None` (Hermes, no harness,
no session id).

- **`ClaudeCodeSession`** wraps today's telemetry functions unchanged in
  behaviour. `ChildDispatch.returned` is the text of the `tool_result`
  answering the dispatching `tool_use` in the orchestrator's transcript
  (paired by `toolUseId`), never the subagent file's handback stub; a
  backgrounded dispatch returns the child's `SubagentHandback`, never its
  launch acknowledgement.
- **`OpenCodeSession`** reads opencode.db through
  `fr.usage.readers.opencode.open_ro` (read-only), scoped to one session id. A
  session the database does not hold is unobserved (`None`), never `[]`.
  `_opencode_wrote_since` becomes `wrote_windows`, scoped to the run session.
  **With no session id** (plugin not delivered, or older), `wrote_windows`
  keeps today's reading of every top-level session active since the unit
  opened through a module-level `opencode_unscoped(env)` view, so
  `deliver-tests-provenance` stays enforced without the plugin; every other
  method is `None` there.

The gates in `commands/run_cmd.py` (`_gate_provenance` `:1193`,
`_verify_reviewer` `:1993`, `_verify_tests_log` `:2112` and `_wrote_before`
`:2097`, and the phase `tests=` witness `_phase_log_windows` `:2230`),
`journal/operator.py` and `run/visual.py`'s witness call `observed_session`
instead of `_this_session` / `orchestrator_wrote_since`.
`_phase_log_windows` today hard-codes OpenCode and Hermes as having "no
child-session reader" (`:2247-2248`); it becomes
`observed_session(...).child(holder).wrote_windows(...)` (the run session's own
windows when the unit ran inline), so on OpenCode a phase log is witnessed in
the holder's child session and only Hermes keeps that message.
The module-level telemetry functions stay importable.

### B. The run session on OpenCode (R1, R2)

- **Plugin.** `packages/fr-opencode-plugin/src/session.ts` adds a `shell.env`
  hook: when `input.sessionID` is a non-empty string, set
  `output.env.FR_OPENCODE_SESSION_ID`. Never throws. Wired in `index.ts`,
  delivered by the existing `scripts/deliver-opencode-plugin.sh`.
- **fr.** `telemetry.SESSION_ID_ENV` becomes a per-harness table
  (`claude-code` → `CLAUDE_CODE_SESSION_ID`, `opencode` →
  `FR_OPENCODE_SESSION_ID`); `current_session(env)` reads the key of the
  harness `detect_harness` names, so gh#537's guard generalises: an OpenCode
  started from a Claude Code shell never records the inherited Claude key.
- **Recording.** `_open_dispatch`'s gh#537 guard (`run_cmd.py:2973`, today
  `session=… if harness == ClaudeCodeReader.harness else None`) records the
  session on any harness that owns its key, through `run_session`.
- **Root session.** A command run from a child session sees the CHILD's id;
  one helper, `run_session(env)`, walks `parent_id` to the top-level session
  (identity on Claude Code). Every place that reads or compares the run's
  session calls it: `advance`'s recording above, capture, the ambient binding,
  window checks, and `telemetry.dispatched_from_this_session` (`:341-351`,
  behind `_dispatched_from_another_session`, `run_cmd.py:3233`). Without the
  last one, filling `attempt.session` on OpenCode would make a child's own
  `fr` command read its unit as "dispatched from another session".
- **Cost.** `usage.sources.sessions_of` already yields every attempt's
  `(harness, session)` and `usage.readers.opencode.read` sums a session with
  its children, so R2 follows from R1.
- `isolation/sessions.py` reads `current_session` for its ambient binding, so
  an OpenCode session now binds its workspace on `fr run start` /
  `fr isolation up` as Claude Code's does (visible in `fr isolation status`).

### C. Positive-evidence attribution (R3)

A keyword-only `ambient: bool` with **no default** is threaded through every
function on the path: `usage.capture.candidates`, `build_capture`, `capture`
and `live_usage` (`usage/capture.py:103,168,219,236`). The cursor's attempt
sessions and the workspace bindings are always candidates, each with its own
recorded harness; the calling process's session (`run_session`) is added only
when `ambient=True`. No default means the type checker names every caller, so
no path can stay ambient by accident.

- `ambient=True` — the run's own step resolves, where the caller is the
  orchestrator: `_capture_usage` / `_capture_on_new_host` on resolve
  (`run_cmd.py:429-457`), the `deliver` capture (`:5194`), and `deliver`'s
  live render (`record/pr_body.py:230`). `advance` captures nothing.
- `ambient=False` — the post-hoc paths: `run/cost.py`'s `recompute_entries`
  (`:212`, the one direct `candidates` caller) and `fr archive`'s capture
  (`archive.py:561`).

With no candidates, `recompute_entries` appends the same `NO_SESSION_FOUND`
placeholder `build_capture` writes (`usage/capture.py:207-208`), and `fr run
cost` prints each unavailable session's reason under its count line (today it
prints only `N read, M unavailable`, `run_cmd.py:4175-4178`), so `--recompute`
reads `unavailable: no session found` exactly as the committed file does.
`fr usage backfill` reads only sessions an archived file already names, and is
unchanged.

### D. Child sessions (R5, R6)

`OpenCodeSession.dispatches(since)` reads the session's `task` parts with
`state.time.start >= since`: `agent_id = state.metadata.sessionId`,
`agent_type = state.input.subagent_type`, `returned` = the child's last
`text` part (falling back to the `<task_result>` body), `None` while
`status` is `running`. A part whose `metadata.parentSessionId` and the child
row's `parent_id` disagree with this session is skipped.

- **Agent names.** `observed.agent_name(t)` drops a plugin qualifier
  (`super-fr:`) and an OpenCode tier suffix (`-mechanical`, `-standard`,
  `-hard`). All three comparison sites call it: `_same_agent`
  (`run_cmd.py:2088`), `_same_agent` in `run/visual.py`, and the
  phase-executor refusal (`run_cmd.py:2048`, today an exact
  `== PHASE_EXECUTOR_AGENT`).
- **Reviewer id (R6).** `_verify_reviewer` asks the protocol for the dispatch
  named by the reviewer id; on OpenCode an id that is no child dispatched since
  the unit opened refuses, as the Claude Code branch does — #816's
  `opencode-gpt-6-luna` is refused. This applies to `spec-review` too: both
  steps route through `_verify_reviewer`.
- **Holder fill (R5).** At resolve, a unit whose open attempt has an
  `agent_type` but no claimed `agent` gets one when the protocol shows exactly
  one child of that agent type (by `agent_name`) dispatched since the attempt
  opened; zero or several leave it unclaimed, and the existing unclaimed
  handling stands. The plugin's own claim (`--open-unit`) names the same child
  id, so the two agree. The fill runs FIRST in resolve, before any evidence
  is derived — in particular before the visual witness's "unclaimed" refusal
  (`run/visual.py:468-482`), which would otherwise refuse a unit the fill
  names.

### E. What the reviewer returned (R7, R8)

Runs on every harness whose backend reads the return (Claude Code, OpenCode);
where it cannot (`None`, Hermes) the check is skipped with
`unobserved=reviewer-return` in the evidence and a yellow warning.

- **Where the instruction lives.** `_build_member_brief` (`run_cmd.py:3299`; review-phase is a group member, so its brief is built there, not in `_build_brief`) adds a
  `review_findings` key to every `review-phase` brief, on both shipped shapes
  (`fr-goal.yaml`, `fr-goal-light.yaml`) since they share the step id: the
  exact text the reviewer must be given, with this phase's `N` filled in.
  fr-goal §6 tells the orchestrator to put that key's text into the reviewer's
  prompt verbatim. The manifests' review-phase comment documents it. It tells
  the reviewer to end its return with:

  ````markdown
  ```review-findings
  p2-r1 | in | <one-line summary>
  p2-r2 | out | <one-line summary>
  ```
  ````

  ids `p<N>-r<k>`, or the single line `none`. With several reviewers in one
  unit, fr-goal §6 gives each a distinct letter (`p<N>a-r<k>`, `p<N>b-r<k>`).
  The fence is named `review-findings` so it is never confused with the
  step's DERIVED `findings` evidence (the closed-finding ids fr records).
- **Who is a reviewer.** A child dispatched since the unit opened is a
  reviewer of the unit when its id is named in the record's `reviewer`
  evidence, or when its return contains a `review-findings` fence. Each named
  reviewer owes a block. Any other child — an Explore or fixer helper the
  orchestrator dispatches while receiving the review — owes nothing, so an
  honest run is never refused for a helper. The residual gap is stated: a
  reviewer the record does not name and that returns no block is invisible to
  this check (R6 still refuses a named id that is no dispatch).
- `fr.run.review_return` (ported) parses the blocks. The review-phase `done`
  refuses a named reviewer with a missing or malformed block, an id repeated
  across two returns, and any returned id that is not a `kind=finding`
  plan-journal entry with `phase >= N` (a later phase is where the manifest files a finding that belongs there) whose `review_scope` equals the block's
  tag; the refusal names every missing id. The journal may hold more findings
  than the blocks, never fewer. Reclassification stays as today (resolving
  `out-of-scope` keeps the reviewer's tag and renders as reclassified).
- **PR body (R8).** `record/pr_body.py` already renders plan-journal findings
  with their resolution; R7 is what puts them in the journal. A test pins the
  rendered sections carrying review-phase findings.

### F. Operator answers (R9, R10, R11)

- **Reading (R9).** `OpenCodeSession.answered_rounds(since)` applies
  `answered_rounds_since`'s rule to the session's parts in `time.start` order:
  consecutive `question` calls form a round; `todowrite` is round-neutral; any
  other tool closes the round; a round counts when any call is `completed`
  with non-empty `metadata.answers`; a declined call is no answer. Question
  texts come from `input.questions[].{question, header}`, so the
  `a 2nd round may follow` check works unchanged.
- **No default (R10).** All three defaults go: `resolve_in_process`
  (`run_cmd.py:5289`, `offered.pop("answered_by", "agent")`), the flag form
  (`:4783`, `answered_by or "agent"`) and `_resolve_body`'s own parameter
  (`:4904`, `answered_by: str = "agent"`), which becomes `AnsweredBy | None =
  None`. Its closed-set check (`:4920-4927`) accepts `None` and still refuses
  any third value, so an ungated step resolves exactly as today.
  `_gate_provenance` (`:1193`) takes `claimed: AnsweredBy | None`; on a gated
  step whose gate is unobserved and `claimed is None` it exits 2: "could not
  verify who answered this gate — pass `answered_by: operator` (the operator
  answered) or `answered_by: agent` (cleared without asking)". An observed
  gate still derives provenance; `--no-questions` still means `agent`.
  `AnsweredBy` keeps its two values; the `run/model.py:41` docstring that
  states the old default is updated.
- **Wording (R11).** `fr run gates` (`run_cmd.py:6065`) and `fr run check`
  (`:5995`) read the step's `unobserved` evidence: an `agent` clearance whose
  step records `unobserved` containing `operator-gate` prints "cleared by the
  agent, as claimed — unobserved: fr could not read who answered"; an observed
  `agent` keeps "no operator answered it"; a claimed-unobserved `operator`
  prints "answered by the operator, as claimed — unobserved".
- **Prose.** fr-goal SKILL.md "Harness — questions" and §2 "Harness — spec
  reviewer": OpenCode uses its `question` tool (same labelling and sequencing
  rules), and fr verifies answers and reviewer ids there. Hermes keeps the
  end-the-turn wording. Mirrors regenerated (`sync-opencode.py`,
  `sync-hermes.py`).

### G. File reads (R12)

`OpenCodeSession.first_read` matches `read` parts whose `input.filePath`
realpath equals the shot's, started at or after `max(since, not_before)`;
`first_shell_executing` applies `_executes` to `bash` parts'
`input.command`. The witness session is chosen as `run/visual.py` chooses it
today — the reviewer's child, the claimed holder's child, or the
orchestrator's own parts — so a PNG the orchestrator opened does not satisfy a
reviewer's check. `_unobservable` stops naming OpenCode.

### H. Parity, fixtures, prose (R13, R14)

- **Fixture.** `tests/fixtures/usage/opencode/build.py` already exists on
  `main` with three consumers (`tests/unit/test_usage_readers.py`,
  `test_run_tests_log_opencode.py`, `test_run_opencode_reader.py`), so #837's
  builder is NOT copied over it: the run tree is ADDED beside the existing
  rows, under new session ids that no existing assertion reads, so what
  `usage.readers.opencode.read` sums for today's sessions is unchanged. The
  run tree: a top-level `ses_run` with answered, declined and pending
  `question` calls, `read`/`bash` parts, `task` dispatches to a
  `fr-spec-reviewer-hard` child and two `general` children (one returning a
  `review-findings` block, one not), and the children's own parts. Every id,
  path and text is fictional (`/work/example/…`); `NOTE.md` says so, gives the
  capture date, and its pinned sha256 moves.
- **Parity rows** (`packages/fr/src/fr/harness/parity.yaml`). OpenCode cell
  moves `→ partial`, with a `scope_note` naming the fixture tests and the
  post-merge row: `operator-gate`, `out-of-scope-operator-guard`,
  `spec-review-independence`, `visual-evidence`. Already `partial`, so only
  the `scope_note` changes: `dispatch-holder-identity` (`:373-374`) and
  `usage-capture` (`:434-435`). `deliver-tests-provenance` stays `enforced`,
  now pinned to the run session. New row `run-session-identity`,
  `kind: interaction`: claude-code `enforced`, opencode `partial`, hermes
  `absent`. Interaction rows are not observed, and `fr.harness.observe`
  accepts markers only for shipped hook scripts (`observe.py:107-135`), so
  observe.py is unchanged and `session.ts` carries NO parity marker, as
  `claim.ts` already does not.
- **#561 (R14).** The `fr-isolation-required` Hermes cell becomes `partial`,
  `scope_note`: the `pre_tool_call` hook gates `write_file|patch`
  (`.hermes/config.snippet.yaml`); `terminal`/`execute_code` writes reach only
  `fr-isolation-guard.sh`, which sees git/gh mutations alone.
- **Who flips OpenCode to `enforced`.** A follow-up issue filed at `deliver`,
  linked from the PR body, whose one job is Test Plan 14's last step once the
  live row flips (d-parity-partial).

### J. Published explainer and delivery

- **Explainer.** `docs/explainers/01-fr-goal.md` describes OpenCode session
  recording ("records a session only when that harness owns the session
  variable it read", `:361-373`) and the question gate; this change alters
  both, so the `.md` is updated and its `.html` regenerated in this PR
  (`.claude/rules/explainers-currency.md`).
- **#837.** Closed as superseded, with a comment linking this PR, when this
  PR's draft opened (d-close-837); its branch and workspace stay until this
  PR merges and go with the post-merge close-out.

### I. Artifact versioning

No artifact's shape changes: `UnitAttempt.session` already exists (OpenCode
now fills it), `AnsweredBy` keeps its two values, `unobserved` is existing
free-form evidence, and the `findings` block lives in a reviewer's return, not
in a record. No `current_version` moves.

## Non-goals

- Hermes: no reader; its observation cells stay as they are.
- Checking the spec reviewer's returned `finding` entries against the spec
  journal; any comparison of spec-review blocks (#851 removed them).
- The orchestrator's model on OpenCode (`orchestrator_model` stays Claude Code only).
- Judging edits to a visual record's labels (#797's take-10 comment) — a
  record-authoring discipline issue, left on #797's thread.
- #823's "closes when the live row flips" rule: the batch's delivery rules put
  `Closes` lines in the PR; the live claim stays owed as the post-merge row.

## Test Plan

1. `tests/unit/test_run_observed_opencode.py` over the fixture: rounds
   (answered, declined, pending, `todowrite` neutral, a tool closing a round);
   dispatches (disagreeing parent keys skipped; running child → `returned
   None`); `first_read`/`first_shell_executing` keyed per session;
   `wrote_windows` scoped to the run session, and with no session id falling
   back to every top-level session.
2. `tests/unit/test_run_observed_claude_code.py`: the Claude Code backend
   returns what the existing functions return on the transcript fixtures, and
   `returned` is the dispatch's `tool_result` text, never the handback stub or
   a background launch ack.
3. Resolve-level tests on OpenCode (`FR_HARNESS=opencode`,
   `FR_OPENCODE_DB`=fixture, `FR_OPENCODE_SESSION_ID=ses_run`), take 10 B's
   shape. Refused: an invented reviewer id (spec-review and review-phase), an
   OpenCode `fr-phase-executor-<tier>` named as reviewer, a review-phase with
   three reviewers whose block ids are not in the journal, a duplicate id
   across two returns, a named reviewer whose return has no block, and a
   record with no `answered_by` on an unobservable gate. The honest record of
   the same run resolves, including one where the orchestrator also
   dispatched an unnamed helper child that returned no block.
4. The R7 cases on Claude Code transcript fixtures: a missing findings block
   and a missing journal finding are refused; the honest one passes.
5. Holder fill: exactly one matching child fills the unclaimed attempt; zero
   or two leave it unchanged; a unit owing `visual` whose single matching
   child is unclaimed resolves (the fill runs before the visual derive).
5a. Phase `tests=` witness on OpenCode: a log written in the holder's child
   session is witnessed; one written only by a sibling session is not; Hermes
   keeps the unobserved message.
6. Visual witness on OpenCode: a PNG read by the orchestrator's session does
   not satisfy the reviewer's check; the same read in the reviewer's child does.
7. `current_session` per harness, incl. an OpenCode process carrying a stale
   `CLAUDE_CODE_SESSION_ID`; `advance` records the OpenCode top-level session
   (from a child's id too); a child's own `fr` command on that attempt is NOT
   read as "dispatched from another session"; `fr run cost` on the fixture run
   prints real figures; the ambient binding picks up the OpenCode session.
8. Attribution (R3): `--recompute` from a process carrying an unrelated
   `CLAUDE_CODE_SESSION_ID` on a run whose attempts record none prints
   `unavailable: no session found`, never that session's figures; the same run
   with an attempt session reads exactly that one; `fr archive`'s capture
   behaves the same; a step resolve still adds its own session. The three
   existing OpenCode-fixture consumers (`test_usage_readers.py`,
   `test_run_tests_log_opencode.py`, `test_run_opencode_reader.py`) pass
   unchanged as regression guards for the added run tree.
9. `answered_by`: the record and flag forms both refuse an unobservable gate
   with no value; `fr run gates`/`check` wording for observed-agent,
   claimed-agent-unobserved and claimed-operator-unobserved.
10. The unobserved-return path: a reviewer whose return fr cannot read
    resolves with `unobserved=reviewer-return` and the warning.
11. `render_pr_body` on a run whose plan journal holds review-phase findings
    lists each with its resolution.
12. `bun test` in `packages/fr-opencode-plugin`: the `shell.env` handler sets
    the variable, ignores a missing session id, never throws.
13. `fr harness parity --check` (incl. the Hermes edit-gate cell), the mirror
    tripwires, `fr acceptance check`.
14. **Post-merge — operator-driven:** re-run take 10 run B's shape on OpenCode
    with this release; confirm the invented reviewer and the missing
    `answered_by` are refused or corrected and the Cost table has real
    numbers; flip `opencode-observe-take10-rerun`; then, in the follow-up
    issue filed at `deliver`, move the OpenCode parity cells §H set to
    `partial` to `enforced`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-10-02-opencode-observe-2 | `derio-net/super-fr` | `2026-10-02-opencode-observe-2` | — |
