"""The `acceptance-fragment` `-design` name repair (spec
2026-11-17-batch-acceptance-edits R13-R16, §F; derio-net/super-fr#1461).

Fragments created before #1451 are `<slug>-design.yaml` with `feature: <slug>-design`;
every writer since creates `<slug>.yaml`, so one feature can hold two fragments. This
renames the old spelling to `<slug>.yaml` (its `feature:` set to `<slug>`), or merges it
into an existing `<slug>.yaml` by `fr.acceptance.spelling.merge_spellings`: the slug
file's entries first, an entry identical in both once, an id held differently refused.

A `Repair`, not a `SchemaMigration`: the fragment's shape has not moved; its name and
`feature:` key are a constraint. Everything is built in memory first, and the fold of
the new set must equal the fold of the old one, row for row (R15), before a byte moves:
then `<slug>.yaml` is written atomically and the `-design` file deleted. The deleted
path is the action's own, so `MigrationReport.changed_paths` names it and the migration
commit stages its deletion. `<slug>.yaml` is a companion, so the uncommitted-changes veto
holds the repair back while the operator is editing it (R16).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from fr.acceptance.edit import append_amendment, render_fragment
from fr.acceptance.fold import fold_texts
from fr.acceptance.fragment import Fragment, parse_fragment
from fr.acceptance.model import AcceptanceError
from fr.acceptance.spelling import design_slug, merge_spellings
from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.runner import MIGRATIONS, Repair

REPAIR_NAME = "design-name"

_FEATURE_RE = re.compile(r"^feature:[^\n]*$", re.MULTILINE)


def _parse(path: Path) -> Fragment:
    return parse_fragment(path.read_text(encoding="utf-8"), source=path.name)


def _slug(path: Path) -> str | None:
    """The slug *path* is the old spelling of: its name ends `-design.yaml` and its
    `feature:` key is its stem. A file that does not parse, or names another feature,
    is the structure validator's to report, never this repair's."""
    if not path.name.endswith("-design.yaml") or not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    feature = data.get("feature") if isinstance(data, dict) else None
    return design_slug(path.name, feature) if isinstance(feature, str) else None


def _applies(path: Path) -> bool:
    return _slug(path) is not None


def _target(path: Path) -> Path:
    slug = _slug(path) or path.stem.removesuffix("-design")
    return path.with_name(f"{slug}.yaml")


def _render(frag: Fragment) -> str:
    text = render_fragment(frag.feature, frag.repo, frag.rows)
    for amendment in frag.amendments:
        text = append_amendment(text, amendment)
    return text


def _renamed_text(text: str, design: Fragment, slug: str) -> str:
    """*text* with only its `feature:` line rewritten, when that parses back to the
    renamed fragment; else the fragment re-rendered."""
    new = _FEATURE_RE.sub(f"feature: {slug}", text, count=1)
    want = design.model_copy(update={"feature": slug})
    try:
        if parse_fragment(new, source=f"{slug}.yaml") == want:
            return new
    except Exception:  # noqa: BLE001  (fall back to the one renderer)
        pass
    return _render(want)


def _matrix(texts: dict[str, str]) -> tuple[dict[str, object], dict[str, object]]:
    eff = fold_texts(texts)
    return {r.id: r for r in eff.matrix.rows}, {r.id: r for r in eff.retired}


def _fn(path: Path) -> list[Path]:
    slug = _slug(path)
    if slug is None:  # the runner re-asks `applies` first; be safe anyway
        return []
    target = path.with_name(f"{slug}.yaml")
    design_text = path.read_text(encoding="utf-8")
    design = parse_fragment(design_text, source=path.name)
    primary = _parse(target) if target.is_file() else None
    merged = merge_spellings(primary, design, slug)
    new_text = _renamed_text(design_text, design, slug) if primary is None else _render(merged)

    def key(p: Path) -> str:
        return f"{p.parent.name}/{p.name}"

    texts = {key(p): p.read_text(encoding="utf-8") for p in sorted(path.parent.glob("*.yaml"))}
    after = {k: t for k, t in texts.items() if k not in (key(path), key(target))}
    after[key(target)] = new_text
    try:
        before = _matrix(texts)
    except AcceptanceError:
        # An entry the two files both hold makes the old set unfoldable (a row defined
        # twice): what it meant is each entry once, which is the -design file without
        # the entries `<slug>.yaml` already holds.
        if primary is None:
            raise
        rest = design.model_copy(
            update={
                "rows": merged.rows[len(primary.rows) :],
                "amendments": merged.amendments[len(primary.amendments) :],
            }
        )
        before = _matrix({**texts, key(path): _render(rest)})
    if _matrix(after) != before:
        raise ValueError(
            f"{path.name}: renaming it to {target.name} would change the effective "
            "matrix; reconcile the two by hand, then migrate"
        )
    write_text_atomic(target, new_text)
    path.unlink()
    return [target]


MIGRATIONS.register(
    Repair(
        kind="acceptance-fragment",
        name=REPAIR_NAME,
        applies=_applies,
        fn=_fn,
        companions=lambda p: [_target(p)],
        description=(
            "acceptance-fragment repair: rename a `<slug>-design.yaml` fragment to "
            "`<slug>.yaml`, merging into an existing one (#1461)"
        ),
    )
)
