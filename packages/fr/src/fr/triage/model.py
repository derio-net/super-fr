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

FACTS_SCHEMA: Literal[3] = 3
# The version this fr WRITES. Stays 1 until the first engine write of a batch
# (plan phase 2); the loader already reads every version in JUDGEMENTS_READS.
JUDGEMENTS_SCHEMA: Literal[1] = 1
JUDGEMENTS_READS: tuple[int, ...] = (1, 2)

ScopeKind = Literal["repo", "org"]
Cx = Literal["XS", "S", "S-M", "M", "L", "-"]
PrState = Literal["OPEN", "CLOSED", "MERGED"]
IssueState = Literal["open", "closed"]
TruncatedList = Literal["repos", "issues", "prs"]
AnchorKind = Literal["issue", "spec", "debug", "unanchored"]
Delivery = Literal["delivers", "partial", "drift", "unanchored"]

# The hidden first line of the comment a batch dispatch posts on each member
# (spec 2026-09-25-triage-batches §3.E). `collect` dates a dispatch by it, so the
# grammar lives here, beside the field it fills. A withdrawal uses a DIFFERENT
# prefix: `<!-- fr-batch:` never matches `<!-- fr-batch-withdrawn:`.
BATCH_MARKER_PREFIX = "<!-- fr-batch:"
WITHDRAWN_MARKER_PREFIX = "<!-- fr-batch-withdrawn:"


def batch_marker(item_id: str) -> str:
    """The dispatch marker for the run item *item_id* (`<repo>/run/batch-<id>`)."""
    return f"{BATCH_MARKER_PREFIX}{item_id} -->"


def withdrawn_marker(item_id: str) -> str:
    """The marker that opens a `batch cancel` comment for *item_id*."""
    return f"{WITHDRAWN_MARKER_PREFIX}{item_id} -->"


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


def _bad_keys(keys: list[object]) -> list[object]:
    """The entries of *keys* that do not match the key grammar `<repo-name>#<number>`."""
    return [k for k in keys if not isinstance(k, str) or not KEY_RE.match(k)]


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
    head_oid: str = ""  # open PRs only (the open-PR list carries headRefOid)
    files: list[str] = []  # open PRs only: the paths the PR touches
    checks: dict[str, int] = {"pass": 0, "fail": 0, "pending": 0}
    mergeable: str = "UNKNOWN"
    merge_state: str = "UNKNOWN"
    review: str | None = None
    anchor: AnchorKind = "unanchored"
    anchor_path: str | None = None
    anchor_body: str = ""
    anchor_reason: str | None = None


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
    # createdAt of the latest fr-batch dispatch marker comment; read only for
    # issues labelled fr:in-progress (spec §3.E stale dispatch).
    dispatch_marker_at: str | None = None

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


class Unviewed(_Strict):
    """A judged issue whose `view_issue` failed (review r-p2-unviewed).

    A deleted issue, a rate limit, a 5xx and a token without access all fail
    the same way, and only the forge could tell them apart. So none of them is
    dropped: `check` reports these as unreachable, never as orphaned.
    """

    key: str  # normalised judgement key
    reason: str


class Truncation(_Strict):
    """A list that returned exactly its limit, so it may have been cut short."""

    source: TruncatedList
    target: str  # the repo (issues, prs) or owner (repos) listed
    limit: int

    def describe(self, target: str) -> str:
        """One plain-words sentence (no final stop) for this warning, naming its remedy.

        *target* is `self.target` already escaped for wherever it prints; CLI and
        board share this wording (review r-p3-copy). Only the PR list has a flag;
        the issue and repo lists have none, and the sentence says so rather than
        inventing one.
        """
        remedy = "raise it with --pr-limit" if self.source == "prs" else "no flag raises this limit"
        return (
            f"the {_LIST_WORDS[self.source]} for {target} returned exactly its limit "
            f"({self.limit}), so it may be cut short; {remedy}"
        )


_LIST_WORDS: dict[str, str] = {"prs": "PR list", "issues": "issue list", "repos": "repo list"}


class Launch(_Strict):
    """How a batch is launched: runner, harness and model (spec §3.B).

    Every field is optional: a batch stores only what was given explicitly,
    and dispatch resolves the rest from `defaults.launch` (§3.I), never by
    picking one itself.
    """

    runner: str | None = None
    harness: str | None = None
    model: str | None = None


class VersionSource(_Strict):
    file: str
    key: str


class VersionBlock(_Strict):
    """`.fr/triage.yaml`'s `version:` — the opt-in to reservations (spec §3.D)."""

    source: VersionSource
    files: list[str]
    set_: str = Field(alias="set")
    relock: str | None = None


class ConfigDefaults(_Strict):
    launch: Launch = Launch()


class TriageConfig(_Strict):
    """`.fr/triage.yaml` of one repo, read at its default branch (spec §3.I).

    An absent file is `TriageConfig()`: no launch defaults, no reservations,
    a 3-day stale-dispatch threshold.
    """

    defaults: ConfigDefaults = ConfigDefaults()
    version: VersionBlock | None = None
    stale_dispatch_days: int = Field(default=3, ge=0)


class Facts(_Strict):
    """What `collect` read from the forge for one scope.

    `repos` is the SCOPE: every repo `collect` set out to read, including the
    ones it then skipped. It is not the repos collected — for that, and for any
    "N repos" a reader presents, use `collected` (review r-p2-repos-doc).
    """

    schema_: Literal[3] = Field(3, alias="schema")
    scope: str
    kind: ScopeKind
    collected_at: str
    repos: list[str]
    issues: list[Issue]
    prs: list[PullRequest] = []
    skipped: list[Skipped] = []
    unviewed: list[Unviewed] = []
    warnings: list[Truncation] = []
    # PRs found by head branch for batches at `dispatched` (spec §3.A): a merged
    # PR that lost every Closes line is linked to no member, so only this finds it.
    batch_prs: list[PullRequest] = []
    # `.fr/triage.yaml` per OWNER/REPO; a repo without the file has no entry.
    config: dict[str, TriageConfig] = {}

    def config_for(self, repo: str) -> TriageConfig:
        """*repo*'s collected config, or the defaults when it declares none."""
        return self.config.get(repo, TriageConfig())

    @property
    def collected(self) -> list[str]:
        """The repos actually read: `repos` minus the `skipped` ones, in scope order."""
        skipped = {s.repo for s in self.skipped}
        return [r for r in self.repos if r not in skipped]

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
    delivery: Delivery | None = None
    delivery_note: str = ""


class Pattern(_Strict):
    title: str
    ids: list[str] = []
    body: str = ""

    @field_validator("ids")
    @classmethod
    def _ids_are_keys(cls, v: list[str]) -> list[str]:
        """Same grammar and normaliser as judgement keys, so a typo is loud (r-p2-pattern-ids)."""
        bad = _bad_keys(list(v))
        if bad:
            raise ValueError(f"pattern ids must be '<repo-name>#<number>', got {bad!r}")
        return [normalize_key(k) for k in v]


class Batch(_Strict):
    """A group of judged issues delivered as one run (spec §3.A).

    Minimal in phase 1 — id, title and member ids. The launch settings, the
    engine-written events and the load-time membership rules land with the
    batch verbs.
    """

    id: str
    title: str
    ids: list[str]


class Judgements(_Strict):
    """`judgements.yaml`. Schema 1 files load as zero batches (spec §3.A)."""

    schema_: Literal[1, 2] = Field(1, alias="schema")
    ranked_at: date | None = None
    tiers: list[Tier] = []
    issues: dict[str, Judgement] = {}
    patterns: list[Pattern] = []
    batches: list[Batch] = []

    @field_validator("issues", mode="before")
    @classmethod
    def _keys_are_repo_hash_number(cls, v: object) -> object:
        """Validate the key grammar, then normalise; a case-only collision is a conflict."""
        if not isinstance(v, dict):
            return v  # pydantic reports the wrong type
        bad = _bad_keys(list(v))
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

    @model_validator(mode="after")
    def _batches_need_schema_2(self) -> Judgements:
        """Batches exist only under schema 2 (spec §3.A). A schema-1 stamp over a
        `batches:` list is a writer that forgot to restamp, and a schema-1 reader
        cannot hold it, so it is refused rather than loaded."""
        if self.batches and self.schema_ != 2:
            raise ValueError(
                f"`batches:` needs schema 2, but this file is stamped schema {self.schema_}"
            )
        return self


# ------------------------------------------------------------------- loaders


def _check_schema(
    path: Path, data: object, expected: int | tuple[int, ...], remedy: str = ""
) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TriageError(f"{path}: expected a mapping at the top level")
    accepted = (expected,) if isinstance(expected, int) else expected
    value = data.get("schema")
    # `type(...) is int`, not `==`: True == 1 == 1.0, and pydantic's Literal[1]
    # accepts all three, so `schema: true` would otherwise load (r-p2-schema-strict).
    if type(value) is not int or value not in accepted:
        suffix = f"; {remedy}" if remedy else ""
        reads = " or ".join(str(v) for v in accepted)
        raise TriageError(
            f"{path}: unsupported schema {value!r} (this fr reads schema {reads}){suffix}"
        )
    return data


def load_facts(path: Path) -> Facts:
    """Read `facts.json`, refusing a bad schema or shape with *path* in the message."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TriageError(f"{path}: cannot read facts: {exc}") from exc
    try:
        return Facts.model_validate(_check_schema(path, data, FACTS_SCHEMA, "re-run collect"))
    except ValidationError as exc:
        raise TriageError(f"{path}: invalid facts: {exc}") from exc


def load_judgements(path: Path) -> Judgements:
    """Read `judgements.yaml`, refusing a bad schema or shape with *path* in the message."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise TriageError(f"{path}: cannot read judgements: {exc}") from exc
    try:
        return Judgements.model_validate(_check_schema(path, data, JUDGEMENTS_READS))
    except ValidationError as exc:
        raise TriageError(f"{path}: invalid judgements: {exc}") from exc
