"""Probe trust (spec 2026-10-22-fr-ops R19).

Probes are repo-authored code, non-mutating only by their author's contract;
trust is the operator's acceptance of that contract for one exact op set. The
set is fingerprinted per op (a SHA-256 of a stable JSON dump of its fields) and
per identity it runs as (its `from:` references), and the set hash is the
SHA-256 of that map. `fr ops trust` records it as a plan-journal `decision`
`op-trust-<n>`, whose body carries the set hash and every per-op hash, so a
later refusal can say what was added, changed or removed since.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    journal_now,
    journal_path,
    parse_journal,
)
from fr.ops.load import LoadedOp, OpsConfig

TRUST_ID_RE = re.compile(r"^op-trust-(\d+)$")
IDENTITY_PREFIX = "identity:"
PROBE_FIELDS = ("check", "na_if", "ready", "escalate", "apply", "undo")
"""The op fields whose text runs (or is offered to run), shown by `fr ops trust`."""
_PLANS_REL = Path("docs/superpowers/plans")


def _sha(data: object) -> str:
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


def fingerprint(ops: Iterable[LoadedOp], config: OpsConfig) -> dict[str, str]:
    """`{op id: hash}` plus `{identity:<name>: hash}` for every identity the ops
    run as — an undeclared one hashes as such, so declaring it later moves the set."""
    out: dict[str, str] = {}
    names: set[str] = set()
    for lo in ops:
        out[lo.op.id] = _sha(lo.op.model_dump(mode="json"))
        names |= set(lo.op.identities)
    for name in names:
        identity = config.identities.get(name)
        dump = identity.model_dump(mode="json", by_alias=True) if identity else None
        out[f"{IDENTITY_PREFIX}{name}"] = _sha(dump)
    return dict(sorted(out.items()))


def set_hash(fp: dict[str, str]) -> str:
    return _sha(dict(sorted(fp.items())))


@dataclass(frozen=True)
class Trusted:
    sha256: str
    ops: dict[str, str]
    entry_id: str


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
        return [
            f"{label}: {', '.join(ids)}"
            for label, ids in (
                ("added", self.added),
                ("changed", self.changed),
                ("removed", self.removed),
            )
            if ids
        ]


def diff(current: dict[str, str], trusted: Trusted | None) -> Diff:
    if trusted is None:
        return Diff(added=sorted(current))
    return Diff(
        added=sorted(k for k in current if k not in trusted.ops),
        changed=sorted(k for k in current if k in trusted.ops and trusted.ops[k] != current[k]),
        removed=sorted(k for k in trusted.ops if k not in current),
    )


def trust_body(fp: dict[str, str]) -> str:
    return "\n".join([f"sha256: {set_hash(fp)}", *(f"trusted: {k} {h}" for k, h in fp.items())])


def latest_trust(entries: Iterable[JournalEntry]) -> Trusted | None:
    """The last `op-trust-<n>` decision in file order, parsed."""
    found: Trusted | None = None
    for e in entries:
        if e.kind != "decision" or not TRUST_ID_RE.match(e.id):
            continue
        sha, ops = "", {}
        for line in e.body.splitlines():
            name, _, value = line.partition(": ")
            if name == "sha256":
                sha = value.strip()
            elif name == "trusted":
                key, _, h = value.strip().rpartition(" ")
                if key:
                    ops[key] = h
        found = Trusted(sha256=sha, ops=ops, entry_id=e.id)
    return found


def _entries(path: Path) -> list[JournalEntry]:
    return parse_journal(path.read_text()) if path.is_file() else []


def plan_trust(repo_root: Path, plan_slug: str) -> Trusted | None:
    from fr.journal.model import resolve_journal_read_path

    return latest_trust(_entries(resolve_journal_read_path(repo_root, "plan", plan_slug)))


def record_trust(repo_root: Path, plan_slug: str, fp: dict[str, str]) -> JournalEntry:
    """Append the next `op-trust-<n>` decision to the plan's journal."""
    if not (repo_root / _PLANS_REL / plan_slug).is_dir():
        raise ValueError(f"no plan {plan_slug!r} to record trust against")
    path = journal_path(repo_root, "plan", plan_slug)
    taken = [int(m.group(1)) for e in _entries(path) if (m := TRUST_ID_RE.match(e.id))]
    entry = JournalEntry(
        kind="decision",
        scope="plan",
        id=f"op-trust-{max(taken, default=0) + 1}",
        created=journal_now(),
        title=f"op-trust: the operator trusted {len(fp)} op probe set(s)",
        body=trust_body(fp),
        decided_by="operator",
    )
    append_journal_entry(path, plan_slug, entry)
    return entry


def describe(ops: Sequence[LoadedOp], config: OpsConfig) -> str:
    """Every probe and command text of `ops`, and every identity reference they run."""
    lines: list[str] = []
    names: list[str] = []
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
        names += [n for n in op.identities if n not in names]
    for name in names:
        identity = config.identities.get(name)
        if identity is None:
            lines.append(f"identity {name}: not declared in .fr/ops.yaml")
            continue
        for var, ref in identity.env.items():
            lines.append(f"identity {name}: {var} from: {ref.from_}")
    return "\n".join(lines)
