<!-- fr:journal-schema=3 -->
# Journal: 2026-11-08-sweep-fixes

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-08T16:06:58+00:00 input=true -->
### operator-brief · discovery · The operator's brief (via the wave coordinator), private repo names redacted

Goal: fix the fr bugs the cross-org gate-backfill sweep found. Run with /fr-goal in super-fr; v6.1.2 is installed.

Issues (each holds the exact symptom and a proposed fix):
1. #1327 Printed commands that cannot run: `fr gate backfill --yes` prints `fr acceptance set-status --id X --issue …` without the required `--status`, and `fr gate pass` prints `fr journal resolve … --body` (resolve takes `--note`). Proposed: let `set-status` accept `--issue` alone (a link-only update keeps the status), fix the printed `--body`, and add a test that executes every command fr prints for these flows against a fixture, so this class cannot recur.
2. #1334 The weekly digest issue (titled "Acceptance debt" in older repos, "<repo>: Technical debt" from the debt engine) matches every row as a look-alike tracker. Exclude it by its markers, not its title.
3. #1325 The Test Plan near-miss repair renames `## N. Test Plan (…)` but not `### Test Plan`, which validate refuses. Make the refused set and the repaired set the same set, and pin that with one fixture per near-miss form.
4. #1328 A tracked-only tracker (`fr-gate-passed` marker) is never closed once its key is discharged.
5. #1323 `fr gate pass` closes held trackers whose key is still owed (a deliberate partial pass).
6. #1321 `release.py` cuts an RC for docs-only/close-out merges. Release nothing when no installable path changed since the newest tag, but an RC→final promotion with identical code must still release.

If a fix is larger than expected, or two fixes conflict, say so in the question round: splitting into a second run is fine. #1328/#1323 touch the same close path (spec 2026-11-01-gate-backfill §H), so do them together.

Context: the sweep scripts carry workarounds for #1327 (`--status` appended) and #1334 (`is_digest`). Once the release ships those workarounds are dead code: say so in the PR so the coordinator can drop them.

Constraints: no local full suite (Mac load), targeted tests through the coordinator's test-slot wrapper, CI runs the full suite (`tests: ci`). One question round, draft PR, change fragment(s), never edit versions. #1321 changes release behaviour, so it needs a spec line in the exit-gates/version-bump specs and an explainer check. Every public artifact must be third-party-privacy clean: say "a private consumer repo". Recovery-wave prep may run in parallel: stay out of `fr/triage/batch*` unless an issue requires it.

<!-- fr:journal kind=decision scope=spec id=q1-one-run created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q1-one-run · decision · One run, one PR

Operator: one run and one PR with five phases. Only #1321 changes release behaviour; the fixes do not conflict.

<!-- fr:journal kind=decision scope=spec id=q2-keep-flag created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q2-keep-flag · decision · #1323: explicit --keep <key>

Operator: `fr gate pass --keep <key>` converts a tracker to tracked-only; the default still closes and its comment names the discharge still owed. Consulting the fold was rejected: every key is still owed at pass time in the normal flow.

<!-- fr:journal kind=decision scope=spec id=q3-repair-neighbours created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q3-repair-neighbours · decision · #1325: repair neighbouring headings too

Operator: shift the neighbouring headings so the promoted section's steps stay as written, rather than renaming one heading or narrowing the matcher.

<!-- fr:journal kind=decision scope=spec id=q4-denylist created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q4-denylist · decision · #1321: installable is a denylist

Operator: everything is installable except docs/, tests/, .github/, .changes/, root *.md and .test_durations, so an unknown path errs towards a spare RC. A test pins requires_bump as a subset.

<!-- fr:journal kind=decision scope=spec id=q5-final-unchanged created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q5-final-unchanged · decision · #1321: the final path is unchanged

Operator: a pending fragment with nothing waiting still releases, even when no installable path changed. The no-op applies to RC cuts only, narrowing the issue's 'RCs and finals alike'.

<!-- fr:journal kind=decision scope=spec id=q6-verification created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### q6-verification · decision · Candidate strategy, tester gate on the #1321 live row

Operator: strategy candidate with installed-CLI scenarios for the printed commands and the heading repair; other rows `none`, pinned by CI tests; the release row `live` with gate tester, walked on the next archive PR merge.

<!-- fr:journal kind=decision scope=spec id=archived-specs-not-edited created=2026-11-08T16:06:58+00:00 decided_by=operator -->
### archived-specs-not-edited · decision · The amended release rule lives in this spec and AGENTS.md

The brief asks for a spec line in the exit-gates and version-bump specs. Both are archived under implemented/, which is frozen, so this spec states the amendment and AGENTS.md restates the rule.

<!-- fr:journal kind=discovery scope=spec id=link-command-wipes-notes created=2026-11-08T16:06:58+00:00 -->
### link-command-wipes-notes · discovery · The printed link command also replaces the row's note

`set-status` writes `notes` over the row's note, so the sweep's link commands (with the workaround `--status`) replaced existing notes: #1383 turned a `Shipped in #1139: …` note into `tracked by …`. R1 makes a link-only update keep the note. Restoring notes already replaced is a follow-up.

<!-- fr:journal kind=discovery scope=spec id=row-discharge-also-broken created=2026-11-08T16:06:58+00:00 -->
### row-discharge-also-broken · discovery · The row discharge command is a third printed command that cannot run

`discharge_command` prints `--walk` without `--harness`, `--model` and `--strategy`, which `_walk_from_flags` requires. Not named by #1327; fixed by R5 and covered by R6.
