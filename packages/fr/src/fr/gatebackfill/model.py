"""The plan file and the operator manifest (spec 2026-11-01-gate-backfill §B, §E).

Both are strict (`extra="forbid"`, `schema: 1`). The plan file lives outside the repo, under
`$HOME/.cache/fr/gate-backfill/<owner--repo>/plan.yaml` (or `--plan`), so `fr gate` stays
forge-only (R14).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from fr.artifacts.atomic import write_text_atomic
from fr.gates import POST_MERGE_GATES

SIMPLE_DECISIONS = ("owed", "tick", "na", "park", "review")
ADOPT_RE = re.compile(r"^adopt (?P<ref>[\w.-]+/[\w.-]+#\d+)$")
KEY_RE = re.compile(
    r"^(spec:[\w.][\w.-]*#step\d+|plan:[\w.][\w.-]*#p\d+|row:[\w.][\w.-]*"
    r"|issue:[\w.][\w.-]*/[\w.-]+#\d+)$"
)


class BackfillError(ValueError):
    """A plan file, manifest or decision that cannot be used; the message names the entry."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def split_decision(decision: str) -> tuple[str, str | None]:
    """`(kind, adopt ref)` of a decision string; `BackfillError` on anything else."""
    if decision in SIMPLE_DECISIONS:
        return decision, None
    m = ADOPT_RE.match(decision)
    if m:
        return "adopt", m.group("ref")
    raise BackfillError(
        f"decision {decision!r} is not one of {', '.join(SIMPLE_DECISIONS)} or adopt <owner/repo#n>"
    )


def _post_merge(v: str | None) -> str | None:
    if v is not None and v not in POST_MERGE_GATES:
        raise ValueError(f"gate {v!r} is not one of {', '.join(sorted(POST_MERGE_GATES))}")
    return v


class PrHit(_Strict):
    """The delivering PR and how it was found (`basis`); `planning` marks a docs-only PR."""

    number: int
    basis: Literal["manifest", "run", "commit", "issue"]
    planning: bool = False


class TrackerInfo(_Strict):
    ref: str | None = None
    candidates: list[str] = Field(default_factory=list)


class PlanEntry(_Strict):
    key: str
    title: str = ""
    gate: str | None = None
    pr: PrHit | None = None
    ambiguous: list[int] = Field(default_factory=list)
    tracker: TrackerInfo = Field(default_factory=TrackerInfo)
    age_days: int | None = None
    ticked: str = ""
    walk_only: bool = False
    why: str = ""
    """Why the default decision is not `owed` (computed, refreshed on every dry run)."""
    note: str = ""
    """The operator's own note; `na` requires it as the reason (kept across dry runs)."""
    decision: str = "owed"

    @field_validator("decision")
    @classmethod
    def _decision_parses(cls, v: str) -> str:
        split_decision(v)
        return v

    @field_validator("gate")
    @classmethod
    def _gate_ok(cls, v: str | None) -> str | None:
        return _post_merge(v)

    @property
    def decision_kind(self) -> str:
        return split_decision(self.decision)[0]

    @property
    def adopt_ref(self) -> str | None:
        return split_decision(self.decision)[1]


class PlanFile(_Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal[1] = Field(default=1, alias="schema")
    repo: str
    generated_at: str = ""
    entries: list[PlanEntry] = Field(default_factory=list)


class ManifestItem(_Strict):
    key: str
    kind: Literal["closed-issue", "audit-gap", "walk", "op"]
    title: str
    issue: int | None = None
    pr: int | None = None
    gate: str | None = None
    walk_only: bool | None = None

    @field_validator("key")
    @classmethod
    def _key_shape(cls, v: str) -> str:
        if not KEY_RE.match(v):
            raise ValueError(
                f"key {v!r} is not spec:<slug>#step<n>, plan:<name>#p<n>, row:<id> or "
                "issue:<owner/repo#n>"
            )
        return v

    @field_validator("gate")
    @classmethod
    def _gate_ok(cls, v: str | None) -> str | None:
        return _post_merge(v)


class Manifest(_Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal[1] = Field(default=1, alias="schema")
    items: list[ManifestItem] = Field(default_factory=list)


def _label(raw: object, index: int) -> str:
    return str(raw.get("key", f"#{index}")) if isinstance(raw, dict) else f"#{index}"


def parse_manifest(text: str) -> Manifest:
    """Parse and validate a manifest; every refusal names the entry."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise BackfillError(f"manifest is not YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise BackfillError("manifest must be a mapping with `schema: 1` and `items:`")
    items = data.get("items") or []
    for i, raw in enumerate(items):
        if isinstance(raw, dict) and raw.get("kind") == "audit-gap" and not raw.get("gate"):
            raise BackfillError(f"manifest entry {_label(raw, i)}: an audit-gap must state `gate:`")
    try:
        manifest = Manifest.model_validate(data)
    except ValidationError as exc:
        err = exc.errors()[0]
        loc = err["loc"]
        where = ""
        if len(loc) >= 2 and loc[0] == "items" and isinstance(loc[1], int):
            raw = items[loc[1]] if loc[1] < len(items) else {}
            where = f"manifest entry {_label(raw, loc[1])}: "
        raise BackfillError(f"{where}{'.'.join(str(p) for p in loc)}: {err['msg']}") from exc
    seen: set[str] = set()
    for item in manifest.items:
        if item.key in seen:
            raise BackfillError(f"manifest entry {item.key}: listed twice")
        seen.add(item.key)
    return manifest


def merge_plan(old: PlanFile | None, fresh: list[PlanEntry]) -> list[PlanEntry]:
    """*fresh* with the operator's decisions carried over (R5): for a key still owed, an existing
    entry's `decision` (so its adopt target), `note`, and any `gate:` the operator wrote (one
    that differs from the computed gate); every other field is refreshed. A key no longer owed
    is dropped."""
    if old is None:
        return list(fresh)
    before = {e.key: e for e in old.entries}
    merged = []
    for entry in fresh:
        prev = before.get(entry.key)
        if prev is None:
            merged.append(entry)
            continue
        gate = prev.gate if prev.gate is not None and prev.gate != entry.gate else entry.gate
        merged.append(
            entry.model_copy(update={"decision": prev.decision, "note": prev.note, "gate": gate})
        )
    return merged


def plan_path(repo: str, override: Path | None) -> Path:
    """`--plan`, else `$HOME/.cache/fr/gate-backfill/<owner--repo>/plan.yaml`."""
    if override is not None:
        return override
    return Path.home() / ".cache" / "fr" / "gate-backfill" / repo.replace("/", "--") / "plan.yaml"


def load_plan(path: Path) -> PlanFile | None:
    """The plan file at *path*; `None` when absent; `BackfillError` when unreadable."""
    if not path.is_file():
        return None
    try:
        data: Any = yaml.safe_load(path.read_text())
        return PlanFile.model_validate(data)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise BackfillError(f"plan file {path} cannot be read: {exc}") from exc


def write_plan(path: Path, plan: PlanFile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = plan.model_dump(mode="json", by_alias=True)
    write_text_atomic(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
