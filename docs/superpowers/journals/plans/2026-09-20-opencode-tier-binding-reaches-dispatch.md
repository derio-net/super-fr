# Journal: 2026-09-20-opencode-tier-binding-reaches-dispatch

<!-- fr:journal kind=discovery scope=plan id=x-plan1 created=2026-09-20T08:55:16 -->
### x-plan1 · discovery · Plan-authoring notes: two self-review hits, and fr plan create dropped tier again

1. `fr plan create` dropped `tier:` from all three agentic phase headers again — issue #434, now observed a second time in super-fr itself (the first was the gh#494 plan last night). Re-added directly to 01-03.yaml; self-review passes after.

2. The agentic-purity gate flagged P1.T1.S1 on `\bby hand\b`. FALSE POSITIVE in substance: the phrase was "never by hand-writing agent content", a clause FORBIDDING a manual operation, not instructing one. Reworded to "never from agent content written inline in the test" — the gate cannot distinguish a prohibition from an instruction, and rewording is cheaper than arguing with it. Worth knowing when authoring: negated manual-operation phrases trip it.

3. Renumbering steps inside an existing phase file requires rebuilding `state.steps` too — the parser enforces that the state keys match the task step ids exactly (`missing=[P3.T4.S1] extra=[P3.T2.S2]`). Splitting P3.T2 into single-step tasks to satisfy the refactor-step rule therefore meant editing both halves of the file. The error message names both sides, which made it a 30-second fix rather than a hunt — worth noting as a case where fr fails usefully.

<!-- fr:journal kind=discovery scope=plan id=p1-smoke1 created=2026-09-20T09:00:42 phase=1 -->
### p1-smoke1 · discovery · Skeleton smoke: opencode agent list cannot show resolved model; file content asserted instead (phase 1)

Ran the materialiser end to end under a sandboxed XDG_CONFIG_HOME + HOME (never
the operator's real ~/.config): seeded config/opencode/agent/ from the
committed .opencode/agent/ mirror (fr-phase-executor{,-hard,-mechanical,-standard}.md),
wrote config/fr/models.yaml binding opencode/{mechanical,standard,hard} to
anthropic/claude-haiku-4-5, anthropic/claude-sonnet-4-5, anthropic/claude-opus-4-1,
then called materialize_agents(config_home, models_cfg=load_models(...)).

`opencode agent list` (v1.18.31) registered all four agents under that
XDG_CONFIG_HOME both before and after materialization, byte-identical output
(diff empty) except this run's own permission tool-output pattern — its output
is only a permission-rules dump per agent, with NO model field at all, so the
binary cannot confirm a resolved model either way. Confirmed instead by reading
the agent files directly: each tier file carries exactly one `model: <bound>`
line immediately after `mode: subagent` (hard -> anthropic/claude-opus-4-1,
mechanical -> anthropic/claude-haiku-4-5, standard -> anthropic/claude-sonnet-4-5),
and the untiered fr-phase-executor.md has no model: line at all.

Stating this plainly rather than implying `agent list` confirmed the binding:
it only confirms agent NAME registration, not model resolution. Anyone adding
a stronger live check later needs a different opencode surface (none found
in 1.18.31's `agent` subcommand family).

<!-- fr:journal kind=finding scope=plan id=r-p1-f3 created=2026-09-20T09:16:06 phase=1 state=fixed -->
### r-p1-f3 · finding [fixed] · The materialiser reported writing a model it had not written — this spec's own defect, one level in (phase 1)

Phase-1 review, and the one that matters. `_rewrite` inserted `model:` only after a line equal to `mode: subagent`. When that anchor was absent — a hand-edited agent file, or a future generator change — it inserted NOTHING, but `changes.append(...)` ran unconditionally, so the function returned `Change(tier=hard, new_model=provider/B)` for a file containing no model line at all. Probed directly: `reported: [(hard, None, provider/B)]` / `file actually contains model:? False`.

A materialiser whose entire purpose is "make the binding real, and say so" was capable of saying so falsely. That is precisely the failure mode gh#498 reports one level out (fr models set reporting a binding that never reached the dispatched agent), reproduced inside the fix for it. Worth naming plainly because it shows the class is not a one-off carelessness — it is what happens by default whenever reporting is separated from the action it describes.

FIXED: `Change` gains `problem: str | None`. `_rewrite` returns None for a shape it cannot write (no closing `---` fence, or a wanted model with no anchor); the caller then reports a Change with `problem` set, `new_model=None`, and writes NOTHING, leaving the file byte-identical. Deliberately not an exception: spec §3.A requires that an operator with one hand-edited agent file can still run `fr models set`. Test: test_a_file_missing_the_anchor_is_reported_as_a_problem_not_a_change.

<!-- fr:journal kind=finding scope=plan id=r-p1-f1 created=2026-09-20T09:16:06 phase=1 state=fixed -->
### r-p1-f1 · finding [fixed] · The rewrite ran over the whole file, eating markdown body lines beginning 'model:' (phase 1)

Phase-1 review. Both `_existing_model` and `_rewrite` scanned every line, so a BODY line starting `model:` was treated as frontmatter and deleted. Probed: a body reading "Keys:\n\nmodel: <provider/id>\n\nEnd." came back as "Keys:\n\n\nEnd." — the documentation line silently removed. Reachable as soon as any agent body documents its own frontmatter, which is a normal thing for an agent body to do.

Inherited rather than introduced: install.sh`s awk used `/^model:/ { next }` over the whole file and had no way to know where the frontmatter ended. In Python there is no such excuse. FIXED: `_split_frontmatter` bounds the rewrite between the opening and closing `---` fences; the body is content and is never touched. Test: test_a_body_line_beginning_model_is_not_eaten.

<!-- fr:journal kind=finding scope=plan id=r-p1-f2 created=2026-09-20T09:16:07 phase=1 state=fixed -->
### r-p1-f2 · finding [fixed] · The early-skip compared model values, so a correct-but-misplaced model stayed misplaced (phase 1)

Phase-1 review. The loop did `if old_model == model: continue`, so a file whose `model:` line carried the RIGHT value in the WRONG position (before the anchor, from a hand-edit or an older generator) was skipped, and the "model: immediately after mode: subagent" invariant the module documents did not hold for it. Probed: anchor at index 3, model at index 1, zero changes reported.

Low severity — YAML key order is irrelevant to OpenCode`s parser, and after phase 2 deletes install.sh`s awk nothing anchors on position either. Fixed anyway because the module DOCUMENTS the invariant, and an invariant that holds only for files the code happened to write is not an invariant. FIXED: the decision to write compares RENDERED content against the desired rendering, not the model value. Idempotence survives — pinned by test_an_already_correct_file_is_not_rewritten, which asserts mtime is unchanged for an already-correct file. Tests: test_a_correct_but_misplaced_model_is_moved_to_the_anchor plus that one.

<!-- fr:journal kind=finding scope=plan id=r-p1-f4 created=2026-09-20T09:16:07 phase=1 state=refuted -->
### r-p1-f4 · finding [refuted] · I doubted a correct report, and my own check was the sloppy one (phase 1)

Phase-1 review, recorded against myself. The executor reported that `opencode agent list` exposes no `model:` field, so the skeleton smoke could not confirm resolution through the binary, and verified via file content instead — explicitly declining to imply the CLI had confirmed it. I doubted that and grepped: `opencode agent list | grep -ciE "?model"?` returned 108, which looked like a contradiction.

It was not. All 108 matches were the BRANCH NAME — `fix__opencode-tier-model-reaches-dispatch` — appearing inside `external_directory` permission patterns. The executor`s claim is correct. REFUTED as a finding against their work; recorded because the mistake was mine and it is the second of this exact shape in two runs (the other being gh#494`s r-p4-f1, where a load-bearing spec premise was checked with an ad-hoc regex through ugrep). Both times: a substring pattern used where a precise one was needed, on a claim that mattered.

The useful corollary, verified: the model IS observable in the session store — `select agent, json_extract(model, $.id) from session` returns `fr-phase-executor|nemotron-3.5-lightning-free` from the gh#494 run. So the binary`s silence limits only the SMOKE, not phase 4`s acceptance, which reads opencode.db as the plan already specifies.
