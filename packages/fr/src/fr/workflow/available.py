"""Which workflow shapes a repo offers (spec 2026-11-28-alacarte-settings R2).

`workflows.disabled` in the repo's settings withdraws a shape. `refuse_disabled` is the
one check, called where a run is BOUND to a shape: `fr run start`, a brainstorm record's
`shape:` rebind and `fr run adopt` (the adopt `fr migrate artifacts` performs included).
`advance`, `resolve` and `reshape` never call it, so a run already started on a shape
later disabled keeps going.
"""

from __future__ import annotations

from pathlib import Path

from fr.workflow.model import WorkflowError


def disabled_shapes(repo_root: Path) -> list[str]:
    """`workflows.disabled` as the effective settings say (the tracking space's under
    stealth). An unreadable settings file is a `WorkflowError`: the check fails closed."""
    from fr.settings import SettingsError, load_settings

    try:
        return list(load_settings(repo_root).settings.workflows.disabled)
    except SettingsError as e:
        raise WorkflowError(f"cannot read workflows.disabled: {e}") from e


def refuse_disabled(name: str, repo_root: Path) -> None:
    """Raise `WorkflowError` when *name* is disabled by the repo's settings, naming the
    setting and the shapes still available; return None otherwise."""
    from fr.workflow.resolve import discover_names

    disabled = disabled_shapes(repo_root)
    if name not in disabled:
        return
    names = sorted(n for n in discover_names(repo_root) if n not in disabled)
    raise WorkflowError(
        f"workflow {name} is disabled by this repo's settings (workflows.disabled); "
        f"available: {', '.join(names) or '(none)'}"
    )
