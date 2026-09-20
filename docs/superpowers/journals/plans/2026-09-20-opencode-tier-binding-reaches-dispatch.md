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

<!-- fr:journal kind=finding scope=plan id=p2-f1-integration-tests-broke created=2026-09-20T07:24:42 phase=2 state=open -->
### p2-f1-integration-tests-broke · finding [open] · The three PR #495 integration tests cannot pass unchanged — all three, not just the one the spec flagged (phase 2)

Spec §3.A / Test Plan item 3 predicted only `test_install_asks_fr_for_every_tier_and_only_for_tiers` would have its premise change (it counts `fr models resolve` calls, one per tier, via a stub `fr`). Ran all three under the new install.sh (plain copy + one `fr models apply --harness opencode` call): all three FAIL, not one.

Root cause: the stub `fr` these three tests install on PATH (`_stub_fr` in tests/integration/test_install_opencode_agents.py) only implements `models resolve --tier <t>` — it echoes a canned model for a given `--tier`. It implements nothing for `models apply`. Since install.sh no longer resolves per-tier in bash (that loop, and the file-rewriting awk, are both deleted — this is the point of the phase), the ONE thing it now calls is `fr models apply --harness opencode`, which the stub does not understand and therefore does nothing: no `model:` line is ever written.

So it is not just the call-counting assertion whose premise changed (the middle test) — the other two, which read back the actual `model:` content of the installed files, also fail because no real `fr models apply`/materialize_agents ever ran; the stub cannot fake resolution-plus-rewrite at harness granularity the way it could fake a single per-tier resolve call.

Confirmed via `uv run pytest tests/integration/test_install_opencode_agents.py -q`: 3 failed, 4 passed — the 4 that pass are the ones with no model-resolution content (file delivery, gating, mode:-anchor-shape, uninstall).

This is a real deviation from the spec Test Plan (item 3), flagged rather than silently edited per the phase brief. The tests are not wrong to assert this behaviour — they are exactly the safety net the spec calls them; the fake-`fr` fixture design just does not compose with moving resolution+rewrite into a single opaque `fr models apply` call. Options for whoever resolves this: (a) upgrade `_stub_fr` to also fake `models apply --harness opencode` by writing the same frontmatter shape the real materialiser would (re-implements the rewrite a second time in the stub, which is the thing this whole spec is trying to avoid duplicating); (b) accept the three tests need editing to assert through a REAL `fr` (e.g. `uv run fr` from PATH via the venv) rather than a stub, which changes what they cover; (c) some other seam. Left unresolved — decision for the orchestrator, not this executor.

<!-- fr:journal kind=discovery scope=plan id=p2-t2-s3-no-refactor created=2026-09-20T07:25:04 phase=2 -->
### p2-t2-s3-no-refactor · discovery · no-refactor-because: P2.T2 — the three OpenCode delivery copy loops (skills, commands, agents) stay separate (phase 2)

With the awk gone, the agent-delivery block is a plain copy loop plus one `fr models apply` call, alongside the pre-existing skills and commands copy loops. Re-examined folding them into one generic loop (task instructions require re-deciding this, not inheriting the prior verdict).

Still not worth it: the three loops differ in shape, not just source path — skills copies into a per-skill SUBDIRECTORY (`mkdir -p "$OPENCODE_SKILLS_DIR/$skill"`) and always names the destination file `SKILL.md`; commands copies FLAT from a different source tree (`.opencode/commands/$skill.md`, keyed by skill name) to a flat destination; agents copies FLAT from `.opencode/agent/*.md`, globbing agent files directly rather than deriving a name from the skill list, and the agent loop alone has a second step (`fr models apply`) with no equivalent in the other two. A generic loop would need a directory-vs-flat parameter, a source-glob-vs-derived-name parameter, and a not-generalizable post-step for exactly one of the three cases — more indirection than the ~24 lines it would replace. Phase 3 of the prior plan (PR #495, gh-494) already reached this conclusion for the pre-existing skills/commands pair; re-deciding it with the agents loop now in the mix reaches the same answer.

<!-- fr:journal kind=discovery scope=plan id=p2-d1-second-preexisting-failure created=2026-09-20T07:31:24 phase=2 -->
### p2-d1-second-preexisting-failure · discovery · A second pre-existing, environment-caused failure alongside the documented one: test_install_bridge_flag_writes_wrapper (phase 2)

Full `uv run pytest -q --no-cov --basetemp=/tmp/sb` shows 4 failing, not the 1 the dispatch brief names. Three are the materialize/apply integration tests already journaled as p2-f1 (a real, in-scope deviation). The fourth, `tests/integration/test_install_bridge.py::test_install_bridge_flag_writes_wrapper`, is unrelated to this phase: it uses the REAL host environment (`env = os.environ.copy()`, not the sandboxed fake_home fixture) and fails because this devcontainer's globally `uv tool install`ed `fr` at `/home/vscode/.local/share/uv/tools/fr/bin/python` cannot `import fr_vk.bridge`.

Verified pre-existing and untouched by this phase: `git stash push -- scripts/install.sh` (reverting to the origin/main version, since this phase's only diff to that file is the OpenCode agent-delivery block) then re-ran the test — same failure, same error text, before `git stash pop` restored my change. My diff never touches the `--install-bridge` code path (lines 56-91, untouched — confirmed via `git diff origin/main -- scripts/install.sh`).

Recording this rather than silently treating it as covered by the "one permitted pre-existing failure" allowance in the dispatch brief, since it is a second, different failure the brief did not name.

<!-- fr:journal kind=finding scope=plan id=p2-f1-integration-tests-broke-resolved created=2026-09-20T09:40:15 state=fixed resolves=p2-f1-integration-tests-broke -->
### p2-f1-integration-tests-broke-resolved · finding [fixed] · resolves p2-f1-integration-tests-broke: The three PR #495 integration tests cannot pass unchanged — all three, not just the one the spec flagged

Resolved by the orchestrator, and the escalation was exactly right — leaving the file unedited and recording three options beat making it green. Decision: option 'use the real fr'. The stub was a bet on install.sh keeping resolution in bash; the fix moved that seam, so the stub could fake nothing. Faking 'apply' would have meant reimplementing the materialiser in shell and asserting a fake did the work. Instead a thin argv-logging wrapper around the REAL fr (resolved from the running interpreter's bin dir, not a hardcoded .venv path) is planted on the sandbox PATH, and bindings are seeded into the sandboxed ~/.config/fr/models.yaml — the same file a real operator writes. The three now exercise install.sh + real resolution + real materialiser end to end: STRONGER than before, not merely green. The per-tier-count test is replaced by test_install_delivers_models_through_one_fr_models_apply_call, pinning what is still install.sh's own contract. NON-VACUITY PROVEN by mutation: removing the 'fr models apply' line fails all three; install.sh restored byte-exact (diff -q). Spec Test Plan item 3 corrected in the same commit — the second correction to that item, and it says so.

<!-- fr:journal kind=finding scope=plan id=r-p2-f2 created=2026-09-20T09:40:15 phase=2 state=fixed -->
### r-p2-f2 · finding [fixed] · Extracting the CLI's resolution helper left the repo-over-user rule written twice, and they disagreed (phase 2)

Phase-2 review. `_resolved_config()` gave the three CLI verbs one resolution path — and left `fr.models.resolve()` with NO production caller (grep: only docstrings and its own test). So the repo-over-user rule existed in two places, which is precisely what extracting a helper is supposed to prevent, one level out.

They did not agree. Proved directly: with `repo={"opencode":{"hard":""}}` and `user={"opencode":{"hard":"provider/U"}}`, `resolve()` returns `provider/U` (a falsy binding is not a binding, so it falls through) while the dict merge returns `""` (the falsy repo value wins). Reachable via a models.yaml with an empty value; and `load_models` does `str(m)`, so a YAML null becomes the string "None" — a pre-existing wart that would propagate differently through each path.

FIXED by making one of them the implementation: `fr.models.resolved_config(repo_cfg=, user_cfg=)` is now THE rule (skipping falsy bindings when layering, preserving `resolve()`s semantics exactly), `resolve()` is a lookup on it, and `models_cmd._resolved_config()` only supplies the two files. The materialiser needs the whole map and `resolve` needs one value — two shapes, one rule. Tests: test_a_falsy_repo_binding_does_not_shadow_a_real_user_one, and test_resolve_and_resolved_config_never_disagree which cross-checks every (harness, tier) either form can name.

<!-- fr:journal kind=discovery scope=plan id=x-p2-envsplit created=2026-09-20T09:40:15 phase=2 -->
### x-p2-envsplit · discovery · Host and devcontainer see DIFFERENT pre-existing failures — that is the whole of #489 (phase 2)

Phase-2 review, reconciling the executor`s report with my own run. The executor reported `test_install_bridge.py::test_install_bridge_flag_writes_wrapper` failing (its devcontainer`s globally uv-tool-installed `fr` cannot import `fr_vk.bridge`) and `test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable` PASSING. On the host I see the exact inverse: install_bridge passes, workflow_check fails.

Both readings are correct. The executor runs inside the fr devcontainer; the orchestrator runs on the macOS host. workflow_check fails only where a Claude Code marketplace clone exists (the unneutralised fourth workflow-resolution source) — present on the host, absent in the container. install_bridge fails only where a stale global `fr` tool install exists — present in the container, absent on the host.

So "the known pre-existing failure" is not a fixed set: it is a function of where the suite runs. That is #489/#463`s thesis stated as a lived fact, and it is worth carrying into future phase briefs — naming ONE permitted failure was wrong of me, because the permitted set differs per environment. The executor`s scoping method was sound and better than last run`s: it reverted only the file it had changed (`git stash push -- scripts/install.sh`) to the origin/main version and re-ran, rather than stashing everything, and confirmed with `git diff origin/main -- scripts/install.sh` that its diff never touches the `--install-bridge` path.

<!-- fr:journal kind=discovery scope=plan id=p3-t1-s3-reread created=2026-09-20T11:04:08 phase=3 -->
### p3-t1-s3-reread · discovery · P3.T1.S3 re-read found one real ambiguity: 'and' read as a conjunction of conditions, not a list of cases (phase 3)

Read the whole **Harness — dispatch:** clause end to end as an OpenCode reader with nothing else loaded. Three of the four things it carries survive the compression fine: the dispatch instruction (task tool, subagent_type, serial, same brief), the why-the-name-carries-the-tier sentence, and the cost policy with its measured figures and the inline escape.

The fallback did NOT, in its first form. I wrote 'use the untiered `fr-phase-executor` when a phase declares no `tier` and when its tier is UNRESOLVED', which a reader can parse as requiring BOTH conditions — exactly the misreading that keeps the tier agent in play for an unbound tier, i.e. the defect this clause is supposed to close. So this is a rebalance, not a no-refactor: the fallback is now its own sentence naming them as two cases ('Two cases take the untiered `fr-phase-executor` instead — a phase declaring no `tier`, and a tier that is UNRESOLVED (`fr models resolve` prints nothing) — and you journal which: ...'), and the preceding clause ends with a full stop instead of a semicolon so the OpenCode arm is two readable sentences rather than one 3-clause chain.

Note what the test could and could not see: the prose test passed BOTH forms, because both name the untiered agent alongside an unresolved-condition word and a journal word within the same neighbourhood. The ambiguity was invisible to it by construction — meaning-that-survives-rewording cannot also detect a misleading conjunction. That is the step's whole point, and it earned its keep here.

Line budget held throughout: the file is still exactly 120/120 (test_under_120_lines), the edit stayed on line 92, which is now 557 chars. That is longer than the file's previous maximum (312) and is the price of the cap; the file's stated convention is long lines rather than more of them, and markdown reflows the paragraph identically either way, so the cost is borne by diffs and greps, not readers. Rejected the alternative of re-flowing the whole 8-line clause to ~180 chars/line: same line count, more uniform source, but it turns a 1-line diff into an 8-line one for reviewers of a clause where every earlier line is unchanged prose.

<!-- fr:journal kind=discovery scope=plan id=p3-d1-gate-one-preexisting-failure created=2026-09-20T11:11:04 phase=3 -->
### p3-d1-gate-one-preexisting-failure · discovery · Full gate: one failure, scoped to a file phase 3 never touched — the host half of #489 (phase 3)

`uv run pytest -q --no-cov --basetemp=/tmp/sb`: 1 failed, 3292 passed, 80 skipped in 241.61s. The one failure is tests/unit/test_workflow_check.py::test_cli_all_fails_when_nothing_is_discoverable, asserting exit 1 and getting 0 with output 'fr-goal: ok' — the host-side pre-existing failure of #489/#463 (a Claude Code marketplace clone exists here as a fourth, unneutralised workflow-resolution source, so 'nothing is discoverable' is not reachable on this machine). This run is on the macOS HOST, which is why it is the inverse of phase 2's container run (x-p2-envsplit): install_bridge passes here, workflow_check fails.

Scoped by the prescribed method rather than by trusting the brief's list: `git stash push -- <every path in git diff --name-only origin/main>` (my uncommitted phase-3 work only, since phases 1-2 are committed), re-ran the single test — SAME failure, same assert — then `git stash pop` restored it. Independently, phase 3's diff against HEAD contains NO Python source at all: fr-goal/SKILL.md + its two mirrors, docs/acceptance/{matrix.yaml,the three reports}, tests/unit/test_fr_goal_dispatch_prose.py, the nine version manifests + uv.lock, and the plan/journal/run artifacts. There is no path by which it could reach fr.workflow.resolve.

Rest of the gate, each output read: ruff check 'All checks passed!'; ruff format --check '366 files already formatted'; mypy 'Success: no issues found in 138 source files'; sync-opencode.py --check and sync-hermes.py --check both 'in sync' exit 0; fr harness parity --check 'declared matrix agrees with the registration files'; fr validate artifacts '28 artifact(s) checked — all structurally valid'; fr acceptance check exit 0 (124 rows OK, ci 102 / skipped 18 / not-implemented 4 — the warnings are the pre-existing archived-spec ref nags on unrelated rows); bump-version.py --check 'ok — versions agree' at 4.8.0; fr journal check exit 0.

<!-- fr:journal kind=discovery scope=plan id=x-p4-manual created=2026-09-20T11:12:58 phase=4 -->
### x-p4-manual · discovery · Phase 4 ships UNIMPLEMENTED by design — never dispatched (and see #496) (phase 4)

Phase 4 is `tag: manual`: the operator, post-merge, clears the opencode tier bindings, answers the model-per-tier question in a real /fr-goal run, and shows an opencode.db session row where `agent = fr-phase-executor-<tier>` AND `model` is the model just answered. That is gh#498`s own acceptance and the half no unit test can buy — it proves the answer reached the dispatched agent inside the run that asked for it.

fr-goal §5 forbids dispatching a phase executor for a manual phase, so nothing was dispatched and the steps stay unticked. The PR marks it "unimplemented — operator pushes to this PR".

As in the gh#494 run, `fr run advance` built a `phase/4/implement-phase` dispatch brief anyway — `for_each: phase` does not consult the phase`s `tag`. That is issue #496, filed from that run; this is its second observed instance, in a plan whose manual phase would have handed a subagent a PAID model run and a real consumer install. Both members are resolved `done` because the cursor has only done|failed, and this entry is the record of what `done` means here.
