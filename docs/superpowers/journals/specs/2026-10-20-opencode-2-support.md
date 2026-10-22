<!-- fr:journal-schema=2 -->
# Journal: 2026-10-20-opencode-2-support

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-20T05:29:50+00:00 input=true -->
### operator-brief · discovery · Operator brief, verbatim

OpenCode 2.0 was released. See whether we need to update our support for
it and whether any of the features lagging behind Claude can be fixed
now. See https://opencode.ai/v2/docs/migrate-v1/

<!-- fr:journal kind=discovery scope=spec id=opencode-2-breaks-plugin-and-store created=2026-10-20T05:29:50+00:00 -->
### opencode-2-breaks-plugin-and-store · discovery · On 2.0.32 the plugin does not load and the store moved to session_v2/session_message

Measured on this host, OpenCode 2.0.32 (the only binary; V1 is not side by
side):

- `~/.local/share/opencode/log/opencode.log` records `failed to load
  plugin ... Plugin must export a default definition with an id and an
  effect or setup function`, for the delivered global copy and this
  repo's project-local copy alike. V1 plugin functions are not an
  implementation in V2, so the edit gate, idle guard, pin, session export
  and claim are all inert.
- `opencode.db` holds both stores. A live 2.0 session has a row in
  `session_v2` and **0** rows in `part`; its messages are `session_message`
  rows whose `data.content[]` carries reasoning/text/tool items. The
  legacy `session`/`message`/`part` tables receive nothing.
- The migration was lossless: `session_v2` holds all 230 sessions
  including 1.18.x/1.19.x, and `session_message` holds 10 871 rows with
  V1's `cost`/`tokens`/`model`/`agent` shape — which is why V2-only
  readers lose no history.
- Tool items are renamed (`bash` -> `shell`) and reshaped (`id`, `name`,
  `state.{status,input,content,metadata}`, `time.{created,ran,completed}`).
- V2 adds `ctx.permission.hook("evaluate")` with `action: "shell"` and
  the scanner's command resources, and `@opencode/plugin/tui` UI slots.

<!-- fr:journal kind=decision scope=spec id=opencode-2-scope created=2026-10-20T05:29:50+00:00 decided_by=operator -->
### opencode-2-scope · decision · Full parity push, V2-only, deny, delivered status line, no worktree routing

Round 1: full parity push (restore plus bash gate, acceptance nag,
pipeline sentinel, session bind/unbind, status line); dual V1/V2 support
rejected in favour of V2-only; V2-only store readers with a loud 1.x
refusal; verification by `candidate` plus post-merge live rows.

Round 2: the loud 1.x refusal is per-session with a version-named reason
(a per-store preflight would refuse a mid-migration store and an upgraded
binary whose store still holds old sessions); the shell gate uses
`effect: "deny"` for Claude parity, never `ask`; the status line is
delivered and registered in `cli.json` by the installer, appending only
its own entry; `fr-worktree-create`/`fr-worktree-remove` stay out and are
filed as a follow-up.

_`decided_by=operator` recorded unverified: the gate could not read who answered it._

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-10-20T05:29:56+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: design-risk. Round 1's full-parity scope decided what to build; round 2 had to settle four things that decision opened and the code could not answer — the shape of the loud 1.x refusal (per-session vs per-store), the shell gate's effect (deny vs ask), how the TUI status line is delivered and registered, and whether worktree routing joins this run.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-10-20T05:35:42+00:00 -->
### spec-review · review · Independent spec review — 16 findings, all resolved

Dispatched `fr-spec-reviewer` (hard tier) into the workspace, read-only.
It returned 16 findings: 15 in scope and one policy nit. Every in-scope
finding was a defect in the spec as written; all are fixed in
docs/superpowers/specs/2026-10-20-opencode-2-support-design.md.

The load-bearing ones: the shell gate must judge the WHOLE command line
(per-resource permission evaluation would deny `cd <worktree> && git
status`), so it moved to `execute.before` with a throw; the session-id
correlation must export nothing when ambiguous; the 1.x refusal needs a
real store probe because `_known` is a boolean and `why_unobservable`
never sees the database; and §D now lists every query site, not the two
obvious ones.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · The shell gate runs once per scanned resource, so it cannot reproduce the bash guard's whole-command decision

check: codebase
evidence: spec R3, §B; plugins/super-fr/hooks/fr-isolation-guard.sh:2-3,10-12,132-200,224-242
Today's guard decides on the whole command line and the cwd, folds a
leading `cd` only when it lands inside the base repo or another repo's
toplevel, and matches `fr …` allowances from the start of the line but not
to the end. Judging resources one at a time turns `cd <worktree> && git
status` into a bare `git status` in the base repo (denied) and denies
`fr isolation status && X`. R3 forbids both.
Fix: decide on the full command text in `execute.before` and reject by
throwing; plan phase 1 confirms the data exists; compound-command fixtures.

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · R3's scope list leaves out the guard's sentinel refresh, self-heal lock and cross-repo target rules

check: consistency
evidence: fr-isolation-guard.sh:58 (touch -c), :132-200 (#421 cross-repo/linked-worktree scoping), :335-385 (sentinel_workspaces, lock, heal)
R3 said "scope is exactly today's" but listed only the sentinel, cwd,
allowances, cd fold and escapes. The mtime refresh, the linked-worktree
case and the orphaned-sentinel heal under the shared lock are part of the
decision; leaving the lock out races `fr isolation attach`, leaving the
heal out locks sessions out (#472/#529).
Fix: R3 now lists all three and requires the same lock primitive.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · The fixture-table drift guard has no named test home and no named way for bun to reach it

check: consistency
evidence: spec §B; tests/unit/test_hooks_guard.py; .github/workflows/ci.yml opencode-plugin-test (cwd packages/fr-opencode-plugin)
The drift guard is the only thing keeping two engines in agreement, and it
had no path, format, Python loader or bun reader.
Fix: tests/fixtures/hooks/guard-verdicts.yaml, loaded by
tests/unit/test_hooks_guard.py and a new
packages/fr-opencode-plugin/test/guard-verdicts.test.ts, with rows for the
cases s1/s2 name.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Session-id correlation is not exact when two sessions run the same command, and its premise is unproven

check: consistency
evidence: spec R6/§C ("pops the oldest entry whose command equals event.command … This is exact")
A parent and a subagent can issue the same command within the TTL; FIFO by
command text then mis-scopes one of them — the failure §C says it rejects.
The premise (input.command equals the shell event's command, in that order)
was also assumed.
Fix: export nothing unless exactly one session matches; phase 1 measures
ordering/fidelity with a stated outcome for "premise false".

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · The "unset FR_OPENCODE_SESSION_ID" message would blame the plugin when the plugin deliberately left the id out

check: codebase
evidence: observed.py:729-734; telemetry.py:1303-1351; run_cmd.py:1437-1442
With no id, deliver-tests-provenance falls back to `opencode_unscoped` and
reports unobserved — correct. But on V2 a missing id with a current plugin
is now normal, and the message says the plugin is "missing or older".
Fix: R6 requires why_unobservable to name the correlation miss.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · §D leaves out several queries on the legacy tables, including the unscoped path and the usage reader's joins

check: codebase
evidence: observed.py:313, :315-321, :383, :426, :436-438, :669, :714; usage/readers/opencode.py:134-146, :103-106
The Context said the readers use `session`/`part`; `fr usage` also reads
`message`, and §D omitted the unscoped top-level query and its activity
probe, the final-text read, the readability probe and the task-brief
metadata. Any one left behind returns None/[] silently on 2.0.
Fix: §D is now a table naming every site and its V2 equivalent, with the
task metadata measured in phase 1.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · The design gives R14's refusal no way to reach the gates' wording

check: codebase
evidence: observed.py:378-383 (_known is a bool), :686-716 (observed_session returns None), :719-740 (why_unobservable takes no db/session)
As designed, a 1.x session still produced today's "check FR_OPENCODE_DB"
text, which R14 forbids.
Fix: a version probe (`v2 | v1-only | absent | unreadable`) feeding both
why_unobservable and the usage reader, with a test on the gate path too.

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · R14 also refuses a whole store, which reads against the per-session decision

check: decisions
evidence: journal decision opencode-2-scope, round 2
The second clause (no `session_v2` at all) is a store-level property. It is
still applied per requested session, but the spec did not say so.
Fix: R14 says per requested session, never a command-level preflight.

<!-- fr:journal kind=finding scope=spec id=s9 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s9 · finding [open] (reviewer: in scope) · The lossless migration is a measurement on one host, written as a guarantee

check: consistency
evidence: spec Context bullet 3, R13
230 sessions on one host do not prove the migration is complete in general,
and this claim is what justifies dropping the V1 readers.
Fix: presented as an observation; R13 pins it as a fixture of migrated rows
with a test.

<!-- fr:journal kind=finding scope=spec id=s10 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s10 · finding [open] (reviewer: in scope) · R9, R10, R11 have no hook in §A's map, and none of the V2 API names are sourced

check: consistency
evidence: spec §A; no citation for any V2 name
The nag needs `session.hook("context")`, the sentinel and bind/unbind need
`execute.after`, and unbind needs `session.deleted`; none appeared in the
design, and no API name cited a source.
Fix: §A now carries those rows and a Sources section names the guides and
the version-pinned typings.

<!-- fr:journal kind=finding scope=spec id=s11 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s11 · finding [open] (reviewer: in scope) · Several requirements have no Verification row or Test Plan item, and Test Plan 5 mixes up the status line with the nag

check: consistency
evidence: spec R4, R7-R11 vs Verification; plugins/super-fr/scripts/fr-statusline-segment.sh:2
The push guard, claim, pin, nag, sentinel and bind/unbind had no row; the
status segment shows branch/isolation, not the matrix, so "no matrix →
silent" belongs to the nag; and the usage claim was listed post-merge
although candidate proves it.
Fix: six rows added at this step (opencode-2-push-guard, -claim, -pin,
-nag, -sentinel, -bind-unbind), Test Plan 5/6 corrected, usage left to
candidate.

<!-- fr:journal kind=finding scope=spec id=s12 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s12 · finding [open] (reviewer: in scope) · The Tester gate is stated in prose but not in the Verification grammar

check: consistency
evidence: spec §Verification; packages/fr/src/fr/verification/spec_section.py:38-46
Nothing the machinery reads tied the live rows to `tester`.
Fix: per-row `gate: <row>=tester` lines.

<!-- fr:journal kind=finding scope=spec id=s13 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s13 · finding [open] (reviewer: in scope) · Delivering a status-line TSX conflicts with how parity is observed and how the plugin is delivered

check: codebase
evidence: harness/observe.py:107-135 (globs src/*.ts; markers name hooks/ scripts); scripts/deliver-opencode-plugin.sh:8-13; the status segment lives under plugins/super-fr/scripts/
A `.tsx` in `src` is not scanned, a `super-fr-parity:` marker naming a
non-hook script raises HarnessError, and a top-level TUI file in the plugin
directory would also be loaded as a server plugin.
Fix: the TUI entrypoint lives beside the server plugin (never top-level),
is registered by path in cli.json, and is credited through a config probe
in observe.py, not a hook marker.

<!-- fr:journal kind=finding scope=spec id=s14 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s14 · finding [open] (reviewer: in scope) · R16 misses the rule prose, the generated mirrors, AGENTS.md and the version bump level

check: consistency
evidence: plugins/super-fr/rules/fr-isolation-required.md ("not bash, a known gap (#436)"); .claude/rules mirror; AGENTS.md; scripts/sync-opencode.py, sync-hermes.py; scripts/check-change-fragment.py:42-64, version_surfaces.py:37,116
The canonical rule still says OpenCode cannot gate bash, which needs both
sync scripts and the hand-maintained mirror; AGENTS.md describes the V1
hook; the fragment's bump was unstated; and "no version-bearing file is
touched" read as if package.json could not change at all.
Fix: R16 lists these, states `bump: major`, and says package.json may change
its dependency but never its `version`; no artifact shape changes, so no
stamp or migration.

<!-- fr:journal kind=finding scope=spec id=s15 created=2026-10-20T05:35:42+00:00 state=open review_scope=in -->
### s15 · finding [open] (reviewer: in scope) · Failure modes of the cli.json registration are not stated

check: consistency
evidence: spec R12/§E
No behaviour for a missing cli.json, malformed or JSONC content, a host
without OpenCode 2, reinstall duplication, or uninstall.
Fix: §E states each (create when absent, refuse rather than overwrite
unparsable content, idempotent by exact path, uninstall removes only ours)
and tests them beside test_opencode_plugin_delivery.py.

<!-- fr:journal kind=finding scope=spec id=s16 created=2026-10-20T05:35:42+00:00 state=open review_scope=out -->
### s16 · finding [open] (reviewer: out of scope) · "A failed live row is a defect" overrules the gate policy

check: consistency
evidence: spec §Verification last line
Policy wording the spec does not own. Removed anyway.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: The shell gate runs once per scanned resource, so it cannot reproduce the bash guard's whole-command decision

R3/§B now decide on the whole command line in `execute.before` and reject by throwing; compound-command fixtures required.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: R3's scope list leaves out the guard's sentinel refresh, self-heal lock and cross-repo target rules

R3 lists the mtime refresh, the linked-worktree case and the heal under the shared lock.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s3 -->
### s3-resolved · finding [fixed] · resolves s3: The fixture-table drift guard has no named test home and no named way for bun to reach it

§B names tests/fixtures/hooks/guard-verdicts.yaml and both loaders.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: Session-id correlation is not exact when two sessions run the same command, and its premise is unproven

§C exports nothing unless exactly one session matches; phase 1 measures the premise with a stated false outcome.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: The "unset FR_OPENCODE_SESSION_ID" message would blame the plugin when the plugin deliberately left the id out

R6 requires why_unobservable to name the correlation miss.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: §D leaves out several queries on the legacy tables, including the unscoped path and the usage reader's joins

§D is a table covering every query site, including the unscoped path, final text, readability probe and task metadata.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: The design gives R14's refusal no way to reach the gates' wording

R14 adds a store version probe feeding why_unobservable and the usage reader, with a gate-path test.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: R14 also refuses a whole store, which reads against the per-session decision

R14 states the refusal is per requested session, never a preflight.

<!-- fr:journal kind=finding scope=spec id=s9-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s9 -->
### s9-resolved · finding [fixed] · resolves s9: The lossless migration is a measurement on one host, written as a guarantee

The claim is an observation, pinned as a fixture per R13.

<!-- fr:journal kind=finding scope=spec id=s10-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s10 -->
### s10-resolved · finding [fixed] · resolves s10: R9, R10, R11 have no hook in §A's map, and none of the V2 API names are sourced

§A gained the session/context, execute.after and event rows; a Sources section names every API.

<!-- fr:journal kind=finding scope=spec id=s11-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s11 -->
### s11-resolved · finding [fixed] · resolves s11: Several requirements have no Verification row or Test Plan item, and Test Plan 5 mixes up the status line with the nag

Six rows added and the Test Plan items corrected.

<!-- fr:journal kind=finding scope=spec id=s12-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s12 -->
### s12-resolved · finding [fixed] · resolves s12: The Tester gate is stated in prose but not in the Verification grammar

Per-row `gate: <row>=tester` lines added.

<!-- fr:journal kind=finding scope=spec id=s13-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s13 -->
### s13-resolved · finding [fixed] · resolves s13: Delivering a status-line TSX conflicts with how parity is observed and how the plugin is delivered

R12/§E fix the entrypoint's location, registration and observation path.

<!-- fr:journal kind=finding scope=spec id=s14-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s14 -->
### s14-resolved · finding [fixed] · resolves s14: R16 misses the rule prose, the generated mirrors, AGENTS.md and the version bump level

R16 lists the rule, its mirror, AGENTS.md, both sync scripts and the bump level, and scopes the package.json freedom.

<!-- fr:journal kind=finding scope=spec id=s15-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s15 -->
### s15-resolved · finding [fixed] · resolves s15: Failure modes of the cli.json registration are not stated

§E states every cli.json failure mode and requires tests beside the delivery test.

<!-- fr:journal kind=finding scope=spec id=s16-resolved created=2026-10-20T05:35:42+00:00 state=fixed resolves=s16 -->
### s16-resolved · finding [fixed] · resolves s16: "A failed live row is a defect" overrules the gate policy

The sentence was removed.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-20-opencode-2-support-p1 created=2026-10-20T05:43:45+00:00 decided_by=agent -->
### phase-split-2026-10-20-opencode-2-support-p1 · decision · review-size: the V2 restore is one ask across the entrypoint, edit gate, pin, idle, claim and export

Phase 5 only records these rows' evidence as matrix bookkeeping; it does not serve the restore ask. Keeping the restore whole makes the diff reviewable as one port, and the enforcement surfaces (sentinel, shell gate, push guard) are a different ask that belongs in its own review.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-20-opencode-2-support-p2 created=2026-10-20T05:43:52+00:00 decided_by=agent -->
### phase-split-2026-10-20-opencode-2-support-p2 · decision · ask: the pipeline sentinel, the shell gate and the push guard are a new enforcement surface

Phase 1's restore does not contain them. Two decision engines must agree on whole-command semantics, and the sentinel is the gate's prerequisite, so they land together as one reviewable enforcement ask.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-20-opencode-2-support-p3 created=2026-10-20T05:43:53+00:00 decided_by=agent -->
### phase-split-2026-10-20-opencode-2-support-p3 · decision · risk-first: the TUI delivery mechanism is the one unproven mechanism in the port

The status line may not be deliverable without consumer-side peer packages. Proving or falling back before the readers keeps the risk early, when the fallback can still shape the parity decision.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-20-opencode-2-support-p4 created=2026-10-20T05:43:54+00:00 decided_by=agent -->
### phase-split-2026-10-20-opencode-2-support-p4 · decision · ask: reading OpenCode 2's store is independent of the plugin

fr must read the 2.0 store whether or not the plugin is installed, and the loud 1.x refusal is its own contract. No other phase can serve it.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-20-opencode-2-support-p5 created=2026-10-20T05:43:55+00:00 decided_by=agent -->
### phase-split-2026-10-20-opencode-2-support-p5 · decision · ask: the published surfaces must describe what actually shipped

Parity rows, the acceptance matrix and its three reports, the canonical rule and its mirrors, the explainer and the release fragment are a distinct ask that no implementation phase serves.

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-20-opencode-2-support-p1 created=2026-10-20T05:43:56+00:00 decided_by=agent -->
### tier-2026-10-20-opencode-2-support-p1 · decision · hard: the V2 hook map is new and the event ordering is measured, not documented

A wrong entrypoint fails silently: the plugin looks installed while every gate is inert (the exact state this run starts from).

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-20-opencode-2-support-p2 created=2026-10-20T05:43:57+00:00 decided_by=agent -->
### tier-2026-10-20-opencode-2-support-p2 · decision · hard: two decision engines must agree on whole-command semantics

The sentinel's mtime refresh, shared lock and orphan heal have no TypeScript precedent, and a broader gate would deny commands the Claude path allows.

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-20-opencode-2-support-p3 created=2026-10-20T05:43:58+00:00 decided_by=agent -->
### tier-2026-10-20-opencode-2-support-p3 · decision · hard: the delivery mechanism is unproven and its failure mode is silent

A slot that never renders looks like a status line that shows nothing. The phase must decide and record which mechanism shipped.

<!-- fr:journal kind=decision scope=spec id=tier-2026-10-20-opencode-2-support-p4 created=2026-10-20T05:43:59+00:00 decided_by=agent -->
### tier-2026-10-20-opencode-2-support-p4 · decision · hard: every query site moves and a missed one returns empty silently

The loud 1.x refusal is the only thing that makes an omission visible, so the probe and both readers must land together.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-20-opencode-2-support-p2-1 created=2026-10-20T05:44:47+00:00 decided_by=agent -->
### phase-split-2026-10-20-opencode-2-support-p2-1 · decision · review-size: folding the enforcement surfaces into the restore would make a 1600-line diff

Phase 5 re-points these rows' evidence as matrix bookkeeping; it does not serve the enforcement ask. The shell gate and the sentinel are a different review from the hook port.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-20-opencode-2-support-p4-1 created=2026-10-20T05:44:48+00:00 decided_by=agent -->
### phase-split-2026-10-20-opencode-2-support-p4-1 · decision · review-size: the readers are an independent contract of their own

Phase 5 only records their evidence. Reading the 2.0 store is 900 lines across two readers, a shared adapter and a fixture; it is reviewable on its own and shares no file with the plugin phases.

<!-- fr:journal kind=decision scope=spec id=phase-split-2026-10-20-opencode-2-support-p5-1 created=2026-10-20T05:44:49+00:00 decided_by=agent -->
### phase-split-2026-10-20-opencode-2-support-p5-1 · decision · tier: phase 5 is mechanical-tier bookkeeping across a dozen published surfaces

It exists to make the published surfaces match the code: parity rows, the matrix and its three reports, the canonical rule and both mirrors, the explainer and the release fragment. Folding it into a hard implementation phase would blur the tier the dispatcher binds.

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-1 created=2026-10-22T16:34:02+00:00 -->
### test-plan-step-1 · discovery · Test Plan step 1: ran

Step: Enter a workspace, start a run, ask the model to edit a tracked file in the base clone; expect the plugin's refusal and no file change.

Evidence: PASS — a model-driven edit to docs/superpowers/specs/2026-10-20-opencode-2-support-design.md in the base clone was refused with the fr-isolation blocked message; git status stayed clean and no file changed.

<!-- fr:journal kind=discovery scope=spec id=test-plan-step-2 created=2026-10-22T16:34:08+00:00 -->
### test-plan-step-2 · discovery · Test Plan step 2: ran

Step: From the workspace, run `git status` (allowed) and then a base-clone write through `shell` during an active pipeline (denied, with the escape list).

Evidence: PASS — with an active pipeline sentinel for this session, git status from the archive workspace was allowed; a base-clone touch fr-shell-gate-probe was denied with the full escape list and no probe file was created. The sentinel was armed in the equivalent state (the session was not running a pipeline skill) and disarmed after the test.
