# Ticket context enrichment — spec link, plan prose, phase YAML

**Date:** 2026-06-04
**Status:** Approved (autonomous run; operator delegated design approval via /goal)
**Tracking:** single PR, spec + plan + implementation together

## Problem

GitHub Issues created by `vk apply` and VK cards created by
`vk.bridge.dispatch_phase` carry only pointers: a repo-relative spec *path*
(plain text, not a link), a plan *directory path*, and a one-line phase
title. Consumers — humans triaging on GitHub, and VK-spawned agents whose
workspace prompt is derived from the card description — must clone the repo
and navigate the plan folder before they can see what the work actually is.
The `vk-execute` skill even promises "the full task description is in the
GitHub Issue body", which is not true today.

## Requirement

When creating GH and VK tickets, their descriptions must include:

1. **A GitHub link to the relevant spec** (`plan.meta.spec`, as a clickable
   blob URL).
2. **The plan's prose** (the plan folder's `_prose.md` content).
3. **The current phase YAML document** (the phase's `NN.yaml` content).

Both creation surfaces are covered:

- **GH Issues** — `render_body()` in `src/vk/render.py`, consumed by
  `IssueCreate` (operator `vk apply --yes`) and `IssueBodyChange` (sync).
- **VK cards** — the `description` built inline in
  `dispatch_phase()` (`src/vk/bridge/dispatch.py`). Enriching it also
  enriches the spawned agent's prompt: VK derives the workspace prompt from
  the linked card's title/description (`start_workspace.issue_id`).

## Decisions (resolved during brainstorm)

- **"Current phase yaml" = the ticket's phase document, embedded verbatim,
  including the `state:` block.** v2 bodies are self-healing projections —
  `observe()` reads the live body, `diff()` emits `IssueBodyChange` when
  `obs.body != rendered.body`, and both the operator `vk apply` and the
  bridge tick apply body changes. Embedding the full document means Issue
  bodies track step ticks / completion stamps automatically. This is the
  reconciliation architecture working as designed; the "Static body
  template" docstring in `render_body` is updated accordingly.
- **Spec link branch is `main`.** Matches the bridge's hardcoded
  `git checkout main` pull convention and the dispatch reachability gate
  ("plan and spec must be on `origin/HEAD`").
- **Prose and YAML go in collapsed `<details>` blocks** so Issues stay
  scannable; the existing tracking header stays first.
- **No body-section parsing is introduced.** Rejected the alternative of
  enriching create-only and excluding enrichment from the body diff — that
  would reintroduce body-text parsing, which v2 deliberately retired ("the
  plan is authoritative").
- **Link-only enrichment rejected** — fails the literal requirement (prose
  and YAML *in* the descriptions).

## Design

### 1. Parser carries raw texts (`src/vk/parser.py`)

The renderer is pure ("never performs I/O"), so the texts are loaded at
parse time:

```python
@dataclass(frozen=True)
class Plan:
    dir: Path
    meta: PlanMeta
    phases: tuple[PhaseDoc, ...]
    repo_root: Path | None = None
    prose: str | None = None                 # _prose.md content, None if absent
    phase_texts: Mapping[int, str] = field(default_factory=dict)
                                             # phase number -> raw NN.yaml text
```

`parse()` populates `prose` (missing `_prose.md` → `None`, graceful) and
`phase_texts` (raw file text, exactly as on disk). Defaults keep existing
direct-`Plan(...)` constructions (tests, builders) valid.

Determinism note: the embedded YAML is the file content read at parse
time. After `plan_ops.set_tracking_issue` writeback, the next
observe→render→diff cycle re-renders with the updated file — the same
mechanism that already handles the post-create URL fill-in.

### 2. Renderer enrichment (`src/vk/render.py`)

New pure helpers:

- `spec_url(plan) -> str | None`
  - `None` spec → `None` (the `📐 Spec:` line keeps `—`).
  - Same-repo path → `https://github.com/{target_repo}/blob/main/{path}`.
  - Cross-repo `owner/repo:path` (detected via the existing
    `vk._urls.is_cross_repo_spec`) →
    `https://github.com/{owner/repo}/blob/main/{path}`.
- `enrichment_block(plan, phase) -> str` producing:

  ````markdown
  ## Plan prose

  <details>
  <summary>📜 _prose.md</summary>

  {prose}

  </details>

  ## Phase document

  <details>
  <summary>🧾 NN.yaml</summary>

  ```yaml
  {raw phase yaml}
  ```

  </details>
  ````

  - The YAML code fence length is computed deterministically:
    `max(3, longest backtick run in content + 1)` — phase YAML legitimately
    contains triple-backtick fences inside step text.
  - Missing prose → the prose section is omitted (no placeholder noise).
  - Missing phase text (direct-constructed `Plan`) → phase section omitted;
    enrichment degrades to nothing rather than crashing.
- **Truncation guard:** GitHub caps Issue bodies at 65,536 characters. If
  the assembled body would exceed a 60,000-char budget, the YAML block is
  truncated first, then the prose block, each with a deterministic marker
  `… (truncated — see {repo-relative path} in the repo)`. Deterministic so
  re-renders converge (no diff churn).

`render_body()` changes:
- `📐 Spec:` renders as `[{path}]({spec_url})` when a URL is resolvable;
  bare path otherwise.
- The enrichment block is appended after the existing Dependencies section.
- Docstring updated: the body is no longer "static through close" — it
  tracks the plan state like every other rendered projection.

### 3. VK card description (`src/vk/bridge/dispatch.py`)

`dispatch_phase()` appends to the existing 4-line description (which test
H9 pins and stays as the prefix):

```
{plan slug}
Phase {n}/{total}
{phase title}
{tracking url}

Spec: {spec_url or spec path or "—"}

{enrichment_block(plan, phase)}
```

Card **titles are untouched** — `pr_state` and `dedup` parse titles, never
descriptions; nothing in `vk.bridge.*` parses card descriptions (verified
end-to-end per the bridge audit rule).

### 4. Docs

- `skills/vk-dispatch/SKILL.md` / `skills/vk-execute/SKILL.md`: note that
  Issue bodies and card descriptions now embed the spec link, plan prose,
  and the phase document (the vk-execute claim becomes true).
- `render_body` / `dispatch_phase` docstrings updated.

### 5. Out of scope

- `vk.bridge.prompt.build_prompt` is currently dead code (no callers); it
  is left untouched. Follow-up candidate: delete or wire it.
- Cross-repo first-dispatch, default-branch detection (the `main` link
  convention is accepted).

## Error handling

- Missing `_prose.md` → section omitted; no failure.
- Unresolvable spec URL → plain-text path (current behavior preserved).
- Oversized content → deterministic truncation, never a GitHub 422.
- All enrichment inputs come from the already-parsed `Plan`; no new I/O or
  failure paths in render/dispatch.

## Testing

- **Parser:** `prose`/`phase_texts` populated from a plan folder; missing
  `_prose.md` → `None`; raw text round-trips byte-for-byte.
- **Renderer:** spec link same-repo / cross-repo / `None`; prose +
  phase-YAML details blocks present; fence-length escaping when content
  contains ``` runs; truncation determinism (`render_body` idempotent on
  same inputs); existing body tests updated.
- **Dispatch:** H9 updated — description starts with the pinned 4 lines and
  contains the spec link, prose, and phase YAML.
- **Integration:** existing apply/diff round-trip tests confirm enriched
  bodies converge (no perpetual `IssueBodyChange`).

## Version

Patch bump (`scripts/bump-version.py patch`) — changes `src/**` and
`skills/**`, no new subcommand or skill.

## Implementation Plans

| Plan | Repo | File | Depends on |
| --- | --- | --- | --- |
| 2026-06-04-ticket-context-enrichment | `derio-net/superpowers-for-vk` | `docs/superpowers/archived-plans/2026-06-04-ticket-context-enrichment/` | — |
