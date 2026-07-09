# Multi-backend git-host adapters: GitLab + Gitea support

**Date:** 2026-07-09
**Status:** Draft — brainstormed with operator (batched Q&A, 2026-07-09, re-asked
once and one answer revised).
**Target repo:** derio-net/super-fr.

## Problem

`fr` only speaks GitHub. Every tracking operation (Issues, labels, PR
observation, contents lookups) goes through `gh`, and the coupling isn't
confined to one seam:

- `fr.ghclient.GhClient` (Protocol) + `fr.real_ghclient.RealGhClient` is the
  intended single seam for the render → observe → diff → apply pipeline. It
  covers 9 operations (`view_issue`, `list_linked_prs`, `edit_issue_labels`,
  `edit_issue_state`, `edit_issue_body`, `comment_issue`, `create_issue`,
  `ensure_labels`, `file_exists`/`list_dir`/`read_file`).
- But `fr-vk`'s bridge bypasses it entirely in two places —
  `pr_observe.py:_default_pr_status_fetch` and
  `pr_state.py:_default_close_gh_issue` both shell out to literal `gh`
  subprocesses.
- The isolation lifecycle (`fr/isolation/local.py`) has its **own** separate
  `gh repo view` / `gh pr view` calls (`_resolve_default_branch`, `_pr_from`),
  routed through the `Runner` callable, not `GhClient` — a second seam.
- `fr-dispatch`'s agent-facing prompt (`fr_dispatch/prompt.py`) hardcodes the
  literal text `gh issue view <n> --repo <owner/repo> --json state` and
  "working on GitHub Issue gh#N" into every dispatched agent's first message.
- `fr._urls.ISSUE_URL_RE` hardcodes `github\.com`; `fr-vk` independently
  re-derives `(repo, issue#)` from PR/Issue URLs and VK card titles with 5+
  duplicate regexes of its own.
- `fr` also writes GitHub-only artifacts into repos it scaffolds: the
  devcontainer's unconditional `github-cli` feature
  (`fr/isolation/scaffold.py`), and the acceptance-report GitHub Actions
  workflow template (`fr/acceptance/scaffold.py`, `gh issue list/close/edit/
  create` inline).

This spec adds GitLab (`glab`) and Gitea (`tea`) as first-class backends
alongside GitHub (`gh`), reaching every one of the surfaces above — not just
the `GhClient` pipeline — per the operator's "full pipeline" scope decision
(§Decisions). Bitbucket is explicitly descoped (§Decisions, §Non-goals).

## Research: CLI capability matrix

Verified directly (not just docs) — `gh` and `glab` were already installed on
the research host; `tea` was installed via `brew install tea` (0.14.2) to
confirm real `--help` output rather than trust a possibly-stale rendered
README.

| Capability | GitHub (`gh`) | GitLab (`glab`) | Gitea (`tea`) |
|---|---|---|---|
| CLI officialness | Official (GitHub) | Official (GitLab, adopted 2022) | Official (Gitea) |
| JSON output | `--json <fields>`, near-universal | `--output json` / `-F json`, most commands | `-o json`/`--output json`, most commands |
| Generic API escape hatch | `gh api` (REST) + `gh api graphql` | `glab api` (REST + GraphQL) | `tea api` (REST only — confirmed on the real 0.14.2 binary; **absent from the rendered gitea.com README**, which reflects an older tagged version — verify against the installed binary, not the website, if this drifts again) |
| Auth | `gh auth login`; ambient `gh auth status` session | `glab auth login`; `GITLAB_TOKEN` env var; auto CI-job-token in GitLab CI | `tea login add` (stores per-host login profiles in `$XDG_CONFIG_HOME/tea`) |
| Tracking-issue URL shape | `https://github.com/{repo}/issues/{n}` | `https://gitlab.example.com/{repo}/-/issues/{n}` (**note the `-/` infix**) | `https://gitea.example.com/{repo}/issues/{n}` (matches GitHub's shape) |
| Label color format | 6-hex, no `#` (`gh label create --color ededed`) | 6-hex **with** leading `#` (`glab label create --color "#FF0000"`, default `#428BCA`) | 6-hex, no `#` (Gitea's label API mirrors GitHub's shape) |
| Label name length | 50 chars (422 above — `MAX_LABEL_NAME_LEN`) | 255 chars | not GitHub-tight; the shared 50-char floor stays authoritative across all three |
| "Which PR/MR closes this issue" | GraphQL `closedByPullRequestsReferences` — one clean field | REST `GET /projects/:id/issues/:iid/related_merge_requests` — a dedicated endpoint exists (exact "will-close" signal per item to be confirmed against a live project in the manual verification phase, §Testing) | **No dedicated endpoint.** Must parse the issue's timeline (`tea api '/repos/{o}/{r}/issues/{n}/timeline'`, `cross_reference`-type events) or heuristically scan open PR descriptions for `[Cc]lose[sd]? #N` — approximate, not authoritative the way GitHub's field is |
| Contents API (file_exists/list_dir/read_file) | `gh api repos/{repo}/contents/{path}` | `glab api projects/{id}/repository/files/{path}` (base64 body by default — different shape, not a straight swap) | `tea api /repos/{o}/{r}/contents/{path}` (mirrors GitHub's Contents API closely) |
| CI/pipeline status vocabulary | GraphQL `statusCheckRollup` → PASS/FAIL/PENDING/NONE | GitLab pipeline status (`success`/`failed`/`running`/`pending`/`canceled`/`skipped`) — different vocabulary, needs its own coercion table | Gitea Actions run status — a third vocabulary; **and** Actions is disabled per-repo by default even when instance-enabled, and requires a self-hosted `act_runner` (no SaaS-hosted default the way GitHub/GitLab provide) |
| Devcontainer feature | `ghcr.io/devcontainers/features/github-cli:1` (official, in the containers.dev registry) | **None exists** in the containers.dev registry (only an unrelated `gitlab-ci-local` runner feature) — needs a `postCreateCommand` binary install | **None exists** — same, needs a `postCreateCommand` binary install |
| CI workflow template | `.github/workflows/*.yml`, GitHub Actions schema | `.gitlab-ci.yml` at repo root — **entirely different schema** (`stages:`/`script:`, not `on:`/`jobs:`/`steps:`) | `.gitea/workflows/*.yml` (**not** `.github/workflows/`) — same YAML schema as GitHub Actions ("designed to be compatible wherever possible" per Gitea's own docs) |
| Auto-close keyword convention | `Closes`/`Fixes`/`Resolves #N` | Same convention, GitLab supports it | Same family (`Close`/`Closes`/`Closed`/`Fix`/`Fixes`/`Fixed`/`Resolve`/`Resolves`/`Resolved #N`) |

### Direct answer: do we need an API fallback?

**GitLab and Gitea: no.** Both `glab api` and `tea api` are full escape
hatches that cover every operation `GhClient` needs (contents lookups, label
CRUD, generic REST) — the same "no direct API usage, ride on the CLI's
ambient auth" architecture `fr.gh` already uses for GitHub carries over
unchanged for both new backends. Neither adapter needs to touch raw HTTP.

**Bitbucket would be different in kind, not degree** — this is exactly why
it's descoped (§Decisions): no official CLI exists at all (only a
single-maintainer community project, `bkt`), Bitbucket Data Center has no
issue tracker whatsoever (Jira-only), and Bitbucket Cloud's own Issue-Tracker
REST API is marked "Deprecated" on every endpoint in Atlassian's docs. If
Bitbucket is tackled later, either fr talks to the REST API directly
(breaking the ride-on-CLI-auth philosophy — fr would manage its own token) or
depends on `bkt`, which is itself just a wrapper around that same REST API —
i.e., *is* the API fallback wearing a CLI costume. That's a materially
different design conversation than "which CLI do we shell out to," which is
why it doesn't belong in this PR.

## Decisions (operator, 2026-07-09 batched Q&A)

| Question | Answer |
|---|---|
| Bitbucket | **Descope from this PR.** GitLab + Gitea adapters ship now; Bitbucket is a follow-up pending a real decision on the Issues-vs-Jira question. The abstraction this PR builds (§Design) is shaped so a third backend is an additive adapter, not a rearchitecture. |
| How far the backend-swap reaches | **Full pipeline** (revised from an initial "core tracking pipeline only" answer). Also fixes fr-vk's 2 `gh`-bypass call sites, genericizes fr-dispatch's prompt text and `_urls` parsing, and routes the isolation lifecycle's `gh repo view`/`gh pr view` calls through the same backend abstraction — so `fr isolation up/status/down/gc`, VK dispatch, and `fr apply` all work end-to-end on GitLab- and Gitea-backed repos, not just Issue tracking in isolation. |
| Backend detection | **Auto-detect + override table.** Default heuristic on the repo's `origin` remote hostname (`github.com`→github, `gitlab.com`→gitlab), plus an explicit `backend`/`host` key in `.devcontainer/fr-profiles.yaml` for everything else. Gitea has no free default the way github.com/gitlab.com do — self-hosting is the norm for Gitea specifically, so a Gitea-backed repo will *always* need the explicit key. |
| Scaffold | **Backend-aware.** `fr init scaffold` picks the devcontainer CLI-install step and `fr acceptance init` picks the CI workflow template/location based on the repo's configured backend. |

## Design

### 1. Backend identity, config, and detection — `fr._hosts`

New module `packages/fr/src/fr/_hosts.py` (naming mirrors the existing
`_urls.py` — an internal, widely-imported helper module, not a package):

```python
HostBackend = Literal["github", "gitlab", "gitea"]

DEFAULT_HOST_BACKENDS: dict[str, HostBackend] = {
    "github.com": "github",
    "gitlab.com": "gitlab",
}

def detect_backend(repo_root: Path) -> HostBackend:
    """1. `.devcontainer/fr-profiles.yaml`'s top-level `backend:` key, if present
    (authoritative — always wins, since it's the only way to declare Gitea or
    a self-hosted GitLab/GitHub Enterprise at all).
    2. Else: `git remote get-url origin`'s hostname against
    DEFAULT_HOST_BACKENDS.
    3. Else: `"github"` (today's only behavior, preserved as the fallback —
    no silent behavior change for existing repos that configure nothing)."""
```

`.devcontainer/fr-profiles.yaml` gains two new **optional**, top-level
(repo-level, not per-profile — a repo lives on one host regardless of which
devcontainer profile is active) keys:

```yaml
backend: gitlab          # github (default) | gitlab | gitea
host: gitlab.mycorp.com  # optional — only needed for self-hosted instances;
                         # omit for gitlab.com / github.com
profiles:
  dev: {...}
```

`fr-init`'s interview gains one question ("which forge does this repo live
on, and is it self-hosted?") feeding `scaffold_profile()`'s new `backend`/
`host` params, which `_update_profiles_yaml` writes alongside the existing
`profiles:` block.

### 2. `WorkItemRef` — one URL parser instead of four

`fr._urls.ISSUE_URL_RE` currently hardcodes `github\.com`. Since GitHub and
Gitea share the same `/issues/N` shape and only GitLab inserts `/-/`, one
pattern with an optional non-capturing group covers all three without
needing to know the backend at parse time:

```python
ISSUE_URL_RE = re.compile(r"^https://([^/]+)/([^/]+/[^/]+)/(?:-/)?issues/(\d+)$")
```

`parse_issue_url()` keeps its existing public signature
(`(url) -> (repo, number)`) — every consumer of it (`observe.py`, `diff.py`,
`render.py`, `fr_dispatch/__init__.py`, `fr_dispatch/prompt.py`,
`fr_vk/dispatch.py`, `undispatch_cmd.py`) never needed the host, so this is a
same-signature internal fix, not a call-site migration. `fr.gh.
extract_issue_number` (an independent, GitHub-only-named duplicate) is
retired in favor of `_urls.issue_number()`.

`fr-vk`'s independent regexes (`pr_state.py`'s
`_GH_REPO_FROM_URL_RE`/`_GH_ISSUE_NUM_FROM_TITLE_RE`/`_GH_REPO_FROM_TITLE_RE`/
`_DONE_TITLE_RE`, `workspaces.py`'s inline title regex) collapse into two
shared functions in `fr_vk/_cardref.py` (new, small): `parse_card_title(title)
-> (backend_tag, repo, number) | None` and `build_card_title(backend, repo,
number) -> str`. The wire format stays `"{tag}#{N}: [{repo}]"` — `tag`
resolves per-backend (`gh`/`gl`/`gt`) via a small constant map rather than a
wider rename, so an operator scanning the VK board can tell which host a card
belongs to, and existing GitHub cards (`gh#N: ...`) keep parsing unchanged.

### 3. The `GhClient` Protocol stays named `GhClient` — no rename churn

`fr.ghclient.GhClient` already defines a backend-**neutral shape** (issue
view/edit/comment/create, label ensure/edit, contents lookups) despite its
GitHub-flavored name. Renaming it (and the ~30 call sites that import it)
buys nothing for this PR beyond cosmetics, so it stays. New adapters
implement the same Protocol structurally (Python `Protocol`s don't care about
import names) — `RealGlabClient` and `RealTeaClient` satisfy `GhClient`
exactly like `RealGhClient` does today.

New: `fr.hostclient.client_for(repo: str, repo_root: Path) -> GhClient` — the
one factory every call site that currently hardcodes `RealGhClient()` switches
to: `cli.py`'s command wiring, `fr_vk/bridge_cli.py`, and the isolation
lifecycle (§5). It calls `_hosts.detect_backend(repo_root)` and returns the
matching adapter.

### 4. GitLab adapter

- `fr/glab.py` — mirrors `fr/gh.py`'s shape exactly: `_run_glab(args) ->
  str`, `GlabError`, `create_issue`, `view_issue`, `swap_issue_labels`
  (`glab issue update <iid> --label X --unlabel Y` — flag names verified
  directly against the installed `glab` binary's `--help`), `ensure_label(s)`
  (`glab label create --color "#{hex}"` — **prepends `#` here**, so
  `LabelDef` itself needs no change), `close_issue`
  (`glab issue close`)/reopen, `_classify_error`/`is_transient`/`with_retry`
  tuned to `glab`'s stderr shapes (verified separately from `gh`'s — do not
  assume the same substring patterns match).
- `fr/real_glabclient.py` — `RealGlabClient`, wraps `fr.glab`, satisfies
  `GhClient`. `list_linked_prs` uses `glab api` against
  `/projects/:id/issues/:iid/related_merge_requests` (REST, not GraphQL —
  simpler than GitHub's path here). `file_exists`/`list_dir`/`read_file` use
  `glab api projects/:id/repository/files/:path` (base64-decode the content
  field — a real shape difference from GitHub's raw-media-type trick).
- CI-status coercion: a new `_CI_PASS`/`_CI_FAIL`/`_CI_PENDING` table for
  GitLab's pipeline-status vocabulary, parallel to but distinct from
  `real_ghclient.py`'s GitHub-GraphQL-enum table.

### 5. Gitea adapter

- `fr/tea.py` — mirrors `fr/gh.py`: `_run_tea`, `TeaError`, issue/label
  CRUD via `tea issues`/`tea labels`/`tea comments`, all with `-o json` for
  structured output.
- `fr/real_teaclient.py` — `RealTeaClient`. `list_linked_prs`: no dedicated
  endpoint (§capability matrix) — implemented via `tea api
  '/repos/{o}/{r}/issues/{n}/timeline'` and filtering `cross_reference`-type
  events; documented in the module docstring as a heuristic, weaker guarantee
  than GitHub's/GitLab's field-based lookups, with a comment pointing back to
  this spec's capability matrix so a future maintainer doesn't "fix" it into
  something that assumes an endpoint Gitea doesn't have.
  `file_exists`/`list_dir`/`read_file` via `tea api
  /repos/{o}/{r}/contents/{path}` (closely mirrors GitHub's Contents API
  shape, per the capability matrix).

### 6. fr-vk bypass fixes

- `pr_observe.py:_default_pr_status_fetch(pr_url)` — currently a bare
  `subprocess.run(["gh","pr","view",...])`. New Protocol method
  `GhClient.pr_status_by_url(url) -> dict[str, Any] | None` (returns
  `{"state": ..., "draft": ...}` or `None`). `RealGhClient` passes the URL
  straight to `gh pr view <url>` (confirmed: `gh` accepts a bare PR URL
  directly). **`RealGlabClient` cannot do the same** — verified directly
  against the installed `glab` binary: `glab mr view`'s usage is `{<id> |
  <branch>}`, not a URL, so the adapter must first parse the MR URL itself
  (same `(?:-/)?` shape as issue URLs, §2, but for `/merge_requests/N`) into
  `(repo, iid)`, then call `glab mr view <iid> -R <repo> --output json`.
  `RealTeaClient` uses `tea api` against the PR-by-index endpoint since `tea
  pulls` doesn't take a bare URL either. `observe_pr_status()` resolves the
  right client via `hostclient.client_for` keyed on the URL's own host (not
  the caller's ambient repo) since one VK board can hold cards from repos on
  different backends.
- `pr_state.py:_default_close_gh_issue(repo, issue_number)` — this one maps
  directly onto the **existing** `GhClient.edit_issue_state(repo, number,
  state="CLOSED")` method; no new Protocol surface needed, just swap the
  subprocess default for a client call, with the client resolved the same
  per-repo way.
- Both changes are additive-default-parameter (existing injected-callable
  test seams stay for unit tests); production wiring in `bridge_cli.py`
  drops the raw-`gh`-subprocess defaults entirely.

### 7. fr-dispatch prompt genericization

`fr_dispatch/prompt.py`'s `_deps_line`/`build_prompt` hardcode `gh issue
view ... --json state` and "GitHub Issue gh#N". Both become backend-
parameterized: `build_prompt` gains a `backend: HostBackend` (or derives it
via `detect_backend`) and selects the verify-command text and noun
("GitHub Issue" / "GitLab Issue" / "Gitea Issue") from a small per-backend
phrase table, so a dispatched agent working a GitLab-backed phase is told to
run `glab issue view <n> -R <owner/repo> --output json`, not `gh issue view`.

**Correction to the original research pass:** `fr_dispatch/__init__.py`'s
`tick()` "stamp `fr:synced`" step (`gh.ensure_labels(...)`/
`gh.edit_issue_labels(...)`) is **not** actually hardcoded to GitHub — both
calls run against the `gh: GhClient` parameter `tick()` already receives, so
passing a `RealGlabClient`/`RealTeaClient` there works with **zero code
change**. The only real fix `fr_dispatch/__init__.py` needs is its `from
fr._urls import parse_issue_url` import picking up §2's generalized parser
automatically. Worth stating explicitly so implementation doesn't duplicate
work chasing a coupling that the Protocol design already avoided.

### 8. Isolation lifecycle

`fr/isolation/local.py`'s `_resolve_default_branch` and `_pr_from` currently
call `gh repo view`/`gh pr view` inline through the `Runner` callable
(deliberately a *different* seam than `GhClient` — see the module's own "every
external call goes through runner" docstring). Both gain a backend branch:
resolve via `_hosts.detect_backend(self.repo_root)` once, then dispatch to
`gh`/`glab`/`tea` equivalents:

- Default branch: `gh repo view --json defaultBranchRef --jq
  .defaultBranchRef.name` → `glab repo view -F json --jq
  .default_branch` / `tea repos --output json` (confirm exact field name
  against a live repo).
- PR/MR-for-branch lookup (`_pr_from`, used by `status`/`down`/`gc`/
  `verify_merge`): `gh pr view <branch> --json state,url` → `glab mr view
  <branch> --output json` / `tea pulls list --output json` filtered to the
  branch (Gitea's CLI has no direct "PR for this branch" single-shot query
  the way `gh`/`glab` do — confirm during manual verification, §Testing;
  worst case this falls back to listing open PRs and matching `head` branch
  client-side, which is a real but bounded degradation, not a missing
  capability).

This is the one place where "full pipeline" costs real design care: isolation
already had a *second* seam (the `Runner` callable) independent of
`GhClient`, and this PR teaches that seam to do its own backend branch rather
than merging it into `GhClient` — merging would mean every isolation
lifecycle call pays the cost of constructing a full `GhClient` adapter for a
two-field lookup; keeping it a lightweight parallel branch is proportionate.

### 9. Devcontainer scaffold — `fr/isolation/scaffold.py`

`GH_FEATURE` (unconditional today) becomes backend-conditional:

```python
HOST_CLI_FEATURE: dict[HostBackend, str | None] = {
    "github": "ghcr.io/devcontainers/features/github-cli:1",  # official feature exists
    "gitlab": None,  # no feature exists — postCreateCommand install instead
    "gitea": None,   # same
}
HOST_CLI_POST_CREATE: dict[HostBackend, str] = {
    "gitlab": "curl -fsSL https://gitlab.com/gitlab-org/cli/-/releases/permalink/latest/downloads/... -o /usr/local/bin/glab && chmod +x /usr/local/bin/glab",
    "gitea": "curl -fsSL https://dl.gitea.com/tea/... -o /usr/local/bin/tea && chmod +x /usr/local/bin/tea",
}
```

(Exact download URLs/checksums pinned properly at implementation time — both
projects publish versioned release binaries; this is mechanical, not a design
question.) `scaffold_profile()` gains a `backend` param threaded from
`fr-init`'s interview answer; `POST_CREATE` is composed from the base `fr`
install plus the backend's CLI-install snippet when the feature table has no
entry.

### 10. Acceptance scaffold — `fr/acceptance/scaffold.py`

`WORKFLOW_TEMPLATE` (GitHub Actions, `gh issue` calls, written to
`.github/workflows/acceptance-report.yml`) gets two siblings:

- `WORKFLOW_TEMPLATE_GITEA` — same trigger/job/step YAML shape (Gitea Actions
  is deliberately GitHub-Actions-compatible), `gh issue`/`gh api` calls
  swapped for `tea` equivalents, written to **`.gitea/workflows/
  acceptance-report.yml`** (not `.github/workflows/` — confirmed directory
  convention, §capability matrix). Doc note in the generated file: Gitea
  Actions must be enabled per-repo and needs a self-hosted `act_runner`
  registered — this workflow won't just start working the way a fresh
  GitHub/GitLab repo's does.
- `WORKFLOW_TEMPLATE_GITLAB` — genuinely different schema (`.gitlab-ci.yml`
  at repo root, `stages:`/`script:` not `on:`/`jobs:`/`steps:`), `glab`
  calls for the issue-upsert step. Written to the repo root, not
  `.github/workflows/`.

`init(root, org, repo, backend)` picks the template + destination path by
`backend`; `MATRIX_TEMPLATE`/`RULE_TEMPLATE`/`GITIGNORE_LINE` are backend-
independent and unchanged.

### 11. Testing strategy

- **Unit, per adapter** — `FakeGlabClient`/`FakeTeaClient` (or a single
  parameterized `FakeGhClient` reused across all three backends, since the
  Protocol shape is identical — the fixture DATA is what varies, not the
  fake's structure) exercising every `GhClient` method, mirroring
  `tests/unit/test_real_ghclient.py`'s coverage but with each backend's own
  raw shapes (GitLab's REST issue/MR JSON, Gitea's REST issue/PR JSON) rather
  than reusing GitHub's GraphQL-shaped fixtures verbatim — the existing
  fixtures do not generalize (per the original research pass).
- **`_hosts.detect_backend`** — unit tests over the 3-tier resolution
  (explicit config → hostname heuristic → github fallback), including a
  self-hosted-hostname case that must NOT silently resolve to any default.
- **Manual, back-loaded (fr-goal §5)** — a dedicated last phase, NOT gating
  any agentic phase before it: smoke-test each adapter's CLI wrapper against
  a real, operator-supplied GitLab.com project and a real Gitea instance
  (gitea.com or self-hosted) — `glab`/`tea` are real Go binaries whose exact
  JSON field names this spec asserts from documentation and (for `glab`)
  `--help` output, not a live authenticated call; the fakes only prove our
  shaping logic is internally consistent, not that the real CLI emits what we
  assumed. Checklist: create an issue, add/remove a label, observe a linked
  MR/PR, read a file via the contents lookup, close via state edit. The PR
  ships with this phase deliberately unimplemented — the operator runs it
  whenever they have (or set up) the credentials, same pattern as any other
  back-loaded manual phase.

## Non-goals

- **Bitbucket** — explicitly descoped (§Decisions). The adapter shape this
  PR establishes (`GhClient` Protocol + `hostclient.client_for` + `_hosts`
  detection) is designed so adding it later is a new adapter module plus a
  new `HostBackend` literal member, not a rearchitecture — but the Issues-vs-
  Jira and CLI-vs-direct-API questions are real design decisions of their
  own, deferred.
- **GitHub Enterprise Server / self-hosted GitLab / self-hosted Gitea beyond
  what the `host` config key already threads through** — `gh`/`glab`/`tea`
  all support pointing at a non-SaaS host already (this is exactly what the
  `host:` config key selects), so no new code is needed for that axis beyond
  what §1 already covers; no separate design work here.
- **Renaming `GhClient`** — deliberately kept (§3) to avoid a ~30-file
  cosmetic diff with no behavior change.
- **CI/pipeline status parity across backends** — each backend's adapter
  produces fr's own normalized `PASS`/`FAIL`/`PENDING`/`NONE` vocabulary from
  its own raw states (§4/§5), but no attempt is made to unify GitLab
  pipeline stages or Gitea Actions runs into anything richer than that
  existing 4-value contract.
- **Migrating existing GitHub-backed repos' data** — nothing about existing
  `fr:*` labels, plan `tracking_issue` URLs, or VK card titles on GitHub-
  backed repos changes; this PR is purely additive for new backends.

## Acceptance rows (added at spec time, presented at spec review)

- **`multibackend-gitlab-tracking`** — "An operator can run `fr apply`
  against a GitLab-backed repo and see phases rendered/observed/diffed/
  applied as GitLab Issues with correctly-shaped GitLab labels (color,
  length)." Business-level: this is the core "GitLab support" claim.
  Capability: multi-backend git hosting.
- **`multibackend-gitea-tracking`** — same claim for Gitea.
- **`multibackend-isolation-lifecycle`** — "`fr isolation up/status/down/gc`
  resolves the default branch and checks PR/MR-merge state correctly against
  a GitLab- or Gitea-backed repo, with zero `gh`-specific calls." Business-
  level because it's the difference between isolation *working at all* on a
  non-GitHub repo vs. silently shelling out to a CLI that doesn't apply.
- **`multibackend-vk-dispatch`** — "The VK dispatch bridge polls PR/MR status
  and auto-closes tracking Issues correctly for a GitLab- or Gitea-backed
  phase." Business-level: without this, "full pipeline" support is only
  tracking, not dispatch, which was the exact distinction the operator's Q2
  answer chose to close.
- **`multibackend-scaffold`** — "`fr init scaffold` on a GitLab- or Gitea-
  backed repo installs the right CLI into the devcontainer (not
  `github-cli`), and `fr acceptance init` generates a working CI workflow in
  the right location and schema for that backend." Business-level: this is
  what an operator actually sees the first time they scaffold a non-GitHub
  repo.

All four target `status: not-implemented` until the corresponding phase
lands; levels are added as each phase's tests land, per the acceptance-matrix
rule (`.claude/rules/acceptance-matrix.md`).

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-07-09-multi-backend-git-host-adapters | `derio-net/super-fr` | `2026-07-09-multi-backend-git-host-adapters` | — |

## References

- `packages/fr/src/fr/ghclient.py`, `real_ghclient.py`, `gh.py` — the
  existing single-backend implementation this spec generalizes.
- `packages/fr/src/fr/_urls.py`, `labels.py`, `states.py` — shared vocabulary
  reused (mostly unchanged) across all three backends.
- `packages/fr-dispatch/src/fr_dispatch/__init__.py`, `prompt.py`,
  `protocols.py` — the dispatch orchestrator and prompt builder this spec
  genericizes; `protocols.py`'s `Runner` Protocol was already host-agnostic
  by design and needed no change.
- `packages/fr-vk/src/fr_vk/pr_observe.py`, `pr_state.py`, `dispatch.py`,
  `workspaces.py` — the bypass call sites and card-title convention this spec
  fixes/consolidates.
- `packages/fr/src/fr/isolation/local.py`, `scaffold.py` — the second
  (Runner-callable) seam and the devcontainer scaffold this spec extends.
- `packages/fr/src/fr/acceptance/scaffold.py` — the CI-workflow template
  this spec adds two siblings to.
- GitLab CLI: https://gitlab.com/gitlab-org/cli (source + docs), verified
  live via the installed `glab` 1.89.0 binary.
- Gitea CLI (`tea`): https://gitea.com/gitea/tea, verified live via
  `brew install tea` (0.14.2) — **the rendered gitea.com README undercounts
  the real binary's commands (e.g. omits `tea api`); trust `--help` output
  over the website if they ever disagree again.**
- Gitea Actions: https://docs.gitea.com/usage/actions/overview,
  https://docs.gitea.com/usage/actions/quickstart (workflow directory,
  GitHub-Actions-compatibility claim, opt-in + self-hosted-runner
  requirement).
- Bitbucket Cloud Issue Tracker REST API (all endpoints marked Deprecated):
  https://developer.atlassian.com/cloud/bitbucket/rest/api-group-issue-tracker/.
- Unofficial Bitbucket CLI (`bkt`, evaluated and not depended on this PR):
  https://github.com/avivsinai/bitbucket-cli.
