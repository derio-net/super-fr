"""`fr validate artifacts` CLI — the structural gate (spec §3.F)."""

from __future__ import annotations

import typer

from fr.commands.common import require_migrated_layout, resolve_repo_root

validate_app = typer.Typer(
    help="Structural validation of generated artifacts.", no_args_is_help=True
)


@validate_app.command("artifacts")
def artifacts_cmd(
    kind: str | None = typer.Option(
        None,
        "--kind",
        help="Validate only this artifact kind (plan, journal, run, matrix, spec).",
    ),
) -> None:
    """Structurally validate every live artifact against the version this fr writes.

    Checks each artifact's stamp (unreadable, stale, or newer-than-this-fr all
    fail) and then its shape: required fields, cross-references that resolve,
    and — for specs — the duplicated section blocks and mid-sentence headings a
    bad splice produces. Archived artifacts under `implemented/` are never
    checked; they record what shipped.

    Exit 0 when everything is valid, 1 when any artifact is not, 2 for an
    unknown `--kind`. Read-only: nothing here writes.
    """
    from fr.artifacts.validate import UnknownArtifactKindError, validate_repo

    repo_root = resolve_repo_root()
    require_migrated_layout(repo_root)
    try:
        report = validate_repo(repo_root, kind_name=kind)
    except UnknownArtifactKindError as e:
        typer.echo(f"validation error: {e}", err=True)
        raise typer.Exit(2) from e

    scope = f" of kind `{kind}`" if kind else ""
    if report.ok:
        # Plain echo, not rich: rich soft-wraps and splits long paths.
        typer.echo(f"{report.checked} artifact(s){scope} checked — all structurally valid.")
        return

    for issue in report.issues:
        typer.echo(f"  {issue.rendered(repo_root)}", err=True)
    typer.echo(
        f"\n{len(report.issues)} problem(s) in {len({i.path for i in report.issues})} of "
        f"{report.checked} artifact(s){scope}.",
        err=True,
    )
    raise typer.Exit(1)
