# Triage board and labels that tell the truth — plan

Spec: `2026-10-12-board-truth-design.md` (batch `board-truth`: #1085, #1065, #1109, #1111, #1122).

Four agentic phases, one per independently reviewable ask:

1. **Labels** (R1–R3): `fr:in-progress` is removed by the same release that removes `fr:claimed`. Collect reads the closed issues still labelled, `check` and the pages name them, and `fr triage clean-labels` cleans them. This phase is the skeleton and owns the facts schema move to 9, including `config_ignored`, which phase 2 consumes.
2. **Schema skew** (R4, R5): every triage config read is lenient, and ignored keys plus skipped repos become a banner and `check` keys.
3. **Board cards** (R6–R8): the close-out follows the card front, and #1111's cancelled lifecycle gets pinning tests.
4. **Nav** (R9–R12): one page registry, every page's nav lists only present pages and is kept current across renders, plus the skill text and mirrors.

Overnight operator rule: executors run only targeted tests locally and record `tests: ci`. The draft PR (#1151) runs the full suite in CI. Any heavy local run goes through `~/.cache/fr/coord/testslot.sh`. No member issue is a phase `tracking_issue`.
