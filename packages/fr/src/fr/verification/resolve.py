"""Strategy resolution — repo > env > wheel > marketplace (spec §A, R1).

The same four-place order as `fr.workflow.resolve` (its docstring owns the
reasoning), sharing one directory walk in `fr._shipped`:

    docs/superpowers/verifications/<name>.yaml     # repo — wins wholesale
    $FR_SHIPPED_VERIFICATIONS_DIR/<name>.yaml      # explicit escape
    fr/verifications/<name>.yaml                   # inside the `fr` wheel
    ~/.claude/plugins/marketplaces/derio-net--super-fr/
        plugins/super-fr/verifications/<name>.yaml # the plugin clone

`plugins/super-fr/verifications/` is canonical; the wheel copy is generated
and guarded by `tests/unit/test_tripwire_shipped_verifications.py`.
"""

from __future__ import annotations

from pathlib import Path

from fr import _shipped
from fr.verification.model import RESERVED, StrategyError, StrategyManifest, parse_strategy

REPO_VERIFICATIONS_REL = Path("docs") / "superpowers" / "verifications"
PLUGIN_VERIFICATIONS_REL = Path("plugins") / "super-fr" / "verifications"
PACKAGED_VERIFICATIONS_DIRNAME = "verifications"
SHIPPED_ENV_VAR = "FR_SHIPPED_VERIFICATIONS_DIR"


def packaged_shipped_verifications_dir() -> Path | None:
    """The shipped strategies inside the `fr` wheel, or `None` (no such data)."""
    return _shipped.packaged_dir(PACKAGED_VERIFICATIONS_DIRNAME)


def shipped_verification_dirs(shipped_root: Path | None = None) -> list[Path]:
    """The shipped sources, in lookup order — one list for resolve AND list."""
    return _shipped.shipped_dirs(
        env_var=SHIPPED_ENV_VAR,
        plugin_rel=PLUGIN_VERIFICATIONS_REL,
        packaged=packaged_shipped_verifications_dir(),
        shipped_root=shipped_root,
    )


def resolve_strategy(
    name: str, repo_root: Path | None, *, shipped_root: Path | None = None
) -> StrategyManifest:
    """Resolve strategy `name`; a repo file wins wholesale over a shipped one.

    `repo_root=None` searches only the shipped sources. Raises `StrategyError`
    naming EVERY searched path when none exists.
    """
    if name == RESERVED:
        raise StrategyError(f"{RESERVED!r} is reserved: it means no strategy, it never resolves")

    shipped = shipped_verification_dirs(shipped_root)
    candidates = (
        _shipped.lookup_candidates(name, repo_root / REPO_VERIFICATIONS_REL, shipped)
        if repo_root is not None
        else [d / f"{name}.yaml" for d in shipped]
    )
    for path in candidates:
        if path.is_file():
            manifest = parse_strategy(path.read_text(), source=str(path))
            if manifest.verification != name:
                raise StrategyError(
                    f"{path}: manifest names itself {manifest.verification!r}, "
                    f"but its file is {name!r}"
                )
            return manifest

    searched = " and ".join(str(p) for p in candidates)
    raise StrategyError(f"unknown verification strategy {name!r} — searched {searched}")


def _label(directory: Path, repo_root: Path) -> str:
    if directory == repo_root / REPO_VERIFICATIONS_REL:
        return "repo"
    if directory == packaged_shipped_verifications_dir():
        return "wheel"
    if directory == Path.home() / _shipped.MARKETPLACE_ROOT / PLUGIN_VERIFICATIONS_REL:
        return "marketplace"
    return "env"


def list_strategies(repo_root: Path, *, shipped_root: Path | None = None) -> list[tuple[str, str]]:
    """`(name, source-label)` for every strategy that resolves, each name once.

    The label is where `resolve_strategy` would take it from: `repo`, `env`,
    `wheel` or `marketplace`.
    """
    shipped = shipped_verification_dirs(shipped_root)
    return [
        (name, _label(directory, repo_root))
        for name, directory in _shipped.listing(repo_root / REPO_VERIFICATIONS_REL, shipped)
    ]
