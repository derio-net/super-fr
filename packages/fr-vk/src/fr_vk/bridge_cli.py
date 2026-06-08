"""fr_dispatch cron entry point — `python -m fr_vk.bridge`.

One tick: sync every managed repo's bridge-OWNED checkout to
head-of-main (a checkout nothing else writes to — #286), walk
`discover_plans` per repo against it, dispatch eligible phases via
`fr_dispatch.tick`, run the PR-state sweep + workspace reaper, push the
heartbeat. The whole thing is wrapped by a single `flock`-based lock
file so two cron firings can never overlap (I4), and each plan's
iteration is wrapped in a try/except boundary so one bad plan can't
take the daemon down (I9).

Hidden by design — there is no `vk bridge` public CLI verb (E1).
"""

from __future__ import annotations

import argparse
import datetime
import errno
import fcntl
import json
import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import IO, Any, cast

from fr.gh import GhError, _classify_error
from fr.real_ghclient import RealGhClient
from fr_dispatch import discover_plans
from fr_dispatch import tick as _tick
from fr_dispatch.metrics import MetricsPusher

from fr_vk._mcp_client import VkMcpClient
from fr_vk.config import bridge_env
from fr_vk.pr_state import tick as _pr_state_tick
from fr_vk.runner import (
    HEARTBEAT_METRIC,
    METRICS_JOB,
    METRICS_NAMESPACE,
    METRICS_REASON_ALIASES,
    VkRunner,
)
from fr_vk.workspaces import reap_orphans

__all__ = ["main"]

logger = logging.getLogger("vk-issue-bridge")

# Legacy VK metric names — wire format preserved across the split.
_metrics = MetricsPusher(
    namespace=METRICS_NAMESPACE,
    job=METRICS_JOB,
    heartbeat_metric=HEARTBEAT_METRIC,
    reason_aliases=METRICS_REASON_ALIASES,
)

_DEFAULT_LOCK_PATH = "/var/run/fr-bridge.lock"
_FALLBACK_LOCK_PATH = "/tmp/fr-bridge.lock"
_SEEN_PLANS_PATH = Path.home() / ".willikins-agent" / "_seen_plans.json"
# Base dir for the bridge-owned checkouts (#286). The bridge is the SOLE
# writer of these, so VK's out-of-band ref moves can never desync them.
_DEFAULT_BRIDGE_CHECKOUT_BASE = Path("~/.cache/fr/bridge-checkouts")


def _emit_banner() -> None:
    """First INFO record of every tick — version + UTC timestamp (G5)."""
    vk_ver = _pkg_version("fr")
    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.info(f"[bridge] - v{vk_ver} - {now} - tick")


def _configured_repos() -> list[Path]:
    """Resolve managed repo checkouts from env / convention.

    `FR_BRIDGE_REPOS` (legacy: `VK_BRIDGE_REPOS`) is a comma-separated
    list of absolute paths. When
    unset, the default is the live bridge convention — every directory
    under `~/repos/<name>/` that contains a `.git` entry.
    """
    raw = (bridge_env("REPOS") or "").strip()
    if raw:
        return [Path(p).expanduser() for p in raw.split(",") if p.strip()]
    home_repos = Path("~/repos").expanduser()
    if not home_repos.is_dir():
        return []
    return sorted(p for p in home_repos.iterdir() if (p / ".git").exists())


def _repo_owner_name(repo_path: Path) -> str | None:
    """Resolve a local checkout to `owner/name` via `git remote get-url`."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("bridge: %s remote lookup failed: %s", repo_path, e)
        return None
    url = result.stdout.strip()
    for prefix in ("git@github.com:", "https://github.com/", "git://github.com/"):
        if url.startswith(prefix):
            tail = url[len(prefix) :]
            if tail.endswith(".git"):
                tail = tail[:-4]
            if "/" in tail:
                return tail
    logger.warning("bridge: %s origin URL %r not recognized as GitHub", repo_path, url)
    return None


def _bridge_checkout_base() -> Path:
    """Base dir for bridge-owned checkouts (#286).

    `FR_BRIDGE_CHECKOUT_DIR` (legacy `VK_BRIDGE_CHECKOUT_DIR`) overrides;
    unset → `~/.cache/fr/bridge-checkouts`.
    """
    raw = (bridge_env("CHECKOUT_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return _DEFAULT_BRIDGE_CHECKOUT_BASE.expanduser()


def _ensure_bridge_checkout(configured: Path, name: str, base: Path | None = None) -> Path | None:
    """Return the bridge-owned checkout for `name`, cloning it if missing (#286).

    The checkout lives at `<base>/<name>` and is cloned from the configured
    repo's `origin` URL — the real remote, so `fetch origin` +
    `reset --hard origin/main` always reach true head-of-main. Returns the
    path, or `None` (logged, no raise) when the origin can't be resolved or
    the clone fails — the tick skips that repo this round.
    """
    base = base or _bridge_checkout_base()
    dest = base / name
    if (dest / ".git").exists():
        return dest
    try:
        url = subprocess.run(
            ["git", "-C", str(configured), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.warning("bridge: %s origin lookup failed: %s; skipping", configured, e)
        return None
    try:
        base.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", url, str(dest)],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        stderr = getattr(e, "stderr", "") or ""
        logger.warning(
            "bridge: clone %s -> %s failed: %s; skipping", url, dest, stderr.strip() or e
        )
        return None
    return dest


def _pull_managed_repo(repo_path: Path) -> bool:
    """`git fetch origin` + `git reset --hard origin/main` (#286).

    Idempotent and self-healing on the bridge-owned checkout: unlike the old
    `checkout main && pull --ff-only`, an unconditional reset reconciles ANY
    out-of-band ref move or dirty tree each tick — including the bug
    signature where `HEAD == origin/main` but the working tree is frozen at
    the pre-merge parent (a no-op for both `checkout` and `pull --ff-only`).

    Returns `True` iff a desync (dirty working tree) was detected and healed;
    a clean tree merely behind `origin/main` is a normal fast-forward, not a
    desync. Best-effort — a git failure logs a warning and returns `False`,
    and the tick continues against the (possibly stale) checkout because a
    stale dispatch beats no dispatch.
    """

    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repo_path), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )

    try:
        _run("fetch", "origin")
        dirty = bool(_run("status", "--porcelain").stdout.strip())
        if dirty:
            logger.warning(
                "bridge: %s working tree desynced (out-of-band ref move?); "
                "reconciling to origin/main",
                repo_path,
            )
        _run("checkout", "main")
        _run("reset", "--hard", "origin/main")
        return dirty
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        stderr = getattr(e, "stderr", "") or ""
        logger.warning(
            "bridge: sync failed for %s: %s; continuing with stale checkout",
            repo_path,
            stderr.strip() or e,
        )
        return False


def _construct_mcp_client() -> VkMcpClient:
    """Build a `VkMcpClient`. Loud-exit when both binaries are missing (I1)."""
    if not shutil.which("vibe-kanban-mcp") and not shutil.which("npx"):
        sys.stderr.write(
            "error: vibe-kanban-mcp and npx both missing. Install via "
            "'apt install nodejs npm' then 'npm install -g vibe-kanban'\n"
        )
        raise SystemExit(2)
    return VkMcpClient()


def _gh_rate_limit_guard(op: Callable[[], Any]) -> Any:
    """Run `op()`; on a gh rate-limit error, push a metric and return None (I3)."""
    try:
        return op()
    except GhError as exc:
        stderr_text = (exc.stderr or "") + " " + str(exc)
        if _classify_error(stderr_text) == "rate_limit":
            logger.warning("bridge: gh rate limit hit; backing off this tick")
            _metrics.push_failure_total(reason="gh_rate_limited")
            return None
        raise


def _load_seen_plans() -> set[str]:
    try:
        with _SEEN_PLANS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {str(x) for x in data}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return set()
    return set()


def _store_seen_plans(slugs: Iterable[str]) -> None:
    try:
        _SEEN_PLANS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _SEEN_PLANS_PATH.open("w", encoding="utf-8") as f:
            json.dump(sorted(slugs), f)
    except OSError as e:
        logger.warning("bridge: failed to write seen-plans state: %s", e)


def _acquire_lock(path: str) -> IO[str]:
    """Acquire `flock(LOCK_EX | LOCK_NB)` on `path` (I4).

    Raises `BlockingIOError` if another tick already holds the lock.
    """
    lock_path = Path(path)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        # /var/run is often read-only for non-root processes; fall back
        # to /tmp so unprivileged operators can still run the daemon.
        if path == _DEFAULT_LOCK_PATH:
            lock_path = Path(_FALLBACK_LOCK_PATH)
        else:
            raise
    fh = open(lock_path, "w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        fh.close()
        if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
            raise BlockingIOError("tick already in progress") from e
        raise
    return fh


def main(argv: list[str] | None = None) -> int:
    """One bridge tick — see module docstring."""
    parser = argparse.ArgumentParser(prog="fr_dispatch")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit the banner and exit 0 without touching gh / MCP.",
    )
    args = parser.parse_args(argv)

    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.setLevel(logging.INFO)

    _emit_banner()

    if args.dry_run:
        logger.info("fr_dispatch: dry-run complete")
        return 0

    lock_path = bridge_env("LOCK_PATH") or _DEFAULT_LOCK_PATH
    try:
        lock_fh = _acquire_lock(lock_path)
    except BlockingIOError:
        logger.info("tick already in progress, skipping")
        return 0

    try:
        gh = RealGhClient()
        mcp = _construct_mcp_client()

        try:
            seen_plans_before = _load_seen_plans()
            seen_plans_after: set[str] = set()

            # VK requires project_id for create_issue / list_issues when the
            # MCP server isn't inside a workspace context (the cron is exactly
            # that case). Read once at tick entry and pass through. The empty-
            # string case is treated as unset so a blank shell export doesn't
            # silently swallow the failure mode.
            # K8s injects `VK_DERIO_OPS_PROJECT_ID` (canonical, `_ID`-suffixed);
            # legacy docs use the no-suffix name. Read both for forgiveness.
            project_id = (
                os.environ.get("VK_DERIO_OPS_PROJECT_ID")
                or os.environ.get("VK_DERIO_OPS_PROJECT")
                or None
            )
            if project_id is None:
                logger.warning(
                    "[bridge] VK_DERIO_OPS_PROJECT_ID unset — dispatch will be "
                    "refused for any plan with vk-ready phases (label sync "
                    "still runs)"
                )
            runner = VkRunner(mcp, project_id=project_id)

            configured = _configured_repos()
            logger.info(
                "[bridge] configured repos: %d found at %s",
                len(configured),
                ",".join(str(p) for p in configured) if configured else "(empty)",
            )

            total_synced = 0
            total_errors = 0
            total_skipped = 0
            total_plans_ticked = 0

            for repo_path in configured:
                owner_name = _repo_owner_name(repo_path)
                if owner_name is None:
                    logger.warning(
                        "[bridge] repo %s skipped: could not resolve owner/name from git remote",
                        repo_path,
                    )
                    continue
                resolved_owner: str = owner_name
                # Sync the bridge's OWN checkout (#286) — never the shared one
                # VK writes from worktrees — so an out-of-band ref move can't
                # desync it. discover_plans then reads from this checkout via
                # FR_REPOS_DIR.
                name = resolved_owner.split("/", 1)[1] if "/" in resolved_owner else resolved_owner
                bridge_path = _ensure_bridge_checkout(repo_path, name)
                if bridge_path is None:
                    logger.warning(
                        "[bridge] repo %s skipped: could not establish bridge-owned checkout",
                        repo_path,
                    )
                    continue
                if _pull_managed_repo(bridge_path):
                    _metrics.push_repo_desync_total(repo=resolved_owner)
                prev_repos_dir = os.environ.get("FR_REPOS_DIR")
                os.environ["FR_REPOS_DIR"] = str(bridge_path.parent)
                try:

                    def _fetch_plans(r: str = resolved_owner) -> Any:
                        return discover_plans(r, gh)

                    discovered = _gh_rate_limit_guard(_fetch_plans)
                    if discovered is None:
                        # _gh_rate_limit_guard already logged the reason
                        continue
                    logger.info(
                        "[bridge] %s: %d discoverable plan(s)%s",
                        resolved_owner,
                        len(discovered),
                        ": " + ", ".join(p.dir.name for p in discovered) if discovered else "",
                    )
                    for plan in discovered:
                        plan_slug = plan.dir.name
                        seen_plans_after.add(plan_slug)
                        try:
                            result = _tick(plan, gh, runner, metrics=_metrics)
                            total_plans_ticked += 1
                            total_synced += result.synced
                            total_errors += result.errors
                            total_skipped += result.skipped
                            logger.info(
                                "[bridge]   %s: synced=%d errors=%d skipped=%d",
                                plan_slug,
                                result.synced,
                                result.errors,
                                result.skipped,
                            )
                        except Exception as e:  # noqa: BLE001 — I9 boundary
                            total_errors += 1
                            logger.exception("bridge: plan %s tick raised; continuing", plan_slug)
                            _metrics.push_failure_total(reason=f"plan_error:{plan_slug}:{e}")
                finally:
                    if prev_repos_dir is None:
                        os.environ.pop("FR_REPOS_DIR", None)
                    else:
                        os.environ["FR_REPOS_DIR"] = prev_repos_dir

            for missing in sorted(seen_plans_before - seen_plans_after):
                logger.warning(
                    "plan %s no longer on disk; cards left intact for manual review",
                    missing,
                )
            _store_seen_plans(seen_plans_after)

            logger.info(
                "[bridge] summary: %d plan(s) ticked, %d synced, %d errors, %d skipped",
                total_plans_ticked,
                total_synced,
                total_errors,
                total_skipped,
            )

            # PR state sweep — observations are wired in Phase 6.
            # The Protocol surfaces in pr_state / workspaces use the
            # FakeMcpClient parameter names (`card_id`, `ws_id`); the
            # real client uses `issue_id` / `workspace_id`. Both bind
            # by position at the call sites in those modules, so the
            # cast is the cheapest fix.
            try:
                _pr_state_tick(cast(Any, mcp), {}, project_id=project_id)
            except Exception as e:  # noqa: BLE001
                logger.exception("bridge: pr_state tick raised: %s", e)
                _metrics.push_failure_total(reason="pr_state_error")

            try:
                reap_orphans(cast(Any, mcp), project_id=project_id)
            except Exception as e:  # noqa: BLE001
                logger.exception("bridge: reap_orphans raised: %s", e)
                _metrics.push_failure_total(reason="reap_error")

            _metrics.push_heartbeat()
        finally:
            try:
                mcp.close()
            except Exception:  # noqa: BLE001
                pass
        logger.info("fr_dispatch: tick complete")
        return 0
    finally:
        try:
            lock_fh.close()
        except Exception:  # noqa: BLE001
            pass
