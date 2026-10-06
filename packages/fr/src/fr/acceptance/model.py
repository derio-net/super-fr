"""Matrix schema, ref grammar, archive-twin resolution.

Row refs are `<repo>:<path>[#fragment]` — the fragment (a heading anchor, a
`#L12` line pin into a non-Python file, or a test's name into a `.py` file —
`fr.acceptance.anchors`) is kept for GitHub URLs and stripped for existence
checks and local links (spec trap 3).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from fr.journal.model import IMPLEMENTED_JOURNALS_REL, JOURNALS_REL, SCOPE_DIRS

LEVELS: tuple[str, ...] = ("unit", "api", "int", "ui")

Status = Literal["ci", "scheduled", "skipped", "not-implemented", "failing"]


# A row's `issues` entry (spec 2026-10-06-verification-strategies R13): the
# issue whose promise the row carries, always fully qualified so a matrix row
# never depends on which checkout reads it.
ISSUE_REF_RE = re.compile(r"^[\w.-]+/[\w.-]+#\d+$")

WalkOutcome = Literal["pass", "fail"]

# The matrix-v3 spelling of "only verifiable after merge". Matrix kind 3 -> 4
# (`fr.artifacts.matrix_strategies`) rewrites it to the `live` strategy; the
# live row refuses it, so a body still carrying it is visibly not v4.
LEGACY_POST_MERGE = "post-merge"


class AcceptanceError(Exception):
    """Any matrix-shape or ref-grammar violation. CLI maps this to exit 1/2."""


def split_ref(ref: str) -> tuple[str, str, str]:
    """`'<repo>:<path>[#frag]'` → `(repo, path, fragment)`."""
    repo, sep, rest = ref.partition(":")
    if not sep or not rest or not repo or "/" in repo:
        raise AcceptanceError(f"ref must be '<repo>:<path>[#anchor]': {ref!r}")
    path, _, frag = rest.partition("#")
    return repo, path, frag


# fr's own pipeline artifacts — specs, plans, runs, journals, their archive.
# None of them is verification: a row whose level evidence is one states how
# the pipeline must run, not what the product does (gh#775 — take 10's
# `basket-single-phase` cited the plan's `01.yaml` as its unit test). A spec is
# a row's ORIGIN, never its evidence.
PIPELINE_ARTIFACTS_REL = "docs/superpowers/"


def pipeline_ref_error(ref: str) -> str | None:
    """Why `ref` cannot be level evidence, or None when it can."""
    import posixpath

    _, path, _ = split_ref(ref)
    # normpath: `./docs/…`, `docs/./superpowers/…` and `x/../docs/…` are the same file.
    if not (posixpath.normpath(path).lstrip("/") + "/").startswith(PIPELINE_ARTIFACTS_REL):
        return None
    return (
        f"{ref} is one of fr's own pipeline artifacts ({PIPELINE_ARTIFACTS_REL}), not a test "
        "— a row verified by the pipeline itself is a process directive, not a business "
        "acceptance; cite a test or captured live evidence, or drop the row"
    )


# Specs migrate specs/ ↔ implemented/specs/ at `fr archive` without renaming
# (spec trap 1), and journals migrate journals/<scope> ↔
# implemented/journals/<scope> the same way (2026-09-28-closeout-always §F).
# Refs written against either location resolve to wherever the file actually
# is, so an archive never breaks links or the staleness guard. The journal
# pairs are DERIVED from `fr.journal.model` (`SCOPE_DIRS` / `JOURNALS_REL` /
# `IMPLEMENTED_JOURNALS_REL`) rather than re-declared here, so a new journal
# scope needs no edit on this side.
ARCHIVE_TWIN_DIRS: tuple[tuple[str, str], ...] = (
    ("docs/superpowers/specs/", "docs/superpowers/implemented/specs/"),
    *(
        (f"{JOURNALS_REL}/{scope_dir}/", f"{IMPLEMENTED_JOURNALS_REL}/{scope_dir}/")
        for scope_dir in SCOPE_DIRS.values()
    ),
)


def archive_twin(path: str) -> str | None:
    """The counterpart path for whichever `ARCHIVE_TWIN_DIRS` pair matches
    `path` at either end, or `None` when no pair matches."""
    for live, done in ARCHIVE_TWIN_DIRS:
        if path.startswith(live):
            return done + path[len(live) :]
        if path.startswith(done):
            return live + path[len(done) :]
    return None


def check_visual_names(states: tuple[str, ...], interactions: tuple[str, ...]) -> None:
    """Shared by `Visual`'s validator and any CLI pre-check (spec 2026-09-28
    §A): at least one of `states`/`interactions` must be non-empty, and no
    name may appear twice — within a list or across the two — because a
    name is what a screenshot's `shows` points at, and a duplicate would make
    that pointer ambiguous."""
    if not states and not interactions:
        raise ValueError("visual: at least one of states/interactions must be non-empty")
    seen: dict[str, str] = {}
    for field, names in (("states", states), ("interactions", interactions)):
        for name in names:
            if name in seen:
                where = "itself" if seen[name] == field else seen[name]
                raise ValueError(
                    f"visual: name {name!r} is duplicated ({field} vs {where}) — "
                    "each name must be unambiguous"
                )
            seen[name] = field


class Visual(BaseModel):
    """A row's user-visible UI evidence obligation (spec 2026-09-28 §A): the
    named states and interactions its screenshots must cover."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    states: tuple[StrictStr, ...] = ()
    interactions: tuple[StrictStr, ...] = ()

    @model_validator(mode="after")
    def _names_are_well_formed(self) -> Visual:
        try:
            check_visual_names(self.states, self.interactions)
        except ValueError as e:
            raise ValueError(str(e)) from e
        return self


class Walk(BaseModel):
    """One recorded walk of a row (spec 2026-10-06-verification-strategies
    R14): which strategy, on which harness and model, with what outcome, when,
    and the evidence (a log path or a note)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    strategy: StrictStr
    harness: StrictStr
    model: StrictStr
    outcome: WalkOutcome
    at: StrictStr
    evidence: StrictStr


def check_issue_refs(issues: tuple[str, ...]) -> None:
    """Shared by `Row` and `AcceptanceItem`: every entry is `owner/repo#n`."""
    for ref in issues:
        if not ISSUE_REF_RE.match(ref):
            raise ValueError(f"issue {ref!r} must be owner/repo#n")


def check_verify(value: str | None) -> None:
    """Shared by `Row` and `AcceptanceItem`: the v3 spelling is refused by
    name, with the way forward. Whether a name RESOLVES needs a repo root, so
    that is `fr validate artifacts`' check (`fr.artifacts.structure`)."""
    if value == LEGACY_POST_MERGE:
        raise ValueError(
            f"verify: {LEGACY_POST_MERGE} is the matrix-v3 spelling — name a strategy "
            "(`live` is what it became) or `none`; `fr migrate artifacts --yes` "
            "rewrites an existing matrix"
        )


class Row(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    # StrictStr: YAML scalars like `yes` / `1.0` arrive as bool/float and must
    # fail loud, not be coerced into an id nobody typed (spec trap 5 class).
    id: StrictStr
    capability: StrictStr
    acceptance: StrictStr
    origin: tuple[StrictStr, ...] = ()
    # validate_default: a row omitting `levels:` entirely must still get all
    # four keys filled by the validator below, or consumers KeyError.
    levels: dict[str, tuple[StrictStr, ...]] = Field(default={}, validate_default=True)
    status: Status
    notes: StrictStr = ""
    # The row's verification strategy, or `none` (spec 2026-10-06 §B, R7):
    # matrix kind 3 -> 4 widened it from `Literal["post-merge"]` (spec
    # 2026-09-28 §F, kind 1 -> 2) and rewrote that value to `live`. Whether
    # it is post-merge is the strategy manifest's answer
    # (`fr.verification.effective.is_post_merge`), never a string compare.
    verify: StrictStr | None = None
    # A user-visible UI requirement's evidence obligation (spec 2026-09-28
    # §A). Matrix kind 2 -> 3 (§G), because an older fr would reject the key
    # on this `extra="forbid"` row.
    visual: Visual | None = None
    # Matrix kind 4 (spec 2026-10-06 §B): the row's walk scenario (R10), the
    # issues whose promise it carries (R13), the harnesses that promise covers
    # and the walks recorded against it (R14).
    scenario: StrictStr | None = None
    issues: tuple[StrictStr, ...] = ()
    harnesses: tuple[StrictStr, ...] = ()
    walks: tuple[Walk, ...] = ()

    @field_validator("verify")
    @classmethod
    def _not_the_v3_spelling(cls, v: str | None) -> str | None:
        check_verify(v)
        return v

    @field_validator("issues")
    @classmethod
    def _issues_are_qualified(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        check_issue_refs(v)
        return v

    @field_validator("levels")
    @classmethod
    def _known_keys_only(cls, v: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        unknown = set(v) - set(LEVELS)
        if unknown:
            raise ValueError(
                f"unknown level keys {sorted(unknown)} (allowed: {list(LEVELS)}) "
                f"— a typo would silently drop refs"
            )
        return {lv: v.get(lv, ()) for lv in LEVELS}

    def refs(self) -> tuple[str, ...]:
        """Every ref this row carries — origins first, then level evidence."""
        return tuple(self.origin) + tuple(x for lv in LEVELS for x in self.levels[lv])


class Matrix(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    # The artifact stamp (`fr.artifacts.registry`, kind `matrix`). The first
    # move past 1 (spec 2026-09-28 §H) writes it, and this model is closed, so
    # it must accept the key or a stamped matrix would not parse.
    schema_version: int = 1
    org: StrictStr | None = None
    repo: StrictStr | None = None
    rows: tuple[Row, ...] = ()

    @field_validator("rows", mode="before")
    @classmethod
    def _none_is_empty(cls, v: object) -> object:
        # The init skeleton ends with a bare `rows:` (implicit null) so that
        # `fr acceptance add` can append list items textually; `rows: []`
        # would make the first append invalid YAML.
        return () if v is None else v


def load_matrix(path: Path) -> Matrix:
    """Parse + validate `matrix.yaml`; every failure is an AcceptanceError."""
    if not path.exists():
        raise AcceptanceError(f"no acceptance matrix at {path}")
    return parse_matrix(path.read_text())


def parse_matrix(text: str) -> Matrix:
    """`load_matrix` over text already in memory — what the step-record engine
    validates a matrix edit against before it writes anything."""
    import yaml

    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        raise AcceptanceError(f"matrix is not valid YAML: {e}") from e
    if not isinstance(data, dict):
        raise AcceptanceError(f"matrix top level must be a mapping, got {type(data).__name__}")
    try:
        matrix = Matrix.model_validate(data)
    except ValidationError as e:
        raise AcceptanceError(f"matrix schema: {e}") from e
    ids = [r.id for r in matrix.rows]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise AcceptanceError(f"duplicate row ids: {dupes}")
    return matrix
