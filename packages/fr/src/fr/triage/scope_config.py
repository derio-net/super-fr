"""Scope identity and the scope config (spec 2026-10-06-triage-claims §3.A, R1, R14, R15).

A triage scope signs its forge claims with a scope id, `s-<sha256(name NUL host id)[:8]>`.
The host id is a random token minted once per host; no hostname is read, because on
macOS `gethostname()` follows the network and a scope whose id moved would find its own
claims foreign. Neither the host id nor `<state dir>/scope.yaml` is durable triage state:
both stay on the host (R15), which is why `state_sync.DURABLE_FILES` never names them.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import secrets
import subprocess
import tempfile
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fr.isolation.types import _home
from fr.triage.errors import TriageError
from fr.triage.model import Scope

PUBLISH_TIMEOUT = 120.0  # seconds; tests shorten it
HOST_ID_ENV = "FR_HOST_ID"
SCOPE_CONFIG_FILE = "scope.yaml"
_HOST_ID_RE = re.compile(r"[0-9a-f]{16}")


def host_id_path() -> Path:
    return _home() / ".config" / "fr" / "host-id"


def _read_host_id(path: Path) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise TriageError(f"{path}: cannot read the host id ({exc})") from exc
    if not _HOST_ID_RE.fullmatch(value):
        raise TriageError(
            f"{path}: not a host id (16 hex characters); fix or remove it, or set {HOST_ID_ENV}"
        )
    return value


def host_id() -> str:
    """`FR_HOST_ID` when set, else this host's id, minted on first use.

    The new id is written to a temporary file and hard-linked into place: `link` fails
    when the file exists, so of two concurrent first uses one wins and the other re-reads
    the winner's id. An unreadable or malformed file is refused, never replaced: fr does
    not silently mint a second identity over one it cannot read.
    """
    override = os.environ.get(HOST_ID_ENV)
    if override:
        return override
    path = host_id_path()
    if path.exists():
        return _read_host_id(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".host-id.", suffix=".fr-tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(secrets.token_hex(8) + "\n")
        os.chmod(tmp_name, 0o600)
        with contextlib.suppress(FileExistsError):
            os.link(tmp_name, path)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
    return _read_host_id(path)


def scope_id(scope: Scope | str) -> str:
    """This host's id for *scope* (a Scope, or its `name`): `s-` and eight hex
    characters, nothing identifying."""
    name = scope if isinstance(scope, str) else scope.name
    digest = hashlib.sha256(f"{name}\0{host_id()}".encode()).hexdigest()
    return f"s-{digest[:8]}"


class ScopeConfig(BaseModel):
    """`<state dir>/scope.yaml`: settings of one scope on one host (R14)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_expiry_hours: int = Field(default=24, ge=1)
    board_name: str | None = None
    # An argument list, never a shell string: `{board}`, `{name}`, `{scope_id}`.
    publish: list[str] = []


def load_scope_config(state_dir: Path) -> ScopeConfig:
    """The scope config in *state_dir*; the defaults when there is none."""
    path = state_dir / SCOPE_CONFIG_FILE
    if not path.exists():
        return ScopeConfig()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return ScopeConfig.model_validate({} if data is None else data)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise TriageError(f"{path}: invalid scope config: {exc}") from exc


def default_board_name(scope: Scope) -> str:
    """`<repo> batches`, `<owner> batches`, or `<scope name> batches` (R14)."""
    if scope.kind == "repo":
        return f"{scope.target.split('/', 1)[1]} batches"
    if scope.kind == "org":
        return f"{scope.target} batches"
    return f"{scope.name} batches"


def publish_board(scope: Scope, config: ScopeConfig, board: Path) -> str | None:
    """Run the scope's `publish` command for the rendered *board* (R14); None when it
    succeeded or there is none, else the cause of the failure on one line.

    The argument list is run as is, with no shell: `{board}`, `{name}` and `{scope_id}`
    are substituted inside each word, so a value is never parsed as syntax. A command
    that does not finish in `PUBLISH_TIMEOUT` seconds is killed. Nothing here raises:
    publishing is a view's afterthought and never changes a command's exit code."""
    if not config.publish:
        return None
    values = {
        "{board}": str(board),
        "{name}": config.board_name or default_board_name(scope),
        "{scope_id}": scope_id(scope),
    }
    argv = []
    for word in config.publish:
        for placeholder, value in values.items():
            word = word.replace(placeholder, value)
        argv.append(word)
    try:
        done = subprocess.run(  # noqa: S603 - an argument list, never a shell string
            argv, capture_output=True, text=True, timeout=PUBLISH_TIMEOUT, check=False
        )
    except subprocess.TimeoutExpired:
        return f"`{argv[0]}` timed out after {PUBLISH_TIMEOUT:g}s"
    except OSError as exc:
        return f"`{argv[0]}` could not run: {exc}"
    if done.returncode == 0:
        return None
    tail = " ".join(done.stderr.split())[:200]
    return f"`{argv[0]}` failed (exit {done.returncode})" + (f": {tail}" if tail else "")
