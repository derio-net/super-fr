# Consumer-delivery follow-ups: gates in the session's directory, Gitea matrix token, tea login page

Batch `consumer-followups`: super-fr#1552, #1553, #1554, delivered as one PR. All three
are out-of-scope findings of the `consumer-delivery` run
(`docs/superpowers/specs/2026-11-18-consumer-delivery-design.md`, "Out of scope").

## Background

- **#1552 (s-r13).** #1375 moved the OpenCode plugin's acceptance nag, bind and claim
  handlers to the session's own `location.directory` (`src/session.ts`,
  `sessionDirectory(info, fallback)`), and #1372 moved the idle guard. Three sites in
  `packages/fr-opencode-plugin/src/index.ts` still judge in the plugin's directory
  (`ctx.location.directory`, `index.ts:265`; the issue cites the lines at filing time, `:281`, `:287`, `:291`):
  - the shell gate: `shellCwd(directory, input.workdir)` (`index.ts:287`), which feeds
    both `decideShell` (the whole-line isolation guard) and `decidePush` (the merged-PR
    push guard);
  - the edit gate: `gate(directory, event)` (`index.ts:293`), whose `normalizeTarget`
    resolves a relative target against that directory (`index.ts:164`, called at `:214`);
  - the pipeline sentinel: `writePipelineSentinel(event, directory)` (`index.ts:297`),
    which takes the sentinel's `repo_root` from `git rev-parse --show-toplevel` in that
    directory (`src/sentinel.ts`).
  One OpenCode server can hold sessions in another checkout than the plugin's (gh#1371).
  For such a session the gates judge the wrong repo: a base-clone command can pass, a
  workspace command can be refused, and the sentinel arms (or skips) the wrong repo.
  Claude Code's hooks read the session's own `cwd` from the hook input, so the two
  harnesses differ here.
- **#1553 (p2-r8).** The scaffolded Gitea acceptance workflow's `matrix` job
  (`packages/fr/src/fr/acceptance/scaffold.py`, `WORKFLOW_TEMPLATE_GITEA`, the checkout at
  `:239`) does not set `persist-credentials: false`, so `gitea.token` stays in
  `.git/config` while the PR's own code runs (`fr acceptance check` and every later step).
  The GitHub `matrix` job sets it (`:157`), and the Gitea `debt` job sets it (`:511`).
  The check's default-ref fetch does not need the credential: `branch_refusals`
  (`packages/fr/src/fr/acceptance/amend.py`) reads a failed fetch as a warning when the
  checkout already holds the default ref, which `fetch-depth: 0` gives it.
- **#1554 (l-errors-r5).** `RealTeaClient` (`packages/fr/src/fr/real_teaclient.py`) has six
  fail-soft sites that turn every `TeaError` into an empty answer: `list_linked_prs`
  (`:84`, `[]`), `pr_status_by_url` (`:128`, `None`), `default_branch` (`:274`, `None`),
  `pr_for_branch` (`:295`, `None`), `file_exists` (`:326`, `False`) and `list_dir`
  (`:333`, `[]`). Consumer-delivery R14 made every tea JSON read name an SSO or
  forward-auth login page, but these sites still swallow that named error, so the
  operator sees "absent" or "unknown" instead of the cause. `tea.api_result` names a
  login page in two ways: an HTML body (`HTTP <n> with <forge_body._REASON>`, which
  `forge_body.names_login_page` recognises) and a 3xx redirect (`HTTP <n>: the Gitea API
  redirected … an SSO or forward-auth proxy is likely in front of it …`, which it does
  not). The GitLab adapter already re-raises a named login page at its fail-soft sites
  (`real_glabclient.py:428`, `:465`, and `pr_for_branch` at `:399`).

## Requirements

R1. The OpenCode plugin's shell gate judges every `shell` call in the session's
directory: the call's `workdir` resolved against the session's `location.directory`, or
that directory itself when the call has no `workdir`. Both the whole-line isolation
guard and the merged-PR push guard receive that directory.

R2. The OpenCode plugin's edit gate resolves a relative target path against the
session's `location.directory`. An absolute target is judged as today.

R3. The OpenCode plugin's pipeline sentinel is written for the repo that contains the
session's `location.directory`.

R4. For R1–R3, "the session's directory" is the `location.directory` of the session the
event names (top-level or child; each session's own, never its parent's). When the
lookup fails, answers about another session, or names no directory, the plugin's
directory is used, as today. The plugin looks a session up at most once per process
while the lookup succeeds: a found directory is cached by session id, and a failed
lookup is not cached. A failed lookup never throws out of a hook, and the gates' own
decisions and refusal texts are unchanged.

R5. The scaffolded Gitea acceptance workflow's `matrix` job checks out with
`persist-credentials: false`, so no job of the Gitea workflow keeps a credential in
`.git/config`.

R6. Each of `RealTeaClient`'s six fail-soft sites (`list_linked_prs`, `pr_status_by_url`,
`default_branch`, `pr_for_branch`, `file_exists`, `list_dir`) re-raises a `TeaError` that
names a login page, in either form `tea.api_result` produces (the HTML-body cause and the
3xx redirect). One predicate in `fr/tea.py` recognises both forms. Every other
`TeaError` keeps the site's fail-soft answer.

## Design

### A. Session directory for the gates (R1–R4)

`src/session.ts` gains a resolver shared by the three gate sites: given the plugin's
`ctx.session`, a session id and the plugin's directory, it returns that session's
`location.directory` or the fallback. It calls `session.get({sessionID})` once per session
id and caches only a found directory in a module-level map shared across plugin reloads,
in the same way as `sharedClaimed()` and `sharedServed()`. An answer whose `id` is not
the asked id, a lookup that throws, or one with no `location.directory` returns the
fallback and is not cached. The resolver never throws.

In `src/index.ts`:

- `execute.before` resolves the directory once per event (after `claimChild`, before the
  shell gate) and passes it to `shellCwd(...)` and `gate(...)`;
- `execute.after` resolves it once and passes it to `writePipelineSentinel(...)`.

The bind handler keeps its own child-session rule (a child never rebinds its parent).
The nag, claim and idle handlers are unchanged. Unbind stays in the plugin's directory
(consumer-delivery R7).

The header comment of `index.ts` and the `session.ts` comment say that the gates now
follow the session, and why (gh#1371, #1552).

### B. Gitea matrix checkout (R5)

`WORKFLOW_TEMPLATE_GITEA`'s `matrix` checkout gains `persist-credentials: false` beside
`fetch-depth: 0`, matching the GitHub template. The golden files of the rendered Gitea
workflow, if any, are regenerated. A consumer gets the change through
`fr acceptance init --refresh-ci`.

### C. tea login page at the fail-soft sites (R6)

`fr/tea.py` gains `names_login_page(err: TeaError) -> bool`. It is true when the message
carries `forge_body.names_login_page`'s cause or `api_result`'s 3xx redirect refusal. The
redirect text gets one module constant so that the predicate and the raise share it. Each
of the six sites changes from `except _tea.TeaError: return <empty>` to: re-raise when
the predicate holds, else return the empty answer as today. The docstrings that say
"fails soft" / "any error" name the exception.

Callers already handle a raised forge error (`hostclient.FORGE_ERRORS` includes
`TeaError`), as they do for the GitLab adapter's same rule.

### Out of scope

- The bash hooks' behaviour (Claude Code already judges in the session's `cwd`).
- The GitHub and GitLab templates (already without a persisted credential in the matrix
  job; GitLab has no `checkout`).
- `tea.with_retry`'s transient classification (a login page is not transient, and is not
  retried today).

## Verification

strategy: candidate

- opencode-gates-session-directory: none — bun tests in `packages/fr-opencode-plugin` with a session directory that differs from the plugin's, for each gate and the fallback
- gitea-matrix-no-persisted-token: none — CI unit test on the rendered Gitea workflow
- tea-fail-soft-login-page: none — one parametrised CI unit test over the six sites with the redacted login-page fixture, plus a non-login `TeaError` staying fail-soft

## Implementation Plans

- (written at `plan`)
