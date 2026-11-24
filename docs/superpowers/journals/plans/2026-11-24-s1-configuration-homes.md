<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-s1-configuration-homes

<!-- fr:journal kind=finding scope=plan id=sec-1-self-attesting-config-branch created=2026-11-24T21:06:33+00:00 phase=3 state=open -->
### sec-1-self-attesting-config-branch · finding [open] · A self-declared fr-config branch must not supply executable or trust keys unless its protection is enforced (phase 3)

Automated security review of phase 1's commit (space.py forge_ref, triage/collect.py): the forge-side reader takes .fr/triage.yaml from fr-config when that branch's own settings say placement: quiet, so anyone able to push a branch named fr-config could redirect post_merge commands and the pr_authors trust list. Default-branch opt-in is not available under quiet by design (D12, R5), and self-attestation of the switch predates S1 (origin/fr). Phase 3 closes it: R7's guard must cover trust keys as well as executable ones (pr_authors, and any key that decides whose PRs are trusted or merged), and every reader that takes such keys from a configuration branch asks require_protected first; when not enforced, those keys come from nowhere (ignored, with the reason), never from the unprotected branch. Test: a pushed fr-config with no pull_request rule yields no post_merge and no pr_authors from it.
