"""The S1 configuration moves as registered hops (spec 2026-11-19-event-driven-a-la-carte
§D, R8 to R12; plan 2026-11-24-s1-configuration-homes P4.T2).

- each location-stamped kind of `fr.config.migrate.all_moved()` relocates 1 -> 2: a rename in
  one checkout (`repo`, and `isolation-allow` everywhere), a cross-space move under quiet
  and stealth (`fr.config.migrate.move_across`, destination pushed first);
- `quiet-config` 1 -> 2 moves the product's R11 `.fr/` files to `fr-config`;
- `settings-location` 1 -> 2 creates the configuration branch from the old switch (it
  does not move: R6 keeps the old file as the legacy copy);
- `profiles` 2 -> 3 relocates `.devcontainer/fr-profiles.yaml` to `.fr/profiles.yaml`,
  writing `schema_version: 3`, built in memory and written once. Its crash window (a
  `.fr/profiles.yaml` at 2 with no old file) is finished in place.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.runner import MIGRATING_ROOT, MIGRATIONS, SchemaMigration, relocate_file
from fr.config import migrate as moves


def _refusal(message: str) -> Exception:
    """A `SettingsError` (exit 2), imported late: `fr.settings` imports the services layer,
    which imports `fr.isolation.types`, which imports this package."""
    from fr.settings import SettingsError

    return SettingsError(message)


def _in_new_place(entry: moves.Moved, path: Path) -> bool:
    return Path(path).full_match(f"**/{entry.new_locator}")


def _across(entry: moves.Moved, product: Path) -> bool:
    from fr.artifacts.paths import REPO

    return entry.across and moves.placement_of(product) != REPO


def _destination(entry: moves.Moved) -> Callable[[Path], Path]:
    def destination(path: Path) -> Path:
        if _in_new_place(entry, path):
            return path
        product = entry.product_of(path)
        root = moves.space_root(product) if entry.across else product
        return root / moves.rel(entry.below(path, product))

    return destination


def _relocation(kind: str) -> SchemaMigration:
    entry = moves.moved(kind)
    destination = _destination(entry)

    def fn(path: Path) -> None:
        product = entry.product_of(path)
        moves.refuse_link(product, path)
        if _across(entry, product):
            moves.move_across(product, path, entry.below(path, product))
        else:
            dest = destination(path)
            moves.refuse_link(product, dest)  # never move a file through a linked parent
            relocate_file(path, dest)

    return SchemaMigration(
        kind=kind,
        from_version=1,
        to_version=2,
        fn=fn,
        relocates=True,
        destination=destination,
        keeps=moves.stealth_keeps,
        description=f"{kind}: move {entry.old} to {entry.new_locator} (S1 R9)",
    )


for _entry in moves.all_moved():
    if _entry.kind != "profiles":  # profiles is body-stamped: its 2 -> 3 hop is below
        MIGRATIONS.register(_relocation(_entry.kind))


# --- profiles 2 -> 3 -------------------------------------------------------------------

_PROFILES = moves.moved("profiles")


def _profiles_text(path: Path) -> str:
    from fr.artifacts.registry import read_verbatim

    bom, text = read_verbatim(path)
    return bom + moves.with_stamp(text, 3)


def _config_checkout(top: Path) -> bool:
    """Whether *top* is a configuration checkout, decided by structure, never by a name
    (review p4-r5): quiet's `fr-config` worktree (HEAD on `refs/heads/fr-config` at the path
    fr computes for this repository), or the configuration space of the product being
    migrated (`MIGRATING_ROOT`) when that product's placement is quiet or stealth (the
    stealth configuration clone its valid marker names)."""
    import subprocess

    from fr.artifacts.paths import REPO
    from fr.config.space import CONFIG_BRANCH, quiet_checkout

    top = Path(top)
    head = subprocess.run(
        ["git", "-C", str(top), "symbolic-ref", "-q", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if head == f"refs/heads/{CONFIG_BRANCH}" and top.resolve() == quiet_checkout(top).resolve():
        return True
    product = MIGRATING_ROOT.get()
    if product is None or moves.placement_of(product) == REPO:
        return False
    return top.resolve() == moves.space_root(product).resolve()


def _profiles_destination(path: Path) -> Path:
    if _in_new_place(_PROFILES, path):
        product = path.parent.parent
        if (product / moves.LEGACY_PROFILES).exists():
            raise _refusal(
                f"both {product / moves.LEGACY_PROFILES} and {path} exist: fr will not "
                "choose between them. Keep the one you want, delete the other, and run "
                "`fr migrate artifacts --yes` again (S1 R12)"
            )
        return path
    return _destination(_PROFILES)(path)


def _profiles_relocate(path: Path) -> None:
    if _in_new_place(_PROFILES, path):
        # The crash window: the file moved and its stamp did not land. Finished in place
        # in a product checkout only; on a configuration branch a change is reviewed.
        if _config_checkout(path.parent.parent):
            raise _refusal(
                f"{path} is at version 2 on the configuration branch: propose its "
                "`schema_version: 3` there in a pull request (S1 §B)"
            )
        moves.refuse_link(path.parent.parent, path)
        write_text_atomic(path, _profiles_text(path))
        return
    product = _PROFILES.product_of(path)
    moves.refuse_link(product, path)
    if _across(_PROFILES, product):
        # One move with the final bytes (review p4-r4): a version-1 file's 1 -> 2 rewrite
        # is redone in memory on the committed bytes, never refused as uncommitted.
        moves.move_across(product, path, _PROFILES.new, body=moves.profiles_body(product, path))
        if moves.stealth_keeps(path):
            moves.restore_committed(product, path)  # the kept copy is the committed one
        return
    text = _profiles_text(path)
    dest = _profiles_destination(path)
    moves.refuse_link(product, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(dest, text)
    path.unlink()


MIGRATIONS.register(
    SchemaMigration(
        kind="profiles",
        from_version=2,
        to_version=3,
        fn=_profiles_relocate,
        relocates=True,
        destination=_profiles_destination,
        expected=lambda path: _profiles_text(path).encode(),
        keeps=moves.stealth_keeps,
        description="profiles: move .devcontainer/fr-profiles.yaml to the configuration "
        "space's profiles.yaml at schema_version 3 (S1 R9)",
    )
)


# --- quiet-config 1 -> 2 (R11) ---------------------------------------------------------


def _quiet_destination(path: Path) -> Path:
    if moves.quiet_stamp(path) == 2:
        return path
    return moves.space_root(path.parent.parent) / moves.rel(path.name)


def _quiet_move(path: Path) -> None:
    moves.move_across(path.parent.parent, path, path.name)


MIGRATIONS.register(
    SchemaMigration(
        kind="quiet-config",
        from_version=1,
        to_version=2,
        fn=_quiet_move,
        relocates=True,
        destination=_quiet_destination,
        description="quiet-config: move the product's .fr/ file to fr-config (S1 R11)",
    )
)


# --- settings-location 1 -> 2 (R5, R6) -------------------------------------------------


def _create_space(path: Path) -> None:
    product = MIGRATING_ROOT.get()
    if product is None:
        raise _refusal("the settings move runs only inside `fr migrate artifacts`")
    moves.ensure_space(product)
    if moves.settings_stamp(path) != 2:
        raise _refusal(
            f"the configuration branch's {moves.rel(moves.SETTINGS)} differs from {path}: "
            "fr will not choose between them (S1 R6, R12). `fr settings sync` shows both"
        )


MIGRATIONS.register(
    SchemaMigration(
        kind="settings-location",
        from_version=1,
        to_version=2,
        fn=_create_space,
        description="settings-location: create the configuration branch from the old "
        "switch, which stays as the legacy copy (S1 R5, R6)",
    )
)
