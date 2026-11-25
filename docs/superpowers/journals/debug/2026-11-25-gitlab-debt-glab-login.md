<!-- fr:journal-schema=4 -->
# Journal: 2026-11-25-gitlab-debt-glab-login

<!-- fr:journal kind=repro scope=debug id=6277c87e16c7 created=2026-11-25T18:42:41+00:00 -->
### 6277c87e16c7 · repro · Scaffolded GitLab technical-debt job refuses every run with FR_DEBT_TOKEN set (gh#1691)

Live on a self-hosted GitLab 15.3 (host redacted) during the 9.0.0 release walks: the technical-debt job rendered by DEBT_STEP_GITLAB exports GITLAB_TOKEN=$FR_DEBT_TOKEN and GITLAB_HOST=$CI_SERVER_HOST, then runs fr debt issue --yes, which fails with GlabHostRefusedError from fr.glab.host_env.

<!-- fr:journal kind=root-cause scope=debug id=412aef2f6009 created=2026-11-25T18:42:43+00:00 -->
### 412aef2f6009 · root-cause · The job never logs glab in, and fr's trust gate (gh#1014) does not count a GITLAB_TOKEN as a login

fr.glab.host_env trusts only hosts in glab's config.yml (known_hosts). The scaffold set env vars alone, so CI_SERVER_HOST is never a known host and every glab call fr makes is refused before a process starts. The gate is correct; the template is missing the login.

<!-- fr:journal kind=finding scope=debug id=42c8fe2e142e created=2026-11-25T18:55:41+00:00 state=fixed -->
### 42c8fe2e142e · finding [fixed] · DEBT_STEP_GITLAB logs glab in before the fr commands

The technical-debt job's script now starts with export GLAB_CONFIG_DIR="$(mktemp -d)" and echo "$FR_DEBT_TOKEN" | glab auth login --hostname "$CI_SERVER_HOST" --stdin (the fix proven live on a self-hosted GitLab 15.3, host redacted: fr debt issue filed the issue, fr debt archive-pr pushed and opened a draft MR). The login sits in script, after every before_script line, so glab is installed by then. Pinned by tests/unit/test_acceptance_scaffold_debt_jobs.py::test_gitlab_debt_job_logs_glab_in_before_any_fr_command (red before the fix, green after); both GitLab goldens regenerated (only the two lines and the header comment changed).

<!-- fr:journal kind=review scope=debug id=563603313dfb created=2026-11-25T18:56:23+00:00 -->
### 563603313dfb · review · Self-review of PR #1703: no findings

Checked: (1) fr.glab._config_yml reads $GLAB_CONFIG_DIR/config.yml first, as glab does, so the login's host is the one known_hosts() sees; (2) GitLab runs before_script and script in one shell, so the export persists and glab is installed before the login; (3) the token goes through stdin and is never on argv; (4) host_env stays unchanged: relaxing it would reopen gh#1014; (5) the goldens differ only by the intended lines; (6) privacy: the diff, journal and PR body name no real host, user or employer.
