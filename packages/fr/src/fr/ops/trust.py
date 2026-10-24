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
import stat
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from fr.journal.model import (
    OP_TRUST_ID_RE,
    JournalEntry,
    appended_journal_text,
    archived_journal_path,
    journal_now,
    journal_path,
    parse_journal,
)
from fr.ops.load import LoadedOp, OpsConfig

CONFIG_KEY = "settings:.fr/ops.yaml"
CODE_KEY = "code:tree"
"""The repo's committed tree minus `TRUST_EXCLUDED`: a probe can reach code no token
names — `make check`, `python -m pkg`, a sourced script, even a script under
`docs/superpowers/` — so any committed change outside fr's evidence files
invalidates trust. Deliberately NOT `fr.run.code_tree.code_tree`, which drops all of
`docs/superpowers/` and `docs/acceptance/`."""
TRUST_EXCLUDED: tuple[str, ...] = (
    "docs/superpowers/journals/<scope>/<slug>.md",
    "docs/superpowers/implemented/journals/<scope>/<slug>.md",
    "docs/superpowers/runs/<run-id>.yaml",
    "docs/superpowers/runs/<run-id>.records/*.yaml",
    "docs/superpowers/runs/<run-id>.records/pr-body.md",
    "docs/acceptance/matrix.yaml",
    "docs/acceptance/report_local.html",
    "docs/acceptance/report_linked.html",
    "docs/acceptance/report_linked.md",
)
"""Exactly the file SHAPES fr writes as evidence while a plan runs: a journal one level
under specs|plans|debug, a run cursor, a step record, a PR body, the acceptance matrix
and its reports. Never a whole prefix, and never an executable or a symlink."""
FILE_PREFIX = "file:"
PROBE_FIELDS = ("check", "na_if", "ready", "escalate", "apply", "undo")
"""The op fields whose text runs (or is offered to run), shown by `fr ops trust`."""
TRUST_DIR_ENV = "FR_OPS_TRUST_DIR"


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


def fingerprint(
    ops: Sequence[LoadedOp],
    config: OpsConfig,
    repo_root: Path,
    *,
    code_tree: str | None = None,
) -> dict[str, str]:
    """`{op id: hash, CONFIG_KEY: hash, file:<path>: hash}` plus `CODE_KEY` when a
    `code_tree` is given (`tree_digest(head_tree(...))`), sorted. A token-referenced
    file is hashed even when it is one of `TRUST_EXCLUDED`."""
    out: dict[str, str] = {lo.op.id: _sha(lo.op.model_dump(mode="json")) for lo in ops}
    out[CONFIG_KEY] = _sha(settings_dump(config))
    if code_tree is not None:
        out[CODE_KEY] = code_tree
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
    tree: dict[str, str] = field(default_factory=dict)
    """`path -> blob oid` of the trusted tree, to name what changed since."""


# --- the committed tree -------------------------------------------------------


_ACCEPTANCE = frozenset(
    {
        "docs/acceptance/matrix.yaml",
        "docs/acceptance/report_local.html",
        "docs/acceptance/report_linked.html",
        "docs/acceptance/report_linked.md",
    }
)
_JOURNAL_SCOPES = frozenset({"specs", "plans", "debug"})
_RISKY_MODES = frozenset({"120000", "100755"})


def is_trust_excluded(path: str, mode: str | None = None) -> bool:
    """`path` (repo-relative, `/`-separated) is a file of a shape fr writes as evidence,
    and (when its git `mode` is known) is neither a symlink nor executable."""
    if mode in _RISKY_MODES:
        return False
    if path in _ACCEPTANCE:
        return True
    parts = path.split("/")
    if (
        parts[:3] == ["docs", "superpowers", "implemented"]
        and len(parts) == 6
        and parts[3] == "journals"
        and parts[4] in _JOURNAL_SCOPES
        and parts[5].endswith(".md")
    ):
        return True
    if parts[:2] == ["docs", "superpowers"] and len(parts) >= 4:
        if parts[2] == "journals":
            return len(parts) == 5 and parts[3] in _JOURNAL_SCOPES and parts[4].endswith(".md")
        if parts[2] == "runs":
            if len(parts) == 4:
                return parts[3].endswith(".yaml")
            if len(parts) == 5 and parts[3].endswith(".records"):
                return parts[4].endswith(".yaml") or parts[4] == "pr-body.md"
    return False


def head_tree(repo_root: Path) -> dict[str, str]:
    """`path -> blob oid` of HEAD, `TRUST_EXCLUDED` removed; empty for an unborn HEAD.
    Raises `GitUnavailableError` when git cannot list a HEAD that exists."""
    from fr.git import GitUnavailableError, git_answer

    if git_answer(repo_root, "rev-parse", "--verify", "-q", "HEAD").returncode != 0:
        return {}
    res = git_answer(repo_root, "ls-tree", "-r", "-z", "--full-tree", "HEAD")
    if res.returncode != 0:
        raise GitUnavailableError(f"`git ls-tree` failed: {res.stderr.strip()}")
    tree: dict[str, str] = {}
    for entry in res.stdout.split("\0"):
        meta, _, path = entry.partition("\t")
        if path and not is_trust_excluded(path, meta.split()[0]):
            tree[path] = meta.split()[-1]
    return dict(sorted(tree.items()))


def tree_digest(tree: Mapping[str, str]) -> str:
    """sha256 over the sorted `(path, oid)` pairs."""
    pairs = "\0".join(f"{path} {oid}" for path, oid in sorted(tree.items()))
    return hashlib.sha256(pairs.encode()).hexdigest()


def _disk_mode(repo_root: Path, path: str) -> str | None:
    """The git-style mode of what is on disk now (`None` when the path is gone)."""
    try:
        st = (repo_root / path).lstat()
    except OSError:
        return None
    if stat.S_ISLNK(st.st_mode):
        return "120000"
    return "100755" if st.st_mode & 0o111 else "100644"


def dirty_paths(repo_root: Path) -> list[str]:
    """Uncommitted paths outside `TRUST_EXCLUDED` — modified, staged, deleted or
    untracked (not ignored), sorted."""
    from fr.git import GitUnavailableError, git_answer

    res = git_answer(
        repo_root, "status", "--porcelain=v1", "-z", "--no-renames", "--untracked-files=all"
    )
    if res.returncode != 0:
        raise GitUnavailableError(f"`git status` failed: {res.stderr.strip()}")
    paths = {e[3:] for e in res.stdout.split("\0") if len(e) > 3}
    return sorted(p for p in paths if not is_trust_excluded(p, _disk_mode(repo_root, p)))


def tree_changes(old: Mapping[str, str], new: Mapping[str, str]) -> list[str]:
    """Paths added, removed or changed between two trees, sorted."""
    return sorted(p for p in set(old) | set(new) if old.get(p) != new.get(p))


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
            sha256=str(data["sha256"]),
            ops=dict(data["ops"]),
            granted=str(data["granted"]),
            tree=dict(data.get("tree") or {}),
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


def grant_trust(
    repo_root: Path,
    plan_slug: str,
    fp: Mapping[str, str],
    *,
    tree: Mapping[str, str] | None = None,
) -> JournalEntry:
    """Store the grant for one unambiguous active or archived plan, then audit it."""
    if (
        not plan_slug
        or plan_slug in {".", ".."}
        or Path(plan_slug).name != plan_slug
        or "/" in plan_slug
        or "\\" in plan_slug
        or any(ch.isspace() for ch in plan_slug)
    ):
        raise ValueError(f"invalid plan slug {plan_slug!r}")

    from fr.refs import resolve_plan_ref

    root = repo_root.resolve()
    resolution = resolve_plan_ref(plan_slug, root)
    # Check every match, not just the preferred one: ambiguity and symlink
    # aliases must never silently select a trust target.
    for candidate in resolution.matches:
        resolved = candidate.resolve()
        current = root
        has_symlink = False
        for part in candidate.relative_to(root).parts:
            current /= part
            has_symlink = has_symlink or current.is_symlink()
        if not resolved.is_relative_to(root) or has_symlink:
            raise ValueError(f"plan {plan_slug!r} resolves through an unsafe path")
    if len(resolution.matches) > 1:
        raise ValueError(f"multiple active or archived plans named {plan_slug!r}")
    if resolution.path is None:
        raise ValueError(f"no plan {plan_slug!r} to record trust against")

    plan_dir = resolution.path
    plan_root = plan_dir.parent.relative_to(root / "docs/superpowers").as_posix()
    archived = plan_root != "plans"
    path = (
        archived_journal_path(root, "plan", plan_slug)
        if archived
        else journal_path(root, "plan", plan_slug)
    )
    other_path = (
        journal_path(root, "plan", plan_slug)
        if archived
        else archived_journal_path(root, "plan", plan_slug)
    )
    if other_path.exists():
        raise ValueError(f"multiple active or archived plan journals named {plan_slug!r}")
    prior_text = path.read_text() if path.is_file() else None
    prior = parse_journal(prior_text) if prior_text is not None else []
    now = journal_now()
    record = {
        "sha256": set_hash(fp),
        "ops": dict(sorted(fp.items())),
        "granted": now,
        "tree": dict(sorted((tree or {}).items())),
    }
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
    from fr.artifacts.atomic import write_text_atomic

    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, appended_journal_text(prior_text, plan_slug, entry))
    try:
        _write_private(store_path(root, plan_slug), json.dumps(record, indent=2) + "\n")
    except BaseException:
        if prior_text is None:
            path.unlink(missing_ok=True)
        else:
            write_text_atomic(path, prior_text)
        raise
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
