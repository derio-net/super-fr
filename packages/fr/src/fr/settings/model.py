"""The closed settings model (spec 2026-11-04-repo-feature-settings, R4).

Every field carries a `description=`; `fr settings init` generates its comments from
them, so the file's documentation cannot drift from the schema.
"""

from __future__ import annotations

import string
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, field_validator

from fr.settings import SettingsError

SCHEMA_VERSION: Final = 1


def _on_off(v: Any) -> Any:
    """PyYAML reads a bare `on`/`off` as a bool; the documented values are the words."""
    if v is True:
        return "on"
    if v is False:
        return "off"
    return v


OnOff = Annotated[Literal["on", "off"], BeforeValidator(_on_off)]


def _check_template(v: str, *, allow_issue: bool) -> str:
    allowed = {"type", "scope", "summary"} | ({"issue"} if allow_issue else set())
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
    model_config = ConfigDict(extra="forbid", populate_by_name=False)


class Artifacts(_Closed):
    acceptance: OnOff = Field(
        "on",
        description="Default: the acceptance matrix and its rows are written.\n"
        "Off: no matrix rows are written and every surface reports it disabled by repo "
        "setting; a spec's Test Plan no longer feeds an acceptance gate.",
    )
    test_plan: OnOff = Field(
        "on",
        description="Default: specs carry a Test Plan.\n"
        "Off: the Test Plan is not required or checked; nothing is lost but the plan's "
        "business-level statement of what proves the feature.",
    )
    gates: OnOff = Field(
        "on",
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


class Forge(_Closed):
    labels: OnOff = Field(
        "on",
        description="Default: fr applies its lifecycle labels on the forge.\n"
        "Off: no labels; whatever reads them (gates, triage claims) goes blind.",
    )
    comments: OnOff = Field(
        "on",
        description="Default: fr posts its marker comments on issues and PRs.\n"
        "Off: no comments; claims and batch markers are not recorded on the forge.",
    )
    issues: OnOff = Field(
        "on",
        description="Default: fr opens and updates tracking issues.\n"
        "Off: no issues are created; work is tracked only in the repo's own files.",
    )
    pr_body: Literal["full", "minimal"] = Field(
        "full",
        description="Default: the PR body carries the full rendered record.\n"
        "Minimal: the live PR stays plain and the full render is kept as a file.",
    )
    report_comment: OnOff = Field(
        "off",
        description="Default: CI posts no report comment.\n"
        "On: CI keeps one report comment on the PR; needs forge.comments on.",
    )

    @field_validator("report_comment", mode="before")
    @classmethod
    def _rc(cls, v: Any) -> Any:
        return _on_off(v)


class Git(_Closed):
    push: Literal["auto", "ask"] = Field(
        "auto",
        description="Default: fr pushes without asking.\n"
        "Ask: fr asks before every push; refused for unattended triage drivers.",
    )
    pr: Literal["auto", "ask"] = Field(
        "auto",
        description="Default: fr opens the PR without asking (always a draft).\n"
        "Ask: fr asks first; ready and merge are never fr's either way.",
    )
    history: Literal["keep", "squash-unpushed"] = Field(
        "keep",
        description="Default: every commit is kept as made.\n"
        "Squash-unpushed: unpushed commits are squashed before a push; pushed history is "
        "never rewritten.",
    )
    commit: Commit = Field(
        default_factory=Commit, description="Commit subject templates (the defaults are today's)."
    )


class Settings(_Closed):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_: Literal[1] = Field(
        1, alias="schema", description="The settings schema version this file is written for."
    )
    placement: Literal["repo", "quiet", "stealth"] = Field(
        "repo",
        description="Default: artifacts live on the feature branch.\n"
        "Quiet or stealth keep them elsewhere; this fr cannot yet serve either.",
    )
    artifacts: Artifacts = Field(
        default_factory=Artifacts,
        description="Policy kinds only: spec, plan, journals and runs have no key.",
    )
    forge: Forge = Field(default_factory=Forge, description="What fr writes to the forge.")
    git: Git = Field(default_factory=Git, description="How fr drives git.")


def _dotted(loc: tuple[Any, ...]) -> str:
    return ".".join(str(p) for p in loc) or "(file)"


def parse_settings(data: object, *, source: str) -> Settings:
    """*data* as `Settings`, or `SettingsError` naming *source* and the dotted key."""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise SettingsError(f"{source}: settings must be a mapping, got {type(data).__name__}")
    schema = data.get("schema")
    if isinstance(schema, int) and not isinstance(schema, bool) and schema > SCHEMA_VERSION:
        raise SettingsError(
            f"{source}: schema: {schema} is newer than this fr understands "
            f"(schema {SCHEMA_VERSION}); upgrade fr"
        )
    try:
        return Settings.model_validate(data)
    except ValidationError as e:
        err = e.errors()[0]
        raise SettingsError(f"{source}: {_dotted(err['loc'])}: {err['msg']}") from e
