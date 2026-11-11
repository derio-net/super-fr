"""`.fr/docs.yaml` and a page's front matter (spec 2026-11-11-docs-currency R2, R4)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml
from pydantic import BaseModel, ConfigDict, Field

_FRONT = re.compile(r"\A---[ \t]*\r?\n(.*?\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_REVIEWED = re.compile(r"\d{4}-\d{2}-\d{2} \S.*")


class DocsConfig(BaseModel):
    """The strict `.fr/docs.yaml`: which files are pages, and what must be covered."""

    model_config = ConfigDict(extra="forbid")

    pages: list[str] = Field(default_factory=list)
    must_cover: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class Page:
    """A page: its path, the globs it covers and its `reviewed` stamp."""

    path: str
    covers: tuple[str, ...]
    reviewed: str


@dataclass(frozen=True)
class PageError:
    """Why a page's front matter is unusable (finding kind `bad-page`)."""

    path: str
    message: str


def parse_page(path: str, text: str) -> Page | PageError:
    """Read `covers` and `reviewed` from `text`'s front matter; other keys are ignored."""
    found = _FRONT.match(text)
    if found is None:
        return PageError(path, "no front matter (a page opens with a `---` block)")
    try:
        data = yaml.safe_load(found.group(1) or "")
    except yaml.YAMLError as e:
        return PageError(path, f"front matter is unreadable YAML: {e}".splitlines()[0])
    if not isinstance(data, dict):
        return PageError(path, "front matter is not a mapping")
    covers = data.get("covers")
    if covers is None:
        return PageError(path, "front matter lacks `covers`")
    if not isinstance(covers, list) or not all(isinstance(c, str) and c for c in covers):
        return PageError(path, "`covers` must be a list of path globs")
    reviewed = data.get("reviewed")
    if reviewed is None:
        return PageError(path, "front matter lacks `reviewed`")
    if not isinstance(reviewed, str) or _REVIEWED.fullmatch(reviewed.strip()) is None:
        return PageError(path, "`reviewed` must be `<ISO date> <one-line note>`")
    return Page(path, tuple(covers), reviewed.strip())
