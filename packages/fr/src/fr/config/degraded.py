"""Executable and trust configuration that DEGRADES, never locks out (spec
2026-11-19-event-driven-a-la-carte R7 as amended; review finding p4-r3, plan decision
p4-degraded-not-lockout).

Under quiet and stealth three more kinds are executable or trust configuration: the repo's
workflow shapes (a `kind: cli` step's argv), its verification strategies (install and
scenario commands) and the profile declarations. When the configuration branch is not
enforced (`fr.config.protection`), none of them refuses the command:

- a repo workflow shape or strategy is ignored, and the SHIPPED one of the same name is
  used (`usable_bytes` answers None), with the reason said once;
- `profiles.yaml` is read, but every key outside `PROFILE_KEPT` is dropped, named, with
  the reason (`read_profiles`): each profile's `secrets` (the env-file names a container
  receives) and `ops` (the ops-trust mount and `FR_PROFILE`), the `forge`, `ci` and
  `tracking` blocks (a type or host override decides where fr sends credentials), the
  version-1 `backend` and `host`, and any key fr does not know. Profile names, purposes,
  the default profile and the stamp stay, so `fr isolation up`, `fr services` and the ops
  commands keep working on a free-plan private repo.

The same rule holds for R13's old paths in the product checkout: no configuration branch's
protection covers them, so their executable and trust content is degraded the same way.

A failed protection read (network, auth, a 5xx) or a failed fetch of the tip is not "not
enforced": an executor still refuses. Only a read-only caller (`fr services`, the forge
consumers of `fr._hosts`) takes the degraded view then, saying "protection unknown".
"""

from __future__ import annotations

import sys
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from fr.config.space import ConfigSpace

PROFILE_KEPT_TOP: Final = ("schema_version", "default", "profiles")
"""The top-level keys of `profiles.yaml` an unprotected configuration branch keeps."""
PROFILE_KEPT_ENTRY: Final = ("purpose",)
"""The keys of one profile an unprotected configuration branch keeps."""

_SAID: set[str] = set()
"""Lines this process has said, so a command says each once."""

_BUILDING_CLIENT: ContextVar[bool] = ContextVar("fr_config_degraded_client", default=False)
"""True while the protection read itself builds the forge client: that client resolves the
forge from `profiles.yaml`, and must take the degraded view (an unprotected `forge.host`
must never choose the forge that answers whether the branch is protected)."""


def _say(line: str) -> None:
    if line not in _SAID:
        _SAID.add(line)
        print(f"fr: {line}", file=sys.stderr)


def _old_path_reason(space: ConfigSpace) -> str:
    return (
        f"it is at its old path in the product checkout, which no {space.placement} "
        "configuration branch's protection covers; run `fr migrate artifacts --yes`"
    )


def usable_bytes(root: Path, path: Path, what: str) -> bytes | None:
    """The bytes of the repo workflow shape or strategy *path* to use, or None: ignore it and
    use the shipped one (said once). Under `repo`, the file. Under quiet and stealth, the
    fetched tip's bytes when the configuration branch is enforced; None when it is not, when
    the file is not on the tip (the checkout's copy is not reviewed), or when *path* is an
    old path in the product. A failed fetch or protection read refuses (`ProtectionError`)."""
    from fr.config import protection
    from fr.config.space import _REPO, _in_space_checkout, config_space

    space = config_space(Path(root))
    if space.placement == _REPO:
        return Path(path).read_bytes()
    if not _in_space_checkout(space, path):
        _say(f"ignoring {path} ({what}): {_old_path_reason(space)}; the shipped one is used")
        return None
    below = Path(path).resolve().relative_to(space.dir.resolve()).as_posix()
    try:
        answer = protection.protection_of(space)
    except protection.ProtectionReadError as exc:
        raise protection.ProtectionReadError(f"fr will not {what}: {exc}") from exc
    if isinstance(answer, protection.NotEnforced):
        where = f"{below} on {space.ref}"
        _say(f"{protection.ignored_line([below], answer, where)}; the shipped one is used")
        return None
    protection.fetch_tip(space, what)
    text = space.at_default(below)
    if text is None:
        _say(
            f"ignoring {path} ({what}): it is not on the fetched tip of {space.ref}, so it is "
            "not reviewed; the shipped one is used"
        )
        return None
    return text.encode()


def degrade_profiles(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """*data* (a parsed `profiles.yaml`) without its security-relevant keys, and the dotted
    names of every key dropped."""
    kept: dict[str, Any] = {}
    dropped: list[str] = []
    for key, value in data.items():
        if key not in PROFILE_KEPT_TOP:
            dropped.append(str(key))
        elif key == "profiles" and isinstance(value, dict):
            entries: dict[str, Any] = {}
            for name, entry in value.items():
                if not isinstance(entry, dict):
                    entries[name] = entry
                    continue
                entries[name] = {k: v for k, v in entry.items() if k in PROFILE_KEPT_ENTRY}
                dropped += [f"profiles.{name}.{k}" for k in entry if k not in PROFILE_KEPT_ENTRY]
            kept[key] = entries
        else:
            kept[key] = value
    return kept, dropped


def _origin_lacks_branch(space: ConfigSpace) -> bool:
    """Whether *space*'s configuration branch is known to be absent: its clone does not
    exist yet (stealth before creation), or origin answers `ls-remote` with no such branch
    (exit 2). A failed probe is not "absent" (lens review l-errors-r7)."""
    from fr.placement.quiet import _default_network

    repo = space.checkout if space.placement == "stealth" else space.product
    if space.ref is None or not (repo / ".git").exists():
        return True
    branch = space.ref.removeprefix("origin/")
    probe = _default_network(repo)(
        ["git", "ls-remote", "--exit-code", "origin", f"refs/heads/{branch}"]
    )
    return probe.returncode == 2


def read_profiles(space: ConfigSpace, cfg: Path, *, unknown_ok: bool = False) -> Any:
    """The profile declarations *cfg* under quiet or stealth (see the module docstring): the
    fetched tip's file in the configuration space, or an old path's file as the product's
    default branch has it committed. *unknown_ok* (read-only callers) takes the degraded view
    when the tip cannot be fetched or protection cannot be read, instead of refusing."""
    import yaml

    from fr.config import protection
    from fr.config.space import PROFILES, _in_space_checkout, branch_fetched

    what = "read the profile declarations (secrets, ops, services)"
    unknown: str | None = None
    in_space = _in_space_checkout(space, cfg)
    if in_space:
        known = branch_fetched(space)
        try:
            protection.fetch_tip(space, what)
        except protection.UncheckedTipError as exc:
            if not known and _origin_lacks_branch(space):
                return {}  # no configuration branch yet: the space declares nothing
            if not unknown_ok:  # lens review l-errors-r7: unknown is not absent
                raise
            if not known:
                _say(f"reading no profile declarations: protection unknown ({exc})")
                return {}
            unknown = str(exc)
        except protection.ProtectionError:
            pass  # no forge protects the branch, so fr never fetches it: the last fetched tip
        if not branch_fetched(space):
            return {}
        text = space.at_default(PROFILES)
        where = f"{PROFILES} on {space.ref}"
    else:
        if not cfg.is_file():
            return {}
        from fr.settings.load import read_at_default

        rel = cfg.relative_to(space.product).as_posix()
        text = read_at_default(space.product, rel)
        where = f"{rel} on the default branch"
    if text is None:
        return {}
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        return data
    kept, dropped = degrade_profiles(data)
    if not dropped or _BUILDING_CLIENT.get():
        return kept if dropped else data
    if not in_space:
        reason = _old_path_reason(space)
    elif unknown is not None:
        reason = f"protection unknown ({unknown})"
    else:
        token = _BUILDING_CLIENT.set(True)
        try:
            answer = protection.protection_of(space)
        except protection.ProtectionReadError as exc:
            if not unknown_ok:
                raise protection.ProtectionReadError(f"fr will not {what}: {exc}") from exc
            answer = None
            reason = f"protection unknown ({exc})"
        finally:
            _BUILDING_CLIENT.reset(token)
        if isinstance(answer, protection.Enforced):
            return data
        if isinstance(answer, protection.NotEnforced):
            reason = (
                f"{answer.branch} on {answer.repo} is not protected ({answer.reason}); "
                f"{protection.fix_text(answer.branch)}"
            )
    _say(f"ignoring {', '.join(dropped)} in {where}: {reason}")
    return kept
