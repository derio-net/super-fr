<!-- fr:journal-schema=4 -->
# Journal: 2026-11-28-s1-followups

<!-- fr:journal kind=discovery scope=spec id=brief created=2026-11-28T08:09:38+00:00 input=true -->
### brief · discovery · Batch s1-followups: 4 issues (#1698 #1699 #1700 #1701), one PR

/fr-goal batch s1-followups — batch `s1-followups` of derio-net/super-fr, delivered as ONE pull request.
Batch title: S1 follow-ups: refuse old paths, config-branch executables, test sites, import-time home.
- super-fr#1698 Owed: Refuse the old configuration paths and drop the legacy settings copy (journal spec/2026-11-19-event-driven-a-la-carte entry s1-refuse-old-paths).
- super-fr#1699 workflow kind:cli run: and verification argv become configuration-branch executables once phase 5 moves them into .fr/ (journal plan/2026-11-24-s1-configuration-homes/p3-r6).
- super-fr#1700 about 20 test sites still set the old FR_SHIPPED_*_DIR variables (p5-r4).
- super-fr#1701 fr.repos.DEFAULT_MANIFEST takes Path.home() at import (l-tests-r6).
Delivery: branch feat/batch-s1-followups; draft PR as soon as the spec is committed, with one `Closes derio-net/super-fr#<n>` line per member; no member as a phase tracking_issue; the wave driver owns mergeability and CI (no `fr pr settle` loop); never add `approved-fr`.

<!-- fr:journal kind=decision scope=spec id=q1-version-gated created=2026-11-28T08:09:38+00:00 decided_by=operator -->
### q1-version-gated · decision · #1698's refusal is version-gated at fr >= 9.2 in the code

Operator (round 1, q1): version-gated at fr >= 9.2.0, the journal's plan, so the PR may merge before or after 9.1.0's final. S1 ships in 9.1.0 (its minor fragment is pending, only RCs cut). Recommended option was unconditional + merge after 9.1.0; the operator chose the gate. Spec R1, R7, R8.

<!-- fr:journal kind=decision scope=spec id=q2-settings-sync-removed created=2026-11-28T08:09:38+00:00 decided_by=operator -->
### q2-settings-sync-removed · decision · fr settings sync is removed once the transition ends

Operator (round 1, q2): remove it. With q1's version gate the command's code stays until the gate: past it, the command is hidden and exits 2 (spec R5); deleting the dormant code is owed after 9.2 ships (R16). The old copy on `fr` is left untouched.

<!-- fr:journal kind=decision scope=spec id=q3-shell-readers created=2026-11-28T08:09:38+00:00 decided_by=operator -->
### q3-shell-readers · decision · All shell readers drop their old-path fallbacks in this PR

Operator (round 1, q3): yes, all harnesses — the Claude Code and Hermes hooks (fr-isolation-decision.sh), the OpenCode plugin and validate-plans.sh, gated by their own release version (spec R7).

<!-- fr:journal kind=decision scope=spec id=q4-argv-residue created=2026-11-28T08:09:38+00:00 decided_by=operator -->
### q4-argv-residue · decision · #1699: pin S1's whole-manifest guard and close the .fr/ file residue

Operator (round 1, q4): pin + close. Walk argv elements under .fr/ run from the exported checked tip; a kind:cli run: naming .fr/ under quiet/stealth is refused (spec R10-R12).

<!-- fr:journal kind=decision scope=spec id=q5-verification created=2026-11-28T08:09:38+00:00 decided_by=operator -->
### q5-verification · decision · Verification: candidate walk, gate developer

Operator (round 1, q5): candidate strategy, the scenario forcing the gate on (FR_OLD_PATHS=refuse); gate developer; no post-merge Test Plan rows (spec ## Verification).

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-28T08:09:38+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · #1699 closes a trust-boundary gap: configuration argv and .fr/ files must run only from the protected tip

<!-- fr:journal kind=finding scope=spec id=sr-1 created=2026-11-28T08:19:42+00:00 state=open review_scope=in -->
### sr-1 · finding [open] (reviewer: in scope) · R7's version files are absent where two of the shell readers actually run, so 'unreadable -> ended' ends the transition on day one

scripts/deliver-opencode-plugin.sh:138-140 copies only .ts files (no package.json); fr hermes install copies the hook tree to ~/.hermes/super-fr-hooks/ (hermes.py:360), away from plugin.json; fr validate plans runs the wheel copy of validate-plans.sh with no plugin.json beside it. Fix: a version source beside every delivered copy, a test per location.

<!-- fr:journal kind=finding scope=spec id=sr-2 created=2026-11-28T08:19:42+00:00 state=open review_scope=in -->
### sr-2 · finding [open] (reviewer: in scope) · Once ended, the edit gate stops seeing an unmigrated quiet repo as fr-enabled (fails open)

_fr_placement_enabled (fr-isolation-decision.sh:443-468) decides fr-enabled from _fr_read_switch; reading only FR_SWITCH_NEW drops an old-only quiet repo, and _fr_paths_enabled's fr would refuse. Same in marker.ts:211-241. Fix: an old-only switch stays fr-enabled (gated), never quiet, never a write target.

<!-- fr:journal kind=finding scope=spec id=sr-3 created=2026-11-28T08:19:42+00:00 state=open review_scope=in -->
### sr-3 · finding [open] (reviewer: in scope) · Hiding `fr settings sync` by version breaks the generated CLI tree in the 9.2.0 release's own suite

scripts/sync-readme.py:180 omits hidden commands and docs/reference/cli.md:236 lists fr settings sync; at prepare's 9.2.0 suite test_tripwire_readme_sync.py would see drift. Fix: keep it listed with a gate-independent help line; test the tree with the version forced into 9.2.

<!-- fr:journal kind=finding scope=spec id=sr-4 created=2026-11-28T08:19:42+00:00 state=open review_scope=in -->
### sr-4 · finding [open] (reviewer: in scope) · §B gates the wrong functions: the old-switch readers are `quiet._read` and `settings.load._stealth`, and the text readers are shared with the migration

quiet._read (quiet.py:191-217) and fr.settings.load._stealth (load.py:324-375) are the fallback readers; switch_texts/target_settings_texts are read by fr.config.migrate (migrate.py:363,433-435) and must stay ungated for R3; settings/load.py was missing from the shape.

<!-- fr:journal kind=finding scope=spec id=sr-5 created=2026-11-28T08:19:42+00:00 state=open review_scope=in -->
### sr-5 · finding [open] (reviewer: in scope) · The write functions are `write_switch`/`write_target_settings`, not `write_settings`; the stealth line cited is the call site

fr.config.space.write_settings (space.py:273-303) dispatches to quiet.write_switch (:1251, write_legacy at :1304) and stealth.write_target_settings (:862, write_legacy_target at :906, def :1006). Docstrings/stderr at quiet.py:1291-1295, stealth.py:899-904 promise the old copy follows.

<!-- fr:journal kind=finding scope=spec id=sr-6 created=2026-11-28T08:19:42+00:00 state=open review_scope=in -->
### sr-6 · finding [open] (reviewer: in scope) · `fr settings init` and other messages still offer the half-written old-copy refusal and `fr settings sync` once the transition has ended

settings_cmd.py:145-149,216-229,254-266,441-447, quiet.py:274-290,420-436 and config_migration.py:216-219 fire on an absent old copy or name fr settings sync. R4 must cover the absent/half-written refusals and every SYNC_COMMAND message, and say _create_from_old_switch stays a mover.

<!-- fr:journal kind=finding scope=spec id=sr-7 created=2026-11-28T08:19:42+00:00 state=open review_scope=in -->
### sr-7 · finding [open] (reviewer: in scope) · R2's refusal in `located` also reaches `fr repos sync` and `fr repair`, which move or rewrite the old plan-config themselves

repos_cmd.py:65-97 (located at :83, writes new and unlinks old at :93-96) and repair.py:337 are movers; §B exempted only fr.config.migrate. Fix: say they keep reading the old path, and test it.

<!-- fr:journal kind=finding scope=spec id=sr-8 created=2026-11-28T08:19:42+00:00 state=open review_scope=in -->
### sr-8 · finding [open] (reviewer: in scope) · R9 has no way for subprocess, shell and TypeScript tests to force the not-ended side, so they still go red at 9.2

Shell-library cases (test_isolation_decision_cases.py), validate-plans tests, bun tests and CLI subprocess tests can only force the ended side. Fix: a defined mechanism per test kind (fixture version source; ended side forced; open side run only below 9.2).

<!-- fr:journal kind=finding scope=spec id=sr-9 created=2026-11-28T08:19:42+00:00 state=open review_scope=in -->
### sr-9 · finding [open] (reviewer: in scope) · R13's tripwire allowlist (one file) contradicts config-homes.sh, test_lenses_resolve.py and the lens resolver's own message

config-homes.sh:42,116-119 sets and unsets the variables; test_lenses_resolve.py:46,71 sets FR_SHIPPED_LENSES_DIR and asserts the lens message (lenses/resolve.py:46) offers it. Fix: define 'sets', list every allowed file, gate the lens message.

<!-- fr:journal kind=finding scope=spec id=sr-10 created=2026-11-28T08:19:42+00:00 state=open review_scope=in -->
### sr-10 · finding [open] (reviewer: in scope) · R10/R11's `.fr/` detection misses absolute and embedded forms; R11 overclaims what `shlex` proves

in_space (space.py:84-86) is a prefix test, so {repo}/.fr/x and --config=.fr/x escape; shlex.split tokens for a;.fr/x, <.fr/x, --opt=.fr/x neither are nor start with .fr/. Fix: fail closed on any .fr/ path segment in the rendered string or element.

<!-- fr:journal kind=finding scope=spec id=sr-11 created=2026-11-28T08:19:42+00:00 state=open review_scope=in -->
### sr-11 · finding [open] (reviewer: in scope) · R6 does not name the exception, and 'callers already surface resolver errors as exit 2' is unverified

_shipped (_shipped.py:128-153,170) has no error type; workflow/resolve.py:96, verification/resolve.py:47, lenses/resolve.py:30 catch their own errors. Fix: raise and map to each kind's own error, test exit 2 through one CLI per kind.

<!-- fr:journal kind=finding scope=spec id=sr-12 created=2026-11-28T08:19:42+00:00 state=open review_scope=out -->
### sr-12 · finding [open] (reviewer: out of scope) · R1 says nothing else compares a version, while R7/R8 add three more comparisons

Wording only: R1's last clause read as global while R7/R8 add shell and TypeScript comparisons.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-28T08:19:42+00:00 -->
### spec-review-1 · review · independent spec review: 12 findings (sr-1..sr-12; 11 in scope, 1 out)

findings: sr-1..sr-12. Decisions q1-q5 reflected in R1-R16. All named files/helpers verified with file:line by the reviewer.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-28T08:19:42+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · R10's promise that no test turns red at 9.2 needs a check of every transition test's gate side, shell, TypeScript and the release suite included

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-28T08:19:42+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · New exit-2 refusals across readers that catch different exception types

<!-- fr:journal kind=finding scope=spec id=sr-1-resolved created=2026-11-28T08:19:42+00:00 state=fixed resolves=sr-1 -->
### sr-1-resolved · finding [fixed] · resolves sr-1: R7's version files are absent where two of the shell readers actually run, so 'unreadable -> ended' ends the transition on day one

R7/§C: version sources beside each delivered copy — plugin.json (Claude Code), a VERSION file written by fr hermes install and by deliver-opencode-plugin.sh, and FR_OLD_PATHS_ENDED from fr settings paths --shell for validate-plans.sh; a test per delivered location.

<!-- fr:journal kind=finding scope=spec id=sr-2-resolved created=2026-11-28T08:19:42+00:00 state=fixed resolves=sr-2 -->
### sr-2-resolved · finding [fixed] · resolves sr-2: Once ended, the edit gate stops seeing an unmigrated quiet repo as fr-enabled (fails open)

New R8 and §C: once ended, an old-only quiet switch keeps the repo fr-enabled (gated), never quiet placement, never a write target; same in marker.ts.

<!-- fr:journal kind=finding scope=spec id=sr-3-resolved created=2026-11-28T08:19:42+00:00 state=fixed resolves=sr-3 -->
### sr-3-resolved · finding [fixed] · resolves sr-3: Hiding `fr settings sync` by version breaks the generated CLI tree in the 9.2.0 release's own suite

R5: sync stays listed with a gate-independent help line; R10 adds a test rendering the CLI tree with the version forced into 9.2.

<!-- fr:journal kind=finding scope=spec id=sr-4-resolved created=2026-11-28T08:19:42+00:00 state=fixed resolves=sr-4 -->
### sr-4-resolved · finding [fixed] · resolves sr-4: §B gates the wrong functions: the old-switch readers are `quiet._read` and `settings.load._stealth`, and the text readers are shared with the migration

Background and §B name quiet._read and fr.settings.load._stealth as the gated readers; switch_texts/target_settings_texts/_read_legacy stay ungated for the movers; settings/load.py added to the shape.

<!-- fr:journal kind=finding scope=spec id=sr-5-resolved created=2026-11-28T08:19:42+00:00 state=fixed resolves=sr-5 -->
### sr-5-resolved · finding [fixed] · resolves sr-5: The write functions are `write_switch`/`write_target_settings`, not `write_settings`; the stealth line cited is the call site

§B names quiet.write_switch and stealth.write_target_settings; Background cites call and definition lines; R4 covers the docstrings and stderr text.

<!-- fr:journal kind=finding scope=spec id=sr-6-resolved created=2026-11-28T08:19:42+00:00 state=fixed resolves=sr-6 -->
### sr-6-resolved · finding [fixed] · resolves sr-6: `fr settings init` and other messages still offer the half-written old-copy refusal and `fr settings sync` once the transition has ended

R4 covers the differing, lagging, absent and half-written refusals and every message naming fr settings sync (config_migration.py included); R3 keeps _create_from_old_switch a mover.

<!-- fr:journal kind=finding scope=spec id=sr-7-resolved created=2026-11-28T08:19:42+00:00 state=fixed resolves=sr-7 -->
### sr-7-resolved · finding [fixed] · resolves sr-7: R2's refusal in `located` also reaches `fr repos sync` and `fr repair`, which move or rewrite the old plan-config themselves

R3 lists fr repos sync and fr repair as movers; §B gives them fr.config.space.old_path(), which never refuses.

<!-- fr:journal kind=finding scope=spec id=sr-8-resolved created=2026-11-28T08:19:42+00:00 state=fixed resolves=sr-8 -->
### sr-8-resolved · finding [fixed] · resolves sr-8: R9 has no way for subprocess, shell and TypeScript tests to force the not-ended side, so they still go red at 9.2

R10 defines how each test kind picks its side: monkeypatch in process, a fixture version source for shell/TS, FR_OLD_PATHS=refuse for subprocess/scenarios with the open side run only below 9.2.

<!-- fr:journal kind=finding scope=spec id=sr-9-resolved created=2026-11-28T08:19:42+00:00 state=fixed resolves=sr-9 -->
### sr-9-resolved · finding [fixed] · resolves sr-9: R13's tripwire allowlist (one file) contradicts config-homes.sh, test_lenses_resolve.py and the lens resolver's own message

R14 defines 'sets' (assignment, export, setenv, env-mapping key; unset/delenv allowed), lists the three allowed files; R6 makes no message offer a per-kind variable, so the lens message and its test change.

<!-- fr:journal kind=finding scope=spec id=sr-10-resolved created=2026-11-28T08:19:42+00:00 state=fixed resolves=sr-10 -->
### sr-10-resolved · finding [fixed] · resolves sr-10: R10/R11's `.fr/` detection misses absolute and embedded forms; R11 overclaims what `shlex` proves

R11/R12 and §D: a .fr/ path segment anywhere in the rendered string or element; absolute paths under the repo or worktree root are resolved; other embedded forms refuse; no shell parsing claimed.

<!-- fr:journal kind=finding scope=spec id=sr-11-resolved created=2026-11-28T08:19:42+00:00 state=fixed resolves=sr-11 -->
### sr-11-resolved · finding [fixed] · resolves sr-11: R6 does not name the exception, and 'callers already surface resolver errors as exit 2' is unverified

R6/§B: LegacyEnvRefused (a TransitionError) mapped by each resolver to its own error type; exit 2 tested through one CLI per kind.

<!-- fr:journal kind=finding scope=spec id=sr-12-resolved created=2026-11-28T08:19:42+00:00 state=open resolves=sr-12 out_of_scope=true -->
### sr-12-resolved · finding [out-of-scope] · resolves sr-12: R1 says nothing else compares a version, while R7/R8 add three more comparisons

Tagged out of scope by the reviewer (wording). R1's last clause was rewritten as part of sr-1's fix, which scopes it to Python and points at R7.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-28T08:19:44+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  repos-manifest-home-at-call: none
  s1-config-argv-from-tip: developer
  s1-old-paths-refused: developer
  s1-old-settings-copy-retired: developer
  s1-shell-readers-refuse: developer
row_kinds:
  repos-manifest-home-at-call: none
  s1-config-argv-from-tip: candidate
  s1-old-paths-refused: candidate
  s1-old-settings-copy-retired: candidate
  s1-shell-readers-refuse: candidate
run_gate: developer
run_kind: candidate
```

<!-- fr:journal kind=decision scope=spec id=tier-2026-11-28-s1-followups-p1 created=2026-11-28T08:22:14+00:00 -->
### tier-2026-11-28-s1-followups-p1 · decision · hard: phase 1 changes the configuration readers, the settings writers and the movers every fr command relies on, behind a version gate that must hold on both sides
