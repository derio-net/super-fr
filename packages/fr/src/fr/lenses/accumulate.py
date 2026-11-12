"""The feature's lens set (spec 2026-11-12-review-lenses R7, §3.B).

`lens_set` is the one definition: the distinct lenses of every `lens` entry in the
run's spec and plan journals, plus the lenses every path rule in force requires for
a file in the feature's diff (`fr.proportionality.feature_diff`: merge-base..HEAD,
fr's own artifacts exempt), restricted to effective lenses. A journalled lens the
repo has since disabled is dropped with a warning naming it. Computed from the
branch as it stands when it is read; nothing is stored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fr.git import GitUnavailableError
from fr.lenses.model import LensError
from fr.lenses.resolve import effective_lenses
from fr.lenses.rules import (
    base_config_text,
    default_ref,
    head_config_text,
    matched,
    rules_in_force,
)

if TYPE_CHECKING:
    from fr.run.model import RunState


@dataclass(frozen=True)
class Reason:
    """One agent's addition of a lens: the reason, the step that added it (None from
    the command line), and the journal entry that records it."""

    text: str
    step: str | None
    entry: str
    scope: str


@dataclass(frozen=True)
class LensEntry:
    """One lens of the set: every reason an agent gave, and the rule and one
    matching file when a path rule requires it."""

    lens: str
    reasons: tuple[Reason, ...] = ()
    rule: tuple[str, ...] | None = None
    file: str | None = None


@dataclass(frozen=True)
class LensSet:
    lenses: tuple[LensEntry, ...] = ()
    warnings: tuple[str, ...] = field(default=())

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(e.lens for e in self.lenses)


def _journal_slugs(run: Any) -> tuple[str | None, str | None]:
    """`(spec slug, plan slug)` from the paths the run's steps emitted."""
    from fr.journal.model import spec_journal_slug

    spec = plan = None
    for record in run.steps.values():
        emitted = getattr(record, "emitted", None) or {}
        spec = spec or emitted.get("spec")
        plan = plan or emitted.get("plan")
    return (
        spec_journal_slug(Path(spec).stem) if spec else None,
        Path(plan).name if plan else None,
    )


def lens_set(root: Path, run: RunState) -> LensSet:
    """The lens set of `run`'s feature at `root`. Raises `LensError`."""
    spec_slug, plan_slug = _journal_slugs(run)
    return lens_set_for(root, spec_slug=spec_slug, plan_slug=plan_slug)


def _added(root: Path, spec_slug: str | None, plan_slug: str | None) -> dict[str, list[Reason]]:
    from fr.journal.model import JournalParseError, parse_journal, resolve_journal_read_path

    added: dict[str, list[Reason]] = {}
    for scope, slug in (("spec", spec_slug), ("plan", plan_slug)):
        if slug is None:
            continue
        path = resolve_journal_read_path(root, scope, slug)  # type: ignore[arg-type]
        if not path.is_file():
            continue
        try:
            entries = parse_journal(path.read_text())
        except JournalParseError as e:
            raise LensError(f"{path.name}: the {scope} journal does not parse: {e}") from e
        for e in entries:
            if e.kind == "lens" and e.lens is not None:
                added.setdefault(e.lens, []).append(Reason(e.title, e.step, e.id, scope))
    return added


def _changed(root: Path, ref: str | None) -> list[str] | None:
    from fr.proportionality import feature_diff, feature_merge_base

    if ref is None:
        return None
    try:
        base = feature_merge_base(root, ref)
        return None if base is None else [c.path for c in feature_diff(root, base)]
    except GitUnavailableError as e:
        raise LensError(f"git could not read the feature's diff: {e}") from e


def lens_set_for(root: Path, *, spec_slug: str | None, plan_slug: str | None) -> LensSet:
    """The lens set from the named journals and the branch's diff. Raises `LensError`."""
    effective = effective_lenses(root)
    added = _added(root, spec_slug, plan_slug)
    ref = default_ref(root)
    rules = rules_in_force(base_config_text(root, ref), head_config_text(root))
    changed = _changed(root, ref)
    warnings: list[str] = []
    if rules and changed is None:
        warnings.append(
            "no default branch to diff against, so no path rule was applied "
            "(fetch the remote, or set its HEAD)"
        )
    required = matched(rules, changed or [])
    out: list[LensEntry] = []
    for lens in sorted(set(added) | set(required)):
        reasons = tuple(added.get(lens, ()))
        if lens not in effective:
            why = "a path rule requires it" if lens in required else "an agent added it"
            warnings.append(f"lens {lens} is not effective in this repo and is dropped ({why})")
            continue
        hit = required.get(lens)
        out.append(
            LensEntry(
                lens=lens,
                reasons=reasons,
                rule=hit.paths if hit else None,
                file=hit.file if hit else None,
            )
        )
    return LensSet(lenses=tuple(out), warnings=tuple(warnings))
