# Owed trackers and archive side effects — plan

Spec: `docs/superpowers/specs/2026-11-15-owed-archive-side-effects-design.md`.

Three agentic phases, one per independently reviewable ask:

1. **Skeleton — owed dedupe and refusals (R7–R9, R12–R14).** The shared default-branch
   helper moves into `fr.git` first, because phases 2 and 3 use it. Then owed issues are
   found by label and fail closed (#1184), closing reads one issue, and a refused archive
   writes nothing (#1183).
2. **Close at merge (R1–R6, #1400).** Resolve stops closing off the default branch, the
   PR body lists discharged owed issues, and `deliver` checks the live body for them.
   Tier `hard`: it changes `deliver`'s premature-close gate, which every run passes.
3. **`fr archive --dry-run` (R10, R11, #1301).** A preview forge, a scratch-checkout
   runner, the flag in every mode, and the quiet/stealth read-only path.

Phases 2 and 3 depend only on phase 1 and touch different code.

Every phase names its negative evidence: a forge double that raises or records, and
byte-identical `git status` and `git diff --cached` before and after.
