<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-stealth-gitlab-visibility

<!-- fr:journal kind=repro scope=debug id=c6c930208a06 created=2026-11-19T12:03:30+00:00 -->
### c6c930208a06 · repro · Stealth privacy refuses a self-hosted GitLab tracking repo given as a bare clone URL

check_privacy(ref='git@<gitlab-host>:<group>/<tracking>.git@<branch>', target on the same self-hosted GitLab declared forge: {type: gitlab}) raises 'cannot read the visibility of <tracking>'. The target's visibility resolves; the tracking repo's does not. (Host redacted, from gh#1527.)

<!-- fr:journal kind=root-cause scope=debug id=d17adbb78f3d created=2026-11-19T12:03:41+00:00 -->
### d17adbb78f3d · root-cause · With no tracking checkout, _forge_visibility picks the backend from the URL alone, and backend_for_url reads every self-hosted host as github

placement/stealth.py _forge_visibility: checkout is None -> _hosts.backend_for_url(url). A bare clone URL carries no /-/merge_requests or /-/issues route shape and its host is not in DEFAULT_HOST_BACKENDS, so it falls through to 'github'; gh pinned to a GitLab host cannot read the project -> None -> R24 refuses. check_privacy only ever hands the TARGET its checkout, though the target's forge declaration already names the backend of that very host.
