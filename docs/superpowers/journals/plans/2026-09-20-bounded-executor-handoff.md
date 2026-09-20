# Journal: 2026-09-20-bounded-executor-handoff

<!-- fr:journal kind=discovery scope=plan id=norefactor-P5.T2 created=2026-09-20T14:10:20 phase=5 -->
### norefactor-P5.T2 · discovery · no-refactor-because P5.T2 (phase 5)

P5.T2 files the two follow-up issues d4 owes. Its two steps are a pair of `gh issue create` calls — there is no code, no duplication and nothing to extract, so a refactor beat would be an empty step, which is exactly what the refactor-or-justify rule says not to author. Kept as two steps rather than one because the issues are separate artifacts with separate bodies, and rather than three because the third would be ceremony. Tagged --phase 5 deliberately: this plan's own d3 decision is that a justification entry carries its phase, so it is bounded by the handoff rules it is shipping.

<!-- fr:journal kind=discovery scope=plan id=dcd55c9ab864 created=2026-09-20T14:14:25 phase=1 -->
### dcd55c9ab864 · discovery · no-refactor-because P1.T1 (phase 1)

GREEN itself already did the extraction: `append_journal_entry` was promoted from a private `_append_entry` in `journal_cmd.py` into `fr.journal.model` so `fr journal add`, `fr journal resolve`, and `build_plan_journal` share the literal same writer function (not merely the same shape). No further duplication exists between `build_plan_journal` and `assert_no_repo_mutation` in test_support.py to extract.

<!-- fr:journal kind=discovery scope=plan id=p1t2s3-shapes-not-seen created=2026-09-20T14:24:23 phase=1 -->
### p1t2s3-shapes-not-seen · discovery · shapes not seen in the captured fixture, and whether phase 4 must handle them (phase 1)

Three concrete shapes P1.T2.S3 asks about, checked against BOTH the fixture and the full source sessions it was reduced from:

1. A session with NO subagent dispatch. NOT a real gap: the fixtures own orchestrator-side records (isSidechain:false, no agentId) already ARE that shape in isolation, and a V2 reader that finds zero Agent tool_use / zero subagents/*.jsonl files for a run simply sums only the isSidechain:false records for that phase — no special-casing needed, it is the degenerate case of the general per-unit walk, not a separate code path.

2. A record with usage absent. Non-assistant record types (last-prompt, mode, permission-mode, atis-latch, user, system/turn_duration) all lack message.usage and are already present in the fixture (rows 0-5, 8) — that shape IS seen and IS handled (a V2 parser must select type=="assistant" before reading usage, per finding 5 in the fixtures NOTE.md). What I have NOT seen, in the fixture or in the full 157-assistant-record source session it was drawn from (checked directly: 0 of 157 assistant records lack usage), is an ASSISTANT record with usage itself missing (e.g. an interrupted stream or an error response that never completed the API call). Not handled today, and cannot be proven safe by a capture that never observed it — the honest answer is phase 4s parser must treat a missing usage on an assistant record as skip-and-continue (contribute nothing to the sum) rather than KeyError, as a defensive default, and this stays a documented assumption, not a verified one, until a real instance is captured.

3. A transcript written while cwd was the fr worktree rather than the base clone. NOT seen anywhere on this machine: every ~/.claude/projects/<slug> directory name is derived from a REAL launch cwd, and none corresponds to a worktree path (grepped) — because fr-phase-executor (the one agent that works inside a worktree) is the carve-out that explicitly does NOT get its own Claude Code session/worktree; it cd/s into the shared worktree via Bash inside a session whose cwd was fixed at the orchestrators base-clone launch. Directly confirmed on a captured record (fixture rows 9-11, NOTE.md finding 3): a subagent dispatched with instructions to cd into a worktree and that did all its real work there still carries cwd=<base clone path> on every one of its own transcript records. So this shape is not merely unseen, it is actively CONTRADICTED by every real subagent record examined, and a V2 reader must not use cwd to attribute a record to a worktree/phase at all.

<!-- fr:journal kind=finding scope=plan id=f-p1-sidechain-file-split created=2026-09-20T14:24:44 phase=1 state=open -->
### f-p1-sidechain-file-split · finding [open] · spec Sec5.C attribution assumption contradicted by a real transcript: subagent turns live in a separate file, not inline via parentUuid (phase 1)

Sec5.C B1 assumes one shared per-session jsonl stream where "subagent turns carry isSidechain: true" and "a dispatch is attributed by walking parentUuid back to the Agent tool_use that started it." A real capture (tests/fixtures/transcripts/claude-code-session.jsonl + NOTE.md, built from a genuine ~/.claude/projects/<slug>/<session-id>.jsonl and its companion subagents/agent-<agentId>.jsonl) refutes the shared-stream half: EVERY record in the orchestrators own session file carries isSidechain:false; isSidechain:true only appears in the separate per-agent files under subagents/. The real correlation is file-to-file: the orchestrators Agent tool_use id (a toolu_... string) matches the companion subagent files own meta.json toolUseId field -- parentUuid inside the subagent file only chains that single subagents own turns (starts at null, never crosses into the orchestrators file). Also: sessionId on a subagent record is the ORCHESTRATORS session id, not a new one -- the subagents own identity is the agentId field, absent on orchestrator records. Whichever phase builds the V2 Claude Code transcript reader (Sec5.C) needs this fix: locate a runs subagents/ directory and pair each agent-<id>.jsonl with its meta.json toolUseId against the orchestrators own Agent tool_use records, rather than filtering one file by isSidechain plus walking parentUuid. The documented fallback (Sec5.C, timestamp-window attribution) still works unchanged since it never depended on parentUuid.

<!-- fr:journal kind=discovery scope=plan id=4d85b64135e0 created=2026-09-20T14:24:59 phase=1 -->
### 4d85b64135e0 · discovery · no-refactor-because P1.T2 (phase 1)

test_handoff_bound.py and test_transcript_fixture.py test unrelated things (a builder function vs. a static fixtures shape) with no shared setup worth extracting -- one uses tmp_path and fr.test_support, the other reads a fixed fixture path with no fixture/parametrization duplication between them. Nothing to clean.

<!-- fr:journal kind=finding scope=plan id=r1-c1 created=2026-09-20T14:51:19 phase=1 state=fixed -->
### r1-c1 · finding [fixed] · CRITICAL: the leak test named the very identities it was scrubbing, in a public repo (phase 1) (phase 1)

test_transcript_fixture.py asserted absence by listing the literal strings — the operator's username and two third-party names (an employer and a client outside the derio-net org) reachable only from this session's additionalWorkingDirectories. The capture note quoted the username twice as well. third-party-privacy.md's whole point is that evidence keeps the shape and drops the identity; the test that existed to prevent the leak was committing one. FIXED by asserting the PROPERTY instead: no real macOS home path survives, and no home directory other than the placeholder appears, scanned across every file in the fixture directory including the note. The commit was amended rather than fixed forward, because the branch was never pushed — fixing forward would have left the leaking blob in history and pushed it.

<!-- fr:journal kind=finding scope=plan id=r1-c2 created=2026-09-20T14:51:19 phase=1 state=fixed -->
### r1-c2 · finding [fixed] · CRITICAL: the fixture merged two streams into a file shape the harness never emits (phase 1) (phase 1)

All 12 records were genuine, but the FILE was a construction: no Claude Code transcript contains both isSidechain true and false records — which is this phase's own headline finding. Worse, a green test asserted both values are present in one file, pinning the refuted assumption, and 04.yaml P4.T1.S1 pointed phase 4 straight at it. A phase-4 parser written against that fixture would filter one stream, pass its tests, and read zero subagent tokens from every real transcript on disk. FIXED by splitting into claude-code-session.jsonl (9 orchestrator records, isSidechain false throughout) and claude-code-subagent.jsonl (3 records, true throughout, carrying agentId), with tests asserting each stream's real invariant, and by rewriting P4.T1.S1 to forbid the single-file isSidechain filter explicitly.

<!-- fr:journal kind=finding scope=plan id=r1-c3 created=2026-09-20T14:51:20 phase=1 state=fixed -->
### r1-c3 · finding [fixed] · CRITICAL: the phase reported its gate green while ruff format --check was red (phase 1) (phase 1)

tests/unit/test_transcript_fixture.py failed 'uv run ruff format --check packages/ tests/', which .github/workflows/ci.yml's lint job runs verbatim. Both P1.T1.S3 and P1.T2.S3 name the format gate, and S3's text explicitly cites r6-c1 — the recorded prior instance of exactly this. The phase still closed all six steps and the cursor advanced. Second instance of the same defect in this repo. FIXED by running ruff format and re-verifying; the executor ran ruff check (which passes) but not ruff format --check (which does not), so the two are not interchangeable and the step text should say which.

<!-- fr:journal kind=finding scope=plan id=r1-i1 created=2026-09-20T14:51:20 phase=1 state=fixed -->
### r1-i1 · finding [fixed] · build_plan_journal's id derivation collided on entries differing only in phase (phase 1) (phase 1)

The helper hashed kind|plan|fixture|title|body — the CLI's content-addressed scheme with the slug replaced by a constant, ignoring phase and state, and with no duplicate guard. Content-addressing is right for the CLI (re-adding an identical entry is idempotent) and wrong for a fixture builder whose job includes emitting N entries that differ only in phase. 02.yaml P2.T1.S2 asks for exactly that shape, so phase 2 would have hit a JournalParseError from the parser, at a distance from the cause. FIXED: the entry's index disambiguates, the builder raises a named ValueError on a duplicate id before writing, and the docstring no longer claims to mirror the CLI's derivation — the WRITER is shared, the id scheme deliberately is not.

<!-- fr:journal kind=finding scope=plan id=r1-i2 created=2026-09-20T14:51:20 phase=1 state=fixed -->
### r1-i2 · finding [fixed] · The handoff assertion could not fail — compose_handoff([]) satisfies it (phase 1) (phase 1)

test_build_plan_journal_composes_a_real_handoff asserted only that the output starts with '# Handoff (phase 3)', which an EMPTY entry list also produces. It proved nothing about the builder's entries reaching the handoff, and its parse check filtered to findings, so the decision entry could vanish silently. FIXED: all entries round-trip with kind/phase/state asserted in order, both titles must appear in the composed handoff, and a second test pins the output against serialize_entry directly so a hand-rolled markdown shortcut fails rather than producing plausible text.

<!-- fr:journal kind=finding scope=plan id=r1-i3i4i5 created=2026-09-20T14:51:21 phase=1 state=fixed -->
### r1-i3i4i5 · finding [fixed] · The capture note omitted the artifact its headline finding rests on, and misdescribed two things (phase 1) (phase 1)

I3: the meta.json carrying toolUseId was not committed, so nothing in the repo could support the correlation claim and phase 4 had no fixture for the CORRECT attribution — only the wrong one. The note also gave two wrong paths (the real layout is <session-id>/subagents/agent-<agentId>.jsonl beside the <session-id>.jsonl, and the metadata file is agent-<agentId>.meta.json, not a bare meta.json), which would send a phase-4 glob nowhere. FIXED: captured as claude-code-subagent.meta.json, with a test asserting its toolUseId matches an Agent tool_use id in the orchestrator fixture — an assertion with real teeth. I4: the note claimed a pure substring redaction; the records are re-serialized with json.dumps, so whitespace differs from source bytes while content canonicalises equal. Corrected, since the note is the provenance record a later reader trusts. I5: the mode/permission-mode/atis-latch records were called session-start metadata but are lines 980-982 of 984. Corrected.

<!-- fr:journal kind=discovery scope=plan id=r1-selfcheck created=2026-09-20T14:51:21 phase=1 -->
### r1-selfcheck · discovery · The redaction test caught its own explanation twice, which is the point (phase 1)

Writing the property-based leak assertion made it fire on the capture note itself: first because the note's Redaction section quoted the /Users/ prefix while explaining that no such path may survive, then because the regex /home/[^/\"\s]+ swallowed a trailing markdown backtick and the angle brackets of a /home/<name> placeholder. Both were fixed rather than excluded — the note is scanned like every other file in the fixture directory, so the explanation has to obey the rule it explains. Recorded because a narrower fix (skip the .md) was available and would have left the note free to leak.

<!-- fr:journal kind=discovery scope=plan id=08ce085e2301 created=2026-09-20T15:06:34 phase=2 -->
### 08ce085e2301 · discovery · P2.T2 measurement: the bound is real (24-41% cut) but lands ~3k above the spec's prediction, and the reason is A2's residual, not a modelling error (phase 2)

Same real journal as spec §2 (docs/superpowers/implemented/journals/plans/2026-09-18-harness-parity-matrix.md, unchanged since ea0b521), same command. BEFORE re-measured on this branch with the pre-change model.py checked out, so the comparison is apples-to-apples rather than copied from the spec.

phase | before | after | cut
1 | 35,080 | 26,593 | -24.2%
2 | 47,028 | 32,838 | -30.2%
3 | 46,889 | 30,328 | -35.3%
4 | 50,439 | 34,404 | -31.8%
5 | 66,228 | 39,694 | -40.1%
6 | 83,132 | 49,110 | -40.9%
7 | 68,908 | 49,874 | -27.6%

My BEFORE column reproduces the spec's table exactly, +1 char per row (the spec used a command substitution, which strips the trailing newline). One discrepancy I could not reproduce: the spec calls the raw journal '728 lines, 129,972 chars'; on disk it is 729 lines / 130,016 chars and git says the file has not been touched since it was archived. 44 chars, immaterial to every conclusion, but recorded rather than smoothed over.

Against §5.A3's predictions — phase 6 near 46k, phase 1 near 24k — the real figures are 49,110 and 26,593: the direction and the magnitude hold, and phase 1 -> phase 6 growth is 1.85x against the predicted 1.9x, but both phases land ~2.5-3k HIGH. The spec committed to reporting the measurement, not to being right, so: the prediction was optimistic by about 6%, consistently.

The cause is measurable, not mysterious. Categorising what still renders in full at phase 6 (49,110 chars total, 38,434 of it full entries):

  discovery (tagged, dependency phase)   13 entries  16,368 chars
  UNTAGGED discovery                     16 entries  13,281 chars
  decision (tagged, dependency phase)     7 entries   8,785 chars
  open findings                           0 entries        0 chars

§5.A3's table assumed the no-refactor bookkeeping entries were phase-TAGGED, and split them 9-stay / 5-collapse (6,557 chars residual, §5.A4). In this real journal 17 such entries exist and 14 of them render in full — because most are UNTAGGED, and an untagged entry is relevant at every phase by rule 3. So the extra ~3k is §5.A2's residual (untagged entries unbounded forever), which phase 3 attacks, not a miss in the state-first collapse. Phase 2 did the thing phase 2 was for: every closed finding, including the 26 on dependency phases, now costs one line.

<!-- fr:journal kind=discovery scope=plan id=ec322bb84636 created=2026-09-20T15:06:52 phase=2 -->
### ec322bb84636 · discovery · The one pre-existing test that changed behaviour, named rather than edited quietly (#464 comment item 11) (phase 2)

Green everywhere after a contract change is the suspicious result, so I ran the whole journal suite against the new rule expecting a failure, and got exactly one:

  tests/unit/test_journal_model.py::TestHandoff::test_dependency_scoped_entries_render_in_full
  AssertionError: assert 'relevant history' in out

'relevant history' is the body of fixture entry f-dep — a finding with state=fixed, tagged to phase 1, composed at phase 2 with depends_on=(1,). That assertion WAS the defect, in test form: it said a closed finding on a dependency phase must render in full, which is the ~30k of phase 6's 83k handoff that spec §2 measured. It should fail, and it did.

Handled by splitting rather than deleting: the original test keeps its three still-correct assertions (dep decision, dep discovery, untagged decision all render in full — dependency scoping survives for the kinds it was ever right for), and a new sibling test_a_closed_finding_on_a_dependency_phase_collapses asserts the inverse for f-dep plus the exact one-line form, with a docstring recording that it used to assert the opposite and why that was wrong. Deleting the assertion would have left no test covering f-dep at all.

Nothing else moved. In particular test_a_resolved_finding_leaves_the_open_findings_section (phase 7's fold test) stays green: its resolution record now reaches the handoff as a collapsed line instead of full context, and its assertion is on the TITLE ('resolves f1'), which the one-line form keeps — a behaviour change the existing assertion is indifferent to, checked deliberately rather than assumed. The CLI-level TestHandoff in test_journal_cmd.py has no fixed-finding-on-a-dependency-phase in its fixture, so it could not have caught this; that gap is now covered at the model level.

<!-- fr:journal kind=finding scope=plan id=78654207c227 created=2026-09-20T15:07:13 phase=2 state=open -->
### 78654207c227 · finding [open] · The collapsed one-line form prints the entry's OWN state, so a finding closed by a resolution record reads '[open]' in Earlier history (phase 2)

_handoff_line (packages/fr/src/fr/journal/model.py) renders '[{entry.state}]' — the field on the entry — while the decision to collapse it now uses the EFFECTIVE state from open_finding_ids. The two disagree for exactly the shape fr journal resolve creates: a finding written state=open and later closed by an appended resolution record keeps state=open on its own entry forever (the journal is append-only, by design), so it collapses correctly but announces itself as open.

Not introduced by this phase — such a finding on a NON-dependency phase already collapsed with the same wrong label — but this phase makes it the common case, because every closed finding now collapses regardless of phase. Measured on the real journal used for the P2.T2 measurement: 10 of its findings have state=open on their own entry and are effectively closed. A phase-6 executor reading that handoff sees 10 one-line entries labelled [open] and nothing marking them resolved, which is precisely the 'chase a bug that no longer exists' cost this phase exists to remove — recovered in a cheaper form rather than eliminated.

Left OPEN rather than fixed here on purpose: the fix (thread effective_finding_states into _handoff_line, or render the effective state) changes _handoff_line's output contract, which is pinned by test_collapsed_lines_carry_state_and_phase and by the new phase-2 assertions, and no step of phase 2 asks for it. tests/unit/test_handoff_bound.py::test_a_resolution_record_collapses_and_so_does_what_it_closed currently PINS the present behaviour with a comment pointing here, so whoever fixes it will see this entry fail loud rather than silently. Small, self-contained, and a good candidate for the orchestrator to schedule into phase 3 or a follow-up.

<!-- fr:journal kind=decision scope=plan id=97092f14683b created=2026-09-20T15:11:55 phase=2 -->
### 97092f14683b · decision · The acceptance row handoff-closed-entries-bounded stays not-implemented at the end of phase 2, on purpose (phase 2)

fr plan edit --complete-phase 2 warned that the row is still not-implemented. Left as-is rather than flipped: P5.T3.S1 owns flipping all four rows of this plan in one place, with --notes and --level refs, and flipping one early would split the transition across two phases and leave the three committed reports regenerated twice. The verification the row waits on now exists — tests/unit/test_handoff_bound.py::test_a_closed_entry_costs_a_constant_regardless_of_its_body_size plus its inverse guard test_but_growing_an_open_findings_body_does_grow_the_handoff — so phase 5 has the refs it needs and the row's bar (O(1) per closed entry, explicitly NOT non-monotonic growth) is exactly what those two assert.

<!-- fr:journal kind=finding scope=plan id=r2-i1 created=2026-09-20T15:27:08 phase=2 state=fixed -->
### r2-i1 · finding [fixed] · REGRESSION: a re-opening resolution record collapsed, dropping the only text saying why (phase 2) (phase 2)

renders_full = e.resolves is None and e.id in still_open collapses ANY entry carrying resolves. But re-opening is a first-class documented path (journal_cmd.py:81 and :190, and effective_finding_states' own docstring). Reproduced live: the original report rendered in full under '### f1 · finding [fixed]' inside ## Open findings while the re-open reason was a one-liner with its body gone — the executor is told to act on something and not told what changed. A regression this phase introduced, covered by no test (verified: applying the fix left all 92 green, so the suite was indifferent). FIXED by asking the fold about the finding an entry SPEAKS FOR — its target when it resolves one, itself otherwise. Still one fold, still O(1) for closed entries since a re-opened finding is by definition open. The spec said 'or a resolution record, collapses', so the code was faithful and the blind spot was upstream; §5.A1 is corrected too.

<!-- fr:journal kind=finding scope=plan id=r2-i2 created=2026-09-20T15:27:08 phase=2 state=fixed -->
### r2-i2 · finding [fixed] · The shipped executor contract described a handoff that no longer exists, in five files (phase 2) (phase 2)

fr-phase-executor.md and its four .opencode mirrors told executors the handoff carries 'unrelated fixed history collapsed' — 'unrelated' being exactly the qualifier this phase removed. That is the text an executor is instructed to trust ('if the handoff is missing anything you need, STOP'), so a description that overstates what arrives is the failure mode the handoff exists to prevent. No later phase scheduled it: 03.yaml touches this file only for --phase N, 05.yaml only adds the sixth norm. FIXED in the canonical file only, mirrors regenerated via scripts/sync-opencode.py (--check clean). The same stale phrase in test_journal_model.py's TestHandoff docstring was corrected with it.

<!-- fr:journal kind=finding scope=plan id=r2-i3 created=2026-09-20T15:27:09 phase=2 state=fixed -->
### r2-i3 · finding [fixed] · A spec-committed test case was dropped without a record (phase 2) (phase 2)

Spec §5.A3 and §7 both commit to 'a second case pins the ceiling on a finding-dominated journal, where closed entries dominate and the handoff does flatten'. The phase shipped the O(1) test and its inverse guard — a different property: the guard asserts open bodies DO grow the handoff, not that entry-count growth flattens. grep for ceiling/flatten across all seven phase files found nothing scheduling it, and the decision entry deferring acceptance to P5.T3.S1 did not mention the drop. FIXED by writing it: test_a_finding_dominated_journal_flattens builds nine closed findings across nine phases and asserts phase 10's handoff is within 1.15x of phase 2's. Had it stayed missing, phase 5 would have flipped handoff-closed-entries-bounded to ci on evidence the spec said would exist and did not.

<!-- fr:journal kind=discovery scope=plan id=r2-measure-delta created=2026-09-20T15:27:09 phase=2 -->
### r2-measure-delta · discovery · The effective-state fix moved every measured figure by exactly +10 chars (phase 2)

Re-measured after the review fixes: 26,603 / 32,848 / 30,338 / 34,414 / 39,704 / 49,120 / 49,884 against the phase-2 figures of 26,593 / 32,838 / 30,328 / 34,404 / 39,694 / 49,110 / 49,874. Uniformly +10. That is the signature of the state-label fix landing on exactly the 10 findings finding 78654207c227 predicted: each collapsed line's label grew one character from [open] to [fixed]. A coincidental match would not be uniform across all seven phases, so the count is confirmed by the delta rather than only by the count query.

<!-- fr:journal kind=finding scope=plan id=78654207c227-resolved created=2026-09-20T15:27:09 state=fixed resolves=78654207c227 -->
### 78654207c227-resolved · finding [fixed] · resolves 78654207c227: The collapsed one-line form prints the entry's OWN state, so a finding closed by a resolution record reads '[open]' in Earlier history

Fixed inside phase 2's review rather than deferred. _handoff_line now takes an effective_state override and compose_handoff passes the folded state for collapsed findings; serialize_entry is deliberately untouched because it writes the append-only log, where each record must keep stating what was true when written. The review's point that deferring to 'phase 3 or a follow-up' was too loose is accepted: leaving it would have had phase 5 flip handoff-closed-entries-bounded to ci while the shipped handoff mislabelled ten closed findings as open, which contradicts the row.

<!-- fr:journal kind=discovery scope=plan id=p3-t1-s3-blast-radius created=2026-09-20T15:43:28 phase=3 -->
### p3-t1-s3-blast-radius · discovery · P3.T1.S3 blast-radius grep: exactly the two files the spec named, plus one plan_ops.py caller the grep scope excluded (phase 3)

Grepped plugins/ and .opencode/ for "journal add --scope plan" before touching prose, per the step. Found exactly what §5.A2 predicted: plugins/super-fr/agents/fr-phase-executor.md:53 and its four .opencode/agent/fr-phase-executor*.md mirrors (all identical, sync-opencode-generated). No other plugin/mirror-tree caller matched. Widening the grep beyond plugins/.opencode (not what the step literally asked, but the trap note said check the blast radius) found a third real caller outside that scope: packages/fr/src/fr/plan_ops.py's refactor-or-justify ReviewIssue message (_refactor_issues) suggested `fr journal add --scope plan --slug <plan> --kind discovery --title 'no-refactor-because <task_id>' --body <reason>` with no --phase — this is CLI-generated advisory text a human/agent would copy-paste and run, so it would now exit 2. Fixed it in the same commit (added --phase {n}, the phase number already in scope); no test pinned the old message so nothing else needed updating. Recording as a discovery rather than silently folding it into T2, since T2's own scope (per spec and plan step) named only the agent contract and fr-execute skill.

<!-- fr:journal kind=discovery scope=plan id=norefactor-P3.T1 created=2026-09-20T15:43:36 phase=3 -->
### norefactor-P3.T1 · discovery · no-refactor-because P3.T1 (phase 3)

The new pairing check (neither/both branches) is a single guarded block with no existing validation elsewhere in journal_cmd.py to share it with — --resolves validation and scope validation are each their own one-off checks with different shapes (existence lookup vs. enum membership vs. this two-flag XOR). Nothing to extract.

<!-- fr:journal kind=discovery scope=plan id=norefactor-P3.T2 created=2026-09-20T15:43:36 phase=3 -->
### norefactor-P3.T2 · discovery · no-refactor-because P3.T2 (phase 3)

Re-read all five changed copies (canonical agent + fr-execute skill + four .opencode/agent mirrors, sync-generated from the same two sources) as a whole. The --phase N addition reads as part of each existing sentence, not appended after a period; fr-execute stayed at exactly 120 lines (extended an existing line rather than adding one) and fr-phase-executor.md has no line-count cap. git diff --word-diff on both canonical files shows only the intended wording changed. Nothing to reword further.

<!-- fr:journal kind=discovery scope=plan id=p3-remeasure-unchanged created=2026-09-20T15:43:49 phase=3 -->
### p3-remeasure-unchanged · discovery · Re-measurement on the archived harness-parity journal is unchanged, as expected — this phase only changes what NEW writes must carry (phase 3)

Re-ran the spec §2 measurement (fr journal handoff --scope plan --slug 2026-09-18-harness-parity-matrix --plan-dir docs/superpowers/implemented/plans/2026-09-18-harness-parity-matrix --phase N for N in 1..7) after landing T1/T2. Result: 26,603 / 32,848 / 30,338 / 34,414 / 39,704 / 49,120 / 49,884 chars — byte-for-byte identical to phase 2's post-review figures (journal entry r2-measure-delta). This is correct, not a regression: that journal's 16 untagged discoveries (13,281 chars) were written before this phase existed, and P3 changes the CLI gate on NEW writes only — spec §5.A2 says explicitly 'no migration is owed'. The gap the phase set out to close (the ~6% over-prediction from A4's residual, which is untagged/no-refactor entries) does not shrink for this or any other already-written journal; it only stops growing for journals written from here on.

<!-- fr:journal kind=discovery scope=plan id=p3-self-check-level-ref created=2026-09-20T15:45:12 phase=3 -->
### p3-self-check-level-ref · discovery · Obeying my own new rule was mechanical, not awkward — one snag: the acceptance --level ref format (phase 3)

Every fr journal add call I made this phase already carried --phase 3, so the new gate never fired against me. The one real friction was adjacent: fr acceptance set-status --level rejected a pytest node-id (path::TestClass) at check time (not at set-status time — set-status writes unconditionally, fr acceptance check is what validates refs resolve), and merge_levels is deliberately additive/non-removing (fr.acceptance.edit.merge_levels docstring: 'removing a ref stays a deliberate edit, not something a status flip does silently'), so a bad ref can't be corrected by re-running set-status with a fixed one -- it only appends. Fixed by hand-editing matrix.yaml's one bad line to a plain file path before the row had been committed anywhere, then fr acceptance report --deterministic to resync the three committed reports. Recording so the next --level caller passes a bare repo:path, not a pytest node-id.

<!-- fr:journal kind=finding scope=plan id=p3-hermes-mirror-gap created=2026-09-20T15:48:14 phase=3 state=open -->
### p3-hermes-mirror-gap · finding [open] · AGENTS.md's canonical/generated-mirror section never mentions scripts/sync-hermes.py or .hermes/, even though a tripwire enforces it (phase 3)

Editing plugins/super-fr/skills/fr-execute/SKILL.md (canonical) and running scripts/sync-opencode.py (the mirror step AGENTS.md's 'Skills/rules: canonical source vs. generated mirrors' section documents, and the only one this phase's own plan step P3.T2.S1 names) left .hermes/skills/fr/fr-execute/SKILL.md stale, caught only by running the FULL pytest suite: tests/unit/test_tripwire_hermes_skills_sync.py::test_mirror_has_no_drift failed. AGENTS.md's mirror section (grep -n hermes AGENTS.md: three hits, none in that section) documents .opencode/ generation via scripts/sync-opencode.py but says nothing about scripts/sync-hermes.py or .hermes/skills+.hermes/SOUL.d as a third mirror needing the same treatment — an executor following that section alone (as I did) ships stale Hermes prose. Fixed here (scripts/sync-hermes.py run, .hermes/skills/fr/fr-execute/SKILL.md regenerated, tripwire green), but AGENTS.md's own doc gap is unaddressed and out of this phase's scope — recommend a follow-up adding sync-hermes.py to that section alongside sync-opencode.py.

<!-- fr:journal kind=finding scope=plan id=r3-i1 created=2026-09-20T16:05:53 phase=3 state=fixed -->
### r3-i1 · finding [fixed] · The flagship test passed only at 80 columns (phase 3) (phase 3)

The three consequence assertions matched rich's soft-wrapped stderr, so the wrap landed inside the asserted phrases at other widths. Reproduced before fixing: COLUMNS=70 turned test_neither_phase_nor_global_is_refused_naming_the_consequence red with nothing wrong in the code. This is the rich mid-phrase wrapping scar the repo already carries (#489, and the same idiom already in test_v2_pickup.py and test_plan_acceptance_links.py with the reason in the comment). FIXED by normalising whitespace first, which also strengthens the assertion: it now pins the whole phrase 'renders in full in every handoff, at every phase' rather than three fragments that could each match by coincidence. Verified green at COLUMNS 70/80/90/120.

<!-- fr:journal kind=finding scope=plan id=r3-i2 created=2026-09-20T16:05:54 phase=3 state=fixed -->
### r3-i2 · finding [fixed] · fr's own re-open advice told agents to run a command that now exits 2 (phase 3) (phase 3)

journal_cmd.py's --state validation error suggests 're-open a finding with fr journal add --resolves <id> --state open'. The phase fixed the analogous suggestion in plan_ops.py but not this one, inside the very file it was editing. Failure path: fr journal resolve --state open is refused, points the agent at fr journal add, which for --scope plan now exits 2 — two refusals and no way forward, on the re-open path fr-goal section 6 names explicitly. FIXED by appending --phase N to the suggested command.

<!-- fr:journal kind=finding scope=plan id=r3-i3 created=2026-09-20T16:05:54 phase=3 state=fixed -->
### r3-i3 · finding [fixed] · The acceptance row claimed prose coverage no test provided (phase 3) (phase 3)

handoff-entries-always-tagged flipped to ci with notes asserting 'root-cause prose (fr-phase-executor.md + fr-execute skill, mirrored) fixed in the same phase'. Nothing tested that: test_phase_executor_agent.py asserted only 'fr journal' in body. So the prose that CAUSED the untagged entries could be reverted by one length-trimming edit with all 3318 tests green and the row still ci — in a repo whose stated convention is that standing conventions are enforced by tests, not prose. FIXED with test_the_journal_example_carries_the_phase_flag pinning '--phase N' in the canonical agent file; the four mirrors are already covered by the sync tripwire.

<!-- fr:journal kind=finding scope=plan id=r3-i4m1 created=2026-09-20T16:05:54 phase=3 state=fixed -->
### r3-i4m1 · finding [fixed] · Two more assertions that could not fail, one of them mine (phase 3) (phase 3)

I4: test_phase_and_global_together_is_refused_as_contradictory asserted only exit_code == 2. Proved vacuous by mutation — replacing the whole message with 'nope' left all 40 tests green, the exact failure its sibling's own comment warns about. FIXED with a normalised assertion on the message. M1: --global outside plan scope was a silent no-op, so --scope spec --phase 3 --global wrote a phase-3-tagged entry while the operator asked for a global one; now refused with a message naming the flag as plan-only. Writing that test I made the same mistake a third time: I omitted _add's root argument, the command failed as a usage error, exit code was 2 anyway, and the exit-code assertion passed. Only the substance assertion caught it — a live demonstration, inside the fix for it, of why the exit-code-only assertion was worth finding.

<!-- fr:journal kind=finding scope=plan id=p3-hermes-mirror-gap-resolved created=2026-09-20T16:05:55 state=fixed resolves=p3-hermes-mirror-gap -->
### p3-hermes-mirror-gap-resolved · finding [fixed] · resolves p3-hermes-mirror-gap: AGENTS.md's canonical/generated-mirror section never mentions scripts/sync-hermes.py or .hermes/, even though a tripwire enforces it

FIXED rather than left for a follow-up. AGENTS.md's 'canonical source vs. generated mirrors' section documented scripts/sync-opencode.py and never mentioned scripts/sync-hermes.py or .hermes/, though test_tripwire_hermes_skills_sync.py enforces it. An agent following AGENTS.md exactly would edit a canonical skill, run sync-opencode, pass every documented check and ship a stale Hermes mirror — which is how phase 3 found it, via the full suite rather than the documented gate list. The section now names the third tree, its script and its tripwire, and says to run both scripts. This is the same class as the defect the PR is about: the gap was in the instructions the next agent inherits, not in anyone's care.

<!-- fr:journal kind=discovery scope=plan id=r3-m2-correction created=2026-09-20T16:05:55 phase=3 -->
### r3-m2-correction · discovery · Correcting p3-self-check-level-ref: matrix refs DO support a precise anchor (phase 3)

The phase-3 entry p3-self-check-level-ref concluded 'the next --level caller passes a bare repo:path, not a pytest node-id'. That is the wrong lesson. fr.acceptance.model.split_ref partitions on '#', and existing rows use the form <path>#TestClass::test_name. The failure was passing '::' with no '#', not that precision is unsupported. Recorded as a correction rather than by editing the original entry, because the journal is an append-only log — and left in place because a future reader hitting the same error will find both.
