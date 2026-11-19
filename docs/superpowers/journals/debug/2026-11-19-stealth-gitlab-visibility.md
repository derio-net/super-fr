<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-stealth-gitlab-visibility

<!-- fr:journal kind=repro scope=debug id=c6c930208a06 created=2026-11-19T12:03:30+00:00 -->
### c6c930208a06 · repro · Stealth privacy refuses a self-hosted GitLab tracking repo given as a bare clone URL

check_privacy(ref='git@<gitlab-host>:<group>/<tracking>.git@<branch>', target on the same self-hosted GitLab declared forge: {type: gitlab}) raises 'cannot read the visibility of <tracking>'. The target's visibility resolves; the tracking repo's does not. (Host redacted, from gh#1527.)

<!-- fr:journal kind=root-cause scope=debug id=d17adbb78f3d created=2026-11-19T12:03:41+00:00 -->
### d17adbb78f3d · root-cause · With no tracking checkout, _forge_visibility picks the backend from the URL alone, and backend_for_url reads every self-hosted host as github

placement/stealth.py _forge_visibility: checkout is None -> _hosts.backend_for_url(url). A bare clone URL carries no /-/merge_requests or /-/issues route shape and its host is not in DEFAULT_HOST_BACKENDS, so it falls through to 'github'; gh pinned to a GitLab host cannot read the project -> None -> R24 refuses. check_privacy only ever hands the TARGET its checkout, though the target's forge declaration already names the backend of that very host.

<!-- fr:journal kind=finding scope=debug id=f-same-host created=2026-11-19T12:40:04+00:00 state=fixed -->
### f-same-host · finding [fixed] · check_privacy hands the target checkout to a tracking repo on the same forge host

stealth.py: _speaks_for(repo, target_root) returns the target checkout when its forge (declared host, else origin) names the tracking URL's host; _forge_visibility's checkout branch then re-checks the host and uses detect_backend. A tracking repo on another host keeps backend_for_url. Pinned by tests/unit/test_placement_stealth_privacy.py::test_a_tracking_url_on_the_targets_self_hosted_forge_is_read_with_its_forge_type (failed first: github client) and ::test_a_tracking_url_on_another_host_is_still_placed_by_its_url. 505 stealth/placement/privacy unit tests pass; ruff, mypy clean; fr docs check current.

<!-- fr:journal kind=review scope=debug id=b82e56bfbd15 created=2026-11-19T12:42:45+00:00 -->
### b82e56bfbd15 · review · Independent adversarial review: no pass-when-it-should-refuse path; one robustness point fixed

A reviewer in a separate context read the diff. It found no path that passes when the guard should refuse: the slug is always asked on its own URL host, and mismatched spellings (trailing dot, IPv6 brackets) fall back to the URL reading or refuse. Raised: (1) _url_host outside the try in _speaks_for, so a malformed URL raised instead of refusing. Fixed: moved inside the try, pinned by test_a_malformed_tracking_url_lends_no_checkout. (2) Test gaps, all fail-closed. The same-host gitea refusal is now pinned (test_a_tracking_url_on_the_targets_gitea_host_is_unreadable); the others were left, since each falls back or refuses. (3) _PRIVACY_OK keyed without target_root: pre-existing, unrelated, not changed.
