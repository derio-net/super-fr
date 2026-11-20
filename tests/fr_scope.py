"""The fast advisory tier, `pytest --fr-scope [<base-ref>]` (spec
2026-11-19-local-suite-cost R6, R7, §3.E).

Pure selection over an `ast` import index of `tests/**/*.py`; `tests/conftest.py`
wires it into pytest. The tier is ADVISORY: tests that start `fr` as a subprocess
are invisible to an import graph, so it makes no claim to be sound. CI is the suite
evidence, and any session that is not the whole configured suite prints
`ADVISORY_LINE`, which fr refuses as a `tests` log.

The selection, for a set of changed repo-relative paths:

- a changed, added or untracked test module (any `tests/**/*.py` with a test in it);
- a test module that imports a changed source module, or a module inside a changed
  package (importing `fr.run.x` runs `fr/run/__init__.py`), directly or through the
  `tests/` modules it imports, transitively within `tests/` only. Imports through
  source modules are not followed: nearly every test reaches `fr.cli`;
- a test module that imports a changed `tests/` module, transitively;
- every test module under the directory of a changed `conftest.py`;
- for a changed path that is neither a source module nor under `tests/` (an agent,
  a skill, a YAML file, a shell script), every test module whose source names the
  path's file name. Paths that still select nothing are named in one line
  (`unreached`), so a gap the import graph cannot see is visible.

`smoke` tests always run and `scenario` tests never do; both are item-level, so
they are decided in `keep_item`, not here.
"""

from __future__ import annotations

import ast
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from fr.run.ci_evidence import ADVISORY_LINE  # one definition: the line fr refuses

__all__ = ["ADVISORY_LINE"]

DEFAULT_BASE = ""  # `--fr-scope` given with no value: the base is the default ref


class ScopeError(Exception):
    """The fast tier cannot name its changed set (no base, no merge-base)."""


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if done.returncode != 0:
        raise ScopeError(f"git {' '.join(args)}: {done.stderr.strip() or done.returncode}")
    return done.stdout


def changed_paths(root: Path, base: str) -> set[str]:
    """Repo-relative paths changed since the merge-base of `base` and HEAD (the
    working tree included), plus untracked files git does not ignore."""
    merge_base = _git(root, "merge-base", base, "HEAD").strip()
    # `--no-renames`: a rename is its old path deleted and its new one added, so
    # the tests that import the OLD module (now broken) are selected too.
    diff = _git(root, "diff", "--name-only", "--no-renames", merge_base)
    untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    return {line for line in (diff + untracked).splitlines() if line.strip()}


def resolve_base(root: Path, value: str) -> str:
    """`value`, or the repo's default ref (`fr.git.remote_default_ref`) when the
    option was given with no value."""
    if value != DEFAULT_BASE:
        return value
    from fr.git import GitRefusal, remote_default_ref

    ref = remote_default_ref(root)
    if isinstance(ref, GitRefusal):
        raise ScopeError(
            f"--fr-scope: no default ref to diff against ({ref.reason}); "
            "name one: --fr-scope <base-ref>"
        )
    if not isinstance(ref, str) or not ref:
        raise ScopeError(
            "--fr-scope: no default ref to diff against (no remote HEAD or default "
            "branch); name one: --fr-scope <base-ref>"
        )
    return ref


def source_module(path: str) -> str | None:
    """The dotted module a source path holds (`packages/<p>/src/<m>.py`), else None."""
    parts = PurePosixPath(path).parts
    if len(parts) < 4 or parts[0] != "packages" or parts[2] != "src":
        return None
    if not path.endswith(".py"):
        return None
    mod = list(parts[3:])
    mod[-1] = mod[-1].removesuffix(".py")
    if mod[-1] == "__init__":
        mod.pop()
    return ".".join(mod) or None


def tests_module(path: str) -> str | None:
    """The dotted module of a `tests/**/*.py` path, else None."""
    p = PurePosixPath(path)
    if not p.parts or p.parts[0] != "tests" or p.suffix != ".py":
        return None
    mod = list(p.with_suffix("").parts)
    if mod[-1] == "__init__":
        mod.pop()
    return ".".join(mod)


def is_test_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return name.startswith("test_") and name.endswith(".py")


def imported_names(source: str, module: str, *, is_package: bool = False) -> set[str]:
    """Every dotted name a module's imports name. `from a.b import c` names
    `a.b.c` (c may be a module or an attribute: either way `a.b` runs). Raises
    `SyntaxError` for a source `ast` cannot parse (`ImportIndex.build` records it)."""
    names: set[str] = set()
    tree = ast.parse(source)
    package = module.split(".") if is_package else module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = package[: len(package) - (node.level - 1)] if node.level > 1 else package
                base = ".".join([*anchor, *([node.module] if node.module else [])])
            else:
                base = node.module or ""
            for alias in node.names:
                names.add(f"{base}.{alias.name}" if base else alias.name)
            if base:
                names.add(base)
    return names


@dataclass(frozen=True)
class ImportIndex:
    """`tests/` module path -> the names its imports name, and -> its source
    (for the file-name mentions a non-Python change selects by). `unparseable`
    holds the modules `ast` could not parse: their imports select nothing, and
    `unparseable_line` names them so the gap is visible."""

    imports: Mapping[str, frozenset[str]]
    sources: Mapping[str, str] = field(default_factory=dict)
    unparseable: frozenset[str] = frozenset()

    @classmethod
    def build(cls, root: Path) -> ImportIndex:
        out: dict[str, frozenset[str]] = {}
        sources: dict[str, str] = {}
        broken: set[str] = set()
        for file in sorted((root / "tests").rglob("*.py")):
            rel = file.relative_to(root).as_posix()
            module = tests_module(rel)
            if module is None:
                continue
            text = file.read_text(encoding="utf-8", errors="replace")
            try:
                names = imported_names(text, module, is_package=file.name == "__init__.py")
            except SyntaxError:
                broken.add(rel)
                names = set()
            out[rel] = frozenset(names)
            sources[rel] = text
        return cls(out, sources, frozenset(broken))


def _names_changed_source(name: str, changed_modules: set[str]) -> bool:
    return any(name == c or name.startswith(c + ".") for c in changed_modules)


def _mentions(index: ImportIndex, path: str) -> set[str]:
    """Test modules whose source names `path`'s file name: the only reach fr can
    see for a change no import names (an agent, a skill, YAML, a script)."""
    name = PurePosixPath(path).name
    return {rel for rel, text in index.sources.items() if is_test_file(rel) and name in text}


def _is_import_reachable(path: str) -> bool:
    return source_module(path) is not None or PurePosixPath(path).parts[:1] == ("tests",)


def select(index: ImportIndex, changed: Iterable[str]) -> set[str]:
    """The test module paths the fast tier runs for `changed` (repo-relative)."""
    changed = set(changed)
    changed_sources = {m for p in changed if (m := source_module(p))}
    by_module = {m: rel for rel in index.imports if (m := tests_module(rel))}

    # A `tests/` module is "hot" when it changed or names a changed source module.
    hot = {
        rel
        for rel, names in index.imports.items()
        if rel in changed or any(_names_changed_source(n, changed_sources) for n in names)
    }
    # Spread heat backwards along tests/-internal imports until nothing moves.
    importers: dict[str, set[str]] = {rel: set() for rel in index.imports}
    for rel, names in index.imports.items():
        for name in names:
            target = by_module.get(name)
            if target is not None and target != rel:
                importers[target].add(rel)
    stack = list(hot)
    while stack:
        for importer in importers.get(stack.pop(), ()):
            if importer not in hot:
                hot.add(importer)
                stack.append(importer)

    selected = {rel for rel in hot if is_test_file(rel)}
    for path in changed:
        p = PurePosixPath(path)
        if p.name == "conftest.py":
            prefix = p.parent.as_posix() + "/"
            selected |= {
                rel for rel in index.imports if is_test_file(rel) and rel.startswith(prefix)
            }
        elif is_test_file(path) and path.startswith("tests/"):
            selected.add(path)
        elif not _is_import_reachable(path):
            selected |= _mentions(index, path)
    return selected


def unreached(index: ImportIndex, changed: Iterable[str]) -> list[str]:
    """The changed code paths (fr's run artifacts excluded) that select no test on
    their own: what the fast tier covers with the smoke set alone. Sorted."""
    from fr.run.code_tree import is_code_path

    return sorted(p for p in set(changed) if is_code_path(p) and not select(index, {p}))


def unreached_line(paths: Sequence[str], limit: int = 10) -> str:
    """The one line naming `unreached` paths (empty when there are none)."""
    if not paths:
        return ""
    shown = ", ".join(paths[:limit])
    more = f", +{len(paths) - limit} more" if len(paths) > limit else ""
    n = len(paths)
    return f"fr-scope: no test reaches {n} changed path{'' if n == 1 else 's'}: {shown}{more}"


def unparseable_line(index: ImportIndex, limit: int = 10) -> str:
    """The one line naming the `tests/` files the index could not parse (empty when
    there are none): no import selects through them, whatever changed."""
    paths = sorted(index.unparseable)
    if not paths:
        return ""
    shown = ", ".join(paths[:limit])
    more = f", +{len(paths) - limit} more" if len(paths) > limit else ""
    n = len(paths)
    return (
        f"fr-scope: {n} test file{'' if n == 1 else 's'} did not parse, so no import "
        f"selects through {'it' if n == 1 else 'them'}: {shown}{more}"
    )


def reasons_line(reasons: Sequence[str]) -> str:
    """The line printed just before `ADVISORY_LINE`: why this session is advisory.
    The advisory line itself stays fixed, for fr's whole-line match."""
    return f"fr-scope: advisory because {', '.join(reasons)}"


def keep_item(rel_path: str, markers: Iterable[str], selected: set[str]) -> bool:
    """Whether the fast tier runs one collected item."""
    marks = set(markers)
    if "scenario" in marks:
        return False
    return "smoke" in marks or rel_path in selected


def advisory_reasons(
    *,
    fr_scope: str | None,
    markexpr: str,
    keyword: str,
    args_source: str,
    last_failed: bool,
    stepwise: bool,
    ignore: Sequence[str] | None,
    ignore_glob: Sequence[str] | None,
    deselect: Sequence[str] | None,
    maxfail: int,
    testpaths_overridden: bool,
    collect_only: bool = False,
) -> list[str]:
    """Why a session is not the whole configured suite (R7); empty when it is.
    `args_source` is the name of pytest's `Config.ArgsSource`: only `TESTPATHS`
    collects the configured suite (`ARGS` is explicit paths, `INVOCATION_DIR` a
    run from a directory other than the root)."""
    reasons = []
    if fr_scope is not None:
        reasons.append("--fr-scope")
    if markexpr.strip():
        reasons.append(f"-m {markexpr!r}")
    if keyword.strip():
        reasons.append(f"-k {keyword!r}")
    if args_source == "ARGS":
        reasons.append("explicit paths")
    elif args_source != "TESTPATHS":
        reasons.append(f"collected from {args_source.lower()}, not testpaths")
    if last_failed:
        reasons.append("--lf")
    if stepwise:
        reasons.append("--sw")
    for flag, values in (
        ("--ignore", ignore),
        ("--ignore-glob", ignore_glob),
        ("--deselect", deselect),
    ):
        if values:
            reasons.append(f"{flag} {' '.join(values)}")
    if maxfail > 0:
        reasons.append(f"--maxfail={maxfail}")
    if testpaths_overridden:
        reasons.append("-o testpaths=")
    if collect_only:
        reasons.append("--collect-only")  # nothing ran
    return reasons


def session_reasons(config: Any) -> list[str]:
    """`advisory_reasons` read off a `pytest.Config` (its options at pytest's own
    defaults: None for the list options, 0 for `maxfail`)."""
    o = config.option
    overrides = getattr(o, "override_ini", None) or []
    return advisory_reasons(
        fr_scope=config.getoption("--fr-scope"),
        markexpr=getattr(o, "markexpr", "") or "",
        keyword=getattr(o, "keyword", "") or "",
        args_source=config.args_source.name,
        last_failed=bool(getattr(o, "lf", False)),
        stepwise=bool(getattr(o, "stepwise", False)),
        ignore=getattr(o, "ignore", None),
        ignore_glob=getattr(o, "ignore_glob", None),
        deselect=getattr(o, "deselect", None),
        maxfail=int(getattr(o, "maxfail", 0) or 0),
        testpaths_overridden=any(
            str(item).split("=", 1)[0].strip() == "testpaths" for item in overrides
        ),
        collect_only=bool(getattr(o, "collectonly", False)),
    )
