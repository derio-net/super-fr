# Journal: 2026-10-09-isolation-up-fr-readiness

<!-- fr:journal kind=repro scope=debug id=repro-suppressed-install created=2026-10-09T13:00:17+00:00 -->
### repro-suppressed-install · repro · Required fr installation failure is reported as ready

The scaffolded postCreateCommand ends its required uv tool install with '|| true'. A forced non-zero install therefore produces a zero post-create status. LocalWorktreeDevcontainerTarget._devcontainer_up accepts a zero devcontainer-up result without executing fr in the container, so isolation up can return a ready state whose first 'fr --version' fails.
