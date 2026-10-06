# Journal: 2026-10-06-glab-host-trust

<!-- fr:journal kind=repro scope=debug id=366819be5164 created=2026-10-06T13:40:43+00:00 -->
### 366819be5164 · repro · Three holes in #994's host trust seam (gh#1014, gh#1015, gh#1013)

Read, not run against a forge (the gaps are structural). (1) gh#1014: RealGlabClient(host=h) threads GITLAB_HOST=h into every glab call with no check that glab is logged into h; h comes from MR URLs and a cloned repo's committed fr-profiles.yaml. (2) gh#1015: real_ghclient._gh_runner(run) returns an injected runner unchanged, so isolation's default_branch / pr_for_branch run gh with no GH_HOST after @_hosted's gate passed; RealGlabClient.default_branch / pr_for_branch apply no GITLAB_HOST on either runner. (3) gh#1013: hostclient.forge_error_kind hands a GhHostRefusedError to fr.gh._classify_error as text; a refused host named e.g. git.timeout.example reads as 'warn' (transient) and gh.is_transient retries it.

<!-- fr:journal kind=root-cause scope=debug id=fdd54a21e4af created=2026-10-06T13:40:49+00:00 -->
### fdd54a21e4af · root-cause · Host trust is fr.gh-private, not a forge-adapter contract

#994 put the whole contract (gate + host env) in fr.gh._env(), reachable only from fr.gh's own subprocess paths and the gh adapter's DEFAULT runner. Every part of the seam outside that one function lacks it: the glab adapter (no gate), an injected CommandRunner (no host env: the protocol has no env parameter, so the host cannot be handed to it), and the classifier (sees a refusal as stderr text, not as its type). One cause, three symptoms; the fix makes the contract the adapters': a typed HostRefusedError both backends' refusals inherit, a host env overlay every runner receives, a glab gate reading the config file glab itself reads.
