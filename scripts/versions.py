#!/usr/bin/env python3
"""The one release-version value: a final `X.Y.Z` or a release candidate of it.

Spec 2026-10-14-exit-gates R25. An RC has two spellings and the release tooling reads
both: semver `X.Y.Z-rc.N` (tags, `plugin.json`, `marketplace.json`, `package.json`)
and PEP 440 `X.Y.ZrcN` (`pyproject.toml`, `uv.lock`, what `fr --version` prints).
`bump-version.py`, `version_surfaces.py`, `changes.py`, `floors.py` and `release.py`
all parse through `Version.parse`, so no reader int-splits an RC string.

Stdlib only, so it runs under `uv run --no-project`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

BUMPS = ("patch", "minor", "major")

_VERSION_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-rc\.(?P<semver_rc>[1-9]\d*)|rc(?P<pep_rc>[1-9]\d*))?$"
)
FINAL_RE = re.compile(r"^\d+\.\d+\.\d+$")
FINAL_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")
"""A final release tag: "the last final" matches this and nothing else."""
RC_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+-rc\.[1-9]\d*$")


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    rc: int | None = None  # None: a final

    @classmethod
    def parse(cls, text: str) -> Version:
        """`X.Y.Z`, `X.Y.Z-rc.N` or `X.Y.ZrcN` (N >= 1); anything else raises ValueError."""
        m = _VERSION_RE.match(text.strip())
        if m is None:
            raise ValueError(f"{text!r} is not X.Y.Z, X.Y.Z-rc.N or X.Y.ZrcN")
        rc = m.group("semver_rc") or m.group("pep_rc")
        return cls(
            int(m.group("major")),
            int(m.group("minor")),
            int(m.group("patch")),
            int(rc) if rc else None,
        )

    @classmethod
    def from_tag(cls, tag: str) -> Version:
        return cls.parse(tag.removeprefix("v"))

    @property
    def is_rc(self) -> bool:
        return self.rc is not None

    @property
    def final(self) -> Version:
        """The final this version is (or is a candidate for)."""
        return Version(self.major, self.minor, self.patch)

    @property
    def semver(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return base if self.rc is None else f"{base}-rc.{self.rc}"

    @property
    def pep440(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        return base if self.rc is None else f"{base}rc{self.rc}"

    @property
    def tag(self) -> str:
        return f"v{self.semver}"

    @property
    def key(self) -> tuple[int, int, int, int, int]:
        """Sort key: an RC sorts above the final before it and below its own final."""
        return (self.major, self.minor, self.patch, 0 if self.rc else 1, self.rc or 0)

    def __lt__(self, other: Version) -> bool:
        return self.key < other.key

    def __le__(self, other: Version) -> bool:
        return self.key <= other.key

    def __gt__(self, other: Version) -> bool:
        return self.key > other.key

    def __ge__(self, other: Version) -> bool:
        return self.key >= other.key

    def __str__(self) -> str:
        return self.semver

    def with_rc(self, n: int) -> Version:
        return Version(self.major, self.minor, self.patch, n)

    def implied_bump(self) -> str:
        """The bump that reaches this release from the last final before it: `X.0.0` is
        a major, `X.Y.0` a minor, anything else a patch."""
        if self.minor == 0 and self.patch == 0:
            return "major"
        return "minor" if self.patch == 0 else "patch"

    def bumped(self, bump: str | None) -> Version:
        """The final this version moves to under *bump* (None: no move).

        A final moves by *bump*. An RC of X.Y.Z is based on the last final it implies
        (`implied_bump`), so a bump it already carries, or a smaller one, lands on X.Y.Z;
        a bigger one moves X.Y.Z by it, which is the same as moving that last final.
        """
        if bump is not None and bump not in BUMPS:
            raise ValueError(f"unknown bump {bump!r}")
        if self.is_rc:
            if bump is None or BUMPS.index(bump) <= BUMPS.index(self.implied_bump()):
                return self.final
            return self.final.bumped(bump)
        if bump is None:
            return self
        if bump == "major":
            return Version(self.major + 1, 0, 0)
        if bump == "minor":
            return Version(self.major, self.minor + 1, 0)
        return Version(self.major, self.minor, self.patch + 1)


def normalize(text: str) -> str:
    """*text* in its semver spelling."""
    return Version.parse(text).semver
