# Journal: 2026-09-26-version-bump-churn

<!-- fr:journal kind=decision scope=spec id=d1-intent-on-merge created=2026-09-26T08:04:32 -->
### d1-intent-on-merge · decision · PRs declare a bump in a .changes/ fragment; the release workflow on main assigns the number

Operator chose intent-in-PR / number-on-merge over consolidating the version surfaces.
Consolidation alone shrinks a 13-file conflict to a one-line conflict but keeps the
collision and the CI rerun; only moving the number out of the PR removes both.

<!-- fr:journal kind=decision scope=spec id=d2-no-consolidation created=2026-09-26T08:04:32 -->
### d2-no-consolidation · decision · Version surfaces stay as they are; only the release bot writes them

Once PRs never edit a version surface, bump-version.py already writes all 12 files plus uv.lock.

<!-- fr:journal kind=decision scope=spec id=d3-reports-in-scope created=2026-09-26T08:04:32 -->
### d3-reports-in-scope · decision · Committed acceptance reports drop aggregates; add inserts rows by capability

Operator put the report conflicts in scope. The row-count stamp and status table are shared
write hotspots. Exploration also found append_row always writes at EOF of matrix.yaml,
so insert-by-capability is included to make "different rows do not conflict" actually true.

<!-- fr:journal kind=decision scope=spec id=d4-no-test-skip-guard created=2026-09-26T08:04:32 -->
### d4-no-test-skip-guard · decision · No general version-only test-skip guard

The release commit is pushed with GITHUB_TOKEN, which triggers no workflow, so it reruns nothing.

<!-- fr:journal kind=discovery scope=spec id=ruleset-allows-bot-push created=2026-09-26T08:04:32 -->
### ruleset-allows-bot-push · discovery · main's ruleset enforces only deletion and non_fast_forward

GET /repos/derio-net/super-fr/rules/branches/main returns ["deletion","non_fast_forward"] (2026-09-26),
so a GITHUB_TOKEN release commit can fast-forward main. AGENTS.md's "branch-protection blocks direct
commits" overstates it; the spec corrects the sentence and requires a bypass actor if rules tighten.

<!-- fr:journal kind=discovery scope=spec id=floors-need-a-guard created=2026-09-26T08:04:32 -->
### floors-need-a-guard · discovery · Hand-written fr_version floors name a release number the PR no longer knows

SCOPE_FR_VERSION / WORKFLOW_FR_VERSION and plan_ops refusal text; three introduced in two months.
Spec §3.E adds a PR-time and a release-time guard instead of a mechanism.

<!-- fr:journal kind=review scope=spec id=sr1-review created=2026-09-26T08:12:00 -->
### sr1-review · review · independent spec review: 12 findings (2 high, 5 medium, 5 low)

Dispatched fr-spec-reviewer (read-only, separate context). All d1-d4 honoured. Two HIGH: report sharp-line panels still a hotspot; bot-push verified against rulesets only. Rest: dependants of the deleted script, rule-2 over-strictness, floor regex, unguarded uv.lock in CI-less commit, HERMES.md, counts, permissions, test plan gaps, CI job list.

<!-- fr:journal kind=finding scope=spec id=sr1-f1 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f1 · finding [open] (reviewer: in scope) · HIGH: committed reports still share a status-panel hotspot, so rows added far apart still conflict in the committed reports; Test Plan item 7 would fail

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f2 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f2 · finding [open] (reviewer: in scope) · HIGH: 'the bot can push to main' was checked against rulesets only; classic branch protection was not checked

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f3 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f3 · finding [open] (reviewer: in scope) · MEDIUM: tests/unit/test_version_bump_guard.py and matrix row invariants-tripwires both depend on the script this spec deletes

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f4 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f4 · finding [open] (reviewer: in scope) · MEDIUM: gate rule 2 would refuse adding a new workspace member or plugin manifest

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f5 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f5 · finding [open] (reviewer: in scope) · MEDIUM: the floor guard's 'any >=X.Y.Z string literal the diff adds or changes' flags historical floors and non-floors

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f6 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f6 · finding [open] (reviewer: in scope) · MEDIUM: nothing checks that the uv.lock changes in the CI-less release commit are version-only, contrary to d4's rationale

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f7 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f7 · finding [open] (reviewer: in scope) · MEDIUM: HERMES.md's release and branch-protection rules are not in the rewrite list

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f8 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f8 · finding [open] (reviewer: in scope) · LOW: §1 says '12 files'; the tree has 10 files carrying 11 values

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f9 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f9 · finding [open] (reviewer: in scope) · LOW: rule 2 says 'values bump-version.py --check enumerates', but --check does not read uv.lock

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f10 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f10 · finding [open] (reviewer: in scope) · LOW: release.yml needs issues: write, and the notes source for a tag-only rerun is not defined

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f11 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f11 · finding [open] (reviewer: in scope) · LOW: the Test Plan misses several promised behaviours, and existing tests pin the aggregates

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f12 created=2026-09-26T08:12:00 state=open review_scope=in -->
### sr1-f12 · finding [open] (reviewer: in scope) · LOW: AGENTS.md's CI job list names version-bump-required

See the reviewer's return; evidence and suggested fix quoted in the resolution.

<!-- fr:journal kind=finding scope=spec id=sr1-f1-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f1 -->
### sr1-f1-resolved · finding [fixed] · resolves sr1-f1: HIGH: committed reports still share a status-panel hotspot, so rows added far apart still conflict in the committed reports; Test Plan item 7 would fail

Confirmed report.py:220-233 (one-line HTML panel). §3.I now drops the sharp-line panels from the deterministic render as well; TP7 uses not-implemented rows.

<!-- fr:journal kind=finding scope=spec id=sr1-f2-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f2 -->
### sr1-f2-resolved · finding [fixed] · resolves sr1-f2: HIGH: 'the bot can push to main' was checked against rulesets only; classic branch protection was not checked

Read classic protection 2026-09-26: GET branches/main/protection -> 404 Branch not protected. Recorded in §3.C; release.py distinguishes a protection refusal (fails at once, names bypass actor) from a lost race; TP4 covers it.

<!-- fr:journal kind=finding scope=spec id=sr1-f3-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f3 -->
### sr1-f3-resolved · finding [fixed] · resolves sr1-f3: MEDIUM: tests/unit/test_version_bump_guard.py and matrix row invariants-tripwires both depend on the script this spec deletes

§3.B now retargets test_version_bump_guard.py to check-change-fragment.py and updates row invariants-tripwires via fr acceptance set-status in this PR.

<!-- fr:journal kind=finding scope=spec id=sr1-f4-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f4 -->
### sr1-f4-resolved · finding [fixed] · resolves sr1-f4: MEDIUM: gate rule 2 would refuse adding a new workspace member or plugin manifest

Rule 2 now refuses only a changed value; an added surface at the base version passes. TP3 covers both cases.

<!-- fr:journal kind=finding scope=spec id=sr1-f5-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f5 -->
### sr1-f5-resolved · finding [fixed] · resolves sr1-f5: MEDIUM: the floor guard's 'any >=X.Y.Z string literal the diff adds or changes' flags historical floors and non-floors

§3.E keys on fr_version-shaped literals' lower bound newer than base (release: previous tag); at-or-below-base passes; upper-bound moves and reformatting never trip. TP5 extended.

<!-- fr:journal kind=finding scope=spec id=sr1-f6-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f6 -->
### sr1-f6-resolved · finding [fixed] · resolves sr1-f6: MEDIUM: nothing checks that the uv.lock changes in the CI-less release commit are version-only, contrary to d4's rationale

release.py runs uv lock --check first and refuses any staged line outside version_surfaces() and the consumed fragments; §3.C sentence corrected; TP4 covers it.

<!-- fr:journal kind=finding scope=spec id=sr1-f7-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f7 -->
### sr1-f7-resolved · finding [fixed] · resolves sr1-f7: MEDIUM: HERMES.md's release and branch-protection rules are not in the rewrite list

§3.G now rewrites HERMES.md rules 2 and 3 and its gate list alongside AGENTS.md.

<!-- fr:journal kind=finding scope=spec id=sr1-f8-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f8 -->
### sr1-f8-resolved · finding [fixed] · resolves sr1-f8: LOW: §1 says '12 files'; the tree has 10 files carrying 11 values

§1 item 2 and d2 row now say 10 files (11 values) plus 6 uv.lock lines. (The brainstorm journal's d2 body keeps its original wording; the journal is append-only and this resolution is the correction.)

<!-- fr:journal kind=finding scope=spec id=sr1-f9-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f9 -->
### sr1-f9-resolved · finding [fixed] · resolves sr1-f9: LOW: rule 2 says 'values bump-version.py --check enumerates', but --check does not read uv.lock

version_surfaces() is defined explicitly as the 11 manifest values plus uv.lock workspace-member entries (editable/virtual source); version-sync starts checking them.

<!-- fr:journal kind=finding scope=spec id=sr1-f10-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f10 -->
### sr1-f10-resolved · finding [fixed] · resolves sr1-f10: LOW: release.yml needs issues: write, and the notes source for a tag-only rerun is not defined

release.yml declares contents+issues write; a rerun reads notes from the release commit body; manual dispatch with no fragments uses --generate-notes alone.

<!-- fr:journal kind=finding scope=spec id=sr1-f11-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f11 -->
### sr1-f11-resolved · finding [fixed] · resolves sr1-f11: LOW: the Test Plan misses several promised behaviours, and existing tests pin the aggregates

TP4/TP5 now cover pre-existing tag, invalid fragment, floor-mismatch-tags-then-fails, protection refusal, lost races, stale lock; §3.I adds an aggregates flag and moves test_acceptance_report.py:115,:188 to the ad-hoc render.

<!-- fr:journal kind=finding scope=spec id=sr1-f12-resolved created=2026-09-26T08:12:00 state=fixed resolves=sr1-f12 -->
### sr1-f12-resolved · finding [fixed] · resolves sr1-f12: LOW: AGENTS.md's CI job list names version-bump-required

§3.G renames the job in AGENTS.md's CI job list; captured triage fixtures stay as data.
