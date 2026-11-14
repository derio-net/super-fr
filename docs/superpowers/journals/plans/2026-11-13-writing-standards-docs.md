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

<!-- fr:journal kind=discovery scope=plan id=p2-baseline-paths created=2026-11-13T22:48:32+00:00 phase=2 -->
### p2-baseline-paths · discovery · phase 2 baselines: the recorded scratchpad paths are session-local; the sha is authoritative (phase 2)

The baseline file paths in the p2-ws-* entries (/tmp/claude-0/.../scratchpad/baselines/...) are session-local and not authoritative; they may not exist later. Each page's baseline is `git show <sha>:<page>`, with the sha named in the same p2-ws-* entry: acceptance-matrix 63764b87921b4f741414cff4def0d5ee205547c9 (merge base), components 4d47e37f3efedbb299d4ef54130382ec115127fc, dispatch-lifecycle e610913551192927a389cc320ea1445726f834d6, hermes a057184df8ee0829a6268b9d91c5b5a1ba065e04, install cb73793da178bddff5a92f9ebf398bbac63032c9, plan-model 5c634cd8402351b4f770b357c414696dbf7cb6ad, workflow-shapes cf7a68a21bbef7cc959aaeefbe275514badea268, cli 30f0f6a4a2322c28f247c56c27004a96d33692c2. Later phases record the sha only. (Review finding p2-r6.)

<!-- fr:journal kind=review scope=plan id=review-p2 created=2026-11-13T22:55:39+00:00 phase=2 -->
### review-p2 · review · phase 2 review: 7 findings (6 in, 1 reclassified in), all fixed; fact-keepers: no lost, changed or added facts (phase 2)

Code reviewer (separate context, read-only) checked every accuracy commit against the cited code, the STE rewrite against each page's baseline (per-page --preserve-from), the checker, fr docs check, sync-readme --check and the wording tripwires. Eight blind fact-keepers (blog-craft agents/fact-keeper.md), one per page, given only baseline and rewrite. Fixes in 0a7eb2a1b, b8dbd1bc8, 30074254d, cd812440e, fcc855c4b, a7753a907; ci-ok green on a7753a9. Reviewer suggested a docs-accuracy lens: the phase-6 path rule requires it for every published page.

<!-- fr:journal kind=discovery scope=plan id=p2-fact-keeper created=2026-11-13T22:55:39+00:00 phase=2 -->
### p2-fact-keeper · discovery · Fact-keeper results per page (R8): page | agent | counts | resolution (phase 2)

docs/reference/hermes.md | a7f4a7f9be839cd80 | kept 28, changed 1, lost 0, added 0 | changed: title/H1 'Running super-fr under Hermes Agent' -> 'Run super-fr under Hermes Agent' (heading wording, no claim) — accepted: STE imperative heading
docs/reference/components.md | a849b5f7b517581c1 | kept 36, changed 0, lost 0, added 0
docs/reference/workflow-shapes.md | a13b9f40a73dbac76 | kept 25, changed 0, lost 0, added 0
docs/reference/plan-model.md | a1ab31e2d855cb915 | kept 18, changed 0, lost 0, added 0
docs/reference/cli.md | a837996281bb338d4 | kept 25, changed 0, lost 0, added 0
docs/reference/install.md | a773534515aa33c8e | kept 32, changed 0, lost 0, added 0
docs/reference/acceptance-matrix.md | a3eaf48db3169f5f8 | kept 41, changed 0, lost 0, added 0
docs/reference/dispatch-lifecycle.md | a47222d599708fcdc | kept 31, changed 0, lost 0, added 0

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-13T22:55:39+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · workflow-shapes: plain fr run adopt also previews unless --yes (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-13T22:55:39+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · install: --uninstall leaves-list omitted marketplace registration/clone and managed clone (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-13T22:55:39+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · cli: drift-gate wording wrong for exempt fr migrate and fr placement (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-13T22:55:39+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · cli: isolation exec 'in the worktree itself' wrong for external mode (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-13T22:55:39+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · plan-model: fr_version 'allowed to read' became 'can read' (policy vs capability) (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-13T22:55:39+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · journal p2-ws-* recorded session-local scratchpad paths (phase 2)

Raised by the phase 2 reviewer.

<!-- fr:journal kind=finding scope=plan id=p2-r7 created=2026-11-13T22:55:39+00:00 phase=2 state=open review_scope=in -->
### p2-r7 · finding [open] (reviewer: in scope) · workflow-shapes: cursor path shown is repo-placement only (phase 2)

Reviewer tagged it out of scope as pre-existing; reclassified in scope because R13 makes each rewritten page's accuracy this feature's responsibility.

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-13T22:55:39+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: workflow-shapes: plain fr run adopt also previews unless --yes (phase 2)

0a7eb2a1b

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-13T22:55:39+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: install: --uninstall leaves-list omitted marketplace registration/clone and managed clone (phase 2)

b8dbd1bc8

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-13T22:55:39+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: cli: drift-gate wording wrong for exempt fr migrate and fr placement (phase 2)

30074254d, cd812440e

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-13T22:55:39+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: cli: isolation exec 'in the worktree itself' wrong for external mode (phase 2)

30074254d

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-13T22:55:39+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: plan-model: fr_version 'allowed to read' became 'can read' (policy vs capability) (phase 2)

fcc855c4b

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-13T22:55:39+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: journal p2-ws-* recorded session-local scratchpad paths (phase 2)

a7753a907 (discovery p2-baseline-paths; journal is append-only)

<!-- fr:journal kind=finding scope=plan id=p2-r7-resolved created=2026-11-13T22:55:39+00:00 phase=2 state=fixed resolves=p2-r7 -->
### p2-r7-resolved · finding [fixed] · resolves p2-r7: workflow-shapes: cursor path shown is repo-placement only (phase 2)

0a7eb2a1b

<!-- fr:journal kind=discovery scope=plan id=p3-acc-cloud-doctor-fix created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-cloud-doctor-fix · discovery · accuracy: cloud-setup.md said fr cloud doctor prints every fix (corrected) (phase 3)

Claim: cloud-setup.md:52 (merge base) "`fr cloud doctor` lists every prerequisite above with its state and fix". Code: packages/fr/src/fr/commands/cloud_cmd.py:28-32 prints ok/FAIL, name and detail for every check, `fix:` only for a failing one; :37-42 then prints the remedy block in a cloud session for the failed items other than merge_method. Correction (542d8890a): prints the fix for each one that fails, exits 1 when any fails, and in a cloud session prints the remedy block for the failed ones other than the merge method.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-cloud-remedy-agents created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-cloud-remedy-agents · discovery · accuracy: cloud-setup.md said an fr command blocked on the agents artifact ends with the remedy block (corrected) (phase 3)

Claim: cloud-setup.md:54-56 an fr command that fails for a GraphQL 403, a worker blocked on the `agents` artifact, or a newer cursor "ends with one block". Code: only gh.py:238 (GraphQL 403) and run/model.py:589 (newer cursor) note the remedy that cli.py:142-145 prints at the CLI boundary; the agents case is triage/batch_dispatch.py:50-55 (`worker_remedy`) quoted in the worker's BLOCKED needs_action (:110-111). Correction (542d8890a): the 403 and the newer cursor end with the block; a worker blocked on the `agents` artifact quotes the same block in its `needs_action`.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-docs-base-fallback created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-docs-base-fallback · discovery · accuracy: docs-currency.md said the default base is read only from origin/HEAD (corrected) (phase 3)

Claim: docs-currency.md:107-108 "the base is the remote's default branch, read from the local `origin/HEAD`". Code: packages/fr/src/fr/docs/load.py:73-86 (`resolve_base`) calls packages/fr/src/fr/git.py:179-206 (`remote_default_ref`): refs/remotes/<remote>/HEAD, else the first of <remote>/main|master|trunk|develop; exit 2 only when neither resolves. Correction (f1a65c028): read locally from `origin/HEAD`, or else from the first of `origin/main`, `master`, `trunk` or `develop` that exists.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-docs-figure-classes created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-docs-figure-classes · discovery · accuracy: docs-currency.md listed 10 figure colour classes; figures.css has 15 (corrected) (phase 3)

Claim: docs-currency.md:189-191 class list fig-ink … fig-big. Code: scripts/site/figures.css:6-19 and :27 also define fig-panel-fill, fig-accent-line, fig-you-line, fig-ok-line and fig-flow. Correction (f1a65c028): the five added to the list.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-docs-narrow-width created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-docs-narrow-width · discovery · accuracy: docs-currency.md said the narrow figure shows up to 860 px only (corrected) (phase 3)

Claim: docs-currency.md:193-194 "the stylesheet shows it up to 860 px wide". Code: scripts/site/figures.css:21 switches at 860 px; :24 shows the narrow form below 1080 px inside `article.explainer`. Correction (f1a65c028): "up to 860 px wide, or up to 1079 px inside an article page".

<!-- fr:journal kind=discovery scope=plan id=p3-acc-docs-h1-drop created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-docs-h1-drop · discovery · accuracy: docs-currency.md said the build drops the leading H1 only in a guide (corrected) (phase 3)

Claim: docs-currency.md:201 "The build drops a leading `# H1` in a guide". Code: scripts/build-site.py:290-301 (`drop_leading_h1`) is called at :1260 in the article renderer for every non-landing page. Correction (f1a65c028): "from every article page".

<!-- fr:journal kind=discovery scope=plan id=p3-acc-gb-pass-command created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-gb-pass-command · discovery · accuracy: gate-backfill.md showed the tracker's gate pass command as acting (corrected) (phase 3)

Claim: gate-backfill.md:31-32 run the `fr gate pass --pr <n> --gate <g> --notes "..."` the tracker prints. Code: packages/fr/src/fr/gatebackfill/trackers.py:170-180 (`pass_command`) prints it without --yes and, for devops, adds `--run <id>` or `--no-run-evidence`; commands/gate_cmd.py:340 (`--yes` "Write to the forge") and :431-432 ("nothing done; re-run with --yes to act"). Correction (8a5c3996e): names the devops flags, says the command previews and `--yes` passes.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-gb-claimed-close-note created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-gb-claimed-close-note · discovery · accuracy: gate-backfill.md said a dry run notes a dropped claimed close (corrected) (phase 3)

Claim: gate-backfill.md:170-171 with `--from`, dry run and `--yes` both drop a recorded close for a claimed key "with a note". Code: gatebackfill/model.py:239-254 (`without_claimed_closes`, the note) runs only under --yes (commands/gate_cmd.py:546-549); on a dry run gatebackfill/close.py:556,587,594 skip claimed keys and gate_cmd.py:566-575 rewrites `closes:` with no note. Correction (8a5c3996e): `--yes` prints a note; a dry run drops it from the rewritten plan file without one.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-mp-spec-path created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-mp-spec-path · discovery · accuracy: merge-protection.md cited a spec path that does not exist (corrected) (phase 3)

Claim: merge-protection.md:16-17 `docs/superpowers/specs/2026-10-11-merge-train-safety-design.md`. Code: the file is docs/superpowers/implemented/specs/2026-10-11-merge-train-safety-design.md (ls). Correction (a3ac2ec20): points there.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-mp-app-permissions created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-mp-app-permissions · discovery · accuracy: merge-protection.md said install the app with contents write only (corrected) (phase 3)

Claim: merge-protection.md:59-60 "with contents write access". Code: .github/workflows/release.yml:108-112 mints with permission-contents: write and permission-issues: write (comment :35-36; the page's own Residual risk says contents and issues). Correction (a3ac2ec20): contents write and issues write access.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-mp-token-auth created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-mp-token-auth · discovery · accuracy: merge-protection.md said the release token authenticates only the two git pushes (corrected) (phase 3)

Claim: merge-protection.md:52-53 "authenticates only its two `git push` calls". Code: scripts/release.py:425-440 (`_git`: only auth=True pushes read the token); publish's GH_TOKEN (release.yml:319-320, the app token) is also used by `gh release create` (release.py:1093) and `gh issue create` (:1119) through `_run_gh` (:155). Correction (a3ac2ec20): the token authenticates the two `git push` calls and the `gh release` and `gh issue` writes; every other git command runs credential-free.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-ops-undo-none created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-ops-undo-none · discovery · accuracy: ops.md said undo takes a string `none: <reason>` (corrected) (phase 3)

Claim: ops.md:59 "`undo` | A command, or `none: <reason>`". Code: packages/fr/src/fr/ops/model.py:34-39 (`UndoNone`, `undo: {none: <reason>}`) and :52 (`undo: StrictStr | UndoNone | None`): a plain string is a command. Correction (6282d74eb): "A command, or the mapping `{none: <reason>}`".

<!-- fr:journal kind=discovery scope=plan id=p3-acc-ops-seal-target created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-ops-seal-target · discovery · accuracy: ops.md said seal's {target} is the target's name (corrected) (phase 3)

Claim: ops.md:177-178 "`{target}` (the target's name)". Code: packages/fr/src/fr/ops/helpers.py:150 (`_checked_target`, absolute path) and :164 (`.replace("{target}", shlex.quote(str(target)))`). Correction (6282d74eb): the target's full path; each substitution is shell-quoted.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-ops-scaffold-flags created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-ops-scaffold-flags · discovery · accuracy: ops.md showed fr init scaffold --ops without its required options (corrected) (phase 3)

Claim: ops.md:189-190 `fr init scaffold --ops` / `--ops --force`. Code: packages/fr/src/fr/commands/init_cmd.py:28-30: `--profile` and `--purpose` are required (`typer.Option(...)`). Correction (6282d74eb): `fr init scaffold --profile <name> --purpose "<line>" --ops` and the same with `--force`.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-ops-trust-exit created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-ops-trust-exit · discovery · accuracy: ops.md said an untrusted op set exits 2 at the DevOps stage (corrected) (phase 3)

Claim: ops.md:260-261 "a refusal such as a moved head, a changed ops profile or an untrusted op set exits 2". Code: packages/fr/src/fr/ops/gate.py:388-397 (`Gate.trust`) raises `StageFailed` with no `code=` (default 1, :63); moved head and changed profile raise with code=2. Correction (6282d74eb): exit 1, also when the op set is not trusted when asked; a moved head or a changed ops profile exits 2.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-vs-scenario-count created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-vs-scenario-count · discovery · accuracy: verification-strategies.md said tests/scenarios/ has six worked scenarios (corrected) (phase 3)

Claim: verification-strategies.md:167-168 "`tests/scenarios/` for six worked ones". Code: `ls tests/scenarios/*.sh | grep -v '/_' | wc -l` = 77. Correction (16d3ddafe): "for worked ones" (no count, which would go stale).

<!-- fr:journal kind=discovery scope=plan id=p3-acc-vs-source-default created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-vs-source-default · discovery · accuracy: verification-strategies.md implied source: worktree is the default (corrected) (phase 3)

Claim: verification-strategies.md:100-101 "`source: worktree`, unless the manifest says otherwise". Code: packages/fr/src/fr/verification/model.py:72 `source: Literal["worktree","prerelease","none"] = "none"`. Correction (16d3ddafe): the manifest sets `source: worktree`; a manifest that omits `source:` gets `none`.

<!-- fr:journal kind=discovery scope=plan id=p3-acc-unverified-left created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-acc-unverified-left · discovery · accuracy: phase 3 unverified claims left as written; none refuted (phase 3)

Not wrong per the reviews and not quickly verifiable, so the text stays: cloud-setup.md "Sonnet by default" for the cloud driver (implemented spec, no code default found) and the 2026-10-08 live walk (#1098, historical); exit-gates-release-walk.md #1207/#1195 forge state (offline); gate-backfill.md older tracker text, older-fr refusal of `closes:`, the RC aside and the collect lanes; herdr-control-sessions.md deeper runner internals; merge-protection.md token revocation at job end (action default) and the wave driver's merge-queue path; ops.md gate:devops held before merge, and "the spec review warn[s]" (only the plan self-review warning was found, plan_ops.py:1900-1925); review-lenses.md which steps can add a lens and the open-lens-finding refusal; verification-strategies.md self-review/deliver refusing a row without a scenario (messages found at plan_ops.py:1675, verification/rows.py:326, run_cmd.py:3034). Refuted: none — all 17 wrong-or-stale items held against the code. exit-gates-release-walk, herdr-control-sessions and review-lenses had no wrong-or-stale finding, so their baseline is the merge base.

<!-- fr:journal kind=finding scope=plan id=p3-ops-seal-encrypt-help created=2026-11-13T23:22:06+00:00 phase=3 state=open review_scope=out -->
### p3-ops-seal-encrypt-help · finding [open] (reviewer: out of scope) · ops_cmd.py `fr ops seal --encrypt` help says {target} is the target's name; it is the shell-quoted full path (phase 3)

packages/fr/src/fr/commands/ops_cmd.py:535-536 help: "{target} the target's name". packages/fr/src/fr/ops/helpers.py:150 resolves the target to an absolute path and :164 substitutes `shlex.quote(str(target))`. docs/ops.md was corrected in 6282d74eb; the CLI help text is code and out of this docs feature's scope. Fix: say "{target} the target's full path, shell-quoted" (and the helpers.py:140-141 docstring "the target's path as a name").

<!-- fr:journal kind=discovery scope=plan id=p3-ws-cloud-setup created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-ws-cloud-setup · discovery · ste rewrite: docs/cloud-setup.md (phase 3)

Baseline: 542d8890aadf305b886f92b2cb1bf9726ec02585. Sentences/avg 35 / 26.6 -> 82 / 12.3. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 15 FAIL, 18 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. Heading "Checking an environment" -> "Check an environment"; no inbound anchor links (git grep '<page>.md#' finds none for any phase-3 page).

<!-- fr:journal kind=discovery scope=plan id=p3-ws-docs-currency created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-ws-docs-currency · discovery · ste rewrite: docs/docs-currency.md (phase 3)

Baseline: f1a65c02891f5c7fc6ef4830ff92626419abfdd0. Sentences/avg 97 / 15.0 -> 133 / 11.4. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 17 FAIL, 28 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. Every build rule kept exact (figures, landing grammar, link rules); the figure rules became a bullet list and the class list a sentence of its own. Title/H1 "keeping pages true" -> "keep pages true"; headings "Adopting it in your repo" -> "Adopt it in your repo", "Writing a page that builds" -> "Write a page that builds" ("Where it runs", which step 5 names, unchanged). `landing` (:227, a phase-1 term no longer listed) reworded to "front-page source"; `layout: landing` is inline code. test_build_site pins stay green.

<!-- fr:journal kind=discovery scope=plan id=p3-ws-exit-gates-release-walk created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-ws-exit-gates-release-walk · discovery · ste rewrite: docs/exit-gates-release-walk.md (phase 3)

Baseline: 63764b87921b4f741414cff4def0d5ee205547c9 (merge base; no corrections). Sentences/avg 52 / 13.0 -> 64 / 11.4. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 4 FAIL, 21 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. No heading changed.

<!-- fr:journal kind=discovery scope=plan id=p3-ws-gate-backfill created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-ws-gate-backfill · discovery · ste rewrite: docs/gate-backfill.md (phase 3)

Baseline: 8a5c3996e9ae5faf9a8fa05b157a77a2a516d9e9. Sentences/avg 111 / 19.4 -> 198 / 11.9. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 38 FAIL, 47 WARN -> 0 FAIL, 4 WARN, no preserve hit. Kept: `closing` (:59) is verbatim CLI output ("gate <g> already passed on #<pr>; closing its trackers"); `planning` (:111 "a planning PR") is fr's category for a candidate PR (same term as the Decisions table, delivery.py); `working` (:236 "working tree") is the git term; `Tracking` (:252 heading "Tracking `none` …") names the `tracking:` key. `landing` (:138) reworded ("a merge of this page's repo-file commands"); "housekeeping merge" -> "a merge of only chores". Title/H1 "bringing" -> "bring"; "**Clearing.**" -> "**Clear the gate.**", "**Settling a PR…**" -> "**Settle a PR…**", "**Closing a discharged tracker**" -> "**Close a discharged tracker**" (bold run-in labels, not headings).

<!-- fr:journal kind=discovery scope=plan id=p3-ws-herdr-control-sessions created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-ws-herdr-control-sessions · discovery · ste rewrite: docs/herdr-control-sessions.md (phase 3)

Baseline: 63764b87921b4f741414cff4def0d5ee205547c9 (merge base; no corrections). Sentences/avg 82 / 12.3 -> 98 / 11.0. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 4 FAIL, 31 WARN -> 0 FAIL, 5 WARN, no preserve hit. Kept: `attempt` x5 (:56, :59, :67, :107, :108): the noun naming fr's recorded replacement/batch attempt (the `replacement` attempt/success/failure events, descriptor/attempt state), not the verb. No heading changed.

<!-- fr:journal kind=discovery scope=plan id=p3-ws-merge-protection created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-ws-merge-protection · discovery · ste rewrite: docs/merge-protection.md (phase 3)

Baseline: a3ac2ec20e7e2feae816f6cd08d1860da8837366. Sentences/avg 53 / 14.8 -> 71 / 11.6. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 8 FAIL, 15 WARN -> 0 FAIL, 2 WARN, no preserve hit. Kept: `require` x2 (:80 the indented command `--stage require` inside step 5, which the checker reads as prose; :82 the quoted GitHub UI label "require branches to be up to date"). Heading "Adopting this in another repo" -> "Adopt this in another repo"; no inbound anchor links.

<!-- fr:journal kind=discovery scope=plan id=p3-ws-ops created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-ws-ops · discovery · ste rewrite: docs/ops.md (phase 3)

Baseline: 6282d74ebd775af31772a3a27ddd4845daffcaaf. Sentences/avg 109 / 18.3 -> 183 / 11.6. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 27 FAIL, 31 WARN -> 0 FAIL, 1 WARN, no preserve hit. Kept: `create` (:14) inside the quoted example of old prose ops, "create the deploy key", which matches the fenced example's `summary: Create the deploy key`. Headings "Authoring an op" -> "Write an op", "Running ops" -> "Run ops"; no inbound anchor links. The DevOps stage table rows were split into short sentences, every condition kept.

<!-- fr:journal kind=discovery scope=plan id=p3-ws-review-lenses created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-ws-review-lenses · discovery · ste rewrite: docs/review-lenses.md (phase 3)

Baseline: 63764b87921b4f741414cff4def0d5ee205547c9 (merge base; no corrections). Sentences/avg 67 / 18.0 -> 107 / 12.0. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 16 FAIL, 15 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. Title "examining the whole feature" -> "examine the whole feature" (the page has no H1). The four lens texts became bullet lists, every item kept.

<!-- fr:journal kind=discovery scope=plan id=p3-ws-verification-strategies created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-ws-verification-strategies · discovery · ste rewrite: docs/verification-strategies.md (phase 3)

Baseline: 16d3ddafef4f6c450925e1c9ee1d1abc633c1e18. Sentences/avg 56 / 14.9 -> 77 / 11.4. Checker (pin 3b0c7d0, `--default ste --preserve-from <baseline> --stats`): 12 FAIL, 17 WARN -> 0 FAIL, 3 WARN, no preserve hit. Kept: `staging` x3 (:103-107): the name of the example strategy and its backend (`staging.yaml`), a noun. Headings "Authoring a strategy" -> "Write a strategy", "Writing a scenario" -> "Write a scenario"; no inbound anchor links.

<!-- fr:journal kind=discovery scope=plan id=p3-ws-totals created=2026-11-13T23:22:06+00:00 phase=3 -->
### p3-ws-totals · discovery · phase 3 writing-standard totals: 141 FAIL -> 0 over the 9 guides (phase 3)

Measured on the accuracy-corrected baselines (per-page sha in p3-ws-*): 141 FAIL, 223 WARN -> 0 FAIL, 15 WARN, all kept with reasons. Wording tripwires (test_tripwire_fr_goal_question_rounds, test_hermes_docs, test_build_site, test_writing_standards_docs, test_tripwire_explainers_fresh, plus test_triage_skill_docs, test_docs_globs): 508 passed; `fr docs check`: 32 pages current. fr-exit-gates.md and fr-wave-driver.md cover guides that changed, so their `reviewed` stamps moved (nothing they describe changed). Sentence splitting note for later phases: the checker starts a new sentence only before a capital, a backtick or a bracket, so a sentence that starts with lowercase `fr` is merged into the one before it. Fact-keeper reviews are owed in review-phase against `git show <sha>:<page>`.

<!-- fr:journal kind=review scope=plan id=review-p3 created=2026-11-13T23:38:18+00:00 phase=3 -->
### review-p3 · review · phase 3 review: 8 findings (7 in, 1 out), all in-scope fixed; fact-keepers: 0 lost, 3 meaning shifts fixed (phase 3)

Code reviewer (separate context, read-only) checked the six accuracy commits against the cited code (all true), the STE rewrite against each page's baseline with --preserve-from, the tripwires, fr docs check, and built the site at e84325d and HEAD to compare rendering: the checker does not see Markdown list breakage, which the build showed on ops.md and review-lenses.md. Nine blind fact-keepers (blog-craft agents/fact-keeper.md), one per guide, given only baseline and rewrite. Fixes in 036276ef9, 9d869f9b3, 3c1e17628, d6750f94c, 2605a2abc, 22103e06b, f52f33659, e8c934efb; ci-ok green on e8c934e. A built-site raw-list-marker scan over docs/*.md and docs/reference/*.md is clean apart from the two pre-existing docs-currency.md defects (p3-r8).

<!-- fr:journal kind=discovery scope=plan id=p3-fact-keeper created=2026-11-13T23:38:18+00:00 phase=3 -->
### p3-fact-keeper · discovery · Fact-keeper results per page (R8): page | counts | resolution (phase 3)

docs/cloud-setup.md | kept 67, changed 0, lost 0, added 0
docs/docs-currency.md | kept 48, changed 1, lost 0, added 0 | 'whatever aggregate check your repo requires' lost its any-scope: fixed in 22103e06b ('any aggregate check that your repo needs')
docs/exit-gates-release-walk.md | kept 46, changed 0, lost 0, added 0
docs/gate-backfill.md | kept 81, changed 0, lost 0, added 0
docs/herdr-control-sessions.md | kept 87, changed 0, lost 0, added 0
docs/merge-protection.md | kept 36, changed 0, lost 0, added 0
docs/ops.md | kept 43, changed 0, lost 0, added 0
docs/review-lenses.md | kept 71, changed 3, lost 0, added 1 | two wording-only; the conditional 'when it rewrites or disables a lens' had become a permission ('But it can ...'): fixed in 9d869f9b3; the added sentence only counts the three checks listed
docs/verification-strategies.md | kept 57, changed 1, lost 0, added 0 | 'walk refuses a source: prerelease strategy' had become 'does not run it': fixed in e8c934efb ('stops with an error', walk.py WalkError)

<!-- fr:journal kind=finding scope=plan id=p3-r1 created=2026-11-13T23:38:18+00:00 phase=3 state=open review_scope=in -->
### p3-r1 · finding [open] (reviewer: in scope) · ops.md: 2-space continuations/nested lists break the Test Plan list in the site renderer (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r2 created=2026-11-13T23:38:18+00:00 phase=3 state=open review_scope=in -->
### p3-r2 · finding [open] (reviewer: in scope) · review-lenses.md: nested lens sub-lists collapse into one paragraph with raw markers (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r3 created=2026-11-13T23:38:18+00:00 phase=3 state=open review_scope=in -->
### p3-r3 · finding [open] (reviewer: in scope) · ops.md stage 2: two merge preconditions moved out of the all-of-these list (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r4 created=2026-11-13T23:38:18+00:00 phase=3 state=open review_scope=in -->
### p3-r4 · finding [open] (reviewer: in scope) · exit-gates-release-walk.md: "workflows that trigger themselves" misstates auto-triggering (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r5 created=2026-11-13T23:38:18+00:00 phase=3 state=open review_scope=in -->
### p3-r5 · finding [open] (reviewer: in scope) · cloud-setup.md: status-bucket literal "working" became "active" (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r6 created=2026-11-13T23:38:18+00:00 phase=3 state=open review_scope=in -->
### p3-r6 · finding [open] (reviewer: in scope) · gate-backfill.md: "still does not pass" made the refusal ambiguous (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r7 created=2026-11-13T23:38:18+00:00 phase=3 state=open review_scope=in -->
### p3-r7 · finding [open] (reviewer: in scope) · gate-backfill.md Trust: subject narrowed from fr to the backfill (phase 3)

Raised by the phase 3 reviewer.

<!-- fr:journal kind=finding scope=plan id=p3-r8 created=2026-11-13T23:38:18+00:00 phase=3 state=open review_scope=out -->
### p3-r8 · finding [open] (reviewer: out of scope) · docs-currency.md and merge-protection.md lists already rendered broken at the merge base (phase 3)

Raised by the phase 3 reviewer; present at e84325d and at the merge base, not caused by the rewrite.

<!-- fr:journal kind=finding scope=plan id=p3-build-site-marker created=2026-11-13T23:38:18+00:00 phase=3 state=open review_scope=out -->
### p3-build-site-marker · finding [open] (reviewer: out of scope) · scripts/build-site.py fill_pages replaces <!-- site:pages --> even inside inline code (phase 3)

fill_pages (scripts/build-site.py:267-280) does a plain text.replace(MARKER, ...), so docs/docs-currency.md item 5, which names the marker as inline code, gets the page list inserted mid-list and its numbered list breaks at item 6. Pre-existing at the merge base; a build-script bug, not a page defect. Found while fixing p3-r8.

<!-- fr:journal kind=finding scope=plan id=p3-r1-resolved created=2026-11-13T23:38:18+00:00 phase=3 state=fixed resolves=p3-r1 -->
### p3-r1-resolved · finding [fixed] · resolves p3-r1: ops.md: 2-space continuations/nested lists break the Test Plan list in the site renderer (phase 3)

036276ef9

<!-- fr:journal kind=finding scope=plan id=p3-r2-resolved created=2026-11-13T23:38:18+00:00 phase=3 state=fixed resolves=p3-r2 -->
### p3-r2-resolved · finding [fixed] · resolves p3-r2: review-lenses.md: nested lens sub-lists collapse into one paragraph with raw markers (phase 3)

9d869f9b3

<!-- fr:journal kind=finding scope=plan id=p3-r3-resolved created=2026-11-13T23:38:18+00:00 phase=3 state=fixed resolves=p3-r3 -->
### p3-r3-resolved · finding [fixed] · resolves p3-r3: ops.md stage 2: two merge preconditions moved out of the all-of-these list (phase 3)

036276ef9

<!-- fr:journal kind=finding scope=plan id=p3-r4-resolved created=2026-11-13T23:38:18+00:00 phase=3 state=fixed resolves=p3-r4 -->
### p3-r4-resolved · finding [fixed] · resolves p3-r4: exit-gates-release-walk.md: "workflows that trigger themselves" misstates auto-triggering (phase 3)

3c1e17628

<!-- fr:journal kind=finding scope=plan id=p3-r5-resolved created=2026-11-13T23:38:18+00:00 phase=3 state=fixed resolves=p3-r5 -->
### p3-r5-resolved · finding [fixed] · resolves p3-r5: cloud-setup.md: status-bucket literal "working" became "active" (phase 3)

d6750f94c

<!-- fr:journal kind=finding scope=plan id=p3-r6-resolved created=2026-11-13T23:38:18+00:00 phase=3 state=fixed resolves=p3-r6 -->
### p3-r6-resolved · finding [fixed] · resolves p3-r6: gate-backfill.md: "still does not pass" made the refusal ambiguous (phase 3)

2605a2abc

<!-- fr:journal kind=finding scope=plan id=p3-r7-resolved created=2026-11-13T23:38:18+00:00 phase=3 state=fixed resolves=p3-r7 -->
### p3-r7-resolved · finding [fixed] · resolves p3-r7: gate-backfill.md Trust: subject narrowed from fr to the backfill (phase 3)

2605a2abc

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved created=2026-11-13T23:38:18+00:00 phase=3 state=open resolves=p3-r8 out_of_scope=true -->
### p3-r8-resolved · finding [out-of-scope] · resolves p3-r8: docs-currency.md and merge-protection.md lists already rendered broken at the merge base (phase 3)

Pre-existing at the merge base. merge-protection.md fixed anyway in f52f33659. docs-currency.md left: its CI YAML fence sits under a 2-space bullet and re-indenting changes the fenced bytes the preserve check compares; item 6 breaks because of the build-script bug p3-build-site-marker, which is filed separately.

<!-- fr:journal kind=finding scope=plan id=p3-ops-seal-encrypt-help-resolved created=2026-11-13T23:38:18+00:00 phase=3 state=open resolves=p3-ops-seal-encrypt-help out_of_scope=true -->
### p3-ops-seal-encrypt-help-resolved · finding [out-of-scope] · resolves p3-ops-seal-encrypt-help: ops_cmd.py `fr ops seal --encrypt` help says {target} is the target's name; it is the shell-quoted full path (phase 3)

A fr CLI help defect (ops_cmd.py:535-536), not caused by a docs rewrite; the page now states the code behaviour. To be filed as an issue at deliver.

<!-- fr:journal kind=finding scope=plan id=p3-build-site-marker-resolved created=2026-11-13T23:38:18+00:00 phase=3 state=open resolves=p3-build-site-marker out_of_scope=true -->
### p3-build-site-marker-resolved · finding [out-of-scope] · resolves p3-build-site-marker: scripts/build-site.py fill_pages replaces <!-- site:pages --> even inside inline code (phase 3)

Pre-existing build-script bug, not caused by this change; to be filed as an issue at deliver.

<!-- fr:journal kind=discovery scope=plan id=p4-acc-acceptance-verify-listing created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-acceptance-verify-listing · discovery · accuracy: fr-acceptance.md said a --verify row keeps appearing in fr acceptance status whatever its status, listed under post-merge owed (corrected) (phase 4)

Claim: fr-acceptance.md:164-167 (merge base) a `--verify live` (or any strategy) row "keeps appearing in `fr acceptance status` whatever its status, and the pull request body lists it under post-merge verification owed". Code: packages/fr/src/fr/acceptance/check.py:109-122 (`open_rows`, the status nag set) keeps only `is_debt` rows, acceptance/model.py:47,54-57 (a DEBT_STATUSES status or contested); commands/acceptance_cmd.py:393-415 reads no `verify`. record/pr_body.py:1135-1138 renders separate `## Pre-merge verification owed` and `## Post-merge verification owed`; plugins/super-fr/verifications/{candidate,client-live,prerelease}.yaml are `when: pre-merge`, only live.yaml is post-merge. Correction (cce064d24): the PR body lists a post-merge (`live`) row under Post-merge and a pre-merge one under Pre-merge; `fr acceptance status` lists it only while its status is debt or the row is contested.

<!-- fr:journal kind=discovery scope=plan id=p4-acc-acceptance-weekly-issue created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-acceptance-weekly-issue · discovery · accuracy: fr-acceptance.md said CI keeps a weekly "Acceptance debt" issue from fr acceptance digest (corrected) (phase 4)

Claim: fr-acceptance.md:218-219 "keeps a weekly 'Acceptance debt' issue up to date from `fr acceptance digest`". Code: .github/workflows/acceptance-report.yml:10-11,86-94 and acceptance/scaffold.py:438-524 (DEBT_STEP_*): the weekly job runs `fr debt issue --yes` (one `<repo>: Technical debt` issue) and `fr debt archive-pr --yes`; debt/render.py:178-180 `acceptance_section` is the `## Acceptance debt` section `fr acceptance digest` re-renders. Correction (cce064d24): a weekly run upserts one `<repo>: Technical debt` issue (`fr debt issue`) whose Acceptance debt section is what digest renders, and refreshes a draft PR that archives long-merged plans.

<!-- fr:journal kind=discovery scope=plan id=p4-acc-acceptance-push-trigger created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-acceptance-push-trigger · discovery · accuracy: fr-acceptance.md said CI runs the gate on push to the default branch only (corrected) (phase 4)

Claim: fr-acceptance.md:218 "on every pull request and push to the default branch". Code: true of super-fr's own .github/workflows/acceptance-report.yml:19-23 (`push: branches: [main]`), but the template `fr acceptance init` scaffolds triggers on `push: branches: ["**"]` (acceptance/scaffold.py:129,217). Correction (cce064d24): every pull request and every branch push; super-fr's own workflow narrows the push trigger to `main`.

<!-- fr:journal kind=discovery scope=plan id=p4-acc-acceptance-init-creates created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-acceptance-init-creates · discovery · accuracy: fr-acceptance.md said fr acceptance init creates the matrix (corrected) (phase 4)

Claim: fr-acceptance.md:129-130 "`fr acceptance init` creates the matrix, the rule and the gitignore entry". Code: acceptance/scaffold.py:1 (module docstring) and :845-849 (init creates the fragments directory via `features/.gitkeep` and no fragment), :887-888 (README badge only with CI). Correction (cce064d24): creates the fragments directory `docs/acceptance/features/`, the rule and the gitignore entry; a CI workflow and a README badge only beside existing CI or with `--with-ci`.

<!-- fr:journal kind=discovery scope=plan id=p4-acc-acceptance-origin-form created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-acceptance-origin-form · discovery · accuracy: fr-acceptance.md used the path form --origin <repo>:<spec-path>#R<n> (corrected) (phase 4)

Claim: fr-acceptance.md:138 (example) and :153 `--origin <repo>:<spec-path>#R<n>`. Code: acceptance/logical.py:68-89 (`to_logical`) rewrites a same-repo spec path to `spec:<slug>[#frag]`; `fr acceptance add --help` documents `spec:<slug>`; the page's own :32 uses `spec:<slug>#R<n>`. Correction (cce064d24): both use `--origin spec:<slug>#R<n>` (example `spec:some-spec#R3`).

<!-- fr:journal kind=discovery scope=plan id=p4-acc-acceptance-add-inserts created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-acceptance-add-inserts · discovery · accuracy: fr-acceptance.md said add appends the row (corrected) (phase 4)

Claim: fr-acceptance.md:143 "`add` validates the shape and appends". Code: `fr acceptance add --help` / commands/acceptance_cmd.py add docstring: inserts after its capability's last row; a new capability goes at the end of `rows:`. Correction (cce064d24): inserts the row after its capability's last row.

<!-- fr:journal kind=discovery scope=plan id=p4-acc-plan-rework-parent created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-plan-rework-parent · discovery · accuracy: fr-brainstorming-and-plan.md said fr plan rework refuses a live or incomplete parent (corrected) (phase 4)

Claim: fr-brainstorming-and-plan.md:166-168 "(the parent must be complete and archived; a live plan is refused)". Code: packages/fr/src/fr/plan_ops.py:801-803 (`_PLAN_HOMES` includes `plan`, the live directory), :860-874 (`rework_create` checks only that the parent dir exists under a plan home; no completeness check). Correction (b54dd8b78): the parent may be live or archived; fr does not check that it is complete. The CLI help still says "(Complete + archived)" (finding p4-plan-rework-help).

<!-- fr:journal kind=discovery scope=plan id=p4-acc-plan-v1-to-v2-scope created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-plan-v1-to-v2-scope · discovery · accuracy: fr-brainstorming-and-plan.md said fr migrate v1-to-v2 converts every v1 plan (corrected) (phase 4)

Claim: fr-brainstorming-and-plan.md:208-209 "converts every one in the repo at once". Code: packages/fr/src/fr/migrate.py:209-216 skips a v1 plan whose status is not Complete unless `--include-in-progress` (commands/migrate_cmd.py:34). Correction (b54dd8b78): converts every completed v1 plan; add `--include-in-progress` for the rest.

<!-- fr:journal kind=discovery scope=plan id=p4-acc-dispatch-forge-off created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-dispatch-forge-off · discovery · accuracy: fr-dispatch.md said fr apply and fr undispatch skip writes under forge.issues/labels: off (corrected) (phase 4)

Claim: fr-dispatch.md:76-78 under `forge.labels: off` or `forge.issues: off` "`fr apply`, `fr undispatch` and the bridge skip that kind of write". Code: packages/fr/src/fr/commands/apply_cmd.py:277-285 (`require_forge` issues and labels; exit 2 under `--yes`), :301-302 (dry run warns "--yes would be refused"); commands/undispatch_cmd.py:70-77 (`require_forge` issues; exit 2 under `--yes`, warning otherwise); only the bridge skips (packages/fr-dispatch/src/fr_dispatch/__init__.py:580-591). Correction (858fa8213): `fr apply --yes` refuses with exit 2 and the dry run warns; under `forge.issues: off` `fr undispatch --yes` refuses with exit 2; the bridge skips the label writes that are off.

<!-- fr:journal kind=discovery scope=plan id=p4-acc-dispatch-cli-wiring created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-dispatch-cli-wiring · discovery · accuracy: fr-dispatch.md said neither fr_dispatch nor fr_vk is wired into the fr command line (corrected) (phase 4)

Claim: fr-dispatch.md:110 "neither is wired into the `fr` command line". Code: commands/apply_cmd.py:130-131,163-164,549-555 import `fr_dispatch` (item_graph, reachability, registry) for `fr apply --to`; commands/triage_batch_cmd.py:20-22 is the second soft point (`fr triage batch dispatch`). Correction (858fa8213): the daemon is not an `fr` command, but `fr apply --to` and `fr triage batch dispatch` call into `fr_dispatch` (runner registry, item graph, reachability gate).

<!-- fr:journal kind=discovery scope=plan id=p4-acc-dispatch-failure-reasons created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-dispatch-failure-reasons · discovery · accuracy: fr-dispatch.md listed the runner failure reasons as complete (corrected) (phase 4)

Claim: fr-dispatch.md:115-116 failure reasons `project_id_missing`, `unknown_repo`, `unit_mismatch`, `mcp_error`, `gh_error`. Code: packages/fr-dispatch/src/fr_dispatch/__init__.py also pushes `repo_gate` (:526), `gh_rate_limited`, `stale_artifact`, `pr_state_error`, `reap_error`, `done_reconcile_error`, `mcp_init_error`; :529-547 `unknown_repo` is any `can_dispatch` refusal other than a unit mismatch, "kept for dashboards"; fr-vk/src/fr_vk/runner.py:62-63 maps backend_error/preflight to mcp_error/project_id_missing. Correction (858fa8213): "the common ones are" the five, and `unknown_repo` means the runner refused the item, usually because of its repo.

<!-- fr:journal kind=discovery scope=plan id=p4-acc-dispatch-label-lifecycle created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-dispatch-label-lifecycle · discovery · accuracy: fr-dispatch.md's label lifecycle omitted fr:blocked and manual-phase closing (corrected) (phase 4)

Claim: fr-dispatch.md:71-73 lifecycle `fr:ready` / `fr:in-progress` / `fr:pr-ready` / closed on completion plus merged PR. Code: packages/fr/src/fr/render.py:86-87 (`blocked` when dependencies are not satisfied), item_state.py:12 (`blocked -> fr:blocked`), render.py:217-218 (a `manual` phase is complete on `completion.at` and `completion.note`, no PR). Correction (858fa8213): adds `fr:blocked` while a dependency is incomplete, and a `[manual]` phase closing once its completion records a time and a note, with no PR.

<!-- fr:journal kind=discovery scope=plan id=p4-acc-unverified-left created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-acc-unverified-left · discovery · accuracy: phase 4 unverified claims left as written; none refuted (phase 4)

Not wrong per the reviews and not quickly verifiable, so the text stays: fr-acceptance.md per-forge Pages visibility read (templates match); fr-audit.md "context carry dominates, turns are the cost unit" (a claim about data, not code); fr-brainstorming-and-plan.md quiet placement "nothing lands on the feature branch" (commit target not traced); fr-debugging.md the push/pr ask refuse-once flow (settings keys confirmed, settings/model.py; the flow is the skill's, SKILL.md). Refuted: none, all 12 wrong-or-stale items held against the code. fr-audit, fr-debugging and fr-devops-gate had no wrong-or-stale finding, so their baseline is the merge base 63764b87921b4f741414cff4def0d5ee205547c9.

<!-- fr:journal kind=discovery scope=plan id=p4-ws-fr-acceptance created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-ws-fr-acceptance · discovery · plain-language rewrite: docs/explainers/fr-acceptance.md (phase 4)

Baseline: cce064d240b97cdca4d69ec4dcf4279eca914e51. Sentences/avg 106 / 16.3 -> 142 / 12.5. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 25 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. Headings became questions (rule 9): "Overview: claims, not tests" -> "What does the matrix record?", "The honesty scale" -> "How honest is each status?", "Changing a row another feature merged" -> "How do you change a row another feature merged?", "Backfilling a repo that has no matrix" -> "How do you backfill a repo that has no matrix?", "Rows born from specs, and rows added mid-flight" -> "Where do rows come from?", "Live verification, and walks" -> "What if only a live run can prove a claim?", "Reports and the gate" -> "Where do the reports go?", "Limits" -> "What can the matrix not do?", "Where to go next" -> "Where do you go next?". The backfill list keeps its baseline layout byte for byte (3-space fence); its pre-existing render break is finding p4-acceptance-backfill-render. No inbound anchor links (git grep '<page>.md#' finds none for any phase-4 page). Built site: no raw list marker introduced (HTML scan of <p> at the merge base and at HEAD).

<!-- fr:journal kind=discovery scope=plan id=p4-ws-fr-audit created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-ws-fr-audit · discovery · plain-language rewrite: docs/explainers/fr-audit.md (phase 4)

Baseline: 63764b87921b4f741414cff4def0d5ee205547c9 (merge base; no corrections). Sentences/avg 65 / 13.5 -> 85 / 10.8. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 10 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. ISO spelled out at first use. Headings: "Overview: the numbers are not yours to compute" -> "Why not compute the numbers yourself?", "The commands" -> "Which commands are there?", "Reading the split" -> "How do you read the split?", "The pages" -> "How do you build the pages?", "Red flags" -> "What are the red flags?", "Limits" -> "What can it not do?", "Where to go next" -> "Where do you go next?". The compare output became a list, every column kept. No inbound anchor links (git grep '<page>.md#' finds none for any phase-4 page). Built site: no raw list marker introduced (HTML scan of <p> at the merge base and at HEAD).

<!-- fr:journal kind=discovery scope=plan id=p4-ws-fr-brainstorming-and-plan created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-ws-fr-brainstorming-and-plan · discovery · plain-language rewrite: docs/explainers/fr-brainstorming-and-plan.md (phase 4)

Baseline: b54dd8b786a3d58373b0477463220f2e4521ee4e. Sentences/avg 102 / 13.3 -> 126 / 10.9. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 10 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. Headings: "Overview: why the idea gets written down twice" -> "Why write the idea down twice?", "fr-brainstorming: design where the work will happen" -> "What does fr-brainstorming add?", "fr-plan: a folder of facts" -> "What is in an fr-plan folder?", "fr-execute: one phase, then stop" -> "How does fr-execute run one phase?", "Limits" -> "What do the skills not do?", "Where to go next" -> "Where do you go next?". No inbound anchor links (git grep '<page>.md#' finds none for any phase-4 page). Built site: no raw list marker introduced (HTML scan of <p> at the merge base and at HEAD).

<!-- fr:journal kind=discovery scope=plan id=p4-ws-fr-debugging created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-ws-fr-debugging · discovery · plain-language rewrite: docs/explainers/fr-debugging.md (phase 4)

Baseline: 63764b87921b4f741414cff4def0d5ee205547c9 (merge base; no corrections). Sentences/avg 73 / 13.4 -> 92 / 11.1. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 14 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. `attempt` -> "before it tries a fourth". Headings: "Overview: why \"just try something\" is the expensive path" -> "Why is \"just try something\" the expensive path?", "The hard gate: isolation before anything" -> "Why must isolation come before anything?", "Autonomous, with two hard stops" -> "When does it stop and ask you?", "The debug journal" -> "What goes in the debug journal?", "Delivering the fix" -> "How does it deliver the fix?", "Limits" -> "What can it not do?", "Where to go next" -> "Where do you go next?". The reuse-a-workspace and mode=stealth conditions stay conditions. No inbound anchor links (git grep '<page>.md#' finds none for any phase-4 page). Built site: no raw list marker introduced (HTML scan of <p> at the merge base and at HEAD).

<!-- fr:journal kind=discovery scope=plan id=p4-ws-fr-devops-gate created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-ws-fr-devops-gate · discovery · plain-language rewrite: docs/explainers/fr-devops-gate.md (phase 4)

Baseline: 63764b87921b4f741414cff4def0d5ee205547c9 (merge base; no corrections). Sentences/avg 75 / 13.4 -> 88 / 11.8. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 16 WARN -> 0 FAIL, 1 WARN, no preserve hit. Kept: `OPEN` (:95, abbreviations) is the literal op state `fr ops status` prints (packages/fr/src/fr/ops/engine.py:36 State = DONE|OPEN|N/A|UNVERIFIABLE|CANNOT-VERIFY|ESCALATE), not an abbreviation; the page keeps all state names literal. "make an operation safe" -> "make an op safe" (the page's term). Headings: "Overview: why a delivered PR can still be unfinished" -> "Why can a delivered PR still have work left?", "The eight stages" -> "What are the eight stages?", "Trust: probes are code from the repo" -> "Why must you trust the probes?", "Reading what the stage tells you" -> "How do you read what the stage tells you?", "Attest, or write a check?" -> "Should you attest, or write a check?", "The Test Plan steps and the tester hand-off" -> "What happens to the Test Plan steps?", "What the stage never does" -> "What does the stage never do?", "Limits" -> "What can it not do?", "Where to go next" -> "Where do you go next?". Stage 2's three merge conditions stay in one list. No inbound anchor links (git grep '<page>.md#' finds none for any phase-4 page). Built site: no raw list marker introduced (HTML scan of <p> at the merge base and at HEAD).

<!-- fr:journal kind=discovery scope=plan id=p4-ws-fr-dispatch created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-ws-fr-dispatch · discovery · plain-language rewrite: docs/explainers/fr-dispatch.md (phase 4)

Baseline: 858fa8213c531c7e0593319fae9b963098e7230b. Sentences/avg 82 / 13.6 -> 102 / 11.2. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 9 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. The label lifecycle and the usual faults became bullet lists, every item kept. Headings: "Overview: the plan stays the source of truth" -> "Why does the plan stay the source of truth?", "Tracking versus queueing" -> "How does tracking differ from queueing?", "Before you dispatch" -> "What do you check before you dispatch?" (the worked example's cross-reference, (see "Before you dispatch" below), now quotes the new heading), "When it refuses" -> "What do the exit codes mean?", "fr-runner: when a queued phase sits still" -> "What if a queued phase sits still? (fr-runner)", "Other runners" -> "Which other runners are there?", "Limits" -> "What does dispatch not do?", "Where to go next" -> "Where do you go next?". No inbound anchor links (git grep '<page>.md#' finds none for any phase-4 page). Built site: no raw list marker introduced (HTML scan of <p> at the merge base and at HEAD).

<!-- fr:journal kind=discovery scope=plan id=p4-ws-totals created=2026-11-14T00:00:20+00:00 phase=4 -->
### p4-ws-totals · discovery · phase 4 writing-standard totals: 0 FAIL -> 0, 84 WARN -> 1 over the 6 explainers (phase 4)

Measured on the accuracy-corrected baselines (per-page sha in p4-ws-*): 0 FAIL, 84 WARN -> 0 FAIL, 1 WARN (fr-devops-gate `OPEN`, kept with its reason). The plain-language standard had no FAIL on these pages before the rewrite (every average was under 20), so the RED step showed warnings only: 24 long sentences (max 67 words), the passives and 5 over-long paragraphs. Wording tripwires (test_tripwire_fr_goal_question_rounds, test_hermes_docs, test_build_site, test_writing_standards_docs, test_tripwire_explainers_fresh): 483 passed; `fr docs check`: 32 pages current. Fact-keeper reviews are owed in review-phase against `git show <sha>:<page>`.

<!-- fr:journal kind=finding scope=plan id=p4-skill-acceptance-verify created=2026-11-14T00:00:20+00:00 phase=4 state=open review_scope=out -->
### p4-skill-acceptance-verify · finding [open] (reviewer: out of scope) · fr-acceptance SKILL.md:116 says a --verify row keeps nagging in fr acceptance status whatever its status, under Post-merge owed (phase 4)

plugins/super-fr/skills/fr-acceptance/SKILL.md:116 makes the claim corrected on the page (p4-acc-acceptance-verify-listing): `open_rows` (acceptance/check.py:109-122) lists only debt or contested rows, and a pre-merge strategy row goes under `## Pre-merge verification owed` (record/pr_body.py:1135-1138). A skill change, outside this docs feature.

<!-- fr:journal kind=finding scope=plan id=p4-plan-rework-help created=2026-11-14T00:00:20+00:00 phase=4 state=open review_scope=out -->
### p4-plan-rework-help · finding [open] (reviewer: out of scope) · fr plan rework help says the parent is "(Complete + archived)"; rework_create accepts a live or incomplete parent (phase 4)

packages/fr/src/fr/commands/plan_cmd.py:365 help "Path to parent plan folder (Complete + archived)." vs plan_ops.py:801-803,860-874 (live plans dir allowed, no completeness check). Either the help or the check is wrong; a code change, outside this docs feature.

<!-- fr:journal kind=finding scope=plan id=p4-acceptance-backfill-render created=2026-11-14T00:00:20+00:00 phase=4 state=open review_scope=out -->
### p4-acceptance-backfill-render · finding [open] (reviewer: out of scope) · fr-acceptance.md backfill list already renders broken at the merge base: step 4 merges into step 3's paragraph (phase 4)

docs/explainers/fr-acceptance.md "How do you backfill...": the paragraph after step 3's fenced example is followed directly by "4. Run ..." with no blank line, so Python-Markdown folds steps 4 and 5 into that paragraph as raw "4. "/"5. " text (built-site <p> scan, same at the merge base 63764b879 and at HEAD). Adding the blank line fixes the render but the checker then reports numerals 4 and 5 as disappeared (`preserve`), so it cannot land in a language-only rewrite. Same class as p3-r8.

<!-- fr:journal kind=review scope=plan id=review-p4 created=2026-11-14T00:13:26+00:00 phase=4 -->
### review-p4 · review · phase 4 review: 3 in-scope findings, all fixed; fact-keepers: 0 lost, 1 meaning shift fixed (phase 4)

Code reviewer (separate context, read-only) checked the accuracy commits cce064d24, b54dd8b78, 858fa8213 and 5be371991 against the cited code (all true), the plain-language rewrite with per-page --preserve-from, meaning drift, inbound links, and built the site at HEAD and the merge base (no new raw list markers, tables and figures unchanged). Six blind fact-keepers, one per explainer, given only baseline and rewrite. Fixes in 5f7745866, a97de88c5, 5b2a89da9. CI went red on 5b2a89d from a date-bound test unrelated to the docs (p4-gh1369-clock), fixed in bd2924af3.

<!-- fr:journal kind=discovery scope=plan id=p4-fact-keeper created=2026-11-14T00:13:26+00:00 phase=4 -->
### p4-fact-keeper · discovery · Fact-keeper results per page (R8): page | counts | resolution (phase 4)

docs/explainers/fr-audit.md | kept 55, changed 1, lost 0, added 1 | 'before the figures were recorded' -> 'before fr recorded the figures': accepted, fr writes the usage file (fr/usage/capture.py); added = ISO acronym expansion
docs/explainers/fr-dispatch.md | kept 56, changed 0, lost 0, added 0
docs/explainers/fr-debugging.md | kept 41, changed 0, lost 0, added 0
docs/explainers/fr-devops-gate.md | kept 66, changed 0, lost 0, added 0
docs/explainers/fr-brainstorming-and-plan.md | kept 61, changed 0, lost 0, added 0
docs/explainers/fr-acceptance.md | kept 75, changed 1, lost 0, added 0 | revision 'written against' -> 'that it amends' is ambiguous about the base revision: fix to 'the revision of the row that the amendment was written against'

<!-- fr:journal kind=discovery scope=plan id=p4-ws-acceptance-passive created=2026-11-14T00:13:26+00:00 phase=4 -->
### p4-ws-acceptance-passive · discovery · Kept warning: passive "was written" in fr-acceptance.md:115 (phase 4)

Restoring p4-r2 brings back the passive "the row it was written against". The base-revision meaning needs the writing-time reference, and the active alternatives ("the row the author wrote it against") name an actor the fact does not have. Kept as a warning, not a fail.

<!-- fr:journal kind=finding scope=plan id=p4-r1 created=2026-11-14T00:13:26+00:00 phase=4 state=open review_scope=in -->
### p4-r1 · finding [open] (reviewer: in scope) · fr-debugging.md: "fr derives the body" gave fr the skill's job (phase 4)

Raised by the phase 4 reviewer.

<!-- fr:journal kind=finding scope=plan id=p4-r2 created=2026-11-14T00:13:26+00:00 phase=4 state=open review_scope=in -->
### p4-r2 · finding [open] (reviewer: in scope) · fr-acceptance.md: amendment revision lost its written-against base (phase 4)

Raised by the phase 4 reviewer and the fr-acceptance fact-keeper.

<!-- fr:journal kind=finding scope=plan id=p4-r3 created=2026-11-14T00:13:26+00:00 phase=4 state=open review_scope=in -->
### p4-r3 · finding [open] (reviewer: in scope) · fr-dispatch.md: "Commit and push it" points across a paragraph break (phase 4)

Raised by the phase 4 reviewer.

<!-- fr:journal kind=finding scope=plan id=p4-gh1369-clock created=2026-11-14T00:13:26+00:00 phase=4 state=open review_scope=out -->
### p4-gh1369-clock · finding [open] (reviewer: out of scope) · test_gh1369_a_manifest_pr_resolves_an_ambiguous_key_fr_debt_holds seeds a fixed 2026-10-30 date (phase 4)

Past fr debt's stale_days (14) from 2026-11-14 the plan reads as stale and the entry defaults to review; every branch and main fail shard 5. Not caused by this change; fixed here anyway (test-only) because it blocks this PR's gate.

<!-- fr:journal kind=finding scope=plan id=p4-r1-resolved created=2026-11-14T00:13:26+00:00 phase=4 state=fixed resolves=p4-r1 -->
### p4-r1-resolved · finding [fixed] · resolves p4-r1: fr-debugging.md: "fr derives the body" gave fr the skill's job (phase 4)

5f7745866

<!-- fr:journal kind=finding scope=plan id=p4-r2-resolved created=2026-11-14T00:13:26+00:00 phase=4 state=fixed resolves=p4-r2 -->
### p4-r2-resolved · finding [fixed] · resolves p4-r2: fr-acceptance.md: amendment revision lost its written-against base (phase 4)

a97de88c5

<!-- fr:journal kind=finding scope=plan id=p4-r3-resolved created=2026-11-14T00:13:26+00:00 phase=4 state=fixed resolves=p4-r3 -->
### p4-r3-resolved · finding [fixed] · resolves p4-r3: fr-dispatch.md: "Commit and push it" points across a paragraph break (phase 4)

5b2a89da9

<!-- fr:journal kind=finding scope=plan id=p4-gh1369-clock-resolved created=2026-11-14T00:13:26+00:00 phase=4 state=fixed resolves=p4-gh1369-clock -->
### p4-gh1369-clock-resolved · finding [fixed] · resolves p4-gh1369-clock: test_gh1369_a_manifest_pr_resolves_an_ambiguous_key_fr_debt_holds seeds a fixed 2026-10-30 date (phase 4)

bd2924af3: the fixture seeds its commit one day before now.

<!-- fr:journal kind=finding scope=plan id=p4-skill-acceptance-verify-resolved created=2026-11-14T00:13:26+00:00 phase=4 state=open resolves=p4-skill-acceptance-verify out_of_scope=true -->
### p4-skill-acceptance-verify-resolved · finding [out-of-scope] · resolves p4-skill-acceptance-verify: fr-acceptance SKILL.md:116 says a --verify row keeps nagging in fr acceptance status whatever its status, under Post-merge owed (phase 4)

A stale claim in plugins/super-fr/skills/fr-acceptance/SKILL.md, not caused by a docs rewrite; to be filed at deliver.

<!-- fr:journal kind=finding scope=plan id=p4-plan-rework-help-resolved created=2026-11-14T00:13:26+00:00 phase=4 state=open resolves=p4-plan-rework-help out_of_scope=true -->
### p4-plan-rework-help-resolved · finding [out-of-scope] · resolves p4-plan-rework-help: fr plan rework help says the parent is "(Complete + archived)"; rework_create accepts a live or incomplete parent (phase 4)

fr plan rework CLI help text (plan_cmd.py:365), not caused by this change; the page states the code behaviour; to be filed at deliver.

<!-- fr:journal kind=finding scope=plan id=p4-acceptance-backfill-render-resolved created=2026-11-14T00:13:26+00:00 phase=4 state=open resolves=p4-acceptance-backfill-render out_of_scope=true -->
### p4-acceptance-backfill-render-resolved · finding [out-of-scope] · resolves p4-acceptance-backfill-render: fr-acceptance.md backfill list already renders broken at the merge base: step 4 merges into step 3's paragraph (phase 4)

Pre-existing at the merge base (same class as p3-r8); fixing it moves numerals the preserve check compares; to be filed at deliver.

<!-- fr:journal kind=discovery scope=plan id=p5-acc-init-scaffold-commit created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-acc-init-scaffold-commit · discovery · accuracy: fr-init.md said scaffold always commits the profile (corrected) (phase 5)

Claim: fr-init.md:50-51 "commits both" and :97-98 "Scaffold already committed the profile". Code: packages/fr/src/fr/isolation/scaffold.py:666-673 (a git-ignored `.devcontainer`: warns, writes, does not commit) and :673-674, :695-711 (`quiet_leaves_uncommitted`: under the quiet placement fr writes the files and makes no commit on a product branch, telling the operator to commit). Correction (20b266de1): the worked example notes the quiet placement leaves the commit to you; the hand-back step names both cases. Stealth still refuses before writing, as the page said.

<!-- fr:journal kind=discovery scope=plan id=p5-acc-isolation-switch-spelling created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-acc-isolation-switch-spelling · discovery · accuracy: fr-isolation.md said a commented placement line counts as quiet (corrected) (phase 5)

Claim: fr-isolation.md:133-136 "a switch the hook cannot read positively as `placement: repo` (quoted, commented, indented, anything else) counts as quiet". Code: plugins/super-fr/hooks/lib/fr-isolation-decision.sh:361-377 (`_fr_switch_enabled`) skips a line whose trimmed form starts with `#`; no live placement line returns 1 (repo); one live line exactly `placement: repo` is repo; any other live spelling (quoted, trailing comment, indented, flow, doubled) returns 0 (quiet). Correction (3e48a4c5f): a commented-out line is skipped, no live line means repo, any other live spelling, including one with a trailing comment, counts as quiet.

<!-- fr:journal kind=discovery scope=plan id=p5-acc-progress-status-yes created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-acc-progress-status-yes · discovery · accuracy: fr-progress.md said fr status previews unless you pass --yes (corrected) (phase 5)

Claim: fr-progress.md:86 "`status`, `repair` and `migrate` preview unless you pass `--yes`". Code: packages/fr/src/fr/commands/status_cmd.py:1-7 (read-only, "no mutation vocabulary and no `--yes`"); repair_cmd.py:54 and migrate_cmd.py:29 take `--yes`. Correction (16ce3f6e4): `status` only reads and takes no `--yes`; `repair` and `migrate` preview unless you pass `--yes`.

<!-- fr:journal kind=discovery scope=plan id=p5-acc-wave-debug-skill created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-acc-wave-debug-skill · discovery · accuracy: fr-wave-driver.md and fr-triage.md tied fr-debugging to defects / said every batch is an fr-goal run (corrected) (phase 5)

Claim: fr-wave-driver.md:23 "(a batch of defects runs fr-debugging instead)"; fr-triage.md:138 "a group of judged issues delivered as one fr-goal run". Code: packages/fr/src/fr/triage/model.py:1101 (`skill: BatchSkill = "goal"`), batch_dispatch.py:152-153 (`/fr-debugging` only when `batch.skill == "debug"`), the `--skill goal|debug` flag of `batch create|edit`. Nothing in the engine reads the issues' kind to choose. Correction: fr-wave-driver (9c5471bb5) and fr-triage (da33c2035): a batch created or edited with `--skill debug` runs fr-debugging. The fr-triage claim was not in the accuracy review; found while verifying the wave-driver one.

<!-- fr:journal kind=discovery scope=plan id=p5-acc-wave-held-foreign created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-acc-wave-held-foreign · discovery · accuracy: fr-wave-driver.md said held batches and foreign PRs are named once (corrected) (phase 5)

Claim: fr-wave-driver.md:59-62 "They are named once, never merged". Code: packages/fr/src/fr/triage/batch_drive.py:1741-1753 appends a `held` action for a held batch on every pass; :1755-1764 reports a foreign PR only when `found.key not in snap.warned`. Correction (9c5471bb5): a PR that is not the batch's is named once and never merged; a batch another scope holds is reported as held on every pass and left alone.

<!-- fr:journal kind=discovery scope=plan id=p5-acc-wave-merge-train created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-acc-wave-merge-train · discovery · accuracy: fr-wave-driver.md said a pass merges only the head of the train (corrected) (phase 5)

Claim: fr-wave-driver.md:63-64 "walks a merge train in order ... and merges the head of it". Code: packages/fr/src/fr/triage/batch_drive.py:1604-1673 (`_walk_merge_train`) emits a `merge` action for every approved, green, unmoved member, steps over failing ones, and stops at a moved or pending head. Correction (9c5471bb5): it merges the head, then the next ready member in the same pass, and so on until one does not merge.

<!-- fr:journal kind=discovery scope=plan id=p5-acc-wave-red-recovery created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-acc-wave-red-recovery · discovery · accuracy: fr-wave-driver.md said a failing check is reported once per head (corrected) (phase 5)

Claim: fr-wave-driver.md:69-70 "A failing check is reported once per head". Code: packages/fr/src/fr/triage/batch_drive.py:887 (`RED_HANDBACKS_PER_DISPATCH = 2`), :893-934 (`red_decision`: skip if already handed back at this head; reupdate when fr's own update went stale against a moved base; needs_you after two delivered hand-backs; handback when the session is idle). Correction (9c5471bb5): failing checks are handed back to an idle batch session at most twice per dispatch, updating again first when the base moved past fr's own update; after that the PR shows under Needs you now.

<!-- fr:journal kind=discovery scope=plan id=p5-acc-wave-pass-order created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-acc-wave-pass-order · discovery · accuracy: fr-wave-driver.md placed the wave export after dispatch and gave no dedupe condition (corrected) (phase 5)

Claim: fr-wave-driver.md:84-86 step 5 "a finished wave's state can be exported, and when a wave finishes ... dedupe". Code: packages/fr/src/fr/triage/batch_drive.py:1958-1964 (3a idle reports, 3b export) run before 4. Dispatch (:1966); 5 closes sessions (:2018); 6 dedupe fires only for a wave in `snap.finished & snap.unfinished_waves` (:2034-2041). Correction (9c5471bb5): the export moved to the close-out step; dedupe prints when the driver sees a wave go from unfinished to finished.

<!-- fr:journal kind=discovery scope=plan id=p5-acc-unverified-left created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-acc-unverified-left · discovery · accuracy: phase 5 unverified claims left as written; none refuted (phase 5)

Not wrong per the reviews and not quickly verifiable, so the text stays: fr-exit-gates.md the gate-ledger figure content and "eight steps" for the DevOps stage (AGENTS.md says eight stages); fr-isolation.md "22+ orphaned containers" (history), the one-stale-workspace bound (design rationale), the profile's SSH identity and tokens; fr-progress.md the archive gate's per-kind evidence and acceptance rows untouched by fr archive; fr-triage.md the `causes:` link content and exit 2 for every verb on a bad entry; fr-wave-driver.md "keeps nothing of its own" (merge-stops.json and drive.lock exist), the herdr runner choice, the hand-back brief contents. Refuted: none; every wrong-or-stale item held against the code. fr-exit-gates had no correction, so its baseline is the merge base 63764b87921b4f741414cff4def0d5ee205547c9.

<!-- fr:journal kind=finding scope=plan id=p5-init-tool-help-markup created=2026-11-14T00:33:23+00:00 phase=5 state=open review_scope=out -->
### p5-init-tool-help-markup · finding [open] (reviewer: out of scope) · fr init scaffold --help prints `<tool>;` - Rich markup eats `[@<version>]` (phase 5)

packages/fr/src/fr/commands/init_cmd.py:33 help "(repeatable; <tool>[@<version>]; ...)" renders as "<tool>;" in `fr init scaffold --help`, because Rich treats `[@<version>]` as markup. The page's `<tool>@<version>` matches the code (scaffold.py:97-102). A CLI help fix (escape the brackets), outside this docs feature.

<!-- fr:journal kind=finding scope=plan id=p5-progress-skill-status-yes created=2026-11-14T00:33:23+00:00 phase=5 state=open review_scope=out -->
### p5-progress-skill-status-yes · finding [open] (reviewer: out of scope) · fr-progress SKILL.md lists fr status among the commands that preview until --yes (phase 5)

plugins/super-fr/skills/fr-progress/SKILL.md:29 "`fr status`/`fr repair`/`fr migrate v1-to-v2` preview by default, no `--yes`"; fr status takes no --yes at all (status_cmd.py:1-7). A skill wording fix, outside this docs feature.

<!-- fr:journal kind=finding scope=plan id=p5-triage-skill-schema created=2026-11-14T00:33:23+00:00 phase=5 state=open review_scope=out -->
### p5-triage-skill-schema · finding [open] (reviewer: out of scope) · fr-triage SKILL.md says a first run creates judgements with schema: 11; the engine writes 12 (phase 5)

plugins/super-fr/skills/fr-triage/SKILL.md:44 "a first run creates the file with `schema: 11`"; packages/fr/src/fr/triage/model.py:86 `JUDGEMENTS_SCHEMA: Literal[12] = 12`, and the same SKILL.md's example (:62) says `schema: 12`. A skill wording fix, outside this docs feature.

<!-- fr:journal kind=finding scope=plan id=p5-exit-gates-code-render created=2026-11-14T00:33:23+00:00 phase=5 state=open review_scope=out -->
### p5-exit-gates-code-render · finding [open] (reviewer: out of scope) · fr-exit-gates.md tester bullet's fenced example renders as inline code, at the merge base too (phase 5)

docs/explainers/fr-exit-gates.md "Who passes a gate?": the ```bash fence under the Tester bullet is indented 2 spaces, so Python-Markdown closes the list and renders the block as `<p><code>bash fr gate pass ...</code></p>` (built-site scan, identical at the merge base 63764b879 and at HEAD). Re-indenting the fence to 4 spaces fixes it but changes the fenced code the preserve check compares byte for byte, so it cannot land in a language-only rewrite. Same class as p3-r8 and p4-acceptance-backfill-render.

<!-- fr:journal kind=discovery scope=plan id=p5-ws-fr-exit-gates created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-ws-fr-exit-gates · discovery · plain-language rewrite: docs/explainers/fr-exit-gates.md (phase 5)

Baseline: 63764b87921b4f741414cff4def0d5ee205547c9 (merge base; no corrections; `git show <sha>:docs/explainers/fr-exit-gates.md`). Sentences/avg 61 / 14.8 -> 66 / 13.9. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 14 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. The unknown-state causes became a four-item list, every cause kept. Headings: "Overview: the work that cannot finish in the pull request" -> "What work cannot finish in the pull request?", "The six gates" -> "What are the six gates?", "Which gate a run gets" -> "Which gate does a run get?", "The labels are the ledger" -> "Why are the labels the ledger?", "How a gate is passed" -> "Who passes a gate?", "Release candidates while a gate waits" -> "What gets released while a gate waits?", "Old work, and the DevOps stage" -> "What about old work, and the DevOps stage?". No inbound anchor links (git grep '<page>.md#' finds none for any phase-5 page). Built site: no raw list marker, tables and the gate-ledger figure unchanged (HTML scan at the merge base and at HEAD); the tester example's pre-existing render break is p5-exit-gates-code-render.

<!-- fr:journal kind=discovery scope=plan id=p5-ws-fr-init created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-ws-fr-init · discovery · plain-language rewrite: docs/explainers/fr-init.md (phase 5)

Baseline: 20b266de168921d47029d69e4c48631e2246851a. Sentences/avg 63 / 13.5 -> 65 / 13.4. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 8 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. POM spelled out (Project Object Model). Headings: "Overview: the profile is the contract" -> "Why is the profile the contract?", "A worked example" -> "What does a worked example look like?", "What the skill does, in order" -> "What does the skill do, in order?", "Services: forge, CI, tracking" -> "Which services does the repo record?", "Limits" -> "What does fr-init not do?", "Where to go next" -> "Where do you go next?". The stealth refusal stays a refusal. Built site: no raw list marker introduced.

<!-- fr:journal kind=discovery scope=plan id=p5-ws-fr-isolation created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-ws-fr-isolation · discovery · plain-language rewrite: docs/explainers/fr-isolation.md (phase 5)

Baseline: 3e48a4c5f1fbe7ab8ffd422fba784f5e3788ed0d. Sentences/avg 89 / 18.3 -> 108 / 15.4. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 30 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. The fr-enabled paragraph split into four (switch reads, switch spelling, the bounded fr call, the structural exception's two shapes) with no pronoun across a break; the five-step staircase and the three escapes stay lists. Headings: "Overview: two boundaries and a bridge" -> "What are the two boundaries and the bridge?", "How it works: where the work lives, where it runs" -> "Where does the work live, and where does it run?", "Who creates worktrees" -> "Who creates worktrees?", "Enforcement: a staircase a faked marker can't climb" -> "Why can't a faked marker get past the gate?", "Tradeoffs: three scars, each a shipped bug" -> "Which three shipped bugs shaped the design?", "Try it: drive the boundary by hand" -> "How do you drive the boundary by hand?". "its copy kept" -> "keeps the preserved copy" (isolation/preserve.py:931-935: the checkout file stays, the preserved copy stays). test_build_site's fr-isolation route is unchanged. Built site: no raw list marker; both tables and the mermaid block unchanged.

<!-- fr:journal kind=discovery scope=plan id=p5-ws-fr-progress created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-ws-fr-progress · discovery · plain-language rewrite: docs/explainers/fr-progress.md (phase 5)

Baseline: 16ce3f6e429ac1e0d116be4b77a9aac3f25d946f. Sentences/avg 47 / 13.2 -> 51 / 12.8. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 7 WARN -> 0 FAIL, 1 WARN, no preserve hit. Kept: passive "once all its rows are implemented" (:119). The spec archive sweep (commands/archive_cmd.py:1039-1056, `spec_archive_sweep`) decides from its plan-table rows; an active form ("read implemented", "you implement") would either suggest a literal status value or name an actor the fact does not have. The four status buckets became a list. Headings: "Overview: nothing to sync" -> "Why is there nothing to sync?", "A worked example" -> "What does a worked example look like?", "The commands" -> "Which commands are there?", "Before you touch `docs/superpowers/` by hand" -> "What do you run before you touch `docs/superpowers/` by hand?", "Archiving finished work" -> "How do you archive finished work?", "Limits" -> "What can these commands not tell you?", "Where to go next" -> "Where do you go next?". Built site: no raw list marker introduced.

<!-- fr:journal kind=discovery scope=plan id=p5-ws-fr-triage created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-ws-fr-triage · discovery · plain-language rewrite: docs/explainers/fr-triage.md (phase 5)

Baseline: da33c2035b9424e7ace8d33abacec25b2e687b75. Sentences/avg 99 / 12.9 -> 102 / 12.9 (the RED figure was taken before the one-line accuracy fix, which changed no sentence count). Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 11 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. The origins window refusal names its actor as Collect (triage/origins.py:157-160). Headings: "Overview: judgement in a file, engine around it" -> "Why keep the judgement in a file, with an engine around it?", "A worked example" -> "What does a worked example look like?", "State: three files, three owners" -> "Which files hold the state, and who writes them?", "What `check` tells you" -> "What does `check` tell you?", "How to judge" -> "How do you judge?", "Batches and the driver" -> "What are batches and the driver?", "Limits" -> "What does triage not do?", "Where to go next" -> "Where do you go next?" ("fr-origins: where did the bugs come from?" was already a question). Built site: no raw list marker introduced.

<!-- fr:journal kind=discovery scope=plan id=p5-ws-fr-wave-driver created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-ws-fr-wave-driver · discovery · plain-language rewrite: docs/explainers/fr-wave-driver.md (phase 5)

Baseline: 9c5471bb5b47e187ad8797f0d3a828ad2dd3f429. Sentences/avg 86 / 17.8 -> 110 / 14.2. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 0 FAIL, 39 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. Steps 2 and 3 of the pass each got a second paragraph, indented 4 spaces inside the item (built HTML: one <ol>, both <p> inside the <li>); the merge refusals became a five-item list; the --once exit codes their own paragraph. "The driver is built around the few moments that are yours" -> "We built the driver around ...". Headings: "Overview: why a loop and not a checklist" -> "Why a loop and not a checklist?", "Batches, waves and `after`" -> "What are batches, waves and `after`?", "What one pass does" -> "What does one pass do?", "The cap" -> "Why is there a cap?", "When it merges, and what it refuses" -> "When does it merge, and what does it refuse?", "No state, so it resumes" -> "Why can you stop it and start it again?", "Where you act" -> "Where do you act?", "Where it runs" -> "Where does it run?". Built site: no raw list marker, the wave-of-batches figure unchanged.

<!-- fr:journal kind=discovery scope=plan id=p5-ws-totals created=2026-11-14T00:33:23+00:00 phase=5 -->
### p5-ws-totals · discovery · phase 5 writing-standard totals: 0 FAIL -> 0, 109 WARN -> 1 over the 6 explainers (phase 5)

Measured on the accuracy-corrected baselines (per-page sha in p5-ws-*): 0 FAIL, 109 WARN -> 0 FAIL, 1 WARN (fr-progress `are implemented`, kept with its reason). No page failed the average before the rewrite (highest fr-isolation 18.3); the warnings were passives, 26 long sentences (max 60 words) and 5 over-long paragraphs. Wording tripwires (test_tripwire_fr_goal_question_rounds, test_hermes_docs, test_build_site, test_writing_standards_docs, test_tripwire_explainers_fresh): 483 passed; `fr docs check`: 32 pages current. Site built at HEAD and at the merge base: no new raw list marker, tables, figures and code blocks unchanged. Fact-keeper reviews are owed in review-phase against `git show <sha>:<page>`.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t1 created=2026-11-14T00:33:23+00:00 phase=5 -->
### no-refactor-p5-t1 · discovery · no-refactor-because P5.T1 (phase 5)

language-only rewrite; the refactor step is the wording tripwires and fr docs check, which passed with nothing to fix

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p5-t2 created=2026-11-14T00:33:23+00:00 phase=5 -->
### no-refactor-p5-t2 · discovery · no-refactor-because P5.T2 (phase 5)

language-only rewrite; the refactor step is the wording tripwires and fr docs check, which passed with nothing to fix

<!-- fr:journal kind=review scope=plan id=review-p5 created=2026-11-14T00:47:42+00:00 phase=5 -->
### review-p5 · review · phase 5 review: 6 findings (5 in, 1 out), all fixed; fact-keepers: 0 lost, 0 changed facts (phase 5)

Code reviewer (separate context, read-only) checked the accuracy commits 20b266de1, 3e48a4c5f, 16ce3f6e4, 9c5471bb5 and da33c2035 against the cited code (all true), the plain-language rewrite with per-page --preserve-from, meaning drift, inbound links, and built the site at HEAD and the merge base (no new raw list markers; tables and figures unchanged). Six blind fact-keepers, one per explainer. Fixes in d5cbd8c90, c2a0f6884, 694431383, c98992699, c2c26d6e3; ci-ok green on c2c26d6. The one kept warning (fr-progress passive) went away with the p5-r6 content correction.

<!-- fr:journal kind=discovery scope=plan id=p5-fact-keeper created=2026-11-14T00:47:42+00:00 phase=5 -->
### p5-fact-keeper · discovery · Fact-keeper results per page (R8): page | counts | resolution (phase 5)

docs/explainers/fr-progress.md | kept 44, changed 0, lost 0, added 0
docs/explainers/fr-init.md | kept 51, changed 1, lost 0, added 0 | 'how work is isolated' -> 'how fr isolates work': accepted, wording only and true (fr isolation)
docs/explainers/fr-exit-gates.md | kept 48, changed 0, lost 0, added 0
docs/explainers/fr-triage.md | kept 64, changed 0, lost 0, added 0
docs/explainers/fr-isolation.md | kept 74, changed 0, lost 0, added 0
docs/explainers/fr-wave-driver.md | kept 81, changed 0, lost 0, added 2 | 'the label is removed' -> 'fr removes the label': verified true, fr/triage/approval.py settle_approvals voids a moved head's approval by removing approved-fr then recording the void; 'We built the driver around...' adds the authors' voice only, no claim

<!-- fr:journal kind=finding scope=plan id=p5-r1 created=2026-11-14T00:47:42+00:00 phase=5 state=open review_scope=in -->
### p5-r1 · finding [open] (reviewer: in scope) · fr-triage.md: "Nobody commits the state" widened the subject and is false (phase 5)

Raised by the phase 5 reviewer.

<!-- fr:journal kind=finding scope=plan id=p5-r2 created=2026-11-14T00:47:42+00:00 phase=5 state=open review_scope=in -->
### p5-r2 · finding [open] (reviewer: in scope) · fr-isolation.md: "stops there" pointed across a new paragraph break (phase 5)

Raised by the phase 5 reviewer.

<!-- fr:journal kind=finding scope=plan id=p5-r3 created=2026-11-14T00:47:42+00:00 phase=5 state=open review_scope=in -->
### p5-r3 · finding [open] (reviewer: in scope) · fr-init.md: the --host confirmation moved from the skill to the operator (phase 5)

Raised by the phase 5 reviewer.

<!-- fr:journal kind=finding scope=plan id=p5-r4 created=2026-11-14T00:47:42+00:00 phase=5 state=open review_scope=in -->
### p5-r4 · finding [open] (reviewer: in scope) · fr-wave-driver.md: red recovery omitted the gone-session path to Needs you now (phase 5)

Raised by the phase 5 reviewer.

<!-- fr:journal kind=finding scope=plan id=p5-r5 created=2026-11-14T00:47:42+00:00 phase=5 state=open review_scope=in -->
### p5-r5 · finding [open] (reviewer: in scope) · fr-triage.md: "fr-goal is the run a batch becomes" contradicted the debug-batch line (phase 5)

Raised by the phase 5 reviewer.

<!-- fr:journal kind=finding scope=plan id=p5-r6 created=2026-11-14T00:47:42+00:00 phase=5 state=open review_scope=out -->
### p5-r6 · finding [open] (reviewer: out of scope) · fr-progress.md: "its rows are implemented" read as acceptance rows (phase 5)

Raised by the phase 5 reviewer; present at the merge base.

<!-- fr:journal kind=finding scope=plan id=p5-r1-resolved created=2026-11-14T00:47:42+00:00 phase=5 state=fixed resolves=p5-r1 -->
### p5-r1-resolved · finding [fixed] · resolves p5-r1: fr-triage.md: "Nobody commits the state" widened the subject and is false (phase 5)

d5cbd8c90

<!-- fr:journal kind=finding scope=plan id=p5-r2-resolved created=2026-11-14T00:47:42+00:00 phase=5 state=fixed resolves=p5-r2 -->
### p5-r2-resolved · finding [fixed] · resolves p5-r2: fr-isolation.md: "stops there" pointed across a new paragraph break (phase 5)

c2a0f6884

<!-- fr:journal kind=finding scope=plan id=p5-r3-resolved created=2026-11-14T00:47:42+00:00 phase=5 state=fixed resolves=p5-r3 -->
### p5-r3-resolved · finding [fixed] · resolves p5-r3: fr-init.md: the --host confirmation moved from the skill to the operator (phase 5)

694431383

<!-- fr:journal kind=finding scope=plan id=p5-r4-resolved created=2026-11-14T00:47:42+00:00 phase=5 state=fixed resolves=p5-r4 -->
### p5-r4-resolved · finding [fixed] · resolves p5-r4: fr-wave-driver.md: red recovery omitted the gone-session path to Needs you now (phase 5)

c98992699

<!-- fr:journal kind=finding scope=plan id=p5-r5-resolved created=2026-11-14T00:47:42+00:00 phase=5 state=fixed resolves=p5-r5 -->
### p5-r5-resolved · finding [fixed] · resolves p5-r5: fr-triage.md: "fr-goal is the run a batch becomes" contradicted the debug-batch line (phase 5)

d5cbd8c90

<!-- fr:journal kind=finding scope=plan id=p5-r6-resolved created=2026-11-14T00:47:42+00:00 phase=5 state=fixed resolves=p5-r6 -->
### p5-r6-resolved · finding [fixed] · resolves p5-r6: fr-progress.md: "its rows are implemented" read as acceptance rows (phase 5)

c2c26d6e3: content correction, every plan in the spec's Implementation Plans table archived (migrate.py:884-905).

<!-- fr:journal kind=finding scope=plan id=p5-init-tool-help-markup-resolved created=2026-11-14T00:47:42+00:00 phase=5 state=open resolves=p5-init-tool-help-markup out_of_scope=true -->
### p5-init-tool-help-markup-resolved · finding [out-of-scope] · resolves p5-init-tool-help-markup: fr init scaffold --help prints `<tool>;` - Rich markup eats `[@<version>]` (phase 5)

fr init scaffold --help Rich markup defect, not caused by this change; to be filed at deliver.

<!-- fr:journal kind=finding scope=plan id=p5-progress-skill-status-yes-resolved created=2026-11-14T00:47:42+00:00 phase=5 state=open resolves=p5-progress-skill-status-yes out_of_scope=true -->
### p5-progress-skill-status-yes-resolved · finding [out-of-scope] · resolves p5-progress-skill-status-yes: fr-progress SKILL.md lists fr status among the commands that preview until --yes (phase 5)

Stale claim in plugins/super-fr/skills/fr-progress/SKILL.md, not caused by this change; to be filed at deliver.

<!-- fr:journal kind=finding scope=plan id=p5-triage-skill-schema-resolved created=2026-11-14T00:47:42+00:00 phase=5 state=open resolves=p5-triage-skill-schema out_of_scope=true -->
### p5-triage-skill-schema-resolved · finding [out-of-scope] · resolves p5-triage-skill-schema: fr-triage SKILL.md says a first run creates judgements with schema: 11; the engine writes 12 (phase 5)

Stale schema number in plugins/super-fr/skills/fr-triage/SKILL.md, not caused by this change; to be filed at deliver.

<!-- fr:journal kind=finding scope=plan id=p5-exit-gates-code-render-resolved created=2026-11-14T00:47:42+00:00 phase=5 state=open resolves=p5-exit-gates-code-render out_of_scope=true -->
### p5-exit-gates-code-render-resolved · finding [out-of-scope] · resolves p5-exit-gates-code-render: fr-exit-gates.md tester bullet's fenced example renders as inline code, at the merge base too (phase 5)

Pre-existing at the merge base; re-indenting changes fenced bytes the preserve check compares; to be filed at deliver.

<!-- fr:journal kind=discovery scope=plan id=p6-acc-frgoal-ready created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-acc-frgoal-ready · discovery · accuracy: 01-fr-goal.md said fr-goal marks the PR ready once the checks pass (corrected) (phase 6)

Claim: 01-fr-goal.md:980-985 (§8 heading "Keep delivery in draft until the checks pass", "Only after the full test suite and plan checks pass does fr-goal mark it ready") and :1505 (Try it, item 7, "marks it ready once the checks pass"). Code: plugins/super-fr/skills/fr-goal/SKILL.md §8 ("never mark the PR ready — the ready transition is the operator's too", run by them once CI green, explicit review ok and no commits since all hold) and plugins/super-fr/workflows/fr-goal.yaml:15-16 ("the review ok and the ready transition are the operator's (#814)"). Correction (2eb18d5c0): the agent opens the draft and leaves it a draft; you mark it ready once CI is green, you gave an explicit review ok and nothing was committed since; heading now "Deliver a draft, and leave it a draft", item 7 "Marking it ready is yours".

<!-- fr:journal kind=discovery scope=plan id=p6-acc-frgoal-gate-claims created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-acc-frgoal-gate-claims · discovery · accuracy: 01-fr-goal.md OpenCode idle continuation and the unobserved gate default (corrected) (phase 6)

Claim 1: :541 OpenCode's idle continuation "has not yet been proved on a live session". Code: packages/fr/src/fr/harness/parity.yaml:211-224 (opencode `state: enforced`, live-verified 2026-10-23 on OpenCode 2.1.3). Correction: weaker than a refusal, recorded as such, proved on a live OpenCode session in October 2026 and declared enforced.
Claim 2: :642 "Only where fr cannot observe the session does the typed claim stand (`agent` unless stated)". Code: packages/fr/src/fr/commands/run_cmd.py:1447-1458 (R10: no default; exit 2 asking for `answered_by: operator|agent`). Correction: on an unobserved session the resolve refuses until the agent states who answered; there is no default, and the stated answer is marked unverified. Both in 2eb18d5c0.

<!-- fr:journal kind=discovery scope=plan id=p6-acc-frgoal-cost created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-acc-frgoal-cost · discovery · accuracy: 01-fr-goal.md said fr run status prints each attempt's cost and estimate (corrected) (phase 6)

Claim: :452-469 "Each attempt also carries its own cost, printed by fr run status directly beneath the holder", with an estimate and a measurement on the same line. Code: packages/fr/src/fr/commands/run_cmd.py:5904-5912 (status docstring: cost is `fr run cost`'s, from the usage file; the cost column went with run 7), packages/fr/src/fr/run/model.py:80-83 (estimate/measured moved to the usage file; the v5/v6 shape frozen as `fr.run.legacy.AttemptV6`), packages/fr/src/fr/run/cost.py:1-6 (read from the usage file, never the cursor; no estimate column). Correction (2eb18d5c0): status shows holders and since when, no cost; `fr run cost` prints it from the usage file; per-attempt estimate/measurement survive only in frozen older cursors. The estimate-vs-measurement paragraph went with it (fr run cost shows no estimate). The "not observable from here" refusal stays: run_cmd.py:4855.

<!-- fr:journal kind=discovery scope=plan id=p6-acc-frgoal-mismatch-family created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-acc-frgoal-mismatch-family · discovery · accuracy: 01-fr-goal.md said ≠ marks two different models (corrected to model family) (phase 6)

Claim: :498 "marked ≠ when the two are different models". Code: packages/fr/src/fr/run/cost.py:296-299 (`mismatch = model_family(ran) != model_family(bound)`, never for an unobserved ran) and :350 (ran_text docstring). Correction (2eb18d5c0): marked ≠ when the model that ran is from a different family than the bound one.

<!-- fr:journal kind=discovery scope=plan id=p6-acc-frgoal-shape-facts created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-acc-frgoal-shape-facts · discovery · accuracy: 01-fr-goal.md brainstorm emits, plan-review as the one command step, the matrix path (corrected) (phase 6)

Claim 1: :172 YAML excerpt `emits: [spec, journal:spec]`. Code: plugins/super-fr/workflows/fr-goal.yaml:65 `emits: [spec, journal:spec, acceptance]`. Corrected inside the fence in the accuracy commit, so the rewrite's preserve check against 2eb18d5c0 stays clean.
Claim 2: :739 "Reviewing that plan is the shape's one command step". Code: fr-goal.yaml:97-98 (plan-review, kind: cli) and :186-187 (journal-check, kind: cli). Correction: one of the shape's two command steps; the other is journal-check (step 7).
Claim 3: :1167 Configuration table "Acceptance matrix | docs/acceptance/matrix.yaml". Code: the retired matrix kind (fr.artifacts.matrix_fragments); rows live in docs/acceptance/features/<spec-slug>.yaml, folded by fr.acceptance.fold. Correction: one fragment per feature, folded into the effective matrix, never stored. All in 2eb18d5c0.

<!-- fr:journal kind=discovery scope=plan id=p6-acc-frgoal-citations created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-acc-frgoal-citations · discovery · accuracy: 01-fr-goal.md stale spec paths and line citations (corrected, sections cited) (phase 6)

:253 and :271 cited docs/superpowers/specs/ for 2026-08-14-workflow-shapes-and-workitem-dispatch-design.md and 2026-09-29-fr-goal-light-path-design.md; both are under docs/superpowers/implemented/specs/ now. :764 cited plan_ops.py:1135-1311; self_review is at packages/fr/src/fr/plan_ops.py:1356, now cited by function name. SKILL.md line ranges were stale (:42-53, :62-70, :75-88, :90-94, :96-97, :99-111, :55-60, fr-brainstorming :67-79); each now cites the section (fr-goal §1, §3, §5, §6, §7, §8, §1 and §2; fr-brainstorming §3 "Acceptance rows"), verified against the headings at SKILL.md:56/66/87/102/106/112 and fr-brainstorming SKILL.md:99. Correction in 2eb18d5c0. Not corrected (not flagged, still in range): SKILL.md:14-27, :1-10, fr-brainstorming :23-53, fr-isolation :55-71, fr-plan and fr-execute ranges.

<!-- fr:journal kind=discovery scope=plan id=p6-acc-whyfr created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-acc-whyfr · discovery · accuracy: why-fr.md review, finding, credential, profile, manual-phase and acceptance claims (corrected) (phase 6)

All in 06f0c034f. (1) :65-66, :111 "the spec, the plan and every implementation slice face an independent review": fr-goal.yaml:97-99 plan-review is `kind: cli` (`fr plan self-review`), SKILL.md §4 "deterministic, exit code is the verdict" -> the spec and every slice get an independent adversarial review, the plan a deterministic self-review (on the light path the spec reviewer reviews it too). (2) :67-68, :113-114 "every finding is fixed", "no backlog": SKILL.md description and §2/§6 fix in-scope findings and file the rest out of scope -> every in-scope finding is fixed; one this change did not cause is filed as a tracked issue and listed in the PR. (3) :93-94 "the agent only ever holds the credentials that workspace was granted": fr-isolation SKILL.md:63-66 (the container sees only the profile's env-file, no SSH identity; all git-host I/O on the host) -> the commands the agent runs hold only the profile's credentials and no SSH identity; pushes and PRs run on your host. (4) :98-99 "the default workspace carries no tokens at all": fr-init SKILL.md:58-62, :115-118 (asks for no forge token by default; keep the default least-privileged) -> least-privileged by convention, fr-init asks for no forge token, credentials belong in a separate profile. (5) :75-78, :132-133 manual work "quarantined into the plan's final phase", the PR "never left half-integrated": fr-goal SKILL.md §3 (back-load by default; front-load when agentic work depends on it, spec+plan PR, pause) -> a manual phase, by default the last; first instead when agentic work depends on it. (6) :123-124 rows "presented for defense in the same question round": fr-brainstorming SKILL.md:106-110 ("Under fr-goal the presentation rides spec-review") -> born in the brainstorm record, defended one line each at spec review. (7) :51-53: fr-isolation SKILL.md:22 (host-worktree is the default in a Claude Code cloud session), fr-goal SKILL.md:22-23 (fr-init pause only with no devcontainer profile) -> cloud session added, the interview scoped to a missing container profile in the default mode.

<!-- fr:journal kind=discovery scope=plan id=p6-acc-unverified-left created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-acc-unverified-left · discovery · accuracy: phase 6 unverified claims left as written; none refuted (phase 6)

Not wrong per the reviews and not quickly verifiable, so the text stays: 01-fr-goal.md the historical token figures of the removed cost paragraph (gone with the correction), "roughly two seconds" for the idle guard, the quiet/stealth placement sections (spot-checked only), the 4.0.0 history; why-fr.md the honesty buckets (a paraphrase that omits `contested`) and the "four moments" framing. Refuted: none; every wrong-or-stale item held against the code.

<!-- fr:journal kind=discovery scope=plan id=p6-ws-01-fr-goal created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-ws-01-fr-goal · discovery · plain-language rewrite: docs/explainers/01-fr-goal.md (phase 6)

Baseline: 2eb18d5c000d4b9b11158091bd09ae7f7c59b374 (the accuracy commit; `git show <sha>:docs/explainers/01-fr-goal.md`). Sentences/avg 635 / 23.4 -> 1027 / 14.8. Checker (pin 3b0c7d0, `--default plain-language --preserve-from <baseline> --stats`): 1 FAIL (average 23.4 > 20), 332 WARN -> 0 FAIL, 6 WARN, no preserve hit. Kept: 6 `attempt` -> `try` (simple_words). "Attempt" is the cursor's own noun for one dispatch of a unit (fr run status lists a unit's attempts; fr.run.legacy.AttemptV6); "try" would break the link to what the tool prints. Lists made from inline series: the seven failure modes, the six fr run commands, the three spec-review conditions, the four verification strategies, the four loop moves, the four unaccounted kinds, the four proportionality items, the eight DevOps stages, the stealth resume outcomes; the settings list made loose (blank lines between items). Several sentences beginning with a lowercase "fr" were reworded, because the checker does not split a sentence there. Headings became questions (the numbered steps keep their number and command): Overview, When it triggers, Workflow, The pipeline is a manifest, The run keeps its place, Ending a turn, steps 1-9 and 7a, When one goal spans several repositories, Configuration, Repo settings, Quiet, Stealth, Merged status, Moving between placements, Try it yourself. No inbound anchor links (`git grep '01-fr-goal.md#'` finds only test_build_site's synthetic `#why`). Built site at HEAD and the merge base: tables (24 rows), 5 code blocks and the mermaid diagrams unchanged, no raw list marker in a <p>; list items 18 -> 64.

<!-- fr:journal kind=discovery scope=plan id=p6-ws-why-fr created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-ws-why-fr · discovery · elements-of-style rewrite: docs/explainers/why-fr.md (phase 6)

Baseline: 06f0c034f882acf1500c4e86d3de736ad832ba97 (the accuracy commit). Sentences/avg 96 / 14.3 -> 97 / 14.0. Checker (pin 3b0c7d0, `--default elements-of-style --preserve-from <baseline> --stats`): 0 FAIL, 25 WARN -> 0 FAIL, 0 WARN, no preserve hit. No warning kept. Essay voice, headings, section order, the mermaid flow, the seams table and the pinned round wording unchanged; the passives became actives with the actor the facts name (the agent pushes and opens the PR through fr; close-out tears workspaces down; review catches a bad plan). Built site: lists, table and code blocks unchanged.

<!-- fr:journal kind=discovery scope=plan id=p6-ws-totals created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-ws-totals · discovery · phase 6 writing-standard totals and the gate (phase 6)

01-fr-goal 1 FAIL / 332 WARN -> 0 / 6; why-fr 0 / 25 -> 0 / 0. `bash scripts/check-writing-standards.sh /home/user/blog-craft` over every page: exit 0 (ste group: 16 checked, 1 skipped; plain-language group incl. why-fr's own standard: 14 checked, 1 skipped; 32 warnings repo-wide, none a FAIL). Wording tripwires (test_tripwire_fr_goal_question_rounds, test_hermes_docs, test_build_site, test_writing_standards_docs, test_tripwire_explainers_fresh): 483 passed; `fr docs check`: 32 pages current. Fact-keeper reviews are owed in review-phase against `git show <sha>:<page>` (shas in p6-ws-*).

<!-- fr:journal kind=discovery scope=plan id=p6-ci-gate created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-ci-gate · discovery · CI: site-build runs scripts/check-writing-standards.sh .blog-craft after the build (R6) (phase 6)

42a19779c adds the step to .github/workflows/ci.yml's site-build job, after the build, reading the job's existing pinned .blog-craft checkout (no SHA named; pages.yml unchanged per spec §2). test_writing_standards_docs::test_site_build_checks_the_writing_standards_after_the_build pins it (RED before the step). No new workflow file, so ci-budget's watch list is unchanged (test_ci_budget passed). T3.S3's full local suite was replaced by `tests: ci` per the orchestrator's brief (slow container; test_acceptance_stale_base fails locally for an environmental git reason): ci-ok on the pushed head is the evidence.

<!-- fr:journal kind=discovery scope=plan id=p6-docs-accuracy-lens created=2026-11-14T01:39:55+00:00 phase=6 -->
### p6-docs-accuracy-lens · discovery · docs-accuracy lens and the rule's accuracy paragraph (R15, R16) (phase 6)

9f95bd675: .fr/lenses.yaml exactly as spec §3b (lens docs-accuracy; require it for docs/explainers/*.md, docs/*.md, docs/reference/*.md, the three .fr/docs.yaml page globs); `fr lenses check` exit 0, `fr lenses status` lists docs-accuracy required by the path rule (it matches pages this branch changed). .claude/rules/explainers-currency.md gains the accuracy paragraph (fr-goal runs review page edits under the lens; outside an fr-goal run check the page against its `covers:` code by hand) and an Enforcement bullet; `uv run python scripts/sync-opencode.py` regenerated .opencode/instructions/explainers-currency.md (`--check` in sync). Two tests pin the lens and the paragraph. The lens set now owes a docs-accuracy reviewer at lens-review.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t1 created=2026-11-14T01:39:55+00:00 phase=6 -->
### no-refactor-p6-t1 · discovery · no-refactor-because P6.T1 (phase 6)

language-only rewrite; the refactor step is the wording tripwires and fr docs check, which passed with nothing to fix

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t2 created=2026-11-14T01:39:55+00:00 phase=6 -->
### no-refactor-p6-t2 · discovery · no-refactor-because P6.T2 (phase 6)

language-only rewrite; the refactor step is the wording tripwires and fr docs check, which passed with nothing to fix

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t3 created=2026-11-14T01:39:55+00:00 phase=6 -->
### no-refactor-p6-t3 · discovery · no-refactor-because P6.T3 (phase 6)

one workflow step and one test; ruff format and the targeted tests left nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p6-t4 created=2026-11-14T01:39:55+00:00 phase=6 -->
### no-refactor-p6-t4 · discovery · no-refactor-because P6.T4 (phase 6)

one config file, one rule paragraph and two tests; ruff, the mirror check and the targeted tests left nothing to clean

<!-- fr:journal kind=review scope=plan id=review-p6 created=2026-11-14T01:45:24+00:00 phase=6 -->
### review-p6 · review · phase 6 review: 3 in-scope findings, all fixed; fact-keepers: 0 lost, 2 actor/wording shifts fixed (phase 6)

Code reviewer (separate context, read-only) checked the accuracy commits 2eb18d5c0 and 06f0c034f against the cited code (every finding corrected, none adds a false claim), the plain-language and elements-of-style rewrites with --preserve-from, the whole-repo gate script (exit 0), meaning drift over the full word diff, the pinned question-round wording, rendering at aa56236ba vs the merge base (tables, pre, mermaid unchanged; no raw list markers), inbound links, the site-build step (CI job on d5fc3b7a9 ran it against blog-craft 3b0c7d0 and passed), .fr/lenses.yaml against spec §3b (byte for byte; fr lenses check 0; docs-accuracy required), the R16 rule paragraph and its OpenCode mirror, and the main-merge rewrite of the acceptance-matrix --origin paragraph. Two blind fact-keepers. Fixes in 43956e3e7. The phase executor was lost to a container restart after it had committed and pushed; the orchestrator merged origin/main (d5fc3b7a9) and made the review fixes.

<!-- fr:journal kind=discovery scope=plan id=p6-fact-keeper created=2026-11-14T01:45:24+00:00 phase=6 -->
### p6-fact-keeper · discovery · Fact-keeper results per page (R8): page | counts | resolution (phase 6)

docs/explainers/why-fr.md | kept 39, changed 3, lost 0, added 1 | 'credentials that profile was explicitly granted' -> 'you explicitly granted that profile': accepted (the operator grants a profile's secrets, fr-init); 'Workspaces are reconciled and torn down' -> 'Close-out reconciles ...': wrong actor (fr isolation reconciles on every up/down, gc), fixed; 'structured' dropped from plans: restored
docs/explainers/01-fr-goal.md | kept ~470 (clustered), changed 0, lost 0, added 2 | added: AI acronym expansion; 'the orchestrator dispatched an agent' names the dispatcher (true: only the orchestrator dispatches and claims). tldr thinned ('a short YAML file listing the steps', 'the autonomous run'): restored

<!-- fr:journal kind=finding scope=plan id=p6-r1 created=2026-11-14T01:45:24+00:00 phase=6 state=open review_scope=in -->
### p6-r1 · finding [open] (reviewer: in scope) · 01-fr-goal.md: "Only the transcripts write any of it down" (transcripts record) (phase 6)

Raised by the phase 6 reviewer.

<!-- fr:journal kind=finding scope=plan id=p6-r2 created=2026-11-14T01:45:24+00:00 phase=6 state=open review_scope=in -->
### p6-r2 · finding [open] (reviewer: in scope) · 01-fr-goal.md: self-review "when you write the plan" moved plan authoring to the operator (phase 6)

Raised by the phase 6 reviewer.

<!-- fr:journal kind=finding scope=plan id=p6-r3 created=2026-11-14T01:45:24+00:00 phase=6 state=open review_scope=in -->
### p6-r3 · finding [open] (reviewer: in scope) · 01-fr-goal.md: the OWNER-collision refusal sentences were muddled (phase 6)

Raised by the phase 6 reviewer.

<!-- fr:journal kind=finding scope=plan id=p6-r1-resolved created=2026-11-14T01:45:24+00:00 phase=6 state=fixed resolves=p6-r1 -->
### p6-r1-resolved · finding [fixed] · resolves p6-r1: 01-fr-goal.md: "Only the transcripts write any of it down" (transcripts record) (phase 6)

43956e3e7

<!-- fr:journal kind=finding scope=plan id=p6-r2-resolved created=2026-11-14T01:45:24+00:00 phase=6 state=fixed resolves=p6-r2 -->
### p6-r2-resolved · finding [fixed] · resolves p6-r2: 01-fr-goal.md: self-review "when you write the plan" moved plan authoring to the operator (phase 6)

43956e3e7

<!-- fr:journal kind=finding scope=plan id=p6-r3-resolved created=2026-11-14T01:45:24+00:00 phase=6 state=fixed resolves=p6-r3 -->
### p6-r3-resolved · finding [fixed] · resolves p6-r3: 01-fr-goal.md: the OWNER-collision refusal sentences were muddled (phase 6)

43956e3e7

<!-- fr:journal kind=review scope=plan id=review-lenses created=2026-11-14T01:53:21+00:00 -->
### review-lenses · review · lens review: docs-accuracy 3 findings, tests 4 findings, all fixed

One reviewer per lens, each in its own context, given only its lens (docs-accuracy: required by the .fr/lenses.yaml path rule for every published page; tests: added at spec review). docs-accuracy sampled claims across all 31 rewritten pages and the rule, script and CI step against the code: three false or imprecise claims, fixed in 079e36ada and cdd83daeb (workflow-shapes adopt, fr-dispatch bridge writes, docs-currency H1). tests mutated scripts/check-writing-standards.sh in a scratch clone: the fake-uv tests did not pin which pages reach the checker and nothing exercised the real checker or .writing-standard-terms; both fixed in 52a8fae41 (page-set assertion; a real-checker test run by site-build at the pinned blog-craft). Acceptance rows moved to ci with their test refs; the gh#1369 fixture change was dropped for main's own fix (#1437).

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-14T01:53:21+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · workflow-shapes.md: plain fr run adopt said to preview unless --yes; it writes at once

run/adopt.py:845-846, 950-952; run_cmd.py --yes help. Raised by the docs-accuracy lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2 created=2026-11-14T01:53:21+00:00 state=open review_scope=in -->
### l-docs-accuracy-r2 · finding [open] (reviewer: in scope) · fr-dispatch.md: the bridge skips issue writes too, not only label writes

fr_dispatch/__init__.py:356-362. Raised by the docs-accuracy lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3 created=2026-11-14T01:53:21+00:00 state=open review_scope=in -->
### l-docs-accuracy-r3 · finding [open] (reviewer: in scope) · docs-currency.md: the build drops an H1 only when it opens the body

scripts/build-site.py:290-299. Raised by the docs-accuracy lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-14T01:53:21+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · fake-uv tests never asserted which pages reach the checker

A script checking only the first page of each group passed every test. Raised by the tests lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-14T01:53:21+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · nothing exercised the real checker or .writing-standard-terms (R4)

Deleting the terms file moved 32 to 98 warnings with exit 0, unnoticed. Raised by the tests lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3 created=2026-11-14T01:53:21+00:00 state=open review_scope=in -->
### l-tests-r3 · finding [open] (reviewer: in scope) · acceptance rows kept levels {} / not-implemented although their tests ship

Raised by the tests lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4 created=2026-11-14T01:53:21+00:00 state=open review_scope=in -->
### l-tests-r4 · finding [open] (reviewer: in scope) · after the main merge, the gh#1369 test carried a false comment and a redundant workaround

Raised by the tests lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-14T01:53:21+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: workflow-shapes.md: plain fr run adopt said to preview unless --yes; it writes at once

079e36ada

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r2-resolved created=2026-11-14T01:53:21+00:00 state=fixed resolves=l-docs-accuracy-r2 -->
### l-docs-accuracy-r2-resolved · finding [fixed] · resolves l-docs-accuracy-r2: fr-dispatch.md: the bridge skips issue writes too, not only label writes

cdd83daeb

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r3-resolved created=2026-11-14T01:53:21+00:00 state=fixed resolves=l-docs-accuracy-r3 -->
### l-docs-accuracy-r3-resolved · finding [fixed] · resolves l-docs-accuracy-r3: docs-currency.md: the build drops an H1 only when it opens the body

cdd83daeb

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-14T01:53:21+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: fake-uv tests never asserted which pages reach the checker

52a8fae41: _assert_both_groups_ran_at_the_toplevel compares every page each group sends with its globs.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-14T01:53:21+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: nothing exercised the real checker or .writing-standard-terms (R4)

52a8fae41: test_real_checker_fails_a_page_and_reads_the_terms_file runs blog-craft's checker; site-build runs it with BLOG_CRAFT_DIR=.blog-craft, and test_site_build_checks_the_writing_standards_after_the_build pins that step.

<!-- fr:journal kind=finding scope=plan id=l-tests-r3-resolved created=2026-11-14T01:53:21+00:00 state=fixed resolves=l-tests-r3 -->
### l-tests-r3-resolved · finding [fixed] · resolves l-tests-r3: acceptance rows kept levels {} / not-implemented although their tests ship

a010ef9, 786b523, bb39620, d5ac113: groups, ci-gate, authoring-rule and accuracy-lens rows to ci with test refs.

<!-- fr:journal kind=finding scope=plan id=l-tests-r4-resolved created=2026-11-14T01:53:21+00:00 state=fixed resolves=l-tests-r4 -->
### l-tests-r4-resolved · finding [fixed] · resolves l-tests-r4: after the main merge, the gh#1369 test carried a false comment and a redundant workaround

52a8fae41: the test file is main's again; main's --stale-days fix stands and this branch's duplicate fixture change is gone.

<!-- fr:journal kind=finding scope=plan id=p3-ops-seal-encrypt-help-resolved-2 created=2026-11-14T01:54:12+00:00 phase=3 state=open resolves=p3-ops-seal-encrypt-help tracked_by=https://github.com/derio-net/super-fr/issues/1441 -->
### p3-ops-seal-encrypt-help-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1441] · resolves p3-ops-seal-encrypt-help: ops_cmd.py `fr ops seal --encrypt` help says {target} is the target's name; it is the shell-quoted full path (phase 3)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1441.

<!-- fr:journal kind=finding scope=plan id=p3-build-site-marker-resolved-2 created=2026-11-14T01:54:12+00:00 phase=3 state=open resolves=p3-build-site-marker tracked_by=https://github.com/derio-net/super-fr/issues/1442 -->
### p3-build-site-marker-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1442] · resolves p3-build-site-marker: scripts/build-site.py fill_pages replaces <!-- site:pages --> even inside inline code (phase 3)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1442.

<!-- fr:journal kind=finding scope=plan id=p3-r8-resolved-2 created=2026-11-14T01:54:12+00:00 phase=3 state=open resolves=p3-r8 tracked_by=https://github.com/derio-net/super-fr/issues/1443 -->
### p3-r8-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1443] · resolves p3-r8: docs-currency.md and merge-protection.md lists already rendered broken at the merge base (phase 3)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1443.

<!-- fr:journal kind=finding scope=plan id=p4-skill-acceptance-verify-resolved-2 created=2026-11-14T01:54:12+00:00 phase=4 state=open resolves=p4-skill-acceptance-verify tracked_by=https://github.com/derio-net/super-fr/issues/1444 -->
### p4-skill-acceptance-verify-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1444] · resolves p4-skill-acceptance-verify: fr-acceptance SKILL.md:116 says a --verify row keeps nagging in fr acceptance status whatever its status, under Post-merge owed (phase 4)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1444.

<!-- fr:journal kind=finding scope=plan id=p4-plan-rework-help-resolved-2 created=2026-11-14T01:54:12+00:00 phase=4 state=open resolves=p4-plan-rework-help tracked_by=https://github.com/derio-net/super-fr/issues/1445 -->
### p4-plan-rework-help-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1445] · resolves p4-plan-rework-help: fr plan rework help says the parent is "(Complete + archived)"; rework_create accepts a live or incomplete parent (phase 4)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1445.

<!-- fr:journal kind=finding scope=plan id=p4-acceptance-backfill-render-resolved-2 created=2026-11-14T01:54:12+00:00 phase=4 state=open resolves=p4-acceptance-backfill-render tracked_by=https://github.com/derio-net/super-fr/issues/1446 -->
### p4-acceptance-backfill-render-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1446] · resolves p4-acceptance-backfill-render: fr-acceptance.md backfill list already renders broken at the merge base: step 4 merges into step 3's paragraph (phase 4)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1446.

<!-- fr:journal kind=finding scope=plan id=p5-init-tool-help-markup-resolved-2 created=2026-11-14T01:54:12+00:00 phase=5 state=open resolves=p5-init-tool-help-markup tracked_by=https://github.com/derio-net/super-fr/issues/1447 -->
### p5-init-tool-help-markup-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1447] · resolves p5-init-tool-help-markup: fr init scaffold --help prints `<tool>;` - Rich markup eats `[@<version>]` (phase 5)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1447.

<!-- fr:journal kind=finding scope=plan id=p5-progress-skill-status-yes-resolved-2 created=2026-11-14T01:54:12+00:00 phase=5 state=open resolves=p5-progress-skill-status-yes tracked_by=https://github.com/derio-net/super-fr/issues/1448 -->
### p5-progress-skill-status-yes-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1448] · resolves p5-progress-skill-status-yes: fr-progress SKILL.md lists fr status among the commands that preview until --yes (phase 5)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1448.

<!-- fr:journal kind=finding scope=plan id=p5-triage-skill-schema-resolved-2 created=2026-11-14T01:54:12+00:00 phase=5 state=open resolves=p5-triage-skill-schema tracked_by=https://github.com/derio-net/super-fr/issues/1449 -->
### p5-triage-skill-schema-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1449] · resolves p5-triage-skill-schema: fr-triage SKILL.md says a first run creates judgements with schema: 11; the engine writes 12 (phase 5)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1449.

<!-- fr:journal kind=finding scope=plan id=p5-exit-gates-code-render-resolved-2 created=2026-11-14T01:54:12+00:00 phase=5 state=open resolves=p5-exit-gates-code-render tracked_by=https://github.com/derio-net/super-fr/issues/1450 -->
### p5-exit-gates-code-render-resolved-2 · finding [deferred → https://github.com/derio-net/super-fr/issues/1450] · resolves p5-exit-gates-code-render: fr-exit-gates.md tester bullet's fenced example renders as inline code, at the merge base too (phase 5)

Filed at deliver as https://github.com/derio-net/super-fr/issues/1450.
