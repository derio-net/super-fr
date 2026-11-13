<!-- fr:journal-schema=4 -->
# Journal: 2026-11-13-writing-standards-docs

<!-- fr:journal kind=decision scope=plan id=plan-gate-last created=2026-11-13T21:49:14+00:00 -->
### plan-gate-last · decision · The CI gate turns on in the last phase

ci-ok depends on site-build (.fr/ci.yaml gate_checks: [ci-ok]); turning the writing-standard step on before every page passes would make every phase's tests: ci evidence red.

<!-- fr:journal kind=decision scope=plan id=plan-fact-keeper-in-review created=2026-11-13T21:49:14+00:00 -->
### plan-fact-keeper-in-review · decision · Fact-keeper reviews run in each phase's review step

A phase executor cannot dispatch agents; the executor writes each page's baseline outside the repo and the orchestrator dispatches one fact-keeper per page during review-phase, recording the results in that record (R8).

<!-- fr:journal kind=decision scope=plan id=baseline created=2026-11-13T22:11:09+00:00 -->
### baseline · decision · Rewrite baseline: 63764b87921b4f741414cff4def0d5ee205547c9

git merge-base HEAD origin/main at the start of the rewrite (after merging origin/main at 63764b879, #1435, in phase 1); every --preserve-from and fact review in phases 2–6 uses it

<!-- fr:journal kind=discovery scope=plan id=ws-starting-totals created=2026-11-13T22:11:09+00:00 phase=1 -->
### ws-starting-totals · discovery · Starting writing-standard totals (pin 3b0c7d0, before the terms file) (phase 1)

`bash scripts/check-writing-standards.sh /home/user/blog-craft`, exit 1, without `.writing-standard-terms`, re-measured after the merge of origin/main at 63764b879 (identical to the pre-merge run):
- guides (`docs/*.md`, ste): 137 FAIL, 243 WARN
- reference (`docs/reference/*.md`, ste; cli.md opted out): 22 FAIL, 49 WARN
- explainers (`docs/explainers/*.md`, plain-language; why-fr.md elements-of-style, index.md none): 1 FAIL, 585 WARN
FAIL kinds: 159 `sentence_length` (ste), 1 `average_sentence_length` (01-fr-goal.md, 23.4 words/sentence).
The spec's reference figure (39 FAIL) included cli.md, which now carries `writing_standard: none`;
the spec's cloud-setup.md plain-language failure no longer applies, as guides run under ste.

<!-- fr:journal kind=discovery scope=plan id=ws-terms-effect created=2026-11-13T22:11:09+00:00 phase=1 -->
### ws-terms-effect · discovery · .writing-standard-terms removes 65 warnings and no FAIL (phase 1)

With 15 abbreviations (API, CI, CLI, HEAD, HTML, ID, JSON, PATH, PR, README, REST, SSH, UI, URL, YAML)
and 6 -ing fr nouns (debugging, finding, landing, pending, sibling, warning), WARN totals go
877 → 812: guides 243 → 221, reference 49 → 46, explainers 585 → 545. FAIL totals are unchanged
(137 / 22 / 1). Abbreviation warnings left for the rewrite: AI, ISO, OPEN, POM, TDD (spell out
or code-format). Vocabulary words such as `refuse`/`require`/`create` were deliberately not listed:
a page can use the standard's replacement.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-13T22:11:09+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

a one-assertion smoke test; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-13T22:11:09+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

a one-line pin and a flat terms list; no code to restructure

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-13T22:11:09+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

a prose rule edit plus its generated mirror; nothing to restructure

<!-- fr:journal kind=discovery scope=plan id=ws-terms-effect-2 created=2026-11-13T22:16:46+00:00 phase=1 -->
### ws-terms-effect-2 · discovery · .writing-standard-terms after review: 19 terms, 63 warnings removed (phase 1)

Supersedes ws-terms-effect's numbers. Review findings p1-r3 and p1-r4: dropped landing (it also exempted the verb at docs/gate-backfill.md:138) and JSON (it removed no warning on any page). 19 terms remain: 14 abbreviations (API, CI, CLI, HEAD, HTML, ID, PATH, PR, README, REST, SSH, UI, URL, YAML) and 5 -ing fr nouns (debugging, finding, pending, sibling, warning). WARN totals with the file: guides 223, reference 46, explainers 545 (814; 877 without it, so 63 removed). FAIL totals are unchanged (137 / 22 / 1). The two landing warnings (gate-backfill.md:138, docs-currency.md:227) are left to their rewrite in phase 3.

<!-- fr:journal kind=review scope=plan id=review-p1 created=2026-11-13T22:23:55+00:00 phase=1 -->
### review-p1 · review · phase 1 review: 5 findings, all in scope, all fixed (phase 1)

Independent reviewer (separate context, read-only) over spec, plan and diff 63764b8..HEAD; ran the pytest set (225 passed), sync-opencode --check, fr docs check, the script (exit 1 as expected pre-rewrite), probed relative paths and cwd. Fixes in 84fd6de8d, 995ec8038; ci-ok green on 89950d2. Suggested lenses: tests (already in the set), shell (not a lens this repo defines; its concerns were covered by p1-r1/p1-r2).

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-13T22:23:55+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · tests pinned script substrings, not behaviour (exit aggregation, relative path, toplevel cd) (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-13T22:23:55+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · script took the toplevel from the caller's cwd; `|| exit 2` was dead (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-13T22:23:55+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · `landing` term exempted verb uses too, contrary to R4 (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-13T22:23:55+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · `JSON` term removed no warning (R4) (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-13T22:23:55+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · redundant smoke and string-pin tests (phase 1)

Raised by the phase 1 reviewer.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-13T22:23:55+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: tests pinned script substrings, not behaviour (exit aggregation, relative path, toplevel cd) (phase 1)

84fd6de8d; test_the_script_runs_every_group_from_the_toplevel_and_exits_with_the_highest_code, test_the_script_exits_zero_when_every_group_passes, test_a_fail_in_either_group_fails_the_script (mutations exit 0 / no realpath now fail)

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-13T22:23:55+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: script took the toplevel from the caller's cwd; `|| exit 2` was dead (phase 1)

84fd6de8d; test_the_script_checks_its_own_repo_whatever_the_callers_directory

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-13T22:23:55+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: `landing` term exempted verb uses too, contrary to R4 (phase 1)

995ec8038; term removed; the two hidden warnings return for the phase-3 rewrite (checker run, no unit test: CI has no blog-craft checkout)

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-13T22:23:55+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: `JSON` term removed no warning (R4) (phase 1)

995ec8038; term removed

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-13T22:23:55+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: redundant smoke and string-pin tests (phase 1)

84fd6de8d; both deleted, replaced by the behaviour tests

<!-- fr:journal kind=discovery scope=plan id=p2-acc-components-gh-host created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-components-gh-host · discovery · accuracy: components.md said gh is not pointed at a self-hosted host (corrected) (phase 2)

Claim: components.md:64-65 (merge base) "`gh` and `tea` are not pointed at a self-hosted host yet, and fr warns instead of pretending". Code: packages/fr/src/fr/hostclient.py:344-364 passes a declared GitHub host to the client and warns only for gitea; packages/fr/src/fr/gh.py:131-152 (`host_env`) sets `GH_HOST` and raises GhHostRefusedError for a host gh is not logged into. Correction (4d47e37f3): fr passes a declared GitHub Enterprise `host:` to gh as `GH_HOST` and refuses a host gh is not logged into; tea is not pointed at a self-hosted host, and fr warns when a Gitea `host:` is declared.

<!-- fr:journal kind=discovery scope=plan id=p2-acc-components-vk-source created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-components-vk-source · discovery · accuracy: components.md named the BloopAI VK server and npx (corrected to install.sh) (phase 2)

Claim: components.md:46-47 linked github.com/BloopAI/vibe-kanban and `npx vibe-kanban@latest --mcp`. Code: scripts/install.sh:116 (`VK_MCP_BINARY=$HOME/bin/vibe-kanban-mcp`), :501-506 (absent binary: warning, MCP setup skipped, "see https://github.com/derio-net/vibe-kanban"), :816-822 (registers that binary); packages/fr-vk/src/fr_vk/_mcp_client.py:39-47 falls back to `npx -y vibe-kanban@latest --mcp` when `vibe-kanban-mcp` is not on PATH. Settled by following install.sh (brief): the link now points at derio-net/vibe-kanban, the page names the installer's binary and keeps the fr-vk npx fallback. Commit 4d47e37f3.

<!-- fr:journal kind=discovery scope=plan id=p2-acc-components-hermes-hooks created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-components-hermes-hooks · discovery · accuracy: components.md said hooks/hermes/ holds only the isolation guards (corrected) (phase 2)

Claim: components.md:28-29 "`plugins/super-fr/hooks/hermes/` holds the Hermes ports of the isolation guards". Code: the directory holds fr-isolation-guard.sh, fr-isolation-required.sh and fr-merged-pr-push-guard.sh (.hermes/config.snippet.yaml:13-21). Correction (4d47e37f3): "…of the isolation guards and the merged-PR push guard".

<!-- fr:journal kind=discovery scope=plan id=p2-acc-dispatch-labels-off created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-dispatch-labels-off · discovery · accuracy: dispatch-lifecycle.md said fr apply skips label writes under forge.labels: off (corrected) (phase 2)

Claim: dispatch-lifecycle.md:44-47 "neither `fr apply` nor the bridge writes any of these labels". Code: packages/fr/src/fr/commands/apply_cmd.py:277-285 calls `require_forge(plan_root, "issues")` and `(…, "labels")` (settings/__init__.py:157-163 raises ForgeQuietError, a ServicesError) and returns exit 2 under `--yes`; only the bridge skips writes (packages/fr-dispatch/src/fr_dispatch/__init__.py:360-371 `_quiet_filtered`, :580-591 the fr:synced stamp). Correction (e61091355): the bullets describe the bridge only, plus "Under either setting, `fr apply --yes` refuses (exit 2) and names the setting."

<!-- fr:journal kind=discovery scope=plan id=p2-acc-dispatch-repos-save created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-dispatch-repos-save · discovery · accuracy: dispatch-lifecycle.md said repos sync always saves names to the manifest (corrected) (phase 2)

Claim: dispatch-lifecycle.md:74-75 "Names you pass are appended to that manifest unless you add `--no-save`". Code: packages/fr/src/fr/commands/repos_cmd.py:118 `if yes and not no_save:` — a preview never saves. Correction (e61091355): "With `--yes`, names you pass are appended…".

<!-- fr:journal kind=discovery scope=plan id=p2-acc-hermes-same-scripts created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-hermes-same-scripts · discovery · accuracy: hermes.md said the Hermes isolation guards are the Claude Code scripts (corrected) (phase 2)

Claim: hermes.md:50-51 "Hermes runs shell hooks over the same block protocol as Claude Code, so the isolation guards are the same scripts." Code: .hermes/config.snippet.yaml:11-21 registers hermes/fr-isolation-required.sh, hermes/fr-isolation-guard.sh and hermes/fr-merged-pr-push-guard.sh; plugins/super-fr/hooks/hermes/fr-isolation-required.sh:6,26 emits `{"decision":"block",…}`; hermes/fr-isolation-guard.sh:2-9 is marker-based, not pipeline-sentinel-based, and shares the decision library. Only fr-acceptance-nag.sh is the same script. Correction (a057184df): Hermes accepts a Claude-Code-style block decision, super-fr ships Hermes versions that share the decision library, and the Hermes shell guard judges by the workspace marker on every git/gh mutation, not only while a pipeline is live.

<!-- fr:journal kind=discovery scope=plan id=p2-acc-install-uninstall created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-install-uninstall · discovery · accuracy: install.md said --uninstall removes what the installer added (corrected) (phase 2)

Claim: install.md:83 "`scripts/install.sh --uninstall` removes what the installer added for each harness". Code: scripts/install.sh:223-296 removes the Claude rules, fr's WorktreeCreate/WorktreeRemove hooks, the vibe_kanban MCP entry, the OpenCode skills/commands/agents/plugin (and its cli.json entry), the Hermes hooks/rules and skills, and prints at :296 that the plugin and PostToolUse hook in settings.json were NOT removed; the marketplace registration and enabledPlugins (:527-551) and the fr CLI stay. Correction (cb73793da): names what it removes and that the plugin registration in ~/.claude/settings.json and the fr CLI must be removed by hand.

<!-- fr:journal kind=discovery scope=plan id=p2-acc-plan-model-folder created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-plan-model-folder · discovery · accuracy: plan-model.md showed the folder as <YYYY-MM-DD-slug> (corrected) (phase 2)

Claim: plan-model.md:22 `docs/superpowers/plans/<YYYY-MM-DD-slug>/`. Code: packages/fr/src/fr/commands/plan_cmd.py:130 (`--slug`, "becomes folder name"); no date is enforced. Correction (5c634cd84): `<slug>/`, with a note that by convention the slug starts with a date.

<!-- fr:journal kind=discovery scope=plan id=p2-acc-plan-model-meta-keys created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-plan-model-meta-keys · discovery · accuracy: plan-model.md listed _meta.yaml keys as slug/…/no created (corrected) (phase 2)

Claim: plan-model.md:23 comment "slug, spec, target repo, fr_version range, schema_version". Code: packages/fr/src/fr/types.py:45-54 `PlanMeta`: `plan` (not `slug`), `spec`, `target_repo`, `fr_version`, required `created`, `schema_version`. Correction (5c634cd84): "plan (its slug), spec, target_repo, fr_version, created, schema_version".

<!-- fr:journal kind=discovery scope=plan id=p2-acc-plan-model-state-block created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-plan-model-state-block · discovery · accuracy: plan-model.md omitted the phase file's state: block (corrected) (phase 2)

Claim: plan-model.md:31-34 a phase file is a `phase:` header "followed by `tasks:`". Code: packages/fr/src/fr/types.py:196-201 `PhaseDoc` also requires `state: PhaseStateBlock` (types.py:176-193: per-step state and the phase's completion). Correction (5c634cd84): adds the `state:` block that records each step's tick and the phase's completion.

<!-- fr:journal kind=discovery scope=plan id=p2-acc-workflow-shapes-yes created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-workflow-shapes-yes · discovery · accuracy: workflow-shapes.md showed adopt --supersede and reshape as writing (corrected) (phase 2)

Claim: workflow-shapes.md:34-35 `fr run adopt <plan-dir> --supersede # replace a stranded run` and `fr run reshape <run-id> # move a drifted cursor…`. Code: `uv run fr run adopt --help` (--supersede "preview unless --yes"; "Dry-run by default; --yes writes one commit") and `fr run reshape --help` ("--yes Write the reshaped cursor (default: preview the diff only)"). Correction (cf7a68a21): both comments end "(preview unless --yes)".

<!-- fr:journal kind=discovery scope=plan id=p2-acc-cli-isolation-exec created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-cli-isolation-exec · discovery · accuracy: cli.md said isolation exec always runs in a container (corrected) (phase 2)

Claim: cli.md:29 "Run a build, test or lint command inside that workspace's container." Code: packages/fr/src/fr/commands/isolation_cmd.py:459-466 runs through `_target_for(root, state)` (:85-93, the backend of the workspace's recorded mode); host-worktree and external modes have no fr container. Correction (30f0f6a4a): "…inside that workspace: in its container in devcontainer mode, in the worktree itself in the docker-less modes."

<!-- fr:journal kind=discovery scope=plan id=p2-acc-cli-drift-gate created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-cli-drift-gate · discovery · accuracy: cli.md said every fr command refuses a drifted branch (corrected) (phase 2)

Claim: cli.md:53-54 "A branch left under the old placement is refused by every fr command, `fr push`, `deliver` and `fr validate artifacts`". Code: packages/fr/src/fr/artifacts/trigger.py:486-494 refuses drift only when `not is_exempt(...)`, so read-only commands pass, and `fr placement` passes on a drifted tree. Correction (30f0f6a4a): "…refused by fr's CLI-entry gate (every command that is not read-only), `fr push`, …".

<!-- fr:journal kind=discovery scope=plan id=p2-acc-unverified-left created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-acc-unverified-left · discovery · accuracy: six unverified claims left as written (phase 2)

Not wrong per the reviews and not quickly verifiable end to end, so the text stays: acceptance-matrix.md:107 GitLab `expose_as` vs job summary (matches fr/init scaffold templates); dispatch-lifecycle.md:28 labels derived "on every tick" (render.py projection; bridge re-render not traced; the rewrite keeps the agentless passive and adds no actor); hermes.md:32 `/fr-goal` slash names (Hermes behaviour, HERMES.md:80); install.md:79 CLI-only capability judgement; plan-model.md:66-67 runner opens one PR per phase; workflow-shapes.md:39 cursor path is the repo placement's (quiet/stealth put it below the feature root, artifacts/paths.py:128-135) — incomplete, not wrong. Refuted: none. acceptance-matrix.md had no wrong-or-stale finding, so its baseline is the merge base.

<!-- fr:journal kind=discovery scope=plan id=p2-ws-acceptance-matrix created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-ws-acceptance-matrix · discovery · ste rewrite: docs/reference/acceptance-matrix.md (phase 2)

Baseline: 63764b87921b4f741414cff4def0d5ee205547c9 (merge base; no corrections); baseline file: /tmp/claude-0/-home-user/2ae187b3-8892-590d-8ab7-d7c2dc9e646f/scratchpad/baselines/docs/reference/acceptance-matrix.md. Sentences/avg 38 / 19.7 -> 64 / 12.4. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 11 FAIL, 12 WARN -> 0 FAIL, 2 WARN, no preserve hit. Kept: `setting` (:68 "stop and name the setting", :69 the quoted output "disabled by repo setting"): a noun naming the `.fr/settings.yaml` key, and the second is verbatim CLI output. Paragraphs split to keep six sentences or fewer; no heading changed.

<!-- fr:journal kind=discovery scope=plan id=p2-ws-components created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-ws-components · discovery · ste rewrite: docs/reference/components.md (phase 2)

Baseline: 4d47e37f3efedbb299d4ef54130382ec115127fc; baseline file: /tmp/claude-0/-home-user/2ae187b3-8892-590d-8ab7-d7c2dc9e646f/scratchpad/baselines/docs/reference/components.md. Sentences/avg 28 / 14.1 -> 40 / 10.4. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 4 FAIL, 7 WARN -> 0 FAIL, 1 WARN, no preserve hit. Kept: `brainstorming` (:34): the name of the superpowers skill, a product term. `refuse(s)` became "stop with an error"; no heading changed.

<!-- fr:journal kind=discovery scope=plan id=p2-ws-dispatch-lifecycle created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-ws-dispatch-lifecycle · discovery · ste rewrite: docs/reference/dispatch-lifecycle.md (phase 2)

Baseline: e610913551192927a389cc320ea1445726f834d6; baseline file: /tmp/claude-0/-home-user/2ae187b3-8892-590d-8ab7-d7c2dc9e646f/scratchpad/baselines/docs/reference/dispatch-lifecycle.md. Sentences/avg 30 / 13.8 -> 36 / 12.2. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 0 FAIL, 15 WARN -> 0 FAIL, 4 WARN, no preserve hit. Kept: `tracking` x3 (:19, :38, :47: "tracking issue", "tracking-only"): fr's name for the issue a phase is mirrored to, an adjective-noun with no verb replacement; `setting` (:50 "names the setting"): noun. No heading changed.

<!-- fr:journal kind=discovery scope=plan id=p2-ws-hermes created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-ws-hermes · discovery · ste rewrite: docs/reference/hermes.md (phase 2)

Baseline: a057184df8ee0829a6268b9d91c5b5a1ba065e04; baseline file: /tmp/claude-0/-home-user/2ae187b3-8892-590d-8ab7-d7c2dc9e646f/scratchpad/baselines/docs/reference/hermes.md. Sentences/avg 24 / 11.6 -> 30 / 9.4. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 2 FAIL, 2 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. H1 and front matter title changed "Running super-fr under Hermes Agent" -> "Run super-fr under Hermes Agent"; no page links its anchor (git grep 'hermes.md#' finds none). test_hermes_docs.py pins stay green.

<!-- fr:journal kind=discovery scope=plan id=p2-ws-install created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-ws-install · discovery · ste rewrite: docs/reference/install.md (phase 2)

Baseline: cb73793da178bddff5a92f9ebf398bbac63032c9; baseline file: /tmp/claude-0/-home-user/2ae187b3-8892-590d-8ab7-d7c2dc9e646f/scratchpad/baselines/docs/reference/install.md. Sentences/avg 27 / 15.7 -> 43 / 10.4. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 4 FAIL, 8 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. H1 and front matter title "Installing super-fr" -> "Install super-fr"; no inbound anchor links (git grep 'install.md#' finds none).

<!-- fr:journal kind=discovery scope=plan id=p2-ws-plan-model created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-ws-plan-model · discovery · ste rewrite: docs/reference/plan-model.md (phase 2)

Baseline: 5c634cd8402351b4f770b357c414696dbf7cb6ad; baseline file: /tmp/claude-0/-home-user/2ae187b3-8892-590d-8ab7-d7c2dc9e646f/scratchpad/baselines/docs/reference/plan-model.md. Sentences/avg 22 / 16.3 -> 32 / 11.7. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 2 FAIL, 4 WARN -> 0 FAIL, 1 WARN, no preserve hit. Kept: `tracking` (:68 "tracking issue"): fr's product term, as on dispatch-lifecycle. Heading "Making and changing one" -> "Make and change one"; no inbound anchor links.

<!-- fr:journal kind=discovery scope=plan id=p2-ws-workflow-shapes created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-ws-workflow-shapes · discovery · ste rewrite: docs/reference/workflow-shapes.md (phase 2)

Baseline: cf7a68a21bbef7cc959aaeefbe275514badea268; baseline file: /tmp/claude-0/-home-user/2ae187b3-8892-590d-8ab7-d7c2dc9e646f/scratchpad/baselines/docs/reference/workflow-shapes.md. Sentences/avg 21 / 14.1 -> 30 / 10.4. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 3 FAIL, 2 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept; no heading changed.

<!-- fr:journal kind=discovery scope=plan id=p2-ws-cli created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-ws-cli · discovery · ste rewrite: docs/reference/cli.md (phase 2)

Baseline: 30f0f6a4a2322c28f247c56c27004a96d33692c2; baseline file: /tmp/claude-0/-home-user/2ae187b3-8892-590d-8ab7-d7c2dc9e646f/scratchpad/baselines/docs/reference/cli.md. Sentences/avg 20 / 17.1 (prose only) -> 29 / 12.2 (prose only). Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 4 FAIL, 5 WARN (prose only) -> 0 FAIL, 0 WARN (prose only), no preserve hit. cli.md carries `writing_standard: none` (R1/R3), so the gate skips it: the prose was measured on a scratch copy with that key and the `<!-- generated:cli-tree -->` block removed, and preservation was checked with the checker's own `preserved_items` against the baseline (no fenced code, inline code, link target or numeral gone or added). The generated block is untouched; `uv run python scripts/sync-readme.py --check` passes. Heading "Moving between placements" -> "Move between placements"; no inbound anchor links.

<!-- fr:journal kind=discovery scope=plan id=p2-ws-totals created=2026-11-13T22:41:35+00:00 phase=2 -->
### p2-ws-totals · discovery · phase 2 writing-standard totals: 30 FAIL -> 0 over the 8 reference pages (phase 2)

Measured on the accuracy-corrected baselines: 26 FAIL over the 7 gated pages plus 4 in cli.md's prose (opted out) -> 0. WARN 50 -> 8 on the gated pages (all 8 kept with reasons in p2-ws-*). Wording tripwires (test_tripwire_fr_goal_question_rounds, test_hermes_docs, test_build_site, test_writing_standards_docs, test_tripwire_explainers_fresh, test_tripwire_readme_sync): 502 passed; `fr docs check`: 32 pages current. Fact-keeper reviews are owed in review-phase (plan-fact-keeper-in-review), against the baseline files under scratchpad/baselines/docs/reference/.
