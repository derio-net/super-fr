"""Entry point for `python -m fr_vk.bridge`.

The bridge daemon is NOT a public `vk` CLI verb (E1). Operators invoke
it via the wrapper that `scripts/install.sh --install-bridge` writes,
which `exec`s this module.
"""

from __future__ import annotations

from fr_vk.bridge_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
