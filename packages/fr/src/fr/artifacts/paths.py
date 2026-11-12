"""The artifact path resolver (spec 2026-11-04-repo-feature-settings R1, §3.E).

One resolver, keyed by kind and placement, produces every artifact path fr writes.
`KIND_DIRS` is the one table of repo-relative artifact directories (and the few
repo-local fr files); an `ArtifactSpace` says where they sit for one checkout.

**The layout rule.** A placement changes the ROOT, never the relative layout below it:

- `repo` (today): the root is the repo toplevel, and `kind_dir` is `<toplevel>/<rel>`;
- `quiet` and `stealth`: the root is the `fr` worktree, or the target's directory in
  the tracking worktree, and a feature's artifacts sit at
  `<root>/features/<feature-id>/<rel>`, the same `<rel>` as under `repo`.

So every reader keeps its shape, and a cross-feature reader (the acceptance fold, the
logical spec lookup) iterates `feature_roots` rather than knowing the placement.

**The only place.** This module is the only place an artifact directory literal
(`docs/superpowers/...`, `docs/acceptance/...`) may appear in fr's source; the tripwire
`tests/unit/test_tripwire_artifact_paths.py` refuses one anywhere else.

The placement is read in the plan's precedence: a stealth marker in this workspace,
then a valid `refs/remotes/origin/fr` switch, then `repo`. Only `repo` is served yet;
any other answer is R4's "not yet available" refusal, in the loader's own wording
(`fr.settings.load.unservable_placement`).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

REPO: Final = "repo"
QUIET: Final = "quiet"
FEATURES_DIR: Final = "features"
"""Below a quiet or stealth root, each feature's artifacts live at `features/<feature-id>/`."""
RECORDS_SUFFIX: Final = ".records"
"""A run's step records sit at `<runs dir>/<run-id>.records/`, beside its cursor."""
SWITCH_REF: Final = "refs/remotes/origin/fr"
"""The quiet switch: the remote `fr` branch, as last fetched."""
SWITCH_SETTINGS: Final = "settings.yaml"

_SP = "docs/superpowers"
_ACC = "docs/acceptance"

# (kind, repo-relative path, shell variable suffix). The ONE table: `KIND_DIRS` and the
# `fr settings paths` names are both derived from it.
_TABLE: Final[tuple[tuple[str, str, str], ...]] = (
    ("superpowers", _SP, "SUPERPOWERS_DIR"),
    ("archive", f"{_SP}/implemented", "ARCHIVE_DIR"),
    ("spec", f"{_SP}/specs", "SPECS_DIR"),
    ("spec-archived", f"{_SP}/implemented/specs", "ARCHIVED_SPECS_DIR"),
    ("plan", f"{_SP}/plans", "PLANS_DIR"),
    ("plan-archived", f"{_SP}/implemented/plans", "ARCHIVED_PLANS_DIR"),
    ("plan-legacy-archived", f"{_SP}/archived-plans", "LEGACY_ARCHIVED_PLANS_DIR"),
    ("journal", f"{_SP}/journals", "JOURNALS_DIR"),
    ("journal-specs", f"{_SP}/journals/specs", "SPEC_JOURNALS_DIR"),
    ("journal-plans", f"{_SP}/journals/plans", "PLAN_JOURNALS_DIR"),
    ("journal-debug", f"{_SP}/journals/debug", "DEBUG_JOURNALS_DIR"),
    ("journal-archived", f"{_SP}/implemented/journals", "ARCHIVED_JOURNALS_DIR"),
    ("journal-archived-specs", f"{_SP}/implemented/journals/specs", "ARCHIVED_SPEC_JOURNALS_DIR"),
    ("journal-archived-plans", f"{_SP}/implemented/journals/plans", "ARCHIVED_PLAN_JOURNALS_DIR"),
    ("journal-archived-debug", f"{_SP}/implemented/journals/debug", "ARCHIVED_DEBUG_JOURNALS_DIR"),
    ("run", f"{_SP}/runs", "RUNS_DIR"),
    ("run-archived", f"{_SP}/implemented/runs", "ARCHIVED_RUNS_DIR"),
    ("usage", f"{_SP}/usage", "USAGE_DIR"),
    ("workflow", f"{_SP}/workflows", "WORKFLOWS_DIR"),
    ("verification", f"{_SP}/verifications", "VERIFICATIONS_DIR"),
    ("plan-config", f"{_SP}/plan-config.yaml", "PLAN_CONFIG_FILE"),
    ("models", f"{_SP}/models.yaml", "MODELS_FILE"),
    ("trackers", f"{_SP}/trackers.yaml", "TRACKERS_FILE"),
    ("acceptance", _ACC, "ACCEPTANCE_DIR"),
    ("acceptance-fragment", f"{_ACC}/features", "ACCEPTANCE_FRAGMENTS_DIR"),
)

KIND_DIRS: Mapping[str, str] = MappingProxyType({k: rel for k, rel, _ in _TABLE})
"""kind -> repo-relative POSIX path. The same relative path under every placement."""

_SHELL_NAMES: Final[Mapping[str, str]] = MappingProxyType({k: f"FR_{v}" for k, _, v in _TABLE})


def _known(kind: str, table: Mapping[str, str]) -> str:
    try:
        return table[kind]
    except KeyError:
        raise KeyError(
            f"unknown artifact kind {kind!r} (known: {', '.join(sorted(KIND_DIRS))})"
        ) from None


def shell_name(kind: str) -> str:
    """The `fr settings paths --shell` variable for *kind* (`plan` -> `FR_PLANS_DIR`)."""
    return _known(kind, _SHELL_NAMES)


@dataclass(frozen=True)
class ArtifactSpace:
    """Where one checkout's artifacts live: the placement, its root, and (outside
    `repo`) the feature whose root below it this checkout writes."""

    placement: str
    root: Path
    feature: str | None = None


def feature_root(space: ArtifactSpace) -> Path:
    """The directory the relative layout hangs from: the root itself under `repo`,
    `<root>/features/<feature>` otherwise."""
    if space.placement == REPO or space.feature is None:
        return space.root
    return space.root / FEATURES_DIR / space.feature


def kind_dir(kind: str, space: ArtifactSpace) -> Path:
    """The absolute path of *kind* in *space*; `KeyError` naming an unknown kind."""
    return feature_root(space) / _known(kind, KIND_DIRS)


def records_dir(run_id: str, space: ArtifactSpace) -> Path:
    """The step-record directory of run *run_id*: `<runs dir>/<run-id>.records`."""
    return kind_dir("run", space) / f"{run_id}{RECORDS_SUFFIX}"


def feature_roots(space: ArtifactSpace) -> Iterator[Path]:
    """Every feature root a cross-feature reader must look in, sorted: `[root]` under
    `repo`; every `<root>/features/*` directory under quiet and stealth."""
    if space.placement == REPO:
        yield space.root
        return
    features = space.root / FEATURES_DIR
    if features.is_dir():
        yield from sorted(p for p in features.iterdir() if p.is_dir())


def feature_id(branch: str) -> str:
    """The feature id of *branch*: fr's isolation branch slug (`feat/a-b` -> `feat__a-b`)."""
    from fr.isolation import types

    return types.branch_slug(branch)


def _common_dir(repo_root: Path) -> Path | None:
    """The repository's common git dir, read from the filesystem (no subprocess: this
    runs on every artifact lookup), or None outside a git checkout."""
    dot = repo_root / ".git"
    if dot.is_dir():
        git_dir = dot
    elif dot.is_file():
        try:
            line = dot.read_text().strip()
        except OSError:
            return None
        if not line.startswith("gitdir:"):
            return None
        git_dir = (repo_root / line.removeprefix("gitdir:").strip()).resolve()
    else:
        return None
    common = git_dir / "commondir"
    if common.is_file():
        try:
            return (git_dir / common.read_text().strip()).resolve()
        except OSError:
            return None
    return git_dir


def _has_switch_ref(repo_root: Path) -> bool:
    common = _common_dir(repo_root)
    if common is None:
        return False
    if (common / SWITCH_REF).is_file():
        return True
    packed = common / "packed-refs"
    try:
        lines = packed.read_text().splitlines() if packed.is_file() else []
    except OSError:
        return False
    return any(line.split(" ", 1)[-1] == SWITCH_REF for line in lines if not line.startswith("#"))


def _switch_placement(repo_root: Path) -> str | None:
    """The placement a fetched `origin/fr` switch names, read by commit (never a working
    tree); None when there is no such ref, it holds no `settings.yaml`, or that file
    says `repo`.

    R23's switch is a root `settings.yaml` saying `placement: quiet`, parsed by the
    settings loader's own closed schema (R4). Any other content refuses, naming the ref:
    invalid settings with the loader's wording, and `stealth` by R24's rule, since stealth
    is never chosen by repo settings."""
    if not _has_switch_ref(repo_root):
        return None
    from fr.git import GitUnavailableError, git_answer
    from fr.settings import SettingsError
    from fr.settings.load import parse_settings_text

    source = f"{SWITCH_REF}:{SWITCH_SETTINGS}"
    try:
        done = git_answer(repo_root, "show", source)
    except GitUnavailableError:
        return None
    if done.returncode != 0:
        return None
    placement = parse_settings_text(done.stdout, source=source, servable=False).placement
    if placement == REPO:
        return None
    if placement != QUIET:
        raise SettingsError(
            f"{source}: placement: {placement} cannot be set on the `fr` switch: stealth is "
            "chosen per run, never by repo settings (R24); the switch says `placement: quiet`"
        )
    return placement


def _marker_placement(repo_root: Path) -> str | None:
    from fr.isolation.marker import marker_at

    marker = marker_at(repo_root)
    placement = marker.get("placement") if marker else None
    return placement if isinstance(placement, str) and placement != REPO else None


def space_for(repo_root: Path) -> ArtifactSpace:
    """The artifact space of the checkout at *repo_root*.

    Precedence: a stealth marker, then a valid `origin/fr` switch, then `repo`. Only
    `repo` is served yet; another placement raises `SettingsError` with the loader's
    refusal, so behaviour is unchanged."""
    from fr.isolation.marker import MARKER
    from fr.settings.load import unservable_placement

    root = Path(repo_root)
    marked = _marker_placement(root)
    if marked is not None:
        raise unservable_placement(marked, str(root / MARKER))
    switched = _switch_placement(root)
    if switched is not None:
        raise unservable_placement(switched, f"{SWITCH_REF}:{SWITCH_SETTINGS}")
    return ArtifactSpace(REPO, root, None)


def repo_glob(kind: str, pattern: str) -> str:
    """A glob below *kind*'s directory under the `repo` placement, relative to the
    toplevel (`repo_glob("plan", "*/_meta.yaml")`): how `fr.artifacts.registry` builds
    each `ArtifactKind.locator`, which is the resolver's `repo` output (§3.E)."""
    return f"{_known(kind, KIND_DIRS)}/{pattern}"
