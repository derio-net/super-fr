# Triage claims across scopes and hosts — design

Issue: derio-net/super-fr#1043. Batch `triage-claims`, wave 10.

## 1. Goal

`fr triage` scopes overlap: one repo, a group of repos (`--repo A/B,C/D`) and a
whole org (`--org`) can all contain the same issue, and each may be driven from a
different host. Nothing coordinates them. `drive.lock` lives in one scope's state
directory on one machine, so a driver on another host, or on an overlapping scope
on the same host, never sees it. The one cross-host guard (a proposed batch
refuses to dispatch when its branch is already on `origin`) has a window of
minutes, because a session pushes its branch only after its first commit. Two
drivers on overlapping scopes would duplicate dispatches, race to update and
merge the same ready PRs, start duplicate close-outs (#883, across hosts) and
render different boards.

This change coordinates on the **issue**, the one object every scope shape
shares. A scope **claims** each issue it plans to act on: an `fr:claimed` label
plus a hidden marker comment naming the claiming scope. Every other scope still
judges a claimed issue, but never batches, dispatches, merges, closes out or
archives it. Claims carry a heartbeat and expire. Expired claims are reported,
and only the operator takes one over. Each driving scope publishes its own named
board after each pass, through a command the operator configures for that scope.

### Non-goals

- Security. A claim is a coordination mark: anyone with write access can forge
  or delete one. "Signed" means "names its signer". The PR-author allowlist
  (`pr_authors`) still guards merging.
- Exclusive judging. Two scopes may rank the same issue differently; only acting
  on it is exclusive.
- Automatic take-over of an expired claim (operator decision, §2.2).
- Claims on GitLab or Gitea. They follow every other batch write: GitHub only
  (gh#611); the glab and tea adapters raise `UnsupportedForgeOperation`.
- fr publishing a page itself. Publishing stays outside fr (wave-driver R12):
  fr runs the operator's command and nothing else.
- Coordinating `fr triage render`, `origins` or `architecture`. They write no
  forge state.

## Requirements

R1. Each triage scope on a host has a scope id `s-<sha256(<scope name> NUL <host id>)[:8]>`. The host id is a random token generated once and stored in `~/.config/fr/host-id`, and `FR_HOST_ID` overrides it. No hostname, path or scope name appears in a scope id. `fr triage scope show` prints the scope's name, id, state directory and scope config.
R2. A claim on an issue is the `fr:claimed` label plus one hidden marker comment per signer, holding the signer's scope id, the batch id, claimed-at, heartbeat and expires-at, followed by one human-readable line. No hostname, path or scope name is written to the forge.
R3. A claim is owed for every member of a batch with a wave from the moment the wave is set, and for every member of a wave-less batch at its dispatch. `batch create` and `batch edit` write the claims they make owed only with `--yes`; without it they print the owed claims and the command that writes them. `fr triage claim sync --yes` and every `batch drive --yes` pass write every owed claim before any other action, and `batch dispatch --yes` claims before any other forge write.
R4. After writing a claim, the writer re-reads the issue's comments. When more than one live claim exists, the oldest marker comment wins; a writer that lost withdraws its own marker in the same call and reports the issue as held by the winner.
R5. `batch create`, and `batch edit` with `--add-issue` or `--wave`, refuse (exit 2, nothing written) an issue that facts show claimed by another scope, naming the holder, its batch and its expiry. For an expired claim the refusal names `fr triage claim take`.
R6. Neither the driver nor `batch dispatch`, `batch merge` or `batch cancel` acts on a batch with a member claimed by another scope, live or expired. The driver emits one `held` action per such batch, naming each member and its holder, and leaves the batch alone that pass. The commands refuse with exit 2.
R7. `fr triage check` reports two more sets: `held elsewhere` (open issues with another scope's live claim: key, holder, batch, expires-at) and `expired claims` (every claim, this scope's or another's, past its expires-at). Both appear in text and in `--json` (`held_elsewhere`, `expired_claims`), and `check` still exits 0.
R8. Each `batch drive --yes` pass and `claim sync --yes` refresh this scope's own live claims by editing their marker comment in place (new heartbeat and expires-at) once the heartbeat is older than a quarter of the expiry. A refresh never posts a second marker. The expiry is 24 hours unless the scope config's `claim_expiry_hours` says otherwise, and it is written into the marker, so every reader judges expiry from the marker alone.
R9. An expired claim is never taken automatically. `fr triage claim take <key> --batch <id> --yes` replaces another scope's expired claim with this scope's claim for one of this scope's batches containing the issue; it is refused while the claim is live. `fr triage claim release <key> --yes` withdraws this scope's own claim at any time, and another scope's only once expired. Without `--yes` both print what they would write.
R10. A claim is released (marker edited to its released form, `fr:claimed` removed once no live claim remains) when its batch is cancelled with `batch cancel --yes`, when the drive pass or `claim sync` sees the batch closed out (merged, partial or abandoned), when `batch edit --remove-issue --yes` drops the member, and when `batch edit --no-wave --yes` clears the wave of a proposed batch.
R11. A live batch of this scope with no claims yet (dispatched before this change) is claimed by the first `drive --yes` pass or `claim sync --yes`. When another scope already holds a member, R6 applies.
R12. The GitHub client's `list_issue_comments` returns each comment's numeric id and its client gains `edit_issue_comment(repo, comment_id, body)`. `collect` reads the comments of every open issue labelled `fr:claimed` and records each signer's latest claim on the issue in facts (facts schema 6; schemas 3–5 still load).
R13. `board.html` shows a "Held elsewhere" group listing the scope's issues claimed by other scopes, with holder, batch and expiry, marking expired claims. Each of this scope's batch cards shows when its claims expire.
R14. A scope may carry a scope config, `<state dir>/scope.yaml`, with `claim_expiry_hours`, `board_name` and `publish`. `publish` is an argument list with `{board}`, `{name}` and `{scope_id}` placeholders. fr runs it after every `drive --yes` pass that rendered the board, and for each render of `fr triage board --publish` (each `--watch` iteration included), with a 120-second timeout. A failure or timeout warns once per cause and never changes an exit code. The default board name is `<repo> batches` for a repo scope, `<owner> batches` for an org scope, and `<scope name> batches` for a group scope.
R15. The host id and the scope config never leave the host: they are not durable triage state, `fr triage state export` never copies them, and no target repo carries them.
R16. The fr-triage skill documents claims, the scope config and publishing, in its canonical source and both generated mirrors.

## 2. Background (verified at 5c4edd18e)

### 2.1 What exists

- **Scope naming.** `Scope` (`fr/triage/model.py:124`) has `kind` (repo, org,
  group), `target` and `repos`. `Scope.name` (`model.py:140`) is `owner--repo`,
  `owner`, or the group's sorted slugs joined by `+` (hash-suffixed past 80
  characters). `state_dir()` (`model.py:161`) is `~/.cache/fr/triage/<name>`.
  Nothing in it is host-qualified.
- **Markers.** `BATCH_MARKER_PREFIX` / `WITHDRAWN_MARKER_PREFIX`
  (`model.py:72-73`) and `latest_marker` (`fr/triage/batch.py:599`) are the batch
  markers. `fr:in-progress` (`fr/labels.py:102`) is added by `_forge_writes`
  (`commands/triage_batch_cmd.py:728-770`) and removed by `batch cancel`
  (`:534`).
- **Forge.** `GhClient` (`fr/ghclient.py:87`) has `edit_issue_labels`,
  `ensure_labels`, `comment_issue` and `list_issue_comments`. The gh
  implementation (`fr/real_ghclient.py:325`) returns `{author, body, created_at}`
  with no comment id, and **no method edits a comment**.
- **Collect** reads comments only for `fr:in-progress` issues (`_marker_at`,
  `fr/triage/collect.py:643`). `Issue` (`model.py:214`) is closed-world.
  `FACTS_SCHEMA` is 5, `FACTS_READS` is `(3, 4, 5)` (`model.py:47-48`), and the
  comment above them is the rule for bumping it.
- **Batch commands.** `batch create` / `edit` (`triage_batch_cmd.py:355`, `:396`)
  write `judgements.yaml` only and never touch the forge. `dispatch`, `merge` and
  `cancel` write the forge only with `--yes`. The "already dispatched from another
  scope" guard is in `dispatch_batch` (`:1087-1096`).
- **Driver.** `_Driver.run_pass` (`triage_batch_cmd.py:2214`) re-collects, loads
  state, builds the `Snapshot` (`:1651`; type at `fr/triage/batch_drive.py:114`),
  runs the pure `drive_pass` (`batch_drive.py:808`), executes each action
  (`:2307`), then, under `--yes`, `_write_board` (`:2286`), which warns once per
  cause and never fails the pass. `ActionKind` (`batch_drive.py:65`) already has
  `held`.
- **check.** `stale_dispatches` (`fr/triage/check.py:262`) reads
  `stale_dispatch_days` from the target repo's `.fr/triage.yaml`
  (`TriageConfig`, `model.py:340`). That file is per repo; an org scope has no
  single one, which is why scope settings cannot live there.
- **Board.** `write_board` (`commands/triage_kanban_cmd.py:277`) renders
  `board.html`; `--watch` (`:312`) re-renders while no driver holds the lock.
  Nothing in triage publishes anything.
- **Host labels.** `fr usage`'s `host_label` (`fr/usage/file.py:158`) hashes run
  id plus hostname. This change does not reuse the hostname: on macOS
  `gethostname()` follows the network, and a scope whose id moved would find its
  own claims foreign.

### 2.2 Operator decisions (brainstorm, 2026-10-06)

1. Claim at wave assignment (wave-less batches at dispatch).
2. Expiry 24 hours, per-scope override.
3. Take-over is operator-confirmed; expired claims are only reported.
4. The heartbeat edits the marker in place, refreshed at a quarter of the expiry.
5. Publishing is a scope-local command in `<state>/scope.yaml`.
6. Verification: `candidate` with scenarios for the read-side behaviour, unit
   tests for the rest; no post-merge row.

## 3. Design

### A. Identity and scope config (`fr/triage/scope_config.py`, new)

- `host_id()` returns `FR_HOST_ID` when set, else reads `~/.config/fr/host-id`,
  creating it (16 random hex characters, written atomically, mode 0600) when
  missing. An unreadable or malformed file raises `TriageError`, naming the path;
  fr never silently mints a second identity over one it cannot read.
- `scope_id(scope)` = `"s-" + sha256(f"{scope.name}\0{host_id()}")[:8]`, pattern
  `^s-[0-9a-f]{8}$`.
- `ScopeConfig` (closed-world): `claim_expiry_hours: int = 24` (≥ 1),
  `board_name: str | None`, `publish: list[str] = []`. Loaded from
  `<state dir>/scope.yaml`; a missing file is the defaults, and an invalid one is
  refused with its path. `default_board_name(scope)` per R14.
- `fr triage scope show [--repo|--org] [--dir]` prints name, id, state dir and
  the effective config. It sits under `triage`, which is already in
  `READ_ONLY_COMMANDS`, and it never touches the forge or a registered artifact.
- `state_sync`'s `DURABLE_FILES` does not gain `scope.yaml` (R15).

### B. The claim (`fr/triage/claims.py`, new, pure)

Marker body, one comment:

```
<!-- fr-claim:{"v":1,"signer":"s-1a2b3c4d","batch":"triage-claims","claimed":"2026-10-06T20:00:00Z","heartbeat":"2026-10-06T20:00:00Z","expires":"2026-10-07T20:00:00Z"} -->
Claimed by triage scope `s-1a2b3c4d` for batch `triage-claims`; expires 2026-10-07 20:00 UTC unless refreshed.
```

Released form: the prefix becomes `<!-- fr-claim-released:` with the same JSON
plus `"released"`, and the line reads "Released by …". Parsing is strict: a
marker whose JSON does not parse or does not match the model is ignored and
counted (a `warn` once per issue), never treated as a claim.

- `Claim` model: `signer`, `batch`, `claimed`, `heartbeat`, `expires`,
  `comment_id: int`, `created_at` (the comment's, used for R4's ordering).
- `claims_from_comments(comments) -> list[Claim]`: the latest live marker per
  signer, dropping a signer whose latest marker is a released one.
- `live(claim, now)`, `expired(claim, now)`, `holder(issue, me, now)` (the
  winning foreign claim or None), `winner(claims)` (oldest `created_at`, then
  lowest comment id), `needs_refresh(claim, now, expiry)` (heartbeat older than
  expiry / 4).
- `owed_claims(batches, stages)`: (key, batch) for every member of a batch with a
  wave whose stage is not closed out, and for members of a wave-less batch that is
  dispatched or later (R3, R11). `owed_releases(...)`: own claims whose batch is
  closed out, missing, no longer lists the member, or is a proposed batch with no
  wave (R10).

### C. Forge (`fr/ghclient.py`, `fr/real_ghclient.py`, glab, tea, fakes)

- `list_issue_comments` adds `id`: the numeric id parsed from each comment's
  `url` (`#issuecomment-<n>`); gh's `--json comments` already returns `url`. A
  comment whose url does not carry one gets `id: None`, and a claim cannot be
  read from it.
- `edit_issue_comment(repo, comment_id, body)`: `gh api -X PATCH
  repos/<repo>/issues/comments/<id> -f body=<body>`. glab and tea raise
  `UnsupportedForgeOperation`, like the other batch methods.
- The label `FR_CLAIMED = LabelDef("fr:claimed", ..., "Claimed by a triage
  scope; others keep hands off")` in `fr/labels.py`, created through
  `ensure_labels`.
- Test fakes that implement `GhClient` gain both changes.

### D. Writing claims (`fr/triage/claim_writes.py`, new)

One module owns every claim write so the batch commands, the driver and the
`claim` group share it:

- `claim(client, repo, number, me, batch, expiry, now)`: ensure the label, add
  `fr:claimed`, post the marker, re-read comments, and apply R4. When this scope
  lost, it edits its own marker to the released form and returns `Held(winner)`;
  the label stays, since the winner's claim is live.
- `refresh(...)`: edit the marker in place with new `heartbeat`/`expires`.
- `release(...)`: edit the marker to its released form; remove `fr:claimed` when
  no other live claim remains in the re-read comments.
- `take(...)`: refuses unless the foreign claim is expired; edits the foreign
  marker to its released form (adding `"released_by": <me>`), then `claim`.

Every write first reads the issue's comments, so a decision never rests on facts
older than the call. Writes go only through `GhClient`; git is not involved.

### E. Commands (`commands/triage_batch_cmd.py`, `commands/triage_claim_cmd.py` new)

- `batch create` / `batch edit`: R5's refusal reads facts' claims. When the
  change makes claims owed (a wave set, a member added to a batch with a wave) or
  releases owed (`--remove-issue`, `--no-wave` on a proposed batch), `--yes`
  writes them after `judgements.yaml` is written; without `--yes` it prints them
  and `fr triage claim sync --yes`. A failed claim write exits 1 and names the
  issue; the judgements change stands, and `claim sync` finishes it.
- `batch dispatch --yes`: claims every member before its other forge writes; a
  member held elsewhere refuses the batch (exit 2) before anything is written.
- `batch merge`, `batch cancel`: refuse a batch with a member held elsewhere
  (R6). `batch cancel --yes` releases this scope's claims on its members.
- `fr triage claim list` (this scope's claims, held-elsewhere, expired; from
  facts), `claim sync [--yes]` (owed claims, refreshes, owed releases),
  `claim take <key> --batch <id> [--yes]`, `claim release <key> [--yes]`.
- `check` gains R7's two sets (`fr/triage/check.py`), computed from facts and
  the scope id.

### F. Driver (`fr/triage/batch_drive.py`, `commands/triage_batch_cmd.py`)

- `Snapshot` gains `me` (scope id), `held` (key → foreign claim, from facts),
  `claims_owed`, `refresh_owed`, `releases_owed`.
- `drive_pass` emits, before every other action: one `claim` action per owed
  claim, one `refresh` per owed refresh, one `release` per owed release (new
  `ActionKind`s), and one `held` per batch with a member held elsewhere (R6). A
  held batch produces no merge, update, closeout, archive or dispatch action that
  pass, and is not counted against `--max-inflight`.
- The command executes `claim`/`refresh`/`release` through §D. A claim that
  turned into `Held` (R4) is reported, and the pass stops acting on that batch.
- Export is untouched: an issue held elsewhere never enters this scope's
  batches, so no batch state about it is exported. Its judgement is exported like
  any other, because judging stays free.

### G. Board and publishing (`fr/triage/kanban.py`, `kanban_render.py`, `commands/triage_kanban_cmd.py`)

- `build_board` takes the scope id and facts' claims: a "Held elsewhere" group
  (key, title, holder, batch, expiry; expired marked), and a claim-expiry line
  on each own card. The page stays within the existing tokens and the 16px gutter.
- `publish_board(config, board_path, name, scope_id)`: substitutes the
  placeholders, runs the argv with no shell and a 120-second timeout, and
  returns the failure cause or None. `_write_board` calls it after a successful
  render; `fr triage board --publish` calls it after each render. A failure warns
  once per cause per process, like `_write_board`'s own warnings.
- The skill names the harness-neutral reading: a CLI command publishes; an agent
  that publishes through its own harness's artifact surface can watch the board
  file instead.

### H. Facts (`fr/triage/model.py`, `fr/triage/collect.py`)

- `Issue.claims: list[IssueClaim] = []` (signer, batch, claimed, heartbeat,
  expires, comment_id, created_at). `FACTS_SCHEMA` = 6, `FACTS_READS` =
  `(3, 4, 5, 6)`, and the comment above them records why.
- `_marker_at`'s single comment read is shared: an issue labelled
  `fr:in-progress` or `fr:claimed` is read once, giving both
  `dispatch_marker_at` and `claims`.
- `judgements.yaml` does not change shape. Facts and judgements are not
  registered artifact kinds, so no artifact migration is owed.

### I. Skill (`plugins/super-fr/skills/fr-triage/SKILL.md`, both mirrors)

A **Claims** paragraph: the scope id, when claims are owed and written, hands-off,
expiry and the operator's `claim take`/`release`, and the `scope.yaml` keys
including `publish`. Regenerate with `scripts/sync-opencode.py` and
`scripts/sync-hermes.py`.

### J. Release

A `.changes/feat-batch-triage-claims.yaml` fragment, `bump: minor` (new commands
and a new label).

## 4. Risks

- **A host id that changes.** A pod with an ephemeral home mints a new id on
  restart, and its old claims become foreign, then expire. Mitigation: set
  `FR_HOST_ID` in the pod's environment. The skill says so.
- **API cost.** Claims add one comment read per claimed issue per collect, and a
  refresh edit per claim every six hours by default. Both scale with live batches,
  not the backlog.
- **A racing writer that dies between posting and withdrawing.** Its stray live
  marker loses every R4 comparison (it is newer), so it never wins; it expires
  and appears under `expired claims`.
- **Clock skew.** Expiry is judged from the writer's own timestamps; skew of
  minutes is immaterial against 24 hours.

## Verification

strategy: candidate

- triage-claims-hands-off: candidate — the scenario feeds a facts fixture with an issue claimed by another scope; `check` lists it held elsewhere and `batch create` refuses it.
- triage-claims-expiry: candidate — the scenario feeds an expired foreign claim; `check` lists it expired and `batch create`'s refusal names `claim take`.
- triage-claims-identity: none — unit tests: scope ids are stable, host-qualified and carry no hostname (`FR_HOST_ID` and the stored file).
- triage-claims-writes: none — forge writes; unit tests against a fake GhClient cover claim, race, refresh, release and take (scenarios reach no forge).
- triage-claims-driver: none — `drive_pass` is pure; unit tests cover the claim, refresh, release and held actions.
- triage-claims-board-publish: none — unit tests render the board's held group and run a fake publish command, including its timeout and failure.

## 5. Test Plan

No deployment step. The release ships it, and every row is verified before
merge; no row needs a released build.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-10-06-triage-claims | `derio-net/super-fr` | `2026-10-06-triage-claims` | — |

## 6. Acceptance rows

Born at brainstorm, presented at spec review: `triage-claims-identity` (R1, R15),
`triage-claims-hands-off` (R5, R6, R7), `triage-claims-expiry` (R7, R8, R9),
`triage-claims-writes` (R2, R3, R4, R10, R11, R12), `triage-claims-driver` (R3,
R6, R8, R10, R11) and `triage-claims-board-publish` (R13, R14, R16).
