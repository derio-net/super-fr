<!-- fr:journal-schema=4 -->
# Journal: 2026-11-25-gitlab-debt-glab-login

<!-- fr:journal kind=repro scope=debug id=6277c87e16c7 created=2026-11-25T18:42:41+00:00 -->
### 6277c87e16c7 · repro · Scaffolded GitLab technical-debt job refuses every run with FR_DEBT_TOKEN set (gh#1691)

Live on a self-hosted GitLab 15.3 (host redacted) during the 9.0.0 release walks: the technical-debt job rendered by DEBT_STEP_GITLAB exports GITLAB_TOKEN=$FR_DEBT_TOKEN and GITLAB_HOST=$CI_SERVER_HOST, then runs fr debt issue --yes, which fails with GlabHostRefusedError from fr.glab.host_env.
