# Checkout-free install bootstrap + `fr repos` instrument command

Implements `docs/superpowers/specs/2026-06-16-install-bootstrap-and-repo-instrument-design.md`.

Two deliverables, plus docs and a version bump:

1. **`scripts/bootstrap.sh`** — a remote one-liner
   (`curl -fsSL .../scripts/bootstrap.sh | bash`) that manages a hidden source
   checkout under `~/.cache/fr/src/super-fr` and delegates to the canonical
   `scripts/install.sh`. Re-running self-heals (`fetch` + `reset --hard
   origin/main`), so the operator never manually clones and stays current.
   `install.sh` remains the single source of truth for install steps.

2. **`fr repos sync`** — instruments **already-checked-out** repos by writing
   `docs/superpowers/plan-config.yaml` in place. It never clones. The collection
   is the union of a manifest (`~/.config/fr/repos.yaml`) and positional
   `owner/repo` args (args also append to the manifest unless `--no-save`).
   Checkouts resolve via the existing `$FR_REPOS_DIR` / `~/repos/<name>`
   convention, with a per-entry `path:` override. A repo that isn't checked out
   locally produces a **warning, not a failure**. Mutating, so dry-run is the
   default; `--yes` writes.

## Why instrument with an "optional" file

Investigation (see spec) confirmed `plan-config.yaml` is optional: only
`scripts/validate-plans.sh` reads it (with built-in fallbacks), and its
`dispatch:` keys are dead config. Instrumenting is still worthwhile — it gives
each repo a real, working **validator profile** and standardizes it. The
template writes the live validator keys and a clearly-labelled, commented,
documentation-only dispatch stub. The command does not pretend the dispatch
keys are functional, and a repo works without the file.

## Phase map

- **Phase 1** — `fr.repos` module: manifest model/loader, checkout resolver,
  template renderer, manifest append. Pure unit-tested library, no CLI.
- **Phase 2** — `fr repos sync` command + `cli.py` registration, driven by
  Phase 1.
- **Phase 3** — `scripts/bootstrap.sh` + integration test (extends the
  `test_install_sh.py` pattern). Independent of 1/2.
- **Phase 4** — README + `fr skills` docs and the **minor** version bump;
  full CI gate locally before delivery. Depends on 2 and 3.

TDD throughout: every code step is preceded by a failing test. No manual phase —
the bootstrap is served automatically from `main` once merged; the only human
step is the standard PR merge.
