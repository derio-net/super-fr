# Journal: 2026-10-06-forge-remainder

<!-- fr:journal kind=decision scope=plan id=p1-gh-host-trust-gate created=2026-10-06T08:09:24+00:00 phase=1 -->
### p1-gh-host-trust-gate · decision · GH_HOST is threaded only for a host gh is logged into; any other fails closed (phase 1)

`gh help environment`: GH_ENTERPRISE_TOKEN "will be used when a command targets a GitHub
Enterprise Server host". So GH_HOST=<any non-github.com host> sends the operator's enterprise
token to that host. The hosts fr threads come from sources that are not fully trusted: a URL
(`client_for_url`, fed by PR/issue URLs) and a cloned repo's committed
`.devcontainer/fr-profiles.yaml` (`client_for`'s declared host). A hostile value would leak
the credential.

So `fr.gh.known_hosts()` reads the top-level keys of gh's own `hosts.yml`
(`$GH_CONFIG_DIR`, else `$XDG_CONFIG_HOME/gh`, else `~/.config/gh`; missing, unreadable or
malformed = empty set), the hosts the operator ran `gh auth login` for. `_env()` is the one
enforcement point, so every gh subprocess path (`_run_gh`, `view_pr_body`, phase 2's lookups)
inherits it: a scoped host not in that set raises GhError ("GitHub host '<h>' is not one gh is
logged into; run `gh auth login --hostname <h>` ...") before any subprocess starts. It never
falls back to github.com, which would be #892's wrong-target write again. The check is lazy
(call time, not `RealGhClient.__init__`), so building a client reads nothing. RealGhClient
methods that already fail soft on GhError (file_exists, list_dir, list_linked_prs,
pr_status_by_url, issues_enabled) return their soft value for an unknown host, still with no
subprocess. Orchestrator decision; the spec records it in R6/§4.E.

<!-- fr:journal kind=decision scope=plan id=p1-hosted-decorator created=2026-10-06T08:09:24+00:00 phase=1 -->
### p1-hosted-decorator · decision · RealGhClient scopes its host with one @_hosted decorator, guarded structurally (phase 1)

Each RealGhClient method that reaches fr.gh is wrapped by `_hosted`, which enters
`fr.gh.host_scope(self._host)` and marks the wrapper `__fr_hosted__`.
`test_gh_host.py::test_every_gh_method_is_hosted` fails if any method whose source mentions
`_gh.` lacks it (shown red by removing one decorator), so a new method cannot silently run
against gh's default host.

<!-- fr:journal kind=discovery scope=plan id=p1-smoke-baseline created=2026-10-06T08:09:24+00:00 phase=1 -->
### p1-smoke-baseline · discovery · Smoke baseline green; PR 994 CI not red (phase 1)

test_hostclient.py + test_tripwire_forge_adapter.py passed (17) before any change. `gh pr
checks 994`: every finished job passed, the test shards were still pending, nothing red.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-10-06T08:09:24+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

client_for gained one backend branch and a narrowed warning condition; the two host sources (declared for github, host_for for gitlab) are deliberately different, so there is no duplication to fold.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-10-06T08:09:24+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

client_for_url is the promoted body of pr_state's private helper, moved unchanged; pr_state and make_client each became a one-line call. Nothing left to clean.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-10-06T08:23:42+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Soft-fail methods swallowed the trust-gate refusal into []/None/False (phase 1)

list_linked_prs, pr_status_by_url, file_exists, list_dir and issues_enabled catch GhError, so a refused host read as "no PR" / "no file", and a test enshrined it.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-10-06T08:23:42+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · A declared github.com host was threaded, demanding a hosts.yml login in token-only CI (phase 1)

client_for passed the declared host straight through. github.com is gh's own default and must never become GH_HOST.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-10-06T08:23:42+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · Test gaps: nested host_scope, pr_state routing, weak hosted-method scan (phase 1)

The reviewer asked for a nested-scope test, a pr_state call-site test and a stricter test_every_gh_method_is_hosted heuristic.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-10-06T08:23:42+00:00 phase=1 state=open review_scope=out -->
### p1-r4 · finding [open] (reviewer: out of scope) · _classify_error classifies by stderr text; the refusal reads as unknown (phase 1)

Pre-existing text classification. The refusal message matches no pattern today, so nothing changes. It is fragile only if someone later adds a pattern that catches it.

<!-- fr:journal kind=finding scope=plan id=p1-x1 created=2026-10-06T08:23:42+00:00 phase=1 state=open review_scope=out -->
### p1-x1 · finding [open] (reviewer: out of scope) · GitLab host threading (gh#490) passes URL/config hosts to glab without a trust gate (phase 1)

Raised by the orchestrator while handling the background security review. glab is handed hosts derived from MR URLs and from fr-profiles.yaml, and a GITLAB_TOKEN in the environment may be sent to whichever host glab targets. It predates this change (gh#490/#865), so it is not caused here. It is the same class as the GitHub gate this phase added.

<!-- fr:journal kind=review scope=plan id=p1-review-r1 created=2026-10-06T08:23:42+00:00 phase=1 -->
### p1-review-r1 · review · Independent review of phase 1: 4 findings (p1-r1..p1-r4) (phase 1)

A dispatched reviewer checked the ContextVar/host_scope/_env mechanics, subprocess coverage in fr.gh, the hosts.yml trust gate, client_for/client_for_backend/client_for_url and the tests. Raised p1-r1, p1-r2, p1-r3 (in scope) and p1-r4 (out of scope). The orchestrator added p1-x1 (out of scope).

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-10-06T08:23:42+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Soft-fail methods swallowed the trust-gate refusal into []/None/False (phase 1)

GhHostRefusedError(GhError) is raised by _env(), and RealGhClient's @_hosted wrapper runs the gate before any method body, so no soft-fail except block sees it. Parametrised test over all five methods asserts the raise and that no subprocess started (04efa619c).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-10-06T08:23:42+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: A declared github.com host was threaded, demanding a hosts.yml login in token-only CI (phase 1)

client_for_backend normalises the GitHub host through _hosts.self_hosted_hostname, so github.com is never threaded. test_a_declared_saas_github_host_is_not_threaded. The refusal text now says a GH_ENTERPRISE_TOKEN alone does not count as a login.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-10-06T08:23:42+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: Test gaps: nested host_scope, pr_state routing, weak hosted-method scan (phase 1)

Added test_a_nested_host_scope_restores_the_outer_host. The hosted-method scan now also matches `from fr.gh import` / `from fr import gh`. pr_state routing was already pinned by test_the_default_close_targets_the_self_hosted_host and test_..._passes_no_host_for_a_saas_url, which patch hostclient.client_for_backend under client_for_url, so no new test was needed there.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-10-06T08:23:42+00:00 phase=1 state=open resolves=p1-r4 out_of_scope=true -->
### p1-r4-resolved · finding [out-of-scope] · resolves p1-r4: _classify_error classifies by stderr text; the refusal reads as unknown (phase 1)

Pre-existing stderr-text classification, unchanged by this phase. The refusal is its own subclass now, so a caller can match on type rather than text.

<!-- fr:journal kind=finding scope=plan id=p1-x1-resolved created=2026-10-06T08:23:42+00:00 phase=1 state=open resolves=p1-x1 out_of_scope=true -->
### p1-x1-resolved · finding [out-of-scope] · resolves p1-x1: GitLab host threading (gh#490) passes URL/config hosts to glab without a trust gate (phase 1)

It predates this change (gh#490). File it as a follow-up to give glab the same hosts trust gate.

<!-- fr:journal kind=finding scope=plan id=p1-x2 created=2026-10-06T08:26:59+00:00 phase=1 state=fixed review_scope=in -->
### p1-x2 · finding [fixed] (reviewer: in scope) · p1-r1's fix let the trust-gate refusal fail fr init scaffold's GHE issues probe (phase 1)

Caught by the post-review full suite (test_github_enterprise_is_asked_as_host_owner_repo): issues_enabled_for passed the host to the GitHub client although the probe already names it as HOST/OWNER/REPO, so the now-unswallowed GhHostRefusedError failed the scaffold for a host gh was not logged into. Fixed in 742c56a68: the probe gives the GitHub client no host. pr_observe, the other URL-host caller, catches and logs every error, so its refusal is a logged warning naming gh auth login.
