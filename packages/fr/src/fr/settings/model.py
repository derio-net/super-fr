"""The closed settings model (spec 2026-11-04-repo-feature-settings, R4).

Every field carries a `description=`; `fr settings init` generates its comments from
them, so the file's documentation cannot drift from the schema.
"""

from __future__ import annotations

import re
import string
from collections.abc import Callable
from typing import Annotated, Any, Final, Literal, cast

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic.config import JsonDict

from fr.settings import SettingsError

SCHEMA_VERSION: Final = 3
SCHEMAS: Final = (1, 2, 3)
"""The settings schemas this fr reads. Schema 2 adds the `triage` section (spec 2026-11-19
R20); schema 3 adds `workflows` and `forge.pr_sections` (spec 2026-11-28-alacarte-settings
R1). A file that names no key of a later schema may stay at an earlier one."""


PLACEMENTS: Final = frozenset({"repo", "quiet", "stealth"})
ON_OFF: Final = frozenset({"on", "off"})
PR_BODIES: Final = frozenset({"full", "minimal"})
AUTO_ASK: Final = frozenset({"auto", "ask"})
HISTORIES: Final = frozenset({"keep", "squash-unpushed"})
PLACEHOLDERS: Final = frozenset({"type", "scope", "summary", "issue"})
SETTLE_MODES: Final = frozenset({"off", "report", "fix"})
PR_SECTIONS: Final = ("cost", "proportionality", "settle")
"""The allowed values, stated once: the validators and `fr settings init` both read them."""


def _on_off(v: Any) -> Any:
    """PyYAML reads a bare `on`/`off` as a bool; the documented values are the words."""
    if v is True:
        return "on"
    if v is False:
        return "off"
    return v


def _member(vocab: frozenset[str]) -> Callable[[Any], str]:
    def check(v: Any) -> str:
        if v not in vocab:
            raise ValueError("must be one of " + ", ".join(sorted(vocab)) + f", got {v!r}")
        return str(v)

    return check


def _no_bool(v: Any) -> Any:
    """A settle mode is a word: PyYAML's bare `off` is a bool, and a bool is refused."""
    if isinstance(v, bool):
        raise ValueError(f"must be one of fix, off, report (quote it: 'off'), got {v!r}")
    return v


def _choice(default: str, vocab: frozenset[str], description: str) -> Any:
    """A closed-vocabulary field; the renderer reads `allowed` back from the schema."""
    return Field(
        default,
        description=description,
        json_schema_extra=cast("JsonDict", {"allowed": sorted(vocab)}),
    )


def _strict_int(v: Any) -> Any:
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"must be the integer 1, 2 or 3, got {v!r}")
    return v


_SLUG = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def _slug(v: Any) -> Any:
    if v is None:
        return v
    if not isinstance(v, str) or not _SLUG.fullmatch(v) or v.split("/")[1] in (".", ".."):
        raise ValueError(f"must be OWNER/REPO, got {v!r}")
    return v


OnOffType = Annotated[str, BeforeValidator(_on_off), AfterValidator(_member(ON_OFF))]
AskType = Annotated[str, AfterValidator(_member(AUTO_ASK))]
BodyType = Annotated[str, AfterValidator(_member(PR_BODIES))]
HistoryType = Annotated[str, AfterValidator(_member(HISTORIES))]
PlacementType = Annotated[str, AfterValidator(_member(PLACEMENTS))]
SettleModeType = Annotated[str, BeforeValidator(_no_bool), AfterValidator(_member(SETTLE_MODES))]


def _check_template(v: str, *, allow_issue: bool) -> str:
    allowed = PLACEHOLDERS if allow_issue else PLACEHOLDERS - {"issue"}
    try:
        parsed = list(string.Formatter().parse(v))
    except ValueError as e:
        raise ValueError(f"not a valid template: {e}") from e
    for _, field, spec, conv in parsed:
        if field is None:
            continue
        if field not in allowed or spec or conv:
            hint = "" if allow_issue or field != "issue" else " (this template has no issue)"
            raise ValueError(
                f"unknown placeholder {{{field}}}{hint}; allowed: "
                + ", ".join(f"{{{p}}}" for p in sorted(allowed))
            )
    return v


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Artifacts(_Closed):
    acceptance: OnOffType = _choice(
        "on",
        ON_OFF,
        description="Default: the acceptance matrix and its rows are written.\n"
        "Off: no matrix rows are written and every surface reports it disabled by repo "
        "setting; a spec's Test Plan no longer feeds an acceptance gate.",
    )
    test_plan: OnOffType = _choice(
        "on",
        ON_OFF,
        description="Default: specs carry a Test Plan.\n"
        "Off: the Test Plan is not required or checked; nothing is lost but the plan's "
        "business-level statement of what proves the feature.",
    )
    gates: OnOffType = _choice(
        "on",
        ON_OFF,
        description="Default: tester and devops exit gates hold a merged PR's release.\n"
        "Off: no gate labels are applied; manual operations in a live plan are then "
        "refused, as nothing would hold them.",
    )


class Commit(_Closed):
    with_issue: str = Field(
        "{type}({scope}): {summary} (#{issue})",
        description="Default: fr's own commit subjects when the run has an issue.\n"
        "Placeholders: {type} {scope} {summary} {issue}. A different template moves the "
        "subject format that tooling reading fr's commits expects.",
    )
    without_issue: str = Field(
        "{type}({scope}): {summary}",
        description="Default: fr's own commit subjects when the run has no issue.\n"
        "Placeholders: {type} {scope} {summary}; {issue} is refused here.",
    )

    @field_validator("with_issue")
    @classmethod
    def _with(cls, v: str) -> str:
        return _check_template(v, allow_issue=True)

    @field_validator("without_issue")
    @classmethod
    def _without(cls, v: str) -> str:
        return _check_template(v, allow_issue=False)


class PrSections(_Closed):
    proportionality: OnOffType = _choice(
        "on",
        ON_OFF,
        description="Default: the PR body carries `## Proportionality`.\n"
        "Off: the section is not rendered or required; `fr plan proportionality` still "
        "shows the figures.",
    )
    cost: OnOffType = _choice(
        "on",
        ON_OFF,
        description="Default: the PR body carries `## Cost`.\n"
        "Off: the section is not rendered or required; `fr run cost` still shows the figures.",
    )
    settle: OnOffType = _choice(
        "on",
        ON_OFF,
        description="Default: the PR body carries `## PR settle`.\n"
        "Off: the section is not rendered or required; `fr pr settle` still reports, and "
        "deliver's settle check still runs as git.settle says.",
    )

    @model_validator(mode="before")
    @classmethod
    def _known_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for k in data:
                if k not in PR_SECTIONS:
                    raise ValueError(f"unknown key {k}; allowed: " + ", ".join(PR_SECTIONS))
        return data


class Forge(_Closed):
    labels: OnOffType = _choice(
        "on",
        ON_OFF,
        description="Default: fr applies its lifecycle labels on the forge.\n"
        "Off: no labels; whatever reads them (gates, triage claims) goes blind.",
    )
    comments: OnOffType = _choice(
        "on",
        ON_OFF,
        description="Default: fr posts its marker comments on issues and PRs.\n"
        "Off: no comments; claims and batch markers are not recorded on the forge.",
    )
    issues: OnOffType = _choice(
        "on",
        ON_OFF,
        description="Default: fr opens and updates tracking issues.\n"
        "Off: no issues are created; work is tracked only in the repo's own files.",
    )
    pr_body: BodyType = _choice(
        "full",
        PR_BODIES,
        description="Default: the PR body carries the full rendered record.\n"
        "Minimal: the live PR stays plain and the full render is kept as a file.",
    )
    report_comment: OnOffType = _choice(
        "off",
        ON_OFF,
        description="Default: CI posts no report comment.\n"
        "On: CI keeps one report comment on the PR; needs forge.comments on.",
    )
    pr_sections: PrSections = Field(
        default_factory=PrSections,
        description="Which optional PR-body sections fr renders (schema 3 only).",
    )


class Settle(_Closed):
    conflicts: SettleModeType = _choice(
        "fix",
        SETTLE_MODES,
        description="Default fix: fr waits for the PR's mergeability and fixes a conflict.\n"
        "Report: waits and reports it. Off: today's behaviour, nothing is read.",
    )
    ci: SettleModeType = _choice(
        "fix",
        SETTLE_MODES,
        description="Default fix: fr waits for the PR's CI and fixes a red or missing run.\n"
        "Report: waits and reports it. Off: today's behaviour, nothing is read.",
    )


class Git(_Closed):
    push: AskType = _choice(
        "auto",
        AUTO_ASK,
        description="Default: fr pushes without asking.\n"
        "Ask: fr asks before every push; refused for unattended triage drivers.",
    )
    pr: AskType = _choice(
        "auto",
        AUTO_ASK,
        description="Default: fr opens the PR without asking (always a draft).\n"
        "Ask: fr asks first; ready and merge are never fr's either way.",
    )
    history: HistoryType = _choice(
        "keep",
        HISTORIES,
        description="Default: every commit is kept as made.\n"
        "Squash-unpushed: unpushed commits are squashed before a push; pushed history is "
        "never rewritten.",
    )
    commit: Commit = Field(
        default_factory=lambda: Commit.model_validate({}),
        description="Commit subject templates (the defaults are today's).",
    )
    settle: Settle = Field(
        default_factory=Settle,
        description="Whether a delivered PR waits for mergeability and CI (fr pr settle).",
    )


class Triage(_Closed):
    state_repo: Annotated[str | None, AfterValidator(_slug)] = Field(
        None,
        description="Default: none; a triage scope of this one repo keeps its state ref in this\n"
        "repo (or, collected from a stealth workspace, in its tracking repo).\n"
        "OWNER/REPO: the repo that keeps the scope's `fr-triage/<scope-id>` branch, used\n"
        "when the scope records none yet. Needs `schema: 2`. Read from the configuration\n"
        "space; under quiet it counts only while fr-config is protected. The privacy\n"
        "guard still refuses a private issue to a public state repo.",
    )


class Workflows(_Closed):
    disabled: list[str] = Field(
        default_factory=list,
        description="Default: every shipped and repo-authored workflow shape can start a run.\n"
        "A listed shape is refused by `fr run start`, a brainstorm's shape rebind and\n"
        "`fr run adopt`; a run already started on it keeps going.",
    )


class Settings(_Closed):
    schema_: Annotated[Literal[1, 2, 3], BeforeValidator(_strict_int)] = Field(
        1, alias="schema", description="The settings schema version this file is written for."
    )
    placement: PlacementType = _choice(
        "repo",
        PLACEMENTS,
        description="Default: artifacts live on the feature branch.\n"
        "Quiet keeps them on the orphan `fr` branch, switched on by that branch's own\n"
        "settings.yaml (`fr settings init --quiet`), never by this key in .fr/settings.yaml;\n"
        "stealth is not yet served.",
    )
    artifacts: Artifacts = Field(
        default_factory=Artifacts,
        description="Policy kinds only: spec, plan, journals and runs have no key.",
    )
    forge: Forge = Field(default_factory=Forge, description="What fr writes to the forge.")
    git: Git = Field(default_factory=Git, description="How fr drives git.")
    triage: Triage = Field(
        default_factory=lambda: Triage.model_validate({}),
        description="Triage of this repo (schema 2 only).",
    )
    workflows: Workflows = Field(
        default_factory=Workflows,
        description="Which workflow shapes this repo offers (schema 3 only).",
    )

    @model_validator(mode="before")
    @classmethod
    def _schema_3_keys(cls, data: Any) -> Any:
        """Naming a schema-3 key at all, empty or not, declares `schema: 3` (R1)."""
        if not isinstance(data, dict):
            return data
        named = []
        if "workflows" in data:
            named.append("workflows")
        forge = data.get("forge")
        if isinstance(forge, dict) and "pr_sections" in forge:
            named.append("forge.pr_sections")
        schema = data.get("schema")
        if named and not (schema == 3 and isinstance(schema, int) and not isinstance(schema, bool)):
            raise ValueError(f"{named[0]} needs schema: 3")
        return data

    @model_validator(mode="after")
    def _triage_needs_schema_2(self) -> Settings:
        if self.triage.state_repo is not None and self.schema_ < 2:
            raise ValueError("triage.state_repo needs `schema: 2` (R20)")
        return self


def _dotted(loc: tuple[Any, ...]) -> str:
    return ".".join(str(p) for p in loc) or "(file)"


def parse_settings(data: object, *, source: str) -> Settings:
    """*data* as `Settings`, or `SettingsError` naming *source* and the dotted key."""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise SettingsError(f"{source}: settings must be a mapping, got {type(data).__name__}")
    schema = data.get("schema")
    if isinstance(schema, int) and not isinstance(schema, bool) and schema > max(SCHEMAS):
        raise SettingsError(
            f"{source}: schema: {schema} is newer than this fr understands "
            f"(schema {SCHEMA_VERSION}); upgrade fr"
        )
    try:
        return Settings.model_validate(data)
    except ValidationError as e:
        err = e.errors()[0]
        raise SettingsError(f"{source}: {_dotted(err['loc'])}: {err['msg']}") from e
