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
import json
import os
import re
import secrets
import tempfile
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fr.forgeapi import ForgeApi
from fr.isolation.types import _home
from fr.triage.errors import TriageError
from fr.triage.gitseam import run_publish
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
    # The scope's durable settings (cloud-triage §B): their home is `scope-durable.yaml`,
    # which rides on the state ref; `state_repo` is mirrored here, `forge_api` may be.
    state_repo: str | None = None
    forge_api: ForgeApi | None = None


SCOPE_DURABLE_FILE = "scope-durable.yaml"


class ScopeDurable(BaseModel):
    """`<state dir>/scope-durable.yaml`: the settings a scope keeps on its state ref, so a
    fresh workspace recovers them (cloud-triage R5-R7, §B): where the ref lives, and the
    forge API the scope's driver talks to."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_repo: str | None = None
    forge_api: ForgeApi | None = None


def load_durable(state_dir: Path) -> ScopeDurable:
    """The durable settings in *state_dir*; the defaults when there are none."""
    path = state_dir / SCOPE_DURABLE_FILE
    if not path.exists():
        return ScopeDurable()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return ScopeDurable.model_validate({} if data is None else data)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise TriageError(f"{path}: invalid {SCOPE_DURABLE_FILE}: {exc}") from exc


def write_durable(state_dir: Path, durable: ScopeDurable) -> None:
    """Write *durable* to `<state_dir>/scope-durable.yaml` (fr's own file, rewritten whole)."""
    from fr.artifacts.atomic import write_text_atomic

    state_dir.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(durable.model_dump(exclude_none=True), sort_keys=False)
    write_text_atomic(state_dir / SCOPE_DURABLE_FILE, "" if body == "{}\n" else body)


_STATE_REPO_LINE = re.compile(r"^state_repo:.*$", re.M)


def mirror_state_repo(state_dir: Path, state_repo: str) -> None:
    """Set `state_repo:` in the host's `scope.yaml`, keeping every other line (the operator's
    comments included): the one line is replaced, or appended when absent."""
    from fr.artifacts.atomic import write_text_atomic

    path = state_dir / SCOPE_CONFIG_FILE
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    line = f"state_repo: {json.dumps(state_repo)}"
    if _STATE_REPO_LINE.search(text):
        text = _STATE_REPO_LINE.sub(lambda _m: line, text, count=1)
    else:
        text += ("" if not text or text.endswith("\n") else "\n") + line + "\n"
    state_dir.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, text)
    load_scope_config(state_dir)  # the file must still load


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


_PLACEHOLDER = re.compile(r"\{(board|name|scope_id)\}")


def publish_board(scope: Scope, config: ScopeConfig, board: Path) -> str | None:
    """Run the scope's `publish` command for the rendered *board* (R14); None when it
    succeeded or there is none, else the cause of the failure on one line.

    The argument list is run as is, with no shell: `{board}`, `{name}` and `{scope_id}`
    are substituted inside each word in one pass (a value that itself contains a
    placeholder is not expanded again; other braces stay literal), so a value is never
    parsed as syntax. The command runs with the operator's full environment and with
    the scope's state directory (the board's own) as its working directory. A command
    that does not finish in `PUBLISH_TIMEOUT` seconds is killed. A failing command
    returns its cause rather than raising; `scope_id()` and `default_board_name()` can
    raise `TriageError`, which the caller (`triage_kanban_cmd.publish`) turns into a
    warning, so publishing never changes a command's exit code."""
    if not config.publish:
        return None
    values = {
        "board": str(board),
        "name": config.board_name or default_board_name(scope),
        "scope_id": scope_id(scope),
    }
    argv = [_PLACEHOLDER.sub(lambda m: values[m.group(1)], word) for word in config.publish]
    return run_publish(argv, board.parent, PUBLISH_TIMEOUT)
