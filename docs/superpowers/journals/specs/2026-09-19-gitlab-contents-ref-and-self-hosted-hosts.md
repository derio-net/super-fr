# Journal: 2026-09-19-gitlab-contents-ref-and-self-hosted-hosts

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-19T18:47:39 -->
### d1 · decision · Live verification is agent-run end-to-end against IDermitzakis/devops-scripts

Operator declined the back-loaded manual phase and named the scratch project. The agent runs the read-path AND the write-path (real GitLab Issues + labels) against gitlab.local.gebit.de and puts the transcript in the PR, which is what lets the acceptance row move on evidence in the same PR as the fix. Consequence: that project has issues_access_level: disabled, so the verification phase enables Issues, runs the walk, and restores disabled — both mutations recorded in the transcript.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-19T18:47:39 -->
### d2 · decision · Self-hosted support: wire host: through, default it to the git remote, warn on silent fallback

Chosen over docs-only and over wiring-without-default. Narrowed in the writing: the chosen option named GITLAB_HOST/GH_HOST/tea --login; the spec wires glab only and makes gh/tea loud instead of silent, because there is no GHE evidence and fr.gh is the highest-traffic module — churn without proof is how gh-486 got in. Flagged in the PR for override; threading gh later is additive.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-19T18:47:39 -->
### d3 · decision · Fail-loud narrowing applies to the GitLab adapter only

RealGlabClient.file_exists/list_dir swallow not-found and re-raise everything else. RealGhClient and RealTeaClient keep today's posture: the issue scopes Gitea out explicitly, and GitHub's contents endpoint needs no ref, so there is no evidence of harm to act on.

<!-- fr:journal kind=decision scope=spec id=d4 created=2026-09-19T18:47:39 -->
### d4 · decision · multibackend-gitlab-tracking goes to failing in the first commit, then to its honest resting state

The row was status: ci for a capability that does not work. Per .claude/rules/acceptance-matrix.md a discovered red acceptance is set to failing, which makes acceptance-report fail by design. Red CI in between is the point. Resting state after live proof is skipped, not ci: the live walk is hand-run in this PR and CI does not re-run it.

<!-- fr:journal kind=decision scope=spec id=d5 created=2026-09-19T18:47:40 -->
### d5 · decision · ref=HEAD rather than a branch name

Branch-agnostic by construction and live-proven against a master-default instance: HEAD is the server's own default branch, so the same call works on master and main alike.
