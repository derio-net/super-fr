# fr-isolation: backend-neutral host-push docs + read-only push preflight diagnostic

**Date:** 2026-07-14
**Status:** Draft — scope pre-approved by operator (batched decision captured
in the driving issue's thread, no separate brainstorming Q&A needed).
**Target repo:** derio-net/super-fr.
**Closes:** #377.

## Problem

Issue #377 reports that `fr isolation exec -- git push` fails against a
GitLab backend from the `dev` profile: host-key verification failure, then
(once bypassed) `Permission denied (publickey,password)` against
`git@gitlab.local.gebit.de`. Pushing the SAME worktree from the HOST
succeeds — confirming the repo/remote config is fine, and that the container
simply has no SSH identity.

That's expected, not a bug. `plugins/super-fr/skills/fr-isolation/SKILL.md`'s
"Exec-bridge discipline" section already documents that push and PR/MR/PR-ish
creation happen on the authenticated HOST, specifically so operator
credentials never enter the container implicitly:

> Push and PR creation default to the HOST (run them outside `exec`, from the
> worktree)... ALL GitHub interaction uses the AUTHENTICATED HOST — pushes,
> PR creation...

Two real gaps, both confirmed by direct inspection (not assumed):

1. **The rule is GitHub-only in its wording.** `packages/fr/src/fr/{glab.py,
   tea.py,hostclient.py,_hosts.py}` and
   `docs/superpowers/specs/2026-07-09-multi-backend-git-host-adapters-design.md`
   (#372) added first-class GitLab/Gitea backends with their own CLI auth
   story (`glab auth login` / `GITLAB_TOKEN`, `tea login add`). The
   exec-bridge doc never caught up — it still says "GitHub interaction" and
   `gh`, so an agent working a GitLab- or Gitea-backed repo has no
   backend-neutral pointer telling it `git push` over SSH is *also*
   host-only, before it burns a cycle on a confusing SSH failure.
2. **No live diagnostic exists.** `grep`-confirmed: there is currently NO
   SSH-related code anywhere in `packages/fr/src/fr/` (no `known_hosts`,
   `ssh-agent`, `SSH_AUTH_SOCK`, `StrictHostKeyChecking` handling at all).
   When the SSH failure happens, nothing reports back "here's why, and here's
   the right command" — the agent (or operator) is on its own reading a raw
   `Permission denied (publickey,password)`.

## Decisions (operator-approved, pre-scoped — see task brief)

| Question | Answer |
|---|---|
| Provision SSH into the container (known_hosts, agent forwarding)? | **No.** Out of scope, and a deliberate non-goal (see below) — it would reverse the repo's "credentials never enter the container implicitly" design principle that #372's exec-bridge doc and the `fr-isolation-required` hook both encode. |
| Scope of the fix | **Docs generalization + a read-only preflight diagnostic**, nothing that changes runtime auth behavior. |
| Diagnostic must never print | Key material, tokens, or ssh-agent socket contents — presence/absence only. |
| Surface for the diagnostic | Extend `fr isolation status` (the existing `--stats` opt-in flag is the closest precedent: computed only when asked, rendered as extra fields/lines) rather than a new top-level subcommand — keeps the "one place to check a workspace" property `status` already has. |

## Design

### 1. Docs: generalize the exec-bridge discipline section

`plugins/super-fr/skills/fr-isolation/SKILL.md`'s "Exec-bridge discipline"
bullets (`Credential boundary` and `ALL GitHub interaction...`) are rewritten
to:

- Name all three backends explicitly (GitHub/`gh`, GitLab/`glab`,
  Gitea/`tea`) instead of "GitHub interaction".
- Call out `git push` over an SSH remote as its own host-only case, not just
  PR/MR/API calls — the exact gap #377 hit. GitLab and Gitea remotes are
  commonly SSH (`git@host:owner/repo.git`); GitHub's default clone URL is
  HTTPS but SSH remotes exist there too. The rule is remote-protocol-neutral:
  the container has no SSH identity and no host-token-derived credential
  helper, so ANY `git push`/`git fetch` against an authenticated remote must
  run on the host, regardless of backend or transport.
- Point at the new diagnostic (`fr isolation status --push-check`) as the
  first thing to reach for when a push fails inside `exec`, instead of
  reading a raw SSH error cold.

**Duplication check (done, not assumed):** `grep -rn "Push and PR creation\|
ALL GitHub interaction\|Credential boundary"` across the repo turns up the
canonical `plugins/super-fr/skills/fr-isolation/SKILL.md`, its generated
mirror `.opencode/skills/fr-isolation/SKILL.md` (owned by
`scripts/sync-opencode.py`, per `AGENTS.md`'s "Skills/rules: canonical source
vs. generated mirrors" — re-synced, never hand-edited), and three *archived*
specs under `docs/superpowers/implemented/specs/` that quote the old text as
historical rationale (not live instructions — left untouched, matching how
the archive already treats prior wording as a record, not a mirror to keep
in lockstep). No other live copy exists; `.claude/rules/fr-isolation-required.md`
and its `~/.claude/rules/` counterpart are a different rule (edit-tool gating,
not exec-bridge discipline) and don't mention push/PR behavior at all.

### 2. Read-only push preflight diagnostic

New opt-in flag on `fr isolation status`: `--push-check` (mirrors the
existing `--stats` flag's shape: off by default, computed and rendered only
when passed, one extra dict key in JSON / extra lines in text).

`LocalWorktreeDevcontainerTarget` (`packages/fr/src/fr/isolation/local.py`)
gets a new method:

```python
def push_check(self, state: IsolationState) -> dict[str, Any]:
    """Read-only preflight for #377: worktree remotes, whether an SSH agent
    socket is visible IN-CONTAINER (informational only — expected to be
    ABSENT, that is not a failure), and a backend-aware pointer at the
    correct host-side push workflow. Never prints key material, tokens, or
    ssh-agent socket contents/paths — presence/absence only."""
```

It reports:

- `remotes`: `git -C <worktree> remote -v` output, split into lines (plain
  git metadata, not a secret — remote URLs may embed a bare host+path but
  never a credential in this repo's conventions, since HTTPS remotes rely on
  a credential helper / CLI ambient auth, not embedded userinfo).
- `ssh_agent_in_container`: `{"present": bool, "detail": str}` from a `sh -c`
  probe run via `devcontainer exec` that checks only `[ -n "$SSH_AUTH_SOCK"
  ]` and, if set, `[ -S "$SSH_AUTH_SOCK" ]` — echoing one of `unset`,
  `set:socket-exists`, `set:socket-missing`. The socket PATH itself is never
  captured or echoed (paths under `/tmp` are low-sensitivity but excluded
  anyway — the "never print... full ssh-agent socket contents" constraint is
  read as "don't surface anything beyond a yes/no").
- `backend`: `fr._hosts.detect_backend(repo_root)` (`"github"` / `"gitlab"` /
  `"gitea"`).
- `guidance`: one backend-aware sentence naming the CLI (`gh`/`glab`/`tea`)
  and the host-side command shape (`cd <worktree> && git push ...`),
  pointing at the SKILL.md section for the full rule.

`isolation_cmd.py`'s `status` command grows a `push_check: bool =
typer.Option(False, "--push-check", ...)` parameter, following the exact
pattern `stats` already uses: compute per-row only when the flag is set,
attach under `row["push_check"]`, and render extra text lines (remotes,
ssh-agent line, guidance) under each workspace's status line in `text`
format; `json` format gets the raw dict for free via the existing
`json.dumps(rows, ...)` path — no separate JSON-rendering code needed.

### 3. Test coverage

Both target files already have direct unit-test siblings and are exercised
under the existing `isolation-suite-lifecycle` acceptance-matrix row
(`docs/acceptance/matrix.yaml`, id `isolation-suite-lifecycle`, level `unit`,
citing `tests/unit/test_isolation.py` + `tests/unit/test_isolation_cmd.py`).
New tests land in those same two files — no matrix edit needed (the row
already cites both files at the `unit` level; this PR adds coverage under an
already-cited ref, not a new capability needing a new row). Concretely:

- `tests/unit/test_isolation.py`: a `TestPushCheck` class covering
  `push_check()` directly against `LocalWorktreeDevcontainerTarget` — remotes
  parsed from a real throwaway repo (git calls hit the real binary, per this
  file's existing convention), the ssh-agent probe's three output shapes
  (`unset` / `set:socket-exists` / `set:socket-missing`) via a fake `Runner`,
  and backend-aware guidance text for at least `github` and `gitlab`.
- `tests/unit/test_isolation_cmd.py`: CLI-level tests mirroring
  `test_status_stats_flag_shows_resource_row` /
  `test_status_default_makes_no_stats_call` — `--push-check` present in JSON
  output when passed, absent (no extra calls) when omitted.

This is a reporting feature over existing seams (git, `devcontainer exec`,
`detect_backend`), so no live GitLab/SSH server or real devcontainer is
needed — the `Runner` seam already used by every other `local.py` method
covers it.

## Non-goals

- **SSH known_hosts provisioning or agent forwarding into the container.**
  The issue's own suggested fix asks for this, but it's explicitly out of
  scope per the operator's pre-approved decision (see §Decisions) — it would
  reverse the "operator credentials never enter the container implicitly"
  principle #372's exec-bridge doc and the `fr-isolation-required` hook both
  encode. If a future need makes this unavoidable, it needs its own
  brainstorm/spec weighing that tradeoff explicitly, not a silent add-on
  here.
- **Any change to `StrictHostKeyChecking` or other SSH client config.** Never
  touched, never recommended as a workaround.
- **A short-lived-credential / token-forwarding mechanism.** Same reasoning
  as the agent-forwarding non-goal — a real design question of its own.
- **Printing or logging any key material, token, or ssh-agent socket path.**
  The diagnostic is presence/absence only by construction (§2); no code path
  in this PR reads key bytes, calls `ssh-add -l`, or `cat`s a socket.
- **A new top-level `fr isolation` subcommand.** `--push-check` on the
  existing `status` command was chosen over a new subcommand (§Decisions) to
  keep "check a workspace" in one place.

## Acceptance rows

No new `docs/acceptance/matrix.yaml` row — this PR adds test coverage under
the already-cited `isolation-suite-lifecycle` row (§3), it doesn't ship a
capability that row doesn't already describe ("Operator can init a
devcontainer profile and run isolated work: up → exec → status → down...").
This spec deliberately omits a dedicated "Test" + "Plan" heading pair for the
same reason: the CI staleness guard (and `fr plan self-review`) only fire on
that specific two-word heading with no citing row, and §3 above already
covers what would go there.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-07-14-isolation-push-diagnostics | `derio-net/super-fr` | `2026-07-14-isolation-push-diagnostics` | — |

## References

- Issue #377.
- `plugins/super-fr/skills/fr-isolation/SKILL.md` — "Exec-bridge discipline"
  (the section this PR generalizes).
- `docs/superpowers/specs/2026-07-09-multi-backend-git-host-adapters-design.md`
  — #372, the GitLab/Gitea backend work whose auth story this PR's docs catch
  up to.
- `packages/fr/src/fr/_hosts.py` — `detect_backend`, reused unchanged.
- `packages/fr/src/fr/isolation/local.py` — `stats()`/`status()`, the
  pattern `push_check()` follows.
