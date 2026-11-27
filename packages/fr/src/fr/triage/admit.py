"""The admission of an issue, pinned to its content (spec 2026-11-22-triage-hardening R2-R4, §B).

The `ready-fr` label alone admits nothing: an author can edit the title or body after an
operator applied it. `fr triage admit` therefore posts one hidden marker comment holding the
digest of the content it admitted:

    <!-- fr-admit:{"v":1,"digest":"sha256:<hex>"} -->
    Admitted for fr triage. ...

and intake admits a labelled issue only while the latest trusted marker's digest equals the
issue's current one (`fr.triage.intake.intake_reason`). Trust is the claim marker's rule,
`fr.triage.claims.trusted_author`: a `claim_trusted` login, or an OWNER, MEMBER or
COLLABORATOR association. A marker that does not parse is ignored.

Everything here is pure: comments in, a digest out. `content_digest` is the ONE function
both `fr triage admit` and collect call (R3).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Collection, Iterable, Mapping
from datetime import datetime

from fr.triage.claims import trusted_author
from fr.utc_time import parse_as_utc

ADMIT_PREFIX = "<!-- fr-admit:"
_SUFFIX = " -->"
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def content_digest(title: str, body: str) -> str:
    """`sha256:<hex>` over the full *title*, a blank line and the full *body*, with `\\r\\n`
    read as `\\n` (R3). Callers pass the forge's record, never a truncated body."""
    text = f"{title}\n\n{body}".replace("\r\n", "\n")
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def admit_marker(digest: str, *, key: str | None = None) -> str:
    """The comment body admitting the content *digest* names: the hidden marker line, then
    one human line saying who may change it."""
    payload = json.dumps({"v": 1, "digest": digest}, separators=(",", ":"))
    again = f"`fr triage admit {key}`" if key else "`fr triage admit`"
    line = (
        "Admitted for fr triage. Only a maintainer can change this admission: an edit to "
        f"the title or body voids it, and a maintainer re-admits the issue with {again}."
    )
    return f"{ADMIT_PREFIX}{payload}{_SUFFIX}\n{line}"


def parse_admit(body: str) -> str | None:
    """The digest of the admit marker *body* opens with; None for any other comment and for
    a malformed marker (a bad JSON payload, a version other than 1, a digest of another
    form)."""
    first = body.lstrip().split("\n", 1)[0].rstrip()
    if not first.startswith(ADMIT_PREFIX) or not first.endswith(_SUFFIX):
        return None
    try:
        data = json.loads(first[len(ADMIT_PREFIX) : -len(_SUFFIX)])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("v") != 1 or set(data) != {"v", "digest"}:
        return None
    digest = data["digest"]
    return digest if isinstance(digest, str) and _DIGEST_RE.match(digest) else None


def latest_admit(comments: Iterable[Mapping[str, object]], trusted: Collection[str]) -> str | None:
    """The digest of the latest admit marker, by `created_at`, whose comment's author is
    trusted (R4); None when there is none. *trusted* are lowercased logins."""
    allowed = {t.lower() for t in trusted}
    best: tuple[datetime, str] | None = None
    for comment in comments:
        digest = parse_admit(str(comment.get("body") or ""))
        if digest is None or not trusted_author(comment, allowed):
            continue
        # the claim reader's contract: a marker no time orders counts for nothing
        at = parse_as_utc(comment.get("created_at"))
        if at is None:
            continue
        if best is None or at >= best[0]:
            best = (at, digest)
    return best[1] if best else None
