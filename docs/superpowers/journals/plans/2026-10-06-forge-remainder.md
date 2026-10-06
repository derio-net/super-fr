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
