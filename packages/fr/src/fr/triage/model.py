"""Triage state: scope, state directory, and the two files (spec §3.B, §3.D).

`facts.json` is what `collect` read from the forge; `judgements.yaml` is the
agent's half. Both carry `schema: 1`, and a reader refuses any other value with
a message naming the file rather than guessing. Neither is an artifact kind:
they live under fr's cache root, never in a repo.

`Scope` is the ONE home of scope naming, and `state_dir` the one home of the
state directory, so the command and the directory can never disagree.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from fr.isolation.types import _home
from fr.triage.errors import TriageError
from fr.triage.stage import Stage, derive_stage

# The version this fr WRITES for facts.json, on EVERY scope. 4 added the `group` scope kind
# (wave-driver §H), and since then every scope's file carries keys a schema-3 reader
# (closed-world) rejects: `viewer`, `judged_prs`, per-PR `author`/`cross_repo`, per-config
# `post_merge`/`pr_authors`, nullable `checks`. 5 is the same story for per-config `mirrors`
# (verification-strategies §G; `to_json` is a full `model_dump`, so every file carries it): a
# schema-4 reader would answer "invalid facts" where "re-run collect" is owed. (`export`, per
# config, was in the same position at 4; it is left as it is.) Stamping a file lower would
# turn that reader's "unsupported schema; re-run collect" into "invalid facts" (gh#885).
# 6 adds per-issue `claims` (2026-10-06-triage-claims §3.H, R12): every file carries the key
# (`to_json` dumps it, `[]` included), which a closed-world schema-5 reader rejects, so the
# stamp moves for the same reason as 4 and 5.
# 3, 4 and 5 still load, and the first collect upgrades them. Independent of JUDGEMENTS_SCHEMA.
FACTS_SCHEMA: Literal[6] = 6
FACTS_READS: tuple[int, ...] = (3, 4, 5, 6)
# The version this fr WRITES: every engine write stamps 6 (spec 2026-10-06-triage-claims
# §3.H: the `claims_released` event; 5 was 2026-10-06-verification-strategies §G: the
# `conflict` event; 4 was
# 2026-10-05-triage-pages-goal §G: `exports:`; 3 was 2026-10-02-wave-driver §A: `wave`,
# `after`; 2 was 2026-09-25-triage-batches §3.A); the loader reads every version in
# JUDGEMENTS_READS.
JUDGEMENTS_SCHEMA: Literal[6] = 6
JUDGEMENTS_READS: tuple[int, ...] = (1, 2, 3, 4, 5, 6)

ScopeKind = Literal["repo", "org", "group"]
SCOPE_NAME_LIMIT = 80
Cx = Literal["XS", "S", "S-M", "M", "L", "-"]
PrState = Literal["OPEN", "CLOSED", "MERGED"]
IssueState = Literal["open", "closed"]
TruncatedList = Literal["repos", "issues", "prs"]
AnchorKind = Literal["issue", "spec", "debug", "unanchored"]
Delivery = Literal["delivers", "partial", "drift", "unanchored"]
Kind = Literal["defect", "feature", "parked"]
Severity = Literal["low", "med", "high"]

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

# A batch id is a slug (spec 2026-09-25-triage-batches §3.A): it becomes the
# branch `feat/batch-<id>` and the item id `<repo>/run/batch-<id>`.
BATCH_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
Bump = Literal["patch", "minor", "major"]
# What a batch's run is (spec 2026-09-27-triage-batch-launch §B): `goal` dispatches
# `/fr-goal`, `debug` dispatches `/fr-debugging`. `goal` is the default so every
# schema-2 file written before this field existed still loads unchanged.
BatchSkill = Literal["goal", "debug"]


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


def _keys(v: list[str], what: str) -> list[str]:
    """Validate the key grammar of *v*, then normalise it (one rule for every key list)."""
    bad = _bad_keys(list(v))
    if bad:
        raise ValueError(f"{what} must be '<repo-name>#<number>', got {bad!r}")
    return [normalize_key(k) for k in v]


@dataclass(frozen=True)
class Scope:
    """What is being triaged: one repo, every non-archived repo of an owner, or a
    group of repos (owners may differ; wave-driver §H)."""

    kind: ScopeKind
    target: str  # "OWNER/REPO" (repo), "OWNER" (org), "A/B,C/D" sorted (group)
    repos: tuple[str, ...] = ()  # a group's OWNER/REPO list; empty for repo and org

    @classmethod
    def group(cls, repos: Iterable[str]) -> Scope:
        """A group scope over *repos*: lowercased, sorted and de-duplicated, so input
        casing and order never change `target`, `repos` or `name`."""
        unique = sorted({r.lower() for r in repos})
        return cls(kind="group", target=",".join(unique), repos=tuple(unique))

    @property
    def name(self) -> str:
        """Directory-safe scope name: `<owner>--<repo>`, `<owner>`, or a group's sorted
        `owner--repo` slugs joined by `+` (spec §3.B, wave-driver §H).

        Lowercase, so `--repo Derio-Net/Super-FR` names the same state
        directory as `--repo derio-net/super-fr` (review r-p2-case). A group name
        over 80 characters is cut and ends in an eight-character hash of the whole.
        """
        if self.kind != "group":
            return self.target.replace("/", "--").lower()
        full = "+".join(sorted(r.replace("/", "--").lower() for r in self.repos))
        if len(full) <= SCOPE_NAME_LIMIT:
            return full
        digest = hashlib.sha256(full.encode("utf-8")).hexdigest()[:8]
        return f"{full[: SCOPE_NAME_LIMIT - 9]}-{digest}"

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
    # When the PR was opened (`createdAt`): dates it against a batch's last
    # dispatch, so a PR from an earlier dispatch is not this one's (r2p-f1).
    created_at: str | None = None
    url: str
    head_ref: str = ""
    head_oid: str = ""  # open PRs only (the open-PR list carries headRefOid)
    # Who opened the PR, and whether from a fork (`isCrossRepository`). None is
    # "never read", which no attribution trusts (gh#936).
    author: str | None = None
    cross_repo: bool | None = None
    files: list[str] = []  # open PRs only: the paths the PR touches
    # Open PRs only — `None` when the record came from `list_prs(state=all)`,
    # which carries none of them, so a default can never pass for data (#648).
    checks: dict[str, int] | None = None
    mergeable: str | None = None
    merge_state: str | None = None
    review: str | None = None
    anchor: AnchorKind = "unanchored"
    anchor_path: str | None = None
    anchor_body: str = ""
    anchor_reason: str | None = None


class IssueClaim(_Strict):
    """One signer's latest un-released claim marker on an issue, live or expired, as
    collect read it (spec 2026-10-06-triage-claims §3.H). Only a trusted author's marker
    is recorded (R17). Stamps are ISO-8601 UTC strings, like every facts time."""

    signer: str
    batch: str
    claimed: str
    heartbeat: str
    expires: str
    comment_id: int
    created_at: str  # the comment's; R4 orders by it


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
    # The claims on the issue (schema 6): read only for issues labelled fr:claimed or
    # fr:in-progress, from the same comment read as `dispatch_marker_at`.
    claims: list[IssueClaim] = []

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
    """A judged issue, or one named by a `duplicate_of`, whose `view_issue` failed
    (review r-p2-unviewed).

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


class ExportConfig(_Strict):
    """`.fr/triage.yaml`'s `export:` (spec 2026-10-05-triage-pages-goal §I): the
    repo-relative directory the driver exports the triage state under."""

    path: str

    @field_validator("path")
    @classmethod
    def _inside_the_repo(cls, v: str) -> str:
        """Normalised once, here (p4-r2): one trailing `/` is stripped, and a path
        `contained()` would refuse later (absolute, or with a `..`, `.` or empty part)
        is refused now, so every reader uses the one value and none fails per pass."""
        norm = v.removesuffix("/")
        parts = norm.replace("\\", "/").split("/")
        if (
            norm.startswith(("/", "\\"))
            or (parts[0][1:2] == ":")
            or any(p in ("", ".", "..") for p in parts)
        ):
            raise ValueError(
                "export path must be a repo-relative directory with no `..`, `.` or empty "
                f"part, got {v!r}"
            )
        return norm


class TriageConfig(_Strict):
    """`.fr/triage.yaml` of one repo, read at its default branch (spec §3.I).

    An absent file is `TriageConfig()`: no launch defaults, no reservations,
    a 3-day stale-dispatch threshold.
    """

    defaults: ConfigDefaults = ConfigDefaults()
    version: VersionBlock | None = None
    stale_dispatch_days: int = Field(default=3, ge=0)
    # The command the wave driver runs once per merged batch, from the repo's
    # fast-forwarded checkout (wave-driver R14). An argument list, never a shell
    # string: a string is refused, and nothing is ever handed to a shell.
    post_merge: list[str] = []
    # The logins whose PRs on a batch branch are the batch's (gh#936). Empty means
    # the user `collect` ran as (`Facts.viewer`); a list REPLACES that default.
    pr_authors: list[str] = []
    # The commands that regenerate this repo's generated mirrors, each an argument list
    # (spec 2026-10-06-verification-strategies §G): a conflict hand-back's brief names
    # them, so a session regenerates a mirror instead of hand-resolving it.
    mirrors: list[Annotated[list[str], Field(min_length=1)]] = []
    # Where the wave driver exports this repo's triage state once a wave is finished
    # (spec 2026-10-05-triage-pages-goal R13); None: the driver never exports.
    export: ExportConfig | None = None


def trusted_logins(config: TriageConfig, viewer: str | None) -> frozenset[str]:
    """The logins a repo trusts, lowercased (gh#936, triage-claims R17): its
    `pr_authors` when it lists any, else *viewer* (the user `collect` ran as). Empty
    when neither is known, so nothing is trusted. Guards batch PRs; claims use
    `claim_trusted`."""
    logins = config.pr_authors or ([viewer] if viewer else [])
    return frozenset(login.lower() for login in logins)


def claim_trusted(config: TriageConfig, viewer: str | None) -> frozenset[str]:
    """The logins whose claim markers count on a repo, lowercased (triage-claims R17):
    *viewer* (the user `collect` ran as) AND the repo's `pr_authors`. Unlike
    `trusted_logins`, a `pr_authors` list never drops the viewer, or this host's own
    claims would not count. Author association (OWNER/MEMBER/COLLABORATOR) is the other
    half of R17, read per comment by `fr.triage.claims.read_claims`."""
    logins = [*config.pr_authors, *([viewer] if viewer else [])]
    return frozenset(login.lower() for login in logins)


def parse_triage_config(
    data: object, *, lenient: bool = False
) -> tuple[TriageConfig, tuple[str, ...]]:
    """`.fr/triage.yaml`'s parsed body as config, and the top-level keys it ignored.

    Strict by default: an unknown key is refused, so a typo fails where a person
    runs `fr triage collect` by hand. *lenient* is the wave driver's (gh#998): it
    reads the file from the default branch every pass, and its own merges land a
    key the running `fr` predates before the release that knows it can. It drops
    unknown TOP-LEVEL keys and names them; a known key with a bad value, or an
    unknown key nested in a known block, is still refused.
    """
    if not lenient or not isinstance(data, dict):
        return TriageConfig.model_validate(data), ()
    known = {f.alias or name for name, f in TriageConfig.model_fields.items()}
    ignored = tuple(sorted(str(k) for k in data if k not in known))
    kept = {k: v for k, v in data.items() if k in known}
    return TriageConfig.model_validate(kept), ignored


class Facts(_Strict):
    """What `collect` read from the forge for one scope.

    `repos` is the SCOPE: every repo `collect` set out to read, including the
    ones it then skipped. It is not the repos collected — for that, and for any
    "N repos" a reader presents, use `collected` (review r-p2-repos-doc).
    """

    schema_: Literal[3, 4, 5, 6] = Field(6, alias="schema")
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
    # PRs a judgement names that no other list here carries: closed or merged and
    # linked to no collected issue (gh#902). A judgement may rank a PR; it is never
    # an issue, so it is kept here rather than in `issues`.
    judged_prs: list[PullRequest] = []
    # `.fr/triage.yaml` per OWNER/REPO; a repo without the file has no entry.
    config: dict[str, TriageConfig] = {}
    # The forge login `collect` ran as: the default allowed batch PR author (gh#936).
    viewer: str | None = None

    @model_validator(mode="after")
    def _group_needs_schema_4(self) -> Facts:
        """The `group` kind exists only from schema 4 (wave-driver §H); an older
        reader cannot hold it, so a schema-3 file naming it is refused."""
        if self.kind == "group" and self.schema_ < 4:
            raise ValueError("`kind: group` needs schema 4")
        return self

    def matches(self, scope: Scope) -> bool:
        """Whether these facts were collected for *scope*: same kind, same name. A
        `--dir` can point any command at any directory, so a reader checks (gh#886)."""
        return self.kind == scope.kind and self.scope == scope.name

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
    # What the issue is, for the board's closing order (wave-driver R9). Optional on
    # every schema: a file that never says loads exactly as before.
    kind: Kind | None = None
    # How bad it is, and what it duplicates (triage-pages-goal R11), and which issues it
    # was judged different from (triage-dedupe R3). Optional on every schema, the `kind`
    # precedent: a file that never says loads exactly as before. The cross-key rules live
    # on `Judgements`, which knows every key.
    severity: Severity | None = None
    duplicate_of: str | None = None
    distinct_from: list[str] = []

    @field_validator("duplicate_of")
    @classmethod
    def _duplicate_of_is_a_key(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _keys([v], "duplicate_of")[0]

    @field_validator("distinct_from")
    @classmethod
    def _distinct_from_are_keys(cls, v: list[str]) -> list[str]:
        keys = _keys(v, "distinct_from")
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if dupes:
            raise ValueError(f"distinct_from lists {dupes} more than once")
        return keys


class Feature(_Strict):
    """A ranked group of issues delivered as one feature (wave-driver R9)."""

    rank: int
    title: str
    ids: list[str] = []
    why: str = ""
    start: str = ""  # how to start it, e.g. `/fr-goal ...`; shown, never run

    @field_validator("ids")
    @classmethod
    def _ids_are_keys(cls, v: list[str]) -> list[str]:
        return _keys(v, "feature ids")


class Pattern(_Strict):
    title: str
    ids: list[str] = []
    body: str = ""

    @field_validator("ids")
    @classmethod
    def _ids_are_keys(cls, v: list[str]) -> list[str]:
        """Same grammar and normaliser as judgement keys, so a typo is loud (r-p2-pattern-ids)."""
        return _keys(v, "pattern ids")


class DispatchEvent(_Strict):
    """A batch was handed to a runner (spec §3.A). Written by the engine only."""

    kind: Literal["dispatch"]
    at: AwareDatetime
    runner: str
    handle: str  # opaque to triage; never posted to the forge
    branch: str
    reserved_version: str | None = None  # absent when the repo declares no version block


class CancelEvent(_Strict):
    """A batch was withdrawn (spec §3.E cancel). Written by the engine only."""

    kind: Literal["cancel"]
    at: AwareDatetime
    reason: str = ""


class CloseoutEvent(_Strict):
    """A batch's close-out was started (wave-driver §A). Needs judgements schema 3.
    Written by the engine only."""

    kind: Literal["closeout"]
    at: AwareDatetime
    runner: str
    handle: str  # opaque to triage; never posted to the forge
    run: str | None = None  # the run id the brief named (`fr pickup --run`), if any
    archive: str | None = None  # the housekeeping branch the close-out will push
    # The archive PR the driver merged (review rg-6): a later event repeats the
    # close-out with this set, so the batch reads as finished without the PR in view.
    archived: int | None = None


class PostMergeEvent(_Strict):
    """The repo's `post_merge` command succeeded for this batch's merge (wave-driver
    R14). Needs judgements schema 3. Written by the engine only."""

    kind: Literal["post_merge"]
    at: AwareDatetime


ConflictDelivery = Literal["session", "fresh", "held"]


class ConflictEvent(_Strict):
    """Drive met a real merge conflict at *head* and handed it back (spec
    2026-10-06-verification-strategies §G; R20-R22). Needs judgements schema 5.
    Written by the engine only.

    `delivered`: `session`, the brief was sent to the batch's idle session; `fresh`, a
    new conflict session was started; `held`, the hand-back bound was reached and the
    operator owns it. `handle` is the item messaged (session) or the runner's handle
    for the started item (fresh); None when held."""

    kind: Literal["conflict"]
    at: AwareDatetime
    head: str
    paths: list[str] = Field(min_length=1)  # the paths merge refused to resolve
    delivered: ConflictDelivery
    handle: str | None = None


class ClaimsReleasedEvent(_Strict):
    """This scope released its claims on *keys*, members of this batch (spec
    2026-10-06-triage-claims §3.H, R10), so a later pass owes them nothing. Needs
    judgements schema 6. Written by the engine only."""

    kind: Literal["claims_released"]
    at: AwareDatetime
    keys: list[str] = Field(min_length=1)

    @field_validator("keys")
    @classmethod
    def _keys_are_keys(cls, v: list[str]) -> list[str]:
        return _keys(v, "claims_released keys")


SCHEMA_3_EVENTS = frozenset({"closeout", "post_merge"})
"""The event kinds only a schema 3 `judgements.yaml` may carry (wave-driver §A)."""
SCHEMA_5_EVENTS = frozenset({"conflict"})
"""The event kinds only a schema 5 `judgements.yaml` may carry (verification-strategies §G)."""
SCHEMA_6_EVENTS = frozenset({"claims_released"})
"""The event kinds only a schema 6 `judgements.yaml` may carry (triage-claims §3.H)."""


BatchEvent = Annotated[
    DispatchEvent
    | CancelEvent
    | CloseoutEvent
    | PostMergeEvent
    | ConflictEvent
    | ClaimsReleasedEvent,
    Field(discriminator="kind"),
]


class Batch(_Strict):
    """A group of judged issues delivered as one run (spec §3.A).

    Structural rules hold here, from the file alone: the id is a slug, `ids` is
    non-empty, each id is a key (normalised like `Pattern.ids`) and all name one
    repo, and `events` is time-ordered. That every member is judged is the
    enclosing `Judgements`' rule; the open-batch rule needs facts, so it is
    `fr.triage.batch`'s.
    """

    id: str
    title: str
    ids: list[str] = Field(min_length=1)
    rationale: str = ""
    order: int | None = None
    wave: int | None = None
    after: list[str] = []  # ids of batches that must be merged first (schema 3)
    bump: Bump = "patch"
    skill: BatchSkill = "goal"
    launch: Launch = Launch()
    events: list[BatchEvent] = []

    @field_validator("id", mode="before")
    @classmethod
    def _id_is_a_slug(cls, v: object) -> object:
        """Lowercased first, so `Lifecycle` and `lifecycle` are one batch id."""
        if not isinstance(v, str) or not BATCH_ID_RE.match(v.lower()):
            raise ValueError(f"batch id must match {BATCH_ID_RE.pattern}, got {v!r}")
        return v.lower()

    @field_validator("ids")
    @classmethod
    def _ids_are_keys_of_one_repo(cls, v: list[str]) -> list[str]:
        keys = _keys(v, "batch ids")
        twice = sorted({k for k in keys if keys.count(k) > 1})
        if twice:
            # Review r2p-f5: caught here, or the open-batch rule later reports the
            # batch clashing with itself ("is in x, x").
            raise ValueError(f"a batch lists {', '.join(twice)} more than once")
        repos = sorted({k.rpartition("#")[0] for k in keys})
        if len(repos) > 1:
            raise ValueError(f"a batch's members must be in one repo, got {repos}")
        return keys

    @field_validator("after")
    @classmethod
    def _after_are_slugs(cls, v: list[str]) -> list[str]:
        """Lowercased like `id`, a slug each, listed once."""
        out = [x.lower() if isinstance(x, str) else x for x in v]
        bad = [x for x in out if not isinstance(x, str) or not BATCH_ID_RE.match(x)]
        if bad:
            raise ValueError(f"`after` names batch ids (slugs), got {bad!r}")
        twice = sorted({x for x in out if out.count(x) > 1})
        if twice:
            raise ValueError(f"`after` lists {', '.join(twice)} more than once")
        return out

    @field_validator("events")
    @classmethod
    def _events_are_time_ordered(
        cls, v: list[DispatchEvent | CancelEvent | CloseoutEvent | PostMergeEvent]
    ) -> list[Any]:
        for earlier, later in zip(v, v[1:], strict=False):
            if later.at < earlier.at:
                raise ValueError(
                    f"batch events must be time-ordered: {later.kind} at {later.at} "
                    f"follows {earlier.kind} at {earlier.at}"
                )
        return v

    @property
    def repo_name(self) -> str:
        """The `<repo-name>` part every member key shares."""
        return self.ids[0].rpartition("#")[0]


class Export(_Strict):
    """One wave's state export by the driver (spec 2026-10-05-triage-pages-goal §G).
    Needs judgements schema 4. Written by the engine only.

    `pr` is None when the export changed nothing, so no PR was opened; `merged` is set
    once the driver merged the PR."""

    wave: str  # the wave key, `str(batch.wave)`
    repo: str  # OWNER/REPO
    at: AwareDatetime  # when the export was recorded
    pr: int | None = None
    # The SHA the merge is pinned to: the commit the driver pushed, or the head of the
    # PR it adopted. A commit anyone else pushes to the branch never merges (R13).
    head: str | None = None
    merged: bool = False
    # The PR was closed without a merge (p4-r6): the entry no longer covers its wave,
    # which is owed again and re-exported on a fresh PR.
    closed: bool = False

    @field_validator("wave", mode="before")
    @classmethod
    def _wave_key(cls, v: object) -> object:
        """A wave written as a number is the same key as its string."""
        return str(v) if isinstance(v, int) and not isinstance(v, bool) else v


class Judgements(_Strict):
    """`judgements.yaml`. Schema 1 files load as zero batches (spec §3.A)."""

    schema_: Literal[1, 2, 3, 4, 5, 6] = Field(1, alias="schema")
    ranked_at: date | None = None
    tiers: list[Tier] = []
    issues: dict[str, Judgement] = {}
    patterns: list[Pattern] = []
    batches: list[Batch] = []
    features: list[Feature] = []  # ranked groups (wave-driver R9); any schema
    exports: list[Export] = []  # the driver's per-wave state exports; schema 4

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

    def duplicate_targets(self) -> set[str]:
        """Every key some judgement names as its original (`duplicate_of`)."""
        return {j.duplicate_of for j in self.issues.values() if j.duplicate_of}

    @model_validator(mode="after")
    def _duplicate_fields_are_coherent(self) -> Judgements:
        """`distinct_from` never names the issue itself, and no key is in both fields (spec
        triage-dedupe §3.A). A `duplicate_of` self reference is the next validator's; a
        chain loads and `check` reports it as `duplicate_chained` (triage-pages-goal)."""
        for key, j in self.issues.items():
            if key in j.distinct_from:
                raise ValueError(f"{key}: distinct_from names the issue itself")
            if j.duplicate_of and j.duplicate_of in j.distinct_from:
                raise ValueError(
                    f"{key}: {j.duplicate_of} is in both duplicate_of and distinct_from"
                )
        return self

    @model_validator(mode="after")
    def _no_judgement_duplicates_itself(self) -> Judgements:
        own = sorted(k for k, j in self.issues.items() if j.duplicate_of == k)
        if own:
            raise ValueError(f"{own} name their own key as duplicate_of")
        return self

    @model_validator(mode="after")
    def _tiers_are_declared(self) -> Judgements:
        declared = {t.n for t in self.tiers}
        undeclared = sorted({j.tier for j in self.issues.values()} - declared)
        if undeclared:
            raise ValueError(f"judgements name undeclared tiers {undeclared}")
        return self

    @model_validator(mode="after")
    def _batch_members_are_judged_and_ids_unique(self) -> Judgements:
        """Every member is judged, and batch ids are unique (ids are already
        lowercased, so this is the case-insensitive check spec §3.A asks for)."""
        seen: set[str] = set()
        for batch in self.batches:
            if batch.id in seen:
                raise ValueError(
                    f"batch ids must be unique (case-insensitively): {batch.id!r} appears twice"
                )
            seen.add(batch.id)
            unjudged = [k for k in batch.ids if k not in self.issues]
            if unjudged:
                raise ValueError(f"batch {batch.id!r}: members {unjudged} are not judged")
        return self

    @model_validator(mode="after")
    def _batches_need_schema_2(self) -> Judgements:
        """Batches exist only under schema 2 or 3 (spec §3.A); `wave` and `after`
        only under 3 (wave-driver §A). A stamp below what a file carries is a writer
        that forgot to restamp, and an older reader cannot hold it, so it is refused
        rather than loaded."""
        if self.batches and self.schema_ < 2:
            raise ValueError(
                f"`batches:` needs schema 2 or 3, but this file is stamped schema {self.schema_}"
            )
        if self.schema_ < 3 and any(b.wave is not None or b.after for b in self.batches):
            raise ValueError(
                f"`wave` and `after` need schema 3, but this file is stamped schema {self.schema_}"
            )
        late = sorted({e.kind for b in self.batches for e in b.events if e.kind in SCHEMA_3_EVENTS})
        if self.schema_ < 3 and late:
            raise ValueError(
                f"`{'`, `'.join(late)}` events need schema 3, but this file is stamped "
                f"schema {self.schema_}"
            )
        if self.exports and self.schema_ < 4:
            raise ValueError(
                f"`exports:` needs schema 4, but this file is stamped schema {self.schema_}"
            )
        later = sorted(
            {e.kind for b in self.batches for e in b.events if e.kind in SCHEMA_5_EVENTS}
        )
        if self.schema_ < 5 and later:
            raise ValueError(
                f"`{'`, `'.join(later)}` events need schema 5, but this file is stamped "
                f"schema {self.schema_}"
            )
        latest = sorted(
            {e.kind for b in self.batches for e in b.events if e.kind in SCHEMA_6_EVENTS}
        )
        if self.schema_ < 6 and latest:
            raise ValueError(
                f"`{'`, `'.join(latest)}` events need schema 6, but this file is stamped "
                f"schema {self.schema_}"
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
        return Facts.model_validate(_check_schema(path, data, FACTS_READS, "re-run collect"))
    except ValidationError as exc:
        raise TriageError(f"{path}: invalid facts: {exc}") from exc


def load_scope_facts(path: Path, scope: Scope) -> Facts:
    """`load_facts`, refusing facts collected for any scope but *scope* (gh#886)."""
    facts = load_facts(path)
    if not facts.matches(scope):
        raise TriageError(
            f"{path}: these facts are for the {facts.kind} scope {facts.scope}, not the "
            f"{scope.kind} scope {scope.name}; collect this scope, or point --dir at its "
            "own state directory"
        )
    return facts


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
