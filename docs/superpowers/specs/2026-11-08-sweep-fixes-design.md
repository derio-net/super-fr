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

R1. `fr acceptance set-status` accepts `--issue` without `--status`: a link-only update keeps the row's status and its existing note. `--notes` is then optional and, when given, is appended to the note instead of replacing it.
R2. Without `--status`, any flag other than `--id`, `--issue` and `--notes` is refused with nothing changed; with `--status`, `--notes` stays required and replaces the note as it does today.
R3. `render.tracked_rows` prints a link-only command that runs and keeps the row's note.
R4. `fr journal resolve` printed by the discharge path uses `--note`.
R5. The `row:` discharge command names every flag `--walk` requires, as placeholders.
R6. A test executes every `fr` command these flows print against a fixture repo, with placeholders filled: the backfill dry-run block, the `--yes` report, `fr gate pass` output including its retry line, and the commands inside tracker bodies and adopt comments. A new `fr …` command literal in `gatebackfill/render.py`, `gatebackfill/trackers.py` or `gatebackfill/close.py` fails that test until it is covered.
R7. An open issue carrying a debt digest marker as a line of its own is never a look-alike tracker, whatever its title and whoever wrote it. An issue the manifest names by `issue:` still matches.
R8. Every heading `find_test_plan_heading` refuses as a near-miss has a repair: the set refused and the set repaired are the same set, pinned with one fixture per form (levels `#`, `##`, `###`; number prefixes `6.`, `6)`, `§6`, `6.1`; a trailing parenthetical; another case), each migrated and then validated clean.
R9. The repair leaves the Test Plan's steps as the writer meant them. Promoting `###` shifts every heading up one level from the Test Plan to the next `#` or `##` heading; demoting `#` shifts every heading down one level from the Test Plan to the next `#` heading. Code fences are respected, and the repair's description says that neighbouring headings move.
R10. `fr gate pass --keep <key>` (repeatable) converts that key's tracker to the tracked-only form instead of closing it, with a comment saying the key is still owed. On an adopted issue it posts the tracked-only adopt comment and prints no close command.
R11. A `--keep` key that no tracker of this PR and gate holds is refused before any write, on the first pass and on the retry route alike.
R12. A closing comment from a gate pass names the discharge command still owed for that key, so it no longer reads as if the item were done.
R13. `fr gate backfill` lists, and with `--yes` closes, an fr-owned tracker carrying `fr-gate-passed:` once its key is discharged, under the `owned_owed_key` author and label guard, with a closing comment naming the evidence. An adopted issue carrying this account's `fr-gate-adopt-passed:` comment gets one comment naming the evidence and a printed close command, and is never closed by fr.
R14. A key counts as discharged only on positive evidence, with the fold holding it through the tracker alone: a `row:` whose row exists with a status outside `DEBT_STATUSES`, a `plan:` whose phase exists with every step ticked or marked n/a, a `spec:` whose step has a recorded outcome. An `issue:` key, a manifest-only key and anything unreadable are never discharged.
R15. Tracker closes are recorded in the plan file by the dry run and re-checked at `--yes`. A key that became discharged after the dry run waits for the next dry run. They happen only from a checkout whose HEAD the default ref contains: elsewhere a note says so and nothing closes.
R16. `release.py` cuts no RC when no installable path differs between HEAD and the newest tag above the last final (or the last final, when no RC is above it), and prints `nothing installable changed since <tag>: no release`. So no tag, release or staged-suite run.
R17. Every path is installable except `docs/`, `tests/`, `.github/`, `.changes/`, root-level `*.md` and `.test_durations`. The definition lives once in `scripts/`, and a test over every tracked path pins that each `requires_bump` path is installable.
R18. The final path is unchanged: gates passing with no code change since the newest RC still cut the final, and a pending fragment with nothing waiting still releases even when no installable path changed. `--version` is unchanged, and an untagged RC at HEAD is still tagged by the next run.

## 3. Design

### A. Printed commands (R1-R6)

`set_status_cmd`: `--status` and `--notes` become optional at the option level and are validated in
the body, so the two refusals keep today's wording and exit code. A link-only call reuses the row's
status and builds the note as the old note plus the given one, separated by `; ` (the old note alone
when none is given). It passes through the same `Row` construction and `_apply_rows` path, so the
report set regenerates. `AcceptanceItem` requires a note only when a status moves, which a link-only
call does not do (`record/apply.py`).

`tracked_rows` prints `fr acceptance set-status --id <row> --issue <ref>`. The `row:` discharge line
gains `--harness "<harness>" --model "<model>" --strategy "<strategy>"`.

The executing test lives in `tests/unit/test_printed_commands_run.py`. It builds one fixture repo
holding each key kind, drives each flow with the fake client from `gatebackfill_fixtures.py`,
extracts each `fr …` line, substitutes every `<placeholder>` with a value valid for that flag, and
runs it through the CLI runner, asserting exit 0. `fr gate pass` runs as its dry run (no `--yes`).
`gh issue close` lines are not `fr`'s to execute: they are parsed and shape-checked here, and run
against the recording `gh` in the scenario. A source scan over the three modules holds a table of
the `fr <verb>` literals they contain, which is R6's guard against a new emitter.

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
and `## Coverage`, so the items under Coverage do not become steps.

### D. Tracker close (R10-R15)

`close_gate_trackers` takes `keep: frozenset[str]`, and `CloseReport` gains `kept`. The driver's pass
passes none, because its rows are walked. `gate_cmd` lists the matching trackers before `pass_gate`
to apply R11. A kept owned tracker gets `rewrite_body(passed_tracker_body(...))` and a comment. From
then on it is an ordinary tracked-only tracker, so `fr_gate_marker` is `None` and a later pass leaves
it alone.

`gatebackfill/close.py` gains `discharged_evidence(root, key) -> str | None` (R14), reusing
`load_matrix`, `DEBT_STATUSES`, `_phase_facts`, `find_spec` and `archive.recorded_outcomes`.
`PlanFile` gains an optional `closes: list[str]` of keys, written by the dry run and shown in the
summary under `Trackers to close`. The plan file is a host-side cache and not an artifact kind, so
there is no stamp; an older `fr` refuses the new key and a fresh dry run clears that. At `--yes`,
`apply_plan` re-checks each key (R14 and the marker) before closing. A forge error is recorded on
that tracker and the rest go on, as elsewhere in apply. An adopted issue's comment carries a marker
line, so a second `--yes` writes nothing. `tracking: none` closes nothing.

### E. No-op releases (R16-R18)

`scripts/installable.py` (stdlib) holds `is_installable(path)` and
`installable_changed(repo, tag)`, which runs `git diff --name-only <tag> HEAD`. A two-dot diff
compares the trees, so a revert to the tag's tree counts as no change. In `compute`, the RC branch
replaces `_merged_since(rcs[-1])` with `installable_changed` against the newest tag above the base
or, when there is no RC, against the last final tag. With no tag to compare against, it cuts an RC as
it does today.

An untagged RC at HEAD: `plan.new` stays `None`, `prepare` returns `None` and `finish` tags HEAD, so
the recovery route is untouched. Promotion: "nothing waits" takes the branch above this check, so
identical code still promotes. A denylist errs towards a spare RC, never a stranded change.

**Amends** exit-gates R20's "nothing when nothing merged since the newest RC tag" to "nothing
installable". The `AGENTS.md` "Release gating" paragraph and `docs/gate-backfill.md` are updated in
this PR. No published explainer describes when an RC is cut (`docs/explainers/` was checked), so the
explainer-currency trigger is met by saying so in the PR body.

## 4. Decisions

Operator-answered in the question round; see the spec journal.

## 5. Risks

- R14 reads the local checkout, so a stale checkout only delays a close: it can miss a discharge but
  cannot invent one on the default ref, which is what R15's containment check enforces.
- A denylist counts `scripts/release.py` and other non-shipped scripts as installable. That costs a
  spare RC, the accepted direction.

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
