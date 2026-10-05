# Journal: 2026-10-05-opencode-tier-question

<!-- fr:journal kind=repro scope=debug id=b780615415f0 created=2026-10-05T20:38:18+00:00 -->
### b780615415f0 · repro · fr-goal brainstorm brief carries no tier bindings; tier question depends on recall

Re-verified on 5.5.0 (gh#538 §1). `plugins/super-fr/skills/fr-goal/SKILL.md` §1 still reads 'a model-per-tier one if `fr models resolve` is unbound', and `fr run advance`'s brief (`run_cmd._build_brief`) has no key naming tier bindings — the only way the question fires is the model remembering to run `fr models resolve` per tier, which the observed OpenCode run never did.
