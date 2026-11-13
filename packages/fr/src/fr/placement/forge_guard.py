"""The stealth forge guard (spec 2026-11-04-repo-feature-settings R24 "what reaches the
target"; review p4-r5).

Under stealth the target's forge receives the code and one minimal draft PR, nothing
else. The per-command refusals name the command; this guard is the layer under them, at
the forge-client factories (`fr.hostclient.client_for_backend`, `client_for`) and the
`fr.gh` write helpers, so a command nobody taught about stealth still cannot write an
issue, a label or a comment there. The one write it lets through is `create_pr`, whose
caller (`fr pr create`) already holds it to one draft with a minimal body.

Stealth is read from the checkout the client is built for and from the process's working
directory: a client built from a URL has no checkout, and the workspace an fr command
runs in is what chose stealth.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, TypeVar, cast

from fr.settings import SettingsError

WRITE_METHODS: Final = frozenset(
    {
        "close_issue",
        "close_pr",
        "comment_issue",
        "comment_pr",
        "create_issue",
        "create_pr",
        "delete_branch",
        "dispatch_workflow",
        "edit_issue",
        "edit_issue_body",
        "edit_issue_comment",
        "edit_issue_labels",
        "edit_issue_state",
        "edit_pr",
        "edit_pr_labels",
        "ensure_labels",
        "pr_create",
        "pr_dequeue",
        "pr_enqueue",
        "pr_merge",
        "pr_ready",
    }
)
"""Every forge-client method that writes (`fr.ghclient.GhClient` and its adapters)."""
ALLOWED_UNDER_STEALTH: Final = frozenset({"create_pr"})
"""The one draft PR (R24)."""


class StealthForgeWriteError(SettingsError):
    """A forge write refused under stealth; a `SettingsError`, so the CLI exits 2."""


def _stealth_at(start: Path) -> bool:
    """Is *start* inside a checkout whose `.fr-isolation` marker records stealth?"""
    from fr.artifacts.paths import STEALTH, outside_repo

    here = Path(start).resolve()
    for root in (here, *here.parents):
        if (root / ".fr-isolation").is_file():
            try:
                return outside_repo(root) == STEALTH
            except SettingsError:
                return True  # a marker fr cannot read is not proof the target may be written
        if (root / ".git").exists():
            return False
    return False


def in_stealth(repo_root: Path | None = None) -> bool:
    """*repo_root* (when given) or the working directory is a stealth workspace."""
    if repo_root is not None and _stealth_at(Path(repo_root)):
        return True
    try:
        return _stealth_at(Path.cwd())
    except OSError:
        return False


def refusal(what: str) -> StealthForgeWriteError:
    return StealthForgeWriteError(
        f"placement stealth: refusing the forge write {what}: the target's forge receives "
        "only the code and one minimal draft PR (R24). Nothing was written"
    )


def refuse_in_stealth(what: str) -> None:
    """For the `fr.gh` write helpers: refuse under stealth, before the call."""
    if in_stealth():
        raise refusal(what)


class StealthForgeGuard:
    """A forge client whose write methods (bar `create_pr`) refuse; reads pass through."""

    def __init__(self, inner: Any) -> None:
        object.__setattr__(self, "_inner", inner)

    def __getattribute__(self, name: str) -> Any:
        # Every lookup goes to the adapter, so a marker base (below) never shadows one of
        # its methods with the base's own stub.
        if name.startswith("__") and name.endswith("__"):
            return object.__getattribute__(self, name)
        if name in WRITE_METHODS and name not in ALLOWED_UNDER_STEALTH:

            def refused(*_a: Any, **_kw: Any) -> Any:
                raise refusal(f"`{name}`")

            return refused
        return getattr(object.__getattribute__(self, "_inner"), name)


C = TypeVar("C")

_GUARD_TYPES: dict[tuple[type, ...], type] = {}


def guard(client: C, repo_root: Path | None = None) -> C:
    """*client* as is, or wrapped in the guard when stealth applies. The wrapper keeps the
    adapter's marker bases (`UnsupportedBatchOps`), which callers test with isinstance."""
    if isinstance(client, StealthForgeGuard) or not in_stealth(repo_root):
        return client
    from fr.ghclient import UnsupportedBatchOps

    markers: tuple[type, ...] = (
        (UnsupportedBatchOps,) if isinstance(client, UnsupportedBatchOps) else ()
    )
    cls = _GUARD_TYPES.get(markers)
    if cls is None:
        cls = type("StealthForgeGuard", (StealthForgeGuard, *markers), {})
        _GUARD_TYPES[markers] = cls
    return cast(C, cls(client))


def guarded(what: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a module-level forge write helper with `refuse_in_stealth`."""
    import functools

    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def inner(*a: Any, **kw: Any) -> Any:
            refuse_in_stealth(what)
            return fn(*a, **kw)

        return inner

    return wrap
