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
    from fr.config.space import repo_config_space, write_settings

    write_settings(repo_config_space(resolve_repo_root()), render_init(), message="")
    typer.echo(f"wrote {path}")


def init_quiet(root: Path) -> str:
    """Create the quiet switch (`render_init("quiet")`): the orphan `fr-config` branch
    holding `.fr/settings.yaml`, then the orphan `fr` branch holding the same bytes as its
    root `settings.yaml` (spec 2026-11-19-event-driven-a-la-carte R5, R6), each made with
    plumbing, so the checkout is never touched, and pushed with a plain push. Refuses with
    no origin, or when origin or this clone already has either branch."""
    from fr.config.space import quiet_config_space, write_settings
    from fr.git import GitUnavailableError, git_answer
    from fr.git_policy.templates import fr_message
    from fr.placement.quiet import (
        CONFIG_BRANCH,
        CONFIG_REF,
        QUIET_BRANCH,
        QUIET_REF,
        unreachable,
    )
    from fr.settings.render import QUIET_LIMITATION, render_init

    try:
        if git_answer(root, "config", "--get", "remote.origin.url").returncode != 0:
            raise SettingsError(
                "fr settings init --quiet: this repository has no `origin`; quiet keeps the "
                "`fr` and `fr-config` branches on origin, so add one first"
            )
        probe = git_answer(root, "ls-remote", "--exit-code", "origin", QUIET_REF, CONFIG_REF)
        if probe.returncode == 0 and _origin_has_only_old_switch(root, probe.stdout):
            return _create_from_old_switch(root)
        for ref, name in ((QUIET_REF, QUIET_BRANCH), (CONFIG_REF, CONFIG_BRANCH)):
            if git_answer(root, "rev-parse", "--verify", "--quiet", ref).returncode == 0:
                # p3-r9: the root commit made here is unrelated to any existing local
                # branch, which a worktree would otherwise adopt and push as a second root.
                raise SettingsError(
                    f"fr settings init --quiet: this clone already has a local `{name}` "
                    "branch, which would not be an ancestor or a descendant of the one fr "
                    f"is about to create. Rename or delete it (`git branch -m {name} "
                    f"{name}-old`) and retry"
                )
    except GitUnavailableError as e:
        raise SettingsError(f"fr settings init --quiet: {e}") from e
    if probe.returncode == 0:
        found = " and ".join(
            f"`{line.split(chr(9), 1)[1].removeprefix('refs/heads/')}`"
            for line in probe.stdout.splitlines()
            if chr(9) in line
        )
        raise SettingsError(
            f"fr settings init --quiet: origin already has {found}; fr never overwrites "
            f"the switch (edit `.fr/settings.yaml` on `{CONFIG_BRANCH}` instead)"
        )
    if probe.returncode != 2:
        raise unreachable(probe.stderr.strip() or "git ls-remote failed", None)
    # fr's own subject goes through the commit templates (R14), like every fr commit.
    message = fr_message(root, "chore(fr): switch this repo to the quiet placement")
    write_settings(quiet_config_space(root), render_init("quiet"), message=message)
    commit = git_answer(root, "rev-parse", "--short=12", CONFIG_REF).stdout.strip()
    return (
        f"pushed the `{CONFIG_BRANCH}` branch ({commit}) and the `{QUIET_BRANCH}` branch to "
        "origin: this repo is now quiet.\n"
        f"{QUIET_LIMITATION}\n"
        f"The policy keys are read from `{CONFIG_BRANCH}`: protect it as you protect the "
        "default branch."
    )


def _origin_has_only_old_switch(root: Path, listing: str) -> bool:
    """*listing* (`ls-remote origin fr fr-config`) names `fr` alone, and that branch, once
    fetched, is a quiet switch: an existing quiet repo whose configuration space is not
    created yet (plan decision p2-create-at-init-and-migration)."""
    from fr.placement.quiet import FETCH_REFSPEC, QUIET_REF, _read_legacy

    heads = {line.split("\t", 1)[1].strip() for line in listing.splitlines() if "\t" in line}
    if heads != {QUIET_REF}:
        return False
    from fr.git import git_answer

    fetched = git_answer(root, "fetch", "--quiet", "--no-tags", "origin", FETCH_REFSPEC)
    if fetched.returncode != 0:
        raise SettingsError(
            f"fr settings init --quiet: cannot fetch origin/fr: {fetched.stderr.strip()}"
        )
    return _read_legacy(root) is not None


def _create_from_old_switch(root: Path) -> str:
    """Create `fr-config` holding the old switch's bytes (`quiet.ensure_config_branch`)."""
    from fr.placement.quiet import CONFIG_BRANCH, QUIET_BRANCH, ensure_config_branch

    if not ensure_config_branch(root):
        raise SettingsError(
            f"fr settings init --quiet: origin already has `{CONFIG_BRANCH}`; fr never "
            f"overwrites the switch (edit `.fr/settings.yaml` on `{CONFIG_BRANCH}` instead)"
        )
    return (
        f"created the `{CONFIG_BRANCH}` branch on origin holding the quiet switch from "
        f"origin/{QUIET_BRANCH}:settings.yaml (byte for byte): this repo's configuration "
        f"space now exists. The old file stays, in step, for older fr (R6)."
    )


def init_stealth(root: Path, text: str) -> str:
    """Write the target's settings (from `render_init("stealth")`): `<target-dir>/.fr/
    settings.yaml` on the tracking repo's `<branch>-config`, then the same bytes as
    `<target-dir>/settings.yaml` on `<branch>` (R5, R6, R24), each pushed
    compare-and-swap. Refuses an unreachable tracking repo or a missing branch before
    writing, and a file that is already at either path."""
    from fr.config.space import stealth_config_space, write_settings
    from fr.git_policy.templates import fr_message
    from fr.placement import stealth
    from fr.settings.render import render_init

    ref = stealth.parse_ref(text)
    stealth.check_reachable(ref, root)
    # R24 privacy, before the tracking worktree is cloned or anything is pushed (the
    # push seam holds the same guard again).
    target_remote = stealth.origin_url(root)
    stealth.check_privacy(ref, target_remote, target_root=root)
    target = stealth.target_dir(root)
    stealth.ensure_worktree(root, ref)
    cref = stealth.config_ref(ref)
    if stealth._remote_has(cref, root):
        stealth.ensure_worktree(root, cref)
    new, old = stealth.target_settings_texts(root, ref, target)
    if new is not None:
        raise SettingsError(
            f"fr settings init --stealth: {cref.text} already holds {target}/"
            f"{stealth.TARGET_SETTINGS}; fr never overwrites it (edit it there instead)"
        )
    message = fr_message(root, f"chore(fr): stealth settings for {target}")
    space = stealth_config_space(root, ref.text, target)
    if old is not None:
        # An existing target (plan decision p2-create-at-init-and-migration): its space
        # is created here, holding the old file's bytes; the old file stays in step (R6).
        url = write_settings(space, old, message=message)
        if url is not None:
            return f"opened {url}: it adds {target}/{stealth.TARGET_SETTINGS} to {cref.text}"
        return (
            f"moved {target}/{stealth.LEGACY_TARGET_SETTINGS} on {ref.text} to {target}/"
            f"{stealth.TARGET_SETTINGS} on {cref.text} (byte for byte); the old file stays, "
            "in step, for older fr (R6)"
        )
    url = write_settings(space, render_init("stealth"), message=message)
    if url is not None:
        return f"opened {url}: it adds {target}/{stealth.TARGET_SETTINGS} to {cref.text}"
    return (
        f"pushed {target}/{stealth.TARGET_SETTINGS} to {cref.text} and "
        f"{target}/{stealth.LEGACY_TARGET_SETTINGS} to {ref.text}: start a run with "
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
    `paths` everywhere). `$FR_REPO_ROOT` wins, as in `resolve_repo_root`."""
    from fr.git import GitUnavailableError, git_answer

    override = os.environ.get("FR_REPO_ROOT")
    if override:
        return Path(override).resolve()
    try:
        done = git_answer(Path.cwd(), "rev-parse", "--show-toplevel")
    except GitUnavailableError:
        return None
    top = done.stdout.strip()
    return Path(top).resolve() if done.returncode == 0 and top else None


def paths_answers(toplevel: Path | None, *, create: bool = True) -> dict[str, str]:
    """The resolver's answers as `FR_*` variables: the placement, its root, the feature,
    then one per `fr.artifacts.paths.KIND_DIRS` entry. `FR_PLACEMENT=none` alone
    outside a git repo. Raises `SettingsError` for a placement this fr cannot serve."""
    from fr.artifacts.paths import (
        CONFIG_KINDS,
        KIND_DIRS,
        config_kind_path,
        kind_dir,
        shell_name,
        space_for,
    )

    if toplevel is None:
        return {"FR_PLACEMENT": "none"}
    space = space_for(toplevel, create=create)
    out = {
        "FR_PLACEMENT": space.placement,
        "FR_ARTIFACT_ROOT": str(space.root),
        "FR_FEATURE": space.feature or "",
    }
    # The configuration kinds name the configuration space under every placement (S1 R9).
    out.update(
        {
            shell_name(kind): str(
                config_kind_path(toplevel, kind) if kind in CONFIG_KINDS else kind_dir(kind, space)
            )
            for kind in KIND_DIRS
        }
    )
    return out


PATHS_REFUSAL_PREFIX = "fr settings paths: refused: "
"""The first bytes of `paths`' stderr when fr refuses the placement (exit 2). A caller that
falls back to the `repo` literals on any other failure (`validate-plans.sh`, review
pr1431-r7) keys on it: exit 2 alone is also a usage error or a binary-identity refusal."""


@settings_app.command("paths")
def paths_cmd(
    shell: bool = typer.Option(False, "--shell", help="Print shell-quoted FR_*=… lines."),
    as_json: bool = typer.Option(False, "--json", help="Print the same keys as one object."),
    no_create: bool = typer.Option(
        False,
        "--no-create",
        help="Compute the paths only: never create the quiet fr branch or worktree, "
        "nor ask a stealth tracking repo (what hooks and plugins call).",
    ),
) -> None:
    """Print the artifact path resolver's answers, for hooks and plugins (R1, R3)."""
    if shell == as_json:
        typer.echo("pass exactly one of --shell or --json", err=True)
        raise typer.Exit(2)
    try:
        answers = paths_answers(_toplevel(), create=not no_create)
    except SettingsError as e:
        typer.echo(f"{PATHS_REFUSAL_PREFIX}{e}", err=True)
        raise typer.Exit(2) from e
    if as_json:
        typer.echo(json.dumps(answers))
        return
    for key, value in answers.items():
        typer.echo(f"{key}={shlex.quote(value)}")


def _sync_placement(root: Path) -> str | None:
    """The placement `sync` works under. The usual reader refuses while the two copies
    differ, which is exactly the state `sync` exists for: a stealth marker answers first,
    then quiet whenever origin has both switches (whatever they say)."""
    from fr.artifacts.paths import outside_repo
    from fr.placement import quiet, stealth

    if stealth.marker_tracking(root) is not None:
        return "stealth"
    new, old = quiet.switch_texts(root)
    if new is not None and old is not None:
        return "quiet"
    return outside_repo(root)


def _protected_tip(root: Path, placement: str) -> str:
    """`--yes` without `--expect` (plan discovery p2-phase3-sync-needs-protection): the
    configuration branch's tip, when the forge's rules for it require a pull request with an
    approving review a later push cannot keep and block force-pushes and deletion (what fr
    checked; it cannot see
    bypass actors, `protection.BYPASS_LIMIT`); otherwise the refusal naming the preview (spec
    R6, R7)."""
    from fr.config.protection import BYPASS_LIMIT, ProtectionReadError, require_protected
    from fr.config.space import quiet_config_space, stealth_config_space
    from fr.placement import quiet, stealth

    if placement == "quiet":
        space = quiet_config_space(root)
    else:
        found = stealth.marker_tracking(root)
        assert found is not None
        ref, target = found
        space = stealth_config_space(root, ref.text, target)
    try:
        require_protected(space, None, "bring the old settings copy in step without `--expect`")
    except ProtectionReadError:
        raise
    except SettingsError as e:
        raise SettingsError(
            f"{e}. Run `{quiet.SYNC_COMMAND}` to preview the change, then "
            f"`{quiet.SYNC_COMMAND} --yes --expect <tip>`"
        ) from e
    if placement == "quiet":
        tip = quiet.sync_plan(root).tip
    else:
        tip = stealth.sync_plan_target(root, ref, target).tip
    typer.echo(
        "the forge's rules for the configuration branch require an approved pull request and "
        f"block force-pushes and deletion ({BYPASS_LIMIT}): writing from its tip {tip}"
    )
    return str(tip)


@settings_app.command("sync")
def sync_cmd(
    yes: bool = typer.Option(
        False, "--yes", help="Write the old settings copy (otherwise only preview)."
    ),
    expect: str | None = typer.Option(
        None, "--expect", help="With --yes: the configuration branch tip the preview showed."
    ),
) -> None:
    """Bring the old settings copy in step after a reviewed change (spec R6)."""
    root = resolve_repo_root()
    try:
        placement = _sync_placement(root)
        if yes and expect is None and placement in ("quiet", "stealth"):
            expect = _protected_tip(root, placement)
        if placement == "quiet":
            from fr.placement import quiet

            plan = quiet.sync_legacy(root, expect=expect) if yes else quiet.sync_plan(root)
        elif placement == "stealth":
            from fr.placement import stealth

            found = stealth.marker_tracking(root)
            assert found is not None
            ref, target = found
            plan = (
                stealth.sync_legacy_target(root, ref, target, expect=expect)
                if yes
                else stealth.sync_plan_target(root, ref, target)
            )
        else:
            typer.echo("placement repo: there is no old settings copy to keep in step")
            return
    except SettingsError as e:
        raise _refuse(e) from e
    typer.echo(f"configuration branch: {plan.new_at}")
    typer.echo(f"old copy:             {plan.old_at}")
    if plan.tip:
        typer.echo(f"tip:                  {plan.tip} (settings blob {plan.blob or 'none'})")
    if plan.state == "in-step":
        typer.echo("in step: nothing to do")
        return
    if plan.state == "none":
        typer.echo("one of the two is absent: nothing to sync (fr reads the one there, R13)")
        return
    if plan.state == "mismatch":  # only the preview gets here; --yes refuses above
        typer.echo(
            "neither matches the other at any earlier version: edit them by hand to the same "
            "bytes (the configuration branch through a pull request)",
            err=True,
        )
        raise typer.Exit(2)
    typer.echo(
        "the configuration branch moved since the old copy's version (first parent, newest "
        "first; the label is information, not a review: check the shas):"
    )
    for sha, second, subject, merged in plan.commits:
        how = (
            "merge of fr-config-change/ (its tip is the second parent)"
            if merged
            else "NOT a merge of a fr-config-change/* branch"
            if second
            else "NOT a merge (a direct commit or a fast-forward)"
        )
        typer.echo(f"  {sha}  second parent {second or 'none'}  {how}  {subject}")
    if yes:
        typer.echo("wrote the old copy: the two are in step")
    else:
        typer.echo(
            "review the commits above, then run "
            f"`fr settings sync --yes --expect {plan.tip}` to write the old copy"
        )


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
