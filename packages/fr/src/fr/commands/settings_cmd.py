"""`fr settings` — the repo's feature settings (spec 2026-11-04-repo-feature-settings, R3).

Read-only for the artifact-migration gate (`fr.artifacts.trigger.READ_ONLY_COMMANDS`):
`init` writes `.fr/settings.yaml`, which is not a registered artifact, and never commits it;
`init --quiet` writes a remote branch (the quiet switch), which is not an artifact either.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel

from fr.commands.common import resolve_repo_root
from fr.settings import SettingsError, load_settings
from fr.settings.check import check_settings
from fr.settings.load import SETTINGS_PATH

settings_app = typer.Typer(
    help="Per-repo feature settings: init, show, paths, check.",
    no_args_is_help=True,
)


def _flatten(model: BaseModel, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, field in type(model).model_fields.items():
        value = getattr(model, name)
        key = f"{prefix}{field.alias or name}"
        if isinstance(value, BaseModel):
            out.update(_flatten(value, f"{key}."))
        else:
            out[key] = value
    return out


def _refuse(error: Exception) -> typer.Exit:
    typer.echo(str(error), err=True)
    return typer.Exit(2)


@settings_app.command("init")
def init_cmd(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing file."),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Switch the repo to the quiet placement: create the orphan `fr` branch with "
        "its root settings.yaml and push it to origin (plain push; refused if it exists).",
    ),
    stealth: str | None = typer.Option(
        None,
        "--stealth",
        help="Write this target's settings.yaml on the stealth tracking branch "
        "<repo>@<branch> and push it compare-and-swap (refused if it exists).",
    ),
) -> None:
    """Write `.fr/settings.yaml` with every key commented out at its default.

    Writes only; commit it (and land it on the default branch) yourself. With
    `--quiet`, create and push the `fr` branch instead (R3, R23).
    """
    from fr.settings.render import render_init

    if stealth is not None:
        if force or quiet:
            typer.echo(
                "--stealth takes neither --force (fr never overwrites a target's file on the "
                "tracking branch) nor --quiet",
                err=True,
            )
            raise typer.Exit(2)
        try:
            typer.echo(init_stealth(resolve_repo_root(), stealth))
        except SettingsError as e:
            raise _refuse(e) from e
        return
    from fr.placement.stealth import refuse_repo_config

    try:  # review p4-r3: from a stealth workspace, neither writes into the target
        refuse_repo_config(
            resolve_repo_root(),
            "fr settings init --quiet" if quiet else "fr settings init",
            "an `fr` branch on its origin" if quiet else SETTINGS_PATH,
        )
    except SettingsError as e:
        raise _refuse(e) from e
    if quiet:
        if force:
            typer.echo(
                "--force is not offered with --quiet: the `fr` branch is append-only and fr "
                "never overwrites it",
                err=True,
            )
            raise typer.Exit(2)
        try:
            pushed = init_quiet(resolve_repo_root())
        except SettingsError as e:
            raise _refuse(e) from e
        typer.echo(pushed)
        return
    path = resolve_repo_root() / SETTINGS_PATH
    if path.exists() and not force:
        typer.echo(f"{SETTINGS_PATH} already exists; pass --force to overwrite it", err=True)
        raise typer.Exit(2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_init())
    typer.echo(f"wrote {path}")


def init_quiet(root: Path) -> str:
    """Create the orphan `fr` branch (one commit, root `settings.yaml` from
    `render_init("quiet")`) with git plumbing, so the checkout is never touched, and push
    it with a plain push. Refuses with no origin, or when origin already has `fr`."""
    from fr.git import GitUnavailableError, git_answer
    from fr.placement.quiet import FETCH_REFSPEC, QUIET_REF, unreachable
    from fr.settings.render import QUIET_LIMITATION, render_init

    def git(*args: str, stdin: str | None = None) -> str:
        try:
            if stdin is None:
                done = git_answer(root, *args)
            else:
                import subprocess

                from fr.git import git_argv

                done = subprocess.run(
                    git_argv(root, *args), input=stdin, capture_output=True, text=True
                )
        except GitUnavailableError as e:
            raise SettingsError(f"fr settings init --quiet: {e}") from e
        if done.returncode != 0:
            raise SettingsError(
                f"fr settings init --quiet: `git {' '.join(args)}` failed: {done.stderr.strip()}"
            )
        return done.stdout

    if git_answer(root, "config", "--get", "remote.origin.url").returncode != 0:
        raise SettingsError(
            "fr settings init --quiet: this repository has no `origin`; quiet keeps the `fr` "
            "branch on origin, so add one first"
        )
    if git_answer(root, "rev-parse", "--verify", "--quiet", QUIET_REF).returncode == 0:
        # p3-r9: the root commit made here is unrelated to any existing local `fr`, which
        # the fr worktree would otherwise adopt and push as a second root.
        raise SettingsError(
            "fr settings init --quiet: this clone already has a local `fr` branch, which "
            "would not be an ancestor or a descendant of the switch fr is about to create. "
            "Rename or delete it (`git branch -m fr fr-old`) and retry"
        )
    probe = git_answer(root, "ls-remote", "--exit-code", "origin", QUIET_REF)
    if probe.returncode == 0:
        raise SettingsError(
            "fr settings init --quiet: origin already has an `fr` branch; fr never overwrites "
            "it (edit its settings.yaml there instead)"
        )
    if probe.returncode != 2:
        raise unreachable(probe.stderr.strip() or "git ls-remote failed", None)
    blob = git("hash-object", "-w", "--stdin", stdin=render_init("quiet")).strip()
    tree = git("mktree", stdin=f"100644 blob {blob}\tsettings.yaml\n").strip()
    from fr.git_policy.templates import fr_message

    # fr's own subject goes through the commit templates (R14), like every fr commit.
    message = fr_message(root, "chore(fr): switch this repo to the quiet placement")
    commit = git("commit-tree", tree, "-F", "-", stdin=message).strip()
    git("push", "origin", f"{commit}:{QUIET_REF}")
    git("fetch", "--no-tags", "origin", FETCH_REFSPEC)
    return (
        f"pushed the `fr` branch ({commit[:12]}) to origin: this repo is now quiet.\n"
        f"{QUIET_LIMITATION}\n"
        "The policy keys are read from `fr`: protect it as you protect the default branch."
    )


def init_stealth(root: Path, text: str) -> str:
    """Write `<target-dir>/settings.yaml` (from `render_init("stealth")`) on the tracking
    branch and push it compare-and-swap (R3, R24). Refuses an unreachable tracking repo
    or a missing branch before writing, and a file that is already there."""
    from fr.git_policy.templates import fr_message
    from fr.placement import stealth
    from fr.settings.render import render_init

    ref = stealth.parse_ref(text)
    stealth.check_reachable(ref, root)
    # R24 privacy, before the tracking worktree is cloned or anything is pushed (the
    # push seam holds the same guard again).
    target_remote = stealth.origin_url(root)
    stealth.check_privacy(ref, target_remote)
    target = stealth.target_dir(root)
    wt = stealth.ensure_worktree(root, ref)
    path = wt / target / stealth.TARGET_SETTINGS
    if path.exists():
        raise SettingsError(
            f"fr settings init --stealth: {ref.text} already holds {target}/"
            f"{stealth.TARGET_SETTINGS}; fr never overwrites it (edit it there instead)"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_init("stealth"))
    message = fr_message(root, f"chore(fr): stealth settings for {target}")
    try:
        outcome = stealth.commit_and_push(
            ref, wt, [path], message, stealth.plain_commit, target_remote=target_remote
        )
    except SettingsError:
        path.unlink(missing_ok=True)
        raise
    if not outcome.committed:
        path.unlink(missing_ok=True)
        raise SettingsError(f"fr settings init --stealth: {outcome.reason}")
    return (
        f"pushed {target}/{stealth.TARGET_SETTINGS} to {ref.text}: start a run with "
        f"`fr isolation up --stealth {ref.text}` (stealth is chosen per run)"
    )


@settings_app.command("show")
def show_cmd(
    as_json: bool = typer.Option(False, "--json", help="Print {key: {value, source}}."),
) -> None:
    """Print the effective settings and each key's source."""
    try:
        eff = load_settings(resolve_repo_root())
    except SettingsError as e:
        raise _refuse(e) from e
    values = _flatten(eff.settings)
    if as_json:
        typer.echo(
            json.dumps({k: {"value": v, "source": eff.sources[k]} for k, v in values.items()})
        )
        return
    width = max(len(k) for k in values)
    typer.echo(f"{'key'.ljust(width)}  {'value'.ljust(8)}  source")
    for key, value in values.items():
        typer.echo(f"{key.ljust(width)}  {str(value).ljust(8)}  {eff.sources[key]}")
    typer.echo(f"policy source: {eff.source} ({eff.ref or 'none'})")
    typer.echo(f"({eff.ref_note})")
    if eff.pending_edit:
        typer.echo(f"note: {eff.pending_edit}")


def _toplevel() -> Path | None:
    """The repo the paths are asked for, or None outside a git repo (hooks call
    `paths` everywhere). `$VK_REPO_ROOT` wins, as in `resolve_repo_root`."""
    from fr.git import GitUnavailableError, git_answer

    override = os.environ.get("VK_REPO_ROOT")
    if override:
        return Path(override).resolve()
    try:
        done = git_answer(Path.cwd(), "rev-parse", "--show-toplevel")
    except GitUnavailableError:
        return None
    top = done.stdout.strip()
    return Path(top).resolve() if done.returncode == 0 and top else None


def paths_answers(toplevel: Path | None) -> dict[str, str]:
    """The resolver's answers as `FR_*` variables: the placement, its root, the feature,
    then one per `fr.artifacts.paths.KIND_DIRS` entry. `FR_PLACEMENT=none` alone
    outside a git repo. Raises `SettingsError` for a placement this fr cannot serve."""
    from fr.artifacts.paths import KIND_DIRS, kind_dir, shell_name, space_for

    if toplevel is None:
        return {"FR_PLACEMENT": "none"}
    space = space_for(toplevel)
    out = {
        "FR_PLACEMENT": space.placement,
        "FR_ARTIFACT_ROOT": str(space.root),
        "FR_FEATURE": space.feature or "",
    }
    out.update({shell_name(kind): str(kind_dir(kind, space)) for kind in KIND_DIRS})
    return out


@settings_app.command("paths")
def paths_cmd(
    shell: bool = typer.Option(False, "--shell", help="Print shell-quoted FR_*=… lines."),
    as_json: bool = typer.Option(False, "--json", help="Print the same keys as one object."),
) -> None:
    """Print the artifact path resolver's answers, for hooks and plugins (R1, R3)."""
    if shell == as_json:
        typer.echo("pass exactly one of --shell or --json", err=True)
        raise typer.Exit(2)
    try:
        answers = paths_answers(_toplevel())
    except SettingsError as e:
        raise _refuse(e) from e
    if as_json:
        typer.echo(json.dumps(answers))
        return
    for key, value in answers.items():
        typer.echo(f"{key}={shlex.quote(value)}")


@settings_app.command("check")
def check_cmd() -> None:
    """Validate the settings: schema, servable placement, coherence."""
    try:
        problems = check_settings(resolve_repo_root())
    except SettingsError as e:
        raise _refuse(e) from e
    if problems:
        for problem in problems:
            typer.echo(f"{problem.id}: {problem.message}", err=True)
        raise typer.Exit(2)
    typer.echo("settings ok")
