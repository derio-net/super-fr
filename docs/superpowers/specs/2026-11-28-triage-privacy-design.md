# Triage privacy: outsider text never reaches worker sessions or the state ref unfenced

Batch `triage-privacy` (derio-net/super-fr#1633, #1634, #1632, #1631), one PR. All four are
out-of-scope findings of the triage-hardening lens and phase reviews
(`docs/superpowers/implemented/journals/plans/2026-11-22-triage-hardening.md`: `l-security-r6`,
`l-security-r7`, `l-security-r5`, `p3-r5`).

## Background

The triage engine (`packages/fr/src/fr/triage/`) reads a backlog from the forge into
`facts.json`. The triage agent reads that file, `fr triage check` reports from it, the pages
render it, and `batch dispatch` builds a worker's brief from it. The triage-intake and
triage-hardening specs (`2026-11-17-triage-intake`, `2026-11-22-triage-hardening`) set a trust
boundary for *issues*: an ineligible issue is stored with no title and no body
(`collect._withhold_untrusted_text`, `collect.py:573`), and an outside author's issue is
admitted only by a trusted `fr-admit` marker whose digest equals the issue's current
`content_digest` (`admit.py:35`, `intake.intake_reason`, `intake.py:90`). Four gaps remain:

1. **Comments are not pinned (#1633).** `content_digest(title, body)` covers the title and body
   only. After an operator admits an issue, an outside author can add a comment, or edit one, and
   the admission still holds. A worker that reads the issue thread (as a fr-goal session does when
   it reads its batch's issues) then reads text that no operator admitted. The admit preview
   (`commands/triage_admit_cmd.py:133`) shows no comments, so the operator never saw comments that
   were there before admission either.
2. **The privacy guard sees only keys (#1634).** `privacy.guard_state` (`privacy.py:249`) refuses a
   push or export to a public state repo when `state_keys` (judged issues, batch and pattern
   members, origins, snapshot keys) or snapshot debt repos name a non-public repo. The state ref
   carries more than that (`state_ref.REF_FILES`, `state_ref.py:54`). `merge-stops.json` reasons
   name PRs, repos and files. The fragment directories (`backlog/`, `issues/`, `origins/`,
   `architecture/`, `history/`, `board/`, `authored-src/`) hold free prose. The claude-cloud
   mailbox's `requests.yaml` holds each dispatch's `prompt`, which is the whole launch brief with
   the members' titles and bodies (`packages/fr-claude-cloud/src/fr_claude_cloud/mailbox.py:41`).
   None of these are inspected, so a private repo's issue text can reach a public state ref.
3. **PR titles are never withheld (#1632).** `parse_prs` (`collect.py:295`) and the judged-PR view
   (`collect.py:905`) store every PR title as read. Facts' `prs`, `gated_prs`, `batch_prs`,
   `judged_prs` and each issue's linked `prs` therefore carry outside authors' text into
   `fr triage check` (`check.py:239`, which the triage agent reads) and the pages
   (`render.py:741`, `render.py:1072`).
4. **A reopened PR stays closed (#1631).** A judged PR that is not in either PR list and was
   finished in the previous facts is carried with no forge call (`finished_prs`,
   `collect.py:860`, `collect.py:878`). A PR that was closed and then reopened is in the open-PR
   list and is picked up there, unless that list was cut at `pr_limit`. Then the PR stays
   `CLOSED` in facts on every later collect. Carried closed *issues* already skip the carry when
   their list was truncated (`collect.py:881`); judged PRs have no such check.

## Requirements

R1. An admission pins the issue's comments as well as its title and body. `content_digest` covers the full title, a blank line, the full body, and then each comment whose author is not trusted under the claim-marker rule (`claims.trusted_author`: a `claim_trusted` login or an OWNER, MEMBER or COLLABORATOR association), in creation order, each as its author's lowercased login, its creation time and its full body, with `\r\n` read as `\n`. A trusted author's comment (the operator's, fr's own markers) never changes the digest. One function computes it, and `fr triage admit`, collect and the dispatch re-read all call it.
R2. The admit marker that pins this digest is version 2 (`{"v":2,"digest":"sha256:<hex>"}`). A version-1 marker no longer admits: the issue is ineligible with a reason saying its admission predates comment pinning and naming `fr triage admit <key>`. A marker of any other version, or malformed, is ignored as today.
R3. `fr triage admit` reads the issue's comments with its title and body, and its preview shows each untrusted comment (author, time, body) inside the quoted untrusted block, beside the title and body, with the digest over all of them. `--yes --digest <d>` re-reads all three and refuses, writing nothing, when the live digest differs. A failed comment read refuses before any write.
R4. Collect computes an issue's `content_digest` from the comments it reads for the admission, so a `ready-fr` issue whose admission rests on its marker alone becomes ineligible, with the "content changed after admission" reason, once an untrusted comment is added or edited. When collect does not read the comments, the issue's `content_digest` is empty and no admit marker admits it. A facts file of an older schema loads with every issue's admission unread, so a `ready-fr` issue in it is ineligible until the next collect.
R5. `batch dispatch --yes` (the wave driver's dispatch included) re-reads each admit-pinned member's comments with its title and body and recomputes the digest; a changed digest or a failed read of either refuses the dispatch as today, naming the member and `fr triage admit <owner/repo#n>`.
R6. Collect stores a PR's title only when the PR's author is trusted for the PR's repo under the claim-trust set (`model.claim_trusted`: the user collect ran as and the repo's `.fr/triage.yaml` `pr_authors`), compared case-insensitively; every other PR, including one whose author was not read, is stored with an empty title. This holds for every PR facts carry: `prs`, `gated_prs`, `batch_prs`, `judged_prs` and each issue's linked PRs. A facts file written before this change is withheld the same way when it loads.
R7. `fr triage check` (text and `--json`) and the pages show a PR with an empty title by its key and URL, with the pages' quiet "title withheld" note in place of the title. No triage decision reads a PR's title.
R8. When the state repo is public, the privacy guard reads every file the write would carry (every `state_ref.REF_FILES` entry present in the state directory, a directory taken whole) as text and refuses when one names a repo that is not public. A repo is named by its full `owner/name`, by a forge URL that contains it, or by its `name#<number>` key form, each matched case-insensitively and only at word boundaries. The repos it looks for are the scope's members (from facts when present, else the scope), the repos of the keys `state_keys` returns and the snapshot debt repos. A certain leak raises `PrivacyError` naming the file and the repo, never the matched text; a repo whose visibility cannot be read raises `VisibilityUnreadable` as today; a carried file that cannot be read refuses.
R9. The scan runs only when the state repo is public and at least one repo it looks for is not public, so a scope whose repos are all public, or whose state repo is private, reads no file for it. A `REF_FILES` entry added later is scanned with no change to the guard.
R10. Collect carries a finished judged PR from the previous facts with no forge call only when it is `MERGED`, or `CLOSED` while its repo's open-PR list this collect returned fewer than `pr_limit` records. Otherwise the PR is viewed again as a pull request and recorded with its current state, and the view is counted in the collect's `viewed` figure.

## Design shape

```
packages/fr/src/fr/triage/
  admit.py           ~ content_digest(title, body, comments, trusted) -> v2 digest   (R1)
                     ~ admit_marker writes v:2; parse_admit -> (version, digest)       (R2)
                     ~ latest_admit -> the latest trusted marker, version kept         (R2)
  intake.py          ~ _admit_reason: a v1 marker -> "predates comment pinning"        (R2)
  collect.py         ~ _comment_facts: content_digest from the comments it read        (R4)
                     + _withhold_untrusted_pr_titles(facts PRs, config, viewer)        (R6)
                     ~ finished judged PR: carry MERGED, CLOSED only if open list < limit (R10)
  model.py           ~ FACTS_SCHEMA 18; load_facts: older -> admit unread, PR titles withheld (R4, R6)
  admit_recheck.py   ~ re-read comments too, v2 digest                                  (R5)
  privacy.py         + carried_text_leaks(state_dir, repos, vis) -> [(file, repo)]       (R8, R9)
                     ~ guard_state: keys check, then the scan when it can leak          (R8)
  render.py          ~ PR rows: empty title -> TITLE_WITHHELD                           (R7)
  check.py           ~ PR lines: key + URL when the title is empty                      (R7)
packages/fr/src/fr/commands/
  triage_admit_cmd.py ~ preview and --yes read comments; preview quotes them             (R3)
```

## Design

### A. Pinning comments (R1-R5)

`content_digest` gains two arguments, the comment records the forge adapter returns
(`list_issue_comments`: `author`, `association`, `body`, `created_at`, `id`) and the
trusted logins. It keeps the comments `claims.trusted_author` rejects, sorts them by
`(created_at, id)`, and appends to the v1 text, for each, a delimiter line followed by its body:

```
<title>

<body>

--- comment <login lowercased> <created_at as the forge gives it>
<comment body>
```

The whole text has `\r\n` read as `\n`, as today. A comment with no parseable `created_at` still
counts: the sort puts it first, and its time is written as the forge gave it, so it cannot be
dropped by ordering.

`admit_marker` writes `"v":2`. `parse_admit` returns `(version, digest)` for versions 1 and 2
and `None` for any other. `latest_admit` returns the latest trusted marker with its version.
`intake_reason` admits a `ready-fr` issue only when that marker is version 2 and its digest
equals the issue's `content_digest`; a version-1 marker gives the reason
`admitted before comments were pinned; run fr triage admit <key>`. The admit command's
existing check, which skips an issue whose author is already trusted, is unchanged.

Collect reads comments for admission only for a `ready-fr` issue that no other clause admits
(`_comment_needs`, unchanged). `_comment_facts` returns the digest it computed from those
comments, and collect stores it as the issue's `content_digest` in place of the title-and-body
digest `_issue` computes today (`collect.py:495`). For every other issue `content_digest` is
`None`; only intake reads the field, and only for that same set of issues.

Facts schema 18 marks the change. `load_facts` of a schema below 18 sets `admit_read` False on
every issue (the stored digests are title-and-body ones) and runs the PR-title withholding of
§B, as the schema-15 load already withholds issue text (`model.py:1843`).

`admit_recheck.recheck_admitted` reads the member's comments after its issue view and compares
`content_digest(title, body, comments, trusted)` with the stored `admit_digest`. A failed
comment read is a failed read.

### B. PR titles (R6, R7)

`_withhold_untrusted_pr_titles(facts)` runs at the same point as `_withhold_untrusted_text`, over
every `PullRequest` facts holds: the top-level lists and every issue's `prs`. A PR keeps its
title only when `pr.author` is in `claim_trusted(config.get(pr.repo, TriageConfig()), viewer)`.
The batch PRs the driver opens are authored by the user collect runs as, so they keep their
titles. No decision reads `PullRequest.title`; the phase that implements this confirms that
with a search of the engine and records the result. The pages already render `TITLE_WITHHELD`
for an issue; PR rows use the same note. `check` prints the key and URL.

### C. The carried-text scan (R8, R9)

`guard_state` keeps its present steps (live state-repo visibility, keys and debt repos). When
the state repo is public, it then builds the look-for set: the scope's members (facts'
`repos` when facts load, else `scope.target` / `scope.repos`), the key repos and the debt repos,
each with its visibility (facts, else read live, as `_fill` does now). When every one is public,
it returns. Otherwise `carried_text_leaks` builds one compiled pattern per non-public repo:
`owner/name` and `name#\d+`, each bounded by `(?<![\w.-])` and `(?![\w.-])`, case-insensitive.
A forge URL is matched through its `owner/name` part. The scan reads every regular file under the
`REF_FILES` entries in the state directory (the same walk `state_ref` uses for the ref's tree,
never through a symlink) as bytes. A file that matches yields `(relative path, repo)`. Certain
leaks raise `PrivacyError`, through a new branch of `refusal`, naming the file and the repo. A
repo whose visibility is unknown raises `VisibilityUnreadable`, so a looping drive retries. An
`OSError` on a file refuses with its path.

Measured during brainstorm: this repo's own scope carries 50 files (4.6 MB), and a read and
scan with a comparable pattern took about 150 ms from a cold cache. The other scopes on the host
took under 5 ms. The push the guard protects makes a live network call before it runs.

### D. Reopened judged PRs (R10)

The per-repo loop records the repos whose `list_open_prs` returned `pr_limit` records. Collect
takes a `CLOSED` entry from `finished_prs` only for a repo outside that set; a `MERGED` one is
taken as today. Otherwise the key falls through to the existing view path (`view_issue`, then
`view_pr` for a PR), which records the current state or an unviewed reason. The partial-collect
carry (`_carried_judgement` for a repo in `keep`) is unchanged: that repo is not read at all.

## Verification

strategy: none
gate: developer

- triage-admit-pins-comments: none — CI unit tests on `content_digest` (a trusted comment changes nothing, an untrusted edit changes it), `parse_admit`/`intake_reason` for v1 and v2 markers, collect over a fake forge, the schema-17 load, `fr triage admit` preview and `--yes` against a fake GhClient, and `recheck_admitted`
- triage-pr-title-withheld: none — CI unit tests on collect over a fake forge with an outside author's PR in each PR list, the older-schema load, `check` output and the rendered PR row
- triage-state-scan-guard: none — CI unit tests on `guard_state` over a state directory whose `merge-stops.json`, a fragment file and `requests.yaml` name a private repo, a clean directory (no refusal), the all-public short circuit (no file read) and an unreadable file
- triage-reopened-pr-uncarried: none — CI unit tests counting forge calls over two collects with a fake forge whose open-PR list is and is not cut at the limit

Every requirement is engine or render behaviour that fakes prove in CI; no released build shows
anything more.

## Out of scope

- Outside comments on issues admitted by a trusted author or association: no admission depends on
  their text, and the worker's brief already fences what it quotes. Not part of #1633.
- A comment's text in facts: facts store no comments, so nothing there needs withholding.
- Rewriting history on a state ref that already carried a private name: the guard stops new
  pushes; it does not scrub old commits.
