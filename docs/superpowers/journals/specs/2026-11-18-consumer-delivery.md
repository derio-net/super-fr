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
