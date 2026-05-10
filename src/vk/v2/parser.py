"""Parser for v2 plan-as-folder format.

Loads `_meta.yaml` and per-phase yaml files (`NN.yaml`) from a plan
folder, validates them against the pydantic schemas in `vk.v2.types`,
and returns an immutable `Plan` dataclass.

Design rationale lives in:
  docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md

Key invariants enforced here:
  - The directory must contain `_meta.yaml` (otherwise it's not a v2 plan).
  - The plan's `vk_version` constraint must be satisfiable by the
    installed `vk` package (otherwise we'd produce wrong renders).
  - All errors surface as `PlanSchemaError` with the offending file
    in the message — no naked pydantic/packaging exceptions leak out.
"""

from __future__ import annotations

import importlib.metadata
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from vk.v2.types import PhaseDoc, PlanMeta


class PlanSchemaError(Exception):
    pass


@dataclass(frozen=True)
class Plan:
    dir: Path  # absolute path to the plan folder
    meta: PlanMeta
    phases: tuple[PhaseDoc, ...]
    repo_root: Path | None = None  # absolute path to the git repo root, if discoverable

    @property
    def prose_path(self) -> Path:
        return self.dir / "_prose.md"

    @property
    def repo_relative_dir(self) -> Path:
        """Plan dir relative to `repo_root`; falls back to `dir` if root unknown.

        Used by the renderer for the Issue-body `📋 Plan:` line so dispatched
        bodies don't leak the dispatcher's local filesystem layout.
        """
        if self.repo_root is None:
            return self.dir
        try:
            return self.dir.relative_to(self.repo_root)
        except ValueError:
            return self.dir


def _find_repo_root(start: Path) -> Path | None:
    """Walk up from `start` looking for a `.git` directory.

    Filesystem-only — no shell-out to git. Returns None if `.git` is
    not found before reaching the filesystem root.
    """
    cur = start.resolve()
    while True:
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:  # reached fs root
            return None
        cur = cur.parent


# Phase yaml filenames are exactly two digits: `01.yaml` through `99.yaml`.
# Plans with 100+ phases would be a smell; if that ever becomes real, bump
# this to three digits and revisit the spec's per-phase decomposition guidance.
_PHASE_FILE_RE = re.compile(r"^(\d{2})\.yaml$")

# Cached at module-import time because `importlib.metadata.version()` is not
# free. The bridge runs under supercronic, which kills and respawns the
# process on every cron tick after `vk-bump`, so a stale cache is not a real
# concern — the new process always re-reads the metadata.
INSTALLED_VK_VERSION = importlib.metadata.version("vk")


def parse(plan_dir: Path) -> Plan:
    """Load and validate a v2 plan folder.

    Raises `PlanSchemaError` for any of:
      - `plan_dir` is not a directory
      - missing `_meta.yaml` (looks like a v1 plan)
      - `_meta.yaml` fails schema validation
      - `vk_version` is malformed or unsatisfiable by the installed vk
      - any `NN.yaml` is malformed yaml or fails schema validation
    """
    plan_dir = Path(plan_dir).resolve()
    if not plan_dir.is_dir():
        raise PlanSchemaError(f"not a directory: {plan_dir}")
    meta_path = plan_dir / "_meta.yaml"
    if not meta_path.exists():
        raise PlanSchemaError(
            f"{plan_dir} is not a v2 plan (no _meta.yaml). "
            f"Run `vk migrate v1-to-v2` first if migrating from v1."
        )
    try:
        meta = PlanMeta.model_validate(yaml.safe_load(meta_path.read_text()))
    except Exception as e:
        raise PlanSchemaError(f"_meta.yaml: {e}") from e

    try:
        spec = SpecifierSet(meta.vk_version)
    except InvalidSpecifier as e:
        raise PlanSchemaError(f"_meta.yaml: invalid vk_version {meta.vk_version!r}: {e}") from e
    try:
        installed = Version(INSTALLED_VK_VERSION)
    except InvalidVersion as e:  # pragma: no cover — installed version comes from packaging
        raise PlanSchemaError(
            f"installed vk version {INSTALLED_VK_VERSION!r} is not a valid PEP 440 version: {e}"
        ) from e
    if installed not in spec:
        raise PlanSchemaError(
            f"plan {plan_dir} requires vk_version {meta.vk_version} "
            f"but installed is {INSTALLED_VK_VERSION}. "
            f"To upgrade: pip install --user --upgrade "
            f'"vk @ git+https://github.com/derio-net/superpowers-for-vk@vX.Y.Z" '
            f"where X.Y.Z is a version satisfying {meta.vk_version}."
        )

    indexed_phase_files: list[tuple[int, Path]] = []
    for p in plan_dir.iterdir():
        m = _PHASE_FILE_RE.match(p.name)
        if m:
            indexed_phase_files.append((int(m.group(1)), p))
    indexed_phase_files.sort(key=lambda pair: pair[0])

    phases: list[PhaseDoc] = []
    for _, f in indexed_phase_files:
        try:
            phases.append(PhaseDoc.model_validate(yaml.safe_load(f.read_text())))
        except Exception as e:
            raise PlanSchemaError(f"{f.name}: {e}") from e

    return Plan(
        dir=plan_dir,
        meta=meta,
        phases=tuple(phases),
        repo_root=_find_repo_root(plan_dir),
    )
