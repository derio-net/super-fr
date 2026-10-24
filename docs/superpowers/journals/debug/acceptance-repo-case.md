<!-- fr:journal-schema=3 -->
# Journal: acceptance-repo-case

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-24T07:33:58+00:00 -->
### repro · repro · Case-only ref prefix makes own-repo refs siblings

gh#1237: a matrix with repo: homelab whose refs are all written HOMELAB:... — fr acceptance treats every own-repo ref as a sibling. check() warns 'repo HOMELAB not checked out locally' and verifies nothing; report_local.html links resolve via <checkout>/../HOMELAB so they depend on the checkout's directory name (CI and fr worktrees render ../../../HOMELAB/..., report drift forever); github links pin own refs to main instead of --ref.
