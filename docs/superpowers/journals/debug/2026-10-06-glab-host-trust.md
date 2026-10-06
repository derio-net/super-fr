# Journal: 2026-10-06-glab-host-trust

<!-- fr:journal kind=repro scope=debug id=366819be5164 created=2026-10-06T13:40:43+00:00 -->
### 366819be5164 · repro · Three holes in #994's host trust seam (gh#1014, gh#1015, gh#1013)

Read, not run against a forge (the gaps are structural). (1) gh#1014: RealGlabClient(host=h) threads GITLAB_HOST=h into every glab call with no check that glab is logged into h; h comes from MR URLs and a cloned repo's committed fr-profiles.yaml. (2) gh#1015: real_ghclient._gh_runner(run) returns an injected runner unchanged, so isolation's default_branch / pr_for_branch run gh with no GH_HOST after @_hosted's gate passed; RealGlabClient.default_branch / pr_for_branch apply no GITLAB_HOST on either runner. (3) gh#1013: hostclient.forge_error_kind hands a GhHostRefusedError to fr.gh._classify_error as text; a refused host named e.g. git.timeout.example reads as 'warn' (transient) and gh.is_transient retries it.
