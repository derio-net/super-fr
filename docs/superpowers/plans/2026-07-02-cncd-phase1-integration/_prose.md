# cncd phase-1 integration: parity harness + CncdRunner

super-fr's slice of the CNC phase-1 spec
(`agentic-stoa/cnc-fr:docs/superpowers/specs/2026-07-02-cncd-phase1-ledger-api.md`,
§3.3 and §3.5). Two deliverables, both additive — no fr internals move.

## Why

cncd (the Go control-plane daemon) re-implements the v2 plan-as-folder
parser. Cross-language drift between fr's Pydantic models and cncd's Go
port must be caught by CI, not prose — that is the **schema parity
harness** (§3.3): a JSON Schema export of the v2 models plus a fixtures
corpus of valid and invalid plan folders that the umbrella repo vendors
and cncd's parser must pass verbatim (golden tests).

Separately, `fr apply --to cncd` (§3.5) needs a registered runner so
plans can be projected into cncd's ledger via `POST /v1/ingest`. The
runner is a thin HTTP client shaped exactly like `fr_vk.VkRunner`:
7-method `fr_dispatch.protocols.Runner` protocol + `name`, registered
under the `fr.runners` entry-point group as `cncd`.

## Shape of the change

**Phase 1 — parity harness (package `fr`):**

- `fr.parser.parse_strict(plan_dir)`: `parse()` plus the two
  folder-level invariants the corpus contract requires — `_prose.md`
  mandatory and contiguous phase numbering 1..N. `parse()` itself stays
  lenient (plans in the wild without prose keep parsing; the bridge
  keeps skipping gracefully).
- `scripts/export-plan-schema.py`: emits `model_json_schema()` for
  `PlanMeta` and `PhaseDoc` (stdout combined doc, or two files into an
  outdir). This is what the umbrella repo runs to vendor the schema.
- `tests/fixtures/plan_folders/`: the corpus. `valid/` and `invalid/`
  plan FOLDERS plus a `manifest.yaml` giving each invalid case a stable
  machine-readable error code (for the Go golden tests) and a Python
  message match (for our own round-trip test). Invalid cases: missing
  `_prose.md`, bad P.T.S id, `state.steps` key-set mismatch, bad `tag`,
  non-contiguous phases, unknown extra field (`extra="forbid"` — the
  `slug:` alias trap is encoded here on purpose: the field is `plan`).
  Existing `tests/fixtures/plans/*.md` are legacy Markdown-AST fixtures
  and are not touched.

**Phase 2 — CncdRunner (new package `packages/fr-cncd`):**

- Mirrors `fr-vk`: workspace member, lockstep version, deps
  `["fr", "fr-dispatch"]`, entry point `cncd = "fr_cncd.runner:CncdRunner"`.
- Config mirrors VkRunner's env convention: `CNCD_URL` (base URL of the
  cncd server), optional `CNCD_SLOT_BUDGET`. `preflight()` fails every
  eligible phase cleanly when `CNCD_URL` is unset.
- `dispatch()` POSTs the plan folder (files verbatim, keyed by name,
  with repo/source_path/phase/issue context) to `POST /v1/ingest` —
  cncd's ingest is idempotent by content hash (spec §3.3), so
  `existing_dispatches()` is honestly empty and re-POSTs are no-ops.
- stdlib `urllib.request` only — no new third-party dependency for a
  thin client.
- Integration-tested against a local stub HTTP server (pytest fixture).
  The real cncd round-trip test lives in the umbrella repo.

## Non-goals

- No Go code, no cncd server, no umbrella-repo vendoring (that's the
  umbrella's plan).
- No change to `--to vk` / GitHub flows, no fr internals moved.
- No `fr status` cncd read-back (spec marks it optional; deferred until
  the server exists to read from).
