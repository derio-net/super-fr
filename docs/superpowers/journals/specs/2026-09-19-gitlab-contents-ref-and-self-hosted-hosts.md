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

<!-- fr:journal kind=review scope=spec id=r1 created=2026-09-19T18:51:29 -->
### r1 · review · fr-init SKILL.md already documents --host — the doc edit is a correction, not an addition

SKILL.md:78-80 already instructs the operator to pass --backend/--host on EVERY profile call for a non-GitHub repo. After §4.C that instruction is wrong, not missing: --host becomes optional (derived from the remote) and is the override. Spec §4.E rewritten; a plan built on the original premise would have added text that is already there and left the now-false instruction standing.

<!-- fr:journal kind=review scope=spec id=r2 created=2026-09-19T18:51:29 -->
### r2 · review · Warning #2 would fire on every GitHub Enterprise repo — narrowed to a declared host, moved to client_for

With §4.C's origin-hostname fallback, a GHE remote (github.corp.com) resolves a host for backend 'github', which fr does not thread — so the warning as designed fired on every client_for call for a configuration that works fine, since gh resolves its own host from the same remote. Narrowed: warn only for an explicitly declared host: key. That requires provenance, which only client_for has, so _hosts now exposes declared_host() beside host_for() and client_for_backend stays provenance-blind (keeping fr_vk.pr_observe, which derives a host from a PR URL, silent).

<!-- fr:journal kind=review scope=spec id=r3 created=2026-09-19T18:51:30 -->
### r3 · review · spec.py's degradation note carries the raised error's text verbatim

Verified compute_status wraps the remote read in 'except Exception as e: fail_note = f"cross-repo read of {ref.repo} failed: {e}"'. So §4.B's fail-loud change does not merely avoid a wrong answer — the GlabError's message surfaces in the operator's fr spec status row. Spec now names the exact call site rather than asserting the behaviour.

<!-- fr:journal kind=review scope=spec id=r4 created=2026-09-19T18:51:30 -->
### r4 · review · fr.glab gains its first os import; two host-resolution risks added

glab.py imports only subprocess/time/Callable/TypeVar today. Also added two risks found while checking the mechanism: a derived host glab has no token for (fails as Unauthenticated, now propagating rather than read as absent) and a vanity remote whose hostname is not the API host (what the explicit host: key is for).

<!-- fr:journal kind=review scope=spec id=r5 created=2026-09-19T18:51:30 -->
### r5 · review · Codebase-reality pass: every other file, line and helper the spec names exists

Verified present: real_glabclient contents methods; fr.glab.is_transient (the pattern is_not_found mirrors); _hosts.host_for:109, DEFAULT_HOST_BACKENDS, _origin_hostname; init_cmd.py:44 --host and scaffold.py:264 writing it; spec.py:237,242 and spec_cmd.py:71 passing gh; migrate.py:931-934 inside except Exception: pass; reachability.py:92-93 and apply_cmd.py:141 calling unreachable_inputs with no gh=; isolation/scaffold.py:209 as the library-warning precedent; fr_vk/pr_observe.py:50 resolving a backend from a URL hostname; test_real_glabclient.py's arg-discarding mocks; fr.gh._run_gh having no host parameter (consistent with the non-goal); docs/explainers containing no page that mentions a backend.
