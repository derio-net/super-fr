"""Matrix schema, ref grammar, archive-twin resolution.

Row refs are `<repo>:<path>[#fragment]` — the fragment (a `#L12` line pin or
a heading anchor) is kept for GitHub URLs and stripped for existence checks
and local links (spec trap 3).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
)

LEVELS: tuple[str, ...] = ("unit", "api", "int", "ui")

Status = Literal["ci", "scheduled", "skipped", "not-implemented", "failing"]


class AcceptanceError(Exception):
    """Any matrix-shape or ref-grammar violation. CLI maps this to exit 1/2."""


def split_ref(ref: str) -> tuple[str, str, str]:
    """`'<repo>:<path>[#frag]'` → `(repo, path, fragment)`."""
    repo, sep, rest = ref.partition(":")
    if not sep or not rest or not repo or "/" in repo:
        raise AcceptanceError(f"ref must be '<repo>:<path>[#Lline|#anchor]': {ref!r}")
    path, _, frag = rest.partition("#")
    return repo, path, frag


# Specs migrate specs/ ↔ implemented/specs/ at `fr archive` without renaming
# (spec trap 1). Refs written against either location resolve to wherever the
# file actually is, so an archive never breaks links or the staleness guard.
ARCHIVE_TWIN_DIRS = ("docs/superpowers/specs/", "docs/superpowers/implemented/specs/")


def archive_twin(path: str) -> str | None:
    live, done = ARCHIVE_TWIN_DIRS
    if path.startswith(live):
        return done + path[len(live) :]
    if path.startswith(done):
        return live + path[len(done) :]
    return None


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
    org: StrictStr | None = None
    repo: StrictStr | None = None
    rows: tuple[Row, ...] = ()


def load_matrix(path: Path) -> Matrix:
    """Parse + validate `matrix.yaml`; every failure is an AcceptanceError."""
    import yaml

    if not path.exists():
        raise AcceptanceError(f"no acceptance matrix at {path}")
    try:
        data = yaml.safe_load(path.read_text()) or {}
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
