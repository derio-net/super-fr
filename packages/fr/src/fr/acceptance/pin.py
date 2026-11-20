"""The fr release a scaffolded pipeline installs (spec 2026-11-18-consumer-delivery R9, R10).

A consumer's pipeline used to install fr from `@main`: whatever merged last ran with the
repo's tokens. Now it installs the commit of the release tag of the fr that scaffolded it.
This module resolves that commit, and is the one place that knows the install line's
format, so the scaffold that writes it and `fr acceptance check` that reads it agree.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

FR_REPO_URL = "https://github.com/derio-net/super-fr"

# One format, written by the scaffold and read back by `fr acceptance check`.
INSTALL_LINE = 'uv tool install "git+' + FR_REPO_URL + '@{sha}#subdirectory=packages/fr"  # {tag}'
PIN_RE = re.compile(r'super-fr@(?P<sha>[0-9a-f]{40})#subdirectory=packages/fr"\s+#\s*(?P<tag>v\S+)')

_RC = re.compile(r"^(\d+\.\d+\.\d+)(?:rc(\d+))?$")
_LS_REMOTE_TIMEOUT = 30

LsRemote = Callable[[str], str]


class FrPinError(Exception):
    """The release commit of this fr could not be resolved."""


@dataclass(frozen=True)
class FrPin:
    sha: str
    tag: str

    def install_line(self) -> str:
        return INSTALL_LINE.format(sha=self.sha, tag=self.tag)


def tag_for_version(version: str) -> str:
    """The release tag of `version`: `8.1.5` is `v8.1.5`, `8.1.6rc2` is `v8.1.6-rc.2`."""
    m = _RC.match(version)
    if m and m.group(2):
        return f"v{m.group(1)}-rc.{m.group(2)}"
    return f"v{version}"


def default_ls_remote(tag: str) -> str:
    """`git ls-remote` of the tag and its peeled form, with no credential."""
    try:
        done = subprocess.run(
            [
                "git",
                "ls-remote",
                FR_REPO_URL,
                f"refs/tags/{tag}",
                f"refs/tags/{tag}^{{}}",
            ],
            capture_output=True,
            text=True,
            timeout=_LS_REMOTE_TIMEOUT,
            check=False,
            env=_anonymous_env(),
        )
    except (OSError, subprocess.SubprocessError) as e:
        raise FrPinError(str(e)) from e
    if done.returncode != 0:
        raise FrPinError(done.stderr.strip() or f"git ls-remote exited {done.returncode}")
    return done.stdout


def _anonymous_env() -> dict[str, str]:
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_CONFIG_")}
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def resolve_fr_pin(version: str, *, ls_remote: LsRemote | None = None) -> FrPin:
    """The commit `version`'s release tag names, preferring an annotated tag's peeled line.

    Raises `FrPinError`, naming the tag and the remedy, when the tag cannot be read."""
    tag = tag_for_version(version)
    remedy = (
        f"fr {version} has no release tag {tag} to pin the pipeline to; "
        "check the network and that this fr is a released version, then retry"
    )
    try:
        out = (ls_remote or default_ls_remote)(tag)
    except FrPinError as e:
        raise FrPinError(f"cannot read tag {tag}: {e}; {remedy}") from e
    except Exception as e:  # an injected resolver may raise anything
        raise FrPinError(f"cannot read tag {tag}: {e}; {remedy}") from e
    plain = peeled = None
    for line in out.splitlines():
        sha, _, ref = line.partition("\t")
        sha = sha.strip()
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            continue
        if ref.strip() == f"refs/tags/{tag}^{{}}":
            peeled = sha
        elif ref.strip() == f"refs/tags/{tag}":
            plain = sha
    found = peeled or plain
    if found is None:
        raise FrPinError(f"tag {tag} not found at {FR_REPO_URL}; {remedy}")
    return FrPin(sha=found, tag=tag)


def stale_pin_warning(root: Path, running: str) -> str | None:
    """One warning when a scaffolded pipeline pins an fr older than `running` (R10).

    Reads the install line `INSTALL_LINE` writes, at each CI type's scaffold path. An
    unpinned (`@main`) or absent pipeline, and an equal or newer pin, give None."""
    from packaging.version import InvalidVersion, Version

    from fr.acceptance.ci import SCAFFOLD_PATHS

    try:
        current = Version(running)
    except InvalidVersion:
        return None
    oldest: tuple[Version, str, str] | None = None
    for rel in SCAFFOLD_PATHS.values():
        path = root / rel
        try:
            text = path.read_text()
        except OSError, UnicodeDecodeError:
            continue
        for m in PIN_RE.finditer(text):
            try:
                v = Version(m["tag"].lstrip("v"))
            except InvalidVersion:
                continue
            if oldest is None or v < oldest[0]:
                oldest = (v, m["tag"], rel)
    if oldest is None or oldest[0] >= current:
        return None
    return (
        f"{oldest[2]} installs fr {oldest[1]}, older than the running fr {running}; "
        "run `fr acceptance init --refresh-ci` to move the pin"
    )
