# Journal: 2026-09-23-archive-merge-evidence

<!-- fr:journal kind=discovery scope=plan id=1976193fd0f3 created=2026-09-23T16:58:49 phase=1 -->
### 1976193fd0f3 · discovery · no-refactor-because P1.T1 (phase 1)

P1.T1 is the red half of red-green-refactor: it only writes failing tests. The refactor step lives at the end of the green task P1.T2, where there is production code to refactor.

<!-- fr:journal kind=discovery scope=plan id=804d6bd5cdb4 created=2026-09-23T16:58:50 phase=2 -->
### 804d6bd5cdb4 · discovery · no-refactor-because P2.T1 (phase 2)

P2.T1 is the red half of red-green-refactor: it only writes failing tests. The refactor step lives at the end of the green task P2.T2, where there is production code to refactor.

<!-- fr:journal kind=discovery scope=plan id=196f121f6fa2 created=2026-09-23T16:58:50 phase=3 -->
### 196f121f6fa2 · discovery · no-refactor-because P3.T1 (phase 3)

P3.T1 is the red half of red-green-refactor: it only writes failing tests. The refactor step lives at the end of the green task P3.T2, where there is production code to refactor.

<!-- fr:journal kind=discovery scope=plan id=80e0b0080222 created=2026-09-23T17:09:36 phase=1 -->
### 80e0b0080222 · discovery · agentic_landed is judged from the ref's copy of the plan (phase 1)

MergeEvidence.agentic_landed is computed from the plan as it exists on the default ref (spec 3.A). A phase that exists only in the working tree (added after an earlier merge) is not in the ref's plan, so it cannot block agentic_landed. Phase 2's sweep (archivable = agentic_landed AND locally complete) could therefore list such a plan as archivable; phase 3's archive_gate still blocks it per phase via landed_phases, which is the safe direction. If phase 2 wants 'archivable only narrows' to hold strictly, it should also require every LOCAL agentic phase number to be in landed_phases[name]. Also: fr.git now owns GitRefusal, GitUnavailableError, git_answer, ref_exists, WELL_KNOWN_DEFAULTS, remote_name, remote_default_ref (returns '<remote>/<branch>'); fr.artifacts.commit re-exports the first two via __all__, so existing imports keep working.

<!-- fr:journal kind=finding scope=plan id=f-p2-local-phases created=2026-09-23T17:18:52 phase=2 state=open -->
### f-p2-local-phases · finding [open] · Sweep's merged buckets must check every LOCAL agentic phase against landed_phases (phase 2)

From phase 1 discovery 80e0b0080222: agentic_landed is judged from the ref's copy of the plan, so a phase that exists only in the working tree (added after an earlier merge) does not block it. The sweep must classify a plan as merged (archivable / merged_manual_open) only when every agentic phase in the WORKING-TREE plan is in landed_phases[name]; otherwise it is complete_unmerged or in_progress. Test: plan on ref with phase 1 landed, phase 2 added + ticked locally -> complete_unmerged, not archivable.

<!-- fr:journal kind=review scope=plan id=rev-p1 created=2026-09-23T17:21:42 phase=1 -->
### rev-p1 · review · Phase 1 review (dispatched feature-dev:code-reviewer): no findings (phase 1)

Reviewer verified default-ref fidelity with the old _default_branch (commit-gate tests unchanged), the fetch seam (timeout, GIT_TERMINAL_PROMPT=0, failure degrades, real destroyed-remote test), git archive materialisation, per-phase landed_phases, agentic_landed excluding manual phases (closed PhaseTag literal), unparsed_on_ref, the tripwire's explicit skip, and test quality (real repos, no network). No findings at >=80 confidence. The known working-tree-only-phase gap is filed against phase 2 as f-p2-local-phases.

<!-- fr:journal kind=finding scope=plan id=f-p2-local-phases-resolved created=2026-09-23T17:30:49 state=fixed resolves=f-p2-local-phases -->
### f-p2-local-phases-resolved · finding [fixed] · resolves f-p2-local-phases: Sweep's merged buckets must check every LOCAL agentic phase against landed_phases

status_cmd._merged requires name in agentic_landed AND every agentic phase of the WORKING-TREE plan in landed_phases[name]. Test: tests/unit/test_status_sweep.py::test_a_phase_added_locally_after_merge_keeps_the_plan_unmerged (GROWN: phase 1 on origin/main, phase 2 added+ticked locally -> complete_unmerged, not archivable/merged_manual_open); also covered by the four-bucket text/JSON tests.

<!-- fr:journal kind=discovery scope=plan id=2972df159e1a created=2026-09-23T17:30:49 phase=2 -->
### 2972df159e1a · discovery · Sweep JSON carries ref_error and unparsed_on_ref beyond the spec's keys (phase 2)

Spec 3.B lists archivable, merged_manual_open, complete_unmerged, in_progress, default_ref. The sweep adds top-level ref_error (why default_ref is null; otherwise the reason is lost from JSON) and unparsed_on_ref (the text note's JSON twin). merged_manual_open stays a list of plan names like the other buckets; the open phase numbers are text-only. With ref=None, locally complete plans go to complete_unmerged in JSON (archivable only narrows) and under 'merge state unknown' in text. Text output is printed with markup=False/soft_wrap so rich neither eats brackets nor wraps long ref/fetch lines.

<!-- fr:journal kind=discovery scope=plan id=0fc64d146f12 created=2026-09-23T17:30:49 phase=2 -->
### 0fc64d146f12 · discovery · fr-progress SKILL.md sits at the 120-line cap (phase 2)

test_skill_validation::test_under_120_lines caps SKILL.md at 120 lines and fr-progress was already at 120, so describing the four buckets forced tightening unrelated prose in the same file (how-it-works, audit-drift, spec-rollup, acceptance-debt, v1-archive paragraphs; meaning kept). The archive-gate paragraph was left as-is for phase 3 to update when archive_gate changes.

<!-- fr:journal kind=finding scope=plan id=f-p2-skill-trim created=2026-09-23T17:35:27 phase=2 state=open -->
### f-p2-skill-trim · finding [open] · fr-progress trim dropped two instructions: single-plan status is safe to allowlist; archive moves are staged, the operator commits (phase 2)

Orchestrator's own diff of 24b48bf1..9bf54ada (the reviewer had no git access for the before/after). Other trims preserved meaning.

<!-- fr:journal kind=finding scope=plan id=f-p2-skill-trim-resolved created=2026-09-23T17:35:27 state=fixed resolves=f-p2-skill-trim -->
### f-p2-skill-trim-resolved · finding [fixed] · resolves f-p2-skill-trim: fr-progress trim dropped two instructions: single-plan status is safe to allowlist; archive moves are staged, the operator commits

Restored both facts in plugins/super-fr/skills/fr-progress/SKILL.md (allowlist note now says it may git fetch remote-tracking refs); folded the apply empty-diff sentence into a code comment to stay at 119/120 lines; mirrors regenerated; skill + mirror tripwires green (134 passed).

<!-- fr:journal kind=review scope=plan id=rev-p2 created=2026-09-23T17:35:28 phase=2 -->
### rev-p2 · review · Phase 2 review (dispatched feature-dev:code-reviewer + orchestrator skill diff): 1 minor finding, fixed (phase 2)

Reviewer: no findings >=80 - buckets exhaustive/disjoint, f-p2-local-phases fix real and tested, wording matches spec, --all never printed, archivable only narrows, fetch only on sweep path, tests real. Sub-threshold note (unparseable plan listed in in_progress and in the unparsed note) is intentional per _Sweep docstring. Reviewer could not diff SKILL.md; orchestrator diffed it and filed f-p2-skill-trim (fixed).

<!-- fr:journal kind=discovery scope=plan id=d-p3-gate-adapter created=2026-09-23T17:56:59 phase=3 -->
### d-p3-gate-adapter · discovery · archive_gate gained two optional wording kwargs; fr.archive.archive_blockers is the one adapter (phase 3)

Beyond the spec's (plan, observed, *, landed): archive_gate also takes optional ref (for 'not on origin/main') and unknown_reason (for 'merge state unknown (<reason>)'); landed itself stays required with no default. fr.archive.landed_for(evidence, name) maps ref=None to landed=None and an absent plan to frozenset(). fr.archive.archive_blockers(plan, observed, evidence) feeds all of it from one MergeEvidence, and is now the only archive_gate caller outside tests (archive_cmd, status_cmd text+JSON, apply_cmd). status_cmd imports it lazily, matching the sweep's existing lazy fr.archive imports.

<!-- fr:journal kind=discovery scope=plan id=d-p3-apply-fetch created=2026-09-23T17:56:59 phase=3 -->
### d-p3-apply-fetch · discovery · fr apply now fetches once per invocation; direct _apply_one callers read their plan's repo (phase 3)

apply_command calls merge_evidence(resolve_repo_root(), fetch=True) once (also under --all) and passes evidence= to _apply_one. _apply_one's evidence kwarg defaults to None, in which case it reads plan.repo_root itself, so existing direct callers (test_v2_apply, test_reachability) keep working; their repos have no remote or a file remote, so no network. archive_cmd prints a note when the fetch failed and the local ref is used.

<!-- fr:journal kind=discovery scope=plan id=d-p3-vacuous-nudge created=2026-09-23T17:57:00 phase=3 -->
### d-p3-vacuous-nudge · discovery · Old nudge assertions were satisfied by drift-warning text, not the nudge (phase 3)

test_status_cmd and test_archive_cmd's apply nudge test asserted 'fr archive' in output, which the never-dispatched drift warning ('fr archive if this plan is done') also contains, so they would stay green with the nudge gone. Migrated onto landed repos (file-path origin) and tightened to the nudge line 'plan complete — run fr archive'. No test gained --force. A shared tests.unit.test_merge_evidence.stub_fetch now owns hermetic git config + the recording _fetch stub for all four CLI test modules.

<!-- fr:journal kind=finding scope=plan id=f-p3-skill-gate created=2026-09-23T18:01:39 phase=3 state=open -->
### f-p3-skill-gate · finding [open] · fr-progress Archive-on-complete paragraph still described the pre-#544 gate (phase 3)

Reviewer finding (minor): SKILL.md said 'fully-ticked never-dispatched' clears the gate; phase 3 now also requires an undispatched agentic phase to be on origin/<default>.

<!-- fr:journal kind=finding scope=plan id=f-p3-skill-gate-resolved created=2026-09-23T18:01:39 state=fixed resolves=f-p3-skill-gate -->
### f-p3-skill-gate-resolved · finding [fixed] · resolves f-p3-skill-gate: fr-progress Archive-on-complete paragraph still described the pre-#544 gate

Paragraph now states all three arms (dispatched: gh evidence; undispatched agentic: ticked AND on origin/<default>; manual: ticked locally); mirrors regenerated; skill + mirror + neutrality tripwires green; 120/120 lines.

<!-- fr:journal kind=review scope=plan id=rev-p3 created=2026-09-23T18:01:40 phase=3 -->
### rev-p3 · review · Phase 3 review (dispatched feature-dev:code-reviewer): 1 minor finding, fixed (phase 3)

Verified: archive_gate landed required keyword-only; undispatched agentic needs local + landed; manual local only; dispatched arm unchanged; landed=None blocks with stated wording; archive_blockers/landed_for single adapter never falsely clears (ref None -> None, absent plan -> empty); one merge_evidence per invocation for archive and apply; --force single still overrides; _apply_one fallback reads the plan-dir's own repo, no cross-repo mixup; failure paths degrade; status read-only; close-out case tested; no test passes via --force; rows at ci; version lockstep 4.19.2. Finding f-p3-skill-gate fixed.

<!-- fr:journal kind=discovery scope=plan id=live-premerge created=2026-09-23T18:02:18 phase=4 -->
### live-premerge · discovery · Live pre-merge check (orchestrator, uv run fr 4.19.2): not merged, no archive suggestion, archive refuses (phase 4)

On fix/526-status-archivable-merged after implement, before any PR: fr status listed this plan under 'in progress' (phase 4 open) and printed no fr archive line for it; with phase 4 temporarily ticked (then restored via git checkout) it moved to 'complete locally, not yet on origin/main (waiting for merge)', JSON archivable=[] complete_unmerged=[this plan] - the exact #526 scenario, now correct. fr archive <this plan> exited 2: 'Phase 1..3: complete locally, not on origin/main; merge the PR first'. Side observation: the four other live plans read 'merged, manual phases still open' (incl. fr-run-cursor-cluster phase 7), a signal the old sweep hid under 'in progress'. The operator still owns ticking P4.T1.S1.

<!-- fr:journal kind=discovery scope=plan id=live-536-c5-var created=2026-09-23T18:13:28 -->
### live-536-c5-var · discovery · #536 C5 live: deliver's tests= check refuses a log written via a shell variable

The orchestrator ran the full verification itself with `L=<path>; { uv run pytest -q; ... } > $L 2>&1` (background Bash). fr run resolve --step deliver --evidence tests=<path> refused: 'no command of YOURS wrote it (a >, >> or tee naming it)'. The check matches the literal path in the command text, so variable indirection is a false refusal. Worked around by re-running the suite into a literal path. Fail-closed direction, so safe, but it costs a 10-minute re-run; worth an issue against #536's C5 (expand simple VAR=... assignments in the same command, or match on the resolved path).

<!-- fr:journal kind=discovery scope=plan id=live-536-c5-background created=2026-09-23T18:45:42 -->
### live-536-c5-background · discovery · #536 C5 live: deliver's tests= gate can never accept a backgrounded suite, which the brief's long_commands rule mandates

fr.run.telemetry.orchestrator_wrote_since takes the run window as tool_use to tool_result, and requires the log's mtime inside it. A run_in_background Bash returns its tool_result immediately, so the log's bytes always land after the window: refused with 'its bytes were not written by the command of yours that names it'. A foreground call past 600 s is moved to the background by the harness, so the full ~10 min suite cannot satisfy the gate either way. The brief's own long_commands rule tells the orchestrator to background the suite, so the two contracts conflict. Workaround used: 5 foreground shards (round-robin over test files) appending to one log, 966+829+756+1102+1327 = 4980 passed + 88 skipped, the same totals as the single run. Fix direction: for a backgrounded command, close the window at its completion notification, not at the immediate tool_result.
