# Journal: 2026-10-09-isolation-up-fr-readiness

<!-- fr:journal kind=repro scope=debug id=repro-suppressed-install created=2026-10-09T13:00:17+00:00 -->
### repro-suppressed-install · repro · Required fr installation failure is reported as ready

The scaffolded postCreateCommand ends its required uv tool install with '|| true'. A forced non-zero install therefore produces a zero post-create status. LocalWorktreeDevcontainerTarget._devcontainer_up accepts a zero devcontainer-up result without executing fr in the container, so isolation up can return a ready state whose first 'fr --version' fails.

<!-- fr:journal kind=hypothesis scope=debug id=hypothesis-two-missing-gates created=2026-10-09T13:03:56+00:00 -->
### hypothesis-two-missing-gates · hypothesis · Provisioning and readiness both fail open

Confirmed by three red tests: forced uv installation failure exits zero, a scaffold without requested tools omits the uv feature required by postCreateCommand, and a successful devcontainer up is accepted when devcontainer exec fr --version fails.

<!-- fr:journal kind=root-cause scope=debug id=root-cause-fr-not-postcondition created=2026-10-09T13:04:03+00:00 -->
### root-cause-fr-not-postcondition · root-cause · fr executability is not an isolation postcondition

POST_CREATE suppresses the required fr installation result and scaffold_profile does not unconditionally provide uv, while _devcontainer_up treats only the wrapper CLI exit code as readiness. Therefore both current and stale profiles can produce a recorded ready workspace without an executable fr.
