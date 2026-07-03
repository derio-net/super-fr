# fr spec status: resolve cross-repo plan rows via the gh contents API

Design spec for [#339](https://github.com/derio-net/super-fr/issues/339).

## Problem

`compute_status()` (`packages/fr/src/fr/spec.py`) is "Local-fs only at this
layer". Every plan row whose folder doesn't resolve on the local filesystem —
the normal shape for a multi-repo feature, where each target repo owns one
plan — is hard-coded to `🔒 Unreachable`. The rollup is mostly noise for
exactly the case the spec Implementation-Plans table exists to coordinate, and
the aggregate under-counts (Unreachable rows contribute neither to
`plans_complete` nor to the step total).

The capability already exists and is used by `fr archive`:
`_spec_fully_implemented()` (`migrate.py:801-806`) probes the *other* repo via
`GhClient.file_exists()` (contents API) to decide whether a cross-repo row is
archived. Same spec table, two verbs, two answers: **archive can see
cross-repo rows; status can't.** This spec closes that gap.

## Decisions (operator-owned, locked in the fr-goal Q&A)

1. **Resolution depth — full remote parse.** Not existence-only. When a row
   doesn't resolve locally, fetch the remote plan folder's `NN.yaml` phase
   files via the contents API, parse them with the existing `PhaseDoc` schema,
   and compute the exact same phase/step counts the local path computes. The
   aggregate reaches full parity — the step-% includes remote plans, and
   In-Progress remote plans show `(pc/pt phases, ticked/total steps)`.

2. **gh network posture — default-on with `--no-gh`.** `fr spec status`
   constructs a `RealGhClient` by default (mirrors `fr archive` / `apply` /
   `status`, which all build one unconditionally and degrade soft). A new
   `--no-gh` flag forces pure-local resolution (offline, CI-without-token,
   deterministic tests) — byte-for-byte today's behavior. Any gh failure or
   missing auth degrades a cross-repo row to `Unreachable` exactly as today.

3. **Scope — CLI + library only, not the GHA.** The reusable
   `.github/workflows/fr-spec-status.yml` is left unchanged. Its default
   `GITHUB_TOKEN` is repo-scoped and cannot read private sibling repos
   (`agentic-stoa/cnc-fr`), so wiring it would still print `Unreachable` there —
   misleading without a cross-repo PAT. Enabling GHA cross-repo resolution is a
   follow-up that needs a broader-scoped token; noted, not built here.

## Approach

### New `GhClient` read surface (two methods)

`file_exists` proves a single path exists; full parse needs to *list* a folder
and *read* files. Add two read-only methods to the `GhClient` Protocol
(`ghclient.py`), the production `RealGhClient` (`real_ghclient.py`), and the
`FakeGhClient` test double (`tests/unit/fakes.py`):

```python
def list_dir(self, repo: str, path: str) -> list[str]:
    """Names of entries in `path` on `repo`'s default branch (contents API).
    Empty list when the path is absent or not a directory. Read-only."""

def read_file(self, repo: str, path: str) -> str:
    """Raw text of `path` on `repo`'s default branch (contents API).
    Raises GhError on absence / non-file. Read-only."""
```

`RealGhClient` implementation:
- `list_dir` → `gh api repos/{repo}/contents/{path} --jq '.[].name'`, returning
  `[]` on any `GhError` (404 on a missing dir is "no such dir", the safe
  direction — matches `file_exists`'s fail-soft).
- `read_file` → `gh api repos/{repo}/contents/{path} -H "Accept:
  application/vnd.github.raw"`, which returns the file bytes directly (no
  base64 decode). Propagates `GhError` so the caller can degrade the whole row.

### Shared status-counts helper (DRY the local/remote math)

The per-plan status arithmetic (steps_total, steps_ticked, phases_complete via
`plan_locally_complete`, and the Not-Started/In-Progress/Complete state
machine) currently lives inline in `compute_status`. Extract it to a pure
helper over a phase sequence:

```python
def _status_counts(phases: Sequence[PhaseDoc]) -> tuple[str, int, int, int, int]:
    """(state, phases_complete, phases_total, steps_ticked, steps_total)."""
```

Both the local branch and the new remote branch call it — the two paths cannot
diverge (the same "shared predicate" doctrine `plan_locally_complete` already
follows across `vk.diff`, the archive gate, and status).

### Remote resolution

```python
def _resolve_remote_plan_phases(
    gh: GhClient, repo: str, file_cell: str,
    cache: dict[tuple[str, str], list[PhaseDoc] | None],
) -> list[PhaseDoc] | None:
```

- Guard: `repo` must be `owner/repo` form (`"/" in repo`); otherwise return
  `None` (can't address a remote).
- Candidate paths come from `migrate._archive_path_variants(file_cell)` —
  `(active, implemented, legacy)`, derived from the bare slug so every
  historical File-cell form resolves. Active-first matches
  `refs.PLAN_ROOTS = ("plans", "implemented/plans", "archived-plans")`: a
  merged-but-not-yet-archived plan reflects current progress; an archived plan
  reflects its final (complete) state.
- For the first variant whose `list_dir` contains `_meta.yaml` (proof it's a v2
  plan folder), read every `NN.yaml` (regex `^\d{2}\.yaml$`, the parser's
  `_PHASE_FILE_RE`), `PhaseDoc.model_validate(yaml.safe_load(...))` each, and
  return the phase list. Memoize on `(repo, slug)` — including the negative
  result — so a repeated row in one run makes no extra calls.
- `_meta.yaml` itself is **not** fetched or validated: `compute_status` reads
  only `plan.phases`, and skipping meta avoids coupling remote resolution to
  the `fr_version` gate (`parse()` enforces it; a version-skewed remote plan
  would otherwise degrade to Unreachable for no status-relevant reason).

### `compute_status` wiring

Signature gains `gh: GhClient | None = None`. The per-call memo dict is created
here (per-run caching — a single CLI invocation; a longer-lived, default-branch-
sha-keyed cache is a deferred nicety, not needed for a run-once command). In
the "unresolved locally, not a manual row" branch:

- `gh is None` (`--no-gh` / offline) → `Unreachable`, note unchanged.
- `gh` present → `_resolve_remote_plan_phases(...)`, wrapped in a broad
  `try/except` (any gh outage, parse error, or schema drift degrades to
  `Unreachable` with a note naming the repo — never a crash, never a silent
  pass). On success, feed the phases through `_status_counts`, build the
  `PlanStatus` with a `note` recording the remote origin, and count a
  `Complete` remote plan toward `plans_complete` and its steps toward the
  aggregate — identical to a local plan.

### Rendering

`render_status_md` is unchanged — remote-resolved rows render with the same
icons and counts as local rows (matching the approved output). The remote
origin is recorded in `PlanStatus.note` for programmatic transparency; genuine
resolution failures still surface in the top-level `warnings` list.

### CLI

`spec_cmd.py` gains the `_make_gh_client()` factory seam (same pattern as
`archive_cmd` / `apply_cmd` — tests monkeypatch it to inject `FakeGhClient`)
and a `--no-gh` flag. `gh = None if no_gh else _make_gh_client()`, threaded
into every `compute_status` call (single spec and `--all`).

### Docs

- `spec.py`: rewrite the `compute_status` docstring (drop "Local-fs only" and
  "not implemented in Phase 3") and the `_resolve_local_plan_dir` note ("out of
  scope for Phase 3" → "resolved remotely by `compute_status` when a GhClient
  is supplied").
- `fr-progress/SKILL.md`: update the note (~L52-54) — cross-repo plans now
  resolve via the gh contents API when `gh` is available; `--no-gh` / offline
  degrades them to `Unreachable`.

## Test plan (TDD, in-process — FakeGhClient, no network)

Extend `FakeGhClient` with `remote_tree: dict[tuple[str, str], str]` (path →
raw content) backing `list_dir`/`read_file`. Red-first for each:

- `_status_counts` extraction: local behavior byte-for-byte unchanged (existing
  `compute_status` tests stay green).
- Remote **archived** plan (all phases complete) → `Complete`, counts toward
  `plans_complete`, steps in aggregate.
- Remote **active, partially-ticked** plan → `In Progress` with exact
  `(pc/pt, ticked/total)`.
- Variant precedence: active path wins over implemented when both exist.
- `--no-gh` / `gh=None` → `Unreachable`, output identical to pre-change.
- gh present but path found in no variant → `Unreachable` with a note.
- `read_file`/`list_dir` raising mid-fetch → degrades to `Unreachable`, no
  crash.
- Non-`owner/repo` Repo cell with gh present → `Unreachable` (no remote call).
- Memo: a repeated `(repo, slug)` triggers no second `list_dir`/`read_file`.
- CLI: `_make_gh_client` seam monkeypatched; `--no-gh` suppresses construction.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| spec-status-crossrepo-resolution | derio-net/super-fr | `2026-07-03-spec-status-crossrepo-resolution` | — |

## Follow-ups (out of scope)

- Wire `.github/workflows/fr-spec-status.yml` for cross-repo resolution — needs
  a token that can read sibling repos (default `GITHUB_TOKEN` is repo-scoped).
- Default-branch-sha-keyed cross-invocation cache, if `fr spec status` ever
  runs in a long-lived process.
