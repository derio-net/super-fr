"""The op carriers (spec 2026-10-22-fr-ops R2, §B).

A plan's ops come from `ops.yaml` in the plan folder (canonical, read through
`Op`) and from fenced YAML blocks in step text whose first non-blank line is
`# manual-operation` (back-compat, dedented, read through `LegacyOp`). The repo
runbook named by `.fr/ops.yaml` is read through `LegacyOp` too, but only into an
explicit selection: `runbook=True`, an id in `ids`, or an id a plan op names in
`needs`. It is never read for a default selection that needs nothing from it.

Every error names a file and a line. Fences are tracked with `fr.spec.FENCE_RE`,
which is anchored at the line start: a fence named mid-prose never opens one.
"""

from __future__ import annotations

import textwrap
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError

from fr.ops.model import LegacyOp, Op

OPS_FILE = "ops.yaml"
CONFIG_REL = Path(".fr/ops.yaml")
MARKER = "# manual-operation"


class OpsLoadError(Exception):
    """An op carrier could not be read; the message names the file and line."""


@dataclass(frozen=True)
class LoadedOp:
    """One op and where it came from."""

    op: Op
    source: Path
    line: int
    legacy_done: bool = False
    runbook: bool = False

    @property
    def where(self) -> str:
        return f"{self.source}:{self.line}"


@dataclass(frozen=True)
class OpSet:
    """The selected ops, in carrier order, plus any warnings the load raised."""

    ops: tuple[LoadedOp, ...]
    warnings: tuple[str, ...] = ()

    def get(self, op_id: str) -> LoadedOp | None:
        return next((lo for lo in self.ops if lo.op.id == op_id), None)


# --- .fr/ops.yaml ------------------------------------------------------------


class IdentityRef(BaseModel):
    """`{from: '<cmd>'}`: a credential read live, never inlined (R5)."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    from_: StrictStr = Field(alias="from", min_length=1)


class Identity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    env: dict[StrictStr, IdentityRef] = {}


class OpsConfig(BaseModel):
    """`.fr/ops.yaml`: the runbook path and the identities a check runs as."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    runbook: StrictStr | None = None
    identities: dict[StrictStr, Identity] = {}


def load_ops_config(repo_root: Path) -> OpsConfig:
    """The repo's `.fr/ops.yaml`, or an empty config when there is none."""
    path = repo_root / CONFIG_REL
    if not path.is_file():
        return OpsConfig()
    data = _safe_load(path.read_text(), path, 0)
    try:
        return OpsConfig.model_validate(data or {})
    except ValidationError as e:
        raise OpsLoadError(f"{path}: {_first_error(e)}") from None


# --- helpers -----------------------------------------------------------------


def _yaml_error(e: yaml.YAMLError, path: Path, line_offset: int) -> OpsLoadError:
    mark = getattr(e, "problem_mark", None)
    line = line_offset + (mark.line + 1 if mark is not None else 1)
    problem = getattr(e, "problem", None) or str(e)
    return OpsLoadError(f"{path}:{line}: malformed YAML: {problem}")


def _safe_load(text: str, path: Path, line_offset: int) -> Any:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise _yaml_error(e, path, line_offset) from None


def _compose(text: str, path: Path) -> yaml.Node | None:
    try:
        node: yaml.Node | None = yaml.compose(text, Loader=yaml.SafeLoader)
    except yaml.YAMLError as e:
        raise _yaml_error(e, path, 0) from None
    return node


def _first_error(e: ValidationError) -> str:
    err = e.errors()[0]
    loc = ".".join(str(p) for p in err["loc"])
    return f"{loc}: {err['msg']}" if loc else err["msg"]


def _key_line(node: yaml.Node | None, key: object, fallback: int) -> int:
    """The 1-based line of `key` in a mapping node, else `fallback`."""
    if isinstance(node, yaml.MappingNode):
        for k, _ in node.value:
            if k.value == key:
                return int(k.start_mark.line) + 1
    return fallback


def _validate(
    model: type[Op] | type[LegacyOp],
    data: object,
    path: Path,
    line: int,
    node: yaml.Node | None = None,
) -> Op | LegacyOp:
    if not isinstance(data, dict):
        raise OpsLoadError(f"{path}:{line}: an op must be a mapping")
    try:
        return model.model_validate(data)
    except ValidationError as e:
        err = e.errors()[0]
        key = err["loc"][0] if err["loc"] else None
        at = _key_line(node, key, line)
        raise OpsLoadError(f"{path}:{at}: op {data.get('id', '?')!r}: {_first_error(e)}") from None


def _to_loaded(parsed: Op | LegacyOp, path: Path, line: int, *, runbook: bool) -> LoadedOp:
    if isinstance(parsed, LegacyOp):
        op, done = parsed.to_op()
        return LoadedOp(op, path, line, legacy_done=done, runbook=runbook)
    return LoadedOp(parsed, path, line, runbook=runbook)


# --- carriers ----------------------------------------------------------------


def _ops_yaml(plan_dir: Path) -> list[LoadedOp]:
    path = plan_dir / OPS_FILE
    if not path.is_file():
        return []
    root = _compose(path.read_text(), path)
    data = _safe_load(path.read_text(), path, 0) or {}
    if not isinstance(data, dict):
        raise OpsLoadError(f"{path}:1: expected `schema_version` and `ops:`")
    unknown = sorted(set(data) - {"schema_version", "ops"})
    if unknown:
        raise OpsLoadError(
            f"{path}:{_key_line(root, unknown[0], 1)}: unknown key {unknown[0]!r} "
            "(expected `schema_version` and `ops:`)"
        )
    items = data.get("ops") or []
    if not isinstance(items, list):
        raise OpsLoadError(f"{path}:{_key_line(root, 'ops', 1)}: `ops:` must be a list")
    nodes = _seq_nodes(_value_node(root, "ops"))
    out = []
    for i, item in enumerate(items):
        node = nodes[i] if i < len(nodes) else None
        line = int(node.start_mark.line) + 1 if node is not None else 1
        out.append(_to_loaded(_validate(Op, item, path, line, node), path, line, runbook=False))
    return out


def _value_node(node: yaml.Node | None, key: str) -> yaml.Node | None:
    if isinstance(node, yaml.MappingNode):
        for k, v in node.value:
            if k.value == key:
                found: yaml.Node = v
                return found
    return None


def _seq_nodes(node: yaml.Node | None) -> list[yaml.Node]:
    return list(node.value) if isinstance(node, yaml.SequenceNode) else []


def _phase_files(plan_dir: Path) -> list[Path]:
    from fr.parser import _PHASE_FILE_RE

    return sorted(p for p in plan_dir.iterdir() if _PHASE_FILE_RE.match(p.name))


def _step_text_nodes(root: yaml.Node | None) -> Iterator[yaml.ScalarNode]:
    for task in _seq_nodes(_value_node(root, "tasks")):
        for step in _seq_nodes(_value_node(task, "steps")):
            text = _value_node(step, "text")
            if isinstance(text, yaml.ScalarNode):
                yield text


def _text_first_line(node: yaml.ScalarNode) -> int:
    """The 1-based file line of the scalar's first content line: a block scalar's
    content starts on the line after its `|`/`>` indicator."""
    start = int(node.start_mark.line) + 1
    return start + 1 if node.style in ("|", ">") else start


def manual_operation_blocks(text: str) -> Iterator[tuple[int, str]]:
    """`(0-based line of the marker, dedented block)` for each fenced block in
    `text` whose first non-blank line is `# manual-operation`."""
    from fr.spec import FENCE_RE

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if not FENCE_RE.match(lines[i]):
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not FENCE_RE.match(lines[j]):
            j += 1
        body = lines[i + 1 : j]
        first = next((k for k, line in enumerate(body) if line.strip()), None)
        if first is not None and body[first].strip() == MARKER:
            yield i + 1 + first, textwrap.dedent("\n".join(body))
        i = j + 1


def _step_blocks(plan_dir: Path) -> list[LoadedOp]:
    out: list[LoadedOp] = []
    for path in _phase_files(plan_dir):
        text = path.read_text()
        if MARKER not in text:
            continue
        for node in _step_text_nodes(_compose(text, path)):
            base = _text_first_line(node)
            for offset, block in manual_operation_blocks(node.value):
                line = base + offset
                data = _safe_load(block, path, line - 1)
                for item in data if isinstance(data, list) else [data]:
                    parsed = _validate(LegacyOp, item, path, line)
                    out.append(_to_loaded(parsed, path, line, runbook=False))
    return out


def _runbook(repo_root: Path, config: OpsConfig) -> list[LoadedOp]:
    if config.runbook is None:
        return []
    path = repo_root / config.runbook
    if not path.is_file():
        raise OpsLoadError(f"{repo_root / CONFIG_REL}:1: runbook {config.runbook} does not exist")
    text = path.read_text()
    root = _compose(text, path)
    data = _safe_load(text, path, 0)
    items_node = root
    if isinstance(data, dict):
        key = "ops" if "ops" in data else "operations"
        items_node = _value_node(root, key)
        data = data.get(key)
    if not isinstance(data, list):
        raise OpsLoadError(f"{path}:1: a runbook is a list of operations")
    nodes = _seq_nodes(items_node)
    out = []
    for i, item in enumerate(data):
        node = nodes[i] if i < len(nodes) else None
        line = int(node.start_mark.line) + 1 if node is not None else 1
        parsed = _validate(LegacyOp, item, path, line, node)
        out.append(_to_loaded(parsed, path, line, runbook=True))
    return out


# --- selection ---------------------------------------------------------------


def load_ops(
    plan_dir: Path, repo_root: Path, *, runbook: bool = False, ids: tuple[str, ...] = ()
) -> OpSet:
    """The plan's ops in carrier order (`ops.yaml`, then phase files), plus the
    runbook ops the selection asks for. `ids` restricts the result to the named
    ops, which may be runbook ops."""
    plan_ops = _ops_yaml(plan_dir) + _step_blocks(plan_dir) if plan_dir.is_dir() else []
    seen: dict[str, LoadedOp] = {}
    for lo in plan_ops:
        prior = seen.get(lo.op.id)
        if prior is not None:
            raise OpsLoadError(f"op {lo.op.id!r} is defined twice: {prior.where} and {lo.where}")
        seen[lo.op.id] = lo

    wanted_from_runbook = {n for lo in plan_ops for n in lo.op.needs if n not in seen}
    wanted_from_runbook |= {i for i in ids if i not in seen}
    warnings: list[str] = []
    selected = list(plan_ops)
    if runbook or wanted_from_runbook:
        book: dict[str, LoadedOp] = {}
        for lo in _runbook(repo_root, load_ops_config(repo_root)):
            if lo.op.id in seen:
                warnings.append(
                    f"plan op {lo.op.id!r} ({seen[lo.op.id].where}) shadows the runbook "
                    f"op of the same id ({lo.where})"
                )
                continue
            book[lo.op.id] = lo
        pulled = set(book) if runbook else _needs_closure(wanted_from_runbook, book)
        selected += [lo for oid, lo in book.items() if oid in pulled]

    if ids:
        known = {lo.op.id for lo in selected}
        missing = [i for i in ids if i not in known]
        if missing:
            raise OpsLoadError(f"no op {', '.join(map(repr, missing))} in the plan or runbook")
        selected = [lo for lo in selected if lo.op.id in ids]
    return OpSet(tuple(selected), tuple(warnings))


def _needs_closure(start: set[str], book: dict[str, LoadedOp]) -> set[str]:
    """`start` plus every runbook op they need, transitively (unknown ids are the
    engine's to refuse)."""
    out: set[str] = set()
    stack = [i for i in start if i in book]
    while stack:
        oid = stack.pop()
        if oid in out:
            continue
        out.add(oid)
        stack.extend(n for n in book[oid].op.needs if n in book)
    return out
