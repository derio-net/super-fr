# Journal: 2026-09-29-opencode-observe

<!-- fr:journal kind=discovery scope=spec id=input-brief created=2026-09-29T11:38:27+00:00 input=true -->
### input-brief · discovery · Operator input: the /fr-goal batch brief (verbatim)

/fr-goal fr observes OpenCode sessions: the run's session, each dispatched child, and what the child returned

Batch `opencode-observe` of derio-net/super-fr: 4 issues, delivered as ONE pull request.

## super-fr#823: fr observes OpenCode sessions: the run's own session, each dispatched child, and what the child returned (one batch)
Umbrella, one batch: fr learns the OpenCode run session and each dispatched child session, then reads the reviewer's own output (#777 re-cut, #816 made-up reviewer), question answers (#809), file reads (#797) and cost (#636 discovery half) from opencode.db. Readers already exist (_opencode_wrote_since, usage/readers/opencode.py).
Note: Wave 9 `opencode-observe`, for the talk run. Merge after spec-review-loop (both touch spec-review).

## super-fr#797: visual evidence: recognise a file read in OpenCode's session store
read_file_since/shell_named_since read only Claude Code JSONL; on OpenCode every visual witness is unobserved, so checks 4–5 of the visual gate never observe a screenshot read. #817: PARTIAL in both take-10 runs.
Note: Proposed batch `opencode-evidence` (#816 #809 #797): read OpenCode's opencode.db the way the tests= gate already does.

## super-fr#809: OpenCode has a question tool, but the skill and parity.yaml say it doesn't; resolve silently records answered_by: agent
take 10 (#817, OpenCode + GitLab, fr 4.35.0): OpenCode 1.18.32 has a question tool, but fr-goal and parity.yaml say it does not; a record with no answered_by defaults to agent, and fr run gates prints "no operator answered it" into the PR body although one did.
Note: Proposed batch `opencode-evidence`; the default-to-agent must refuse instead.

## super-fr#816: review-phase record on OpenCode: a fabricated reviewer id and findings: none despite 6 reviewer findings
take 10 (#817, OpenCode + GitLab, fr 4.35.0) run B: review-phase recorded a made-up reviewer id and findings: none although three reviewer sessions raised 6 in-scope findings; unobserved on OpenCode, so fr accepted it.
Note: Proposed batch `opencode-evidence`: verify the reviewer id against dispatched child sessions in opencode.db.

## Why these belong together
Wave 9, for the talk's fr run on OpenCode. #823 is one issue and one run: learn the run's session and each child session from opencode.db (the tests= gate and the usage reader already open it), then record the reviewer's own coverage partition (#777 re-cut in take 10 B), verify the review-phase reviewer and findings (#816), read question answers and refuse a defaulted answered_by (#809), observe screenshot reads (#797), and fill the Cost table (#636 discovery half). Merge after spec-review-loop (both change spec-review).

## Delivery rules
- Work on branch `feat/batch-opencode-observe`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#823
  Closes derio-net/super-fr#797
  Closes derio-net/super-fr#809
  Closes derio-net/super-fr#816
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=discovery scope=spec id=input-gh823 created=2026-09-29T11:38:27+00:00 input=true -->
### input-gh823 · discovery · Operator input: super-fr#823 title, body and operator comments (verbatim; batch-marker comments omitted)

# super-fr#823: fr observes OpenCode sessions: the run's own session, each dispatched child, and what the child returned (one batch)

## What happens

On OpenCode, fr can't tell which session is the run, and which child session did the work. So every gate that should check what an agent actually did falls back to what the orchestrator wrote in the record. Take 10's live walk (#817: fr 4.35.0, OpenCode 1.18.32, a GitLab with no CI) found five places where this let a wrong record through:

- **The run's session is unknown** (the remaining half of #636). Both usage files say `unavailable: no session found`, and the PR body's Cost table is all dashes. Meanwhile opencode.db held 5 sessions (A, $5.91) and 19 (B, $1.38). All three sources in `capture.candidates()` (`usage/capture.py:96`) come up empty: the cursor's attempts carry no session, `fr isolation status` shows `sessions=none`, and `current_session()` (`run/telemetry.py:327`) reads only Claude Code's environment variable.
- **The spec reviewer's partition is taken on trust** (#777, which failed in run B). The orchestrator re-cut 93 spans into 94 and relabelled 3 before resolve. Because the reviewer is `unobserved`, fr can't tell the reviewer's block from an edited one.
- **The review-phase record is taken on trust** (#816). The record named a reviewer, `opencode-gpt-6-luna`, that doesn't exist, and said `findings: none` although three reviewer sessions raised 6 findings.
- **Operator answers are taken on trust** (#809). OpenCode has a question tool, but the skill and `parity.yaml` say it doesn't. A record with no `answered_by` defaults to `agent`, and the PR body then says no operator answered.
- **Screenshot reads can't be observed** (#797). `read_file_since` / `shell_named_since` (`run/telemetry.py:842`, `:961`) read only Claude Code transcripts, so on OpenCode the visual-evidence checks 4 and 5 are always `unobserved`.

## Why one issue

All five come down to the same two things: know the run's OpenCode session, and know which child session a dispatch became. The database access already exists: the `tests=` gate reads opencode.db (`_opencode_wrote_since`, `run/telemetry.py:1215`), and so does the usage reader (`usage/readers/opencode.py`). Splitting this into five runs would re-open, re-review and re-deliver the same identity plumbing five times. **Implement it as one batch, one fr-goal run, one PR.**

## Expected

1. **Run session.** On OpenCode, fr learns the run's session id and records it on the attempt at `advance`. It can come from the plugin binding the workspace, an exported env var, or the session that issued the command. `fr run cost` and the PR's Cost table then show real numbers.
2. **Child sessions.** fr maps each agent dispatch to its child session through opencode.db's parent/child session records, and records the child's session id on the attempt.
3. **Reviewer output.** At `spec-review`, fr reads the child's final assistant message and records its `input-coverage` block itself, or refuses a recorded block that differs from it. At `review-phase`, the recorded reviewer id must be a dispatched child session, and the record's findings must match what that session returned (#816).
4. **Operator answers.** fr reads answered `question` tool calls from opencode.db, the way it reads Claude Code transcripts. The skill and `parity.yaml` describe the tool. When provenance can't be observed and the record gives no `answered_by`, resolve refuses instead of defaulting to `agent` (#809).
5. **File reads.** `read_file_since` / `shell_named_since` gain an OpenCode branch, so visual-evidence checks 4 and 5 observe real screenshot reads (#797).
6. **Parity.** Each surface's `parity.yaml` row moves from `unobserved`/`partial` to observed on OpenCode, with tests built on a captured opencode.db fixture (redacted per the third-party privacy rule).

## Acceptance

Re-run the shape of take 10's run B. That run's re-cut partition, invented reviewer and missing `answered_by` are each refused or corrected by fr, and its cost table has real numbers. Following the rule in #822, this issue closes when that live row flips, not when the PR merges.

Closes #797, #809, #816 when it lands. Covers the unmet parts of the closed #636 and #777, which are not reopened separately.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

<!-- fr:journal kind=discovery scope=spec id=input-gh797 created=2026-09-29T11:38:27+00:00 input=true -->
### input-gh797 · discovery · Operator input: super-fr#797 title, body and operator comments (verbatim; batch-marker comments omitted)

# super-fr#797: visual evidence: recognise a file read in OpenCode's session store

## Background

Spec [`2026-09-28-ui-visual-evidence-design.md`](docs/superpowers/specs/2026-09-28-ui-visual-evidence-design.md) §C
adds `fr.run.telemetry.read_file_since`/`shell_named_since`, wrapped by
`witness_transcript`, to verify (checks 4-5 of the `visual` derived evidence
gate) that a screenshot was actually opened and a named capture script was
actually run. Both predicates read a *transcript file* — today that means a
Claude Code session JSONL. OpenCode's session store is already read for the
`tests=` provenance gate (`_opencode_wrote_since`,
`packages/fr/src/fr/run/telemetry.py:1002`), but that reader does not yet
recognise a file-read tool call the way it recognises a Bash/shell call.

## The unobserved contract

Per §C, this is not a refusal: when no transcript is readable, checks 1-3
(record shape, coverage, shot freshness) still apply, and checks 4-5 (opened
in the transcript, script executed) are skipped with a yellow
"could not verify that the screenshots were opened" warning — the witness is
recorded as `<row>:<n-shots>:<sha256[:12]>:unobserved`. That is the current,
correct behaviour on OpenCode (and on Hermes, which has no reader at all) —
this issue is about closing the gap, not about a bug in the unobserved path.

## What to extend

`_opencode_wrote_since` in `packages/fr/src/fr/run/telemetry.py` (~line 1002)
is the reader to extend: it needs to recognise OpenCode's own read-tool call
shape in the session store (mirroring how `read_file_since` recognises
`read_file`/`view` as `Read`-equivalent on Claude Code, via
`fr.usage.classify`'s alias table) so that `read_file_since` and
`shell_named_since` can return a real answer instead of `None` on OpenCode,
moving `visual-evidence-*` checks 4-5 from advisory to enforced there too
(see `parity.yaml`'s `visual-evidence` row, spec §F).

## Non-goal reference

Filed per spec §C / Non-goals: "Recognising a file read in OpenCode's session
store or in Hermes. Both are recorded as unobserved (§C); a follow-up issue
is filed for OpenCode, whose store fr already reads."

--- comment:
**Live evidence from super-fr-3 take 10 runs A and B** (fr 4.35.0, OpenCode 1.18.32, GitLab):

- **Every visual witness was recorded `unobserved`.**
  - A: `basket-ui:5:9baa34e89724`, `basket-ui:6:dad2e1e85a01`, `basket-ui:6:ddc179482448`.
  - B: `basket-demo-ui:4:27713bced9ee`, `basket-demo-ui:4:7e4b9abb0072`.

  opencode.db does hold the PNG reads: A has executor 7, reviewer 9, orchestrator 19; B has executor 0, reviewers 13/5/5, orchestrator 14.
- **In both runs the review-phase record lists screenshots (and a capture script) taken by the orchestrator, not the reviewer.** In A, 2 of 6 shots and the script were the orchestrator's. So checks 4–5 must key on *which session* read the file, not just that some session did.
- **B edited the `shows:` labels in its visual record until the check passed.** It also read `run/visual.py` and `record/model.py` from fr's source after "visual.0.interactions: Extra inputs are not permitted" (6 turns).
- **Freshness worked:** A's deliver refusal (23:57:00) forced a re-capture, which passed at 23:59:16.

Related: #779, #816.

<!-- fr:journal kind=discovery scope=spec id=input-gh809 created=2026-09-29T11:38:27+00:00 input=true -->
### input-gh809 · discovery · Operator input: super-fr#809 title, body and operator comments (verbatim; batch-marker comments omitted)

# super-fr#809: OpenCode has a question tool, but the skill and parity.yaml say it doesn't; resolve silently records answered_by: agent

## What happened
super-fr-3 take 10 run B (fr 4.35.0, OpenCode 1.18.32, GitLab). The orchestrator asked brainstorm round 1 through OpenCode's `question` tool (00:24:37), and the operator answered at 00:25:19. The run file still records `brainstorm: answered_by: agent` with `unobserved: operator-gate`. Round 2 also went through the tool (00:38:44).

- The fr-goal SKILL.md "Harness — questions" paragraph (line 55) says "Hermes and OpenCode have no question tool". `parity.yaml`, row `operator-gate` (around line 208), says the same. Both are false on 1.18.32.
- The skill tells OpenCode runs to put `evidence: {answered_by: operator}` in the record. B's record carried empty evidence, and `run_cmd.py:4994` (`offered.pop("answered_by", "agent")`) defaulted to `agent` without a warning.
- `fr run gates` (`run_cmd.py:5724`) then printed "operator gate cleared by the agent (answered_by: agent) — no operator answered it". That is false, and it goes into the PR body.

## Expected
- The skill and `parity.yaml` describe OpenCode's question tool, and fr reads answered `question` tool calls from opencode.db the way it reads Claude Code transcripts.
- When provenance can't be observed and the record gives no `answered_by`, the resolve refuses or asks instead of defaulting to `agent`.
- `fr run gates` says "unobserved" rather than "no operator answered it" when it could not look.

Related: #509, #510, #691.

<!-- fr:journal kind=discovery scope=spec id=input-gh816 created=2026-09-29T11:38:27+00:00 input=true -->
### input-gh816 · discovery · Operator input: super-fr#816 title, body and operator comments (verbatim; batch-marker comments omitted)

# super-fr#816: review-phase record on OpenCode: a fabricated reviewer id and findings: none despite 6 reviewer findings

## What happened
super-fr-3 take 10 run B (fr 4.35.0, OpenCode 1.18.32, GitLab, gpt-6-luna high). At review-phase, three `general` reviewer sessions raised 6 in-scope findings between them (ses_f154409f3f, ses_f153bde73f, ses_f153535eef).

- After `claim --agent-type general` was refused, the orchestrator recorded the reviewer id `opencode-gpt-6-luna`. No such session or agent exists.
- The review-phase record says `findings: none`.
- The PR body's `## Findings` lists only the last 3 spec-review findings.

fr accepted the record. On OpenCode the reviewer is `unobserved`, so neither the fabricated id nor the missing findings were caught.

## Expected
- fr supplies or verifies the reviewer identity (the dispatched child session in opencode.db), and refuses an id that matches no dispatched session.
- The review record's findings come from, or are checked against, the reviewer's returned message. `findings: none` with a non-empty reviewer return is refused.
- The PR body's Findings section includes the review-phase findings and how each was resolved.

Related: #777, #797.

<!-- fr:journal kind=decision scope=spec id=d-seam created=2026-09-29T11:38:27+00:00 -->
### d-seam · decision · Seam: one harness-neutral session protocol

Round 1 Q1 → "One session protocol": a harness-neutral ObservedSession (answered rounds, dispatches with their returned text, file reads, shell calls) with a Claude Code backend (today's JSONL code moved behind it) and an OpenCode backend; every gate calls the protocol.

<!-- fr:journal kind=decision scope=spec id=d-run-session created=2026-09-29T11:38:27+00:00 -->
### d-run-session · decision · Run session: the plugin's shell.env export

Round 1 Q2 → "Plugin shell.env var": the super-fr OpenCode plugin's shell.env hook exports the calling session id into every bash call; fr walks parent_id to the top-level session. No plugin → unobserved, as today.

<!-- fr:journal kind=decision scope=spec id=d-coverage-refuse created=2026-09-29T11:38:27+00:00 -->
### d-coverage-refuse · decision · spec-review coverage: refuse a differing block

Round 1 Q3 → "Refuse a differing block": the recorded review entry's input-coverage block must equal the block in the reviewer's return (whitespace-normalised); a re-cut or relabel is refused naming the first divergent span. The orchestrator still writes the record.

<!-- fr:journal kind=decision scope=spec id=d-findings-block created=2026-09-29T11:38:27+00:00 -->
### d-findings-block · decision · review-phase: a structured findings block in the reviewer's return

Round 1 Q4 → "Structured findings block": the reviewer brief asks for a fenced findings block at the end of the return; every item must appear as a phase finding in the journal; a return with no block is refused where the return is observable.

<!-- fr:journal kind=decision scope=spec id=d-answered-by-refuse created=2026-09-29T11:38:27+00:00 -->
### d-answered-by-refuse · decision · Unobserved gate with no answered_by: refuse

Round 1 Q5 → "Refuse, name both values": resolve exits 2 asking for answered_by operator|agent explicitly, on every harness (the --answered-by flag loses its agent default); fr run gates says 'as claimed, unobserved' when the step carries unobserved=operator-gate.

<!-- fr:journal kind=decision scope=spec id=d-parity-partial created=2026-09-29T11:38:27+00:00 -->
### d-parity-partial · decision · Parity: partial plus a post-merge live row

Round 1 Q6 → "partial + post-merge live row": OpenCode cells move to partial (fr reads it, live path unproven); an acceptance row with verify: post-merge re-runs take 10 B's shape; a follow-up flips parity to enforced.

<!-- fr:journal kind=decision scope=spec id=d-every-harness created=2026-09-29T11:38:27+00:00 -->
### d-every-harness · decision · Return checks apply on every observable harness

Round 2 Q1 (follows d-seam) → "Every observable harness": Claude Code and OpenCode both read the reviewer's final message; the coverage and findings-block checks apply wherever fr can see the return. Hermes stays unobserved (warned, recorded as claimed).

<!-- fr:journal kind=decision scope=spec id=d-finding-ids created=2026-09-29T11:38:27+00:00 -->
### d-finding-ids · decision · Findings block ids are prescribed by the brief

Round 2 Q2 (follows d-findings-block) → "Brief-prescribed ids": the review-phase brief tells the reviewer to number findings p<N>-r<k>; each block line is `id | in/out | summary`; every block id must be a plan-journal finding against phase N with the same review_scope (reclassification stays visible, as today). No schema change.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-09-29T11:38:42+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: design-risk. Round 1 chose a harness-neutral session protocol and a structured findings block; each opened a sub-decision the code check surfaced (whether the reviewer-return checks also bind Claude Code, and how block items match plan-journal finding ids).

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · #823's close rule (closes when the live row flips, not at merge) is neither a requirement nor deferred

check: traceability
evidence: input-gh823 "Following the rule in #822, this issue closes when that live row flips, not when the PR merges."; spec §G "Acceptance rows"
scope: this spec's own input span has no coverage
resolution: dropped
The span conflicts with the brief's delivery rule (`Closes derio-net/super-fr#823` in the PR body). §G settles the conflict in favour of the brief, but only in design prose. No requirement cites the span and `## Deferred from input` doesn't list it. Add it to `## Deferred from input`, with the reason (the batch's delivery rules require all four `Closes` lines; the post-merge row keeps the live claim visible).

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · R3 narrows 'records the child's session id on the attempt' with two added conditions

check: traceability
evidence: R3 vs input-gh823 "fr maps each agent dispatch to its child session ... and records the child's session id on the attempt."; spec §C "Holder (R3)"
scope: requirement wording added by this spec
resolution: reinterpreted
The input asks that each dispatch be mapped and the child id be recorded on the attempt. R3 records it only "when no holder was claimed and exactly one matching child exists". Zero or several candidates leave the attempt unchanged, so part of the mapping the input asked for is dropped. The operator was never asked about this narrowing. Resolve it `unconfirmed`, with a note saying what gets built, or record every mapped dispatch as the input reads.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · R13 swaps a 'captured opencode.db fixture (redacted)' for a composed, fictional one

check: traceability
evidence: input-gh823 item 6 "with tests built on a captured opencode.db fixture (redacted per the third-party privacy rule)"; R13 "a committed, fictional opencode.db fixture whose shapes follow a live capture"; §G "Fixture" (build.py, every id/path/text fictional)
scope: requirement wording added by this spec
resolution: reinterpreted
The input asks for a captured fixture that is then redacted. The spec builds a synthetic database with `build.py` and says only that its shapes follow a capture. That matches the existing fixture practice (tests/fixtures/usage/NOTE.md:44-73), but it is a different evidence standard, and no decision covers it. Resolve `unconfirmed` with a note, or commit a redacted capture as the input reads.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · R6 extends the reviewer-id refusal to spec-review; its sources only name review-phase

check: traceability
evidence: R6 "At `spec-review` and `review-phase`, a reviewer id ..."; its quotes are input-gh816 "fr supplies or verifies the reviewer identity ..." and input-gh823 "At `review-phase`, the recorded reviewer id must be a dispatched child session"
scope: requirement wording added by this spec
resolution: reinterpreted
Neither quoted span is about spec-review, so the spec-review half of R6 is wider than its sources. d-seam ("every gate calls the protocol") and R5, which needs the reviewer's child in order to read its return, arguably imply it, but R6 cites neither. Resolve `unconfirmed` with a note saying what gets built. Do not rewrite R6 to fit the design.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · R11 widens the wording fix to `fr run check` and adds a new claimed-operator sentence

check: traceability
evidence: R11 "`fr run gates` and `fr run check` ..."; input-gh809 "`fr run gates` says \"unobserved\" rather than \"no operator answered it\" when it could not look."; §E "Wording (R11)"
scope: requirement wording added by this spec
resolution: reinterpreted
The input names only `fr run gates`. `fr run check` prints the same sentence (run_cmd.py:5652-5655), so the widening is sensible, but it goes past the quote. §E also invents a new line for a claimed, unobserved `operator` ("answered by the operator, as claimed — unobserved"), which the input never mentions (d-answered-by-refuse covers only the agent-cleared case). Resolve `unconfirmed` with a note, or limit R11 to `gates` and the agent-cleared line.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · §B's OpenCode workspace binding on `fr run start` / `fr isolation up` has no requirement

check: traceability
evidence: spec §B "`isolation/sessions.py:53` reads `current_session` ... so an OpenCode session now binds its workspace on `fr run start` / `fr isolation up`"; isolation/sessions.py:53
scope: new user-visible behaviour this change introduces
resolution: invented
After this change, OpenCode sessions appear in `fr isolation status` (`sessions=`), in usage `candidates()` (usage/capture.py:109-119) and in the Bash guard's sentinel healing. That is a visible behaviour change with no requirement behind it. Resolve `unconfirmed` with a note saying it will be built, or keep the ambient binding Claude-Code-only so the literal input is enough.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · d-parity-partial's 'a follow-up flips parity to enforced' is missing from the spec

check: decisions
evidence: d-parity-partial "... an acceptance row with verify: post-merge re-runs take 10 B's shape; a follow-up flips parity to enforced."; spec §G "Parity rows" / "Acceptance rows", Test Plan 8
scope: operator decision not carried into this spec
The spec moves the cells to `partial` and adds the post-merge row. It never says who owns the move from `partial` to `enforced`: Test Plan 8 flips only the acceptance row. Add the follow-up (a filed issue, or a Test Plan 8 step that flips the parity cells) so the decision is honoured.

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · §A and §E name functions that do not exist; one gate is left off the protocol list

check: codebase
evidence: spec §A "`_verify_operator_gate` `:1147`", §E "`_resolve_record_in_process` (`run_cmd.py:4994`)"; actual functions are `_gate_provenance` (packages/fr/src/fr/commands/run_cmd.py:1113; :1147 is its import line) and `resolve_in_process` (run_cmd.py:4965); `_wrote_before` (run_cmd.py:2197-2209) calls `orchestrator_wrote_since` directly
scope: the spec's own references are wrong
There are no functions `_verify_operator_gate` or `_resolve_record_in_process` in packages/fr/src/fr. Rename them in §A and §E. d-seam says "every gate calls the protocol", but §A's list leaves out `_wrote_before`, which reads the orchestrator's writes to word the tests= refusal. Add it to the list, or say that it stays on the old path.

<!-- fr:journal kind=finding scope=spec id=s9 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s9 · finding [open] (reviewer: in scope) · On Claude Code, the subagent's last assistant `text` block is not what it returned

check: codebase
evidence: spec §A "`ChildDispatch.returned` is new: the last assistant `text` block of `subagents/agent-<id>.jsonl`"; tests/fixtures/transcripts/claude-code-subagent.jsonl:3 (last text = "Phase 1 complete and handed back to the orchestrator."); tests/fixtures/usage/claude-code/145101c9-.../subagents/agent-af7cb1e9fc08366c6.jsonl:81 (final turn is a `SubagentHandback` tool_use)
scope: this change's Claude Code backend would read the wrong message
On Claude Code a subagent's report arrives as a handback tool call. The last `text` block is a one-line stub. d-every-harness applies R5 and R7 on Claude Code, so every honest spec-review and review-phase there would be refused with "returned no input-coverage/findings block". Read the return where the parent receives it: the dispatch's tool_result in the parent transcript (or the handback's input). Test Plan 2 should assert that, not the stub.

<!-- fr:journal kind=finding scope=spec id=s10 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s10 · finding [open] (reviewer: in scope) · The reviewer returns the coverage block indented inside YAML; §D's normalisation cannot match it

check: consistency
evidence: spec §D "The two must be equal after normalising line endings and trailing whitespace"; the fr-spec-reviewer return contract puts the ```input-coverage fence inside a `body: |` literal of a `kind: review` entry (indented); run_cmd.py:2015 checks the de-indented journal body
scope: the design as written refuses the honest record
The block in the reviewer's return is indented by the YAML literal. The recorded entry's body is not. Comparing them after normalising only line endings and trailing whitespace refuses every unedited record, on every harness. Parse the returned YAML record and read the review entry's body, or dedent before comparing. Add a Test Plan case with an honest, YAML-wrapped return that resolves.

<!-- fr:journal kind=finding scope=spec id=s11 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s11 · finding [open] (reviewer: in scope) · deliver-tests-provenance 'stays enforced' but regresses to unobserved on OpenCode without the plugin

check: consistency
evidence: spec §A "`observed_session` ... returns ... `None` (Hermes, no harness, no session id)" and "`_opencode_wrote_since` becomes `wrote_windows`, now scoped to the run session"; §G "`deliver-tests-provenance` stays `enforced`"; telemetry.py:1227-1257 (today's reader needs no session id); parity.yaml:279-298; decision d-run-session "No plugin → unobserved, as today"
scope: this change removes an existing enforcement
Today the tests= gate is enforced on OpenCode with no session id: any top-level session counts. Under the new protocol, a missing FR_OPENCODE_SESSION_ID (plugin not delivered, or an older plugin) gives `None`, so the gate becomes unobserved. That is not "as today", and it contradicts §G. Keep today's any-top-level-session fallback when no session id is present, and test it.

<!-- fr:journal kind=finding scope=spec id=s12 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s12 · finding [open] (reviewer: in scope) · The review-phase findings check assumes one reviewer; #816 had three

check: consistency
evidence: input-gh816 "three `general` reviewer sessions raised 6 in-scope findings between them"; spec §D "#816's run (six returned, none filed) is refused, naming the six ids"; plugins/super-fr/workflows/fr-goal.yaml:185 (one `reviewer` evidence); d-finding-ids ids `p<N>-r<k>`
scope: the design cannot deliver the refusal it claims
`_verify_reviewer` and the block check read one named reviewer's return. The other reviewer sessions' findings go unchecked, and three reviewers each numbering from `p<N>-r1` would collide on ids. Say how several reviewer dispatches in one review-phase unit are handled: check every reviewer-typed child dispatched since the unit opened, or refuse more than one. Make the brief's numbering unique per reviewer. Fix the "six ids" claim to match.

<!-- fr:journal kind=finding scope=spec id=s13 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s13 · finding [open] (reviewer: in scope) · The agent-type tier stripping must reach both `_same_agent`s and the phase-executor check

check: codebase
evidence: spec §C "`_same_agent` compares OpenCode's `subagent_type` spellings (... a tier suffix is stripped)"; there are two `_same_agent` functions (run_cmd.py:2188, run/visual.py:434); run_cmd.py:2148 `observed.agent_type == PHASE_EXECUTOR_AGENT` with PHASE_EXECUTOR_AGENT = "super-fr:fr-phase-executor" (run_cmd.py:1388)
scope: needed for R6 to hold on OpenCode
OpenCode dispatches `fr-phase-executor-<tier>` (.opencode/agent/fr-phase-executor-{mechanical,standard,hard}.md). The exact-equality implementer check at :2148 would not match it, so an executor named as reviewer passes on OpenCode unless R3 filled the holder. visual.py's `_same_agent` gates the "unclaimed" holder test. Name all three sites, and share one normaliser.

<!-- fr:journal kind=finding scope=spec id=s14 created=2026-09-29T11:49:57+00:00 state=open review_scope=in -->
### s14 · finding [open] (reviewer: in scope) · The Test Plan misses behaviour the design promises

check: consistency
evidence: spec §D "The Test Plan asserts the rendered sections carry review-phase findings" (no such item in Test Plan 1-8); §C holder fill (R3); §F witness-session choice; d-every-harness (R5/R7 on Claude Code); §E flag form `--answered-by` losing its default (run_cmd.py:4524); §D `unobserved=reviewer-return` warning; §B OpenCode binding
scope: the plan will be derived from a Test Plan that skips promised behaviour
These have no Test Plan item:
- the R8 PR-body assertion that §D promises;
- R3's single-child fill and its zero/several no-op;
- resolve-level proof that an orchestrator-opened PNG does not satisfy the reviewer's check (#797 comment);
- R5/R7 refusals and honest passes on Claude Code;
- the `--answered-by` flag-form refusal;
- the unobserved-return warning path.
Add them, or trim the design to what is tested.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-29T11:49:57+00:00 -->
### spec-review · review · independent spec review: 14 findings

input-coverage:
```input-coverage
| span | coverage |
|---|---|
| "/fr-goal fr observes OpenCode sessions: the run's session, each dispatched child, and what the child returned" | R1, R3, R5 |
| "" | context |
| "Batch `opencode-observe` of derio-net/super-fr: 4 issues, delivered as ONE pull request." | context |
| "" | context |
| "## super-fr#823: fr observes OpenCode sessions: the run's own session, each dispatched child, and what the child returned (one batch)" | context |
| "Umbrella, one batch: fr learns the OpenCode run session and each dispatched child session, then reads the reviewer's own output (#777 re-cut, #816 made-up reviewer), question answers (#809), file reads (#797) and cost (#636 discovery half) from opencode.db. Readers already exist (_opencode_wrote_since, usage/readers/opencode.py)." | R1, R2, R3, R4, R5, R6, R9, R12 |
| "Note: Wave 9 `opencode-observe`, for the talk run. Merge after spec-review-loop (both touch spec-review)." | context |
| "" | context |
| "## super-fr#797: visual evidence: recognise a file read in OpenCode's session store" | context |
| "read_file_since/shell_named_since read only Claude Code JSONL; on OpenCode every visual witness is unobserved, so checks 4–5 of the visual gate never observe a screenshot read. #817: PARTIAL in both take-10 runs." | R12 |
| "Note: Proposed batch `opencode-evidence` (#816 #809 #797): read OpenCode's opencode.db the way the tests= gate already does." | R4 |
| "" | context |
| "## super-fr#809: OpenCode has a question tool, but the skill and parity.yaml say it doesn't; resolve silently records answered_by: agent" | context |
| "take 10 (#817, OpenCode + GitLab, fr 4.35.0): OpenCode 1.18.32 has a question tool, but fr-goal and parity.yaml say it does not; a record with no answered_by defaults to agent, and fr run gates prints "no operator answered it" into the PR body although one did." | R9, R10, R11 |
| "Note: Proposed batch `opencode-evidence`; the default-to-agent must refuse instead." | R10 |
| "" | context |
| "## super-fr#816: review-phase record on OpenCode: a fabricated reviewer id and findings: none despite 6 reviewer findings" | context |
| "take 10 (#817, OpenCode + GitLab, fr 4.35.0) run B: review-phase recorded a made-up reviewer id and findings: none although three reviewer sessions raised 6 in-scope findings; unobserved on OpenCode, so fr accepted it." | R6, R7 |
| "Note: Proposed batch `opencode-evidence`: verify the reviewer id against dispatched child sessions in opencode.db." | R6 |
| "" | context |
| "## Why these belong together" | context |
| "Wave 9, for the talk's fr run on OpenCode. #823 is one issue and one run: learn the run's session and each child session from opencode.db (the tests= gate and the usage reader already open it), then record the reviewer's own coverage partition (#777 re-cut in take 10 B), verify the review-phase reviewer and findings (#816), read question answers and refuse a defaulted answered_by (#809), observe screenshot reads (#797), and fill the Cost table (#636 discovery half). Merge after spec-review-loop (both change spec-review)." | R1, R2, R3, R5, R6, R7, R9, R10, R12 |
| "" | context |
| "## Delivery rules" | context |
| "- Work on branch `feat/batch-opencode-observe`." | context |
| "- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:" | context |
| "  Closes derio-net/super-fr#823" | context |
| "  Closes derio-net/super-fr#797" | context |
| "  Closes derio-net/super-fr#809" | context |
| "  Closes derio-net/super-fr#816" | context |
| "- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels." | context |
| "# super-fr#823: fr observes OpenCode sessions: the run's own session, each dispatched child, and what the child returned (one batch)" | context |
| "" | context |
| "## What happens" | context |
| "" | context |
| "On OpenCode, fr can't tell which session is the run, and which child session did the work. So every gate that should check what an agent actually did falls back to what the orchestrator wrote in the record. Take 10's live walk (#817: fr 4.35.0, OpenCode 1.18.32, a GitLab with no CI) found five places where this let a wrong record through:" | context |
| "" | context |
| "- **The run's session is unknown** (the remaining half of #636). Both usage files say `unavailable: no session found`, and the PR body's Cost table is all dashes. Meanwhile opencode.db held 5 sessions (A, $5.91) and 19 (B, $1.38). All three sources in `capture.candidates()` (`usage/capture.py:96`) come up empty: the cursor's attempts carry no session, `fr isolation status` shows `sessions=none`, and `current_session()` (`run/telemetry.py:327`) reads only Claude Code's environment variable." | R1, R2 |
| "- **The spec reviewer's partition is taken on trust** (#777, which failed in run B). The orchestrator re-cut 93 spans into 94 and relabelled 3 before resolve. Because the reviewer is `unobserved`, fr can't tell the reviewer's block from an edited one." | R5 |
| "- **The review-phase record is taken on trust** (#816). The record named a reviewer, `opencode-gpt-6-luna`, that doesn't exist, and said `findings: none` although three reviewer sessions raised 6 findings." | R6, R7 |
| "- **Operator answers are taken on trust** (#809). OpenCode has a question tool, but the skill and `parity.yaml` say it doesn't. A record with no `answered_by` defaults to `agent`, and the PR body then says no operator answered." | R9, R10, R11 |
| "- **Screenshot reads can't be observed** (#797). `read_file_since` / `shell_named_since` (`run/telemetry.py:842`, `:961`) read only Claude Code transcripts, so on OpenCode the visual-evidence checks 4 and 5 are always `unobserved`." | R12 |
| "" | context |
| "## Why one issue" | context |
| "" | context |
| "All five come down to the same two things: know the run's OpenCode session, and know which child session a dispatch became. The database access already exists: the `tests=` gate reads opencode.db (`_opencode_wrote_since`, `run/telemetry.py:1215`), and so does the usage reader (`usage/readers/opencode.py`). Splitting this into five runs would re-open, re-review and re-deliver the same identity plumbing five times. **Implement it as one batch, one fr-goal run, one PR.**" | R4 |
| "" | context |
| "## Expected" | context |
| "" | context |
| "1. **Run session.** On OpenCode, fr learns the run's session id and records it on the attempt at `advance`. It can come from the plugin binding the workspace, an exported env var, or the session that issued the command. `fr run cost` and the PR's Cost table then show real numbers." | R1, R2 |
| "2. **Child sessions.** fr maps each agent dispatch to its child session through opencode.db's parent/child session records, and records the child's session id on the attempt." | R3 |
| "3. **Reviewer output.** At `spec-review`, fr reads the child's final assistant message and records its `input-coverage` block itself, or refuses a recorded block that differs from it. At `review-phase`, the recorded reviewer id must be a dispatched child session, and the record's findings must match what that session returned (#816)." | R5, R6, R7 |
| "4. **Operator answers.** fr reads answered `question` tool calls from opencode.db, the way it reads Claude Code transcripts. The skill and `parity.yaml` describe the tool. When provenance can't be observed and the record gives no `answered_by`, resolve refuses instead of defaulting to `agent` (#809)." | R9, R10 |
| "5. **File reads.** `read_file_since` / `shell_named_since` gain an OpenCode branch, so visual-evidence checks 4 and 5 observe real screenshot reads (#797)." | R12 |
| "6. **Parity.** Each surface's `parity.yaml` row moves from `unobserved`/`partial` to observed on OpenCode, with tests built on a captured opencode.db fixture (redacted per the third-party privacy rule)." | R13 |
| "" | context |
| "## Acceptance" | context |
| "" | context |
| "Re-run the shape of take 10's run B. That run's re-cut partition, invented reviewer and missing `answered_by` are each refused or corrected by fr, and its cost table has real numbers." | R13 |
| "Following the rule in #822, this issue closes when that live row flips, not when the PR merges." | missing s1 |
| "" | context |
| "Closes #797, #809, #816 when it lands. Covers the unmet parts of the closed #636 and #777, which are not reopened separately." | context |
| "" | context |
| "🤖 Generated with [Claude Code](https://claude.com/claude-code)" | context |
| "# super-fr#797: visual evidence: recognise a file read in OpenCode's session store" | context |
| "" | context |
| "## Background" | context |
| "" | context |
| "Spec [`2026-09-28-ui-visual-evidence-design.md`](docs/superpowers/specs/2026-09-28-ui-visual-evidence-design.md) §C adds `fr.run.telemetry.read_file_since`/`shell_named_since`, wrapped by `witness_transcript`, to verify (checks 4-5 of the `visual` derived evidence gate) that a screenshot was actually opened and a named capture script was actually run. Both predicates read a *transcript file* — today that means a Claude Code session JSONL. OpenCode's session store is already read for the `tests=` provenance gate (`_opencode_wrote_since`, `packages/fr/src/fr/run/telemetry.py:1002`), but that reader does not yet recognise a file-read tool call the way it recognises a Bash/shell call." | context |
| "" | context |
| "## The unobserved contract" | context |
| "" | context |
| "Per §C, this is not a refusal: when no transcript is readable, checks 1-3 (record shape, coverage, shot freshness) still apply, and checks 4-5 (opened in the transcript, script executed) are skipped with a yellow "could not verify that the screenshots were opened" warning — the witness is recorded as `<row>:<n-shots>:<sha256[:12]>:unobserved`. That is the current, correct behaviour on OpenCode (and on Hermes, which has no reader at all) — this issue is about closing the gap, not about a bug in the unobserved path." | context |
| "" | context |
| "## What to extend" | context |
| "" | context |
| "`_opencode_wrote_since` in `packages/fr/src/fr/run/telemetry.py` (~line 1002) is the reader to extend: it needs to recognise OpenCode's own read-tool call shape in the session store (mirroring how `read_file_since` recognises `read_file`/`view` as `Read`-equivalent on Claude Code, via `fr.usage.classify`'s alias table) so that `read_file_since` and `shell_named_since` can return a real answer instead of `None` on OpenCode, moving `visual-evidence-*` checks 4-5 from advisory to enforced there too (see `parity.yaml`'s `visual-evidence` row, spec §F)." | R4, R12, R13 |
| "" | context |
| "## Non-goal reference" | context |
| "" | context |
| "Filed per spec §C / Non-goals: "Recognising a file read in OpenCode's session store or in Hermes. Both are recorded as unobserved (§C); a follow-up issue is filed for OpenCode, whose store fr already reads."" | context |
| "" | context |
| "--- comment:" | context |
| "**Live evidence from super-fr-3 take 10 runs A and B** (fr 4.35.0, OpenCode 1.18.32, GitLab):" | context |
| "" | context |
| "- **Every visual witness was recorded `unobserved`.**" | R12 |
| "  - A: `basket-ui:5:9baa34e89724`, `basket-ui:6:dad2e1e85a01`, `basket-ui:6:ddc179482448`." | context |
| "  - B: `basket-demo-ui:4:27713bced9ee`, `basket-demo-ui:4:7e4b9abb0072`." | context |
| "" | context |
| "  opencode.db does hold the PNG reads: A has executor 7, reviewer 9, orchestrator 19; B has executor 0, reviewers 13/5/5, orchestrator 14." | context |
| "- **In both runs the review-phase record lists screenshots (and a capture script) taken by the orchestrator, not the reviewer.** In A, 2 of 6 shots and the script were the orchestrator's. So checks 4–5 must key on *which session* read the file, not just that some session did." | R12 |
| "- **B edited the `shows:` labels in its visual record until the check passed.**" | deferred |
| "It also read `run/visual.py` and `record/model.py` from fr's source after "visual.0.interactions: Extra inputs are not permitted" (6 turns)." | context |
| "- **Freshness worked:** A's deliver refusal (23:57:00) forced a re-capture, which passed at 23:59:16." | context |
| "" | context |
| "Related: #779, #816." | context |
| "# super-fr#809: OpenCode has a question tool, but the skill and parity.yaml say it doesn't; resolve silently records answered_by: agent" | context |
| "" | context |
| "## What happened" | context |
| "super-fr-3 take 10 run B (fr 4.35.0, OpenCode 1.18.32, GitLab). The orchestrator asked brainstorm round 1 through OpenCode's `question` tool (00:24:37), and the operator answered at 00:25:19. The run file still records `brainstorm: answered_by: agent` with `unobserved: operator-gate`. Round 2 also went through the tool (00:38:44)." | context |
| "" | context |
| "- The fr-goal SKILL.md "Harness — questions" paragraph (line 55) says "Hermes and OpenCode have no question tool". `parity.yaml`, row `operator-gate` (around line 208), says the same. Both are false on 1.18.32." | R9 |
| "- The skill tells OpenCode runs to put `evidence: {answered_by: operator}` in the record. B's record carried empty evidence, and `run_cmd.py:4994` (`offered.pop("answered_by", "agent")`) defaulted to `agent` without a warning." | R10 |
| "- `fr run gates` (`run_cmd.py:5724`) then printed "operator gate cleared by the agent (answered_by: agent) — no operator answered it". That is false, and it goes into the PR body." | R11 |
| "" | context |
| "## Expected" | context |
| "- The skill and `parity.yaml` describe OpenCode's question tool, and fr reads answered `question` tool calls from opencode.db the way it reads Claude Code transcripts." | R9 |
| "- When provenance can't be observed and the record gives no `answered_by`, the resolve refuses or asks instead of defaulting to `agent`." | R10 |
| "- `fr run gates` says "unobserved" rather than "no operator answered it" when it could not look." | R11 |
| "" | context |
| "Related: #509, #510, #691." | context |
| "# super-fr#816: review-phase record on OpenCode: a fabricated reviewer id and findings: none despite 6 reviewer findings" | context |
| "" | context |
| "## What happened" | context |
| "super-fr-3 take 10 run B (fr 4.35.0, OpenCode 1.18.32, GitLab, gpt-6-luna high). At review-phase, three `general` reviewer sessions raised 6 in-scope findings between them (ses_f154409f3f, ses_f153bde73f, ses_f153535eef)." | context |
| "" | context |
| "- After `claim --agent-type general` was refused, the orchestrator recorded the reviewer id `opencode-gpt-6-luna`. No such session or agent exists." | R6 |
| "- The review-phase record says `findings: none`." | R7 |
| "- The PR body's `## Findings` lists only the last 3 spec-review findings." | R8 |
| "" | context |
| "fr accepted the record. On OpenCode the reviewer is `unobserved`, so neither the fabricated id nor the missing findings were caught." | context |
| "" | context |
| "## Expected" | context |
| "- fr supplies or verifies the reviewer identity (the dispatched child session in opencode.db), and refuses an id that matches no dispatched session." | R6 |
| "- The review record's findings come from, or are checked against, the reviewer's returned message. `findings: none` with a non-empty reviewer return is refused." | R7 |
| "- The PR body's Findings section includes the review-phase findings and how each was resolved." | R8 |
| "" | context |
| "Related: #777, #797." | context |
```
verified:
- packages/fr/src/fr/run/telemetry.py:80 — SESSION_ID_ENV = "CLAUDE_CODE_SESSION_ID" (a single key today)
- packages/fr/src/fr/run/telemetry.py:271 — attribute_dispatches
- packages/fr/src/fr/run/telemetry.py:327 — current_session reads only SESSION_ID_ENV
- packages/fr/src/fr/run/telemetry.py:341-351 — dispatched_from_this_session
- packages/fr/src/fr/run/telemetry.py:462 — ROUND_NEUTRAL_TOOLS
- packages/fr/src/fr/run/telemetry.py:485 — answered_rounds_since
- packages/fr/src/fr/run/telemetry.py:573-582 — _this_session returns None off Claude Code
- packages/fr/src/fr/run/telemetry.py:585 — subagent_dispatch_since
- packages/fr/src/fr/run/telemetry.py:842 — read_file_since
- packages/fr/src/fr/run/telemetry.py:953 — _executes
- packages/fr/src/fr/run/telemetry.py:961 — shell_named_since
- packages/fr/src/fr/run/telemetry.py:993 — witness_transcript (Path | False | None)
- packages/fr/src/fr/run/telemetry.py:1012 — orchestrator_wrote_since
- packages/fr/src/fr/run/telemetry.py:1179 — OPENCODE_DB_ENV = "FR_OPENCODE_DB"
- packages/fr/src/fr/run/telemetry.py:1215-1257 — _opencode_wrote_since, any top-level session, docstring at :1227
- packages/fr/src/fr/run/visual.py:418 — _unobservable names non-claude-code harnesses
- packages/fr/src/fr/run/visual.py:444-488 — _witness_file (reviewer / holder / orchestrator choice, main_thread at :384)
- packages/fr/src/fr/run/visual.py:457 — imports _this_session, attribute_dispatches, witness_transcript
- packages/fr/src/fr/commands/run_cmd.py:1113-1238 — _gate_provenance (unobserved path returns the claim)
- packages/fr/src/fr/commands/run_cmd.py:1989 — _coverage_witness reads the review entry's block
- packages/fr/src/fr/commands/run_cmd.py:2096-2185 — _verify_reviewer (observed False refuses; None is unobserved)
- packages/fr/src/fr/commands/run_cmd.py:2188 — _same_agent
- packages/fr/src/fr/commands/run_cmd.py:2212 — _verify_tests_log
- packages/fr/src/fr/commands/run_cmd.py:2801-2805 — gh#537 guard, session recorded only on claude-code
- packages/fr/src/fr/commands/run_cmd.py:4524 — answered_by or "agent" (flag form)
- packages/fr/src/fr/commands/run_cmd.py:4994 — offered.pop("answered_by", "agent")
- packages/fr/src/fr/commands/run_cmd.py:5652-5655 — fr run check prints "no operator answered it"
- packages/fr/src/fr/commands/run_cmd.py:5717-5726 — fr run gates prints the same sentence
- packages/fr/src/fr/usage/capture.py:96 — candidates (cursor, bindings, current_session)
- packages/fr/src/fr/usage/sources.py:40 — sessions_of yields (harness, session)
- packages/fr/src/fr/usage/readers/opencode.py:60 — open_ro
- packages/fr/src/fr/usage/readers/opencode.py:120-144 — read sums the session and its direct children (s.id = ? OR s.parent_id = ?)
- packages/fr/src/fr/isolation/sessions.py:53 — ambient binding via current_session
- packages/fr/src/fr/journal/operator.py:42 — operator_answered_since import
- packages/fr/src/fr/record/pr_body.py:94 — _findings renders every journal's findings with verdicts
- packages/fr/src/fr/commands/journal_cmd.py:490 — "reclassified by the orchestrator" rendering
- packages/fr/src/fr/run/model.py:88-93 — UnitAttempt.agent / agent_type / session exist
- packages/fr/src/fr/harness/detect.py:50,102 — OPENCODE* detection, FR_HARNESS override
- packages/fr/src/fr/harness/observe.py:107-160 — OpenCode parity observed by marker comments in index.ts
- packages/fr/src/fr/harness/parity.yaml:192,215,238,261,309,362,412 — operator-gate, out-of-scope-operator-guard, spec-review-independence, deliver-tests-provenance (opencode enforced), visual-evidence, dispatch-holder-identity, usage-capture rows
- packages/fr-opencode-plugin/src/index.ts:120-183 — plugin hooks (event, tool.execute.before), no shell.env yet; session.ts is new
- packages/fr-opencode-plugin/src/claim.ts:109 — claims with --agent <child sessionID>
- scripts/deliver-opencode-plugin.sh — exists
- plugins/super-fr/skills/fr-goal/SKILL.md:55,59,98 — "Harness — questions", §2 "Harness — spec reviewer", §6 review-phase
- plugins/super-fr/workflows/fr-goal.yaml:185 — review-phase evidence [review, reviewer, findings, visual]
- tests/fixtures/usage/opencode/build.py — exists; NOTE.md is tests/fixtures/usage/NOTE.md (opencode sha at :73)
- tests/fixtures/transcripts/claude-code-subagent.jsonl — exists (last text block is a handback stub)

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-29T11:49:57+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: #823's close rule (closes when the live row flips, not at merge) is neither a requirement nor deferred

Added to `## Deferred from input` with its reason: the batch's delivery rules require `Closes derio-net/super-fr#823`, and the live claim stays owed as the post-merge row `opencode-observe-take10-rerun`.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-29T11:49:57+00:00 state=open resolves=s2 unconfirmed=true -->
### s2-resolved · finding [unconfirmed] · resolves s2: R3 narrows 'records the child's session id on the attempt' with two added conditions

Built as R3 reads: every dispatch is mapped to its child session (`dispatches()`, used by the reviewer, return and witness checks), but fr fills an unclaimed attempt's `agent` only when exactly one matching child exists; zero or several leave the attempt unchanged.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-29T11:49:57+00:00 state=open resolves=s3 unconfirmed=true -->
### s3-resolved · finding [unconfirmed] · resolves s3: R13 swaps a 'captured opencode.db fixture (redacted)' for a composed, fictional one

Built as a composed fixture (`build.py`) whose DDL and JSON shapes are copied from the live 2026-09-29 OpenCode 1.18.33 capture, every identity fictional — the repo's existing fixture practice (`tests/fixtures/usage/NOTE.md`); no captured operator database is committed.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-29T11:49:57+00:00 state=open resolves=s4 unconfirmed=true -->
### s4-resolved · finding [unconfirmed] · resolves s4: R6 extends the reviewer-id refusal to spec-review; its sources only name review-phase

Built: the reviewer-id refusal applies at spec-review on OpenCode as well as review-phase (it already applies at both on Claude Code), because R5 must read the named reviewer's own return.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-09-29T11:49:57+00:00 state=open resolves=s5 unconfirmed=true -->
### s5-resolved · finding [unconfirmed] · resolves s5: R11 widens the wording fix to `fr run check` and adds a new claimed-operator sentence

Built: `fr run check` gets the same wording change as `fr run gates` (it prints the same sentence today), plus a line for a claimed, unobserved `operator`.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-09-29T11:49:57+00:00 state=open resolves=s6 unconfirmed=true -->
### s6-resolved · finding [unconfirmed] · resolves s6: §B's OpenCode workspace binding on `fr run start` / `fr isolation up` has no requirement

Built: OpenCode sessions bind their workspace through the ambient `current_session` read in `isolation/sessions.py`, so they appear in `fr isolation status`, usage `candidates()` and the Bash guard's sentinel list, as Claude Code sessions do.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-09-29T11:49:57+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: d-parity-partial's 'a follow-up flips parity to enforced' is missing from the spec

§G now names the owner: a follow-up issue filed at `deliver`, linked from the PR body, flips the OpenCode parity cells to `enforced` once the live row flips (Test Plan 13).

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-09-29T11:49:57+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: §A and §E name functions that do not exist; one gate is left off the protocol list

§A/§E now name `_gate_provenance` (:1113) and `resolve_in_process` (:4965); `_wrote_before` (:2197) is on §A's protocol list.

<!-- fr:journal kind=finding scope=spec id=s9-resolved created=2026-09-29T11:49:57+00:00 state=fixed resolves=s9 -->
### s9-resolved · finding [fixed] · resolves s9: On Claude Code, the subagent's last assistant `text` block is not what it returned

§A: on Claude Code `returned` is the dispatch's `tool_result` text in the parent transcript, paired by toolUseId — never the subagent file's handback stub; Test Plan 2 asserts it.

<!-- fr:journal kind=finding scope=spec id=s10-resolved created=2026-09-29T11:49:57+00:00 state=fixed resolves=s10 -->
### s10-resolved · finding [fixed] · resolves s10: The reviewer returns the coverage block indented inside YAML; §D's normalisation cannot match it

§D: fr parses the reviewer's YAML return and compares the `kind: review` entry's body (dedenting the fence if the return does not parse); Test Plan 3 has an honest YAML-wrapped return that resolves.

<!-- fr:journal kind=finding scope=spec id=s11-resolved created=2026-09-29T11:49:57+00:00 state=fixed resolves=s11 -->
### s11-resolved · finding [fixed] · resolves s11: deliver-tests-provenance 'stays enforced' but regresses to unobserved on OpenCode without the plugin

§A: with no session id, `wrote_windows` keeps today's any-top-level-session reading (`opencode_unscoped`), so deliver-tests-provenance stays enforced without the plugin; Test Plan 1 covers it.

<!-- fr:journal kind=finding scope=spec id=s12-resolved created=2026-09-29T11:49:57+00:00 state=fixed resolves=s12 -->
### s12-resolved · finding [fixed] · resolves s12: The review-phase findings check assumes one reviewer; #816 had three

§D: every non-executor child dispatched since the unit opened is a reviewer owing a block; fr checks the union; ids are `p<N>-r<k>` for one reviewer and `p<N><letter>-r<k>` for several (fr-goal §6 assigns the letters); a duplicate id across returns is refused; Test Plan 3 covers three reviewers.

<!-- fr:journal kind=finding scope=spec id=s13-resolved created=2026-09-29T11:49:57+00:00 state=fixed resolves=s13 -->
### s13-resolved · finding [fixed] · resolves s13: The agent-type tier stripping must reach both `_same_agent`s and the phase-executor check

§C: one normaliser `agent_name()` (qualifier and tier suffix dropped) used by both `_same_agent`s and the phase-executor check at run_cmd.py:2148; Test Plan 3 names an OpenCode tier executor as reviewer and is refused.

<!-- fr:journal kind=finding scope=spec id=s14-resolved created=2026-09-29T11:49:57+00:00 state=fixed resolves=s14 -->
### s14-resolved · finding [fixed] · resolves s14: The Test Plan misses behaviour the design promises

Test Plan items 2, 4, 5, 6, 8, 9 and 10 now cover the Claude Code return, R5/R7 on Claude Code, the holder fill, the orchestrator-vs-reviewer PNG read, the flag-form refusal, the unobserved-return warning and the R8 PR-body assertion.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-09-29-opencode-observe-p2 created=2026-09-29T11:52:25+00:00 -->
### phase-split-2026-09-29-opencode-observe-p2 · decision · ask: reviewer identity and returns (R3, R5-R8) are independently reviewable from the protocol
