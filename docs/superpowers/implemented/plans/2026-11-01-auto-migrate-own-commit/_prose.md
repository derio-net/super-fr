# Auto-migrate stale artifacts in their own commit — plan

Spec: `docs/superpowers/specs/2026-11-01-auto-migrate-own-commit-design.md` (super-fr#1242).

One agentic phase. The asks (a workspace commits the migration alone, CI migrates in place,
everything else still refuses, the nag relays it, the rule says so) are all one change to the
CLI-entry gate's context decision, and they review as a unit. Splitting them would review the
classification without its consumers. Tier `hard`: this is the migration gate every fr command
passes through.

Order inside the phase: shared marker validator → classification and test seam → workspace path
→ CI path → nag hooks → scenarios and matrix → rule, mirrors, fragment, then the full suite last.
Heavy suites run only through `~/.cache/fr/coord/testslot.sh`.
