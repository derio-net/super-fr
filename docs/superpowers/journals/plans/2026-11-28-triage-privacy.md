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
