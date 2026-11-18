# Consumer delivery: OpenCode rules and scaffolds

Batch `consumer-delivery`: super-fr#1402, #1375, #1308, #1186, #1271, delivered as one PR.

## Background

What super-fr ships to **consumer** repos and machines has five gaps:

- **#1402.** `scripts/install.sh` copies the shipped rules only to `~/.claude/rules/`
  (`install.sh:773-781`, list `CLAUDE_RULES` at `:168-174`). For OpenCode it installs
  skills, commands, agents and the plugin (`scripts/deliver-opencode-plugin.sh`), and no
  instructions. Only this repo's own `opencode.json` (`"instructions":
  [".opencode/instructions/*.md"]`) loads them. So an OpenCode consumer never sees
  `fr-isolation-required`, `docs-currency` or the other shipped rules. Registering a file
  in the operator's global OpenCode config is fragile: that config can be JSONC
  (`opencode.jsonc`), which `jq` cannot edit, and `deliver-opencode-plugin.sh` already
  refuses a JSONC `cli.json`. The plugin already adds a system part at a session's first
  model request (`packages/fr-opencode-plugin/src/nag.ts`).
- **#1375.** Three plugin handlers run `fr` in the plugin's directory
  (`ctx.location.directory`, `src/index.ts:260`) instead of the session's: the nag
  (`src/nag.ts:132`, `repoRootOf(options.directory)`), bind (`src/bind.ts:109`,
  `shellCwd(options.directory, input.workdir)`) and claim (`src/claim.ts:104`,
  `runFr(options.directory, …)`). #1372 moved only the idle guard to the session's
  `location.directory` (`src/idle.ts:160-165`). The unbind handler (`src/bind.ts:130`)
  runs `fr isolation detach --session <id>`, which acts on every binding of that session
  id wherever it is (`packages/fr/src/fr/commands/isolation_cmd.py:975-984`), so its cwd
  does not choose what it acts on.
- **#1308.** The consumer `acceptance-report.yml` scaffold
  (`packages/fr/src/fr/acceptance/scaffold.py`) pulls third-party actions by mutable tag
  (`actions/checkout@v7`, `astral-sh/setup-uv@v5`, and `@v4` on Gitea) and installs fr
  from `super-fr@main` in every job (`:157, :241, :298, :348, :398, :435, :480, :503,
  :525`). The `debt` job holds `contents/issues/pull-requests: write` and checks out with
  `token: FR_DEBT_TOKEN || github.token` and the default `persist-credentials: true`
  (`:469-477`), so the token sits in `.git/config` for every later step. super-fr's own
  CI pins `@<sha> # vX.Y.Z` (for example `actions/checkout@3d3c42e5… # v7.0.1`,
  `astral-sh/setup-uv@1c37ad07… # v10.3.0`) and `.github/dependabot.yml` keeps them
  fresh. super-fr's tags are not protected and immutable releases are off.
  `fr acceptance init --refresh-ci` (`commands/acceptance_cmd.py:1315-1351, :1408`)
  re-renders the workflow.
- **#1186.** `DEBT_STEP_GITEA` (`scaffold.py:491-509`) runs `fr debt issue --yes` with no
  forge credential and no `tea` installed; its checkout has no push credential.
  `DEBT_STEP_GITLAB` (`:511-528`) runs both debt commands in `python:3.12` with no `glab`
  and no `GITLAB_TOKEN`. GitLab's `CI_JOB_TOKEN` cannot create issues or merge requests;
  Gitea's job token can. `fr debt archive-pr` already maps `FR_DEBT_TOKEN` to `GH_TOKEN`
  and `GITLAB_TOKEN` (`commands/debt_cmd.py:376-380`) and pushes to `origin`
  (`:509-516`), relying on the checkout's stored credential.
- **#1271.** A forge behind an SSO forward-auth proxy answers API calls with an HTML
  login page. `fr.tea.api_result` (`packages/fr/src/fr/tea.py:84-130`) already names that
  cause for `tea api`. The other JSON reads of `tea` and `glab` output (`tea.py:193`,
  `glab.py:269`, `real_teaclient.py:153`, `real_glabclient.py:206` and their siblings)
  surface a raw decode error or a generic "unreadable output". The infra half (exempting
  the instance's `/api/` paths from the proxy) belongs in `derio-net/frank`.

## Requirements

R1. `scripts/install.sh` delivers every shipped rule that it installs for Claude Code
(`CLAUDE_RULES`) to OpenCode as well, inside the delivered plugin directory at
`<plugins>/fr-opencode-plugin/rules/<rule>.md`, copied from the generated
`.opencode/instructions/` mirror. Uninstall removes them with the plugin directory.

R2. The OpenCode plugin adds the text of every `*.md` file in its own `rules/`
directory to the system prompt of every model request of every session (top-level and
child), in file-name order. No `rules/` directory, or an empty one, adds nothing. A file
that cannot be read is skipped. The handler never throws.

R3. A test fails when a rule in `CLAUDE_RULES` is not delivered to the OpenCode plugin
directory, or when the delivered list and `CLAUDE_RULES` differ.

R4. The acceptance nag runs `fr` in the top-level session's `location.directory`, and
in the plugin's directory only when the session has none.

R5. The bind handler resolves a shell call's `workdir` against the session's
`location.directory` (the plugin's directory when the session has none), and runs `fr`
there.

R6. The claim handler runs `fr run claim` in the child session's `location.directory`
(the plugin's directory when the session has none).

R7. The unbind handler keeps running in the plugin's directory, with a comment saying
why: `fr isolation detach --session` acts on the session's bindings wherever they are.

R8. Every `uses:` in the consumer scaffold (GitHub and Gitea templates, every job) names
a 40-hex commit SHA followed by `# vX.Y.Z`. The GitHub template's pins equal super-fr's
own CI pins for the same action, and a test fails when they differ. The Gitea template
keeps today's majors, pinned the same way.

R9. Every `uv tool install` of fr in the consumer scaffold (all three templates, every
job) installs `git+https://github.com/derio-net/super-fr@<sha>#subdirectory=packages/fr`
followed by `# vX.Y.Z`, where `vX.Y.Z` is the release tag of the fr that renders the
workflow (an RC `X.Y.ZrcN` names tag `vX.Y.Z-rc.N`) and `<sha>` is the commit that tag
names, read with `git ls-remote` at render time. When the tag cannot be resolved, the
render refuses (exit 2), names the tag and the remedy, and writes nothing.

R10. `fr acceptance check` prints a warning, never a failure, when the repo's scaffolded
workflow pins an fr version older than the fr running the check; the warning names
`fr acceptance init --refresh-ci`. A workflow with no recognisable pin gives no warning.

R11. In the GitHub `debt` job, the checkout sets `persist-credentials: false`, and
`FR_DEBT_TOKEN` is in the environment of the `fr debt archive-pr` step only.
`fr debt archive-pr` pushes its branch with `FR_DEBT_TOKEN`, else the forge token in its
environment, supplied for that one push and never written to `.git/config` or put on a
command line.

R12. The Gitea `debt` job installs a pinned `tea`, logs it in to the instance with
`FR_DEBT_TOKEN`, else the job's own token, checks out with `persist-credentials: false`,
and gives both debt steps the credential they need.

R13. The GitLab `technical-debt` job installs a pinned `glab` and runs both debt commands
with `GITLAB_TOKEN` taken from the masked variable `FR_DEBT_TOKEN`; `archive-pr` pushes
with that token as in R11. When `FR_DEBT_TOKEN` is not set, the job fails before either
command with one line naming the masked `FR_DEBT_TOKEN` variable and its `api` scope.

R14. Every read of JSON output from `tea` or `glab` in fr's adapters (`tea.py`,
`glab.py`, `real_teaclient.py`, `real_glabclient.py`) recognises an HTML body and raises
the adapter's own error naming the cause: an SSO or forward-auth login page, with the
remedy (exempt the instance's API paths, or use an internal URL). One shared helper does
the recognition; a captured HTML-redirect fixture with an RFC 2606 host pins it.

## Design

### A. OpenCode rules ride the plugin (R1–R3)

`deliver-opencode-plugin.sh install` already replaces `<plugins>/fr-opencode-plugin/`
wholesale. It gains one step: copy `.opencode/instructions/<rule>` for each rule in a
list it receives, into `<plugins>/fr-opencode-plugin/rules/`. The list is the one
`install.sh` already holds (`CLAUDE_RULES`), so there is one list, not two: `install.sh`
passes it (an env var or extra arguments; the plan picks). Repo-local-only rules
(`acceptance-matrix.md`, `artifact-versioning.md`, …) are not in `CLAUDE_RULES` and are
never delivered. The source is the `.opencode/instructions/` mirror, which
`sync-opencode.py` already generates and CI guards, so the OpenCode copy reads as it
does in this repo.

A new module `src/rules.ts` reads `<plugin dir>/rules/*.md` (the plugin's own
directory, from `import.meta`), sorted by name, and appends each as a system part on
every model request of every session, through the same system hook the nag uses. It
reads the files once per process and caches them. In this repo the in-tree plugin
(`.opencode/plugins/fr-isolation-required.ts`, a re-export of `packages/fr-opencode-plugin`)
has no `rules/` directory, so `opencode.json`'s own `instructions` stay the only copy and
nothing loads twice. It carries a `// super-fr-parity:` marker and a `parity.yaml` row if
`fr harness parity` requires one for a new surface (the plan checks).

The drift test (R3) sits beside `tests/unit/test_install_copies_rules.py`: it runs the
delivery into a temp plugins directory and compares the delivered `rules/` to
`CLAUDE_RULES`.

### B. Handlers follow the session (R4–R7)

A small shared helper, `sessionDirectory(session, id, fallback)`, wraps the lookup the
idle guard already does (`idle.ts:160-165`): `session.get({sessionID})`, then
`location.directory`, else the fallback. The nag calls it for the top-level session, bind
for the shell call's session, claim for the child session. Each handler keeps its
"never throws" contract; a failed lookup uses the fallback. Each gains a test where the
session's directory differs from the plugin's.

The isolation guard in `src/index.ts:281` also resolves `shellCwd(directory, …)` against
the plugin's directory. It is out of scope here (see below).

### C. Scaffold pins (R8–R10)

`scaffold.py` gets one table of action pins, `ACTION_PINS`, keyed by
`(action, ci_type)`, each a `(sha, version)` pair, rendered as `@<sha> # <version>`. The
GitHub entries copy super-fr's own `.github/workflows/` pins; a test reads those
workflows and fails when an entry differs, so a Dependabot bump of super-fr's CI fails
until the scaffold moves with it. The Gitea entries keep today's majors (`checkout` v4,
and any other action the Gitea template names), with SHAs resolved when the plan is
implemented.

fr's own pin is computed at render time. `render_workflow` takes a resolved
`FrPin(sha, tag)`; a new `resolve_fr_pin(version, *, ls_remote=…)` maps the running
version to its tag and runs `git ls-remote https://github.com/derio-net/super-fr
refs/tags/<tag> refs/tags/<tag>^{}`, preferring the peeled commit of an annotated tag.
Tests inject `ls_remote`. A failure raises an error that `fr acceptance init` turns into
exit 2 before writing any file, naming the tag and the remedy (network access, or a
released fr).

The staleness warning (R10) reads the pin comment from the workflow file at the path the
repo's CI type uses (`acceptance/ci.py:32-33`, and `.gitlab-ci.yml` for GitLab), compares
it with the running version, and prints one warning line.

### D. Debt-job credentials (R11–R13)

`fr debt archive-pr` pushes with a token when it has one, through git's environment
config (`GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0=http.<origin>/.extraheader`,
`GIT_CONFIG_VALUE_0=AUTHORIZATION: basic <base64(user:token)>`), so the token is in the
child's environment only. The user part follows the forge (`x-access-token` on GitHub,
`oauth2` on GitLab and Gitea). With no token it pushes as today.

GitHub: the checkout keeps `fetch-depth: 0`, drops `token:` and sets
`persist-credentials: false`; `fr debt issue` keeps `GH_TOKEN: github.token`;
`archive-pr` gets `GH_TOKEN` and `FR_DEBT_TOKEN`.

Gitea: a step installs `tea` (the version `fr isolation`'s scaffold already pins,
`isolation/scaffold.py:359`, checked by SHA-256) and runs `tea login add` against
`gitea.server_url` with `secrets.FR_DEBT_TOKEN || gitea.token`, passed through `env:`.
`archive-pr` pushes with the same token.

GitLab: `before_script` installs a pinned `glab`, then fails with the R13 line when
`FR_DEBT_TOKEN` is empty; `variables:` sets `GITLAB_TOKEN: $FR_DEBT_TOKEN` (and
`GITLAB_HOST: $CI_SERVER_HOST` for a self-hosted instance).

### E. HTML bodies from tea and glab (R14)

A new `fr.forge_body.not_json_reason(out: str, stderr: str) -> str | None` returns the
named reason when the text is an HTML body (starts with `<`, or names `text/html`), else
`None`. `tea.api_result` uses it in place of its inline check, and every other
`json.loads` of `tea`/`glab` output catches `JSONDecodeError`, asks the helper, and
raises `TeaError` / `GlabError` with the reason (or the existing message when it is not
HTML). The fixture is a 302 response header block plus an HTML login page, with the
proxy host written as `auth.example.com` and the forge as `git.example.com`, stated as
redacted.

### Out of scope

- The isolation guard's `shellCwd` in `src/index.ts:281` has the same premise as #1375
  but is a gate, not a best-effort handler; changing what it judges needs its own
  decision. It is filed as a follow-up.
- The frank half of #1271 (`skip_path_regex` on the Gitea proxy provider). An issue is
  filed in `derio-net/frank` during this run and linked from the PR.
- A consumer `dependabot.yml`: not emitted; pins move with `--refresh-ci`.
- The GitHub adapters and SSO (GitHub Enterprise Server behind a proxy).

## Verification

strategy: candidate
gate: tester

- opencode-rules-delivered: live — only a real OpenCode 2 session started on a machine where the released `install.sh` ran can show the delivered rules in its system prompt; delivery and injection are unit-tested before merge
- opencode-handlers-session-directory: none — bun tests in `packages/fr-opencode-plugin` with a session directory that differs from the plugin's
- scaffold-pins-actions: none — CI unit tests on the rendered templates and the pin-equality test against `.github/workflows/`
- scaffold-pins-fr: none — CI unit tests with an injected `ls-remote`: pin rendered, RC tag form, refusal writes nothing, staleness warning
- debt-token-scope-github: none — CI unit tests on the rendered GitHub debt job and on `archive-pr`'s push environment
- debt-credentials-gitea-gitlab: live — only a real Gitea and GitLab runner can show the weekly job write its issue and push; the rendered jobs and the missing-token line are unit-tested before merge
- forge-sso-html-refusal: none — CI unit tests over the redacted fixture at every `tea`/`glab` JSON read

## Test Plan

Post-merge, operator-driven:

1. On a machine with OpenCode 2, run the released `scripts/install.sh`. In a consumer
   repo, start a session and ask the agent to quote the first heading of
   `fr-isolation-required`; it answers from its system prompt. (Row
   `opencode-rules-delivered`.)
2. In a Gitea consumer repo, run `fr acceptance init --refresh-ci` with the debt job on,
   dispatch the workflow with `debt: true`, and see the "Technical debt" issue upserted
   and the archive branch pushed. In a GitLab consumer repo, do the same once with
   `FR_DEBT_TOKEN` unset (the job fails with the one-line remedy) and once with it set
   (issue upserted, branch pushed). (Row `debt-credentials-gitea-gitlab`.)
