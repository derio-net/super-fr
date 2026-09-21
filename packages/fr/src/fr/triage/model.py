"""Triage state: scope, state directory, and the two files (spec §3.B, §3.D).

`facts.json` is what `collect` read from the forge; `judgements.yaml` is the
agent's half. Both carry `schema: 1`, and a reader refuses any other value with
a message naming the file rather than guessing. Neither is an artifact kind:
they live under fr's cache root, never in a repo.

`Scope` is the ONE home of scope naming, and `state_dir` the one home of the
state directory, so the command and the directory can never disagree.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from fr.isolation.types import _home
from fr.triage.errors import TriageError
from fr.triage.stage import Stage, derive_stage

SCHEMA: Literal[1] = 1

ScopeKind = Literal["repo", "org"]
Cx = Literal["XS", "S", "S-M", "M", "L", "-"]
PrState = Literal["OPEN", "CLOSED", "MERGED"]
IssueState = Literal["open", "closed"]
TruncatedList = Literal["repos", "issues", "prs"]

# "<repo-name>#<number>" in both scopes (spec §3.D): one code path.
KEY_RE = re.compile(r"^[A-Za-z0-9._-]+#[0-9]+$")


def normalize_key(key: str) -> str:
    """The canonical form of a judgement key: lowercase (spec §3.D, review r-p2-case).

    GitHub repo names are case-insensitive, so `Super-FR#5` and `super-fr#5`
    are one issue. EVERY key — built by `issue_key`, loaded from
    `judgements.yaml`, passed to `collect` — goes through here, and `check` and
    `render` compare through it too. One function, so no two readers disagree.
    """
    return key.lower()


@dataclass(frozen=True)
class Scope:
    """What is being triaged: one repo, or every non-archived repo of an owner."""

    kind: ScopeKind
    target: str  # "OWNER/REPO" for a repo, "OWNER" for an org

    @property
    def name(self) -> str:
        """Directory-safe scope name: `<owner>--<repo>` or `<owner>` (spec §3.B).

        Lowercase, so `--repo Derio-Net/Super-FR` names the same state
        directory as `--repo derio-net/super-fr` (review r-p2-case).
        """
        return self.target.replace("/", "--").lower()

    @property
    def owner(self) -> str:
        return self.target.split("/", 1)[0]


def state_dir(scope: Scope, override: Path | None = None) -> Path:
    """`--dir` if given, else `$HOME/.cache/fr/triage/<scope>/` — fr's cache root.

    Resolved through `_home()` like every other fr cache path; `XDG_CACHE_HOME`
    is deliberately not read (spec-review r1).
    """
    if override is not None:
        return override
    return _home() / ".cache" / "fr" / "triage" / scope.name


def issue_key(repo: str, number: int) -> str:
    """The judgement key for `OWNER/REPO` issue *number*: `<repo-name>#<number>`, normalised."""
    return normalize_key(f"{repo.split('/', 1)[-1]}#{number}")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


# ---------------------------------------------------------------- facts.json


class PullRequest(_Strict):
    repo: str  # OWNER/REPO the PR lives in — not necessarily the issue's
    number: int
    title: str
    state: PrState
    is_draft: bool
    merged_at: str | None = None
    url: str
    head_ref: str = ""


class Issue(_Strict):
    repo: str  # OWNER/REPO
    number: int
    title: str
    state: IssueState
    labels: list[str] = []
    url: str
    created_at: str | None = None
    updated_at: str | None = None
    closed_at: str | None = None
    body: str = ""
    prs: list[PullRequest] = []  # most advanced first

    @property
    def key(self) -> str:
        return issue_key(self.repo, self.number)

    @property
    def stage(self) -> Stage:
        """Derived from the facts on every read, never stored (spec §3.E)."""
        return derive_stage(self, self.prs)


class Skipped(_Strict):
    repo: str
    reason: str


class Truncation(_Strict):
    """A list that returned exactly its limit, so it may have been cut short."""

    source: TruncatedList
    target: str  # the repo (issues, prs) or owner (repos) listed
    limit: int


class Facts(_Strict):
    schema_: Literal[1] = Field(1, alias="schema")
    scope: str
    kind: ScopeKind
    collected_at: str
    repos: list[str]
    issues: list[Issue]
    skipped: list[Skipped] = []
    warnings: list[Truncation] = []

    def to_json(self) -> dict[str, Any]:
        """The `facts.json` document, with `schema` spelled as on disk."""
        return self.model_dump(mode="json", by_alias=True)


# ----------------------------------------------------------- judgements.yaml


class Tier(_Strict):
    n: int
    title: str
    description: str = ""


class Judgement(_Strict):
    tier: int
    theme: str = ""
    cx: Cx = "-"
    verified: bool = False
    detail: str = ""
    note: str = ""


class Pattern(_Strict):
    title: str
    ids: list[str] = []
    body: str = ""


class Judgements(_Strict):
    schema_: Literal[1] = Field(1, alias="schema")
    ranked_at: date | None = None
    tiers: list[Tier] = []
    issues: dict[str, Judgement] = {}
    patterns: list[Pattern] = []

    @field_validator("issues", mode="before")
    @classmethod
    def _keys_are_repo_hash_number(cls, v: object) -> object:
        """Validate the key grammar, then normalise; a case-only collision is a conflict."""
        if not isinstance(v, dict):
            return v  # pydantic reports the wrong type
        bad = [k for k in v if not isinstance(k, str) or not KEY_RE.match(k)]
        if bad:
            raise ValueError(f"judgement keys must be '<repo-name>#<number>', got {bad!r}")
        out: dict[str, object] = {}
        seen: dict[str, str] = {}
        for key, value in v.items():
            canon = normalize_key(key)
            if canon in seen:
                raise ValueError(
                    f"judgement keys {seen[canon]!r} and {key!r} conflict: keys are "
                    "case-insensitive, so they name the same issue"
                )
            seen[canon] = key
            out[canon] = value
        return out

    @model_validator(mode="after")
    def _tiers_are_declared(self) -> Judgements:
        declared = {t.n for t in self.tiers}
        undeclared = sorted({j.tier for j in self.issues.values()} - declared)
        if undeclared:
            raise ValueError(f"judgements name undeclared tiers {undeclared}")
        return self


# ------------------------------------------------------------------- loaders


def _check_schema(path: Path, data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TriageError(f"{path}: expected a mapping at the top level")
    if data.get("schema") != SCHEMA:
        raise TriageError(
            f"{path}: unsupported schema {data.get('schema')!r} (this fr reads schema {SCHEMA})"
        )
    return data


def load_facts(path: Path) -> Facts:
    """Read `facts.json`, refusing a bad schema or shape with *path* in the message."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TriageError(f"{path}: cannot read facts: {exc}") from exc
    try:
        return Facts.model_validate(_check_schema(path, data))
    except ValidationError as exc:
        raise TriageError(f"{path}: invalid facts: {exc}") from exc


def load_judgements(path: Path) -> Judgements:
    """Read `judgements.yaml`, refusing a bad schema or shape with *path* in the message."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TriageError(f"{path}: cannot read judgements: {exc}") from exc
    try:
        return Judgements.model_validate(_check_schema(path, data))
    except ValidationError as exc:
        raise TriageError(f"{path}: invalid judgements: {exc}") from exc
