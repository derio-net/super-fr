> **⚠️ SUPERSEDED 2026-05-17 — see issue [#147](https://github.com/derio-net/superpowers-for-vk/issues/147)**
>
> This spec proposed spec-level DAG dispatch + cross-repo plan resolution
> as a feature added on top of the existing v2 bridge surface. The
> 2026-05-17 audit found that the responsibility this spec tried to add
> ALREADY lives in the legacy bridge (`agent-images/kali/scripts/vk-issue-bridge.py`'s
> `check_blockers` + body-text dep parsing), and the v2 rebuild was
> supposed to absorb it but never did. The fix is the v2 bridge rebuild
> (#147), not another patch layer on top of the half-rebuilt bridge.
>
> Original content preserved below for historical reference.
>
> ---
>
# Spec-Level Dispatch with Plan DAG

**Status:** Proposed
**Date:** 2026-05-13
**Repos affected:** `derio-net/superpowers-for-vk`, `derio-net/agent-images` (bridge daemon cron caller)

## Goal

Make a spec dispatchable as a whole. The spec table's `Depends on` column
becomes a machine-parseable plan-level DAG; a new `vk spec apply` command
dispatches every plan whose upstream deps are `Complete`; the live VK bridge
extends its tick to advance the DAG autonomously as upstream plans complete.

No new persistent state is introduced. Spec progress and inter-plan readiness
are derived every tick from the same source of truth `vk spec status` already
uses — phase YAML `completion.at` markers on each repo's `main` branch.

## Problem Statement

The v2 toolchain has no spec-level dispatch. `vk apply` operates on a single
plan dir or all plans in the current repo (`src/vk/commands/apply_cmd.py:201`).
The bridge's `tick()` operates on a single `Plan` (`src/vk/bridge/__init__.py:124`)
and intra-plan phase ordering is already handled by the parallel-dispatch-dag
design (2026-04-20). One layer up — plan ordering within a spec — is undefined.

Specs already carry a `Depends on` column in the `## Implementation Plans`
table (introduced by the v2 rebuild spec, 2026-05-06). The column is stored as
free-form `str` on `PlanRef` (`src/vk/spec.py:32`). No parser, no enforcement,
no consumer. Specs with cross-repo plans look like this today:

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| vk-v2-library | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-05-09-vk-v2-library/` | — |
| bridge-migration | `derio-net/willikins` | `docs/superpowers/plans/2026-05-06-vk-v2-bridge-migration/` | vk-v2-library |
| rework-1 | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-05-09-vk-v2-library-rework-1/` | vk-v2-library |
| bridge-integration | `derio-net/agent-images` | `docs/superpowers/plans/2026-05-12-bridge-vk-library-integration/` | rework-1 |

An operator who wants to dispatch the rework-1 plan once `vk-v2-library` is
complete must (a) notice that completion happened, (b) `cd` into the right
repo, (c) `vk apply docs/superpowers/plans/2026-05-09-vk-v2-library-rework-1/
--yes` from there. The signal exists in the spec; the automation does not.

The bridge could do this — it already walks repos, reads plan state, mutates
GH — but it has no spec-level view today.

## Non-goals

- Cross-spec dependencies. A plan in spec A cannot declare a dep on a plan in
  spec B. Spec is the unit of orchestration.
- Per-plan budget or rate-limiting of dispatch. If 10 root plans are unblocked
  at once, all 10 dispatch this tick.
- Parallel `gh issue create` calls. Each `vk.apply()` runs serially. Same
  simplicity guarantee `vk apply --all` already gives.
- Replacing the phase-DAG. Intra-plan phase ordering keeps its own
  `**Depends on:**` grammar; this spec only adds the inter-plan layer.
- Migrating closed/archived plans into the new grammar. Old specs render
  under `vk spec status` unchanged; only specs whose author wants
  spec-dispatch adopt the grammar.
- A second state machine for spec progress. Status remains derived; no
  `_spec_state.yaml`, no GH-comment-as-state, no spec-doc auto-mutation.

## Cross-cutting principle: derive, don't store

Inherited from the v2 rebuild spec's "if it can be derived, don't store it"
rule (`src/vk/spec.py:8-11`). Every spec-level signal in this design is
computed from existing state on each repo's `main` branch. The bridge never
writes to a spec markdown file; the operator does, once, when authoring the
spec.

## Design Decisions

| # | Decision | Alternatives considered |
|---|----------|-------------------------|
| D1 | Dispatch is gated, not one-shot. `vk spec apply` only dispatches plans whose deps are `Complete`; downstream plans are re-evaluated on every bridge tick. | One-shot: dispatch every plan immediately with cross-plan `- Blocked by #N` lines so the bridge gates at issue-pickup. Spec state machine: persist spec-level state in a yaml. |
| D2 | Read-through aggregation, no second state machine. Spec progress derived from each plan's `completion.at` markers on `main`. | Persist spec state in `_spec_state.yaml`. Track completion via labels on a per-spec tracking Issue. Webhook push instead of pull. |
| D3 | Cross-repo plan files read via `gh api repos/{owner}/{name}/contents/{path}`. No local checkout required for upstream repos. | Require checkouts of every referenced repo under `VK_REPOS_DIR`. Use issue-state CLOSED-only as the gate (less authoritative). |
| D4 | Shared library primitive `vk.spec.dispatch(spec, gh, yes=...) → SpecDispatchResult`. Both `vk spec apply` CLI and the bridge cron call it. | Bridge-only orchestration with no CLI. CLI-only with no bridge autonomy. |
| D5 | `Depends on` cell grammar: Plan-column refs verbatim, `;` separator, `—`/`-`/`None` for root. Plan column becomes the spec-internal ID; uniqueness enforced. | Dir-slug refs (basename of File path). Repo-qualified slugs (`owner/repo:slug`). Free-form text with regex fishing. |
| D6 | "Plan complete" = every phase has `state.completion.at` set in `_state.yaml` on `main`. Same rule `compute_status` already applies. | All GH issues for `plan:<slug>` CLOSED. Hybrid (issue-state plus yaml). |
| D7 | Validation runs **only** at `vk spec self-review` and `vk spec apply` invocation — never at parse. `parse_spec` returns whatever was in the cell; `compute_status` ignores `depends_on`. | Validate at parse time. Validate on every `vk spec status` call. |
| D8 | Backward-only refs (a plan can only depend on plans listed above it). | Topological sort with full any-order DAG. Matches the phase-DAG convention. |
| D9 | Manual-action rows (File = `—`) cannot appear in any `Depends on` cell. Validation error. | Treat them as instantly-complete. Allow ref but never resolve (deadlock). |
| D10 | `vk.spec.dispatch` derives outcome from `vk.apply`'s result, not a pre-flight "already-dispatched" check. | Pre-check `all(phase.tracking_issue for phase in plan.phases)` before calling apply. |
| D11 | `GhClient.read_repo_file(repo, path, *, ref="main") → bytes` added to the Protocol. `RealGhClient` implements via `gh api ... /contents/...`. `FakeGhClient` gains an in-memory dict. | Read via `gh api git/trees/main?recursive=1`. Shell out to `git archive`. |
| D12 | Rollout in three PRs (parser+status / dispatch+CLI / bridge integration in agent-images). Each independently revertible. | Single PR; two PRs (combine bridge with CLI). |
| D13 | Minor version bump `2.1.4 → 2.2.0`. New user-visible CLI commands and library surface. | Patch (too small for new commands). Major (no breaking API). |
| D14 | `vk.spec.dispatch` is **repo-aware**: it dispatches only plans whose `plan_ref.repo` resolves to a locally-writable checkout (`Path.cwd()` for the operator CLI; `VK_REPOS_DIR/<repo>` for the bridge). Cross-repo plans without a local writable checkout emit a new `deferred_cross_repo` outcome — they'll be dispatched the next time `dispatch` runs in a context that has that repo checked out. Same writeback story as `vk apply` and `vk.bridge.tick`: dispatch is local-fs to allow `plan_ops.set_tracking_issue` to persist. | Cross-repo dispatch via gh contents API materialised into a tempdir (writeback lost when tempdir deleted → reintroduces the duplicate-Issue regression PR #122 fixed). gh PUT contents API for upstream writeback (adds write-side gh complexity, deferred until v2.3+). |
| D15 | After `apply()` succeeds, `vk.spec.dispatch` runs the same `plan_ops.set_tracking_issue(plan.dir, phase_n, url)` writeback loop that `apply_cmd._apply_one` and `bridge.tick` already do. Same guard against the duplicate-Issue regression. | Skip writeback (would reintroduce duplicates on every re-run). Rely on `phase:<N>` label matching in observe (orthogonal — observe also reads `phase.tracking_issue`, so writeback is still required). |

## What stays unchanged

- `vk apply` per-plan semantics. The `observe → render → diff → apply` pipeline
  is unchanged. Spec-dispatch sits one layer up and delegates.
- `vk.bridge.tick(plan, gh, mcp)` semantics. Same `vk-ready` → `vk-synced`
  projection, same per-plan failure isolation.
- The phase-DAG within a plan. `**Depends on:** Phase N` lines (per
  2026-04-20-parallel-dispatch-dag-design) continue to gate intra-plan ordering.
- `vk spec status` rendering for old specs. Free-form prose in the
  `Depends on` cell renders the same way today and after this release; only
  `vk spec status` displaying cross-repo plans as `Unreachable` changes (they
  become resolvable via gh contents API).
- Spec filename convention, `## Implementation Plans` heading, four-column
  table schema, `## ` row separator.
- The `dispatch` gate's opt-in mechanism (`plan-config.yaml::dispatch`).
- Plan filename convention, archive layout, all label conventions.

---

## 1. Grammar, parser, validation

### 1.1 Formal grammar for `Depends on`

```
deps_cell    := root | refs
root         := "—"             # em-dash, U+2014 (canonical)
              | "-"             # hyphen-minus (transitional alias)
              | "None"          # plain-text alias
refs         := ref ( WS* ";" WS* ref )*
ref          := non-empty trimmed text, no semicolons,
                must exactly match the Plan column of some row above this one
WS           := space | tab
```

Notes:
- Em-dash is canonical. `vk plan format` (when applied to specs in a follow-up)
  canonicalises hyphen/`None` into em-dash. Hyphen is accepted because the
  existing manual-row sentinel uses hyphen and we don't want a forced rewrite
  of every spec on day one.
- Semicolon-separated refs because Plan-column IDs are author-chosen and could
  contain commas. Semicolon is unambiguous.
- Whitespace around `;` is trimmed.
- Empty cell is not a valid root; root plans use `—` explicitly. A blank cell
  is a validation error (`use '—' for root plans`).

### 1.2 `PlanRef` change

`src/vk/spec.py:27` gains a parsed tuple:

```python
@dataclass(frozen=True)
class PlanRef:
    name: str                       # Plan column value — the spec-internal ID
    repo: str
    file: str
    depends_on: tuple[str, ...]     # CHANGED. Was str. Empty tuple = root.
    depends_on_raw: str             # NEW. Preserves the original cell text
                                    # so 'vk spec status' on old specs with
                                    # free-form prose can still display it.
```

`parse_spec` populates both fields. `depends_on` is best-effort parsed
(semicolon split, sentinel detection, trimmed). `depends_on_raw` is the cell
text verbatim.

### 1.3 Validation gates

Validation runs **only** when explicitly invoked:

- `vk spec self-review <spec>` — pure local check, no GH calls.
- `vk spec apply <spec> --dry-run` — runs self-review, then dry-runs dispatch.
- `vk spec apply <spec> --yes` — runs self-review, then dispatches.
- `vk.spec.dispatch(spec, gh)` library call — calls `_validate_spec` internally
  and raises `SpecValidationError` if it fails.

`parse_spec` itself **never raises** on bad refs. `compute_status` **ignores**
`depends_on`. This preserves the "old specs still render" promise.

Validation table:

| Check | Message |
|-------|---------|
| Plan column duplicate within a single spec | `Plan ID 'X' appears in rows {row indices}; must be unique within a spec table.` |
| Unknown ref (not present as a Plan ID in this spec) | `Plan 'B' depends on 'A', which does not appear in this spec table. Refs must match a Plan column value.` |
| Forward ref (depends on a plan listed below) | `Plan 'B' (row 2) depends on 'C' (row 4); only backward refs are permitted.` |
| Self-ref | `Plan 'B' depends on itself.` |
| Manual-row ref (depends on a row with File = `—`/`-`) | `Plan 'B' depends on 'A', which is a manual/informational row (File = '—') with no automatable completion signal.` |
| Empty `Depends on` cell | `Plan 'B' has an empty 'Depends on' cell; use '—' for root plans.` |
| Blank Plan column value | `Plan column at row N is blank; Plan IDs must be non-empty.` |

Plan-column uniqueness applies *within* one spec table. Across specs, the same
Plan ID can appear — each spec is its own namespace.

### 1.4 Existing-spec compatibility

The 9 existing specs in `docs/superpowers/specs/` use a mix of:
- New grammar (e.g., `2026-05-09-vk-v2-library` as ref in `vk-rebuild-state-machine-design.md`).
- Free-form prose (e.g., `superpowers-for-vk plan` in older rows).
- Em-dash for roots.

None of these break. `vk spec status` ignores `depends_on`. `vk spec self-review`
and `vk spec apply` are opt-in commands — they're invoked when an operator
explicitly wants spec-dispatch behaviour, at which point the operator
migrates the cells by hand.

No bulk migration script. No PR to convert all specs. Migration is per-spec,
driven by the operator who wants to use spec-dispatch on that spec.

---

## 2. Cross-repo plan resolution

### 2.1 `GhClient.read_repo_file`

Protocol extension at `src/vk/ghclient.py:14`:

```python
class GhClient(Protocol):
    ...existing methods...

    def read_repo_file(
        self,
        repo: str,
        path: str,
        *,
        ref: str = "main",
    ) -> bytes:
        """Fetch a file's contents from `repo` at `ref`. Bytes; caller decodes.

        Raises FileNotFoundError if the path doesn't exist at that ref.
        Other gh failures raise the wrapper's existing error type.
        """
        ...
```

`RealGhClient` implementation:

```python
def read_repo_file(self, repo, path, *, ref="main"):
    payload = self._gh_json("api", f"repos/{repo}/contents/{path}",
                            "-H", "Accept: application/vnd.github.raw",
                            "-q", "")
    # `-H Accept: ...raw` returns the file body directly, no base64 round-trip.
    # 404 → translate to FileNotFoundError.
```

`FakeGhClient` implementation backed by `self._files: dict[tuple[str, str, str], bytes]`
keyed on `(repo, path, ref)`. Fixtures populate the dict.

### 2.2 `compute_status` cross-repo upgrade

`vk.spec.compute_status` (`src/vk/spec.py:135`) signature gains a `gh`
parameter:

```python
def compute_status(spec: SpecMeta, repo_root: Path,
                   gh: GhClient | None = None) -> SpecStatus: ...
```

For each `PlanRef`:

1. `file == "—"` (manual row) → emit `state="Not Started"` as today.
2. Local resolution (current-repo + file path resolves locally) → parse from
   the working tree as today.
3. Cross-repo (file does not resolve locally, `gh is not None`) → read plan
   files via `gh.read_repo_file`, materialise into a temporary directory,
   call `vk.parser.parse(tmpdir)`, compute completion, then delete the
   tempdir. Wrapping bytes back through the existing parser preserves a single
   source of truth for the parse path.
4. Cross-repo when `gh is None` → emit `state="Unreachable"` with the
   existing `Unreachable` note (`vk spec status --no-gh` mode for offline use).

The tempdir round-trip is the smallest seam — alternatives (a `parse_from_mapping`
overload, an in-memory virtual FS) require touching the parser. v1 stays with
the tempdir; v2 may consolidate if a faster path matters.

### 2.3 Cost analysis

Per cross-repo plan, `compute_status` reads:
- `_meta.yaml` (1 file)
- One `_state.yaml` for each phase (N files for N phases)
- One `_prose.md` if accessed (optional; parser reads it lazily)

Net: **1 + N gh API calls per cross-repo plan per status computation.**

For a spec with 5 cross-repo plans averaging 5 phases each:
- 5 × 6 = 30 gh API calls per `compute_status` invocation.
- Bridge tick interval: 60 s.
- Per hour: 30 × 60 = **1,800 calls/hr**.

The authenticated gh API quota is 5,000/hr. A bridge host with a single such
spec sits at 36 % of quota; with three such specs the bridge approaches 100 %.
No caching in v1 — if quota becomes a real problem we add a per-tick LRU
keyed on `(repo, path, sha)` (the gh API returns the file SHA, which is
stable until the file changes).

Mitigation paths that are *not* v1:
- `gh api repos/{repo}/git/trees/main?recursive=1` to fetch the plan
  subtree in one call. Reduces N+1 calls to 1 listing + N file fetches.
- gh webhooks subscribing to push events on referenced repos. Push-shape
  instead of pull-shape.

### 2.4 Unreachable rows

A cross-repo file that returns 404 (the path doesn't exist on `main`) emits
`state="Unreachable"` with a `note` like `gh contents 404: docs/.../plan-x/_meta.yaml`.
This is distinct from `Missing` (file exists locally but isn't parseable) and
distinct from generic gh errors (which raise and propagate, killing the run).

---

## 3. `vk.spec.dispatch`

### 3.1 Signature and result type

`src/vk/spec.py` gains:

```python
@dataclass(frozen=True)
class PlanDispatchOutcome:
    plan_ref: PlanRef
    state: Literal[
        "dispatched",            # at least one IssueCreate mutation this run
        "already_dispatched",    # vk.apply returned zero IssueCreate mutations
        "blocked",               # one or more deps are not Complete
        "skipped_manual",        # this row IS a manual-action row
        "unreachable",           # cross-repo plan file 404 via gh contents
        "parse_error",           # plan files exist but don't parse
        "deferred_cross_repo",   # plan's repo isn't locally writable (D14);
                                 # the bridge picks it up when it visits that repo
    ]
    blocking_deps: tuple[str, ...] = ()      # plan IDs blocking this row
    issues_created: int = 0                  # count of new IssueCreate mutations
    apply_failures: tuple[str, ...] = ()
    note: str | None = None


@dataclass(frozen=True)
class SpecDispatchResult:
    spec: SpecMeta
    outcomes: tuple[PlanDispatchOutcome, ...]
    dispatched: int
    already_dispatched: int
    blocked: int
    deferred_cross_repo: int                  # plans whose repo wasn't locally writable
    errors: int                               # apply failures + unreachable + parse_error
    failures: tuple[str, ...]


class SpecValidationError(Exception):
    """Raised by vk.spec.dispatch when self-review fails."""


def dispatch(
    spec: SpecMeta,
    gh: GhClient,
    *,
    yes: bool = False,
    repo_root: Path | None = None,
) -> SpecDispatchResult:
    """Dispatch every unblocked plan in `spec` that isn't already dispatched.

    Topologically walks the spec table (backward-only refs make table order
    a valid topological order). For each plan whose deps are all 'Complete'
    AND whose repo resolves to a locally-writable checkout, runs the standard
    observe→render→diff→apply pipeline followed by the same
    `plan_ops.set_tracking_issue` writeback that `apply_cmd._apply_one` and
    `bridge.tick` perform — guarding against the duplicate-Issue regression
    PR #122 fixed.

    Plans whose repo is not locally writable (i.e., no checkout under
    `repo_root` for same-repo or `VK_REPOS_DIR/<repo>` for cross-repo) emit
    a `deferred_cross_repo` outcome and wait for the bridge to dispatch them
    when it visits their repo (D14).

    Validates the spec first; raises SpecValidationError on bad grammar.
    """
```

Note: `"blocked_by_manual"` is **not** a runtime state. Self-review rejects
manual-row refs before dispatch ever runs.

### 3.2 Algorithm

```python
def dispatch(spec, gh, *, yes=False, repo_root=None):
    _validate_spec(spec)                       # raises SpecValidationError on grammar error

    repo_root = repo_root or Path.cwd()
    status = compute_status(spec, repo_root, gh=gh)
    by_id = {ps.plan_ref.name: ps for ps in status.plans}

    outcomes: list[PlanDispatchOutcome] = []

    for row in spec.plans:
        # Manual-action row: nothing to dispatch.
        if row.file in ("—", "-", ""):
            outcomes.append(PlanDispatchOutcome(
                plan_ref=row, state="skipped_manual"))
            continue

        # Reachability check (cross-repo 404, parse error).
        my_status = by_id[row.name]
        if my_status.state == "Unreachable":
            outcomes.append(PlanDispatchOutcome(
                plan_ref=row, state="unreachable", note=my_status.note))
            continue
        if my_status.state == "Missing":
            outcomes.append(PlanDispatchOutcome(
                plan_ref=row, state="parse_error", note=my_status.note))
            continue

        # Dep gate.
        blocking = [d for d in row.depends_on
                    if by_id[d].state != "Complete"]
        if blocking:
            outcomes.append(PlanDispatchOutcome(
                plan_ref=row, state="blocked", blocking_deps=tuple(blocking)))
            continue

        # Resolve plan.dir to a locally-writable checkout (D14).
        # Same-repo: <repo_root>/<file>. Cross-repo: VK_REPOS_DIR/<repo>/<file>.
        local_dir = _resolve_writable_plan_dir(row, repo_root)
        if local_dir is None:
            outcomes.append(PlanDispatchOutcome(
                plan_ref=row, state="deferred_cross_repo",
                note=f"no local checkout for {row.repo}; bridge will pick up"))
            continue

        # Parse from the local checkout (cross-repo plans live in VK_REPOS_DIR).
        plan = parse(local_dir)

        # Run the standard pipeline — apply is idempotent.
        observed = observe(plan, gh)
        rendered = render(plan, observed)
        d = diff(rendered, observed, plan=plan)

        if not yes:
            # Dry-run: outcome derived from the diff.
            issues_created = sum(1 for m in d.mutations
                                 if isinstance(m, IssueCreate))
            if issues_created == 0:
                outcomes.append(PlanDispatchOutcome(
                    plan_ref=row, state="already_dispatched"))
            else:
                outcomes.append(PlanDispatchOutcome(
                    plan_ref=row, state="dispatched",
                    issues_created=issues_created,
                    note="(dry-run)"))
            continue

        # Yes: actually apply, then write tracking_issue back per D15
        # (same loop apply_cmd._apply_one and bridge.tick run).
        result = apply(d, gh, plan=plan)
        issues_created = len(result.created_issues)
        failures = list(f.error for f in result.failures)
        for phase_n, url in result.created_issues.items():
            try:
                plan_ops.set_tracking_issue(plan.dir, phase_n, url)
            except (PlanEditError, OSError, PlanSchemaError) as e:
                failures.append(f"phase {phase_n}: writeback failed: {e}")
        failures = tuple(failures)

        if issues_created == 0 and not failures:
            outcomes.append(PlanDispatchOutcome(
                plan_ref=row, state="already_dispatched"))
        elif failures:
            outcomes.append(PlanDispatchOutcome(
                plan_ref=row, state="dispatched",
                issues_created=issues_created,
                apply_failures=failures))
            # Do NOT advance to downstream plans this run — their deps
            # may now be in an indeterminate state. Next tick resumes.
            break
        else:
            outcomes.append(PlanDispatchOutcome(
                plan_ref=row, state="dispatched",
                issues_created=issues_created))

    return _summarise(spec, outcomes)
```

`_resolve_writable_plan_dir(ref, repo_root)`:

```python
def _resolve_writable_plan_dir(
    ref: PlanRef,
    repo_root: Path,
) -> Path | None:
    """Return a path to a locally-writable plan directory, or None.

    Order of resolution:
    1. Same-repo: `repo_root / ref.file` if it exists.
    2. Cross-repo: `VK_REPOS_DIR / <name(ref.repo)> / ref.file` if it exists.
       Mirrors `vk.bridge._repo_checkout_root` convention.
    Returns None if no local checkout has the file — caller emits
    deferred_cross_repo.
    """
    same_repo = (repo_root / ref.file).resolve()
    if same_repo.is_dir():
        return same_repo
    base = os.environ.get("VK_REPOS_DIR")
    if not base:
        return None
    name = ref.repo.split("/", 1)[1] if "/" in ref.repo else ref.repo
    cross = (Path(base) / name / ref.file).resolve()
    return cross if cross.is_dir() else None
```

### 3.3 Idempotency

`vk.apply` is idempotent at the issue level: phases whose plan yaml already
carries a `tracking_issue` produce no `IssueCreate` mutation during diff.
The idempotency depends on the `tracking_issue` writeback that
`apply_cmd._apply_one` and `bridge.tick` perform after `apply()` succeeds
(D15) — `vk.spec.dispatch` runs the same writeback loop for the same
reason. Without it, every re-run of `dispatch` would re-emit `IssueCreate`
for every phase — exactly the regression PR #122 (commit `421cec7`) fixed.

So `vk.spec.dispatch` is idempotent by composition: re-running on a fully-
dispatched spec produces only `already_dispatched` outcomes and makes zero
issue-creating GH calls.

The outcome distinction `dispatched` vs `already_dispatched` is **derived
from apply's result**, not pre-computed. A partial-failure recovery run
(where plan B had 3 of 5 phases dispatched on a prior tick) reports
`dispatched` with `issues_created=2` on the next run — accurate, not
misleading.

### 3.4 Partial-failure policy

If `vk.apply` reports any failures for a plan, the dispatcher:
1. Records the failure in that plan's outcome.
2. **Stops iteration.** Does not advance to downstream plans this run.

Reason: a partial dispatch leaves plan B's issue set in an indeterminate state.
Downstream plan C's deps include B; advancing C now would skip the gate the
operator needs to see. The next tick re-evaluates B from a known state (some
issues exist, some don't — `vk.apply`'s diff handles this) and either
completes the dispatch or surfaces the error again.

### 3.5 Concurrency

Multiple root plans dispatch in declaration order — sequentially, one
`vk.apply` at a time. No threadpool, no async. `gh issue create` calls are
serial. Same simplicity guarantee `vk apply --all` already gives.

### 3.6 Exit codes for `vk spec apply`

| Code | Meaning |
|------|---------|
| 0 | Success — dispatched and/or already-dispatched outcomes, no errors |
| 2 | Usage error or `SpecValidationError` (bad grammar / cycle / etc.) |
| 4 | gh API failure during `vk.apply` (at least one outcome carries `apply_failures`) |
| 5 | Plan parse error for at least one plan in the spec |
| 6 | At least one cross-repo plan returned 404 via gh contents (`unreachable`) |

Code 6 distinguishes "spec-table path drift" (a row points at a path that no
longer exists upstream) from generic gh failures. Surfaces fast for the
common operator typo case.

---

## 4. CLI surface

### 4.1 New commands

```
vk spec apply <spec> [--yes] [--format text|json]
vk spec apply --all   [--yes] [--format text|json]
vk spec self-review <spec>
vk spec self-review --all
```

Both commands follow existing v2 conventions:
- Dry-run is the default; `--yes` is the explicit mutate flag.
- `--all` walks `docs/superpowers/specs/*.md` from the current working tree.
- `--format json` emits a machine-readable schema mirroring
  `vk apply --format json`.
- Exits 2 on flag misuse, 5 on parse error, 4/6 on runtime failures.

### 4.2 Output format (text mode)

```
$ vk spec apply docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md --yes
spec: vk-rebuild-state-machine

  ✅ vk-v2-library            already_dispatched
  ⚪ bridge-migration         blocked (deps: vk-v2-library)
  ✅ rework-1                 already_dispatched
  🟢 bridge-integration       dispatched (3 issues created)

summary: 1 dispatched, 2 already_dispatched, 1 blocked, 0 errors.
```

### 4.3 Output format (json mode)

```json
{
  "spec": "docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md",
  "applied": true,
  "outcomes": [
    {
      "plan": "vk-v2-library",
      "state": "already_dispatched",
      "issues_created": 0,
      "blocking_deps": []
    },
    {
      "plan": "bridge-migration",
      "state": "blocked",
      "issues_created": 0,
      "blocking_deps": ["vk-v2-library"]
    },
    {
      "plan": "bridge-integration",
      "state": "dispatched",
      "issues_created": 3,
      "blocking_deps": [],
      "apply_failures": []
    }
  ],
  "summary": {
    "dispatched": 1,
    "already_dispatched": 2,
    "blocked": 1,
    "errors": 0
  }
}
```

### 4.4 `vk spec status` cross-repo side-effect

`vk spec status` already exists. With `compute_status` now taking a `gh`
parameter, it gains cross-repo resolution for free — cross-repo rows stop
showing as `Unreachable` whenever a `GhClient` is available. The CLI passes
`gh = _make_gh_client()` (matching `vk apply`'s factory pattern). A
`--no-gh` flag for offline use degrades gracefully to today's
`Unreachable`-for-cross-repo behaviour.

---

## 5. Bridge integration

### 5.1 `discover_specs(repo)`

`src/vk/bridge/__init__.py` gains:

```python
def discover_specs(repo: str) -> list[SpecMeta]:
    """Walk docs/superpowers/specs/*.md in repo's checkout. Return parsed SpecMeta.

    Returns [] if checkout missing or specs dir absent. Unparseable specs
    are logged and skipped — one bad spec mustn't kill the tick. 'Unparseable'
    here means a markdown read or `## Implementation Plans` parse failure
    (not a Depends-on grammar error; grammar isn't validated at parse).
    """
```

Same shape as `discover_plans(repo)`. Uses `_repo_checkout_root(repo)` to
resolve the local path.

### 5.2 Cron caller change

In `agent-images/kali/scripts/vk-issue-bridge.py`:

```python
# existing
for plan in vk.bridge.discover_plans(repo, gh):
    result = vk.bridge.tick(plan, gh, vk_mcp)
    accumulate(result)

# NEW — added before the plans loop
for spec in vk.bridge.discover_specs(repo):
    try:
        spec_result = vk.spec.dispatch(spec, gh, yes=True,
                                       repo_root=vk.bridge._repo_checkout_root(repo))
        accumulate_spec(spec_result)
    except vk.spec.SpecValidationError as e:
        logger.warning("bridge: spec %s failed validation: %s", spec.path, e)
    except Exception as e:  # noqa: BLE001
        logger.exception("bridge: dispatch raised on %s", spec.path)
        accumulate_spec_failure(spec.path, str(e))
```

Order: **specs first, then plans, within a single repo's tick.** A plan
dispatched mid-tick gets its issues created with `vk-ready` labels; the
same tick's `discover_plans` then picks it up and runs `tick(plan)` to
project labels and sync the VK board card.

### 5.3 Cross-repo dispatch via the bridge's per-repo checkouts

A spec lives in one repo (typically `superpowers-for-vk`). Per D14,
`vk.spec.dispatch` only dispatches plans whose repo has a locally-writable
checkout — so `set_tracking_issue` can persist the writeback that prevents
the duplicate-Issue regression PR #122 fixed.

For the **operator** running `vk spec apply` locally, this typically means
only same-repo plans dispatch; cross-repo plans emit `deferred_cross_repo`
in the output (the operator sees clearly which plans need to be dispatched
elsewhere or wait for the bridge).

For the **bridge**, all managed repos are checked out under `VK_REPOS_DIR`
already (see `vk.bridge._repo_checkout_root`). `_resolve_writable_plan_dir`
finds the upstream plan there and dispatches normally. The writeback
(`set_tracking_issue` staging the change in the upstream checkout) follows
the same pattern `vk.bridge.tick` uses today — same persistence story,
same operator-driven commit path.

The newly-created issues in repo B get picked up by `discover_plans(B)`
on the SAME bridge tick (the per-repo loop visits each repo's plans dir
after the spec dispatch in that repo runs). Same-repo: zero-tick handoff.
Cross-repo: when the bridge later visits repo B for its own per-repo work,
`discover_plans(B)` picks up the new plan (≤ 60 s delay).

### 5.4 Failure isolation

A `vk.spec.dispatch` exception is caught by the cron caller and logged. The
existing plan-tick loop continues unaffected. Matches the existing "one bad
phase mustn't kill the tick" pattern at `vk/bridge/__init__.py:91`.

### 5.5 Bridge `TickResult` accumulation

The existing `TickResult` (plan-level) is unchanged. The cron caller adds a
parallel `SpecDispatchSummary` accumulator:

```python
@dataclass(frozen=True)
class SpecDispatchSummary:
    specs_walked: int = 0
    plans_dispatched: int = 0
    plans_already_dispatched: int = 0
    plans_blocked: int = 0
    errors: int = 0
    failures: tuple[str, ...] = ()
```

Logged at the end of each cron tick alongside the existing per-plan
`TickResult`. Operators see both layers in the bridge's tick log.

---

## 6. Testing strategy

### 6.1 Unit tests

| File | New cases |
|------|-----------|
| `tests/unit/test_spec_parser.py` | Parses `Depends on: —` → `()`. `None` → `()`. `-` → `()` (hyphen alias). `slug-a; slug-b` → `("slug-a", "slug-b")`. Whitespace tolerance around `;`. `depends_on_raw` preserves original text. `parse_spec` never raises on bad refs (validation is separate). |
| `tests/unit/test_spec_validation.py` | **New file.** All 7 validation errors fire with the documented messages. Plan-column duplicate names both rows. Forward-ref includes row indices. Manual-row ref names the offending dep. |
| `tests/unit/test_spec_dispatch.py` | **New file.** Root plan dispatches. Plan with `Complete` dep dispatches. Plan with `In Progress` dep emits `blocked` with the dep ID. Plan with all phases having `tracking_issue` emits `already_dispatched` (no gh writes). Dry-run produces no mutations. Partial-failure on plan B stops iteration (plan C not advanced). Multiple roots dispatched in declaration order. Cross-repo plan unreachable on 404 emits `unreachable`. |
| `tests/unit/test_spec_cross_repo.py` | **New file.** `compute_status` resolves cross-repo plan via mocked `gh.read_repo_file`. Resulting `Plan` round-trips through `vk.parser.parse` and matches the local-parse equivalent. 404 → `Unreachable` with the documented note. |
| `tests/unit/test_spec_cli.py` | **New file.** `vk spec apply <spec>` exit codes 0/2/4/5/6. `--all` walks all specs. `--format json` emits the documented schema. `vk spec self-review` is local-only (no gh client instantiated). |
| `tests/unit/test_ghclient.py` | `RealGhClient.read_repo_file` 404 → `FileNotFoundError`. `FakeGhClient.read_repo_file` returns dict-backed bytes. |

### 6.2 Integration tests

| File | New cases |
|------|-----------|
| `tests/integration/test_spec_dispatch.py` | **New file.** Fixture spec with 4 plans (root, 2 middle plans both depending on root, leaf depending on both middles — diamond). Step 1: dispatch root, verify issues created in correct repos with correct labels. Step 2: re-run; root emits `already_dispatched`, middles still `blocked`. Step 3: simulate root completion (mark all phase `completion.at`), re-run; both middles dispatch in declaration order. Step 4: re-run; middles `already_dispatched`, leaf still `blocked` (one middle not complete). Step 5: complete both middles; leaf dispatches. Asserts cross-repo `gh issue create --repo X` calls in correct order. |
| `tests/integration/test_bridge_specs.py` | **New file.** `discover_specs(repo)` walks specs dir, returns parsed list. Unparseable spec is skipped with a warning. Same-tick spec→plan handoff: spec dispatches plan B, the same iteration's `discover_plans` picks up the plan, `tick(plan)` syncs the VK board. Tests verify call order. |

### 6.3 Fixtures

- `tests/fixtures/specs/linear-three-plans.md` — root → middle → leaf, all
  same-repo. For basic dispatch flow.
- `tests/fixtures/specs/cross-repo-diamond.md` — root in repo-a, two middle
  plans in repo-b, leaf in repo-c depending on both middles. Exercises gh
  contents API path and fan-in semantics.
- `tests/fixtures/specs/old-style-free-form.md` — pre-grammar spec with
  free-form `Depends on` prose. Asserts `parse_spec` returns
  `depends_on_raw` correctly and that `compute_status` (without invoking
  validation) renders status normally. Regression guard for the "old specs
  still render" promise.

### 6.4 Coverage

The 85 % gate stays. New code is parse + branchy gate logic + thin CLI
wrappers + a Protocol method — reaches full coverage cheaply.

---

## 7. Release mechanics

### 7.1 Rollout phases

The work spans two repos and is naturally a three-PR sequence:

1. **Phase A — superpowers-for-vk parser + cross-repo status.** Parser
   change (`depends_on` tuple + `depends_on_raw`), `compute_status` gains
   `gh` parameter, `GhClient.read_repo_file` Protocol method, `RealGhClient`
   and `FakeGhClient` implementations, unit tests. `vk spec status` keeps
   working on old specs. PR 1 in this repo. Independently shippable.

2. **Phase B — superpowers-for-vk dispatch + CLI.** `vk.spec.dispatch`,
   `vk spec apply`, `vk spec self-review`, validation, integration tests,
   skill doc updates, version bump. Independently shippable after Phase A.
   PR 2 in this repo.

3. **Phase C — agent-images bridge integration.** Cron caller adds the
   `discover_specs` / `dispatch` loop. Add the same-tick integration test
   from §6.2. PR 3 in `derio-net/agent-images`.

Phases A and B are independently safe to ship without Phase C: the operator
can run `vk spec apply` manually, and the spec rendering improvements
land for everyone. Phase C is the autonomy unlock.

### 7.2 Version bump

Per `CLAUDE.md`, three-file lockstep:

| File | Field | Target |
|------|-------|--------|
| `pyproject.toml` | `[project].version` | `2.1.4 → 2.2.0` |
| `.claude-plugin/plugin.json` | `.version` | `2.1.4 → 2.2.0` |
| `.claude-plugin/marketplace.json` | `.plugins[0].version` | `2.1.4 → 2.2.0` |

Minor bump — new user-visible CLI commands (`vk spec apply`,
`vk spec self-review`), new library surface (`vk.spec.dispatch`,
`vk.bridge.discover_specs`), and new mandatory grammar for the
opt-in spec-dispatch workflow.

The version bump lives in Phase B (Phase A is pure refactor + additive
protocol method).

After editing: `uv sync && uv run vk --version`.

### 7.3 Skill doc updates

Updated in the same PR as the behaviour change:

- `skills/vk-dispatch/SKILL.md` — note the new spec-level entry point and
  example `vk spec apply` flow. Phase B.
- `skills/vk-plan/SKILL.md` — sample `Depends on` grammar; link to
  `vk spec self-review`. Phase B.
- `skills/vk-progress/SKILL.md` — note that cross-repo plans no longer
  show as `Unreachable` after Phase A.

Whether a new `vk-spec` skill exists or this folds into `vk-dispatch` is
decided at plan-writing time, not now.

---

## 8. Rollback story

Each phase is independently revertible:

- **Phase A revert:** `compute_status` loses cross-repo resolution; cross-repo
  rows show as `Unreachable` again (today's behaviour). `read_repo_file`
  Protocol method becomes unused. No spec file mutations to undo.
- **Phase B revert:** `vk spec apply` and `vk spec self-review` disappear.
  Specs that adopted the new `Depends on` grammar render normally because
  the parser tolerates anything in the cell. No spec file mutations to undo.
- **Phase C revert:** Bridge cron stops auto-advancing specs. Plans that
  were dispatched stay dispatched. Operator can resume manual `vk spec apply`
  from any working tree.

The spec table format itself is forward-compatible: adding `depends_on_raw`
to `PlanRef` doesn't break consumers; specs with new grammar still parse
under the old parser (the depends_on cell becomes a single-element tuple
containing the raw string, which fails ref-resolution if dispatch is
invoked — but dispatch doesn't exist in the rolled-back code, so no
breakage).

No irreversible schema change is introduced anywhere.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Operator forgets to migrate a spec's `Depends on` cells and runs `vk spec apply`; bad-grammar errors pile up. | `vk spec self-review` reports every error with the row index and the offending cell text. Operator runs it once before `apply --yes`. |
| Cross-repo plan is renamed/moved on upstream `main`; spec table File cell still points at the old path. | `compute_status` emits `state="Unreachable"` with the 404 path in the note. `vk spec apply` exits 6 with the offending spec/plan named. Operator fixes the spec row, re-runs. |
| Bridge tick is slow because of gh API calls for cross-repo reads. | Cost analysis (§2.3) sizes the worst case at 1,800 calls/hr for one heavy spec — within quota. If quota becomes real, add an `(repo, path, sha)`-keyed LRU cache. |
| Multiple bridge instances run concurrently on different hosts; double-dispatch races. | Existing risk for `vk apply` already; same mitigation: only one bridge runs at a time per organisation. Documented operator constraint, not enforced in code. |
| Author depends on a manual-action row (File = `—`), expecting the bridge to wait forever. | Self-review rejects this with the documented error (decision D9). Manual rows are advisory-only. |
| Plan-column ID with surrounding whitespace renders identically to a trimmed version, but the ref doesn't match because we don't trim Plan column values. | Plan-column extraction trims whitespace; refs also trimmed. Documented in §1.1. Unit test pins the behaviour. |
| Free-form `Depends on` cell in an old spec contains `;` characters; parser splits incorrectly. | Old specs aren't validated; `depends_on` is best-effort parsed and the resulting unresolvable refs are simply ignored by `compute_status`. Only matters if the author then opts into spec-dispatch — in which case `self-review` flags the bad refs. |
| `gh api repos/.../contents/` rate-limit hit mid-tick. | Failure isolation: bridge logs the spec failure and moves on to the next spec / plan-tick loop. Next tick retries. |

---

## 10. Open questions

None at spec time. The following are explicit deferrals, not unknowns:

- Caching strategy for cross-repo reads (deferred until quota becomes real).
- Bulk migration tool for old `Depends on` cells (deferred — opt-in per spec).
- Push-shape via gh webhooks (deferred — pull-shape suffices for now).
- Whether spec-dispatch deserves a dedicated `vk-spec` skill or folds into
  `vk-dispatch` (decided at plan-writing time).

---

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-05-14-spec-dispatch | `derio-net/superpowers-for-vk` | `2026-05-14-spec-dispatch` | — |
| 2026-05-14-spec-dispatch-bridge | `derio-net/agent-images` | `docs/superpowers/plans/2026-05-14-spec-dispatch-bridge/` | 2026-05-14-spec-dispatch |
