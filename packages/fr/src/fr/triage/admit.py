"""The admission of an issue, pinned to its content (spec 2026-11-22-triage-hardening R2-R4, §B;
spec 2026-11-28-triage-privacy R1-R3).

The `ready-fr` label alone admits nothing: an author can edit the title or body, or add or edit
a comment, after an operator applied it. `fr triage admit` therefore posts one hidden marker
comment holding the digest of the content it admitted, comments by outsiders included:

    <!-- fr-admit:{"v":2,"digest":"sha256:<hex>"} -->
    Admitted for fr triage. ...

and intake admits a labelled issue only while the latest trusted marker's digest equals the
issue's current one (`fr.triage.intake.intake_reason`). Trust is the claim marker's rule,
`fr.triage.claims.trusted_author`: a `claim_trusted` login, or an OWNER, MEMBER or
COLLABORATOR association. A marker that does not parse, or is not version 2, is ignored: a
version-1 digest did not cover comments (R2).

Everything here is pure: comments in, a digest out. `content_digest` is the ONE function
both `fr triage admit` and collect call (R3).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Collection, Iterable, Mapping
from datetime import UTC, datetime

from fr.triage.claims import TRUSTED_ASSOCIATIONS, trusted_author
from fr.utc_time import parse_as_utc

ADMIT_PREFIX = "<!-- fr-admit:"
_SUFFIX = " -->"
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_comment(comment: Mapping[str, object]) -> tuple[str, str, int, str]:
    """`(login, time, id, body)` of *comment* in the one form both forge adapters agree on
    (R1): the login lowercased with a trailing `[bot]` removed (`ghost` when empty), the time
    as UTC `YYYY-MM-DDTHH:MM:SSZ` (`""` when it does not parse), the id (-1 when missing)
    and the body with `\\r\\n` read as `\\n`."""
    login = str(comment.get("author") or "").lower()
    login = login.removesuffix("[bot]") or "ghost"
    at = parse_as_utc(comment.get("created_at"))
    stamp = at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if at else ""
    raw_id = comment.get("id")
    cid = raw_id if isinstance(raw_id, int) and not isinstance(raw_id, bool) else -1
    body = str(comment.get("body") or "").replace("\r\n", "\n")
    return login, stamp, cid, body


def pinned(comment: Mapping[str, object], pinned_authors: Collection[str]) -> bool:
    """*comment* is pinned by an admission: its association is not OWNER, MEMBER or
    COLLABORATOR and its author is not in *pinned_authors* (the repo's `pr_authors`; the
    viewer is no part of this, so every caller agrees whatever account it runs as)."""
    if str(comment.get("association") or "").upper() in TRUSTED_ASSOCIATIONS:
        return False
    # Both sides in the canonical form (lowercased, `[bot]` dropped), so the REST login
    # `x[bot]` and the GraphQL login `x` give one verdict whichever spelling is listed.
    allowed = {a.lower().removesuffix("[bot]") for a in pinned_authors}
    return str(comment.get("author") or "").lower().removesuffix("[bot]") not in allowed


def content_digest(
    title: str,
    body: str,
    *,
    comments: Iterable[Mapping[str, object]],
    pinned_authors: Collection[str],
) -> str:
    """`sha256:<hex>` over the JSON framing `{"v":2,"title":...,"body":...,"comments":[[login,
    time, id, body], ...]}` (sorted keys, compact, not ASCII-escaped) of the full *title* and
    *body* and each pinned comment, with `\\r\\n` read as `\\n` in every text field (R1).
    JSON framing means body text that imitates a comment can never hash like one. Callers pass
    the forge's record, never a truncated body, and both keyword arguments are required, so no
    caller silently digests the title and body alone. The ONE function `fr triage admit`,
    collect and the dispatch re-read all call."""
    rows = sorted(
        (canonical_comment(c) for c in comments if pinned(c, pinned_authors)),
        key=lambda r: (r[1], r[2], r[0], r[3]),
    )
    doc = {
        "v": 2,
        "title": title.replace("\r\n", "\n"),
        "body": body.replace("\r\n", "\n"),
        "comments": [[login, stamp, cid, text] for login, stamp, cid, text in rows],
    }
    text = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def admit_marker(digest: str, *, key: str | None = None) -> str:
    """The comment body admitting the content *digest* names: the hidden marker line, then
    one human line saying who may change it."""
    payload = json.dumps({"v": 2, "digest": digest}, separators=(",", ":"))
    again = f"`fr triage admit {key}`" if key else "`fr triage admit`"
    line = (
        "Admitted for fr triage. Only a maintainer can change this admission: an edit to "
        "the title or body, or a new or edited comment by an outside author, voids it, and "
        f"a maintainer re-admits the issue with {again}."
    )
    return f"{ADMIT_PREFIX}{payload}{_SUFFIX}\n{line}"


def parse_admit(body: str) -> str | None:
    """The digest of the admit marker *body* opens with; None for any other comment and for
    a malformed marker (a bad JSON payload, a version other than 2, a digest of another
    form)."""
    first = body.lstrip().split("\n", 1)[0].rstrip()
    if not first.startswith(ADMIT_PREFIX) or not first.endswith(_SUFFIX):
        return None
    try:
        data = json.loads(first[len(ADMIT_PREFIX) : -len(_SUFFIX)])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("v") != 2 or set(data) != {"v", "digest"}:
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
