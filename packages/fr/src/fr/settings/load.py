"""Load a repo's settings from the DEFAULT REF (spec 2026-11-04-repo-feature-settings, R2, R4).

The policy keys are read from the default branch's revision of `.fr/settings.yaml`,
never the working tree: a branch that edits them gets no effect until the edit lands
there, so a branch can never relax its own controls. An edit that has not landed is
reported (`pending_edit`), not applied.

R2's resolution order: (1) a remote WITH tracking refs reads its default (refusing
when none resolves); (2a) no remote reads the local default branch (defaults when there
is none); (2b) a remote never fetched is built-in defaults with a note, never a local
branch; (3) a CI context where none of these found a ref reads HEAD's committed tree,
with one stderr notice.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal

import yaml
from pydantic import BaseModel

from fr.git import GitRefusal, GitUnavailableError, git_answer, remote_default_ref, remote_name
from fr.settings import SettingsError
from fr.settings.model import PLACEMENTS, Settings, parse_settings

SETTINGS_PATH: Final = ".fr/settings.yaml"
SERVABLE_PLACEMENTS: Final = frozenset({"repo", "quiet", "stealth"})
"""The placements this fr can serve."""

Source = Literal["remote", "local", "head", "defaults", "quiet", "stealth"]
"""Where the policy came from: R2 step 1, step 2, the CI exception, nowhere, (quiet) the
`fr` branch's root `settings.yaml` (`fr.placement.quiet`), or (stealth) the target's file
on the tracking ref (`fr.placement.stealth`)."""


@dataclass(frozen=True)
class EffectiveSettings:
    settings: Settings
    sources: dict[str, str]
    """Dotted key -> `default` or `repo`, for every leaf key."""
    ref: str | None
    ref_note: str
    pending_edit: str | None
    source: Source = "defaults"
    """Which R2 step supplied `ref` (`fr settings show` reports it)."""
    contrary: tuple[str, ...] = ()
    """Under stealth, the forge keys the tracking file sets explicitly to something other
    than stealth's own value (R5 refuses them, `stealth-forge-explicit`)."""


_CACHE: dict[tuple[str, str], tuple[Settings, dict[str, str]]] = {}
_NOTICED: set[tuple[str, str]] = set()
"""(root, sha) pairs whose CI HEAD-source notice was printed: one notice per process."""


def _leaf_keys(model: Any, prefix: str = "") -> list[str]:
    keys: list[str] = []
    for name, field in type(model).model_fields.items():
        value = getattr(model, name)
        dotted = f"{prefix}{field.alias or name}"
        if isinstance(value, BaseModel):
            keys.extend(_leaf_keys(value, f"{dotted}."))
        else:
            keys.append(dotted)
    return keys


def _present(data: object, dotted: str) -> bool:
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _show(root: Path, sha: str, path: str = SETTINGS_PATH) -> str | None:
    """*path* at commit *sha*: None only when the commit's tree has no such path.

    Any other git failure is a read failure and raises: it must never read as "absent"
    (which means defaults).
    """
    listed = git_answer(root, "ls-tree", "--name-only", sha, "--", path)
    if listed.returncode != 0:
        raise SettingsError(
            f"cannot read {path} at {sha[:12]}: git ls-tree failed: {listed.stderr.strip()}"
        )
    if not listed.stdout.strip():
        return None
    done = git_answer(root, "show", f"{sha}:{path}")
    if done.returncode != 0:
        raise SettingsError(
            f"cannot read {path} at {sha[:12]}: git show failed: {done.stderr.strip()}"
        )
    return done.stdout


show_at_commit = _show
"""*path* at a commit: the reader the quiet switch (`fr.placement.quiet`) shares."""


def _commit_of(root: Path, qualified_ref: str) -> str | None:
    """The commit a FULLY QUALIFIED ref names, or None. Never a short name: a local
    branch called `origin/main` would shadow the remote-tracking ref in git's DWIM order."""
    done = git_answer(root, "rev-parse", "--verify", "--quiet", f"{qualified_ref}^{{commit}}")
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def _has_tracking_refs(root: Path, remote: str) -> bool:
    done = git_answer(
        root, "for-each-ref", "--count=1", "--format=%(refname)", f"refs/remotes/{remote}/"
    )
    if done.returncode != 0:
        raise SettingsError(
            f"cannot list refs/remotes/{remote}/*: git for-each-ref failed: {done.stderr.strip()}"
        )
    return bool(done.stdout.strip())


def _head_source(root: Path) -> tuple[str | None, str | None, str, Source]:
    """R2's CI exception: HEAD's COMMITTED tree, never the working tree."""
    sha = _commit_of(root, "HEAD")
    if sha is None:
        return None, None, "CI, no default ref and no HEAD commit: defaults", "defaults"
    note = f"CI, no default ref: read from HEAD's committed tree ({sha[:12]})"
    key = (str(root), sha)
    if key not in _NOTICED:
        _NOTICED.add(key)
        print(f"fr: settings: {note}", file=sys.stderr)
    return "HEAD", sha, note, "head"


def _resolve_source(root: Path) -> tuple[str | None, str | None, str, Source]:
    """(qualified ref, commit sha, note, source) of the policy source, in R2's order."""
    from fr.artifacts.trigger import in_ci

    remote = remote_name(root)
    if isinstance(remote, GitRefusal):
        raise SettingsError(f"cannot establish the default branch: {remote.reason}")
    if remote is not None and _has_tracking_refs(root, remote):
        # Step 1: the policy source is the remote default, never a local branch (an
        # unpushed local edit would be a branch relaxing its own controls).
        named = remote_default_ref(root)
        if isinstance(named, GitRefusal):
            raise SettingsError(f"cannot establish the default branch: {named.reason}")
        if named is None:
            configured = git_answer(root, "config", "init.defaultBranch").stdout.strip()
            if configured:
                qualified = f"refs/remotes/{remote}/{configured}"
                if _commit_of(root, qualified) is not None:
                    named = f"{remote}/{configured}"
        if named is not None:
            qualified = f"refs/remotes/{named}"
            sha = _commit_of(root, qualified)
            if sha is None:
                raise SettingsError(f"{qualified} does not name a commit; run `git fetch {remote}`")
            return qualified, sha, f"read from {named}", "remote"
        if in_ci():
            return _head_source(root)
        raise SettingsError(
            f"cannot find the default branch of remote `{remote}`: no "
            f"refs/remotes/{remote}/HEAD and no {remote}/main or {remote}/master. "
            f"Run `git fetch {remote}` and "
            f"`git remote set-head {remote} -a`"
        )
    if remote is not None:
        # Step 2b: a remote with no tracking refs yet (the bootstrap state). Never a local
        # branch: deleting tracking refs locally must not hand the policy to one.
        if in_ci():
            return _head_source(root)
        return (
            None,
            None,
            f"remote `{remote}` has no tracking refs yet; using built-in defaults "
            "until it is fetched",
            "defaults",
        )
    # Step 2a: no remote at all reads the local default branch.
    configured = git_answer(root, "config", "init.defaultBranch").stdout.strip()
    for name in dict.fromkeys(n for n in (configured, "main", "master") if n):
        qualified = f"refs/heads/{name}"
        sha = _commit_of(root, qualified)
        if sha is not None:
            return qualified, sha, f"no origin default branch: read local {name}", "local"
    if in_ci():
        return _head_source(root)
    return None, None, "no default branch found: defaults", "defaults"


def read_at_default(repo_root: Path, path: str) -> str | None:
    """*path* as the default ref's commit has it (None: absent, or no default ref).

    The one reader of a policy-adjacent file: same SHA the settings come from, never
    the working tree. Raises `SettingsError` on a read failure or an unresolvable remote.
    """
    root = Path(repo_root)
    try:
        if git_answer(root, "rev-parse", "--git-dir").returncode != 0:
            return None
        _, sha, _, _ = _resolve_source(root)
    except GitUnavailableError:
        return None
    return None if sha is None else _show(root, sha, path)


def _pending(root: Path, committed: str | None) -> str | None:
    path = root / SETTINGS_PATH
    try:
        current = path.read_text() if path.is_file() else None
    except OSError:
        return None
    if current == committed:
        return None
    return (
        f"{SETTINGS_PATH} differs from the default branch's revision; the edit has no effect "
        "until it lands there"
    )


def _yaml_of(text: str | None, source: str) -> object:
    if text is None:
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SettingsError(f"{source}: not valid YAML: {e}") from e


yaml_of = _yaml_of


def unservable_placement(placement: str, source: str) -> SettingsError:
    """R4's refusal of a placement this fr cannot yet serve: the one wording, shared by
    the loader and the path resolver (`fr.artifacts.paths.space_for`)."""
    return SettingsError(
        f"{source}: placement: {placement} is not yet available in this fr (only "
        f"{', '.join(f'`{p}`' for p in sorted(SERVABLE_PLACEMENTS))} are served)"
    )


def _servable(settings: Settings, source: str) -> Settings:
    if settings.placement not in SERVABLE_PLACEMENTS:
        assert settings.placement in PLACEMENTS
        raise unservable_placement(settings.placement, source)
    return settings


def _repo_file(settings: Settings) -> Settings:
    """`.fr/settings.yaml` is the `repo` placement's file, so it says `repo` (§3.A: the
    placement must match where the file lives). Quiet is switched on by the `fr` branch."""
    if settings.placement == "stealth":
        raise SettingsError(
            f"{SETTINGS_PATH}: placement: stealth cannot be set in repo settings: stealth is "
            "chosen per run, never by repo settings (R24). Start the run with "
            "`fr isolation up --stealth <tracking-repo>@<branch>` (or fr-goal mode=stealth)"
        )
    if settings.placement != "repo":
        raise SettingsError(
            f"{SETTINGS_PATH}: placement: {settings.placement} is not set here: this file is "
            "the `repo` placement's. Quiet is switched on by the `fr` branch's root "
            "settings.yaml (`fr settings init --quiet`)"
        )
    return settings


def _quiet(root: Path) -> EffectiveSettings | None:
    """R2 under quiet: the policy is the `fr` branch's root settings.yaml, read from
    `origin/fr` by commit. A `.fr/settings.yaml` on the default branch is ignored, and
    the note says so."""
    from fr.artifacts.paths import SWITCH_REF, SWITCH_SETTINGS
    from fr.placement.quiet import switch

    found = switch(root)
    if found is None:
        return None
    settings = found.settings
    sources = {k: ("quiet" if _present(found.data, k) else "default") for k in _leaf_keys(settings)}
    note = f"quiet: read from origin/fr:{SWITCH_SETTINGS} ({found.sha[:12]})"
    try:
        _, sha, _, _ = _resolve_source(root)
        ignored = sha is not None and _show(root, sha) is not None
    except (SettingsError, GitUnavailableError):
        ignored = False
    if ignored:
        note += f"; {SETTINGS_PATH} on the default branch is ignored under quiet"
    return EffectiveSettings(settings, sources, SWITCH_REF, note, None, "quiet")


_STEALTH_NOTICED: set[str] = set()


def _stealth(root: Path) -> EffectiveSettings | None:
    """R2 under stealth: the policy is `<target-dir>/settings.yaml` on the tracking ref,
    read by commit in the tracking worktree; a target's `.fr/settings.yaml` is ignored
    and fr prints that it was. Stealth sets the forge keys itself (R5, R24): the
    effective values are always the quiet ones, and an explicit contrary value is
    reported in `contrary` for `fr settings check` and `fr run start` to refuse."""
    from fr.placement.stealth import (
        QUIET_FORGE,
        TARGET_SETTINGS,
        marker_tracking,
        worktree_path,
    )

    found = marker_tracking(root)
    if found is None:
        return None
    ref, target = found
    wt = worktree_path(root, ref)
    qualified = f"refs/remotes/origin/{ref.branch}"
    rel = f"{target}/{TARGET_SETTINGS}"
    source = f"{ref.text}:{rel}"
    sha = _commit_of(wt, qualified) if (wt / ".git").exists() else None
    if sha is None:
        raise SettingsError(
            f"placement stealth: cannot read the tracking ref {ref.text} in {wt}; re-run "
            f"`fr isolation up --stealth {ref.text}` (R24 fail-fast)"
        )
    text = _show(wt, sha, rel)
    data = _yaml_of(text, source)
    settings = parse_settings(data, source=source)
    if _present(data, "placement") and settings.placement != "stealth":
        raise SettingsError(
            f"{source}: placement: {settings.placement} cannot be set in a target's stealth "
            "settings file; it says `placement: stealth` (or nothing)"
        )
    contrary = tuple(
        f"forge.{key}"
        for key, value in QUIET_FORGE.items()
        if _present(data, f"forge.{key}") and getattr(settings.forge, key) != value
    )
    settings = settings.model_copy(
        update={
            "placement": "stealth",
            "forge": settings.forge.model_copy(update=dict(QUIET_FORGE)),
        }
    )
    sources = {k: ("stealth" if _present(data, k) else "default") for k in _leaf_keys(settings)}
    for key in QUIET_FORGE:
        sources[f"forge.{key}"] = "stealth"
    note = f"stealth: read from {source} ({sha[:12]}); the forge keys are stealth's own"
    try:
        _, own, _, _ = _resolve_source(root)
        ignored = own is not None and _show(root, own) is not None
    except (SettingsError, GitUnavailableError):
        ignored = False
    if ignored:
        note += f"; the target's {SETTINGS_PATH} is ignored under stealth"
        if str(root) not in _STEALTH_NOTICED:
            _STEALTH_NOTICED.add(str(root))
            print(
                f"fr: settings: placement stealth: the target's {SETTINGS_PATH} is ignored; "
                f"the tracking repo's {rel} wins (R24)",
                file=sys.stderr,
            )
    return EffectiveSettings(settings, sources, qualified, note, None, "stealth", contrary=contrary)


def parse_settings_text(text: str | None, *, source: str, servable: bool = True) -> Settings:
    """A settings file's text (None: absent, the defaults) as `Settings`, by the same
    closed, strict model and placement check the checkout reader applies.

    `servable=False` skips only the placement check, for a caller that decides what a
    valid placement means itself (the `origin/fr` switch, `fr.artifacts.paths`)."""
    settings = parse_settings(_yaml_of(text, source), source=source)
    return _servable(settings, source) if servable else settings


def load_settings(repo_root: Path) -> EffectiveSettings:
    """The effective settings of *repo_root*, with per-key provenance.

    Raises `SettingsError` for an unparseable or invalid file and for a placement this
    fr cannot serve — the refusal is the loader's, so every reader gets it.
    """
    root = Path(repo_root)
    try:
        in_repo = git_answer(root, "rev-parse", "--git-dir").returncode == 0
        hidden = _stealth(root) if in_repo else None
        if hidden is not None:
            return hidden
        quiet = _quiet(root) if in_repo else None
        if quiet is not None:
            return quiet
        ref, sha, note, source = (
            _resolve_source(root) if in_repo else (None, None, "not a git repo", "defaults")
        )
    except GitUnavailableError:
        ref, sha, note, source = None, None, "git unavailable: defaults", "defaults"
    if ref is None or sha is None:
        defaults = parse_settings({}, source="defaults")
        return EffectiveSettings(
            defaults,
            dict.fromkeys(_leaf_keys(defaults), "default"),
            None,
            note,
            _pending(root, None),
        )
    text = _show(root, sha)
    pending = _pending(root, text)
    key = (str(root), sha)
    cached = _CACHE.get(key)
    if cached is None:
        data = _yaml_of(text, SETTINGS_PATH)
        settings = _repo_file(_servable(parse_settings(data, source=SETTINGS_PATH), SETTINGS_PATH))
        sources = {k: ("repo" if _present(data, k) else "default") for k in _leaf_keys(settings)}
        cached = (settings, sources)
        _CACHE[key] = cached
    settings, sources = cached
    return EffectiveSettings(settings, dict(sources), ref, note, pending, source)
