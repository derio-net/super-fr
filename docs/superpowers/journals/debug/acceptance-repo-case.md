<!-- fr:journal-schema=3 -->
# Journal: acceptance-repo-case

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-24T07:33:58+00:00 -->
### repro · repro · Case-only ref prefix makes own-repo refs siblings

gh#1237: a matrix with repo: homelab whose refs are all written HOMELAB:... — fr acceptance treats every own-repo ref as a sibling. check() warns 'repo HOMELAB not checked out locally' and verifies nothing; report_local.html links resolve via <checkout>/../HOMELAB so they depend on the checkout's directory name (CI and fr worktrees render ../../../HOMELAB/..., report drift forever); github links pin own refs to main instead of --ref.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-24T07:34:17+00:00 -->
### root-cause · root-cause · Own-repo identity compared with exact string equality

Own-repo identity is decided by exact string equality (repo == own) at every site: check.py check() + staleness guard + _workflow_coverage_warnings, report.py LinkBuilder._base/_actual_path/url, artifacts/matrix_anchors.py, requirements.origin_fragment. A case-only mismatch between a ref prefix and the matrix repo: key therefore falls through to the sibling branch, and nothing names the mismatch.
