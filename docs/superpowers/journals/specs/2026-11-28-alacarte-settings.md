<!-- fr:journal-schema=4 -->
# Journal: 2026-11-28-alacarte-settings

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-28T08:21:58+00:00 input=true -->
### operator-brief · discovery · Batch s2-alacarte-settings: issue #1654 as dispatched

Batch `s2-alacarte-settings` of derio-net/super-fr, one issue, one PR.

#1654 — S2: à la carte .fr/settings.yaml — available workflows, PR-body sections, modes, stealth code-push confirmation.

Part of the event-driven, à la carte epic (#1652). Depends on: S1.

Composable `.fr/settings.yaml`:
- which workflows are available in the repo;
- which PR-body sections are required (today `fr.record.pr_body.REQUIRED_SECTIONS` is fixed — e.g. a repo may drop Proportionality or Cost);
- mode choices, including stealth settings read from its own file in the tracking space;
- stealth: code reaches the target (`fr push`, `fr pr create`) only after explicit operator confirmation, regardless of `git.push`; state keeps being pushed to the tracking repo on every write. fr-goal's push at `deliver` open becomes a confirmation gate under stealth.

Delivery rules from the dispatch: branch feat/batch-s2-alacarte-settings; draft PR once the spec is committed with `Closes derio-net/super-fr#1654`; `fr run start --issue 1654`; no member issue as a phase tracking_issue; the wave driver owns mergeability and CI (no `fr pr settle` loop); never add `approved-fr`.

<!-- fr:journal kind=decision scope=spec id=q1-workflows-denylist created=2026-11-28T08:21:58+00:00 decided_by=operator -->
### q1-workflows-denylist · decision · Available workflows are a denylist: workflows.disabled

Operator chose a denylist (`workflows.disabled: [...]`) over the recommended allowlist and an on/off map. Everything not listed stays available; runs already started keep going (spec R1-R3).

<!-- fr:journal kind=decision scope=spec id=q2-sections-informational created=2026-11-28T08:21:58+00:00 decided_by=operator -->
### q2-sections-informational · decision · Only informational PR-body sections are configurable

Operator chose: Proportionality, Cost and PR settle may be turned off; Findings, Out-of-scope, Shape, Pre/Post-merge owed, Manual operations and Owed actions discharged stay fixed (spec R4).

<!-- fr:journal kind=decision scope=spec id=q3-off-not-rendered created=2026-11-28T08:21:58+00:00 decided_by=operator -->
### q3-off-not-rendered · decision · An off section is rendered nowhere

Operator chose: dropped from the live PR body and the durable pr-body.md; figures stay reachable through their own commands (spec R5).

<!-- fr:journal kind=decision scope=spec id=q4-modes-fix-document created=2026-11-28T08:21:58+00:00 decided_by=operator -->
### q4-modes-fix-document · decision · Modes: nothing new; fix the placement text and document

Operator chose: S1's stealth settings read is the delivered half; S2 corrects the `placement` key's stale description and documents where each mode's settings live. No allowed-placements key, no retirement of the key (spec R6).

<!-- fr:journal kind=decision scope=spec id=q5-stealth-every-push-asks created=2026-11-28T08:21:58+00:00 decided_by=operator -->
### q5-stealth-every-push-asks · decision · D7: every stealth push and PR creation asks

Operator chose: under stealth `fr push` and `fr pr create` always take the `ask` path, one verified approval each; fr-goal under stealth skips per-phase pushes, its one code push is the deliver-open gate (spec R7-R9).

<!-- fr:journal kind=decision scope=spec id=q6-verify-candidate-developer created=2026-11-28T08:21:58+00:00 decided_by=operator -->
### q6-verify-candidate-developer · decision · Verification: candidate, gate developer

Operator chose the candidate strategy with a scenario walk and gate developer; nothing is held after merge.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-28T08:21:58+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · D7 is a control on code leaving for a stealth target without the operator's confirmation
