# Bridge dedicated-checkout + self-healing sync (#286)

## Why

The bridge's per-tick sync (`_pull_managed_repo`) does
`fetch && checkout main && pull --ff-only` on a checkout it **shares** with
VibeKanban. VK force-moves `main` from a worktree on PR-merge
(`git branch -f main origin/main`), leaving the bridge's `HEAD/main` at the
merged commit while its working tree stays frozen at the pre-merge parent.
Both recovery commands become no-ops (`checkout main` → already on main;
`pull --ff-only` → already up to date), so the stale tree never reconciles.
`discover_plans` reads plan state from that frozen tree → dispatch wedges
silently. Observed 2026-06-08 on `derio-net/runs-fr`.

The root cause is a single-source-of-truth violation: **two writers, one
working tree.**

## What

Per the spec (`docs/superpowers/specs/2026-06-08-bridge-dedicated-checkout-self-healing-sync-design.md`):

1. **Dedicated bridge-owned checkout.** The bridge stops sharing VK's
   checkout and maintains its own at `<base>/<name>` (base =
   `FR_BRIDGE_CHECKOUT_DIR`, else `~/.cache/fr/bridge-checkouts`),
   clone-if-missing from the configured repo's origin URL. As the sole
   writer, VK's out-of-band ref moves can never desync it. The parser
   (`parse()` / `discover_plans`) is untouched — only *which* path it reads
   and *who else writes* there changes. (Reading plan state from git objects
   was rejected: it would rewrite the deeply path-coupled core parser shared
   across the CLI, tests, and dispatch.)

2. **Idempotent self-healing sync.** `_pull_managed_repo` becomes
   `fetch origin` → detect dirty tree → `checkout main` →
   `reset --hard origin/main`. Unconditional reset reconciles any
   out-of-band ref move or dirty tree each tick, killing the
   "Already up to date" trap. Best-effort log-and-continue resilience is
   preserved — a stale dispatch still beats no dispatch.

3. **Desync observability metric.** When the pre-reset tree is dirty (the
   bug signature; a clean tree merely behind origin/main is a normal
   fast-forward), emit a dedicated counter
   `willikins_vk_bridge_repo_desync_total{repo="owner/name"}` + a clear WARN
   log. Kept distinct from `failure_total` so a self-healed desync never
   reads as a tick failure. In the new architecture this should be ~0, so
   any nonzero value is a genuine anomaly signal.

## How (phases)

1. **Desync metric** — `MetricsPusher.push_repo_desync_total` (+ NullMetrics
   no-op). Foundational.
2. **Dedicated checkout + sync** — `_bridge_checkout_base`,
   `_ensure_bridge_checkout` (clone-if-missing), and the `_pull_managed_repo`
   rewrite (fetch + reset --hard, returns desync-detected bool).
3. **Wire the loop** — `main()` resolves owner → ensures+syncs the bridge
   checkout → pushes the desync metric on detection → points `FR_REPOS_DIR`
   at the bridge checkout → discovers. Plus the integration-test rewrite for
   the new architecture and a bridge regression sweep.
4. **Version bump + gates** — patch bump, ruff/mypy/pytest per ci.yml.

Every phase is TDD (RED → GREEN) and fully agentic — no manual phases. The
live repro + self-heal verification is a **post-merge** Test Plan (carried
in the spec and PR body), not a build step.
