"""vk.bridge cron entry point — `python -m vk.bridge`.

One tick: pull every managed repo to head-of-main, walk
`discover_plans` per repo, dispatch eligible phases via
`vk.bridge.tick`, run the PR-state sweep + workspace reaper, push the
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

from vk._mcp_client import VkMcpClient
from vk.bridge import discover_plans
from vk.bridge import metrics as _metrics
from vk.bridge import tick as _tick
from vk.bridge.pr_state import tick as _pr_state_tick
from vk.bridge.workspaces import reap_orphans
from vk.gh import GhError, _classify_error
from vk.real_ghclient import RealGhClient

__all__ = ["main"]

logger = logging.getLogger("vk.bridge")

_DEFAULT_LOCK_PATH = "/var/run/vk-bridge.lock"
_SEEN_PLANS_PATH = Path.home() / ".willikins-agent" / "_seen_plans.json"


def _emit_banner() -> None:
    """First INFO record of every tick — version + UTC timestamp (G5)."""
    vk_ver = _pkg_version("vk")
    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.info(f"[bridge] - v{vk_ver} - {now} - tick")


def _configured_repos() -> list[Path]:
    """Resolve managed repo checkouts from env / convention.

    `VK_BRIDGE_REPOS` is a comma-separated list of absolute paths. When
    unset, the default is the live bridge convention — every directory
    under `~/repos/<name>/` that contains a `.git` entry.
    """
    raw = os.environ.get("VK_BRIDGE_REPOS", "").strip()
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


def _pull_managed_repo(repo_path: Path) -> None:
    """`git fetch && git checkout main && git pull --ff-only` (E4).

    Best-effort — failures log a warning and continue with the stale
    checkout, because a stale dispatch beats no dispatch.
    """
    cmds: tuple[list[str], ...] = (
        ["git", "-C", str(repo_path), "fetch"],
        ["git", "-C", str(repo_path), "checkout", "main"],
        ["git", "-C", str(repo_path), "pull", "--ff-only"],
    )
    for cmd in cmds:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            stderr = getattr(e, "stderr", "") or ""
            logger.warning(
                "bridge: %s failed for %s: %s; continuing with stale checkout",
                " ".join(cmd[3:]),
                repo_path,
                stderr.strip() or e,
            )
            return


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
            lock_path = Path("/tmp/vk-bridge.lock")
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
    parser = argparse.ArgumentParser(prog="vk.bridge")
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
        logger.info("vk.bridge: dry-run complete")
        return 0

    lock_path = os.environ.get("VK_BRIDGE_LOCK_PATH", _DEFAULT_LOCK_PATH)
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

            for repo_path in _configured_repos():
                _pull_managed_repo(repo_path)
                owner_name = _repo_owner_name(repo_path)
                if owner_name is None:
                    continue
                resolved_owner: str = owner_name
                prev_repos_dir = os.environ.get("VK_REPOS_DIR")
                os.environ["VK_REPOS_DIR"] = str(repo_path.parent)
                try:

                    def _fetch_plans(r: str = resolved_owner) -> Any:
                        return discover_plans(r, gh)

                    discovered = _gh_rate_limit_guard(_fetch_plans)
                    if discovered is None:
                        continue
                    for plan in discovered:
                        plan_slug = plan.dir.name
                        seen_plans_after.add(plan_slug)
                        try:
                            _tick(plan, gh, mcp)
                        except Exception as e:  # noqa: BLE001 — I9 boundary
                            logger.exception("bridge: plan %s tick raised; continuing", plan_slug)
                            _metrics.push_failure_total(reason=f"plan_error:{plan_slug}:{e}")
                finally:
                    if prev_repos_dir is None:
                        os.environ.pop("VK_REPOS_DIR", None)
                    else:
                        os.environ["VK_REPOS_DIR"] = prev_repos_dir

            for missing in sorted(seen_plans_before - seen_plans_after):
                logger.warning(
                    "plan %s no longer on disk; cards left intact for manual review",
                    missing,
                )
            _store_seen_plans(seen_plans_after)

            # PR state sweep — observations are wired in Phase 6.
            # The Protocol surfaces in pr_state / workspaces use the
            # FakeMcpClient parameter names (`card_id`, `ws_id`); the
            # real client uses `issue_id` / `workspace_id`. Both bind
            # by position at the call sites in those modules, so the
            # cast is the cheapest fix.
            try:
                _pr_state_tick(cast(Any, mcp), {})
            except Exception as e:  # noqa: BLE001
                logger.exception("bridge: pr_state tick raised: %s", e)
                _metrics.push_failure_total(reason="pr_state_error")

            try:
                reap_orphans(cast(Any, mcp))
            except Exception as e:  # noqa: BLE001
                logger.exception("bridge: reap_orphans raised: %s", e)
                _metrics.push_failure_total(reason="reap_error")

            _metrics.push_heartbeat()
        finally:
            try:
                mcp.close()
            except Exception:  # noqa: BLE001
                pass
        logger.info("vk.bridge: tick complete")
        return 0
    finally:
        try:
            lock_fh.close()
        except Exception:  # noqa: BLE001
            pass
