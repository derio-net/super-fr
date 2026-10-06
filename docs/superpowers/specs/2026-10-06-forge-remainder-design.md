# Every forge call goes through the adapter — design

**Date:** 2026-10-06
**Slug:** `2026-10-06-forge-remainder`
**Status:** design (fr-goal, batch `forge-remainder`)
**Repo:** `derio-net/super-fr` (single-repo change)
**Issues:** super-fr#742 (remainder), super-fr#892

## 1. Goal

`fr.hostclient` is the seam that lets fr work on GitHub, GitLab and Gitea. #744
moved `deliver`'s PR-body gate onto it and added a shrink-only tripwire,
`tests/unit/test_tripwire_forge_adapter.py`. That tripwire allows three sites to
keep calling `gh` directly (its `KNOWN` set). This change empties that set and
fixes a related bypass in the triage batch verbs, where the self-hosted host is
dropped (#892).

### Non-goals

- **No GitLab/Gitea triage.** Triage collection stays GitHub-only. The adapter's
  GitLab and Gitea backends *refuse* the listing reads honestly
  (`UnsupportedForgeOperation`, gh#611) instead of implementing them.
- **No self-hosted host for `fr triage collect`.** `--repo`/`--org` carry no
  host. Collect uses gh's own host resolution (`GH_HOST`, `gh auth`), as it
  does today.
- **No new prose tripwire.** Skill wording is fixed by hand (§4.F).
- **Not in scope from #742:** forge-parity checks at `fr run start` and the
  review-checklist item. Both belong to #611 and the review skills. The
  `deliver` gate, refusal texts and closeout brief were already fixed by #744
  (`commands/run_cmd.py:5452`, `run/closeout.py:281`).

## 2. Background

What is still bypassed (the tripwire's `KNOWN`, at
`tests/unit/test_tripwire_forge_adapter.py:38`):

| Site | What it does today |
|---|---|
| `packages/fr/src/fr/triage/collect.py:22,98` | `GhForge` calls `fr.gh.list_repos/list_issues/list_prs/list_open_prs/view_issue/read_file_at_ref/viewer_login` directly. Only `list_issue_comments` and `list_prs_by_head` go through `RealGhClient`. Built by `commands/triage_cmd.py:87` `make_forge()`. |
| `packages/fr/src/fr/isolation/local.py:2779` | `_resolve_default_branch`: `git symbolic-ref`, then its own `gh repo view` / `glab repo view` / `tea repos` branch, then `"main"`. Runs on the isolation `Runner` with `run_network`'s non-interactive env and timeout. |
| `packages/fr/src/fr/isolation/local.py:2929` | `_pr_from` (+ `_pr_from_gitlab`, `_pr_from_gitea`): PR-by-branch lookup normalised to `{state: OPEN\|MERGED\|CLOSED, url, mergedAt}`, on `self.run`. |
| `packages/fr-vk/src/fr_vk/bridge_cli.py:33,257` | `_gh_rate_limit_guard` catches `fr.gh.GhError` and calls `fr.gh._classify_error` to back off on a rate limit. That is GitHub-only. |

#892: `commands/triage_batch_cmd.py:174`:

```python
def make_client(url: str) -> GhClient:
    return client_for_backend(backend_for_url(url))
```

Its four callers (`:485`, `:949`, `:1127`, `:1451`) build `url` from
`_host_of(facts, owner_repo)`, so the host is known and then dropped. Triage
facts come only from GitHub, so a self-hosted triage repo is in practice a
GitHub Enterprise one. Passing `host=` alone would not fix that:
`client_for_backend` ignores `host` for GitHub (`hostclient.py:83-100`), and
`RealGhClient` has no host at all. The same pattern, done right for GitLab,
already exists as `fr_vk/pr_state.py:88` `_client_for_url`.

Two facts about the existing adapter shape the design:

- `GhClient.view_issue` (`real_ghclient.py:35`) returns a *projected* dict:
  `{state, labels: [names], assignees, body}`. Collect reads the *raw*
  `fr.gh.view_issue` record (`ISSUE_VIEW_FIELDS`: `title`, `url`, label
  objects; `collect.py:313-320,517,616`). GitLab and Gitea implement
  `view_issue` too. So collect cannot reuse that method.
- `fr.gh.view_pr_body` (`gh.py:67`) calls `subprocess.run` itself, not
  `_run_gh`.

Skill prose that still presents `gh` as *the* forge CLI:
`plugins/super-fr/skills/fr-triage/SKILL.md:39,43` (`gh issue view`), `:49`
("the `gh` commands you recommend") and `:112` ("the exact `gh` command"), and
`plugins/super-fr-dispatch/skills/fr-dispatch/SKILL.md:39-40` (`gh pr list`,
`gh api`) and `:91` ("Check `gh auth status`"). fr-goal's wording is already
forge-aware.

## Requirements

R1. `fr triage collect` makes every forge read through a `GhClient` adapter
    from `fr.hostclient`. No `fr.gh` import remains in `fr/triage/collect.py`.
    The GitHub backend implements the reads with today's exact records. The
    GitLab and Gitea backends raise `UnsupportedForgeOperation`, which collect
    reports as its own `ForgeError`, never a traceback. The adapter's existing
    `view_issue` contract is unchanged.
R2. `GhClient` gains a default-branch lookup and a PR-for-branch lookup, both
    implemented on GitHub, GitLab and Gitea with today's per-forge commands.
    The PR lookup keeps today's normalised shape (`state`
    OPEN/MERGED/CLOSED, `url`, `mergedAt`). Both accept an injected command
    runner, and both return `None`, never raising, when the CLI fails, is
    missing or prints something unparseable.
R3. `fr/isolation/local.py` runs both lookups through the adapter, passing its
    own `Runner`. The default-branch lookup keeps the `symbolic-ref` step first,
    the non-interactive network env and timeout, and the `"main"` fallback. No
    `gh`, `glab` or `tea` argv remains in `local.py`.
R4. `fr.hostclient` classifies any forge error (every member of `FORGE_ERRORS`)
    as `rate_limit` | `info` | `warn` | `unknown`. The fr-vk bridge's
    rate-limit guard uses that classification and catches every
    `FORGE_ERRORS` member. So a GitLab or Gitea rate limit also backs off the
    tick, and `bridge_cli.py` no longer imports `fr.gh`.
R5. `fr.hostclient.client_for_url(url)` returns the adapter for the forge AND
    host a URL lives on: the backend from `backend_for_url`, and a host only
    when it is not a SaaS domain. `fr_vk.pr_state` and
    `triage_batch_cmd.make_client` both use it.
R6. The GitHub adapter honours a host. Built with `host=`, every `gh`
    subprocess it starts carries `GH_HOST=<host>`: `_run_gh`'s, `view_pr_body`'s
    and its own default command runner's. Built without one, it passes no
    `env=` and behaviour is unchanged. For a checkout, `client_for` gives the
    GitHub backend a host only when one is DECLARED in
    `.devcontainer/fr-profiles.yaml`. A host merely derived from origin is not
    threaded: inside a checkout, `gh` already infers it from the remote, and an
    SSH-alias remote (`git@github-work:…`) would otherwise become a bogus
    `GH_HOST`. `client_for`'s warning about a declared host fr cannot thread now
    fires only for Gitea.
R7. The forge-adapter tripwire has no allowlist. Any `fr.gh` import or
    `["gh", …]` argv under `packages/*/src` outside the GitHub backend files
    fails CI.
R8. Shipped skill prose that tells the agent to run a forge command names the
    operation, with `gh` shown only as the GitHub example ("on GitHub, `gh
    issue view`"). This covers fr-triage and fr-dispatch, and the OpenCode and
    Hermes mirrors are regenerated. One kind of mention keeps `gh`: a
    statement of fact about a component that is GitHub-only by design, such as
    fr-triage:96's "each `gh` call is bounded" about the GitHub-only collector
    (d1).

## 4. Design

### 4.A Triage collect on the adapter (R1)

Add collect's reads to the `GhClient` protocol (`fr/ghclient.py`):

- `list_repos(owner, limit)`;
- `list_issues(repo, state, limit, fields=None)`;
- `list_prs(repo, state, limit)` and `list_open_prs(repo, limit)`;
- `read_file_at_ref(repo, path, ref)`;
- `viewer_login()`;
- **`view_issue_record(repo, number)`**: the raw `gh issue view --json
  ISSUE_VIEW_FIELDS` record collect reads. This is a NEW method, so the
  projected `view_issue` that observe, apply and the bridge rely on stays
  untouched (sr-f1).

`RealGhClient` implements each by delegating to the existing `fr.gh` function,
so the GitHub records are byte-identical. `UnsupportedBatchOps`, the mixin
`RealGlabClient`/`RealTeaClient` inherit (`real_glabclient.py:56`,
`real_teaclient.py:47`), gains a raising stub for each. GitLab and Gitea refuse.

`GhForge` is renamed `ClientForge(client: GhClient)`, with every method
delegating to `client`. Its construction site is `commands/triage_cmd.py:87`
`make_forge()`, which returns `ClientForge(client_for_backend("github"))`.
Triage is GitHub-only by its own scope (§1), so that is the honest default
without a checkout.

`_forge_errors()` translates every `FORGE_ERRORS` member and
`UnsupportedForgeOperation` (plus the existing `FileNotFoundError` →
`GH_MISSING`) into `ForgeError`. `ORIGINS_ISSUE_LIST_FIELDS` is re-exported
through `fr.real_ghclient`, so `collect.py` imports no `fr.gh`. The `Forge`
protocol stays, because tests and `origins.py:36,161` fake it.

The same PR updates these, with no alias kept:

- the three `GhForge` tests (`tests/unit/test_triage_collect.py:392-447`).
  They monkeypatch `gh._run_gh`, which still works through the delegation, so
  only the name changes;
- the docstrings at `triage/errors.py:3` and `triage/collect.py:6`;
- the AGENTS.md line "one implementation, `GhForge` over `fr.gh`", which
  becomes "`ClientForge` over the forge adapter".

### 4.B Isolation lookups on the adapter (R2, R3)

New in `fr/ghclient.py`:

```python
class CommandRunner(Protocol):
    def __call__(self, argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]: ...

class GhClient(Protocol):
    def default_branch(self, *, cwd: Path, run: CommandRunner | None = None) -> str | None: ...
    def pr_for_branch(self, branch: str, *, cwd: Path, run: CommandRunner | None = None) -> dict[str, Any] | None: ...
```

- `run=None` means the adapter's own default runner: `subprocess.run(argv,
  cwd=cwd, capture_output=True, text=True)`, with `FileNotFoundError` caught
  and returned as `None`. The GitHub adapter's default runner adds `GH_HOST`
  when it has a host (§4.E).
- Both return `None` on any CLI failure or unparseable output, never raise.
  This keeps today's tolerance, where a failed lookup reads as "unknown".
- The bodies move verbatim from `local.py`. GitHub uses `gh repo view --json
  defaultBranchRef` and `gh pr view <branch> --json state,url,mergedAt`.
  GitLab uses `glab repo view --jq .default_branch` and `glab mr view <branch>`
  plus its state mapping. Gitea uses `tea repos` JSON and the `tea pulls list
  --state all` head-label scan.
- These are real implementations on all three backends, not
  `UnsupportedBatchOps` stubs.

`local.py`:

- `_resolve_default_branch` keeps `symbolic-ref` first. It then calls
  `client_for(self.repo_root).default_branch(cwd=self.repo_root, run=lambda
  argv, cwd: run_network(self.run, self.repo_root, argv, cwd))` and falls back
  to `"main"`.
- `_pr_from(cwd, branch)` becomes `client_for(cwd).pr_for_branch(branch, cwd=cwd,
  run=self.run)`.
- `_pr_from_gitlab`/`_pr_from_gitea` are deleted.
- `push_check`'s `_CLI_FOR_BACKEND` builds guidance text, not an argv, and
  stays.

The argv each lookup sends through the injected runner does not change.

Exactly one existing test changes its patch point (sr-f3).
`tests/unit/test_isolation_network_timeouts.py:90-113`
`test_default_branch_lookup_is_bounded_and_falls_back_on_timeout`
monkeypatches `fr.isolation.local.detect_backend`. That name stays imported
for `push_check`, so the patch would still succeed but would have no effect
on the lookup. The backend is now resolved inside `hostclient.client_for`, so
the test patches `fr._hosts.detect_backend` instead (plus `declared_host` →
`None`, so `client_for` emits no warning). Its assertions stay as they are.
The same applies to any other isolation test that selects a non-GitHub
backend for these two lookups by patching `local.detect_backend`. The plan
greps for them.

### 4.C Forge-error classification (R4)

`hostclient.forge_error_kind(exc: BaseException) -> Literal["rate_limit",
"info", "warn", "unknown"]`:

- A `GhError` delegates to `gh._classify_error` on its stderr + message.
- A `GlabError` or `TeaError` gets the same text heuristics: 403/429 + "rate
  limit" → `rate_limit`, 404/"not found" → `info`, the transient patterns →
  `warn`.
- Anything else is `unknown`.

`bridge_cli._gh_rate_limit_guard` catches `FORGE_ERRORS` and backs off when
`forge_error_kind(exc) == "rate_limit"`. The metric reason string stays
`gh_rate_limited`, because dashboards key on it. The import becomes
`from fr.hostclient import FORGE_ERRORS, forge_error_kind`.

### 4.D `client_for_url` (R5)

Promote `fr_vk.pr_state._client_for_url` to `fr.hostclient.client_for_url(url)`
unchanged:

```python
client_for_backend(_hosts.backend_for_url(url),
                   host=_hosts.self_hosted_hostname(urlparse(url).hostname))
```

`pr_state` calls it, and no test references the private name.
`triage_batch_cmd.make_client(url)` returns `client_for_url(url)`.

### 4.E The GitHub adapter honours a host (R6)

**Mechanism.**

- `RealGhClient(host: str | None = None)`.
- `fr.gh` gains one `contextvars.ContextVar[str | None]` and a helper, `_env()`.
  `_env()` returns `None` when the var is unset, and a copy of `os.environ`
  plus `GH_HOST` otherwise.
- `_run_gh` and `view_pr_body` both pass `env=_env()`. With no host that is
  `env=None`, so the SaaS path is untouched.
- `RealGhClient` sets the var around each delegated call with a context
  manager (`token = var.set(host)` … `var.reset(token)` in `finally`), so it
  cannot leak into a later bare `fr.gh` call.
- Its default command runner (§4.B) passes `env=_env()` the same way, inside
  that context.
- Nothing else in fr sets the var.

**Reach (sr-f4).**

- `client_for_backend(backend, host=)` passes `host` to `RealGhClient`, so
  `client_for_url` reaches a GitHub Enterprise instance named in a URL.
- `client_for(repo_root)` passes the GitHub backend only
  `_hosts.declared_host(repo_root)`. GitLab keeps `host_for` as today.
- So for a checkout, only an operator-declared GitHub host changes
  behaviour. Every `client_for` caller (apply, deliver's `pr_body`, the bridge,
  isolation) on such a repo then runs `gh` with that `GH_HOST`. That is
  exactly what the declaration asked for. Today it is silently ignored with a
  warning.
- A derived origin host is not threaded. Inside a checkout `gh` infers it
  itself, and an SSH alias must never become `GH_HOST`.
- `client_for`'s declared-host warning now fires for Gitea only.

`gh` documents `GH_HOST` as the host for commands where it "cannot be inferred
from the context of a local Git repository". The `--repo` reads (triage's) are
exactly that case. A cwd-based call inside a checkout still prefers the
checkout's remote, which for a GHE repo is that same host.

What remains, recorded rather than designed for: a self-hosted *GitLab* repo
URL with no MR path shape still reads as `github` in `client_for_url`. That
cannot arise from triage facts, which are GitHub-only (§1).

### 4.F Skill prose (R8)

- `fr-triage/SKILL.md:39,43`: "confirm on the forge (on GitHub, `gh issue
  view`)", and the same for the truncated-body read.
- `fr-triage/SKILL.md:49`: "the forge commands you recommend (on GitHub,
  `gh …`)".
- `fr-triage/SKILL.md:112`: "the exact forge CLI command (on GitHub, `gh …`)".
- `fr-triage/SKILL.md:96` keeps "each `gh` call is bounded". It states a fact
  about the GitHub-only collector (d1), not a command for the agent.
- `fr-dispatch/SKILL.md:39-40`: name the operations ("list merged PRs matching
  the slug, read the file at the deliverable path"), with the `gh` commands
  given as the GitHub example.
- `fr-dispatch/SKILL.md:91`: "check the forge CLI's auth (on GitHub, `gh auth
  status`)".
- Then run `scripts/sync-opencode.py` **and** `scripts/sync-hermes.py`.

### 4.G Tripwire (R7)

Delete `KNOWN` and `test_every_known_site_still_offends` from
`test_tripwire_forge_adapter.py`, and update its docstring: there is no
allowlist now. A future exemption means arguing for a `BACKEND` entry in a
diff. `BACKEND` stays `{gh.py, real_ghclient.py, hostclient.py}`.

## 5. Risks

- **`fr.gh` contextvar leakage.** A host set by one `RealGhClient` call must
  not reach a later bare `fr.gh` call. The `reset(token)` in `finally`
  prevents it, and Test Plan item 4 pins it.
- **Isolation behaviour drift.** §4.B moves code verbatim, and the argv the
  injected runner sees is unchanged. Isolation test edits are limited to
  *where the backend is patched* (§4.B). A changed assertion is a red flag for
  review.
- **Protocol growth on the fakes.** Structural `GhClient` fakes live under
  `tests/` (e.g. `tests/unit/fakes.py:38` `FakeGhClient`), and CI's mypy does
  not check them. A fake missing a new method fails only at runtime, if
  something calls it. The new methods are reached only through `client_for`
  in isolation and through `ClientForge` in collect, and the tests for those
  paths use the real adapter on a scripted runner or a faked `Forge`. If a
  test does route a fake through them, the plan adds the methods to that fake.

## 6. Test Plan

1. **CI:** the forge-adapter tripwire passes with no allowlist. A planted
   `from fr import gh` in a non-backend module fails it (unit-pinned).
2. **CI:** `client_for_url` passes the self-hosted host for a self-hosted URL
   and `None` for a SaaS URL. `make_client` returns exactly that client.
3. **CI:** `RealGhClient(host="ghe.example")` puts `GH_HOST=ghe.example` on a
   `--repo` read (`_run_gh`), on `pr_body` (`view_pr_body`) and on a lookup's
   default runner. `RealGhClient()` passes `env=None` on all three.
4. **CI:** after a `RealGhClient(host=…)` call returns, or raises, a bare
   `fr.gh` call carries no `GH_HOST`.
5. **CI:** `client_for` on a checkout declaring `forge: {type: github, host:
   ghe.example}` builds a GitHub client with that host and emits no warning.
   A derived (undeclared) non-SaaS origin host yields a GitHub client with no
   host. A declared Gitea host still warns. This rewrites
   `tests/unit/test_hostclient.py:134` (now asserting the Gitea warning and the
   GitHub silence).
6. **CI:** `default_branch` and `pr_for_branch` on each of GitHub, GitLab and
   Gitea, through a scripted runner: the right argv, the normalised
   OPEN/MERGED/CLOSED shape, `None` on a non-zero exit, on unparseable output,
   and with `run=None` on a missing binary.
7. **CI:** isolation's lookups use the injected runner with the network env
   and timeout, across all three backends
   (`test_isolation_network_timeouts.py`, re-pointed per §4.B). A scan pins
   that `local.py` holds no `gh`, `glab` or `tea` argv list, because R7's
   tripwire only sees `gh`.
8. **CI:** triage collect through a GitLab or Gitea adapter fails as a
   `ForgeError` naming the unsupported operation. `ClientForge` over GitHub
   returns the raw `view_issue_record` (title, url, label objects).
9. **CI:** a GitLab rate-limit `GlabError` makes the bridge guard back off. A
   non-rate-limit one re-raises.
10. Post-merge, operator-driven, optional: `fr isolation status` and
    `verify-merge` on this repo still show the PR state, and `fr triage
    collect --repo derio-net/super-fr` still collects.

## 7. Acceptance rows (born here; presented at spec review)

- `forge-calls-through-adapter`: every forge call fr's packages make goes
  through the forge adapter, enforced by a tripwire with no allowlist
  (R1, R3, R4, R7).
- `isolation-lookups-every-forge`: the isolation lifecycle's default-branch
  and PR-for-branch lookups work on GitHub, GitLab and Gitea through the
  adapter (R2, R3).
- `triage-batch-self-hosted-host`: triage batch verbs talk to the forge
  instance the batch's repo lives on, self-hosted included (R5, R6).

R8 is skill prose, checked by review. It is a process obligation, not a
product claim, so it gets no row.
