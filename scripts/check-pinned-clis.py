#!/usr/bin/env python3
"""Re-download every pinned host-CLI asset and confirm its sha256 still matches (gh#576).

`fr init scaffold --backend gitlab|gitea` installs glab/tea from a pinned
release asset, verified by a recorded sha256 (`fr.isolation.scaffold.HOST_CLI_PINS`).
A pin can rot silently — an asset re-uploaded, moved or deleted — and the first
anyone would hear of it is a devcontainer failing postCreate. This script is the
check that fails on its own instead: one line per (cli, arch) asset, exit 1 on
any mismatch or fetch failure. `.github/workflows/pinned-clis.yml` runs it
weekly, on workflow_dispatch, and on PRs touching the pins or this script.

Run: `uv run python scripts/check-pinned-clis.py`
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping

from fr.isolation.scaffold import HOST_CLI_PINS, HostCliPin

TIMEOUT_SECONDS = 60
CHUNK_BYTES = 1 << 20

Fetch = Callable[[str], Iterable[bytes]]


def fetch_url(url: str) -> Iterator[bytes]:
    """Stream the asset in CHUNK_BYTES reads — never the whole thing in memory."""
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp:  # noqa: S310 - https pins only
        while chunk := resp.read(CHUNK_BYTES):
            yield chunk


def check(pins: Mapping[str, HostCliPin], fetch: Fetch) -> int:
    """Print one line per asset; return 0 when every asset matches, else 1."""
    failed = False
    for pin in pins.values():
        for arch, (url, expected) in pin.assets.items():
            label = f"{pin.name} {pin.version} {arch}"
            digest = hashlib.sha256()
            try:
                for chunk in fetch(url):
                    digest.update(chunk)
            except Exception as exc:  # noqa: BLE001 - any failure to fetch is a failed check
                print(f"FETCH-FAILED {label} {url}: {exc}")
                failed = True
                continue
            got = digest.hexdigest()
            if got == expected:
                print(f"OK {label}")
            else:
                print(f"MISMATCH {label} expected {expected} got {got}")
                failed = True
    return 1 if failed else 0


def main() -> None:
    sys.exit(check(HOST_CLI_PINS, fetch_url))


if __name__ == "__main__":
    main()
