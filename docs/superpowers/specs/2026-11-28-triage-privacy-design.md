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

R1. An admission pins the issue's comments as well as its title and body. `content_digest` is sha256 over one JSON document, `{"v":2,"title":…,"body":…,"comments":[[login,time,id,body],…]}` (compact separators, keys sorted, non-ASCII kept), so no field's text can pass for another's. It holds the full title, the full body and each pinned comment in a canonical form: its author's login lowercased with a trailing `[bot]` removed (`ghost` when the forge names no author), its creation time as UTC `YYYY-MM-DDTHH:MM:SSZ` (empty when it does not parse), and its full body, with `\r\n` read as `\n` throughout. A comment is pinned unless its association is OWNER, MEMBER or COLLABORATOR or its author is in the repo's `.fr/triage.yaml` `pr_authors`; the viewer is not part of this rule, so `fr triage admit`, collect and dispatch agree when they run as different users. Pinned comments are ordered by (creation time, comment id with a missing id read as -1, login, body). One function computes the digest, and `fr triage admit`, collect and the dispatch re-read all call it.
R2. The admit marker that pins this digest is version 2 (`{"v":2,"digest":"sha256:<hex>"}`). Only a version-2 marker admits: a version-1 marker, any other version and a malformed marker are ignored, so an issue admitted before this change reads as having no trusted admit marker, with the existing reason that names `fr triage admit <key>`. Because the version-2 digest is taken over a JSON document carrying `"v":2`, no version-1 digest (over plain title and body text) can equal it.
R3. `fr triage admit` reads the issue's comments with its title and body. Its preview shows each pinned comment (author, time, body, each passed through the preview's visible-character rendering and included in its hidden-character warning) inside the quoted untrusted block, beside the title and body, with the digest over all of them. `--yes --digest <d>` re-reads all three and refuses, writing nothing, when the live digest differs. A failed comment read refuses before any write. The marker's human line says that an edit to the title or body, or a new or edited comment by an outside author, voids the admission.
R4. Collect computes an issue's `content_digest` from the comments it reads for the admission, so a `ready-fr` issue whose admission rests on its marker alone becomes ineligible, with the existing reason `edited after admission: run fr triage admit <key> again`, once a pinned comment is added or edited. When collect does not read the comments, the issue's `content_digest` is empty and no admit marker admits it. Facts schema 22 marks the change: a facts file of an older schema loads with every issue's admission unread and with ineligible issues' titles and bodies withheld, so a `ready-fr` issue in it is ineligible, and shows no text, until the next collect.
R5. `batch dispatch --yes` (the wave driver's dispatch included) re-reads each admit-pinned member's comments with its title and body and recomputes the digest with that member's repo `pr_authors`; a changed digest or a failed read of either refuses the dispatch as today, naming the member and `fr triage admit <owner/repo#n>`.
R6. Collect stores a PR's title only when the PR's author is trusted for the PR's repo under the claim-trust set (`model.claim_trusted`: the user collect ran as and the repo's `.fr/triage.yaml` `pr_authors`), compared case-insensitively; every other PR, including one whose author was not read, is stored with an empty title. This holds for every PR facts carry: `prs`, `gated_prs`, `batch_prs`, `judged_prs` and each issue's linked PRs. A facts file of an older schema is withheld the same way when it loads.
R7. `fr triage check` (text and `--json`), the pages and the board show a PR with an empty title by its key and URL, with a quiet "title withheld" note in place of the title. The merge queue's squash subject for a batch PR whose stored title is empty is the batch's own title followed by ` (#<n>)`. No other triage reader uses a PR's title.
R8. When the state repo is public, the privacy guard reads every file the write carries as text and refuses when one names a repo that is not public. A push carries every `state_ref.REF_FILES` entry present in the state directory (a directory taken whole, never through a symlink); `state export` carries its own set (`state_sync.DURABLE_FILES` and `DURABLE_DIRS`). A repo is named by its full `owner/name`, including inside a forge URL, or by its `name#<number>` key form, matched case-insensitively, with no word character, `.` or `-` before it and none of a word character, `-`, or a `.` followed by a word character after it. The key form is not looked for when a public repo of the look-for set has the same name. The repos it looks for are the scope's members (facts' `repos` when facts load; `scope.target` or `scope.repos` otherwise), the repos of the keys `state_keys` returns and the snapshot debt repos. A certain leak raises `PrivacyError` naming the file and the repo, never the matched text, and saying to move the scope's state to a private repo or remove that file's mention; a looping drive handles it as it handles a `PrivacyError` today. A repo whose visibility cannot be read raises `VisibilityUnreadable` as today. A carried file that cannot be read refuses, and an org scope whose facts are missing or unusable refuses as `VisibilityUnreadable` naming `fr triage collect`, since its members cannot be named.
R9. The scan runs only when the state repo is public and at least one repo it looks for is not public, so a scope whose repos are all public, or whose state repo is private, reads no file for it. A `REF_FILES` entry added later is scanned with no change to the guard.
R10. Collect carries a finished judged PR from the previous facts with no forge call only when it is `MERGED`, or `CLOSED` while its repo's open-PR list this collect returned fewer than `pr_limit` records. Otherwise the PR is viewed again as a pull request and recorded with its current state, and the view is counted in the collect's `viewed` figure.

## Design shape

```
packages/fr/src/fr/triage/
  admit.py           ~ content_digest(title, body, *, comments, pinned_authors) -> sha256(JSON v2) (R1)
                     + canonical_comment(c) -> (login, utc time, id, body)             (R1)
                     ~ admit_marker writes v:2, new human line; parse_admit: v2 only     (R2, R3)
  collect.py         ~ _comment_facts: content_digest from the comments it read        (R4)
                     + _withhold_untrusted_pr_titles(facts) -> facts                   (R6)
                     ~ finished judged PR: MERGED carried; CLOSED only if open list < limit (R10)
  model.py           ~ FACTS_SCHEMA 22; load_facts < 22: admit unread, issue text and
                       PR titles withheld                                              (R4, R6)
  admit_recheck.py   ~ re-read comments too, v2 digest with the repo's pr_authors     (R5)
  privacy.py         + carried_text_leaks(files, look_for, vis) -> [(file, repo)]      (R8, R9)
                     ~ guard_state(state_dir, ..., carried=REF|EXPORT): keys, then scan (R8)
                     ~ refusal: a carried-file branch with its remedy                 (R8)
  render.py          ~ PR rows and cells: empty title -> TITLE_WITHHELD               (R7)
  kanban.py, kanban_render.py ~ gated-PR card: empty title -> withheld note           (R7)
  check.py           ~ JSON PR rows keep key and url                                   (R7)
packages/fr/src/fr/commands/
  triage_admit_cmd.py ~ preview and --yes read comments; preview quotes them           (R3)
  triage_cmd.py       ~ text check: PR lines print key, URL, withheld note             (R7)
  triage_batch_cmd.py ~ queue EntryInput title: pr.title or batch.title                (R7)
  triage_state_cmd.py ~ export passes its carried set to guard_state                   (R8)
```

## Design

### A. Pinning comments (R1-R5)

`content_digest(title, body, *, comments, pinned_authors)` (both keyword arguments required, so no caller falls back to a title-and-body digest) hashes
`json.dumps({"v": 2, "title": title, "body": body, "comments": [[login, time, id, body], …]}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` after the `\r\n` → `\n` normalisation of each text field. JSON framing means body text that imitates a comment can never hash like a real comment (security review of the first commits).

Comment records come from either adapter (`real_ghclient.py:364` GraphQL, `real_ghrestclient.py:295`
REST), both shaped `{association, author, body, created_at, id}`. `canonical_comment` normalises
the fields the two adapters can spell differently: the login is lowercased, a trailing `[bot]`
is removed, and an empty author is written `ghost`; the time goes through `utc_time.parse_as_utc`
and is written as UTC seconds. The sort key is total, so a missing id never compares `None` with
an `int`.

The pinning rule is association or `pr_authors`, not `claim_trusted`. The claim set adds the
viewer, which is the admitting operator in `fr triage admit` and the collecting account in collect
and dispatch, and a different set on each side would void every admission. The driving account
is already expected in `pr_authors` (triage-hardening R7), and fr's own markers are posted by it.

`admit_marker` writes `"v":2` and the new human line. `parse_admit` returns a digest only for
version 2, so `latest_admit` and `intake_reason` need no version argument. The `fr-admit-v2`
first line guarantees no version-1 digest matches, even for an issue with no pinned comment.

Collect reads comments for admission only for a `ready-fr` issue that no other clause admits
(`_comment_needs`, unchanged). `_comment_facts` returns the digest computed from those comments
with the repo's `pr_authors`, and collect stores it as the issue's `content_digest` (on listed and
viewed issues alike, `collect.py:928`) in place of the title-and-body digest `_issue` computes
today (`collect.py:495`). For every other issue `content_digest` is `None`; only intake reads the
field, and only for that same set of issues.

Facts schema 22 (`FACTS_SCHEMA` is 21, `model.py:108`) marks the change. `load_facts` of a
schema below 22 sets `admit_read` False on every issue, then runs `_withhold_untrusted_text`
and the PR-title withholding of §B, as the below-17 load already withholds issue text
(`model.py:1838`).

`admit_recheck.recheck_admitted` reads the member's comments after its issue view and compares
`content_digest(title, body, comments, facts.config_for(repo).pr_authors)` with the stored
`admit_digest`. A failed comment read is a failed read.

### B. PR titles (R6, R7)

`_withhold_untrusted_pr_titles(facts) -> Facts` runs where `_withhold_untrusted_text` runs, over
every `PullRequest` facts holds: the top-level lists and every issue's `prs`. A PR keeps its title
only when `pr.author` is in `claim_trusted(facts.config_for(pr.repo), facts.viewer)`.

Readers of `PullRequest.title`: the pages (`render.py:721`, `:741`, `:1072`), the board's gated
cards (`kanban.py:977`, `kanban_render.py:709`), `fr triage check` JSON (`check.py:239`) and text
(`commands/triage_cmd.py:917`, `:930`), and the merge queue's squash subject
(`commands/triage_batch_cmd.py:6983`, `queue_exec._subject`). The display readers show the key,
URL and a withheld note for an empty title; the queue uses the batch's title. A batch PR opened
by a worker that runs as another account is withheld like any other untrusted PR; the operator
lists that account in `pr_authors` to keep its titles.

### C. The carried-text scan (R8, R9)

`guard_state` keeps its present steps (live state-repo visibility, keys and debt repos) and gains
the set of files the write carries: the `REF_FILES` walk for a push, the durable set for an
export. When the state repo is public, it builds the look-for set and reads each repo's
visibility (facts, else live, as `_fill` does now). When every repo is public, it returns before
reading any file. An org scope with no usable facts cannot name its members and refuses as
unreadable.

`carried_text_leaks` builds, per non-public repo, a case-insensitive pattern for `owner/name`, plus
`name#\d+` unless a public look-for repo has the same name, each bounded by `(?<![\w.-])` before
and `(?![\w-])(?!\.\w)` after, so `owner/name.` at a sentence end and
`github.com/owner/name.git` both match. It reads every carried file as bytes, decoded as UTF-8 with
replacement. A match yields `(relative path, repo)`. Certain leaks raise `PrivacyError`
through a new `refusal` branch naming the file, the repo and the remedy. A repo whose visibility
is unknown raises `VisibilityUnreadable`, so a looping drive retries. An `OSError` on a file
refuses with its path.

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

- triage-admit-pins-comments: none — CI unit tests on `content_digest` (a trusted comment changes nothing, an untrusted edit changes it), `parse_admit`/`intake_reason` for v1 and v2 markers, collect over a fake forge, the schema-21 load (admission unread, issue text and PR titles withheld), `fr triage admit` preview and `--yes` against a fake GhClient, and `recheck_admitted`
- triage-pr-title-withheld: none — CI unit tests on collect over a fake forge with an outside author's PR in each PR list, the older-schema load, `check` text and JSON output, the rendered PR row and gated card, and the queue's squash subject with a withheld title
- triage-state-scan-guard: none — CI unit tests on `guard_state` over a state directory whose `merge-stops.json`, a fragment file and `requests.yaml` name a private repo, a clean directory (no refusal), sentence-final and `.git` mentions, a public and a private repo sharing a name, the export set, the all-public short circuit (no file read), an org scope with no facts and an unreadable file
- triage-reopened-pr-uncarried: none — CI unit tests counting forge calls over two collects with a fake forge whose open-PR list is and is not cut at the limit

Every requirement is engine or render behaviour that fakes prove in CI; no released build shows
anything more.

## Out of scope

- Outside comments on issues admitted by a trusted author or association: no admission depends on
  their text, and the worker's brief already fences what it quotes. Not part of #1633.
- Outside authors' PR titles in `fr triage origins` data (`origins.py:218`) and the state-export target repo's own visibility (`commands/triage_state_cmd.py:106`): filed as follow-ups from spec review.
- A comment's text in facts: facts store no comments, so nothing there needs withholding.
- Rewriting history on a state ref that already carried a private name: the guard stops new
  pushes; it does not scrub old commits.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-28-triage-privacy | `derio-net/super-fr` | `2026-11-28-triage-privacy` | — |
