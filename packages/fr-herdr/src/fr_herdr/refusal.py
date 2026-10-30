"""Private, bounded publication of redacted readiness evidence only."""

from __future__ import annotations

import json
import os
import secrets
import stat
from pathlib import Path
from typing import Any

MAX_BYTES = 65536
FILENAME = "readiness-refusal.json"


def publish(directory: Path, evidence: dict[str, Any]) -> None:
    """Require a pre-created private attempt directory; never follow path symlinks.

    Atomic no-clobber publication uses a hard link within the held directory.
    The temporary file contains only the caller's redacted projection. This does
    not promise crash durability or a bound on filesystem syscall latency.
    """
    data = json.dumps(evidence, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    if len(data) > MAX_BYTES:
        raise ValueError("evidence exceeds bound")
    if not directory.is_absolute() or ".." in directory.parts:
        raise ValueError("unsafe destination")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    temporary = None
    created = None
    try:
        for part in directory.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            if info.st_uid not in {0, os.getuid()} or info.st_mode & 0o022:
                raise ValueError("untrusted directory")
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("destination must be private")
        temporary = ".refusal-" + secrets.token_hex(16)
        out = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd
        )
        try:
            created = os.fstat(out)
            os.fchmod(out, 0o600)
            with os.fdopen(out, "wb", closefd=False) as stream:
                stream.write(data)
            os.link(temporary, FILENAME, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
        finally:
            os.close(out)
    finally:
        if temporary and created:
            try:
                info = os.stat(temporary, dir_fd=fd, follow_symlinks=False)
                if (info.st_dev, info.st_ino) == (created.st_dev, created.st_ino):
                    os.unlink(temporary, dir_fd=fd)
            except OSError:
                pass
        os.close(fd)
