# fr spec status: resolve cross-repo plan rows via the gh contents API

Wire `compute_status()` to reach into sibling repos the same way `fr archive`
already does, so a multi-repo spec's rollup stops reporting merged-and-verified
cross-repo plans as `🔒 Unreachable`. Closes the "archive can see cross-repo
rows; status can't" inconsistency in [#339](https://github.com/derio-net/super-fr/issues/339).

Full design: `docs/superpowers/specs/2026-07-03-spec-status-crossrepo-resolution-design.md`.

## Operator-locked decisions

- **Full remote parse**, not existence-only: fetch each remote `NN.yaml` and
  compute exact phase/step counts, so the aggregate reaches parity.
- **Default-on gh with `--no-gh`**: `fr spec status` builds a `RealGhClient`
  by default (like `fr archive`); `--no-gh` and any gh failure/offline degrade
  a cross-repo row to `Unreachable` — today's behavior, unchanged.
- **CLI + library only**: the GHA workflow is untouched (its repo-scoped
  `GITHUB_TOKEN` can't read private sibling repos; a broader token is a
  follow-up).

## Shape

1. **New read surface** — `list_dir` / `read_file` on the `GhClient` Protocol,
   `RealGhClient` (`gh api .../contents/...`, `--jq .[].name` and the raw
   Accept header), and `FakeGhClient` (a `remote_tree` map). `file_exists`
   proves one path; full parse needs to list a folder and read files.
2. **Shared `_status_counts`** — the per-plan arithmetic is extracted from
   `compute_status` so the local and remote branches compute completion
   identically (the same shared-predicate doctrine `plan_locally_complete`
   already follows).
3. **Remote resolution** — `_resolve_remote_plan_phases` probes the
   active/implemented/legacy path variants (`_archive_path_variants`, active
   first), gates on `_meta.yaml`, parses the phase files, and memoizes per run.
   `compute_status` gains an optional `gh`; every failure path degrades to
   `Unreachable`, never a crash and never a silent pass.
4. **CLI** — `spec_cmd` gets the `_make_gh_client` seam and `--no-gh`.
5. **Docs + version bump** — retire the "Phase 3 / Local-fs only" wording and
   bump the plugin version.

## TDD

Every code phase is red → green (→ optional refactor). All tests run in-process
against `FakeGhClient` — no network. The existing `compute_status` tests are
the guard that the `_status_counts` extraction changes no local behavior.
