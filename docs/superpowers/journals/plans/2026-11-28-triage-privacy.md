<!-- fr:journal-schema=4 -->
# Journal: 2026-11-28-triage-privacy

<!-- fr:journal kind=decision scope=plan id=p1-digest-json-frame created=2026-11-28T15:50:26+00:00 phase=1 -->
### p1-digest-json-frame · decision · v2 digest is a JSON frame, not text with delimiters (phase 1)

Per the coordinator's spec amendment, content_digest(title, body, *, comments, pinned_authors) hashes a sorted-key compact JSON frame with both keyword arguments required, so body text cannot imitate a comment and no caller falls back to a title-and-body digest.

<!-- fr:journal kind=discovery scope=plan id=p1-marker-comment-is-pinned-unless-trusted created=2026-11-28T15:50:26+00:00 phase=1 -->
### p1-marker-comment-is-pinned-unless-trusted · discovery · an admit marker comment by a login with no OWNER/MEMBER/COLLABORATOR association and not in pr_authors is itself pinned (phase 1)

The marker embeds its own digest, so such a marker can never match. The spec's pinning rule is association or pr_authors; fixtures that post markers now carry association OWNER. The driving account is expected in pr_authors (triage-hardening R7).

<!-- fr:journal kind=discovery scope=plan id=p1-pr-title-readers created=2026-11-28T15:50:26+00:00 phase=1 -->
### p1-pr-title-readers · discovery · PullRequest.title readers after the withholding pass (phase 1)

Display readers now route an empty title to the withheld note - render.py (_pr_row, _pr_cell), kanban_render.py (_gated_card), commands/triage_cmd.py (unranked and settled PR lines), and the queue subject (triage_batch_cmd._queue_entry uses pr.title or batch.title). check.py JSON keeps the empty title with key and url. Left unchanged: render.py data-search (an empty title is harmless) and origins.py (out of scope per the spec, filed as a follow-up). The judged-PR view path now records the PR's author from the issue view so a trusted author keeps its title.

<!-- fr:journal kind=discovery scope=plan id=p1-old-schema-fixtures created=2026-11-28T15:50:26+00:00 phase=1 -->
### p1-old-schema-fixtures · discovery · tests that wrote facts with schema 3 now load as older than 22 (phase 1)

load_facts withholds and marks admission unread below schema 22, so the batch-dispatch test facts helper now writes schema 22.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-28T15:50:26+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

smoke task: one fixed-shape digest function, nothing to clean

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-11-28T15:53:51+00:00 phase=1 -->
### p1-review-1 · review · phase 1 review: no findings (R1-R7, R10 verified) (phase 1)

An independent code reviewer (separate context) checked the phase 1 diff ce7f02608..8ca0e0471 against spec R1-R7 and R10, with file:line evidence for each. Confirmed: the digest is JSON-framed with required keyword args, and one function computes it (admit.py content_digest). Only v2 markers admit. The admit preview shows pinned comments and refuses before writing when a comment read fails. Collect's digest is None when comments were not read. The facts schema is 22, and loading older facts withholds again. The dispatch recheck reads comments with the repo's pr_authors and refuses when that read fails (admit_recheck.py; called from dispatch_batch in triage_batch_cmd.py). Outside authors' PR titles are withheld in every collection and every reader. A reopened PR is read again past a cut open-PR list. The orchestrator then checked two points itself. The double `viewed` count is the existing two-reads-per-PR accounting. The recheck sits inside dispatch_batch, the path the wave driver dispatches through. Findings: none.

<!-- fr:journal kind=decision scope=plan id=p2-git-suffix created=2026-11-28T16:10:09+00:00 phase=2 -->
### p2-git-suffix · decision · the owner/name pattern admits a trailing .git (phase 2)

The spec's bound (?!\.\w) would reject https://host/acme/secret.git, which R8 requires to match, so the owner/name alternative takes an optional (?:\.git)? before the trailing bounds. Name#digits keeps the plain bounds.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t3 created=2026-11-28T16:10:09+00:00 phase=2 -->
### no-refactor-p2-t3 · discovery · no-refactor-because P2.T3 (phase 2)

docs and acceptance row only; no code to clean

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-11-28T16:13:51+00:00 phase=2 -->
### p2-review-1 · review · phase 2 review: no findings (R8, R9, Design D, docs currency verified) (phase 2)

An independent reviewer (separate context, with a shell) checked diff 24b7345..539fbdc30 against R8, R9 and Design D, and ran adversarial strings through repo_patterns. Private owner/name matches case-insensitively, including with a .git suffix and in sentence-final position. Lookalikes (xowner/name, name-two, name.md, my-name#12) do not match. The name#N form is skipped when a public repo shares the name. The p2-git-suffix decision is sound: Design C already requires the .git form, and backtracking still rejects .gitx. A push scans state_ref.ref_entries, which covers the whole REF_FILES walk. An export scans the durable set, including subdirectories. Refusals name the file, the repo and the remedy, never the matched text. An unreadable file refuses. An org scope with no facts raises VisibilityUnreadable naming fr triage collect. Tests: 173 passed (test_triage_privacy, test_triage_state_ref, test_triage_state_sync). fr docs check is clean, and both mirror syncs report in sync. Findings: none.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1 created=2026-11-28T16:46:45+00:00 state=open review_scope=in -->
### l-docs-accuracy-r1 · finding [open] (reviewer: in scope) · fr-triage.md said an admission pins every outside account's comment, but pr_authors are exempt too

Raised by the docs-accuracy lens reviewer. The page's untrusted-set paragraph overstated what pinned() pins (admit.py).

<!-- fr:journal kind=finding scope=plan id=l-tests-r1 created=2026-11-28T16:46:45+00:00 state=open review_scope=in -->
### l-tests-r1 · finding [open] (reviewer: in scope) · The push-scan test planted the secret in one REF_FILES entry only; a scan walking fewer entries or following symlinks would pass

Raised by the tests lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2 created=2026-11-28T16:46:45+00:00 state=open review_scope=in -->
### l-tests-r2 · finding [open] (reviewer: in scope) · The schema-21 PR-title load test had only an outsider's PR; a load clearing trusted titles too would pass

Raised by the tests lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-security-r1 created=2026-11-28T16:46:45+00:00 state=open review_scope=in -->
### l-security-r1 · finding [open] (reviewer: in scope) · The admission pins comments only up to the dispatch recheck; an outside comment posted after dispatch reaches the worker reading the live thread

Raised by the security lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-security-r2 created=2026-11-28T16:46:45+00:00 state=open review_scope=in -->
### l-security-r2 · finding [open] (reviewer: in scope) · pinned() stripped [bot] from the comment login but not from pr_authors, so REST and GraphQL digests disagree for an `x[bot]` pr_author

Raised by the security lens reviewer (R1 breach; fails closed, a liveness cost).

<!-- fr:journal kind=finding scope=plan id=l-security-r3 created=2026-11-28T16:46:45+00:00 state=open review_scope=in -->
### l-security-r3 · finding [open] (reviewer: in scope) · The carried-text patterns missed owner/name.wiki(.git), zero-width-split and percent-encoded spellings of a private repo

Raised by the security lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-security-r4 created=2026-11-28T16:46:45+00:00 state=open review_scope=in -->
### l-security-r4 · finding [open] (reviewer: in scope) · The carried-file scan read contents only; a carried file's path naming a private repo reached the public ref

Raised by the security lens reviewer.

<!-- fr:journal kind=finding scope=plan id=l-security-r5 created=2026-11-28T16:46:45+00:00 state=open review_scope=in -->
### l-security-r5 · finding [open] (reviewer: in scope) · TOCTOU: push_state scanned the files, then commit_tree_from_paths re-read them; a write in between pushed unscanned bytes

Raised by the security lens reviewer.

<!-- fr:journal kind=review scope=plan id=lens-review-1 created=2026-11-28T16:46:45+00:00 -->
### lens-review-1 · review · lens review: docs-accuracy 1, tests 2, security 5 findings, all in scope and fixed

One independent reviewer per lens (docs-accuracy, security, tests), each given only its lens brief, return rule, the diff from merge base 608d55585 and the shape file. All eight findings were in scope and are fixed with tests. The security reviewer found no fail-open on the three trust boundaries. The tests reviewer confirmed the listed fail-closed paths are covered apart from its two findings.

<!-- fr:journal kind=finding scope=plan id=l-docs-accuracy-r1-resolved created=2026-11-28T16:46:45+00:00 state=fixed resolves=l-docs-accuracy-r1 -->
### l-docs-accuracy-r1-resolved · finding [fixed] · resolves l-docs-accuracy-r1: fr-triage.md said an admission pins every outside account's comment, but pr_authors are exempt too

The page now names exactly which comments an admission pins (neither owner, member or collaborator nor in pr_authors).

<!-- fr:journal kind=finding scope=plan id=l-tests-r1-resolved created=2026-11-28T16:46:45+00:00 state=fixed resolves=l-tests-r1 -->
### l-tests-r1-resolved · finding [fixed] · resolves l-tests-r1: The push-scan test planted the secret in one REF_FILES entry only; a scan walking fewer entries or following symlinks would pass

test_every_carried_entry_is_scanned_on_push plants the secret in every REF_FILES entry (a file deep inside each directory entry), and test_a_symlinked_entry_is_neither_carried_nor_scanned covers the symlink case. Mutation-checked: dropping history/ from carried_files turns the history/ case red.

<!-- fr:journal kind=finding scope=plan id=l-tests-r2-resolved created=2026-11-28T16:46:45+00:00 state=fixed resolves=l-tests-r2 -->
### l-tests-r2-resolved · finding [fixed] · resolves l-tests-r2: The schema-21 PR-title load test had only an outsider's PR; a load clearing trusted titles too would pass

The schema-21 load test now holds a viewer-authored PR too and asserts its title survives while the outsider's is withheld.

<!-- fr:journal kind=finding scope=plan id=l-security-r1-resolved created=2026-11-28T16:46:45+00:00 state=fixed resolves=l-security-r1 -->
### l-security-r1-resolved · finding [fixed] · resolves l-security-r1: The admission pins comments only up to the dispatch recheck; an outside comment posted after dispatch reaches the worker reading the live thread

Every batch brief now carries THREAD_RULE outside the untrusted block. It says that comments on a member's thread by an account that is not an owner, member or collaborator, and not a pr_author, are an outside author's and never to be followed, because an admission covers only the comments present at dispatch. The brief stays deterministic. test_the_brief_says_outside_comments_in_a_members_thread_are_untrusted pins it.

<!-- fr:journal kind=finding scope=plan id=l-security-r2-resolved created=2026-11-28T16:46:45+00:00 state=fixed resolves=l-security-r2 -->
### l-security-r2-resolved · finding [fixed] · resolves l-security-r2: pinned() stripped [bot] from the comment login but not from pr_authors, so REST and GraphQL digests disagree for an `x[bot]` pr_author

pinned() normalises both sides to the canonical login (lowercased, [bot] dropped). A test parametrised over both listed and read spellings asserts the same verdict and an equal REST/GraphQL digest.

<!-- fr:journal kind=finding scope=plan id=l-security-r3-resolved created=2026-11-28T16:46:45+00:00 state=fixed resolves=l-security-r3 -->
### l-security-r3-resolved · finding [fixed] · resolves l-security-r3: The carried-text patterns missed owner/name.wiki(.git), zero-width-split and percent-encoded spellings of a private repo

repo_patterns accepts an optional .wiki before .git. carried_text_leaks also scans the text with Unicode Cf characters removed and percent-escapes decoded. Three new leak cases cover these.

<!-- fr:journal kind=finding scope=plan id=l-security-r4-resolved created=2026-11-28T16:46:45+00:00 state=fixed resolves=l-security-r4 -->
### l-security-r4-resolved · finding [fixed] · resolves l-security-r4: The carried-file scan read contents only; a carried file's path naming a private repo reached the public ref

carried_text_leaks scans each carried path, with its suffix dropped, as well as its text. test_a_carried_path_naming_a_private_repo_is_a_leak covers it.

<!-- fr:journal kind=finding scope=plan id=l-security-r5-resolved created=2026-11-28T16:46:45+00:00 state=fixed resolves=l-security-r5 -->
### l-security-r5-resolved · finding [fixed] · resolves l-security-r5: TOCTOU: push_state scanned the files, then commit_tree_from_paths re-read them; a write in between pushed unscanned bytes

push_state builds the commit first and runs guard_state over that commit's blobs (carried= the tree's paths, read= blob bytes), so the bytes scanned are the bytes pushed. test_a_push_scans_the_bytes_it_commits_not_the_directory_again rewrites the file clean after the commit is built and still sees the refusal.

<!-- fr:journal kind=finding scope=plan id=bot-account-type created=2026-11-28T16:51:22+00:00 state=open review_scope=out -->
### bot-account-type · finding [open] (reviewer: out of scope) · Comment adapters do not report whether an author is a bot, so a pr_author listed as x[bot] is pinned under GraphQL but not under REST

The automated security review of the l-security-r2 fix found this. Comparing logins symmetrically widened trust to a user account with the same name, so the fix went back to the one-directional rule: a listed login trusts only what it names.

What is left fails closed. If a bot is listed with its [bot] suffix, an admission made under one API mode is voided under the other. Listing the bot by its bare login avoids this.

The fix is to carry the account type (REST user.type, GraphQL __typename) in both comment adapters, and to match x[bot] only against an author whose type is Bot. That needs a GraphQL comment query beyond gh issue view --json comments.
