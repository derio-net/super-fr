# Drive collects only what changed each pass — design

**Date:** 2026-10-04
**Slug:** `2026-10-04-drive-scoped-collect`
**Status:** design (fr-goal, autonomous)
**Repo:** `derio-net/super-fr` (single-repo change)
**Closes:** derio-net/super-fr#911

## 1. Goal

Every pass of `fr triage batch drive` re-collects the scope's facts through
`collect_into` (`packages/fr/src/fr/commands/triage_cmd.py`), exactly as
`fr triage collect` does. The bulk part of that collect is cheap: three list
calls per repo plus one config read. The expensive part is
`collect_facts`'s per-key loop (`packages/fr/src/fr/triage/collect.py`,
`_judged_elsewhere` and the `forge.view_issue` call after it). It runs one
`gh issue view` for **every judged key that is not in the open-issue list**,
which means every settled issue the judgements still name. On this repo that
was more than 200 serial calls per pass, about 10 minutes against a 120 s
`--interval`, and each call was another chance to stall (gh#911, found in the
wave-driver Test Plan item 16 live run during a GitHub API degradation).

This change makes a drive pass view only the keys whose state could have
changed since the previous pass. Everything already known to be closed is
carried over from the previous `facts.json`.

### Non-goals

- `fr triage collect` stays a full re-read. It is the explicit refresh that
  heals any drift the carry-over allows (decision `d2`).
- No change to the bulk list calls, the config read, the `fr:in-progress`
  comment reads, the batch head-branch lookups or the snapshot's live PR reads.
  Each is bounded by repos, in-progress issues or batches, never by the
  settled backlog.
- No change to the `facts.json` shape (`Facts` stays as it is). `facts.json`
  is cache state under `~/.cache/fr/triage/`, not a registered artifact kind.

## 2. Background — why carrying "closed" is safe

All of a key's possible transitions are already visible without a view:

| Previous facts say | This pass's bulk lists say | What it means | View? |
|---|---|---|---|
| (any) | key is in the open-issue list | open now, reopened included | no: the list is the record |
| (any) | key is a listed PR | a judged PR (gh#902) | no: already handled by `listed_prs` |
| `closed` | not in the open list | still closed | **no: carry over** |
| `open` | not in the open list | it just closed, or moved/deleted | yes |
| unviewed (`facts.unviewed`) | not in the open list | last read failed | yes: the #916 retry |
| absent | not in the open list | never seen | yes |

The one thing a carried issue can get wrong is the detail of a **closed**
issue that changed while closed: its title, labels or `closed_at`, or a
transfer or deletion. None of those changes a batch's stage, because a
batch's stage reads only member state and PR links. The PR links are
recomputed every pass. `fr triage collect` repairs the rest.

## Requirements

R1. A drive pass does not call `view_issue` for a judged key that the previous `facts.json` (same scope) records as a closed issue in a repo this pass collected. That issue is carried into the new facts as closed, with its PR links recomputed from this pass's PR lists.
R2. A drive pass still views a judged key that is not open now and that the previous facts recorded as open, recorded as unviewed, or did not record at all. The result is exactly what `fr triage collect` would produce for that key.
R3. A judged key that is open again appears as open in a drive pass's facts, whatever the previous facts said.
R4. When the previous `facts.json` is missing, unreadable, or for a different scope, the drive pass collects exactly as `fr triage collect` does.
R5. `fr triage collect` never carries over: it views every judged key that is not open, as today.
R6. Each drive pass prints one line naming how many issues the collect viewed and how many it carried over.
R7. A carried-over issue's batch is staged exactly as a fully collected one would be when the issue did not change while closed. A merged batch whose members were all closed before the pass stays `merged`, not `partial`.

## Design

### A. The engine: `collect_facts(..., carried=...)`

`collect_facts` gains one keyword argument, `carried: Iterable[Issue] = ()`:
closed issues the caller vouches for. Inside the existing judged-elsewhere
loop (after the `listed_prs` check, before `forge.view_issue`), a key found
in `carried` (by normalised `Issue.key`) whose issue is `closed` and whose
repo is in `collected` is appended as
`issue.model_copy(update={"prs": linked(repo, number), "dispatch_marker_at": None})`.
It costs no forge call. Every other key takes the existing view path,
unchanged. The default `()` keeps every current caller byte-identical (R5).

The engine stays pure. It never reads a previous `facts.json` itself; the
command layer decides what to vouch for.

`collect_facts` must also report how many issues it viewed and how many it
carried, for R6. `Facts` is a strict model written to disk and cannot take
the counts, so the counts come back beside it (a small `CollectStats`
`(viewed, carried)` value, or an equivalent return, chosen in the plan).

### B. The command layer: `collect_into(..., carry=False)`

`collect_into` gains `carry: bool = False`. With `carry=True` it reads the
previous `<target_dir>/facts.json` (it already reads it for
`_previous_batch_prs`). If that file loads, and its `scope`/`kind` match
this scope, every issue in it with `state == "closed"` is passed as
`carried`. If the file is missing, unreadable (`TriageError`), from an older
schema, or for another scope, the carried set is empty, which is a full
collect (R4). Keys in the previous `unviewed` list are never carried,
because they were never issues in the facts (R2).

`collect_command` keeps calling `collect_into` with the default
`carry=False` (R5, decision `d2`). `recollect` (the driver's per-pass
collect, `triage_batch_cmd.py`) calls it with `carry=True` on every pass,
the first pass of an invocation included (decision `d3`).

### C. The pass line

`recollect` prints one line per pass, through the driver's existing
`_say`, before the pass's action lines:

    collect: <V> issues viewed, <C> carried over

`plural()` handles the singular (`1 issue viewed`). The line names only the
per-key reads this change bounds. The bulk lists are constant per repo and
need no count (decision `d4`).

### D. Tests (TDD, unit)

- engine: a fake `Forge` that counts `view_issue` calls. A carried closed
  key is not viewed and keeps its fields, with fresh links (R1). A
  previously open, unviewed or unseen key is viewed (R2). A carried key
  that is in the open list is open and not duplicated (R3). A carried key
  in a skipped or uncollected repo is not emitted. `carried=()` behaves
  exactly as before (R5).
- command: `collect_into(carry=True)` with no, corrupt, or other-scope
  previous facts views everything (R4). `collect_command` never carries
  (R5).
- driver: a two-pass drive whose second pass makes zero `view_issue` calls
  for settled keys and prints the `collect:` line (R1, R6). A merged batch
  whose members were all carried stays `merged` (R7).

## Risks

- **Drift on closed issues** (retitled, relabelled, transferred, deleted
  while closed) persists in a long drive. That is accepted: it touches no
  stage, the board shows it until the next `fr triage collect`, and
  `collect` heals it.
- **A transferred or deleted closed issue** is carried as closed instead of
  being reported unreachable by `fr triage check`. It is the same drift, and
  the same heal.

## Test Plan (post-merge, operator-driven)

1. On this repo, run `fr triage collect --repo derio-net/super-fr`, then
   `fr triage batch drive --repo derio-net/super-fr --once` (plan mode).
   The `collect:` line shows a small viewed count and a carried count near
   the number of settled judged issues. The pass takes seconds, not minutes.
2. Run `fr triage check --repo derio-net/super-fr`. Its settled count
   matches the one from right after the full collect.

## Acceptance rows (born here; presented at spec review)

- `drive-collect-carries-closed` (R1, R3, R7), unit
- `drive-collect-views-what-changed` (R2, R4), unit
- `collect-stays-full` (R5), unit
- `drive-collect-cost-line` (R6), unit
- `drive-pass-fast-on-settled-backlog` (Test Plan 1), `verify: post-merge`
