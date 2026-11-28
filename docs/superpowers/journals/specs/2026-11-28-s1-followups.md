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
