<!-- fr:journal-schema=4 -->
# Journal: 2026-11-18-consumer-delivery

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-11-18T13:07:21+00:00 input=true -->
### operator-brief · discovery · Operator brief — batch consumer-delivery (verbatim)

Consumer delivery: OpenCode rules and scaffolds

Batch `consumer-delivery` of derio-net/super-fr: 5 issues, delivered as ONE pull request.

## super-fr#1402: install.sh delivers no rules to OpenCode consumers
Still live: `scripts/install.sh` copies rules only to `~/.claude/rules/` (:773-781). It installs no OpenCode instructions (the word does not appear in `install.sh` or `deliver-opencode-plugin.sh`). Consumers on OpenCode therefore never load `fr-isolation-required`, `docs-currency` or the other shipped rules. Only this repo's own `opencode.json` loads them.
Note: The fix also needs an `install.sh` drift tripwire, like `test_install_copies_rules.py`.

## super-fr#1375: fr-opencode-plugin: nag, bind and claim handlers still run fr in the plugin's directory, not the session's
Still live. Three handlers still run `fr` in the plugin's directory, not the session's: `src/nag.ts` (`repoRootOf(options.directory)`, was :90, now :132), `src/bind.ts:109` (`shellCwd(options.directory, input.workdir)`) and :130 (detach), and `src/claim.ts:104` (`runFr(options.directory, ...)`). Only the idle guard was moved to the session's directory.
Note: Each handler needs a decision. Run `bun test` in `packages/fr-opencode-plugin`.

## super-fr#1308: Consumer acceptance-report.yml scaffold: assess pinning (third-party actions, fr@main) + debt-job token scope
Still live: `packages/fr/src/fr/acceptance/scaffold.py` still emits `astral-sh/setup-uv@v5` and `uv tool install "git+...super-fr@main#..."` (:148, :232, :289, :339, :471). The `debt` job holds `contents/issues/pull-requests: write`, and its checkout keeps the default `persist-credentials` while it uses `FR_DEBT_TOKEN` (:465-468). The matrix and comment jobs now set `persist-credentials: false`. Each pin needs a `# vX.Y.Z` version comment, per the operator.
Note: The issue asks for an assessment first. `fr@main` means a consumer's CI runs unreleased code.

## super-fr#1186: Gitea/GitLab scaffolds give the debt steps no forge or push credentials
Live: `DEBT_STEP_GITEA` (`packages/fr/src/fr/acceptance/scaffold.py:482`) runs `fr debt issue --yes` with no forge token env, and its checkout has no push token. `DEBT_STEP_GITLAB` (:502) runs both debt commands with no `GITLAB_TOKEN`/push credential. The GitHub variant (:468-480) passes `GH_TOKEN`/`FR_DEBT_TOKEN`.

## super-fr#1271: Forge behind SSO forward-auth: Gitea API answers HTML; fr surfaces a raw JSON decode error
fr's adapters wrap a JSON decode failure as a generic "unreadable output" error (`packages/fr/src/fr/real_teaclient.py:153`, `real_glabclient.py:206`). Nothing recognizes an HTML or SSO redirect body and names the forward-auth cause. The original failure was in `tea login add` itself, outside fr. The infra part belongs in the frank repo.
Note: Needs a redacted HTML-redirect fixture (RFC 2606 host), per the third-party-privacy rule.

## Why these belong together
Shares the OpenCode plugin with guard-trust and install.sh with release-truth, so it waits for both.

## Delivery rules
- Work on branch `feat/batch-consumer-delivery`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#1402
  Closes derio-net/super-fr#1375
  Closes derio-net/super-fr#1308
  Closes derio-net/super-fr#1186
  Closes derio-net/super-fr#1271
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

Never add the `approved-fr` label: it is the operator's approval to merge, and fr voids it on your next push.

<!-- fr:journal kind=decision scope=spec id=q1-rules-route created=2026-11-18T13:07:21+00:00 decided_by=operator -->
### q1-rules-route · decision · OpenCode rules ride the plugin: delivered into <plugins>/fr-opencode-plugin/rules/ and injected as system parts

Operator chose plugin injection over registering in the global opencode config (JSONC-unsafe) or a managed AGENTS.md block. Spec R1-R3.

<!-- fr:journal kind=decision scope=spec id=q2-handler-cwd created=2026-11-18T13:07:21+00:00 decided_by=operator -->
### q2-handler-cwd · decision · nag, bind and claim follow the session's location.directory; detach stays plugin-scoped

Operator chose the session's directory with plugin-directory fallback; detach is global by session id. Spec R4-R7.

<!-- fr:journal kind=decision scope=spec id=q3-fr-pin created=2026-11-18T13:07:21+00:00 decided_by=operator -->
### q3-fr-pin · decision · Scaffold pins fr as @<sha> # vX.Y.Z, sha of the running fr's release tag via git ls-remote; refuse when unresolvable

Operator chose SHA + version comment over tag + immutable releases or keeping @main. Spec R9.

<!-- fr:journal kind=decision scope=spec id=q4-pin-refresh created=2026-11-18T13:07:21+00:00 decided_by=operator -->
### q4-pin-refresh · decision · Pins move with fr acceptance init --refresh-ci; fr acceptance check warns when the pinned fr is older

Operator chose --refresh-ci plus a staleness warning, no consumer dependabot.yml. Spec R8, R10.

<!-- fr:journal kind=decision scope=spec id=q5-gitlab-no-token created=2026-11-18T13:07:21+00:00 decided_by=operator -->
### q5-gitlab-no-token · decision · GitLab debt job fails with a one-line remedy when FR_DEBT_TOKEN is unset

Operator asked what #1186 is for; after the explanation chose fail-loudly over warn-and-skip. Spec R13.

<!-- fr:journal kind=decision scope=spec id=q6-sso-scope created=2026-11-18T13:07:21+00:00 decided_by=operator -->
### q6-sso-scope · decision · SSO/HTML recognition covers the tea and glab adapters, not gh

Operator chose tea + glab via one shared helper. Spec R14.

<!-- fr:journal kind=decision scope=spec id=q7-verification created=2026-11-18T13:07:21+00:00 decided_by=operator -->
### q7-verification · decision · Strategy candidate, gate tester, two post-merge live rows (OpenCode rule loading; Gitea/GitLab debt job)

Operator chose candidate + post-merge rows. Spec ## Verification and ## Test Plan.

<!-- fr:journal kind=decision scope=spec id=q8-frank-half created=2026-11-18T13:07:21+00:00 decided_by=operator -->
### q8-frank-half · decision · File one issue in derio-net/frank for the forward-auth skip_path_regex and link it from the PR

Operator chose filing a frank issue over a PR-body note or Refs. #1271 still closes with this PR.

<!-- fr:journal kind=lens scope=spec id=lens-security-1 created=2026-11-18T13:07:21+00:00 lens=security step=brainstorm -->
### lens-security-1 · lens · Token scope in CI jobs, action and fr pinning, push credentials kept out of .git/config and argv

<!-- fr:journal kind=finding scope=spec id=s-r1 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r1 · finding [open] (reviewer: in scope) · A parity marker on src/rules.ts would break fr harness parity; the spec leaves the choice to the plan

evidence: observe.py:118-136 accepts a marker only when it names an existing hook script; Claude Code delivers rules as files, so rules.ts has no script to name.

<!-- fr:journal kind=finding scope=spec id=s-r2 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r2 · finding [open] (reviewer: in scope) · R2 assumes the context hook runs on every model request; nothing in the repo shows it

evidence: nag.ts:6-12 and README.md:98-103 document the hook only for the first request; whether event.system is rebuilt or kept is unrecorded.

<!-- fr:journal kind=finding scope=spec id=s-r3 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r3 · finding [open] (reviewer: in scope) · Rules are injected twice when the plugin loads twice, and in super-fr on an installed machine

evidence: nag.ts:85-89: OpenCode 2 can load the delivered plugin twice; a per-process cache does not dedupe across copies or against opencode.json instructions.

<!-- fr:journal kind=finding scope=spec id=s-r4 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r4 · finding [open] (reviewer: in scope) · archive-pr's ls-remote has no credential once persist-credentials is false

evidence: debt_cmd.py:509-516 runs ls-remote --heads origin before push --force-with-lease.

<!-- fr:journal kind=finding scope=spec id=s-r5 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r5 · finding [open] (reviewer: in scope) · On GitLab, origin carries the job token in its URL; an added header may conflict

evidence: GitLab runners clone as https://gitlab-ci-token:<CI_JOB_TOKEN>@host/...; git would send those credentials.

<!-- fr:journal kind=finding scope=spec id=s-r6 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r6 · finding [open] (reviewer: in scope) · R12 is untestable, and the gitea.token fallback never reaches archive-pr

evidence: debt_cmd.py:376-380 reads only FR_DEBT_TOKEN.

<!-- fr:journal kind=finding scope=spec id=s-r7 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r7 · finding [open] (reviewer: in scope) · The sessionDirectory helper clashes with idle.ts's, cites wrong lines, and doubles session lookups

evidence: idle.ts:162-165 is a pure sessionDirectory(info, fallback); nag/bind/claim already call session.get.

<!-- fr:journal kind=finding scope=spec id=s-r8 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r8 · finding [open] (reviewer: in scope) · R8 silently moves GitHub consumers from setup-uv v5 to v10.3.0

evidence: scaffold.py uses setup-uv@v5; super-fr CI pins v10.3.0.

<!-- fr:journal kind=finding scope=spec id=s-r9 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r9 · finding [open] (reviewer: in scope) · R13's pinned glab has no named source

evidence: isolation/scaffold.py:358-394 pins glab 1.107.0 and tea 0.14.2 with sha256.

<!-- fr:journal kind=finding scope=spec id=s-r10 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r10 · finding [open] (reviewer: in scope) · R9 does not say the pin is resolved only when CI is scaffolded and before init's first write

evidence: scaffold.py:858-867 writes .gitkeep and the rule before render_workflow; :841 has_ci.

<!-- fr:journal kind=finding scope=spec id=s-r11 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r11 · finding [open] (reviewer: in scope) · Test Plan step 2's GitLab half does not match --refresh-ci and the GitLab trigger

evidence: scaffold.py:737-741 GitLab refresh prints a job to paste; :519-521 web pipeline with DEBT=true.

<!-- fr:journal kind=finding scope=spec id=s-r12 created=2026-11-18T13:14:50+00:00 state=open review_scope=in -->
### s-r12 · finding [open] (reviewer: in scope) · R14's 'every read' is unbounded and the helper's stderr is unavailable at most sites

evidence: _run_tea gives stdout only; several real_glabclient.py reads lack a JSONDecodeError catch.

<!-- fr:journal kind=finding scope=spec id=s-r13 created=2026-11-18T13:14:50+00:00 state=open review_scope=out -->
### s-r13 · finding [open] (reviewer: out of scope) · The isolation gate and the pipeline sentinel also judge in the plugin's directory

evidence: index.ts:281, :287, :291.

<!-- fr:journal kind=review scope=spec id=spec-review-1 created=2026-11-18T13:14:50+00:00 -->
### spec-review-1 · review · independent spec review: 13 findings (12 in scope, 1 out)

Reviewer (fr-spec-reviewer, separate context) verified decisions q1-q8 are honoured and checked every cited file:line. Findings s-r1..s-r12 in scope, all fixed in the spec; s-r13 out of scope (pre-existing gate uses), named in Out of scope for a follow-up.

<!-- fr:journal kind=lens scope=spec id=lens-tests-1 created=2026-11-18T13:14:50+00:00 lens=tests step=spec-review -->
### lens-tests-1 · lens · R2's context-hook semantics and R11-R13's push credentials rest on platform behaviour that unit tests mock; check each mock against a measured shape

<!-- fr:journal kind=finding scope=spec id=s-r1-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r1 -->
### s-r1-resolved · finding [fixed] · resolves s-r1: A parity marker on src/rules.ts would break fr harness parity; the spec leaves the choice to the plan

§A now decides: no marker, no parity.yaml row; parity does not model rule delivery and R3's drift test is the guard.

<!-- fr:journal kind=finding scope=spec id=s-r2-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r2 -->
### s-r2-resolved · finding [fixed] · resolves s-r2: R2 assumes the context hook runs on every model request; nothing in the repo shows it

R2 and §A now append a rule only when event.system does not already contain its text, which is correct under either semantics; the Test Plan checks a later turn and a child session.

<!-- fr:journal kind=finding scope=spec id=s-r3-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r3 -->
### s-r3-resolved · finding [fixed] · resolves s-r3: Rules are injected twice when the plugin loads twice, and in super-fr on an installed machine

The same content-presence check (R2, §A) dedupes across plugin copies and against opencode.json's instructions.

<!-- fr:journal kind=finding scope=spec id=s-r4-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r4 -->
### s-r4-resolved · finding [fixed] · resolves s-r4: archive-pr's ls-remote has no credential once persist-credentials is false

R11 and §D now authenticate every remote git call archive-pr makes (ls-remote and push), with a unit test asserting both.

<!-- fr:journal kind=finding scope=spec id=s-r5-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r5 -->
### s-r5-resolved · finding [fixed] · resolves s-r5: On GitLab, origin carries the job token in its URL; an added header may conflict

R11 and §D call git against origin's URL with user-info stripped, so only the header's token is used.

<!-- fr:journal kind=finding scope=spec id=s-r6-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r6 -->
### s-r6-resolved · finding [fixed] · resolves s-r6: R12 is untestable, and the gitea.token fallback never reaches archive-pr

R11 names the fallback variable per forge (GH_TOKEN, GITLAB_TOKEN, GITEA_TOKEN); R12 names the exact env of each Gitea step.

<!-- fr:journal kind=finding scope=spec id=s-r7-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r7 -->
### s-r7-resolved · finding [fixed] · resolves s-r7: The sessionDirectory helper clashes with idle.ts's, cites wrong lines, and doubles session lookups

§B reuses idle's pure helper on the info each handler already fetches, and states the order per handler (cheap checks first, one lookup).

<!-- fr:journal kind=finding scope=spec id=s-r8-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r8 -->
### s-r8-resolved · finding [fixed] · resolves s-r8: R8 silently moves GitHub consumers from setup-uv v5 to v10.3.0

§C states the jump and that the change fragment says so; Gitea keeps v5.

<!-- fr:journal kind=finding scope=spec id=s-r9-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r9 -->
### s-r9-resolved · finding [fixed] · resolves s-r9: R13's pinned glab has no named source

R12, R13 and §D name isolation/scaffold.py's pin table for both, with a test asserting equality.

<!-- fr:journal kind=finding scope=spec id=s-r10-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r10 -->
### s-r10-resolved · finding [fixed] · resolves s-r10: R9 does not say the pin is resolved only when CI is scaffolded and before init's first write

R9 and §C: resolve only when a workflow will be rendered, before any write, so ci none needs no network.

<!-- fr:journal kind=finding scope=spec id=s-r11-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r11 -->
### s-r11-resolved · finding [fixed] · resolves s-r11: Test Plan step 2's GitLab half does not match --refresh-ci and the GitLab trigger

Test Plan step 2 now says paste the printed job, then run a web pipeline with DEBT=true, without and with FR_DEBT_TOKEN.

<!-- fr:journal kind=finding scope=spec id=s-r12-resolved created=2026-11-18T13:14:50+00:00 state=fixed resolves=s-r12 -->
### s-r12-resolved · finding [fixed] · resolves s-r12: R14's 'every read' is unbounded and the helper's stderr is unavailable at most sites

R14 defines the sites (every json.loads of _run_tea/_run_glab/tea api/glab api output in the four modules), makes stderr optional, and §E requires one parametrised test over an enumerated list.

<!-- fr:journal kind=finding scope=spec id=s-r13-resolved created=2026-11-18T13:14:50+00:00 state=open resolves=s-r13 out_of_scope=true -->
### s-r13-resolved · finding [out-of-scope] · resolves s-r13: The isolation gate and the pipeline sentinel also judge in the plugin's directory

These uses predate this change and are gates, not best-effort handlers; the spec's Out of scope now names all three, and one follow-up issue will cover them.

<!-- fr:journal kind=decision scope=spec id=exit-baseline created=2026-11-18T13:14:53+00:00 -->
### exit-baseline · decision · exit when spec-review resolved

The exit when spec-review resolved; `fr verification set` and `deliver` compare against it.

```yaml
row_gates:
  debt-credentials-gitea-gitlab: tester
  debt-token-scope-github: none
  forge-sso-html-refusal: none
  opencode-handlers-session-directory: none
  opencode-rules-delivered: tester
  scaffold-pins-actions: none
  scaffold-pins-fr: none
row_kinds:
  debt-credentials-gitea-gitlab: live
  debt-token-scope-github: none
  forge-sso-html-refusal: none
  opencode-handlers-session-directory: none
  opencode-rules-delivered: live
  scaffold-pins-actions: none
  scaffold-pins-fr: none
run_gate: tester
run_kind: candidate
```
