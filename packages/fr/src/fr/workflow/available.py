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

_WHERE: dict[str, str] = {
    "repo": "`.fr/settings.yaml` on the default branch",
    "quiet": "`.fr/settings.yaml` on the `fr-config` branch",
    "stealth": "the tracking repo's settings file (`<target-dir>/.fr/settings.yaml` on its "
    "`<branch>-config` branch), not the target's",
}
"""Where `workflows.disabled` is read from, per placement (l-errors-r3)."""


def _disabled_and_placement(repo_root: Path) -> tuple[list[str], str]:
    """`workflows.disabled` as the effective settings say (the tracking space's under
    stealth), and the placement it was read under. An unreadable settings file is a
    `WorkflowError`: the check fails closed."""
    from fr.settings import SettingsError, load_settings

    try:
        settings = load_settings(repo_root).settings
    except SettingsError as e:
        raise WorkflowError(f"cannot read workflows.disabled: {e}") from e
    return list(settings.workflows.disabled), settings.placement


def refuse_disabled(name: str, repo_root: Path) -> None:
    """Raise `WorkflowError` when *name* is listed in `workflows.disabled`, naming the
    setting, the file it lives in, the shapes still available and how to choose one;
    return None otherwise."""
    from fr.workflow.resolve import discover_names

    disabled, placement = _disabled_and_placement(repo_root)
    if name not in disabled:
        return
    names = sorted(n for n in discover_names(repo_root) if n not in disabled)
    where = _WHERE.get(placement, "the repo's settings file")
    fix = (
        f"; choose one with `--workflow <shape>` (`fr run adopt <plan> --workflow "
        f"{names[0]}`, `fr run start {names[0]}`)"
        if names
        else "; enable one in that file"
    )
    raise WorkflowError(
        f"workflow {name} is disabled by workflows.disabled in {where}; "
        f"available: {', '.join(names) or '(none)'}{fix}"
    )
