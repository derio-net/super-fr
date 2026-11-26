# Landing method — implementation plan

Spec: `docs/superpowers/specs/2026-11-26-landing-method-design.md` (super-fr#1705, #1702, #1603).

One agentic phase: the four asks (method order, the push landing rule, the rebase warning and
doctor check, release.py's closed-unmerged landing) share one decision point, `choose_method`,
and one review is cheaper than four round trips.

Order inside the phase: the method's source first (T1), because the landing refusal (T2) and the
doctor check (T3) name it; release.py (T4) is independent; config, docs and the fragment (T5)
close the phase. Every behavioural step is red → green; T1 and T2 end with a refactor/cleanup step.

The operator hand-merges this PR as a merge commit; the driver is stopped, so nothing in this plan
waits on the queue.
