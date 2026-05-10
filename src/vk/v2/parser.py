from __future__ import annotations

import importlib.metadata
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from vk.v2.types import PhaseDoc, PlanMeta


class PlanSchemaError(Exception):
    pass


@dataclass(frozen=True)
class Plan:
    dir: Path
    meta: PlanMeta
    phases: tuple[PhaseDoc, ...]

    @property
    def prose_path(self) -> Path:
        return self.dir / "_prose.md"


_PHASE_FILE_RE = re.compile(r"^(\d{2,})\.yaml$")

INSTALLED_VK_VERSION = importlib.metadata.version("vk")


def parse(plan_dir: Path) -> Plan:
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

    spec = SpecifierSet(meta.vk_version)
    if Version(INSTALLED_VK_VERSION) not in spec:
        raise PlanSchemaError(
            f"plan {plan_dir} requires vk_version {meta.vk_version} "
            f"but installed is {INSTALLED_VK_VERSION}. "
            f"To upgrade: pip install --user --upgrade "
            f'"vk @ git+https://github.com/derio-net/superpowers-for-vk@v<version>"'
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

    return Plan(dir=plan_dir, meta=meta, phases=tuple(phases))
