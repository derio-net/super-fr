# Phase sizing — implementation plan

Spec: `docs/superpowers/specs/2026-09-28-phase-sizing-design.md` (super-fr#745,
super-fr#760).

## Shape

This plan is dogfooded under its own rule. It serves **one independently
reviewable ask**: make fr-plan size phases to the asks, with the checks that
enforce it and the prose that teaches it. So it has **one agentic phase**:

- no walking-skeleton marker (a one-phase plan is first-class);
- no `phase-split-*` decisions;
- no `[manual]` phase. The post-merge check that the next real fr-goal run
  writes one phase per ask is a Test Plan line, and the before/after audit is
  the follow-up issue #793.

The tier is `hard`. The rule table in spec §B has several subtle interactions
(the waived-phase exclusion in `own`, and which tokens may clear which error),
and the proportionality section must stay a pure function of HEAD.

## Order inside the phase

1. `fr/phase_sizing.py`: pure logic, tested alone.
2. `_phase_sizing_issues` in `plan_ops.py`: the self-review gate and the
   single-step trailing-manual warning.
3. The proportionality `## Phases` section, read from HEAD only.
4. Skill prose and both mirror generators.
5. The explainer, the change fragment, and the acceptance rows moved to `ci`.
6. Full verification.

## Notes for the executor

- Do not name super-fr#745 or #760 as a `tracking_issue` (batch delivery rule).
- `fr plan create` writes a constant `fr_version`, so the gate's cut-off is the
  spec's parseable `## Requirements` table, never a version probe (spec §B).
- `fr-goal/SKILL.md` is also edited by batch `closeout-always`. Keep the §3 edit
  small, so a rebase conflict stays small.
