"""Parser for v2 plan-as-folder format.

Loads `_meta.yaml` and per-phase yaml files (`NN.yaml`) from a plan
folder, validates them against the pydantic schemas in `vk.types`,
and returns an immutable `Plan` dataclass.

Design rationale lives in:
  docs/superpowers/specs/2026-05-06-vk-rebuild-state-machine-design.md

Key invariants enforced here:
  - The directory must contain `_meta.yaml` (otherwise it's not a v2 plan).
  - The plan's `fr_version` constraint (when present) must be satisfiable by the
    installed `vk` package (otherwise we'd produce wrong renders).
  - All errors surface as `PlanSchemaError` with the offending file
    in the message — no naked pydantic/packaging exceptions leak out.
"""

from __future__ import annotations

import importlib.metadata
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from fr import refs
from fr._urls import is_cross_repo_spec
from fr.types import PhaseDoc, PlanMeta


class PlanSchemaError(Exception):
    pass


@dataclass(frozen=True)
class Plan:
    dir: Path  # absolute path to the plan folder
    meta: PlanMeta
    phases: tuple[PhaseDoc, ...]
    repo_root: Path | None = None  # absolute path to the git repo root, if discoverable
    # Raw plan texts, loaded by parse() so the (I/O-free) renderer can embed
    # them in Issue bodies / VK card descriptions. `prose` is `_prose.md`
    # verbatim (None when absent); `phase_texts` maps phase NUMBER → raw
    # `NN.yaml` file content. Defaults keep direct `Plan(...)` constructions
    # (tests, builders) valid — enrichment then degrades to nothing.
    prose: str | None = None
    phase_texts: Mapping[int, str] = field(default_factory=dict)
    # Lifecycle-resolved repo-relative spec path, loaded by parse() so the
    # (I/O-free) renderer can link the spec's CURRENT location even after
    # it archives to implemented/specs/ (2026-06-06 spec-path-repair).
    # None when meta.spec is unset, cross-repo, or unresolvable.
    spec_path: str | None = None

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
INSTALLED_FR_VERSION = importlib.metadata.version("fr")


def _enforce_fr_version(plan_dir: Path, declared: object) -> None:
    """Refuse the plan when the installed fr is outside its `fr_version`.

    Takes the raw declared value rather than a validated `PlanMeta` so it can
    run before schema validation — see `parse`. A non-string (or absent)
    value is left to `PlanMeta` to reject with a type error; this function
    only answers the version question. The legacy `vk_version` field is inert
    (it constrains a tool that no longer exists — labels-are-data doctrine
    applied to plan files; see the super-fr split design).
    """
    if not declared:
        return
    if not isinstance(declared, str):
        return
    try:
        spec = SpecifierSet(declared)
    except InvalidSpecifier as e:
        raise PlanSchemaError(f"_meta.yaml: invalid fr_version {declared!r}: {e}") from e
    try:
        installed = Version(INSTALLED_FR_VERSION)
    except InvalidVersion as e:  # pragma: no cover — installed version comes from packaging
        raise PlanSchemaError(
            f"installed fr version {INSTALLED_FR_VERSION!r} is not a valid PEP 440 version: {e}"
        ) from e
    if installed not in spec:
        raise PlanSchemaError(
            f"plan {plan_dir} requires fr_version {declared} "
            f"but installed is {INSTALLED_FR_VERSION}. "
            f"To upgrade: uv tool install --force "
            f'"fr @ git+https://github.com/derio-net/super-fr@vX.Y.Z#subdirectory=packages/fr" '
            f"where X.Y.Z is a version satisfying {declared}."
        )


def parse(plan_dir: Path, *, enforce_fr_version: bool = True) -> Plan:
    """Load and validate a v2 plan folder.

    Raises `PlanSchemaError` for any of:
      - `plan_dir` is not a directory
      - missing `_meta.yaml` (looks like a v1 plan)
      - `_meta.yaml` fails schema validation
      - `fr_version` is malformed or unsatisfiable by the installed fr
        (legacy `vk_version` is inert metadata — never enforced), and
        `enforce_fr_version` is True
      - any `NN.yaml` is malformed yaml or fails schema validation

    `enforce_fr_version` (spec §3.E.1, artifact-migration-framework) defaults
    to **on** — safety stays the default, so every existing caller keeps
    today's behavior with no code change. The gate exists to stop an
    incompatible `fr` from *executing* a plan (`fr apply`, `fr_dispatch`,
    `fr pickup`); it must never apply to a purely historical read.
    `fr.spec.compute_status` is the one caller that passes `False`, so an
    archived plan (which records what shipped, under whatever `fr` shipped
    it — spec §2 non-goal: archives are never migrated) still reports its
    real state instead of `PlanSchemaError` degrading it to `state="Missing"`.
    """
    plan_dir = Path(plan_dir).resolve()
    if not plan_dir.is_dir():
        raise PlanSchemaError(f"not a directory: {plan_dir}")
    meta_path = plan_dir / "_meta.yaml"
    if not meta_path.exists():
        raise PlanSchemaError(
            f"{plan_dir} is not a v2 plan (no _meta.yaml). "
            f"Run `fr migrate v1-to-v2` first if migrating from v1."
        )
    try:
        raw_meta = yaml.safe_load(meta_path.read_text())
    except Exception as e:
        raise PlanSchemaError(f"_meta.yaml: {e}") from e

    # The `fr_version` gate runs on the RAW mapping, BEFORE schema validation
    # (review r5-b4). `PlanMeta` is `extra="forbid"`, so a plan carrying a key
    # this fr does not know is a hard parse failure — and validating first
    # meant the version floor, the one message that says "upgrade fr", was
    # never reached. fr 3.x meeting 4.0.0's `workflow:` key therefore died on
    # pydantic's `extra_forbidden` instead of the floor the plan carries
    # precisely to be understood by an old reader. The gate is the plan's way
    # of telling an older fr not to try, so it has to be answerable by an fr
    # that cannot parse the rest of the file.
    if enforce_fr_version and isinstance(raw_meta, dict):
        _enforce_fr_version(plan_dir, raw_meta.get("fr_version"))

    try:
        meta = PlanMeta.model_validate(raw_meta)
    except Exception as e:
        raise PlanSchemaError(f"_meta.yaml: {e}") from e

    indexed_phase_files: list[tuple[int, Path]] = []
    for p in plan_dir.iterdir():
        m = _PHASE_FILE_RE.match(p.name)
        if m:
            indexed_phase_files.append((int(m.group(1)), p))
    indexed_phase_files.sort(key=lambda pair: pair[0])

    phases: list[PhaseDoc] = []
    phase_texts: dict[int, str] = {}
    for _, f in indexed_phase_files:
        raw = f.read_text()
        try:
            doc = PhaseDoc.model_validate(yaml.safe_load(raw))
        except Exception as e:
            raise PlanSchemaError(f"{f.name}: {e}") from e
        phases.append(doc)
        # Keyed by the PARSED phase number (not the filename index) — the
        # renderer looks up by `phase.phase.number`.
        phase_texts[doc.phase.number] = raw

    prose_path = plan_dir / "_prose.md"
    prose = prose_path.read_text() if prose_path.exists() else None

    repo_root = _find_repo_root(plan_dir)

    spec_path: str | None = None
    if meta.spec and repo_root is not None and not is_cross_repo_spec(meta.spec):
        res = refs.resolve_spec_ref(meta.spec, repo_root)
        if res.path is not None:
            spec_path = res.path.relative_to(repo_root).as_posix()

    return Plan(
        dir=plan_dir,
        meta=meta,
        phases=tuple(phases),
        repo_root=repo_root,
        prose=prose,
        phase_texts=phase_texts,
        spec_path=spec_path,
    )


def parse_strict(plan_dir: Path) -> Plan:
    """`parse()` plus the folder-level invariants of the parity contract.

    The cncd schema-parity harness (cnc-fr spec 2026-07-02, §3.3) pins
    the plan-as-folder contract that cncd's Go parser must mirror. Two
    invariants live at folder level rather than in the pydantic models,
    so `parse()` cannot enforce them without breaking wild plans:

      - `_prose.md` is mandatory. Every authoring path (`fr plan
        create`, `fr plan rework`) writes it; a folder without one is
        not a complete v2 plan.
      - Phase numbers are contiguous 1..N (and at least one phase
        exists). `parse()` tolerates gaps because historical plans
        carry them; new-world consumers must not.

    `parse()` itself stays lenient — the bridge keeps skipping
    gracefully and `prose=None` plans keep parsing. Use this entry
    point wherever the corpus contract applies (the fixtures corpus
    test, ingestion-bound tooling).

    Raises `PlanSchemaError` — same class, same "name the offending
    file" doctrine as `parse()`.
    """
    plan = parse(plan_dir)
    if plan.prose is None:
        raise PlanSchemaError(f"{plan.dir}: missing _prose.md (mandatory in strict/parity mode)")
    numbers = [p.phase.number for p in plan.phases]
    if not numbers:
        raise PlanSchemaError(f"{plan.dir}: no phase files (NN.yaml) found")
    expected = list(range(1, len(numbers) + 1))
    if numbers != expected:
        raise PlanSchemaError(
            f"{plan.dir}: phase numbers must be contiguous 1..{len(numbers)}, got {numbers}"
        )
    return plan
