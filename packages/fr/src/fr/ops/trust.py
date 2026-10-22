"""Probe trust (spec 2026-10-22-fr-ops R19).

Probes are repo-authored code, non-mutating only by their author's contract;
trust is the operator's acceptance of that contract for one exact op set.

The fingerprint is a map of SHA-256 hashes: one per op (a stable JSON dump of its
fields), one for the `.fr/ops.yaml` settings that affect probes (`CONFIG_KEY`:
identities, env_passthrough, timeout_seconds, runbook), and one per repo file a
probe, `apply`/`undo` or identity `from:` names by path (`file:<path>`, its
content), so editing a referenced script moves it. The set hash is the SHA-256 of
that map.

A grant is stored per operator OUTSIDE the repo (`trust_dir()`), because anything a
checkout carries a PR author can forge: a committed `op-trust` decision with a
matching hash must grant nothing. The plan journal gets an `op-trust-<n>` decision
for audit only; nothing reads it back.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from fr.journal.model import (
    OP_TRUST_ID_RE,
    JournalEntry,
    append_journal_entry,
    journal_now,
    journal_path,
    parse_journal,
)
from fr.ops.load import LoadedOp, OpsConfig

CONFIG_KEY = "settings:.fr/ops.yaml"
FILE_PREFIX = "file:"
PROBE_FIELDS = ("check", "na_if", "ready", "escalate", "apply", "undo")
"""The op fields whose text runs (or is offered to run), shown by `fr ops trust`."""
TRUST_DIR_ENV = "FR_OPS_TRUST_DIR"
_PLANS_REL = Path("docs/superpowers/plans")


def _sha(data: object) -> str:
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


# --- the fingerprint ---------------------------------------------------------


def _texts(ops: Iterable[LoadedOp], config: OpsConfig) -> list[str]:
    """Every shell text that runs: each op's probe fields, and identity references."""
    out: list[str] = []
    for lo in ops:
        for name in PROBE_FIELDS:
            value = getattr(lo.op, name)
            if isinstance(value, str):
                out.append(value)
    for identity in config.identities.values():
        out += [ref.from_ for ref in identity.env.values()]
    return out


def _tokens(text: str) -> list[str]:
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return text.split()


def referenced_files(texts: Iterable[str], repo_root: Path) -> list[str]:
    """Repo-relative paths of the regular files inside `repo_root` that a token of
    `texts` names (relative to the repo root, or absolute)."""
    root = repo_root.resolve()
    found: set[str] = set()
    for text in texts:
        for token in _tokens(text):
            if not token or token.startswith("-"):
                continue
            try:
                path = (root / token).resolve()
                if path.is_file() and path.is_relative_to(root):
                    found.add(path.relative_to(root).as_posix())
            except (OSError, ValueError):
                continue
    return sorted(found)


def settings_dump(config: OpsConfig) -> dict[str, object]:
    """The `.fr/ops.yaml` settings that change what a probe runs or sees."""
    return {
        "identities": {
            n: i.model_dump(mode="json", by_alias=True) for n, i in config.identities.items()
        },
        "env_passthrough": list(config.env_passthrough),
        "timeout_seconds": config.timeout_seconds,
        "runbook": config.runbook,
    }


def fingerprint(ops: Sequence[LoadedOp], config: OpsConfig, repo_root: Path) -> dict[str, str]:
    """`{op id: hash, CONFIG_KEY: hash, file:<path>: hash}`, sorted."""
    out: dict[str, str] = {lo.op.id: _sha(lo.op.model_dump(mode="json")) for lo in ops}
    out[CONFIG_KEY] = _sha(settings_dump(config))
    for rel in referenced_files(_texts(ops, config), repo_root):
        content = (repo_root / rel).read_bytes()
        out[f"{FILE_PREFIX}{rel}"] = hashlib.sha256(rel.encode() + b"\0" + content).hexdigest()
    return dict(sorted(out.items()))


def set_hash(fp: Mapping[str, str]) -> str:
    return _sha(dict(sorted(fp.items())))


@dataclass(frozen=True)
class Trusted:
    sha256: str
    ops: dict[str, str]
    granted: str


@dataclass(frozen=True)
class Diff:
    added: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    @property
    def untrusted(self) -> bool:
        """Code would run that the operator has not seen: something added or changed."""
        return bool(self.added or self.changed)

    def lines(self) -> list[str]:
        groups = (("added", self.added), ("changed", self.changed), ("removed", self.removed))
        return [f"{label}: {', '.join(ids)}" for label, ids in groups if ids]


def diff(current: Mapping[str, str], trusted: Trusted | None) -> Diff:
    if trusted is None:
        return Diff(added=sorted(current))
    return Diff(
        added=sorted(k for k in current if k not in trusted.ops),
        changed=sorted(k for k in current if k in trusted.ops and trusted.ops[k] != current[k]),
        removed=sorted(k for k in trusted.ops if k not in current),
    )


# --- the per-operator store --------------------------------------------------


def trust_dir() -> Path:
    """`$FR_OPS_TRUST_DIR`, else `$XDG_STATE_HOME/fr/ops-trust`, else
    `~/.local/state/fr/ops-trust`."""
    override = os.environ.get(TRUST_DIR_ENV)
    if override:
        return Path(override)
    state = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(state) / "fr" / "ops-trust"


def repo_key(repo_root: Path) -> str:
    """The origin slug lowercased with `/` -> `--`, else the toplevel's name."""
    from fr import _hosts

    slug = _hosts.origin_slug(repo_root)
    return slug.lower().replace("/", "--") if slug else repo_root.resolve().name


def store_path(repo_root: Path, plan_slug: str) -> Path:
    return trust_dir() / repo_key(repo_root) / f"{plan_slug}.json"


def load_trust(repo_root: Path, plan_slug: str) -> Trusted | None:
    """The operator's grant for this plan, from the store; never from the repo."""
    path = store_path(repo_root, plan_slug)
    try:
        data = json.loads(path.read_text())
        return Trusted(
            sha256=str(data["sha256"]), ops=dict(data["ops"]), granted=str(data["granted"])
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write_private(path: Path, text: str) -> None:
    """Write `text` to `path` atomically, mode 0600."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def grant_trust(repo_root: Path, plan_slug: str, fp: Mapping[str, str]) -> JournalEntry:
    """Store the grant for this operator, then append the audit decision."""
    if not (repo_root / _PLANS_REL / plan_slug).is_dir():
        raise ValueError(f"no plan {plan_slug!r} to record trust against")
    now = journal_now()
    record = {"sha256": set_hash(fp), "ops": dict(sorted(fp.items())), "granted": now}
    _write_private(store_path(repo_root, plan_slug), json.dumps(record, indent=2) + "\n")
    path = journal_path(repo_root, "plan", plan_slug)
    prior = parse_journal(path.read_text()) if path.is_file() else []
    taken = [int(m.group(1)) for e in prior if (m := OP_TRUST_ID_RE.match(e.id))]
    entry = JournalEntry(
        kind="decision",
        scope="plan",
        id=f"op-trust-{max(taken, default=0) + 1}",
        created=now,
        title="op-trust: the operator trusted this op set (audit only; never read back)",
        body=f"sha256: {set_hash(fp)}",
        decided_by="operator",
    )
    append_journal_entry(path, plan_slug, entry)
    return entry


# --- what the operator is shown ---------------------------------------------


def describe(ops: Sequence[LoadedOp], config: OpsConfig, repo_root: Path) -> str:
    """Every probe and command text of `ops`, the probe settings, and the files the
    fingerprint hashes."""
    lines: list[str] = []
    for lo in ops:
        op = lo.op
        lines.append(f"{op.id}  [{op.phase}]  {op.summary}  ({lo.where})")
        for name in PROBE_FIELDS:
            value = getattr(op, name)
            if value is None:
                continue
            text = value if isinstance(value, str) else f"none: {value.none}"
            lines.append(f"    {name}: {text}")
        for name in ("commands", "verify"):
            value = getattr(op, name)
            for item in (value,) if isinstance(value, str) else value or ():
                lines.append(f"    {name}: {item}")
        if op.identities:
            lines.append(f"    identities: {', '.join(op.identities)}")
    settings = settings_dump(config)
    lines.append(".fr/ops.yaml settings:")
    for name, identity in config.identities.items():
        for var, ref in identity.env.items():
            lines.append(f"    identity {name}: {var} from: {ref.from_}")
    for name in ("env_passthrough", "timeout_seconds", "runbook"):
        lines.append(f"    {name}: {settings[name]}")
    files = referenced_files(_texts(ops, config), repo_root)
    lines.append("files: " + (", ".join(files) if files else "(none)"))
    return "\n".join(lines)
