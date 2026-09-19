# GitLab contents reads and self-hosted host targeting — design

Status: draft (fr-brainstorming, 2026-09-19)
Branch: `fix/gh-486-gitlab-contents-ref`
Issue: [super-fr#486](https://github.com/derio-net/super-fr/issues/486)
Operator decisions recorded in §3 (d1–d5).

## 1. Goal

Make `fr`'s GitLab adapter work against a real GitLab instance, and make the
claim that it does **provable** rather than asserted.

Three things ship together because they are one failure:

1. `RealGlabClient.file_exists` / `.read_file` omit GitLab's **mandatory `ref`**
   query parameter, so every contents read fails against any live instance.
2. `file_exists` collapses *every* error into `False`, so the malformed request
   above is indistinguishable from an absent file. A 400 became a wrong answer.
3. There is no working way to point `fr` at a **self-hosted** instance. The
   declaration surface is complete — `fr init scaffold --host` writes `host:`
   into `.devcontainer/fr-profiles.yaml`, `fr._hosts.host_for()` reads it back,
   and it is unit-tested — but **no production code path consumes it**. A dead
   last mile.

After this ships:

- every GitLab contents read pins `ref=HEAD`, branch-agnostically (the
  instance this was found on defaults to `master`, not `main`);
- a GitLab error that is **not** a not-found propagates instead of being read
  as "absent";
- a repo that declares `backend: gitlab` reaches its own self-hosted instance
  with **no further configuration** — the host is derived from the git remote,
  and `host:` overrides it;
- an unrecognized origin host that silently resolves to `github` says so;
- the `multibackend-gitlab-tracking` acceptance row is backed by a transcript
  from a live instance, not by mocks.

### Non-goals

- **Gitea.** Out of scope per the issue; `tea` stays explicitly unproven, and
  no host is threaded to it (§4.D makes that gap loud rather than silent).
- **GitHub Enterprise.** `fr.gh` is not given host threading. There is no
  evidence of a GHE user, and `fr.gh` is the highest-traffic module in the
  package — churning it without proof is exactly how the bug being fixed here
  got in. `client_for_backend` warns when `host:` is declared for a backend
  whose adapter does not thread it, so the limit is visible at the moment it
  matters. See §3 d2 for the operator's wider mandate and why this narrows it.
- **Retrofitting the other adapters' fail-soft posture.** `RealGhClient` and
  `RealTeaClient` keep swallowing every error (§3 d3).
- **Changing what `ref` means.** `HEAD` is the repository's default branch on
  the server. Reading a *specific* branch or tag through these methods is not
  a capability anything asks for today.

## 2. Background — verified live, 2026-09-19

Every line in this section was run against `gitlab.local.gebit.de` (GitLab
self-hosted, authenticated as `IDermitzakis`) from this branch's worktree.
Nothing here is inferred from documentation.

### A. The bug

```
$ glab api --hostname gitlab.local.gebit.de \
    "projects/IDermitzakis%2Fdevops-scripts/repository/files/README.md"
{"error":"ref is missing, ref is empty"}glab: HTTP 400

$ glab api --hostname gitlab.local.gebit.de \
    "projects/IDermitzakis%2Fdevops-scripts/repository/files/README.md?ref=HEAD"
{"file_name":"README.md","file_path":"README.md","size":664,"encoding":"base64",
 "ref":"HEAD",...}
```

The project's `default_branch` is **`master`** — `ref=HEAD` resolves anyway,
which is the whole reason to prefer it over a hardcoded branch name.

`list_dir`'s tree endpoint is unaffected (it defaults to the default branch):

```
$ glab api --hostname gitlab.local.gebit.de \
    "projects/IDermitzakis%2Fdevops-scripts/repository/tree?path="
[{"id":"e74f1983...","name":".github","type":"tree",...}, ...]
```

### B. Who actually calls the broken methods

| Caller | Method | Today's behaviour on GitLab |
|---|---|---|
| `fr.spec.compute_status` (`spec.py:237,242`), reached by `fr spec status` (`spec_cmd.py:71` passes `gh`) | `list_dir` + `read_file` | `list_dir` works; `read_file` raises `GlabError` → the row degrades to `Unreachable`. Loud, but wrong. |
| `fr.migrate` archival probes (`migrate.py:931-934`) | `file_exists` | Returns `False` for every variant → falls through to "confirm and re-run", which **blocks** archival. Already wrapped in `except Exception: pass`, so §4.B's fail-loud change does not alter the outcome here. |
| `fr_dispatch.reachability._missing_remotely` (`reachability.py:92-93`) | `list_dir` + `file_exists` | **Latent, not live.** `apply_cmd.py:141` calls `unreachable_inputs` with **no** `gh=`, so cross-repo refs are skipped there, and `check_reachable` has no production caller yet. This path becomes live when the dispatch cutover completes — and would then read every cross-repo artifact as unreachable. |

The issue's framing ("callers affected include the multi-repo spec rollup and
spec-archival existence probes") is correct; the reachability gate is a trap
armed for later rather than a break today.

### C. Why the unit suite is green

`tests/unit/test_real_glabclient.py` mocks `_run_glab` as `lambda args: <json>`
— the mock **discards `args`**. No test in the file can observe what was
requested, only that a request was made. The tests assert that the code calls
the function it calls.

### D. The dead last mile

```
$ grep -rn host_for packages tests docs
packages/fr/src/fr/_hosts.py:109:def host_for(repo_root) -> str | None:
tests/unit/test__hosts.py:{24,95,100,104}
docs/.../2026-07-09-multi-backend-git-host-adapters/01.yaml:43
```

Written by `fr init scaffold --host` (`init_cmd.py:44`, `scaffold.py:264`),
read by `host_for`, tested three ways — and called by **nothing** that makes
an API call.

What `glab` does without it, verified from this worktree (whose origin is
GitHub):

```
$ glab api user                                   # no host
ERROR  Unauthenticated.                           # defaulted to gitlab.com

$ GITLAB_HOST=gitlab.local.gebit.de glab api user
{"id":230,"username":"IDermitzakis",...}          # works

$ GITLAB_HOST=gitlab.local.gebit.de glab issue list --repo IDermitzakis/devops-scripts
No open issues match your search in IDermitzakis/devops-scripts.
```

Two facts the design turns on:

- **`GITLAB_HOST` works for every subcommand**, not just `glab api`. The
  `--hostname` flag does not: `glab api` accepts it, `glab label create` does
  not. A flag cannot cover all of `fr.glab`'s call sites; the env var can.
- **glab resolves the host from the current git directory** when neither is
  given. So `fr` running *inside* a GitLab checkout often gets the right host
  by accident. The override earns its keep in exactly the cases that do not:
  the cross-repo read (`fr spec status` resolving a plan in another repo on
  another host) and any process running outside the checkout (a bridge tick).

### E. `_hosts` resolution for a self-hosted host

`DEFAULT_HOST_BACKENDS` holds `github.com` and `gitlab.com` only, so
`gitlab.local.gebit.de` falls through to the `"github"` default. Documented
behaviour — but silent, and combined with (D) it means a self-hosted GitLab
repo talks to the wrong adapter until two separate keys are set.

## 3. Operator decisions (asked once, 2026-09-19)

**d1 — live verification is agent-run, end to end.** The write-path walk runs
against `https://gitlab.local.gebit.de/IDermitzakis/devops-scripts`, named by
the operator. Not a back-loaded manual phase: the agent creates the Issues and
labels itself and puts the transcript in the PR. This is the decision that lets
the acceptance row move on evidence in the same PR as the fix.

*Consequence the operator did not have to be asked twice about:* that project
has `issues_access_level: disabled`. The walk cannot run without Issues, so the
verification phase **enables Issues, runs the walk, and restores
`disabled`** — both mutations recorded in the transcript. A reversible settings
change on the operator's own private project, named by them for exactly this
purpose.

**d2 — self-hosted support: wire it, default it, and warn.** Thread `host:`
through the client factory into the subprocess environment; when `host:` is
absent, derive it from the git remote so declaring `backend: gitlab` alone
suffices; and warn when an unrecognized origin host resolves silently to
`github`.

*Narrowed in the writing, flagged for override:* the operator's chosen option
named `GITLAB_HOST / GH_HOST / tea --login`. This spec wires **glab only** and
makes the other two loud instead of silent — see §1 non-goals for why, and §4.D
for the warning that keeps the gap visible. If the operator wants gh threaded
too, it is an additive follow-up, not a redesign.

**d3 — fail-loud, GitLab only.** Narrow `RealGlabClient`'s swallow to
not-found; re-raise everything else. `RealGhClient` and `RealTeaClient` keep
today's posture — Gitea is out of scope per the issue, and GitHub's contents
endpoint needs no `ref`, so there is no evidence of harm to act on.

**d4 — the acceptance row goes to `failing` first.** `multibackend-gitlab-tracking`
is `status: ci` while the capability does not work. Per
`.claude/rules/acceptance-matrix.md`, a discovered red acceptance is set to
`failing`, which makes the `acceptance-report` workflow fail **by design**. The
row is flipped in this branch's first commit and moved to its honest resting
state once live proof lands. CI is red in between; that is the point.

**d5 — `ref=HEAD`, not a branch name.** Branch-agnostic by construction, live-
proven against a `master`-default instance (§2.A).

## 4. Design

### A. `ref` on every contents read — `fr/real_glabclient.py`

A module constant carries the ref so the three methods cannot drift apart:

```python
# GitLab's contents endpoint requires `ref`; HEAD is the server's own default
# branch, so this works on a `master` instance and a `main` one alike (live-
# proven 2026-09-19 against a master-default self-hosted instance). GitHub's
# equivalent endpoint needs no ref, which is why the adapter was written
# without one — see gh-486.
_CONTENTS_REF = "HEAD"
```

- `file_exists`: `…/repository/files/{path}?ref=HEAD`
- `read_file`: same
- `list_dir`: `…/repository/tree?path={path}&ref=HEAD`

`list_dir` does not need it (§2.A). It gets it anyway, for one reason: three
contents reads against one backend should speak one convention, and the
asymmetry is precisely what let two of the three be wrong while the third
worked. The tree endpoint's `ref=HEAD` is verified live in Phase 2 before the
change is kept — a call that works today is not broken on a hunch.

**The regression guard is the request, not the call.** Every contents test
captures `args` and asserts the query string. A test that mocks `_run_glab` as
`lambda args: …` cannot fail for this bug and is therefore not a test of it.

### B. Fail-loud — narrow the swallow

`fr/glab.py` gains a sibling to the existing `is_transient`, using the same
stderr-pattern technique on glab's own vocabulary:

```python
def is_not_found(err: GlabError) -> bool:
    """True if this error is GitLab saying the thing is absent, as opposed to
    saying the request was wrong. `file_exists` may only translate the first
    kind into `False` — reading a 400 as "absent" is what made gh-486 a wrong
    answer instead of an error."""
```

Patterns: `404`, `not found` (glab's stderr renders both `glab: HTTP 404` and
GitLab's `{"message":"404 Project Not Found"}` body). Exact strings are pinned
by tests captured from real glab output, not composed.

`RealGlabClient.file_exists` returns `False` only when `is_not_found`, and
re-raises otherwise. `list_dir` gets the same treatment, for the same reason —
it answers the plan-folder half of the reachability probe.

Blast radius, from §2.B: `fr.migrate` already swallows (`except Exception:
pass`) and blocks archival either way — unchanged. `fr.spec` already catches,
caches the negative, and degrades the row with a note — now with a truthful
error instead of a phantom empty folder. `reachability` has no live caller; when
it gains one, a propagating error must surface as a refusal message rather than
a traceback, which is that cutover's obligation and is recorded as a risk (§5).

### C. The last mile — `host:` to the subprocess

**`fr._hosts.host_for(repo_root)`** gains one fallback. Today: the `host:` key
or `None`. New: when `host:` is absent, the origin hostname — but only when it
is **not** one of `DEFAULT_HOST_BACKENDS`, so `github.com` and `gitlab.com`
still return `None` and nothing changes for a SaaS repo. Never raises, same as
today.

This is what makes `backend: gitlab` sufficient on its own: the host comes from
the remote the operator already has.

**`fr.glab`** carries the host to the process:

```python
def _run_glab(args: list[str], *, host: str | None = None) -> str:
    env = {**os.environ, "GITLAB_HOST": host} if host else None
    subprocess.run(["glab", *args], env=env, ...)
```

`GITLAB_HOST` and not `--hostname`, because only the env var covers every
subcommand (§2.D). Each public helper in `fr.glab` gains a keyword-only
`host: str | None = None` and passes it through — mechanical, explicit, and
default-None so every existing caller and test is untouched.

**`RealGlabClient(host=None)`** stores it and threads it into each call.

**`fr.hostclient`** is the seam that supplies it:

- `client_for(repo_root)` → `client_for_backend(backend, host=_hosts.host_for(repo_root))`
- `client_for_backend(backend, *, host=None)` → `RealGlabClient(host=host)`

`fr_vk.pr_observe` already resolves a backend from a bare PR URL's hostname; it
can now pass that same hostname as `host`, which is the case the factory was
shaped for.

### D. Loud degradation

Two silences become one-line warnings on stderr, each emitted **once** per
process per distinct host (a module-level guard set — `detect_backend` is called
often and must not become chatty):

1. **`_hosts.detect_backend`** — no explicit `backend:` and an origin hostname
   that is not in `DEFAULT_HOST_BACKENDS`:

   > `warning: origin host 'gitlab.local.gebit.de' is not a recognized forge; assuming backend "github". Declare it: backend: gitlab in .devcontainer/fr-profiles.yaml (or fr init scaffold --backend gitlab).`

   The behaviour is unchanged — `"github"` is still returned, so no repo's
   resolution moves. Only the silence is fixed.

2. **`hostclient.client_for_backend`** — a `host:` is supplied for a backend
   whose adapter does not thread it (`github`, `gitea`):

   > `warning: host 'git.example.com' is declared but fr does not yet target a self-hosted instance for backend "github" — the CLI's own host resolution applies. See gh-486.`

   This is the non-goal in §1 made audible. Accepting a `host:` and ignoring it
   in silence is the same class of failure as the bug being fixed.

Warnings print to stderr, so JSON output modes are unaffected. `fr._hosts`
already prints nothing today; the precedent for a library-module warning is
`isolation/scaffold.py:209`.

### E. Docs

- **`README.md`** — a "Self-hosted instances" paragraph under the existing
  backend material (`README.md:466-478`): declare `backend:`, the host is taken
  from the git remote, `host:` overrides it, `GITLAB_HOST` is what reaches
  `glab`, and gh/tea are not threaded yet.
- **`plugins/super-fr/skills/fr-init/SKILL.md`** — `--host` exists in
  `fr init scaffold` but the skill does not say when an operator needs it. One
  sentence: for a self-hosted instance it is optional (derived from the remote)
  and is the override when the remote is not the API host.
- **Explainers**: `docs/explainers/` contains no page mentioning a backend or
  GitLab (verified by grep), so no page is made stale. Per
  `.claude/rules/explainers-currency.md` this is recorded in the PR body rather
  than acted on.

### F. Acceptance matrix

Two moves and one new row.

1. **First commit**: `fr acceptance set-status --id multibackend-gitlab-tracking
   --status failing --notes "…"` (d4).
2. **After live verification**: move it with the transcript's evidence. Its
   honest resting state is **`skipped`**, not `ci` — the live walk is hand-run
   in this PR and CI does not re-run it, which is exactly what `skipped` means
   ("verification exists, not in CI — warning, backfill owed"). The new unit
   tests that assert the request go into `levels.unit`.
3. **New row** for the capability this spec adds — an operator can target a
   self-hosted instance (§7).

## 5. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `ref=HEAD` on the **tree** endpoint breaks a call that works today. | Verified live before the change is kept (Phase 2), and reverted to no-ref if it regresses. A working call is not changed on a hunch. |
| Fail-loud turns a silent wrong answer into a traceback for whoever next wires `gh=` into the reachability gate. | Recorded here and in the plan journal as that cutover's obligation: the gate must render a propagating error as a refusal message. Not fixed here — no caller exists to fix. |
| Threading `host` through every `fr.glab` helper is a wide mechanical diff. | Keyword-only with `None` default, so no existing call site or test changes. The per-helper passthrough is asserted once per helper rather than trusted. |
| The one-time warning becomes noise, or worse, breaks a parser. | stderr only, once per process per host, and `detect_backend`'s return value is unchanged. A test pins that the second call is silent. |
| Live verification mutates the operator's project. | A private project the operator named. Issues are enabled, the walk runs, Issues are restored to `disabled`; every created Issue and label is listed in the transcript so nothing is left behind unrecorded. |
| `GITLAB_HOST` in the env could leak into an unrelated `glab` call in the same process. | The env is built per `subprocess.run` call, never assigned to `os.environ`. |

## 6. Test plan

Unit (CI, `uv run pytest`):

1. `file_exists`, `read_file`, `list_dir` each send `ref=HEAD` — asserted by
   **capturing the request args**, the guard §2.C shows was missing.
2. `is_not_found` maps real glab stderr strings (404 body, `HTTP 404`) to True
   and a 400 / auth failure to False.
3. `file_exists` returns `False` on a not-found and **raises** on a 400.
4. `list_dir` returns `[]` on a not-found and raises on a 400.
5. `host_for` returns `host:` when set; the origin hostname when it is
   self-hosted; `None` for `github.com`/`gitlab.com`; `None` with no remote.
6. `_run_glab` puts `GITLAB_HOST` in the child env when a host is given, and
   does not touch `os.environ`; omits it when not.
7. Each `fr.glab` helper forwards `host` to `_run_glab`.
8. `client_for(repo_root)` builds a `RealGlabClient` carrying the resolved host.
9. `detect_backend` warns once for an unrecognized host and is silent the
   second time; its return value is unchanged.
10. `client_for_backend` warns when `host:` is set for `github`/`gitea`.

Live (this PR, agent-run, transcript in the PR body — d1):

11. `file_exists` / `read_file` / `list_dir` against
    `IDermitzakis/devops-scripts` on `gitlab.local.gebit.de`, through
    `fr.hostclient.client_for_backend`, from a cwd that is **not** a GitLab
    checkout — the configuration that failed in §2.D.
12. End-to-end `fr apply` against that project: phases rendered, observed,
    diffed, applied as GitLab Issues with correctly-shaped labels (colour and
    length) — the acceptance row's own sentence, demonstrated.
13. `fr spec status` resolving a plan folder from that project (the cross-repo
    read that motivated the host override).

Post-merge, operator-driven: none. Everything this spec claims is proven in
the PR — that is the point of the issue's "live proof, not unit tests".

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-09-19-gitlab-contents-ref-and-self-hosted-hosts | `derio-net/super-fr` | `2026-09-19-gitlab-contents-ref-and-self-hosted-hosts` | — |

## 7. Acceptance rows (born here; presented at spec review)

| id | capability | acceptance | level |
|---|---|---|---|
| `gitlab-contents-reads-live` | Multi-backend git hosting | An operator's GitLab-backed repo can be read through fr's contents API — file existence, file text, and directory listing — against a live instance whose default branch is not `main`. | unit + live |
| `gitlab-selfhosted-host-targeting` | Multi-backend git hosting | An operator whose GitLab is self-hosted reaches it by declaring `backend: gitlab` alone; `host:` overrides, and a host declared for a backend fr cannot target says so. | unit + live |
| `forge-errors-are-not-absence` | Multi-backend git hosting | A malformed or unauthorized GitLab request surfaces as an error rather than as "the file is not there". | unit |

`multibackend-gitlab-tracking` is not a new row — it is the existing row this
spec makes honest (§4.F).
