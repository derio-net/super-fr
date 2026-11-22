# Local suite cost — plan

Spec: `docs/superpowers/specs/2026-11-19-local-suite-cost-design.md` (issue #1555).

Four phases, ordered so each one's savings are measurable by the next:

1. **Git answer cache (skeleton).** The single biggest cost in CLI-driven tests is fr
   asking git for the default remote and branch about 7 times per invocation. A
   context-scoped cache with a stat fingerprint removes about 400 of 926 git starts in
   the profiled test, and speeds up every operator's `fr` too. It is `hard`: it is a
   correctness cache on a path that every merge, archive and dispatch check relies on.
2. **Test diet.** Profile the twelve slowest files, then give the started-run and
   workspace fixtures sandboxed copyable templates. Apply one remedy per file, each
   with before and after numbers in the plan journal. Merge a case only when its
   claim survives in another test.
3. **Tiers and the gate.** The `scenario` marker comes out of the default local run
   but stays in every CI and release command (pinned by parsing them). The
   `--fr-scope` fast tier is added with the advisory line, and fr refuses an advisory
   log. `.fr/ci.yaml`'s `tests: ci` default reaches the briefs, the phase executor and
   fr-goal. Then `.test_durations` is refreshed and AGENTS.md updated. It is `hard`:
   it changes what `deliver` accepts.
4. **[manual] Required `ci-ok`.** The operator adds the bypass actor, waits for a
   release pushed by the app, then sets the required check.

**This run's own evidence.** Until phase 3 lands, the phases use the existing `tests:
ci` mode: push, then cite CI green. They do not run the multi-hour local suite this
plan removes. So the draft PR opens when `implement` starts.
