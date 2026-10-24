<!-- fr:journal-schema=3 -->
# Journal: acceptance-repo-case

<!-- fr:journal kind=repro scope=debug id=repro created=2026-10-24T07:33:58+00:00 -->
### repro · repro · Case-only ref prefix makes own-repo refs siblings

gh#1237: a matrix with repo: homelab whose refs are all written HOMELAB:... — fr acceptance treats every own-repo ref as a sibling. check() warns 'repo HOMELAB not checked out locally' and verifies nothing; report_local.html links resolve via <checkout>/../HOMELAB so they depend on the checkout's directory name (CI and fr worktrees render ../../../HOMELAB/..., report drift forever); github links pin own refs to main instead of --ref.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-10-24T07:34:17+00:00 -->
### root-cause · root-cause · Own-repo identity compared with exact string equality

Own-repo identity is decided by exact string equality (repo == own) at every site: check.py check() + staleness guard + _workflow_coverage_warnings, report.py LinkBuilder._base/_actual_path/url, artifacts/matrix_anchors.py, requirements.origin_fragment. A case-only mismatch between a ref prefix and the matrix repo: key therefore falls through to the sibling branch, and nothing names the mismatch.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-10-24T07:48:04+00:00 state=fixed -->
### fix · finding [fixed] · same_repo() decides own-repo identity everywhere, case-insensitively

New fr.acceptance.model.same_repo (casefold) replaces == at check.py (resolution, staleness, workflow coverage), report.py (_base, _actual_path, url — own github links now use the matrix spelling and --ref), requirements.origin_fragment, artifacts/matrix_anchors. check() warns 'ref prefix X: differs from the matrix's repo: y only by case'. Failing-first: tests/unit/test_acceptance_repo_case.py (checkout dir not named like the prefix) — 6 red before the call-site change, 8 green after; 654 related tests pass.

<!-- fr:journal kind=review scope=debug id=review created=2026-10-24T07:49:02+00:00 -->
### review · review · Self-review of PR #1241

Reviewed the diff against every == own-repo site found by grep (check.py x3, report.py x3, requirements, matrix_anchors); no remaining exact comparison. Finding raised: add-time prefix normalisation (issue's optional 3rd suggestion) not implemented — deferred as out of scope, covered by the new check warning, noted in the PR body. No other findings.
