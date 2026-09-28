# Journal: 2026-09-28-closeout-always

<!-- fr:journal kind=discovery scope=spec id=i1-batch-brief created=2026-09-28T19:31:09+00:00 input=true -->
### i1-batch-brief · discovery · Operator input — batch closeout-always-2 dispatch brief (verbatim)

/fr-goal Close-out is an always condition of every fr flow: branch-keyed, archives every artifact the branch added

Batch `closeout-always-2` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#733: Close-out is an always condition of every fr flow: keyed on the branch, archives every artifact it added (fr-debugging has none; 26 debug journals never archived)
fr-debugging has no close-out and `fr archive` moves only plans/specs and their journals: 26 debug journals live on main since 2026-07-23, none ever archived (no implemented/journals/debug/). Close-out is per-skill, hung off the fr-goal run cursor.
Note: Feature (fr-goal). Branch-keyed close-out + "live only while its PR is open" check. Batch `closeout-always`, after `reverted-merge` (#716 edits the same branch-diff code in isolation/local.py); `closeout-queue` (#667) builds on it.

## Why these belong together
Retry of the batch cancelled on 2026-09-28 at its question gate (#783): dispatch only after question-order (#783) merges. Wave 5, after reverted-merge (#716 edits the branch-diff code in fr/isolation/local.py that this reuses). fr-debugging has no close-out, and fr archive moves only plans and specs, so 26 debug journals have never been archived. One close-out keyed on the branch (verify-merge, archive everything the branch added including debug journals, housekeeping PR, isolation down), with fr pickup --run as a caller. A structural check reports live artifacts whose PR has merged, and fr-debugging's deliver relays the close-out line. The first run sweeps the 26. closeout-queue (#667) builds on this. The issue's design is a direction; the brainstorm decides the shape.

## Delivery rules
- Work on branch `feat/batch-closeout-always-2`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#733
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=discovery scope=spec id=i2-issue-733 created=2026-09-28T19:31:09+00:00 input=true -->
### i2-issue-733 · discovery · Operator input — derio-net/super-fr#733 body (verbatim)

## Problem

Only fr-goal has a post-merge close-out. It hangs off the run cursor: `deliver` relays `fr pickup --run <run-id>`, and the brief it prints runs verify-merge, `fr archive`, the housekeeping PR and `isolation down`.

fr-debugging has none. Its SKILL.md never mentions archiving, a close-out or `fr pickup`, and a debug run keeps no run cursor that one could hang off. `fr archive` also moves only plans, specs and their journals. The result, on `origin/main` at baff515e:

- 26 debug journals are still live under `docs/superpowers/journals/debug/`, dating from 2026-07-23 to 2026-09-27.
- None has ever been archived. `docs/superpowers/implemented/journals/` has `plans/` and `specs/`, but never a `debug/`.

Nothing reports this, because every flow decides for itself whether it has a close-out. A flow that doesn't have one leaves its files live on `main`, and nobody notices.

## Proposal (a design direction; the shape is for the brainstorm)

Make the close-out an always-on condition at the end of **every** fr-shaped flow. Key it on the **branch**, not the skill or the run cursor, because every flow ends with a branch and a PR.

1. **One close-out keyed on the branch** (for example `fr closeout --branch <b>`, or `fr pickup --branch <b>`):
   - `fr isolation verify-merge`;
   - archive every live artifact the branch *added* (plans, specs, and journals of every scope, `debug` included);
   - the housekeeping PR;
   - `isolation down`.

   "What did this branch add" already has hardened diff logic in `branch_changes_present` (#696, #727). fr-goal's `fr pickup --run` becomes a caller of it, not a second path.
2. **A structural rule that catches misses:** a live artifact is legal only while the PR that introduced it is open. After that PR merges, the file belongs under `implemented/`. `fr status` and/or `fr triage check` report every live artifact whose introducing PR has merged, so a flow that skips its close-out shows up instead of piling up.
3. **fr-debugging's `deliver`** relays the same close-out line fr-goal does.

The first run clears the 26 existing debug journals as a one-time sweep.

## Related

- #667, the batch close-out queue, should build on this: it becomes a loop over (1), one branch per merged batch.
- #458 (`fr archive` offering to file open ends) belongs in the same close-out step.

<!-- fr:journal kind=decision scope=spec id=d1-surface created=2026-09-28T19:31:09+00:00 -->
### d1-surface · decision · Surface: `fr pickup --branch` brief + `fr archive --branch`; `--run` delegates

Q (Round 1 · question 1 of 5): what is the branch-keyed close-out surface?
A (operator): Brief + fr archive --branch (Recommended). `fr pickup --branch <b>` prints the brief; `fr pickup --run` resolves the run's branch and calls it, adding run-only extras; `fr archive --branch <b>` does the moving. Rejected: a new `fr closeout` verb, and fr executing every step itself.

<!-- fr:journal kind=decision scope=spec id=d2-added-and-modified created=2026-09-28T19:31:09+00:00 -->
### d2-added-and-modified · decision · Archive artifacts the branch added OR modified, each through its kind's gate

Q (Round 1 · question 2 of 5): added only, or also modified?
A (operator): Added + modified, per-kind gate (Recommended). Plans use the archive gate, specs the fully-implemented sweep, plan/spec journals + runs + usage follow their owner; a debug journal is done once its branch merged.

<!-- fr:journal kind=decision scope=spec id=d3-status-advisory created=2026-09-28T19:31:09+00:00 -->
### d3-status-advisory · decision · The owed-artifact check reports in `fr status`, advisory only

Q (Round 1 · question 3 of 5): where does the structural check report?
A (operator): fr status, advisory (Recommended). Extend `fr status`'s gh-free "merged but not archived" sweep to every kind, each with the command that clears it; never fails CI. Rejected: also `fr triage check`; a CI gate with a grace period.

<!-- fr:journal kind=decision scope=spec id=d4-no-debug-cursor created=2026-09-28T19:31:09+00:00 -->
### d4-no-debug-cursor · decision · fr-debugging relays `fr pickup --branch <b>`; no run cursor

Q (Round 1 · question 4 of 5): how does fr-debugging's deliver get a close-out?
A (operator): Relay the branch line, no cursor (Recommended). Rejected: a new fr-debugging workflow shape driven by `fr run`.

<!-- fr:journal kind=decision scope=spec id=d5-sweep-in-pr created=2026-09-28T19:31:09+00:00 -->
### d5-sweep-in-pr · decision · The live debug journals are swept in this PR, by the new code

Q (Round 1 · question 5 of 5): when are the 36 live debug journals swept?
A (operator): In this PR, by the new code (Recommended). `fr archive --all` learns debug journals; this PR's last phase runs it and commits the moves.

<!-- fr:journal kind=discovery scope=spec id=x1-matrix-cites-debug-journals created=2026-09-28T19:31:09+00:00 -->
### x1-matrix-cites-debug-journals · discovery · The acceptance matrix cites debug journals as evidence — moving them must not break refs

Round-1 cross-check: `docs/acceptance/matrix.yaml` cites `docs/superpowers/journals/debug/*.md` 22 times, and `fr acceptance check` fails on an unresolvable ref. `archive_twin` (packages/fr/src/fr/acceptance/model.py:46) only covers specs/ ↔ implemented/specs/. Design §F extends it to every journal scope, so the sweep (d5) rewrites no row. No open PR (#786/#787/#788) appends to an existing main debug journal, so the sweep conflicts with none. Neither finding needed an operator decision, so no second round.

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-28T19:39:01+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · "every fr-shaped flow" is dropped: only fr-goal and fr-debugging relay the close-out

check: traceability
evidence: i2-issue-733 "Make the close-out an always-on condition at the end of **every** fr-shaped flow." (also the i1 title "Close-out is an always condition of every fr flow"); plugins/super-fr/skills/fr-execute/SKILL.md:84 (standalone fr-execute opens PRs, has no close-out); plugins/super-fr/skills/fr-brainstorming/SKILL.md:97-98 ("cleanup belongs to whoever finishes the run (`fr isolation down` after the PR merges)")
scope: The span is the headline of the input and no requirement quotes it or defers it, so it belongs to this change.
resolution: dropped
No requirement quotes this span, and nothing in ## Deferred from input lists it. R1 only makes a branch close-out *available* for any branch. R6 wires it into fr-debugging and §E into fr-goal, but other flows that end in a branch and PR, such as standalone fr-execute and standalone fr-brainstorming→fr-plan, still end at "fr isolation down" with no close-out relayed. The fix is either a requirement that every shipped flow ending in a PR relays `fr pickup --branch <b>`, or an explicit deferral naming those flows with a reason (for example, R5's `fr status` report is the backstop for them).

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-28T19:39:01+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · R5 narrows "every live artifact whose introducing PR has merged" to gate-passing plans/specs and drops runs/usage

check: traceability
evidence: R5 and §C versus i2 "report every live artifact whose introducing PR has merged," and "a live artifact is legal only while the PR that introduced it is open."; decision d3-status-advisory ("Extend `fr status`'s gh-free 'merged but not archived' sweep to every kind"); status_cmd.py:137-141 (archivable = merged AND locally complete)
scope: This is how the change defines its own structural rule, and it is narrower than both the input and d3. I am unsure whether d2's per-kind gate was meant to cover reporting as well, so I have tagged it in scope.
resolution: reinterpreted
R5 opens with "every live artifact whose introducing PR has merged", but §C lists only four narrower things. A plan counts only once the archive gate passes, so a merged plan with open manual phases is not listed. A spec counts only when `_spec_fully_implemented` is true, so a merged spec with a pending slice or no plan rows is never owed. Live runs/usage files are not listed at all, although d3 says "every kind". §C also never names the per-kind "command that clears it" that R5 and d3 promise. Resolve this `unconfirmed` with a note stating exactly which artifacts get reported, or widen §C to the literal reading (every kind, runs/usage included) and name the clearing command for each.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-28T19:39:01+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · Debug-journal findings lines in the branch brief (out-of-scope OR open) are invented, and `_out_of_scope_lines` does not produce that shape

check: traceability
evidence: §D second bullet ("every debug journal in `branch_artifacts` whose effective finding state is `out-of-scope` or `open`, using the same `_out_of_scope_lines` shape with `--scope debug`"); Deferred row for #458; packages/fr/src/fr/run/closeout.py:93-115 (filters `st == "out-of-scope"` only and emits `--state deferred --tracked-by`)
scope: This is new user-visible brief content introduced by this spec with no requirement behind it.
resolution: invented
The brief would now list debug findings, and it would include `open` ones, telling the operator to resolve them `--state deferred --tracked-by '<#N>'`. That is a new way to close an open finding at close-out. No requirement row holds this behaviour; the only mention is the reason text on the #458 deferral, and #458 was itself deferred. `_out_of_scope_lines` would also need a state parameter to emit `open` findings, which §D does not say. Either resolve it `unconfirmed` with a note stating exactly which lines are printed, or drop it so the brief carries only today's run-mode out-of-scope lines.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-28T19:39:01+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · §D claims the run-mode housekeeping branch is "unchanged", but the no-plan fallback and commit line both change

check: consistency
evidence: §D first bullet vs packages/fr/src/fr/run/closeout.py:184-186 (fallback `chore/closeout-{state.run}`), :177 (housekeeping printed only `if plan_path or out_of_scope`), :206-211 (commit message `chore: archive <plan_slug>`; no-plan case prints `git push` only)
scope: These are this change's own edits to the existing brief, and the spec misdescribes them.
resolution: n/a
Today a run with no plan falls back to the run id, `chore/closeout-<run-id>`. The spec's `chore/closeout-<branch-slug>` changes that, and it also changes the commit message to `chore: close out <b>` and makes the housekeeping block unconditional. R2 says `--run` "adds only the run-specific lines", so the spec should state these run-mode changes explicitly instead of labelling the naming "(unchanged)". It should also say whether `chore/archive-<plan-slug>` keeps the old `chore: archive <slug>` commit line.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-28T19:39:01+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · Test Plan covers only the run-mode happy path, and most designed behaviour is untested

check: consistency
evidence: ## Test Plan (a single post-merge `fr pickup --run` walk) vs R1/§D (`fr pickup --branch` with no run cursor, its exit-2 refusals), R4/§B.2 (refuse an unmerged branch), §B.3 (`held:` lines, the "nothing to archive" exit 0), R5/§C (`fr status` owed listing for each kind), R6/§E (fr-debugging relay), R7/§F/§G (`--all` moves debug + orphan journals; `archive_twin` journal pairs keep matrix refs resolving)
scope: The rule is that "nothing the design promises is missing from the Test Plan", and this spec's design outruns its Test Plan.
resolution: n/a
The one scenario never exercises the path the issue exists for, a branch with no run cursor (fr-debugging). It checks R5 only negatively ("no owed artifact"), and it never checks the refusal or held paths, the `archive_twin` extension, or the one-time sweep. Add Test Plan entries, at least at unit level, for each of these so the acceptance rows have something to cite.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-09-28T19:39:01+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · §B does not say how `fr archive --branch <b>` resolves the branch ref, or how it treats --no-spec-sweep

check: consistency
evidence: §B.1-2 vs §D last bullet (pickup resolves the branch locally or as `origin/<b>`); packages/fr/src/fr/commands/isolation_cmd.py:893-896 (verify-merge checks every surviving ref, `origin/<b>` after a fresh fetch and the local branch); packages/fr/src/fr/commands/archive_cmd.py:88-92,112-121 (`--no-spec-sweep` exists; the `--sweep-only` conflict list includes it)
scope: These are gaps in the new mode's own contract.
resolution: n/a
`branch_changes_present` needs a resolvable `<b>`, and after merge the remote branch is often deleted, while the local one may be absent on a fresh clone or pod. §B names neither the ref it diffs nor what happens when `<b>` does not resolve; Error handling covers only pickup's "does not resolve". §B lists four flags it conflicts with but not `--no-spec-sweep`, and it does not say whether that flag is honoured in `--branch` mode. State the ref-resolution order (matching verify-merge) and whether `--no-spec-sweep` is accepted.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-09-28T19:39:01+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · A §G sweep via `fr archive --all` is repo-wide, but its commit and PR count describe only debug journals

check: consistency
evidence: §G; packages/fr/src/fr/commands/archive_cmd.py:153-159,232-246 (`--all` archives every gate-passing plan, runs the repo-wide spec sweep, repairs refs repo-wide)
scope: This is a side effect of this change's own sweep step. It is small, but it sits in this PR.
resolution: n/a
d5 chose `fr archive --all`, so the command is right. But on this branch it will also move any merged, complete plan, any spec the sweep qualifies, and orphan journals, and it rewrites refs in passing. The commit `chore: sweep live debug journals (#733)` and "the PR body states the count moved" should cover every move `--all` makes, or §G should state that nothing but debug and orphan journals is expected to move and have the phase check that.

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-09-28T19:39:01+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · Line citations drift, and the `_spec_fully_implemented` contract is misstated

check: codebase
evidence: Background "closeout_brief (packages/fr/src/fr/run/closeout.py:125)" — defined at closeout.py:118 (:125 is the deliver check); "fr pickup --run (packages/fr/src/fr/commands/pickup_cmd.py:46)" — pickup_command is at pickup_cmd.py:24, :46 is `require_migrated_layout()`, the --run branch is :48; §C "`_spec_fully_implemented(spec, repo_root, gh=None)` is true" — packages/fr/src/fr/migrate.py:882 returns `tuple[bool, str | None]`
scope: These are small inaccuracies in the spec's own references. I tagged it in scope because a fix is trivial.
resolution: n/a
Correct the two line numbers. Note that `_spec_fully_implemented` lives in `fr.migrate` and returns `(implemented, note)`, so §C's predicate should test `[0]`, and the note could feed the held/owed message.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-28T19:39:01+00:00 -->
### spec-review · review · independent spec review: 8 findings

input-coverage:
```input-coverage
| span | coverage |
|---|---|
| "/fr-goal Close-out is an always condition of every fr flow: branch-keyed, archives every artifact the branch added" | R1, R3 |
| "Batch `closeout-always-2` of derio-net/super-fr: 1 issues, delivered as ONE pull request." | context |
| "## super-fr#733: Close-out is an always condition of every fr flow: keyed on the branch, archives every artifact it added (fr-debugging has none; 26 debug journals never archived)" | R1, R3, R6, R7 |
| "fr-debugging has no close-out and `fr archive` moves only plans/specs and their journals: 26 debug journals live on main since 2026-07-23, none ever archived (no implemented/journals/debug/)." | context |
| "Close-out is per-skill, hung off the fr-goal run cursor." | context |
| "Note: Feature (fr-goal)." | context |
| "Branch-keyed close-out + "live only while its PR is open" check." | R1, R5 |
| "Batch `closeout-always`, after `reverted-merge` (#716 edits the same branch-diff code in isolation/local.py); `closeout-queue` (#667) builds on it." | context |
| "## Why these belong together" | context |
| "Retry of the batch cancelled on 2026-09-28 at its question gate (#783): dispatch only after question-order (#783) merges." | context |
| "Wave 5, after reverted-merge (#716 edits the branch-diff code in fr/isolation/local.py that this reuses)." | context |
| "fr-debugging has no close-out, and fr archive moves only plans and specs, so 26 debug journals have never been archived." | context |
| "One close-out keyed on the branch (verify-merge, archive everything the branch added including debug journals, housekeeping PR, isolation down), with fr pickup --run as a caller." | R1, R2, R3, R4 |
| "A structural check reports live artifacts whose PR has merged, and fr-debugging's deliver relays the close-out line." | R5, R6 |
| "The first run sweeps the 26." | R7 |
| "closeout-queue (#667) builds on this." | deferred |
| "The issue's design is a direction; the brainstorm decides the shape." | context |
| "## Delivery rules" | context |
| "- Work on branch `feat/batch-closeout-always-2`." | context |
| "- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:" | context |
| "Closes derio-net/super-fr#733" | context |
| "- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels." | context |
| "## Problem" | context |
| "Only fr-goal has a post-merge close-out. It hangs off the run cursor: `deliver` relays `fr pickup --run <run-id>`, and the brief it prints runs verify-merge, `fr archive`, the housekeeping PR and `isolation down`." | context |
| "fr-debugging has none. Its SKILL.md never mentions archiving, a close-out or `fr pickup`, and a debug run keeps no run cursor that one could hang off." | context |
| "`fr archive` also moves only plans, specs and their journals. The result, on `origin/main` at baff515e:" | context |
| "- 26 debug journals are still live under `docs/superpowers/journals/debug/`, dating from 2026-07-23 to 2026-09-27." | context |
| "- None has ever been archived. `docs/superpowers/implemented/journals/` has `plans/` and `specs/`, but never a `debug/`." | context |
| "Nothing reports this, because every flow decides for itself whether it has a close-out. A flow that doesn't have one leaves its files live on `main`, and nobody notices." | context |
| "## Proposal (a design direction; the shape is for the brainstorm)" | context |
| "Make the close-out an always-on condition at the end of **every** fr-shaped flow." | missing s1 |
| "Key it on the **branch**, not the skill or the run cursor, because every flow ends with a branch and a PR." | R1 |
| "1. **One close-out keyed on the branch** (for example `fr closeout --branch <b>`, or `fr pickup --branch <b>`):" | R1 |
| "- `fr isolation verify-merge`;" | R1, R4 |
| "- archive every live artifact the branch *added* (plans, specs, and journals of every scope, `debug` included);" | R3 |
| "- the housekeeping PR;" | R1 |
| "- `isolation down`." | R1 |
| ""What did this branch add" already has hardened diff logic in `branch_changes_present` (#696, #727)." | R4 |
| "fr-goal's `fr pickup --run` becomes a caller of it, not a second path." | R2 |
| "2. **A structural rule that catches misses:** a live artifact is legal only while the PR that introduced it is open." | R5 |
| "After that PR merges, the file belongs under `implemented/`." | R5 |
| "`fr status`" | R5 |
| "and/or `fr triage check`" | deferred |
| "report every live artifact whose introducing PR has merged, so a flow that skips its close-out shows up instead of piling up." | R5 |
| "3. **fr-debugging's `deliver`** relays the same close-out line fr-goal does." | R6 |
| "The first run clears the 26 existing debug journals as a one-time sweep." | R7 |
| "## Related" | context |
| "- #667, the batch close-out queue, should build on this: it becomes a loop over (1), one branch per merged batch." | deferred |
| "- #458 (`fr archive` offering to file open ends) belongs in the same close-out step." | deferred |
```
decisions: d1-surface (§D split closeout_brief / branch_closeout_brief, §B archive --branch), d2-added-and-modified (§A "added and modified alike", §B per-kind gates), d4-no-debug-cursor (§E), d5-sweep-in-pr (§C/§G) are honoured. d3-status-advisory's "every kind" is only partly honoured; see s2.
verified: 26 file:line citations checked (local.py:545,562,624; archive.py:208,275,348,374,467,513,531; journal/model.py:38,67,217,226; archive_cmd.py:63,78; closeout.py:93,118; pickup_cmd.py:24; status_cmd.py:160; migrate.py:882; acceptance/model.py:43,46 and the five archive_twin callers; isolation_cmd.py:878; hostclient.py:61; fr-debugging SKILL.md:101,108; fr-goal SKILL.md:104-105; the four debug-path prose mentions; fr-goal.yaml the only shipped workflow).

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-28T19:39:01+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: "every fr-shaped flow" is dropped: only fr-goal and fr-debugging relay the close-out

Added R8 (every shipped skill whose flow ends at a PR it opens relays a close-out line — fr-goal's `--run` line, fr-debugging and standalone fr-execute `fr pickup --branch`, fr-isolation's cleanup points at it; fr-dispatch's runner PRs are backstopped by R5) with §E prose, Test Plan item 8 and acceptance row `every-pr-flow-relays-closeout`.

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-28T19:39:01+00:00 state=open resolves=s2 unconfirmed=true -->
### s2-resolved · finding [unconfirmed] · resolves s2: R5 narrows "every live artifact whose introducing PR has merged" to gate-passing plans/specs and drops runs/usage

§C now covers every kind with its clearing command: debug journals on the default ref (`fr archive --all`), archivable plans with their run/usage/journal (`fr archive <plan-dir>`), fully implemented specs (`fr archive --sweep-only`), orphan plan/spec journals and orphan runs (`fr archive --all`). Merged plans with open manual phases keep today's non-owed block, and held specs get a visible `held live (spec)` block with their reason. Nothing live and merged is silent.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-28T19:39:01+00:00 state=open resolves=s3 unconfirmed=true -->
### s3-resolved · finding [unconfirmed] · resolves s3: Debug-journal findings lines in the branch brief (out-of-scope OR open) are invented, and `_out_of_scope_lines` does not produce that shape

Dropped. The brief prints no debug-journal finding lines; its only findings lines are today's run-mode out-of-scope ones from the run's spec/plan journals (§D, #458 deferred).

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-28T19:39:01+00:00 state=fixed resolves=s4 -->
### s4-resolved · finding [fixed] · resolves s4: §D claims the run-mode housekeeping branch is "unchanged", but the no-plan fallback and commit line both change

§D now carries an explicit before/after table of the run-mode changes (archive line, always-printed housekeeping block, unchanged housekeeping branch naming incl. `chore/closeout-<run-id>`, commit line kept as `chore: archive <plan-slug>` with a plan, `chore: close out <b>` otherwise).

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-09-28T19:39:01+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: Test Plan covers only the run-mode happy path, and most designed behaviour is untested

Test Plan gains eight pre-merge unit-level items covering branch-mode pickup, refusals, held paths, modified-only journals, status owed/held listing, --all debug/orphan moves, archive_twin journal pairs with acceptance check, and the skill-relay tripwire.

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-09-28T19:39:01+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: §B does not say how `fr archive --branch <b>` resolves the branch ref, or how it treats --no-spec-sweep

§B.2-4 now resolve refs as verify-merge does (explicit-refspec fetch of origin/<b>, then every ref that resolves; exit 2 when none), check presence per ref, union the changed paths, and accept --no-spec-sweep (specs then reported held).

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-09-28T19:39:01+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: A §G sweep via `fr archive --all` is repo-wide, but its commit and PR count describe only debug journals

§G now records `fr status`'s owed set first, runs `fr archive --all`, treats any move outside that set as a finding, commits all moves as `chore: sweep owed artifacts (#733)`, confirms `fr acceptance check`, and lists every move by kind in the PR body.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-09-28T19:39:01+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: Line citations drift, and the `_spec_fully_implemented` contract is misstated

Background citations corrected to pickup_cmd.py:24/:48 and closeout.py:118; §C uses `fr.migrate._spec_fully_implemented(...)[0]` and feeds its note into the held block.
