# Drive quota pacing — plan

Spec: `docs/superpowers/specs/2026-10-12-quota-pacing-design.md` (super-fr#1136, batch `quota-pacing`).

Three agentic phases, one per independently reviewable ask:

1. **Pacing core** (skeleton): the pure `fr/triage/quota.py` decisions, `pacing.json`, the
   `quota_floor` host setting, `rate_limit()` on the forge seam, and the loop changes that make a
   rate-limited drive wait for the reset (host loop and cloud pass) without letting its lease lapse.
   This answers #1136 ask 1 and the floor's configuration.
2. **Probes, partial collect and the essential-only pass**: the conditional REST probes and their
   ETag ordering, `collect_facts_counted(only=, previous=)` with cross-repo link carry, and the
   quiet / partial / essential pass kinds in `run_pass`. This answers asks 2 and 3. It is `hard`
   because it changes `collect_facts_counted`, which `fr triage collect`, the drive and the watch
   all rely on, and because the ETag/facts ordering is the correctness core of the quiet pass.
3. **Conditional visibility, watch pacing and the footer**: R12, R17 and R14, the last of ask 3 and
   ask 5.

Tests: targeted runs locally (`uv run pytest <files> -q --no-cov`). The full suite runs on CI
(`tests: ci`), per the operator's overnight rule; any local heavy run goes through
`bash ~/.cache/fr/coord/testslot.sh -- <command>`.

Item 4 of #1136 is super-fr#1152 and is not part of this plan.
