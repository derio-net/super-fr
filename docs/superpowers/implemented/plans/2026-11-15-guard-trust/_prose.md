# Guard-trust batch — implementation plan

Spec: `docs/superpowers/specs/2026-11-15-guard-trust-design.md` (R1–R8). Five issues, one PR,
three agentic phases, one per independently reviewable ask:

1. **Durable opt-in (#1277, R1–R2).** The skeleton: the smoke run first, then the archive's
   `.gitkeep` and the gates' `implemented/plans` test on both harness libraries, then the rule and
   doc text and the change fragment.
2. **Absolute-path binaries (#1429, R3–R4).** The two git resolvers, then every bash hook that
   starts `fr`, then the OpenCode modules. Bare `git` inside hook scripts is a non-goal.
3. **Pin, probes, comment (#1259, #1230, #1279, R5–R8).** Append-only sibling pins, the reworded
   warning, `-P` on both lock probes, and the nag comment.

Every test that proves a planted binary or module is not run plants it and checks a marker
file is never written. The security, tests and errors lenses review the whole diff before
deliver. No member issue is a phase `tracking_issue`.
