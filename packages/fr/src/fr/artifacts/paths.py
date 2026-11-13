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

The placement is read in the plan's precedence: a stealth marker in this workspace
(`fr.placement.stealth`, chosen per run, R24), then a valid `refs/remotes/origin/fr`
switch (quiet, `fr.placement.quiet`), then `repo`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from fr.settings import SettingsError

REPO: Final = "repo"
QUIET: Final = "quiet"
STEALTH: Final = "stealth"
FEATURES_DIR: Final = "features"
"""Below a quiet or stealth root, each feature's artifacts live at `features/<feature-id>/`."""
FEATURE_OWNER: Final = "OWNER"
"""`<root>/features/<feature-id>/OWNER` names the branch that owns that feature root (one
line), so a second branch with the same id is refused even from another clone (gh#1419)."""
FEATURE_BASE: Final = "BASE"
"""`<root>/features/<feature-id>/BASE`: the product commit the branch stood on (its merge
base with the default ref) when it claimed the root, written with `OWNER` by the same
first fr commit. Merged status counts only commits the base does not contain (R17)."""
FEATURE_HEADS: Final = "HEADS"
"""`<root>/features/<feature-id>/HEADS`: the product heads `fr push` pushed for the feature,
one sha a line, append-only: owned evidence that outlives the branch's refs (R17)."""
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
    ("spec-legacy-archived", f"{_SP}/archived-specs", "LEGACY_ARCHIVED_SPECS_DIR"),
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
    ("usage-archived", f"{_SP}/implemented/usage", "ARCHIVED_USAGE_DIR"),
    ("audit-archived", f"{_SP}/implemented/audits", "ARCHIVED_AUDITS_DIR"),
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

ARTIFACT_TREES: Final = (_SP, _ACC)
"""The two repo-relative trees fr's artifacts live under (the stealth push refuses a
commit touching one, R24)."""

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


def artifact_root(repo_root: Path) -> Path:
    """The directory the repo-relative layout hangs from for the checkout at
    *repo_root*: its toplevel under `repo`, this feature's root in the `fr` worktree
    under quiet. `artifact_root(root) / RUNS_REL` is how a module holding a relative
    constant asks the resolver."""
    return feature_root(space_for(repo_root))


def kind_dir(kind: str, space: ArtifactSpace) -> Path:
    """The absolute path of *kind* in *space*; `KeyError` naming an unknown kind."""
    return feature_root(space) / _known(kind, KIND_DIRS)


def below(root: Path, kind: str) -> Path:
    """*kind*'s directory directly below *root*, with NO placement read. For a root that
    already is an artifact root by construction (a feature root, an exported tree, the
    root an artifact's own path names), or a reader of the product checkout's OWN git
    tree, comparing it with its own history (which under quiet holds no fr artifact,
    R23). Every other caller asks `artifact_root` (the tripwire holds the line)."""
    return Path(root) / _known(kind, KIND_DIRS)


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


def _marker_placement(repo_root: Path) -> str | None:
    """The placement this workspace's `.fr-isolation` marker recorded at `up` (R23
    "sticky"), or None for no marker. A marker an older fr wrote without the key was
    written before quiet existed, so it recorded `repo` (review p3-r5): a workspace made
    before the switch appeared refuses rather than silently moving."""
    from fr.isolation.marker import marker_at

    marker = marker_at(repo_root)
    if not marker:
        return None
    placement = marker.get("placement", REPO)
    return placement if isinstance(placement, str) else REPO


def sticky_refusal(recorded: str, current: str, source: str) -> SettingsError:
    """R23 "sticky": the placement a workspace recorded and the one the switch now names
    disagree. The one wording `space_for` and every other sticky check share."""
    from fr.settings import SettingsError

    return SettingsError(
        f"{source}: this workspace was set up under placement: {recorded}, but the "
        f"`fr` switch (origin/fr) now says placement: {current} (the `fr` branch was "
        "deleted or renamed, or its settings changed). fr will not move a live workspace "
        f"between placements: restore origin/fr to placement: {recorded}, or finish this "
        "workspace and start the next one with `fr isolation up`"
    )


def space_for(repo_root: Path, *, create: bool = True) -> ArtifactSpace:
    """The artifact space of the checkout at *repo_root*.

    Precedence: a stealth marker (R24: stealth is chosen per run and recorded in the
    workspace, so no command run there falls back to `repo`), then a valid `origin/fr`
    switch (quiet), then `repo`. A workspace whose marker recorded one placement while
    the switch now names another refuses, naming both (R23 "sticky").

    `create=False` only computes the space: the quiet fr worktree and branch are not
    created and the stealth tracking repo is not asked (`fr settings paths --no-create`,
    which the hooks and the OpenCode plugin call, review p6-r4)."""
    from fr.isolation.marker import MARKER
    from fr.placement.quiet import quiet_space, read_switch
    from fr.settings.load import unservable_placement

    root = Path(repo_root)
    marked = _marker_placement(root)
    if marked == STEALTH:
        from fr.placement.stealth import stealth_space

        return stealth_space(root, create=create)
    if marked is not None and marked not in (REPO, QUIET):
        raise unservable_placement(marked, str(root / MARKER))
    current = QUIET if read_switch(root) is not None else REPO
    if marked is not None and marked != current:
        raise sticky_refusal(marked, current, str(root / MARKER))
    if current == QUIET:
        return quiet_space(root, create=create)
    return ArtifactSpace(REPO, root, None)


def outside_repo(repo_root: Path) -> str | None:
    """`quiet` or `stealth` when the checkout's artifacts live off its product branches,
    None under `repo`. Reads the marker and the switch only: no worktree is created and
    no tracking repo asked, so a writer can refuse BEFORE it writes."""
    root = Path(repo_root)
    if _marker_placement(root) == STEALTH:
        return STEALTH
    from fr.placement.quiet import read_switch

    return QUIET if read_switch(root) is not None else None


REPO_CONFIG_KINDS: Final = frozenset(
    {"workflow", "verification", "models", "trackers", "plan-config"}
)
"""Kinds below the artifact directories that are REPO CONFIGURATION, authored by the repo
owner and read from the product checkout under every placement (decision
quiet-artifact-root-scope). Everything else below `docs/superpowers/` and
`docs/acceptance/` is placement-bound: it lives at the placement's root (R1)."""


def placement_bound(rel: str) -> bool:
    """Does the repo-relative path (or glob) *rel* name a placement-bound fr artifact?
    `docs/superpowers/**` and `docs/acceptance/**` are, except `REPO_CONFIG_KINDS`;
    repo configuration elsewhere (`.devcontainer/`, `.claude/`, `.fr/`) is not."""
    rel = rel.removeprefix("./")
    for kind in REPO_CONFIG_KINDS:
        own = KIND_DIRS[kind]
        if rel == own or rel.startswith(f"{own}/"):
            return False
    return any(rel == root or rel.startswith(f"{root}/") for root in (_SP, _ACC))


def search_roots(repo_root: Path, rel: str) -> list[Path]:
    """The roots a reader of *rel* (a repo-relative path or glob) looks below: the
    toplevel for repo configuration and under `repo`; every feature root otherwise."""
    if not placement_bound(rel):
        return [Path(repo_root)]
    return list(feature_roots(space_for(Path(repo_root))))


def repo_glob(kind: str, pattern: str) -> str:
    """A glob below *kind*'s directory under the `repo` placement, relative to the
    toplevel (`repo_glob("plan", "*/_meta.yaml")`): how `fr.artifacts.registry` builds
    each `ArtifactKind.locator`, which is the resolver's `repo` output (§3.E)."""
    return f"{_known(kind, KIND_DIRS)}/{pattern}"
