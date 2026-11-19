<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-stealth-gitlab-visibility

<!-- fr:journal kind=repro scope=debug id=c6c930208a06 created=2026-11-19T12:03:30+00:00 -->
### c6c930208a06 · repro · Stealth privacy refuses a self-hosted GitLab tracking repo given as a bare clone URL

check_privacy(ref='git@<gitlab-host>:<group>/<tracking>.git@<branch>', target on the same self-hosted GitLab declared forge: {type: gitlab}) raises 'cannot read the visibility of <tracking>'. The target's visibility resolves; the tracking repo's does not. (Host redacted, from gh#1527.)
