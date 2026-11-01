<!-- fr:journal-schema=3 -->
# Journal: 2026-11-01-gitea-adapter-live-shapes

<!-- fr:journal kind=repro scope=debug id=repro created=2026-11-01T09:08:28+00:00 -->
### repro · repro · Phase 9 live walk: 9 of 30 RealTeaClient checks fail against real Gitea + tea 0.16.0

Walked 2026-11-01 against a self-hosted Gitea (operator's cluster, reached via kubectl port-forward because its external host is SSO-gated, derio-net/frank#909; host and LAN address redacted), tea 0.16.0, a private scratch repo. Driver: a script calling every RealTeaClient method. Failing: ensure_labels duplicates (2 labels named fr:walk after two calls); file_exists on a missing path returns True; pr_for_branch and default_branch always None; pr_status_by_url None for an http ROOT_URL and would read a merged PR as CLOSED; list_open_issues_with_body returns number as a str and splits labels on commas. Passing: list_linked_prs (PR surfaced, plain referencing issue excluded, merged state correct, deduped), contents read, pr_body by index/URL/branch, labels/comments/body edits, close/reopen.

<!-- fr:journal kind=hypothesis scope=debug id=h1 created=2026-11-01T09:08:34+00:00 -->
### h1 · hypothesis · H1: fixtures modelled Gitea's swagger, but most reads parse tea's rendered output

Evidence: tests/unit/test_real_teaclient.py and test_forge_adapter_lookups.py feed {merged: bool, head: {label}, default_branch} to methods that call tea's --fields/--output json renderings. Live tea 0.16: `pulls list --fields` rejects 'merged' (Error: invalid field) and renders head as a bare string and state as open|closed|merged; `pulls <n>` has hasMerged/mergedAt and no draft key; `repos --fields` has no default_branch (it lists repos); `issues list` renders index as a string and labels SPACE-separated. Methods that go through `tea api` (timeline, contents) got the shapes right.

<!-- fr:journal kind=hypothesis scope=debug id=h2 created=2026-11-01T09:08:40+00:00 -->
### h2 · hypothesis · H2: tea api exits 0 on an HTTP error, so check=True never fires

Live: `tea api /repos/o/r/contents/nope.txt` prints the 404 error JSON and exits 0; with -i the status line (HTTP/1.1 404 Not Found) goes to stderr. Unit doubles modelled a 404 as a raised TeaError, so file_exists' safe direction was only ever tested against behaviour tea does not have.

<!-- fr:journal kind=hypothesis scope=debug id=h3 created=2026-11-01T09:08:45+00:00 -->
### h3 · hypothesis · H3: Gitea permits duplicate label names, so create-and-tolerate-ALREADY-EXISTS never converges

Live: two ensure_labels calls left two labels named fr:walk with the same colour; the create succeeded both times (no ALREADY-EXISTS refusal for the GitLab-parity tolerance to catch). Issues created with --labels fr:walk then carry both.

<!-- fr:journal kind=root-cause scope=debug id=root-cause created=2026-11-01T09:08:51+00:00 -->
### root-cause · root-cause · RealTeaClient parses tea's presentation layer as if it were Gitea's API, and trusts tea api's exit code

One cause, seven symptoms: tea's --fields/--output json renderings are tea's own undocumented shape (renamed, flattened, stringly-typed fields), and `tea api` signals HTTP errors only in its -i status line. Fix: one helper, fr.tea.api_json, that runs `tea api -i`, refuses on a status >= 400 or a missing status line, and returns Gitea's documented swagger shape; every RealTeaClient read moves onto it ({owner}/{repo} placeholders resolve from the cwd checkout for default_branch/pr_for_branch). ensure_labels lists existing names via the API and creates only the missing ones (drift tolerated, GitLab parity). pr_status_by_url accepts http:// ROOT_URLs.

<!-- fr:journal kind=finding scope=debug id=fix created=2026-11-01T10:22:20+00:00 state=fixed -->
### fix · finding [fixed] · Every RealTeaClient read moved onto fr.tea.api_json; ensure_labels converges

Source: fr/tea.py gains api_result/api_json/api_pages (tea api -i; refuses non-2xx, a missing status line, a non-JSON body; names a 3xx as an SSO/forward-auth proxy). real_teaclient.py: list_linked_prs, pr_status_by_url (http(s) URLs; API merged/draft), authenticated_login, list_open_issues_with_body (API issues, int number, label objects), default_branch and pr_for_branch ({owner}/{repo} from cwd, through the caller's CommandRunner, so isolation timeouts still apply), file_exists/list_dir/read_file. ensure_labels lists existing names first. Tests first: tests/unit/test_tea_live_shapes.py over tests/fixtures/gitea/ (12 captures, redacted) — 20 of 21 red before the fix. 19 older tests moved off the tea-rendering contract; 4 of them had been passing by accident (patching _run_tea, which the reads no longer call, so they reached the real binary). Verified: the live walk re-run 2026-11-01 on the fixed code, 33/33 checks pass.
