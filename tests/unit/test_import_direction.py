"""Package boundary enforcement (super-fr split, B2 style).

Dependency direction is the architecture: `fr` imports neither sibling;
`fr_dispatch` never imports `fr_vk` (adapters plug in via the Runner
protocol / entry points). A violation here is a design regression, not
a style nit — the whole point of the split is that the base ships
without the dispatch stack and the framework ships without VibeKanban.
"""

from __future__ import annotations

import re
from pathlib import Path

PACKAGES = Path(__file__).resolve().parents[2] / "packages"

_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.M)


def _imports_of(package_dir: Path) -> dict[Path, set[str]]:
    out: dict[Path, set[str]] = {}
    for py in (package_dir).rglob("*.py"):
        roots = set(_IMPORT_RE.findall(py.read_text()))
        out[py] = roots
    return out


# The ONE sanctioned soft point (spec §Architecture): `fr apply --to`
# imports fr_dispatch.registry behind an importlib.util.find_spec guard.
_SOFT_POINT = ("apply_cmd.py", "fr_dispatch")


def test_fr_imports_no_siblings() -> None:
    offenders = {
        str(f): roots & {"fr_dispatch", "fr_vk"}
        for f, roots in _imports_of(PACKAGES / "fr" / "src" / "fr").items()
        if roots & {"fr_dispatch", "fr_vk"}
        and not (f.name == _SOFT_POINT[0] and roots & {"fr_dispatch", "fr_vk"} == {_SOFT_POINT[1]})
    }
    assert not offenders, f"fr must not import siblings: {offenders}"


def test_soft_point_is_guarded() -> None:
    """The sanctioned import must stay behind find_spec — never module-level."""
    src = (PACKAGES / "fr" / "src" / "fr" / "commands" / "apply_cmd.py").read_text()
    assert 'importlib.util.find_spec("fr_dispatch")' in src
    assert "\nfrom fr_dispatch" not in src  # no module-level import


def test_fr_dispatch_never_imports_fr_vk() -> None:
    offenders = {
        str(f): roots & {"fr_vk"}
        for f, roots in _imports_of(PACKAGES / "fr-dispatch" / "src" / "fr_dispatch").items()
        if "fr_vk" in roots
    }
    assert not offenders, f"fr_dispatch must not import the adapter: {offenders}"


def test_fr_dispatch_never_imports_fr_cncd() -> None:
    offenders = {
        str(f): roots & {"fr_cncd"}
        for f, roots in _imports_of(PACKAGES / "fr-dispatch" / "src" / "fr_dispatch").items()
        if "fr_cncd" in roots
    }
    assert not offenders, f"fr_dispatch must not import the adapter: {offenders}"


def test_adapters_never_import_each_other() -> None:
    """fr_cncd is a peer of fr_vk: each may import the base and the
    framework, never the sibling adapter."""
    cncd_offenders = {
        str(f): roots & {"fr_vk"}
        for f, roots in _imports_of(PACKAGES / "fr-cncd" / "src" / "fr_cncd").items()
        if "fr_vk" in roots
    }
    assert not cncd_offenders, f"fr_cncd must not import fr_vk: {cncd_offenders}"
    vk_offenders = {
        str(f): roots & {"fr_cncd"}
        for f, roots in _imports_of(PACKAGES / "fr-vk" / "src" / "fr_vk").items()
        if "fr_cncd" in roots
    }
    assert not vk_offenders, f"fr_vk must not import fr_cncd: {vk_offenders}"


def test_fr_vk_strings_stay_in_the_adapter() -> None:
    """The framework carries no VK vocabulary: no MCP client types, no
    VibeKanban wire shapes, no willikins metric names."""
    banned = re.compile(r"VkMcpClient|vibe-kanban|willikins|project_id|VK_[A-Z]", re.I)
    offenders = []
    for py in (PACKAGES / "fr-dispatch" / "src" / "fr_dispatch").rglob("*.py"):
        for n, line in enumerate(py.read_text().splitlines(), 1):
            if banned.search(line):
                offenders.append(f"{py.name}:{n}: {line.strip()}")
    assert not offenders, "VK vocabulary leaked into fr_dispatch:\n" + "\n".join(offenders)
