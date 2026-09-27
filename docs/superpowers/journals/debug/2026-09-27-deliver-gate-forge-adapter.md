# Journal: 2026-09-27-deliver-gate-forge-adapter

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-27T14:27:11+00:00 -->
### repro · repro · deliver refuses forever on a GitLab/Gitea checkout

Observed (gh#742): an OpenCode run on a self-hosted GitLab (host redacted) opened the MR with glab, then `fr run resolve --step deliver` refused twice: "cannot read the PR <mr-url> (none of the git remotes ... point to a known GitHub host)", advising `gh pr create`. Cursor stuck on deliver; closeout unreachable. Static repro: commands/run_cmd.py `_deliver_pr_gate` imports `fr.gh` and calls `gh.view_pr_body(ref, cwd=repo_root)` unconditionally; `gh` cannot read a GitLab/Gitea PR, so the gate can never pass there. Every existing test (test_deliver_pr_body.py, conftest `complete_live_pr`) monkeypatches `fr.gh.view_pr_body`, so the non-GitHub path was never exercised.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-09-27T14:27:26+00:00 -->
### root-cause · root-cause · deliver PR gate bypasses the forge adapter

The deliver gate reads the live PR body through `fr.gh` (GitHub-only) instead of `fr.hostclient.client_for(repo_root)`, because the lean-process spec (2026-09-25 §5.C.4) prescribed `fr.gh` and the `GhClient` protocol had no body-read operation at all (`pr_view` returns state/head only, and glab/tea raise UnsupportedForgeOperation for it). The refusal text hardcodes `gh pr create`/`gh pr edit` for the same reason. Scope of THIS fix: the hard gate (adapter method `pr_body` for github/gitlab/gitea + gate moved onto client_for), forge-aware refusal wording, forge-neutral wording in the closeout brief and fr-goal skill, and a tripwire against new direct `fr.gh` imports. Out of scope (non-gating, filed as follow-ups): triage collect is GitHub-only; isolation/local.py duplicate backend branching; forge-parity check at `fr run start`; review-checklist item.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-09-27T14:40:17+00:00 state=fixed -->
### fix · finding [fixed] · deliver PR gate routed through client_for; forge-aware wording; tripwire

Fix (5ed80de8): GhClient.pr_body(ref, *, cwd) on every backend (gh pr view / glab mr view -> description, URL parsed to repo+iid / tea pulls list --fields body matched by url|index|head); _deliver_pr_gate reads through client_for(repo_root) and catches FORGE_ERRORS; hostclient.PR_COMMANDS + pr_command give the create/edit/ready/fill command per forge (verified against each CLI --help; a PR URL is reduced to its number for glab/tea, never a branch like fix/742), used by the gate refusals, closeout brief and fr-goal skill. Failing-test-first: tests/unit/test_deliver_pr_body_forges.py drove the real gate on gitlab/gitea-declared checkouts with gh refusing — failed (refusal advised `gh pr create`), passes after. Adapter argv pinned in test_pr_body_adapters.py. Tripwire test_tripwire_forge_adapter.py flags the pre-fix run_cmd.py:4058 import and is clean after; KNOWN is a closed shrink-only set (triage/collect.py, isolation/local.py, fr_vk/bridge_cli.py). Full suite: 6575 passed, 115 skipped.
