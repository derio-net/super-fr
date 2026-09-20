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
