# Sweep fixes: printed commands, digest look-alikes, heading repair, tracker close, no-op releases

**Issues:** #1327, #1334, #1325, #1328, #1323, #1321 (found by the cross-org gate-backfill sweep).

## 1. Goal

Six defects, each found in real use, fixed on one branch in one PR. Each section below is
independently reviewable; #1323 and #1328 share one, because both act on the §H close path of
`2026-11-01-gate-backfill-design.md`.

### Non-goals

- Restoring row notes that earlier link commands already replaced, here or in consumer repos
  (recorded as a follow-up).
- A tripwire over every command `fr` prints anywhere: this covers the gate and backfill flows.
- Widening `requires_bump`, so the change-fragment gate is unchanged.
- Editing the archived exit-gates, version-bump or gate-backfill specs: `implemented/` is frozen.
  This spec carries the amended rules, and `AGENTS.md` restates the release rule.

## 2. Background (read from the code)

- `fr acceptance set-status` requires `--status` and `--notes`, and writes `notes` over the row's
  note (`commands/acceptance_cmd.py`). `render.tracked_rows` prints it with `--issue` and `--notes`
  only, so the command exits 2. The sweep worked around that by appending the current status, and
  the note was then replaced: #1383 turned a row's `Shipped in #1139: …` into `tracked by …`.
- `trackers._journal_resolve` prints `fr journal resolve … --body`, but that verb takes `--note`.
- `trackers.discharge_command` prints `set-status --status walked --walk "<walk log>" --notes …`
  for a `row:` key, but `_walk_from_flags` requires `--harness`, `--model` and `--strategy` too.
- `candidates._lookalikes` matches a row id anywhere in an open issue. The weekly digest lists
  every row id, so it matches them all. `fr.triage.debt.has_marker` already reads both digest
  markers (`fr-technical-debt`, `fr-acceptance-digest`) as a line of their own.
- `find_test_plan_heading` refuses `#` to `###` near-misses, and the repair (`_renamable`) handles
  only `##`. The section reader stops at `^#{1,2} ` (`_NEXT_SECTION_RE`).
- `close_gate_trackers` closes every owned tracker whose `fr-gate:<g> pr:<n>` marker names the
  pass. In the normal flow the key is still owed at that moment: the discharge command is printed
  for afterwards (§H step 4). So the debt fold cannot tell a partial pass from a normal one.
- A tracker's own owed marker keeps its key in the fold (`debt/engine._issue_owed`, source `issue`,
  lowest precedence). So "no longer a candidate" never becomes true for a tracked-only tracker, and
  a manifest-only item has no other source at all.
- `release.compute` cuts an RC while a PR waits on a gate unless `_merged_since(newest RC)` is
  false. Any commit counts, so housekeeping merges cut RCs.
- The final path needs no change for docs-only merges: with no fragment pending and HEAD not an
  RC, `compute` already returns "no pending fragments".

## Requirements

R1. `fr acceptance set-status` accepts `--issue` without `--status`: a link-only update keeps the row's status and its existing note, including an empty one. `--notes` is then optional and, when given, is appended to the note instead of replacing it.
R2. Without `--status`, `--issue` is required and any flag other than `--id`, `--issue` and `--notes` is refused with nothing changed, exit 2, naming the missing `--status`; `--notes` alone is refused the same way. With `--status`, `--notes` stays required and replaces the note as it does today.
R3. `render.tracked_rows` prints a link-only command that runs and keeps the row's note.
R4. `fr journal resolve` printed by the discharge path uses `--note`.
R5. The `row:` discharge command names every flag `--walk` requires, as placeholders.
R6. A test executes every `fr` command these flows print against a fixture repo, with placeholders filled, wherever the command sits: on its own line, in backticks, or inline after a colon or `;`. The flows are the backfill dry-run block and its refusal hints, the `--yes` report, `fr gate pass` output including its retry line (run without `--yes`), and the commands inside tracker bodies and adopt comments. A new `fr …` command literal in `gatebackfill/render.py`, `gatebackfill/trackers.py`, `gatebackfill/close.py` or `commands/gate_cmd.py` fails that test until it is covered.
R7. An open issue carrying a debt digest marker as a line of its own is never a look-alike tracker, whatever its title and whoever wrote it. An issue the manifest names by `issue:` still matches.
R8. Every heading `find_test_plan_heading` refuses as a near-miss has a repair: the set refused and the set repaired are the same set, pinned with one fixture per form (levels `#`, `##`, `###`; number prefixes `6.`, `6)`, `§6`, `6.1`; a trailing parenthetical; another case), each migrated and then validated clean.
R9. The repair leaves the Test Plan's steps as the writer meant them, and every section fr reads still reads. Promoting `###` shifts every heading up one level from the Test Plan to the next `#` or `##` heading. Demoting `#` shifts every heading down one level from the Test Plan to the next `#` heading or to the next `##` heading that fr reads by keyword (`## Verification`, `## Implementation Plans`, `## Requirements`), which stays where it is and ends the section. A `######` heading stays at level six. Code fences are respected, and the repair's description says that neighbouring headings move.
R10. `fr gate pass --keep <key>` (repeatable) converts that key's tracker to the tracked-only form instead of closing it, with a comment saying the key is still owed. On an adopted issue it posts the tracked-only adopt comment once and prints no close command, then or on any later pass: this account's `fr-gate-adopt-passed:` comment for the same gate and PR overrides its older `fr-gate-adopt:` comment. `--keep` is refused when there is no checkout to read the key from.
R11. A `--keep` key that no tracker of this PR and gate holds is refused before any write, on the first pass and on the retry route alike. A tracker or adopted issue already in the tracked-only form for this gate and PR counts as holding it, so a retry succeeds and writes nothing for that key. The printed retry line carries every `--keep`.
R12. A closing comment from a gate pass states the key's real position: the evidence when the key is already discharged (R14), the discharge command still owed when it is not, and neither when there is no checkout to read it from. So it no longer reads as if an undischarged item were done, nor claims a discharged one is still owed.
R13. `fr gate backfill` lists, and with `--yes` closes, an fr-owned tracker carrying `fr-gate-passed:` once its key is discharged, under the `owned_owed_key` author and label guard, with a closing comment naming the evidence. An adopted issue carrying this account's `fr-gate-adopt-passed:` comment, for a key discharged by the same rule, gets one comment naming the evidence (with its own marker, so a second run writes nothing) and a printed close command, and is never closed by fr.
R14. A key counts as discharged only on positive evidence, with no source but its own tracker holding it in the fold: a `row:` whose row exists with a status outside `DEBT_STATUSES`, a `plan:` whose phase exists with at least one step and every step ticked or marked n/a, a `spec:` whose step's effective outcome is recorded and not `owed`, or any key whose journal `owed` entry was resolved fixed. An `issue:` key, a manifest-only key and anything unreadable are never discharged.
R15. Tracker closes are recorded in the plan file by the dry run with their issue and evidence, and re-checked at `--yes`. A key that became discharged after the dry run waits for the next dry run. A discharged key leaves the plan's entries, so it is never both owed and closing, and any decision recorded on it is dropped with a note. Closes happen only when HEAD equals the default ref as last fetched and `docs/acceptance/` and `docs/superpowers/` are clean: otherwise, or when no default ref resolves, a note says so and nothing closes.
R16. `release.py` cuts no RC when no installable path differs between HEAD and the newest tag above the last final (or the last final, when no RC is above it), and prints `nothing installable changed since <tag>: no release`. So no tag, release or staged-suite run. A move out of an installable path counts as a change, and the rule applies when the gate state is unknown and to a fragment-only merge alike.
R17. Every path is installable except `docs/`, `tests/`, `.github/`, `.changes/`, root-level `*.md` and `.test_durations`. The definition lives once in `scripts/`, and a test over every tracked path pins that each `requires_bump` path is installable.
R18. The final path is unchanged: gates passing with no code change since the newest RC still cut the final, and a pending fragment with nothing waiting still releases even when no installable path changed. `--version` is unchanged, and an untagged RC at HEAD is still tagged by the next run.

## 3. Design

### A. Printed commands (R1-R6)

`set_status_cmd`: `--status` and `--notes` become optional at the option level and are validated in
the body, and `--walk-outcome` defaults to `None` so R2 can see it (a walk still reads `None` as
`pass`). Typer's own refusal goes away, so the body prints its own: exit 2, naming the missing
option. A link-only call reuses the row's status and builds the note as the old note plus the given
one, separated by `; ` (the old note alone when none is given). It passes through the same `Row`
construction and `_apply_rows` path, so the report set regenerates.

`record/apply.py` currently refuses an empty `notes` on every non-create item, with a message that
is only true of a status move. That check narrows to `item.status != existing.status`, and a test
covers a link-only update of a row whose note is empty. `.claude/rules/acceptance-matrix.md` learns
the link-only form, and both mirror syncs run.

`tracked_rows` prints `fr acceptance set-status --id <row> --issue <ref>`. The `row:` discharge line
gains `--harness "<harness>" --model "<model>" --strategy "<strategy>"`.

The executing test lives in `tests/unit/test_printed_commands_run.py`. It builds one fixture repo
holding each key kind and drives each flow with `FakeGhClient` (`tests/unit/fakes`) and `FakeForge`
(`gatebackfill_fixtures.py`). One extractor finds commands in the output, in tracker bodies and in
adopt comments: whole lines, backtick spans, and the inline `: fr …; fr …` and `record it ran: fr …`
forms. It substitutes every `<placeholder>` with a value valid for that flag and runs each command
through the CLI runner, asserting exit 0. `fr gate pass` and the retry line run as dry runs, with
`--yes` stripped. `gh issue close` lines are not `fr`'s to execute: they are parsed and shape-checked
here, and run against the recording `gh` in the scenario. A source scan over the four modules holds
a table of the `fr <verb>` literals they contain, which is R6's guard against a new emitter.

### B. Digest look-alikes (R7)

`_lookalikes` skips an issue for which `fr.triage.debt.has_marker(body)` is true, before the text
match and after the manifest check, so a manifest-named issue still matches. There is deliberately
no author check, unlike the board's: this only withholds a suggestion. A forged marker costs one
missed look-alike, and the older digests were written by more than one account.

### C. Heading repair (R8, R9)

`_renamable` drops its `## ` limit. `_fn` reads the heading's level, rewrites the region R9 defines
with fences tracked, then renames the heading as it does today, keeping a trailing parenthetical as
the section's first line. `####` and deeper Test Plan headings are not refused, so they are not
repaired. The stamp stays untouched: this is the same `Repair`, with a wider predicate.

Example: a `### Test Plan` under `## Testing`, followed by `### Coverage`, becomes `## Test Plan`
and `## Coverage`, so the items under Coverage do not become steps. A `# Test Plan` followed by
`## Notes` and `## Verification` becomes `## Test Plan`, `### Notes` and `## Verification`.

### D. Tracker close (R10-R15)

**The pass.** `close_gate_trackers` takes `keep: frozenset[str] = frozenset()`, and `CloseReport`
gains `kept`. The driver's call site is not edited: it passes nothing, because its rows are walked.
The listing adds `title` to `OWED_ISSUE_FIELDS` locally, for the tracked-only body. `gate_cmd` lists
the matching trackers before `pass_gate` to apply R11. A kept owned tracker gets its comment first,
then `client.edit_issue_body(passed_tracker_body(...))`: a failure between the two leaves it held, so
a retry repeats the work and at worst repeats a comment, and never loses the key. Once rewritten it
is an ordinary tracked-only tracker, so `fr_gate_marker` is `None` and a later pass leaves it alone.
`_one` reads this account's comments on a foreign issue and lets an `fr-gate-adopt-passed:` for the
gate and PR override the `fr-gate-adopt:` one, returning with no close command. `--keep` needs a
checkout (`root`), because the tracked-only body names the discharge command. The closing comment
takes its wording from `discharged_evidence` (R12).

**The evidence.** `gatebackfill/close.py` gains `discharged_evidence(root, key) -> str | None` (R14),
reusing `load_matrix`, `DEBT_STATUSES`, `_phase_facts` (with the `k/n` it returns, `n >= 1`),
`find_spec`, `fr.ops.holds.fold_step_outcomes` over the spec journal (never
`archive.recorded_outcomes`, which counts `owed` entries), and `journal_owed`'s discharged set. The
journal route matters: `fr journal resolve` is the command `discharge_command` prints first, and once
resolved the engine drops the tracker's item from the fold. So the list is built from the open owned
issues carrying the marker, never from the candidates.

**The plan.** `PlanFile` gains an optional `closes` list of `{key, ref, adopted, evidence}`, written
by the dry run and shown in the summary under `Trackers to close`. `BackfillForge` gains
`issue_comments(number)`, called once per foreign `fr:owed` issue, which is what finds an
`fr-gate-adopt-passed:` comment, since the fold holds such an issue as `issue:<ref>` and not by the
comment's key. A new `fr-gate-adopt-discharged:<key> pr:<n>` marker on the evidence comment makes the
second `--yes` write nothing. A discharged key leaves `entries` in `merge_plan`, so `_apply` never
reports "discharge the key itself" for it, and a recorded `park` or `adopt` on it is dropped with a
note. The plan file is a host-side cache and not an artifact kind, so there is no stamp. An older
`fr` refuses the new key on its dry run as well as on `--yes`, because `load_plan` runs on both paths;
the recovery is deleting the plan file.

**The apply.** At `--yes`, `apply_plan` re-checks each close (R14, R15 and the marker) before
writing. A forge error is recorded on that tracker and the rest go on, as elsewhere in apply.
`tracking: none` closes nothing. R15's check compares HEAD with `merge_evidence().ref` and asks git
for uncommitted changes under the two evidence trees, because the readers use the working tree: a
printed discharge command can leave its evidence uncommitted, and an older HEAD can show a status
that later moved back. Ancestry alone would allow both.

### E. No-op releases (R16-R18)

`scripts/installable.py` (stdlib) holds `is_installable(path)` and
`installable_changed(repo, tag)`, which runs `git diff --no-renames --name-only -z <tag> HEAD`. A
two-dot diff compares the trees, so a revert to the tag's tree counts as no change. `--no-renames`
lists both sides of a move, so a file moved from `plugins/` to `docs/` is a change, and `-z` reads a
non-ASCII path unquoted. In `compute`, the RC branch
replaces `_merged_since(rcs[-1])` with `installable_changed` against the newest tag above the base
or, when there is no RC, against the last final tag. With no tag to compare against, it cuts an RC as
it does today.

An untagged RC at HEAD: `plan.new` stays `None`, `prepare` returns `None` and `finish` tags HEAD, so
the recovery route is untouched. Promotion: "nothing waits" takes the branch above this check, so
identical code still promotes. A denylist errs towards a spare RC, never a stranded change.

**A behaviour this changes, stated:** `.changes/` is not installable, so a merge that lands only a
fragment cuts no RC while something waits, even a major bump after an RC, and also when the gate
state is unknown. The tests in `test_release_script.py` whose fixtures land only a fragment and
assert an RC change to land an installable path too, and a new test pins the fragment-only case.

**Amends** exit-gates R20's "nothing when nothing merged since the newest RC tag" to "nothing
installable". The `AGENTS.md` "Release gating" paragraph (including its "unknown" sentence) and
`docs/gate-backfill.md` are updated in this PR. No published explainer describes when an RC is cut (`docs/explainers/` was checked), so the
explainer-currency trigger is met by saying so in the PR body.

## 4. Decisions

Operator-answered in the question round; see the spec journal.

## 5. Risks

- R15 compares with the default ref as last fetched, so a stale fetch can only delay a close or, if
  a status moved back upstream since, close on evidence that was true at that ref. The next fetch
  and run do not reopen it; the row's own debt still counts in `fr debt`.
- A `### Verification` or `### Implementation Plans` sibling after a promoted `### Test Plan` becomes
  a real keyword section. If the spec already has one, the first still wins; `fr validate artifacts`
  reports a malformed one, so this is visible, never silent.
- A denylist counts `scripts/release.py` and other non-shipped scripts as installable. That costs a
  spare RC, the accepted direction.

## Delivery

- Draft PR, never marked ready by the run. A change fragment `.changes/fix-sweep-fixes.yaml`, bump
  `minor` (`--keep` and link-only `set-status` are new surface). No version edit.
- Targeted tests only, through the coordinator's test-slot wrapper; the full suite runs in CI
  (`tests: ci`).
- No edit under `fr/triage/batch*`: the driver's call site keeps working through `keep`'s default.
- The PR body says that once this ships the sweep scripts' #1327 workaround (`--status` appended) and
  #1334 workaround (`is_digest`) are dead code the coordinator can drop, and that no published
  explainer needed a change. Public artifacts name no private repo: "a private consumer repo".

## Verification

strategy: candidate
gate: none
gate: release-noop-first-real-use=tester
- printed-commands-run: candidate — scenario runs the printed link and discharge commands through the installed CLI against a fixture repo with a recording `gh`
- gate-backfill-digest-not-lookalike: none — unit tests over `_lookalikes` with fixture issues in CI; an installed CLI adds nothing
- test-plan-repair-covers-refused: candidate — scenario migrates a fixture holding each near-miss level through the installed CLI, then validates clean
- gate-pass-keep: none — unit tests drive `fr gate pass` and its retry against the fake client in CI
- gate-backfill-closes-discharged: none — unit tests drive dry run and apply over each key kind and the fake client in CI
- release-skips-rc-nothing-installable: none — `release.py` unit tests over fixture git histories in CI
- release-noop-first-real-use: live — only a real Release run on `main` shows that a housekeeping merge cuts nothing; walked on first real use, the next archive PR merge

## Test Plan

1. [tester] After this PR's RC is cut, merge the next archive or close-out PR. The Release run prints `nothing installable changed since <tag>: no release`, and no new tag or pre-release appears. Then pass the gate and confirm the next run cuts the final with no code change since the RC.

## Implementation Plans

| Plan | Status |
|------|--------|
