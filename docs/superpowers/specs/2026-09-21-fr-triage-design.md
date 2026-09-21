# Backlog triage that runs anywhere: `fr triage` and the `fr-triage` skill

- **Date:** 2026-09-21
- **Status:** designed
- **Origin:** a Backlog Triage board built by hand in one Claude Code session and published as
  a claude.ai Artifact. It worked, and it proved the shape. It also proved three limits this
  spec exists to remove: it only runs where the Artifact tool exists, its data was typed into
  the page by the agent that built it, and it covered one repo.

## 1. Problem

Ranking a backlog is recurring work, and super-fr has no tool for it. The one board that exists
was assembled ad hoc, and the session that built it surfaced what a durable version must do
differently.

**It is tied to one harness.** The board is an Artifact. OpenCode and Hermes have no Artifact
tool, so the capability is Claude-Code-only by construction — the exact class of gap
`fr harness parity` exists to catch.

**Its data had no engine.** Every row — title, stage, PR number — was typed into the page by the
agent. Keeping it current meant re-querying `gh` and hand-editing, and it drifted: three syncs in,
the board still said "Forty-two open" in prose after the count had moved, and four newly filed
issues were simply absent until someone noticed. Nothing reported them missing.

**Its judgement was unchecked where it mattered most.** The value of a triage is in claims like
"verified in code" and "this is the one to look at". One such claim was wrong on arrival: #493 was
ranked as live work when the row it challenged had already been fixed by the commit at `main`'s
HEAD. The issue's quoted YAML was trusted instead of re-read. A triage that ranks stale claims as
live is worse than none.

**It covered one repo.** An org owner wants the same view across every repo they own.

## 2. Goal

An operator on **any** harness can say "triage this repo" or "triage this org" and get a ranked,
filterable backlog board as a **local HTML file**, kept current by re-running one command, with
the ranking judgement verified against code rather than copied from issue text.

### Non-goals

- **Forges other than GitHub** (decision `d2`). Every forge call sits behind one seam in
  `fr/triage/collect.py`; GitLab and Gitea are a follow-up issue, not this PR.
- **Writing to the forge.** `fr triage` never comments, labels or closes. The skill may
  *recommend* a close or a dedupe; acting on it stays an operator-confirmed step.
- **Editing status in the page** (decision `d3`). The page is read-only; see §3.E.
- **Knowing about fr runs.** A stage like "an fr-goal run is building this" would need
  `fr isolation status`, which only exists on one machine and only in repo scope. Stages come from
  forge facts alone.
- **An LLM inside the engine.** Judgement is data the agent writes. The engine makes no model
  call (`no-claude-p-batch`: separate the engine from the transport).

## 3. Design

### A. An `fr` verb, because only the wheel reaches every harness

`scripts/sync-opencode.py` and `scripts/sync-hermes.py` both mirror **only** `SKILL.md`: the
canonical glob is `*/SKILL.md` and the writer emits `dest_dir / "SKILL.md"`. A script or template
bundled beside a skill would reach Claude Code and silently never reach OpenCode or Hermes. Every
existing `fr-*` skill is a single `SKILL.md` for this reason.

So the deterministic engine is `fr triage`, shipped in the `fr` wheel, and `fr-triage` is thin
prose over it — the pattern `fr run`, `fr journal` and `fr acceptance` already establish. Three
verbs:

| verb | reads | writes | deterministic |
|---|---|---|---|
| `fr triage collect` | the forge | `facts.json` | yes, given the same forge state |
| `fr triage check` | facts + judgements | stdout (or `--json`) | yes |
| `fr triage render [--open]` | facts + judgements | `triage.html` | yes — same inputs, same bytes |

"Sync" is `collect` then `render`. Judging new issues is the skill's job, between the two.

### B. Scope and where state lives (decision `d1`)

Exactly one of `--repo OWNER/REPO` or `--org OWNER`. The scope names a directory:

| flag | scope | directory |
|---|---|---|
| `--repo derio-net/super-fr` | `derio-net--super-fr` | `$HOME/.cache/fr/triage/derio-net--super-fr/` |
| `--org derio-net` | `derio-net` | `$HOME/.cache/fr/triage/derio-net/` |

`$HOME/.cache/fr` is fr's existing cache root — worktrees, sentinels, session bindings and the
gc lock all live there, resolved through `fr.isolation.types._home()`. Triage joins that tree
rather than honouring `XDG_CACHE_HOME`, which nothing else in `fr` reads; splitting fr's cache
across two roots would be worse than either (spec-review `r1`). The `<owner>--<repo>` form mirrors the marketplace
naming convention in `AGENTS.md`, so a scope name is never ambiguous between a repo and an org.
`--dir <path>` overrides the location for an operator who wants the state in git.

Because the state is never committed by default, it is **not an artifact kind**: no
`fr.artifacts.registry` entry, stamp, migration or structure validator. Each file still carries
`schema: 1`, and a reader refuses an unknown value with a message naming the file, rather than
guessing.

Keeping it out of git by default also means triaging an employer's or a customer's org can never
land in a public repo (`.claude/rules/third-party-privacy.md`).

### C. `collect` — two calls per repo, inverted

Per repo, two bulk `gh` calls, and no per-issue calls:

1. `gh issue list --state open --limit 1000 --json number,title,labels,createdAt,updatedAt,url,body`
2. `gh pr list --state all --limit 200 --json number,title,state,isDraft,mergedAt,url,headRefName,closingIssuesReferences`

Both limits are explicit on purpose: `gh`'s default `--limit` is **30**, so an unspecified list
would silently truncate any backlog past thirty issues — the same "rows silently absent" failure
§1 describes. `collect` reports when a list returns exactly its limit, since that means it may
have been cut short. `--pr-limit` raises the PR window for a repo with a long merge history.

The PR list is inverted into issue → PRs. This direction is deliberate: verified live on
2026-09-21, `closingIssuesReferences` on a PR reliably names the issues it closes, while the
per-issue `closedByPullRequestsReferences` is the expensive direction.

**The inversion keys on the reference's own repository, never the PR's** (spec-review `r2`).
Each reference carries `repository.owner.login` and `repository.name`, and a PR in one repo can
close an issue in another. Keying on the PR's repo would attach an org's cross-repo PRs to
whatever same-numbered issue sat in the wrong repo — a plausible, wrong board. A reference whose
repository is outside the scope is dropped: in repo scope that means any other repo, in org scope
any other owner.

Org scope enumerates repos with `fr.gh.list_repos(owner=, include_archived=True)`. The repo list
is a third list that can be cut short, so it gets the same treatment: when it returns exactly its
limit, `collect` records the possibly-truncated warning (review `r-p1-repo-cap`). Archived repos
are counted *before* they are dropped. Counting after the filter would hide a full list that
happens to contain archived repos, which is precisely the truncation the warning exists for.

**When there is nothing to show, exit 2 rather than write a board** (review `r-p2-empty`). Repo
scope whose one repo fails, and org scope where every repo is skipped, both exit 2 with the
reasons. An empty `facts.json` would render as a clean backlog, a failure reported as a clean
result. The "one unreadable repo never aborts the board" rule is about org scope with at least one
readable repo.

**A judged issue that could not be viewed is recorded, not dropped** (review `r-p2-unviewed`).
`view_issue` fails for a deleted issue, and also for a rate limit, a 5xx or a token without access.
The forge's reply does distinguish them, but only as prose (`Could not resolve to an issue…` for a
missing one), and fr does not classify on error strings, which are brittle. So every failure is
recorded under `unviewed` with its reason verbatim. `check` reports it as unreachable, never as
orphaned, and the skill tells the agent to confirm a not-found reason before recommending removal
(the GREEN run and the phase-4 review showed this sentence originally overstated the forge).

A repo whose issue list fails — issues disabled, no access — is recorded under
`skipped` with its reason and the collection continues. One unreadable repo never aborts the
board.

A judged issue that is no longer open still needs its closed state. For each judgement key
absent from the open set, one `gh issue view`. That is bounded by the number of judgements, not
the size of the backlog.

Bodies are stored truncated (first 2,000 characters), enough for the agent to triage from one
file and for the page to excerpt an unranked issue.

Every forge call goes through a `Forge` protocol with one implementation, `GhForge`, backed by
`fr.gh`. That protocol is the whole of decision `d2`'s seam: a second forge is a second class,
not an edit to the collector.

### D. `judgements.yaml` — the agent's half, as data

```yaml
schema: 1
ranked_at: 2026-09-21
tiers:
  - {n: 1, title: Data loss, description: Work destroyed with no prompt or salvage.}
  - {n: 2, title: Silent wrongness, description: The failure looks like success.}
issues:
  "super-fr#435":
    tier: 1
    theme: isolation
    cx: S            # XS | S | S-M | M | L | -
    verified: true   # re-read in the code, not copied from the issue
    detail: "`gc()` trusts `pr_state == MERGED` and calls `down(force=False)` …"
    note: ""         # free-form; the operator's or the agent's
patterns:
  - {title: A fact about remote state used to justify local destruction, ids: ["super-fr#435"], body: "…"}
```

**Key grammar:** `"<repo-name>#<number>"` in **both** scopes, so there is one code path. In
repo scope every key simply shares a prefix.

**Keys and scope names are case-insensitive, and lowercase is canonical** (review
`r-p2-case`). GitHub repo names are case-insensitive, so `Super-FR#5` and `super-fr#5` are the
same issue, and `--repo Derio-Net/Super-FR` must name the same state directory as
`--repo derio-net/super-fr`. Every key is lowercased at one point, on construction and on load,
and `collect`, `check` and `render` all compare through that one function. Two judgement keys that
differ only by case are refused on load as a conflict, never silently merged.

`detail`, `note` and pattern `body` accept exactly two inline forms — `` `code` `` and
`**bold**` — applied **after** HTML escaping. Nothing else is interpreted.

### E. Stages are derived, never set (decision `d3`)

| stage | derived when |
|---|---|
| `closed` | the issue is closed |
| `merged` | open, but a PR naming it has merged |
| `pr-ready` | open, with an open non-draft PR naming it |
| `pr-draft` | open, with an open draft PR naming it |
| `blocked` | open, no open or merged PR, and carrying a label named `blocked` (case-insensitive). A PR closed without merging advances nothing, so it does not unblock (review `r-p2-blocked`) |
| `backlog` | anything else |

The most advanced linked PR wins. The page is read-only; "moving" an issue means doing the work
and re-running `collect`. This deliberately differs from the Artifact board, which had a shared
server-side store. A local file has none, and browser `localStorage` would create a second source
of truth invisible to the agent. `localStorage` is used only for the viewer's own filter and sort
preference.

### F. `check` — make debt visible

`check` reports four sets:

- **unranked** — in `facts`, with no judgement. These are the rows the board silently lacked.
- **settled** — judged, and now `closed` or `merged`. Kept and rendered as done; listed so the
  agent can note what shipped.
- **orphaned** — a judgement whose key names **no repo collect read**: a typo'd or renamed repo,
  or one outside the scope. That is its only meaning, which makes it the only set an agent may act
  on without asking the forge again.
- **unreachable** — a judgement collect could not settle either way, reported with its reason:
  its issue is in `unviewed` (the forge would not show it, including a deleted issue or a typo'd
  number, whose reason says so), its repo is in `skipped`, or its key names a collected repo but
  was added after the last collect (reason: "judged after the last collect"). Pruning on any of
  these would destroy a ranking over a transient failure or stale facts (reviews `r-p2-unviewed`,
  phase-4 C1 and C2).

A deleted issue is therefore unreachable, not orphaned. An earlier draft said the opposite, and
it was wrong: collect views every judged key in a collected repo, so a deleted issue always
reaches `unviewed`. Only a key whose repo was never read can be absent without a recorded reason.

It exits 0 in every case. The sets are the work queue for the skill, not a failure. `--json`
emits them for machine use.

**Every forge-sourced string `check` prints goes through `rich.markup.escape`** (spec-review
`r7`). Issue titles are arbitrary text, and rich parses `[...]` as markup, so a title like
`[manual] …` would silently lose its prefix and one containing `[/red]` would raise
`MarkupError`. That is exactly #525's defect class, open in ~44 existing sites. This command must
not become the 45th.

### F′. Exempt from the migration gate, on the list's own criterion

`fr.artifacts.trigger.READ_ONLY_COMMANDS` holds the commands that "promise not to mutate the
repo's artifacts" — `status`, `skills`, `isolation`, `init`, `validate`, `harness`. `triage`
meets that promise strictly: it never reads or writes a registered artifact, and every file it
writes is under its own state directory (spec-review `r3`).

Leaving it gated would refuse an agent's triage — commonly an org triage run from inside some
unrelated repo — over stale artifacts the command never touches. That refusal protects nothing.
The gate exists so that no command proceeds *over* a stale artifact, and triage cannot. The list
is pinned by `test_the_exemption_list_is_exactly_these_things`, so this argument lands as a diff
to that test, which is the rule's intended cost for widening it.

### G. `render` — deterministic, self-contained, safe

One HTML file, following `fr.acceptance.report`'s pattern: a pure Python renderer, inline CSS,
`html.escape` on every forge-sourced string.

- **Rows are rendered in Python**, grouped by tier, with the filter and sort keys as `data-*`
  attributes. The ~80 lines of inline JavaScript only show, hide and reorder rows. The content is
  complete with JavaScript off, and tests assert on HTML rather than a DOM.
- **Unranked renders first and loudly**, as its own tier: "not yet triaged — run the fr-triage
  skill". An unjudged issue is the most important thing on a stale board.
- **Deterministic:** no clock read at render time. Every timestamp shown — `collected_at`,
  `ranked_at` and each row's filed date — is read from the facts or the judgements, never from
  the clock. The same facts and judgements give the same bytes.
- **Untrusted text is inert.** Issue titles, bodies and labels come from anyone who can file an
  issue, and in org scope that is many people. They are escaped, and the facts blob is never
  interpolated into a `<script>` element. It works offline: web fonts, if reachable, degrade to
  the system font stack.
- Light and dark themes via `prefers-color-scheme`, and phone-width layout, both carried over from
  the Artifact board.

`--open` hands the path to Python's `webbrowser`, which works from any harness's shell tool.

### H. The `fr-triage` skill

Under 120 lines (`test_skill_validation.py`), harness-neutral (`fr.harness.prose.scan_prose`),
authored with `superpowers:writing-skills` discipline: a **baseline run without the skill
first**, then the skill written against the observed failures, then a re-run.

It carries the judgement discipline that is the actual value, most of all:

1. **Rank by what the failure costs**, not by age, label or reporter.
2. **Verify before claiming verified.** Re-read the cited `file:line` at the current `main`. An
   issue's quoted snippet is a claim about the past. #493 is the worked example, and it is the
   baseline scenario (§5).
3. **Hunt duplicates and batches.** Same predicate, same file, same sentence: #433/#470,
   #439/#526, and #472/#529, where one line fails in two opposite directions.
4. **Never act on the forge unasked.** Recommend a close or a dedupe; the operator confirms.

It drives `collect → check → judge the unranked → render --open`, and treats a re-run as the sync.

## 4. Risks

- **`gh` field drift.** `closingIssuesReferences` is the load-bearing field. A captured fixture
  pins its shape, and a missing field fails collect loudly rather than rendering every PR as
  unlinked.
- **The PR window is already full for this repo.** At capture on 2026-09-21,
  `gh pr list --limit 200` on `derio-net/super-fr` returned exactly 200. So the
  possibly-truncated warning will fire on the first real super-fr board. That is the warning
  working, not a bug. A linked PR older than the newest 200 is missed, which only matters for
  an old issue whose PR is also old, and `--pr-limit` widens the window.
- **Large orgs.** Two calls per repo is linear in repos. At derio-net's 19 that is fine. An org
  of hundreds would want `gh search`, which is a follow-up if it is ever needed, not a guess made
  now.
- **Stale judgements look authoritative.** The `ranked_at` date is rendered in the masthead, and
  settled issues are listed by `check`, so an old ranking reads as old.
- **Prose that is only prose.** The verify-before-claiming rule is skill text. Nothing can force
  an agent to re-read a file. The baseline/re-run pair in §5 is the evidence it changes behaviour,
  and it is recorded honestly if it does not.

## 5. Test Plan

**In this PR:**

1. Unit, `collect`: a fake `Forge` fed **captured** `gh issue list` / `gh pr list` JSON from
   `derio-net/super-fr` (public, `derio-net`-owned, so no redaction is needed). The PR → issue
   inversion, the most-advanced-PR rule, body truncation, both `--limit` values actually passed,
   and the possibly-truncated warning when a list returns exactly its limit.
2. Unit, `collect` in org scope: a repo whose issue list fails lands in `skipped` with its reason,
   and the other repos still collect. A PR in repo A whose `closingIssuesReferences` names an
   issue in repo B attaches to **B's** issue, not to A's same-numbered one, and a reference to a
   repo outside the scope is dropped (`r2`).
3. Unit, stage derivation: one case per row of §3.E, including "a merged PR naming a still-open
   issue" → `merged`.
4. Unit, `check`: the unranked, settled, orphaned and unreachable sets — a judgement in `unviewed` or in a `skipped` repo is unreachable, never orphaned — and exit 0 in every case. An issue
   titled `[manual] x [/red]` prints verbatim and does not raise (`r7`).
4a. Unit: `triage` is in `READ_ONLY_COMMANDS`, and the pinned exemption-list test is updated
   with the argument from §3.F′ (`r3`). The state directory is `$HOME/.cache/fr/triage/<scope>`
   under a sandboxed `HOME` (`r1`).
5. Unit, `render`: an unranked issue renders in the first tier; a judged one renders in its own
   tier.
6. Unit, `render`: an issue title of `<script>alert(1)</script>` and a body containing
   `</script>` render inert, and the inline-markup allowlist permits exactly `` `code` `` and
   `**bold**`.
7. Unit, `render`: two renders of identical inputs are byte-identical.
8. Unit: a `schema` other than `1` in either file is refused with a message naming the file.
9. Skill: `test_skill_validation.py`, the neutrality tripwire and both mirror tripwires pass with
   `fr-triage` included.
10. Skill (writing-skills RED/GREEN): a subagent given the fr-triage task **without** the skill,
    where one issue quotes code already fixed on `main` (#493's captured body against the current
    `parity.yaml`). The run is recorded, then repeated with the skill. The claim under test is
    that, with the skill, the agent re-reads before marking `verified`. The observed result goes
    into the journal whether or not it confirms.

**Post-merge, operator-driven** (decision `d4`):

11. On **Claude Code**: `fr-triage` on `derio-net/super-fr`, then on the `derio-net` org, and open
    both boards.
12. On **OpenCode**: the same repo-scope walk, which proves an agent on a harness without the
    Artifact tool can follow the skill end to end. It may ride along with the OpenCode
    verification run already in progress.
13. **Hermes**: not walked. The acceptance row is recorded `not-implemented` with that reason.

## 6. Evidence hygiene

Fixtures are captured from `derio-net/super-fr`, a public repo in the `derio-net` org, so there
is nothing to redact under `.claude/rules/third-party-privacy.md`. The org-scope unit test uses
fictional repo names. Any live walk against a non-`derio-net` org is recorded with the host and
org redacted.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-21-fr-triage | `derio-net/super-fr` | `2026-09-21-fr-triage` | — |
