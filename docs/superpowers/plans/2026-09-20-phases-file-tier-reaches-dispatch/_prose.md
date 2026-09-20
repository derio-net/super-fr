# --phases-file tier ingestion, and the rest of the chain to dispatch

Implements `docs/superpowers/specs/2026-09-20-phases-file-tier-reaches-dispatch-design.md`
(gh#434).

## What is actually broken

`fr plan create --phases-file` drops `phase.tier` at ingestion, one layer
upstream of the `extra="forbid"` on `PhaseHeader` that would have complained.
Verified live at `fr 4.8.0`: a phases file carrying `tier`, `acceptance` and
`skeleton` produced a header with the last two and not the first.

The investigation found this is one of **three** breaks between a planner's
intent and a dispatched subagent's model:

1. `--phases-file` drops `tier` (`plan_cmd.py:160`, `plan_ops.py:103`);
2. nothing instructs a planner to write one — `fr-plan/SKILL.md` never says
   the word, while fr-goal section 3 asserts "fr-plan tags each phase a `tier`";
3. `fr` never resolves the `from_phase` sentinel — `_build_member_brief`
   hands the orchestrator the literal string, and the join to a concrete tier
   is LLM prose.

Phases 1, 5 and 3 close them in that order.

## Phase shape and why

**Phase 1 is the walking skeleton** because it is the smallest slice that
proves the whole delivery path: the real CLI, the real emitter, the real
re-parse, CI green. Its first test is the *derived* one — built from
`PhaseHeader.model_fields` rather than a restated list — so the next field
added to the model is covered without anyone remembering to add a test. The
instance-level `tier` test rides beside it. That ordering is deliberate: the
class-level test is what would have caught this in 3.12.0, and #434 says so.

**Phase 2** gives `tier` the two gates its siblings have or imply. Both are
`severity="warn"`, so neither can turn a gate red — and P2.T2.S3 proves that
against this repo's own plans rather than asserting it, because both warnings
will fire there by design.

**Phase 3** adds `resolved_tier` to the member brief rather than resolving
`from_phase` in place, preserving the documented property that `tier` is a
faithful echo of the manifest's `Step` field. The group brief is untouched: a
group spans every phase, so it has no single tier, and a confidently-wrong
value is worse than an absent one.

**Phase 4** is the only test that spans ingestion → plan → run → brief. Every
link in this chain already had coverage while the chain was broken, which is
precisely the argument for it. It scaffolds through the CLI on purpose — a
test that hand-writes `01.yaml` would pass against the bug.

**Phase 5** makes fr-goal's existing claim true, corrects a matrix row that
read `ci` for a capability broken upstream of its own tests, and bumps.

## A note on the #498 question

The goal that prompted this work asked whether `tier` never reaching a plan
explains most of #498. It does not, and the correction is in the spec's
Background: `tier` **does** reach this repo's plans, by hand-edit — evidenced
by a key order `create()` cannot produce. #498's break was independent and
#504 fixed it. What #434 contributes is that tier arrival is undocumented and
unreliable, and that post-#504 an untiered dispatch is *indistinguishable*
from working tiering, because the agent files now carry correct models.

## Dogfooding note

This plan will itself be scaffolded by the very command that drops `tier`, so
its own phase tiers must be restored by hand — the exact workaround #434
reports. That is recorded in the plan journal as live evidence rather than
quietly worked around.
