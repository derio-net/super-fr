# fr usage records an explicit `unavailable` capture when it finds no session — design

**Date:** 2026-09-26
**Slug:** `2026-09-26-usage-unavailable-when-no-session`
**Status:** design (fr-goal, autonomous)
**Repo:** `derio-net/super-fr` (single-repo change)
**Fixes:** derio-net/super-fr#636 (cheapest cut only)

## 1. Goal

When `fr usage`'s capture finds **no session at all** — which is what happens
on OpenCode, where `candidates()` (`packages/fr/src/fr/usage/capture.py:95`)
finds nothing through the cursor, the workspace bindings, or
`current_session` (which reads only `CLAUDE_CODE_SESSION_ID`) — `capture()`
today writes `sessions: []` as though it were a successful, measured capture.
`docs/superpowers/implemented/usage/2026-09-26-fix-models-opencode-noop-505.yaml`
is the live example. Every reader then sees "a capture with nothing in it",
which reads as a free run.

Fix: in that case write **one explicit unavailable entry** with a reason, so
every reader renders `—` with the reason and nothing mistakes an empty list for
zero cost. Capture stays never-raising.

### Non-goals

- **No change to session discovery.** `fr/run/telemetry.py::current_session`
  is untouched: another batch is editing it, and OpenCode discovery needs
  super-fr#537 (the plugin binding its session id, paired with #530) first.
  This change makes the absence *visible*; it does not make it go away.
- No change to `require_sessions` (see §3.3).
- No schema change (see §3.1).

## 2. Background — verified in code

- `capture()` (`capture.py:144-201`): `pairs = candidates(...)`; `if
  require_sessions and not pairs: return None`; otherwise loops `pairs` into
  `entries`, so with no pairs `entries == []` and the written `Capture` has
  `sessions=()`, dumped as `sessions: []` (`file.py:353`).
- `require_sessions=True` is passed only from a new host's first
  `fr run resolve` (`commands/run_cmd.py:448`); `deliver`, `closeout` and
  `archive` capture with it `False`, which is where the empty list is written.
- The unavailable shape already exists and is already an allowlisted,
  committed shape: `SessionEntry(session=..., unavailable=<reason>)` (`file.py:76`),
  and the OpenCode and Hermes readers already return
  `unavailable("", HARNESS, "no session id given")` with an **empty** session id
  (`readers/opencode.py:121`, `readers/hermes.py:67`). The committed-reason
  vocabulary is closed (`_KEPT_REASONS`, `file.py:191`; `committed_reason`
  maps anything else to `reader failed`).
- Readers of the file: `run/cost.py::effective_entries` keys sessions by
  `entry.session` and already treats an `unavailable` entry as "no figure"
  (never as zero); `run_usage_split.py` only re-hosts captures.
- `capture._merge` (`capture.py:122`) carries an earlier capture's entries
  forward when a re-capture no longer sees them. Unmodified, a placeholder
  written by an earlier capture would survive forever beside real sessions.

## 3. Design

### 3.1 The entry (decision: empty session id)

When `pairs` is empty (and `require_sessions` is false), `capture()` builds
`entries = [session_entry(unavailable("", harness_now, NO_SESSION_FOUND), ...)]`
where the reason is `"no session found"` — a new member of `_KEPT_REASONS`, so
the committed vocabulary stays closed and `committed_reason` keeps it verbatim.
`harness_now` is already computed for the capture and the entry's reason is
harness-neutral; the harness lives on the `Capture` (`harness: opencode`).

The entry carries `session: ""`, the same convention the readers already use
for "no session id given". This is **not a shape change**: `SessionEntry`
already permits it, `schema_version` stays 1, no released `fr` rejects the file
(unavailable entries with a session id are read today). So under
`.claude/rules/artifact-versioning.md` no stamp bump, migration or new
validator is owed; a test pins that the file still validates and round-trips.
(The rule's own test for "shape": would an older reader raise? It would not.)

### 3.2 A later real capture drops the placeholder (decision: drop)

`_merge` discards a previous entry with `session == ""` and
`unavailable == "no session found"` whenever the new capture has entries of its
own with real session ids. Real per-session unavailable entries keep today's
behaviour (kept, unless a fresh read replaced them). When the new capture is
*also* empty, the fresh placeholder simply replaces the old one (same host,
one entry) — never two.

### 3.3 First-resolve path unchanged (decision: keep skipping)

`require_sessions=True` still returns `None` on no sessions. A mid-run resolve
with nothing to read is "not a capture"; stamping a run `unavailable` before it
has done anything would be noise. Only `deliver`, `closeout` and `archive`
write the placeholder.

### 3.4 Rendering and cost

`fr run cost` / `fr usage report` from the file already render an
`unavailable` entry as `—` with its reason. A test pins that a file consisting
solely of the placeholder produces no total and shows the reason, never `$0`.

## 4. Approach: debugging-first

This is a bug. Phase 1 opens with a failing test that reproduces it (empty
`candidates()` → `deliver` capture → `sessions == ()`), then the fix.

## 5. Risks

- **`session: ""` collides in `effective_entries`** across captures on
  different hosts (keyed by session). Harmless: all are unavailable, and the
  loop keeps an unavailable entry only when nothing better is held.
- **Reason text drift**: mitigated by putting the string in one module constant
  used by both `capture.py` and `_KEPT_REASONS`, with a vocabulary test.

## 6. Test Plan (post-merge, operator-driven)

1. On an OpenCode run with no bound session, `fr run resolve --step deliver`
   writes `sessions: [{session: '', unavailable: no session found}]`, never
   `sessions: []`.
2. `fr run cost <run-id>` on that run prints `—` and the reason for it, no
   dollar total.
3. After session discovery lands (#537), a later closeout capture on the same
   host replaces the placeholder with the real sessions.

## Implementation Plans

One phase (tier: standard) — `2026-09-26-usage-unavailable-when-no-session`.

## 7. Acceptance rows (born here; presented at spec review)

- `usage-no-session-is-unavailable-not-free` — *Operator reading a run's usage
  never mistakes "no session was found" for a free run.* Defense: the business
  claim is honest cost reporting; verified at unit level over
  `capture`/`fr run cost`; OpenCode live proof stays owed until #537.
