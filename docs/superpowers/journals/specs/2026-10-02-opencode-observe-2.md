# Journal: 2026-10-02-opencode-observe-2

<!-- fr:journal kind=discovery scope=spec id=input-batch-brief created=2026-10-02T19:06:33+00:00 input=true -->
### input-batch-brief · discovery · Operator brief — batch opencode-observe-2 (verbatim)

/fr-goal fr observes OpenCode sessions (run session, each child, what it returned); question answers, reviewer ids, cost and screenshot reads stop being the orchestrator's word

Batch `opencode-observe-2` of derio-net/super-fr: 6 issues, delivered as ONE pull request.

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

## super-fr#848: fr run cost --recompute attributes a foreign Claude Code transcript to an OpenCode run
fr run cost --recompute attributes a foreign Claude Code transcript to an OpenCode run (take 11, fr arm), so a cost is shown that the run never incurred.
Note: Found by take 11 on 5.0.0. Same family as #637; belongs with the re-scoped #823.

## super-fr#561: parity.yaml: Hermes edit gate declared enforced while OpenCode is partial for the same shell-write gap
`parity.yaml` declares the edit gate `partial` on OpenCode (bash ungated) but `enforced` on Hermes, whose `pre_tool_call` covers only `write_file|patch` (`.hermes/config.snippet.yaml:13-14`); terminal writes reach only the bash guard (`partial`). Filed from the super-fr#564 review; the prose there already states the gap.
Note: Declaration-only fix (Hermes -> `partial` with a scope_note), plus `fr harness parity --check`'s observed side. Batch with super-fr#563.

## Why these belong together
Wave 11 of the post-talk closing order (2026-10-02). The one feature batch. fr learns the OpenCode run session and each child, so question answers, reviewer ids, cost and screenshot reads stop being the orchestrator's word. Draft PR #837 is the salvage; it must not touch the input.

## Delivery rules
- Work on branch `feat/batch-opencode-observe-2`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#823
  Closes derio-net/super-fr#797
  Closes derio-net/super-fr#809
  Closes derio-net/super-fr#816
  Closes derio-net/super-fr#848
  Closes derio-net/super-fr#561
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=d-salvage created=2026-10-02T19:06:33+00:00 -->
### d-salvage · decision · Salvage: port #837, then finish

Round 1 Q1 → 'Port, then finish': new branch from main; #837's new modules/fixtures come over verbatim (observed.py, review_return.py, fixture builder, plugin session.ts), its run_cmd/telemetry hunks are re-applied by hand onto current main, the R5 input-coverage commit is dropped; phase 2 is reviewed afresh here, phase 3 built new.

<!-- fr:journal kind=decision scope=spec id=d-carry-837 created=2026-10-02T19:06:33+00:00 -->
### d-carry-837 · decision · Carry #837's operator decisions, drop coverage

Round 1 Q2 → 'Carry all, drop coverage': d-seam (one harness-neutral ObservedSession protocol), d-run-session (plugin shell.env exports FR_OPENCODE_SESSION_ID; fr walks parent_id to the top-level session), d-findings-block + d-finding-ids (reviewer ends with a findings block, brief-prescribed ids p<N>-r<k>, each a phase-N plan-journal finding with the same scope), d-answered-by-refuse (no default to agent; refuse on every harness), d-every-harness (return checks wherever the return is readable), d-parity-partial (OpenCode cells → partial + a verify: post-merge row re-running take 10 B; a follow-up flips to enforced) are this run's decisions unchanged. d-coverage-refuse is dropped with the input gates (#851).

<!-- fr:journal kind=decision scope=spec id=d-attribution created=2026-10-02T19:06:33+00:00 -->
### d-attribution · decision · #848: positive-evidence attribution only

Round 1 Q3 → 'Positive evidence only': --recompute (and fr archive's capture) use only sessions the cursor's attempts or the workspace bindings name, each with its own recorded harness; the ambient session is added only at a step's own resolve/advance capture. Nothing found → unavailable: no session found.

<!-- fr:journal kind=decision scope=spec id=d-hermes-partial created=2026-10-02T19:06:33+00:00 -->
### d-hermes-partial · decision · #561: Hermes edit gate → partial

Round 1 Q4 → 'Hermes → partial': the Hermes cell of fr-isolation-required becomes partial with a scope_note naming the write_file|patch scope and the terminal/execute_code gap.

<!-- fr:journal kind=decision scope=spec id=d-close-837 created=2026-10-02T19:06:33+00:00 -->
### d-close-837 · decision · Close #837 as superseded when this draft PR opens

Round 1 Q5 → 'Close as superseded': when this batch's draft PR opens, close #837 with a comment linking it; its branch and workspace stay until this one merges, then go with the close-out.
