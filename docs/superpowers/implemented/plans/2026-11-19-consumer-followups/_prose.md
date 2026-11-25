# Consumer-delivery follow-ups — implementation plan

Spec: `docs/superpowers/specs/2026-11-19-consumer-followups-design.md` (R1–R7).

One agentic phase covers the three asks. Each is small, and together they make a diff one
reviewer can read at once. Splitting them would cost two more executor/reviewer round
trips and buy nothing. The phase is tiered `hard` because R1–R4 change what the OpenCode
isolation gates judge, and every tool call of every OpenCode session goes through them.

Order inside the phase:

1. The change fragment (`patch`).
2. The session-directory resolver (R4): bounded, caches only a success, never throws.
3. Wiring it into the shell gate, the edit gate (relative targets and the
   unresolvable-patch probe) and the sentinel (R1–R3), with tests in which the session
   directory differs from the plugin directory.
4. The Gitea matrix checkout (R5) and both goldens.
5. The tea predicate and the six re-raising sites (R6).
6. The DevOps gate's refusal and the isolation refusal pin (R7).
7. Docs currency, the acceptance rows moved to `ci`, and the full suite last.

There are no manual steps. The verification strategy is `candidate`, and every row has
`verify: none` (CI and bun tests). There is no Test Plan.
