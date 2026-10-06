# Journal: 2026-10-06-forge-remainder

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-06T07:38:09+00:00 input=true -->
### operator-brief · discovery · Operator brief — batch forge-remainder (super-fr#742, super-fr#892)

Every forge call goes through the adapter: triage collect and isolation lookups, allowlist emptied

Batch `forge-remainder` of derio-net/super-fr: 2 issues, delivered as ONE pull request.

## super-fr#742: Pipeline code and skills call gh directly, bypassing the forge adapter: deliver can never resolve on GitLab/Gitea
Hard gate fixed by #744 (deliver reads the PR body via `client_for`; tripwire `test_tripwire_forge_adapter.py` with a shrink-only allowlist). Still direct `gh`: triage collect (`fr.gh.list_*`), isolation/local.py default-branch and PR-by-branch lookups (second copy of the adapter), remaining skill prose.
Note: Feature (fr-goal), batch `forge-remainder`, after `closeout-always` (both touch run/closeout.py). Driven by the tripwire allowlist: each site removed shrinks it.

## super-fr#892: fr triage batch: make_client drops the self-hosted host (same class as #490)
`triage_batch_cmd.make_client` never passes `host=`, so batch verbs on a self-hosted forge talk to the SaaS default.
Note: Same class as super-fr#490.

## Why these belong together
Wave 5 (high severity): #742 is a high-severity regression (deliver never resolves on GitLab/Gitea); #744 fixed the hard gate and left a shrink-only allowlist, this empties it. #892 is the same bypass in the triage batch verbs (make_client drops the self-hosted host).

## Delivery rules
- Work on branch `feat/batch-forge-remainder`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#742
  Closes derio-net/super-fr#892
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=d1-collect-adapter-github-only created=2026-10-06T07:38:09+00:00 -->
### d1-collect-adapter-github-only · decision · Triage collect moves onto the adapter, GitHub-only

Collect reads join the GhClient protocol; GitHub implements them, glab/tea raise UnsupportedForgeOperation (gh#611). No GitLab/Gitea triage.

<!-- fr:journal kind=decision scope=spec id=d2-isolation-injected-runner created=2026-10-06T07:38:09+00:00 -->
### d2-isolation-injected-runner · decision · Isolation lookups become adapter methods with an injected runner

default_branch / pr_for_branch on all three backends; isolation passes its Runner (network env + timeout), so its tests and timeouts are preserved.

<!-- fr:journal kind=decision scope=spec id=d3-client-for-url-and-gh-host created=2026-10-06T07:38:09+00:00 -->
### d3-client-for-url-and-gh-host · decision · Shared client_for_url helper, and RealGhClient honours host via GH_HOST

Promote pr_state's resolver to hostclient.client_for_url; thread host into the GitHub adapter so a GHE triage batch reaches its instance.

<!-- fr:journal kind=decision scope=spec id=d4-forge-error-kind created=2026-10-06T07:38:09+00:00 -->
### d4-forge-error-kind · decision · Bridge rate-limit classification via hostclient over every FORGE_ERRORS member

hostclient.forge_error_kind(exc); bridge_cli catches FORGE_ERRORS so glab/tea rate limits back off too.

<!-- fr:journal kind=decision scope=spec id=d5-skill-prose-neutral created=2026-10-06T07:38:09+00:00 -->
### d5-skill-prose-neutral · decision · Forge-neutral skill prose, no prose tripwire

fr-triage and fr-dispatch name operations with "on GitHub, `gh …`" examples; both mirror syncs run.
