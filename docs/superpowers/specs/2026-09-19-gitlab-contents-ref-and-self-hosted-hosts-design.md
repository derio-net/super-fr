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
- ~~**Resolving a self-hosted host to its real backend.**~~ This was a
  non-goal when the spec was written — §1 gap 3 and §4.D settled for warning
  that `fr` was guessing. Phase 5 showed the compromise does not survive
  contact with the **bridge**, which has a URL and no config to read, so the
  operator lifted it mid-run. See §4.C2; the warning stays, because a repo
  that *can* declare `backend:` still should.
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

Captured through `subprocess.run(..., capture_output=True)` — i.e. exactly what
`fr.glab._run_glab` sees — rather than read off a terminal, because **the two
streams carry different halves of the error and only one of them survives
today**:

| case | `stderr` (what `GlabError` keeps) | `stdout` (what `_run_glab` discards) |
|---|---|---|
| missing `ref` | `glab: HTTP 400` | `{"error":"ref is missing, ref is empty"}` |
| absent file | `glab: 404 File Not Found (HTTP 404)` | `{"message":"404 File Not Found"}` |
| absent project | `glab: 404 Project Not Found (HTTP 404)` | `{"message":"404 Project Not Found"}` |
| absent dir (tree) | `glab: 404 invalid revision or path Not Found (HTTP 404)` | `{"message":"404 invalid revision or path Not Found"}` |
| no token for host | rich-boxed `ERROR` / `Unauthenticated.` + width padding | *(empty)* |

Two consequences, both load-bearing:

1. **The operator's repro saw a diagnostic that `fr` never sees.** Typed at a
   shell, `{"error":"ref is missing, ref is empty"}` is right there. Through
   `fr`, `GlabError` is built from `stderr` alone, so the error reads
   `glab: HTTP 400` and the sentence naming the actual fault is dropped on the
   floor. §4.B therefore also fixes `_run_glab`: making an error *propagate* is
   worth little if what propagates cannot be read.
2. **The auth failure carries no HTTP status code at all**, and is rendered
   through rich with width-dependent padding. A predicate that classified
   errors by status code would mis-file it, and a fixture pinning that padding
   byte-for-byte would pass or fail by terminal width.

(An earlier draft of this spec claimed glab wrote the body to *both* streams.
That was an artifact of zsh's `MULTIOS` mishandling `2>&1 1>/dev/null` in the
shell used to check it — a reminder that a transcript is only evidence of what
the capture method could see. The table above was taken from Python.)

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

Patterns come from the captured strings in §2.A, and are deliberately
**anchored**: `http 404` (glab's own summary) and `"message":"404 ` (the API
body). A bare `"404" in text` is refused — the probed path is echoed in some
glab errors, so `errors/404.md` would make a genuine 400 read as "absent",
which is the bug class this function exists to close.

**`_run_glab` must also stop discarding stdout**, or the second pattern can
never match and a propagated error is unreadable (§2.A consequence 1).
`GlabError` gains a `stdout` field and the message folds the body in:

```python
# glab splits an error across both streams: its own summary on stderr, the
# API's JSON on stdout. Keeping only stderr turns "ref is missing, ref is
# empty" into a bare "glab: HTTP 400" — the fault named, then forgotten.
parts = [s for s in (exc.stderr.strip(), (exc.stdout or "").strip()) if s]
msg = " — ".join(parts) or f"glab exited with code {exc.returncode}"
raise GlabError(msg, stderr=exc.stderr or "", stdout=exc.stdout or "",
                returncode=exc.returncode) from exc
```

`stdout` is keyword-only with a `""` default, so every existing `GlabError(...)`
construction and test is untouched. `is_not_found` and `is_transient` then read
both streams through one shared `_haystack`.

`RealGlabClient.file_exists` returns `False` only when `is_not_found`, and
re-raises otherwise. `list_dir` gets the same treatment, for the same reason —
it answers the plan-folder half of the reachability probe.

Blast radius, from §2.B: `fr.migrate` already swallows (`except Exception:
pass`) and blocks archival either way — unchanged. `fr.spec` already catches,
caches the negative, and degrades the row with a note (`spec.py:45-50` of
`compute_status` — `except Exception as e: fail_note = f"cross-repo read of
{ref.repo} failed: {e}"`), so a raised error's text now reaches the operator's
`fr spec status` row verbatim instead of the row reporting a phantom empty
folder — and with the message fix above, that text is now
`glab: HTTP 400 — {"error":"ref is missing, ref is empty"}` rather than a bare
status line. `reachability` has no live caller; when
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

(`fr.glab` imports `os` for the first time to do this.)

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

### C2. The forge a URL names — `backend_for_url` (added 2026-09-19, mid-run)

§4.C threads a *host*. It does not help the one consumer that has no
checkout at all, and phase 5 proved why: for a **bare URL**,
`backend_for_hostname` and `self_hosted_hostname` are mutually exclusive by
construction of the same `DEFAULT_HOST_BACKENDS` table. Verified live:

```
https://gitlab.com/g/p/-/merge_requests/7                 -> gitlab, host None
https://gitlab.local.gebit.de/…/-/merge_requests/7        -> github, host set   (!)
```

So the VK bridge polling a self-hosted GitLab MR does not merely lose the
host — **it picks the GitHub CLI**. §4.C's threading in `fr_vk.pr_observe`
could never fire, which made it the very thing this spec exists to remove: a
parameter written, read, and consumed by nothing.

§1's non-goals allowed "documented" for gap 2 (`_hosts` resolving a
self-hosted host to `github`), and for `fr apply` that is honest — an
operator declares `backend:` in `.devcontainer/fr-profiles.yaml`. **For a
bare URL there is no repo and therefore no configuration to document**, so
the box cannot be closed that way. The operator chose to fix it.

The URL's own **path** names the forge, needing no configuration:

| forge | PR/MR path | issue path |
|---|---|---|
| GitLab | `/-/merge_requests/N`, or `/merge_requests/N` pre-dash | `/-/issues/N` |
| Gitea | `/pulls/N` | `/issues/N` |
| GitHub | `/pull/N` | `/issues/N` |

`_hosts.backend_for_url(url)` matches the path against that table
most-specific-first (`/pulls/` before `/pull/`, so Gitea is never read as
GitHub) and falls back to `backend_for_hostname` when no shape matches.

**`/issues/N` is deliberately not in the table.** It is both GitHub's and
Gitea's shape, so it cannot discriminate; leaving it out preserves the
existing documented Gitea boundary instead of replacing a known limit with a
guess. `fr_dispatch.prompt`'s
`test_prompt_backend_wording_gitea_hostname_alone_is_not_enough` is the
tripwire: if the table ever grows greedy enough to pass that test, it is
wrong.

Three call sites hold a URL and no checkout, and all three switch:
`fr_vk.pr_observe` (which is what finally makes §4.C's host threading
reachable), `fr_vk.pr_state._close_linked_gh_issue`, and
`fr_dispatch.prompt._backend_for_tracking_url` (a self-hosted GitLab phase's
prompt now says `glab issue view`, not `gh issue view`).

**What is still not fixed, and why.**
`pr_state._default_close_gh_issue` now gets the right *backend* but still no
*host*: its public `closer: Callable[[str, str, str], None]` — two call
sites and every test double — has no room for one, and widening that arity
is a bridge-wide change beyond this issue. So on a self-hosted instance the
belt-and-braces Issue auto-close builds a GitLab client aimed at
`gitlab.com` and fails non-fatally with a logged warning. Stated in the PR
body, carried as an open journal finding, not papered over.

### D. Loud degradation

Two silences become one-line warnings on stderr, each emitted **once** per
process per distinct host (a module-level guard set — `detect_backend` is called
often and must not become chatty):

1. **`_hosts.detect_backend`** — no explicit `backend:` and an origin hostname
   that is not in `DEFAULT_HOST_BACKENDS`:

   > `warning: origin host 'gitlab.local.gebit.de' is not a recognized forge; assuming backend "github". Declare it: backend: gitlab in .devcontainer/fr-profiles.yaml (or fr init scaffold --backend gitlab).`

   The behaviour is unchanged — `"github"` is still returned, so no repo's
   resolution moves. Only the silence is fixed.

2. **`hostclient.client_for`** — an **explicitly declared** `host:` for a
   backend whose adapter does not thread it (`github`, `gitea`):

   > `warning: host 'git.example.com' is declared in .devcontainer/fr-profiles.yaml but fr does not thread a host to backend "github" — the CLI's own host resolution applies instead. See gh-486.`

   This is the non-goal in §1 made audible: accepting a `host:` and ignoring it
   in silence is the same class of failure as the bug being fixed.

   **It warns on a declared host only, never a derived one** — and that is why
   it lives in `client_for` rather than `client_for_backend`. With §4.C's
   origin-hostname fallback, a **GitHub Enterprise** repo (origin
   `github.corp.com`) resolves a host for a backend fr does not thread, and
   would trip this warning on every call — for a configuration that works
   perfectly well, since `gh` resolves its own host from the same remote. A
   derived host is an inference; a declared one is an operator expectation fr
   is quietly failing. Only the second is worth a warning.

   `client_for` is also the only layer that can tell them apart, so `_hosts`
   exposes both: `declared_host(repo_root)` (the raw `host:` key — today's
   `host_for` behaviour) and `host_for(repo_root)` (declared, else derived).
   `client_for_backend` stays provenance-blind, which keeps `fr_vk.pr_observe`
   — which derives a host from a bare PR URL — correctly silent.

Warnings print to stderr, so JSON output modes are unaffected. `fr._hosts`
already prints nothing today; the precedent for a library-module warning is
`isolation/scaffold.py:209`.

### E. Docs

- **`README.md`** — a "Self-hosted instances" paragraph under the existing
  backend material (`README.md:466-478`): declare `backend:`, the host is taken
  from the git remote, `host:` overrides it, `GITLAB_HOST` is what reaches
  `glab`, and gh/tea are not threaded yet.
- **`plugins/super-fr/skills/fr-init/SKILL.md`** — a **correction**, not an
  addition. Lines 78-80 today instruct the operator to pass `--backend`/`--host`
  on *every* profile call for a non-GitHub repo
  (`fr init scaffold ... --backend gitlab --host gitlab.mycorp.com`). After
  §4.C that is no longer true: `--host` becomes **optional** for GitLab — the
  host is derived from the git remote — and is the override for when the
  remote's hostname is not the API host. The skill must say the new thing,
  because an instruction to set a key that is now redundant is how the dead
  last mile got built in the first place.
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
| A derived host is one `glab` holds no token for, so every call fails. | It fails as glab's own `Unauthenticated`, propagated as `GlabError` — and §4.B now lets that propagate rather than reading it as "file absent". Documented in README beside the derivation, since the fix is `glab auth login --hostname <host>`. |
| The origin hostname is not the API host (a vanity remote, or SSH on another name). | Exactly what the explicit `host:` key is for. §4.D's warning does not fire in this case, because the operator declared it and the GitLab adapter honours it. |

## 6. Test plan

Unit (CI, `uv run pytest`):

1. `file_exists`, `read_file`, `list_dir` each send `ref=HEAD` — asserted by
   **capturing the request args**, the guard §2.C shows was missing.
2. `is_not_found` maps every captured 404 shape (§2.A) to True, and both the
   400 and the auth failure to False — including that a 400 whose text contains
   a path like `errors/404.md` does not read as absent.
3. `GlabError` carries `stdout`, and `_run_glab`'s message contains the API's
   body: a missing-`ref` failure reads
   `glab: HTTP 400 — {"error":"ref is missing, ref is empty"}`.
4. `file_exists` returns `False` on a not-found and **raises** on a 400.
5. `list_dir` returns `[]` on a not-found and raises on a 400.
6. `host_for` returns `host:` when set; the origin hostname when it is
   self-hosted; `None` for `github.com`/`gitlab.com`; `None` with no remote.
7. `_run_glab` puts `GITLAB_HOST` in the child env when a host is given, and
   does not touch `os.environ`; omits it when not.
8. Each `fr.glab` helper forwards `host` to `_run_glab`.
9. `client_for(repo_root)` builds a `RealGlabClient` carrying the resolved host.
10. `detect_backend` warns once for an unrecognized host and is silent the
   second time; its return value is unchanged.
11. `client_for_backend` warns when `host:` is set for `github`/`gitea`.
12. `backend_for_url` reads the forge off the path — GitLab's
    `/-/merge_requests/` and pre-dash `/merge_requests/`, Gitea's `/pulls/`,
    GitHub's `/pull/` — falls back to the hostname for a shapeless URL, and
    leaves the ambiguous `/issues/N` to that fallback.
13. `pr_observe` resolves backend `gitlab` **and** a self-hosted host from
    one MR URL — the combination that was unreachable before §4.C2.

Live (this PR, agent-run, transcript in the PR body — d1):

14. `file_exists` / `read_file` / `list_dir` against
    `IDermitzakis/devops-scripts` on `gitlab.local.gebit.de`, through
    `fr.hostclient.client_for_backend`, from a cwd that is **not** a GitLab
    checkout — the configuration that failed in §2.D.
15. End-to-end `fr apply` against that project: phases rendered, observed,
    diffed, applied as GitLab Issues with correctly-shaped labels (colour and
    length) — the acceptance row's own sentence, demonstrated.
16. `fr spec status` resolving a plan folder from that project (the cross-repo
    read that motivated the host override).
17. From inside a checkout carrying **only** `backend: gitlab` and no `host:`,
    `client_for` builds a `RealGlabClient` whose host was derived from the git
    remote, and reads a file with it — the spec's headline claim, which
    `client_for_backend(host=...)` does not exercise.
18. A self-hosted MR URL resolves to the GitLab adapter through
    `backend_for_url`, live — the §4.C2 fix, shown on a real URL rather than
    a constructed one.

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
