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
| `packages/fr/src/fr/triage/collect.py:22,98` | `GhForge` calls `fr.gh.list_repos/list_issues/list_prs/list_open_prs/view_issue/read_file_at_ref/viewer_login` directly. Only `list_issue_comments` and `list_prs_by_head` go through `RealGhClient`. |
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
`client_for_backend` ignores `host` for GitHub (`hostclient.py`,
`client_for_backend`), and `RealGhClient` has no host at all. The same pattern,
done right for GitLab, already exists as `fr_vk/pr_state.py:88`
`_client_for_url`.

Skill prose that still names `gh` without saying it is the GitHub case:
`plugins/super-fr/skills/fr-triage/SKILL.md:39,43` (`gh issue view`) and
`plugins/super-fr-dispatch/skills/fr-dispatch/SKILL.md:39-40` (`gh pr list`,
`gh api`). fr-goal's wording is already forge-aware.

## Requirements

R1. `fr triage collect` makes every forge read through a `GhClient` adapter
    from `fr.hostclient`. No `fr.gh` import remains in `fr/triage/collect.py`.
    The GitHub backend implements the reads. The GitLab and Gitea backends
    raise `UnsupportedForgeOperation`, which collect reports as its own
    `ForgeError`, never a traceback.
R2. `GhClient` gains a default-branch lookup and a PR-for-branch lookup, both
    implemented on GitHub, GitLab and Gitea with today's per-forge behaviour.
    The PR lookup keeps today's normalised shape (`state`
    OPEN/MERGED/CLOSED, `url`, `mergedAt`). Both accept an injected command
    runner, so a caller controls the subprocess (env, timeout, test double).
R3. `fr/isolation/local.py` runs both lookups through the adapter, passing its
    own `Runner`. The default-branch lookup keeps the `symbolic-ref` step first,
    the non-interactive network env and timeout, and the `"main"` fallback. No
    `gh`/`glab`/`tea` argv remains in `local.py`.
R4. `fr.hostclient` classifies any forge error (every member of `FORGE_ERRORS`)
    as `rate_limit` | `info` | `warn` | `unknown`. The fr-vk bridge's
    rate-limit guard uses that classification and catches every
    `FORGE_ERRORS` member. So a GitLab or Gitea rate limit also backs off the
    tick, and `bridge_cli.py` no longer imports `fr.gh`.
R5. `fr.hostclient.client_for_url(url)` returns the adapter for the forge AND
    host a URL lives on: the backend from `backend_for_url`, and a host only
    when it is not a SaaS domain. `fr_vk.pr_state` and
    `triage_batch_cmd.make_client` both use it.
R6. The GitHub adapter honours a self-hosted host. Built with `host=`, every
    `gh` subprocess it starts targets that host. Built without one (the SaaS
    case), behaviour is unchanged. `client_for_backend` passes `host` to the
    GitHub backend too, and `client_for`'s "declared host fr cannot thread"
    warning no longer fires for GitHub.
R7. The forge-adapter tripwire has no allowlist. Any `fr.gh` import or
    `["gh", …]` argv under `packages/*/src` outside the GitHub backend files
    fails CI.
R8. Shipped skill prose names forge operations neutrally, with `gh` shown only
    as the GitHub example ("on GitHub, `gh issue view`"), in fr-triage and
    fr-dispatch. The OpenCode and Hermes mirrors are regenerated.

## 4. Design

### 4.A Triage collect on the adapter (R1)

Add the collect reads to the `GhClient` protocol (`fr/ghclient.py`):
`list_repos(owner, limit)`, `list_issues(repo, state, limit, fields=None)`,
`list_prs(repo, state, limit)`, `list_open_prs(repo, limit)`,
`read_file_at_ref(repo, path, ref)`, `viewer_login()`. `view_issue` already
exists. `RealGhClient` implements each by delegating to the existing `fr.gh`
function, so the GitHub behaviour is byte-identical. `UnsupportedBatchOps`,
the mixin `RealGlabClient`/`RealTeaClient` inherit, gains a raising stub for
each. GitLab and Gitea refuse, honestly.

`GhForge` becomes `ClientForge(client: GhClient)`. Its default
(`collect`'s entry point) is `ClientForge(client_for_backend("github"))`.
Triage is GitHub-only by its own scope (§1), so this is the honest default
without a checkout. `_forge_errors()` translates `FORGE_ERRORS` and
`UnsupportedForgeOperation` (plus the existing `FileNotFoundError` → `GH_MISSING`) into
`ForgeError`. `ORIGINS_ISSUE_LIST_FIELDS` is re-exported through the adapter
module (`fr.real_ghclient`), not `fr.gh`, so `collect.py` imports no `fr.gh`.
The `Forge` protocol stays, because tests and `origins.py` fake it.

### 4.B Isolation lookups on the adapter (R2, R3)

New in `fr/ghclient.py`:

```python
class CommandRunner(Protocol):
    def __call__(self, argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]: ...

class GhClient(Protocol):
    def default_branch(self, *, cwd: Path, run: CommandRunner | None = None) -> str | None: ...
    def pr_for_branch(self, branch: str, *, cwd: Path, run: CommandRunner | None = None) -> dict[str, Any] | None: ...
```

- `run=None` means a plain `subprocess.run(capture_output=True, text=True)`.
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
- `push_check`'s `_CLI_FOR_BACKEND` is a string for guidance text, not an argv,
  and stays.

`client_for` reads `.devcontainer/fr-profiles.yaml` and the origin. That is the
same `detect_backend` call `local.py` already makes, so there is no new I/O
class. Isolation's existing tests drive these lookups through a fake `Runner`
keyed on argv, and they keep passing unchanged, because the argv is unchanged
and the runner is still the one injected.

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

`pr_state` imports it (its private name stays as an alias only if tests
reference it). `triage_batch_cmd.make_client(url)` returns
`client_for_url(url)`.

### 4.E The GitHub adapter honours a host (R6)

- `RealGhClient(host: str | None = None)`. With a host, every `gh` subprocess
  it starts runs with `GH_HOST=<host>` in its environment. That is gh's own
  documented override, and it beats `gh`'s default host for every command.
- Mechanism: a `contextvars.ContextVar[str | None]` in `fr.gh` that `_run_gh`
  reads to add `GH_HOST` to a copied `os.environ`. `RealGhClient` sets it
  around each delegated call (one small context manager). The `fr.gh`
  module's free functions keep their signatures. Nothing else in fr sets it.
  With no host, `_run_gh`'s `subprocess.run` gets no `env=` at all, so the
  SaaS path is untouched.
- `client_for_backend` passes `host` to `RealGhClient`. `client_for`'s warning
  about a declared host fr cannot thread now fires for Gitea only.

Consequence: a triage batch on a GitHub Enterprise repo (facts carry
`https://ghe.example/…` URLs) reaches that instance. A self-hosted *GitLab*
repo URL with no MR path shape still reads as `github`. That cannot arise
from triage facts, which are GitHub-only (§1). It is noted here, not
designed for.

### 4.F Skill prose (R8)

- `fr-triage/SKILL.md:39,43`: "confirm on the forge (on GitHub, `gh issue
  view`)", and the same for the truncated-body read.
- `fr-dispatch/SKILL.md:39-40`: name the operations ("list merged PRs matching
  the slug, read the file at the deliverable path") with the `gh` commands
  given as the GitHub example.
- Then run `scripts/sync-opencode.py` **and** `scripts/sync-hermes.py`.

### 4.G Tripwire (R7)

Delete `KNOWN` and `test_every_known_site_still_offends` from
`test_tripwire_forge_adapter.py`, and update its docstring: there is no
allowlist now. A future exemption means arguing for a `BACKEND` entry in a
diff. `BACKEND` stays `{gh.py, real_ghclient.py, hostclient.py}`.

## 5. Risks

- **`fr.gh` contextvar leakage.** A host set by one `RealGhClient` call must
  not reach a later bare `fr.gh` call. A context manager with `reset(token)`
  in `finally` prevents it, and a test pins it.
- **Isolation behaviour drift.** §4.B moves code verbatim, and the existing
  isolation tests run against identical argv. Any test edit beyond imports is
  a red flag for review.
- **Protocol growth on the fakes.** Test fakes that implement `GhClient`
  structurally may need the new methods. mypy will name them.

## 6. Test Plan

1. **CI:** the forge-adapter tripwire passes with no allowlist. A planted
   `from fr import gh` in a non-backend module fails it (unit-pinned).
2. **CI:** `client_for_url` passes the self-hosted host for a self-hosted URL
   and `None` for a SaaS URL. `make_client` returns exactly that client.
3. **CI:** `RealGhClient(host="ghe.example")` runs `gh` with
   `GH_HOST=ghe.example`, and `RealGhClient()` passes no env.
4. **CI:** triage collect through a GitLab/Gitea adapter fails as a
   `ForgeError` naming the unsupported operation.
5. **CI:** a GitLab rate-limit `GlabError` makes the bridge guard back off.
6. Post-merge, operator-driven, optional: `fr isolation status` and
   `verify-merge` on this repo still show the PR state, and `fr triage collect
   --repo derio-net/super-fr` still collects.

## 7. Acceptance rows (born here; presented at spec review)

- `forge-calls-through-adapter`: every forge call fr's packages make goes
  through the forge adapter, enforced by a tripwire with no allowlist
  (R1, R3, R4, R7).
- `isolation-lookups-every-forge`: the isolation lifecycle's default-branch
  and PR-for-branch lookups work on GitHub, GitLab and Gitea through the
  adapter (R2, R3).
- `triage-batch-self-hosted-host`: triage batch verbs talk to the forge
  instance the batch's repo lives on, self-hosted included (R5, R6).
- `triage-skill-prose-forge-neutral`: not a row. R8 is prose checked by
  review. It is a process obligation, not a product claim.
