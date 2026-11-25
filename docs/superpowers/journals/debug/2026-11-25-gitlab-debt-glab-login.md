<!-- fr:journal-schema=4 -->
# Journal: 2026-11-25-gitlab-debt-glab-login

<!-- fr:journal kind=repro scope=debug id=6277c87e16c7 created=2026-11-25T18:42:41+00:00 -->
### 6277c87e16c7 · repro · Scaffolded GitLab technical-debt job refuses every run with FR_DEBT_TOKEN set (gh#1691)

Live on a self-hosted GitLab 15.3 (host redacted) during the 9.0.0 release walks: the technical-debt job rendered by DEBT_STEP_GITLAB exports GITLAB_TOKEN=$FR_DEBT_TOKEN and GITLAB_HOST=$CI_SERVER_HOST, then runs fr debt issue --yes, which fails with GlabHostRefusedError from fr.glab.host_env.

<!-- fr:journal kind=root-cause scope=debug id=412aef2f6009 created=2026-11-25T18:42:43+00:00 -->
### 412aef2f6009 · root-cause · The job never logs glab in, and fr's trust gate (gh#1014) does not count a GITLAB_TOKEN as a login

fr.glab.host_env trusts only hosts in glab's config.yml (known_hosts). The scaffold set env vars alone, so CI_SERVER_HOST is never a known host and every glab call fr makes is refused before a process starts. The gate is correct; the template is missing the login.
