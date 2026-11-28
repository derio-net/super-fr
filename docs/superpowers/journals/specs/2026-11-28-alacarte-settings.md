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

<!-- fr:journal kind=finding scope=spec id=s-r1-1 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-1 · finding [open] (reviewer: in scope) · Schema 3's presence rule is stated two ways, and the design's mechanism does not fit where the validator lives

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-2 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-2 · finding [open] (reviewer: in scope) · fr settings init cannot render the new list key, its stealth text misstates git.push/git.pr, and the quiet wording in `_repo_file` is still stale

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-3 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-3 · finding [open] (reviewer: in scope) · Under a requested stealth, run start's pre-isolation disabled check reads the wrong settings

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-4 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-4 · finding [open] (reviewer: in scope) · Keying the adopt exemption on the `--supersede` flag is incoherent with what supersede does

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-5 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-5 · finding [open] (reviewer: in scope) · Forcing git.pr to ask under stealth also gates every stealth configuration-change PR on the tracking repo, contradicting R8

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-6 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-6 · finding [open] (reviewer: in scope) · Forced git.push=ask under stealth trips the push-ask-with-driven-triage rule, which the operator cannot fix

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-7 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-7 · finding [open] (reviewer: in scope) · fr push asks even when there is nothing to push, and the skills call it several times

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-8 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-8 · finding [open] (reviewer: in scope) · The spec does not state that stealth can no longer push or open its PR through fr on a harness whose transcript fr cannot read

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-9 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-9 · finding [open] (reviewer: in scope) · Under stealth, dropping per-phase pushes weakens cross-host resume

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-10 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-10 · finding [open] (reviewer: in scope) · Design shape and Design disagree on the new function and leave out files the Design changes

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-11 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-11 · finding [open] (reviewer: in scope) · The Test Plan does not cover R9, R5's settle-still-runs clause, or the scenario's registration test

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-12 created=2026-11-28T08:30:59+00:00 state=open review_scope=in -->
### s-r1-12 · finding [open] (reviewer: in scope) · R4 says an unknown pr_sections key is refused naming the three, but the closed model's error does not name them

See the spec review (spec-review-r1).

<!-- fr:journal kind=finding scope=spec id=s-r1-13 created=2026-11-28T08:30:59+00:00 state=open review_scope=out -->
### s-r1-13 · finding [open] (reviewer: out of scope) · fr placement move pushes product-side branches to a stealth target without reading git.push

See the spec review (spec-review-r1).

<!-- fr:journal kind=review scope=spec id=spec-review-r1 created=2026-11-28T08:30:59+00:00 -->
### spec-review-r1 · review · independent spec review: 13 findings (12 in scope, 1 out of scope)

fr-spec-reviewer checked the spec against decisions q1-q6, the codebase (file:line for every named file) and itself. In scope s-r1-1..s-r1-12, all fixed in the spec; out of scope s-r1-13 (placement move).

<!-- fr:journal kind=lens scope=spec id=lens-errors-1 created=2026-11-28T08:30:59+00:00 lens=errors step=spec-review -->
### lens-errors-1 · lens · Several new refusals (disabled shape, schema-3 presence, stealth contrary git keys, triage rule under stealth) must be ones the operator can act on

<!-- fr:journal kind=finding scope=spec id=s-r1-1-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-1 -->
### s-r1-1-resolved · finding [fixed] · resolves s-r1-1: Schema 3's presence rule is stated two ways, and the design's mechanism does not fit where the validator lives

One rule: any raw `workflows` or `forge.pr_sections` key needs schema 3, by a mode=before validator in model.py; `_strict_int` and render.py's hint named (R1, Design §A).

<!-- fr:journal kind=finding scope=spec id=s-r1-2-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-2 -->
### s-r1-2-resolved · finding [fixed] · resolves s-r1-2: fr settings init cannot render the new list key, its stealth text misstates git.push/git.pr, and the quiet wording in `_repo_file` is still stale

render.py added (list defaults as YAML lists, stealth git keys at ask, schema hint) and `_repo_file` text corrected (R6, Design §D).

<!-- fr:journal kind=finding scope=spec id=s-r1-3-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-3 -->
### s-r1-3-resolved · finding [fixed] · resolves s-r1-3: Under a requested stealth, run start's pre-isolation disabled check reads the wrong settings

Under stealth the disabled check runs in the workspace beside the manifest re-resolve; test pins it (R2, Design §B).

<!-- fr:journal kind=finding scope=spec id=s-r1-4-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-4 -->
### s-r1-4-resolved · finding [fixed] · resolves s-r1-4: Keying the adopt exemption on the `--supersede` flag is incoherent with what supersede does

Exempt only when superseding an existing run onto its own shape; plain adopt, --supersede with no run, and migrate's adopt are checked (R2, Design §B).

<!-- fr:journal kind=finding scope=spec id=s-r1-5-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-5 -->
### s-r1-5-resolved · finding [fixed] · resolves s-r1-5: Forcing git.pr to ask under stealth also gates every stealth configuration-change PR on the tracking repo, contradicting R8

Configuration PRs follow the tracking file's own git.pr (`config_pr`), read by config/change.py's pr_policy; stated in R8 and tested.

<!-- fr:journal kind=finding scope=spec id=s-r1-6-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-6 -->
### s-r1-6-resolved · finding [fixed] · resolves s-r1-6: Forced git.push=ask under stealth trips the push-ask-with-driven-triage rule, which the operator cannot fix

Under stealth the rule names the driven triage keys as the only fix (R7, Design §E), tested.

<!-- fr:journal kind=finding scope=spec id=s-r1-7-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-7 -->
### s-r1-7-resolved · finding [fixed] · resolves s-r1-7: fr push asks even when there is nothing to push, and the skills call it several times

New R9: under stealth fr push with no code pending pushes and asks nothing; each code push, settle fixes included, asks its own approval.

<!-- fr:journal kind=finding scope=spec id=s-r1-8-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-8 -->
### s-r1-8-resolved · finding [fixed] · resolves s-r1-8: The spec does not state that stealth can no longer push or open its PR through fr on a harness whose transcript fr cannot read

R10 and Design §E state the limit and that deliver's ask gate now holds every stealth run; the skills and docs say it.

<!-- fr:journal kind=finding scope=spec id=s-r1-9-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-9 -->
### s-r1-9-resolved · finding [fixed] · resolves s-r1-9: Under stealth, dropping per-phase pushes weakens cross-host resume

R10 states the trade-off; the fr-goal resume sentence gains its limit.

<!-- fr:journal kind=finding scope=spec id=s-r1-10-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-10 -->
### s-r1-10-resolved · finding [fixed] · resolves s-r1-10: Design shape and Design disagree on the new function and leave out files the Design changes

One name, refuse_disabled; shape adds resolve.py, workflow_cmd.py, render.py, config/change.py, push_cmd.py, mirrors and the scenario test.

<!-- fr:journal kind=finding scope=spec id=s-r1-11-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-11 -->
### s-r1-11-resolved · finding [fixed] · resolves s-r1-11: The Test Plan does not cover R9, R5's settle-still-runs clause, or the scenario's registration test

Test Plan adds the skill-prose test (R10), settle-off-still-checks (R5), the no-op push test (R9) and the test_scenarios.py test.

<!-- fr:journal kind=finding scope=spec id=s-r1-12-resolved created=2026-11-28T08:30:59+00:00 state=fixed resolves=s-r1-12 -->
### s-r1-12-resolved · finding [fixed] · resolves s-r1-12: R4 says an unknown pr_sections key is refused naming the three, but the closed model's error does not name them

PrSections gets a mode=before validator naming the three (Design §A).

<!-- fr:journal kind=finding scope=spec id=s-r1-13-resolved created=2026-11-28T08:30:59+00:00 state=open resolves=s-r1-13 out_of_scope=true -->
### s-r1-13-resolved · finding [out-of-scope] · resolves s-r1-13: fr placement move pushes product-side branches to a stealth target without reading git.push

Pre-existing and operator-typed: `fr placement move` is not a stealth run's push, and D7 as decided (q5) covers `fr push` and `fr pr create`. Recorded in the spec's Out of scope.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-28T08:31:01+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  s2-pr-sections: developer
  s2-stealth-confirm: developer
  s2-workflows-disabled: developer
row_kinds:
  s2-pr-sections: candidate
  s2-stealth-confirm: candidate
  s2-workflows-disabled: candidate
run_gate: developer
run_kind: candidate
```

<!-- fr:journal kind=finding scope=spec id=s-r1-13-resolved-2 created=2026-11-28T11:14:43+00:00 state=open resolves=s-r1-13 tracked_by=https://github.com/derio-net/super-fr/issues/1770 -->
### s-r1-13-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1770] · resolves s-r1-13: fr placement move pushes product-side branches to a stealth target without reading git.push

Filed at deliver as https://github.com/derio-net/super-fr/issues/1770.
