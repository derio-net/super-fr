"""The claude-cloud mailbox: pending session requests and recorded sessions, as plain
data over the scope's state directory (cloud-triage R14, R15, §F).

Pure apart from the two files it is handed the directory of, `requests.yaml` and
`sessions.yaml`; both travel in the scope's state ref (`fr.triage.state_ref.REF_FILES`),
so a driver restored on a fresh workspace still holds them. Without a directory (a
runner built by `from_env` and never opened) everything stays in memory, and a mailbox
opened `read_only` (the board's read) never writes either file.

- A request has a stable id, `<item id>:<kind>:<n>`; *n* counts that item's requests of
  that kind, kept in `requests.yaml`'s `issued`, so a retried request is a new id and a
  re-emitted one the same id.
- A request is pending until a result names it. The agent executes the outbox with its
  session tools (`REQUEST_TABLE`) and records each result with `fr triage drive record`.
- Every session a `dispatch` or `rehome` creates carries two tags: the batch's item id
  (`tag`) and the request's own id (`request_tag`). The agent looks the request tag up
  before creating anything, so a request whose result was lost is replayed, never
  duplicated, even after a rehome left two sessions under the item's tag (p5-r2).
- A recorded session is matched by its session id; a tag only finds a session no record
  names (p5-r1). An archived session, or one whose close was recorded (`sessions.yaml`'s
  `closed`), releases its item and is never closed again (p5-r6).
- `status` requests are never stored: every pass asks one per recorded session with no
  pending close, id `<item id>:status:1`, and recording one updates that session's state.
- `record` validates every result, applies them in memory and saves once: a refused
  batch leaves both files byte-identical (p5-r4).
"""

from __future__ import annotations

import copy
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

REQUESTS_FILE = "requests.yaml"
SESSIONS_FILE = "sessions.yaml"

Kind = Literal["dispatch", "message", "close", "rehome", "status"]
FrStatus = Literal["working", "blocked", "idle", "done", "unknown", "absent"]

# R15: a cloud session's state onto fr's session statuses. `completed` is idle, not
# done: the agent finished its last turn and can still be messaged (spec §F).
STATE_MAP: Mapping[str, FrStatus] = {
    "working": "working",
    "blocked": "blocked",
    "review_ready": "idle",
    "completed": "idle",
    "failed": "blocked",
}
# A session in one of these states is gone: it releases its item (p5-r6).
ENDED_STATES = frozenset({"archived"})

CLOSE_OUTCOMES = frozenset({"closed", "busy", "absent"})
MESSAGE_OUTCOMES = frozenset({"sent", "refused"})
# The request kinds that create a session, so carry a request-scoped tag (p5-r2).
CREATING = frozenset({"dispatch", "rehome"})


@dataclass(frozen=True)
class Row:
    """One request kind: what the agent executes, and the result it records."""

    execute: str
    record: str


REQUEST_TABLE: Mapping[str, Row] = {
    "dispatch": Row(
        execute="list_sessions and look for one tagged `request_tag`; when one exists, "
        "create nothing and record its id; otherwise create_session(repo, branch, model, "
        "tags = [tag, request_tag], prompt)",
        record="{id, session: <session id>}, or {id, error} when the create failed",
    ),
    "message": Row(
        execute="send_message(session, text), unless a message carrying this request id "
        "was already sent",
        record="{id, outcome: sent | refused}",
    ),
    "close": Row(
        execute="archive_session(session) (archiving twice is harmless)",
        record="{id, outcome: closed | busy | absent}",
    ),
    "rehome": Row(
        execute="list_sessions and look for one tagged `request_tag`; when one exists, "
        "create nothing, archive_session on the old session and record its id; otherwise "
        "send_message(session, push and stop); at its next idle, create_session(repo, "
        "branch, model, tags = [tag, request_tag], prompt = the resume brief); then "
        "archive_session on the old session",
        record="{id, session: <new session id>}",
    ),
    "status": Row(
        execute="get_session(session)",
        record="{id, state, needs_action}",
    ),
}


def request_id(item: str, kind: str, n: int) -> str:
    return f"{item}:{kind}:{n}"


def split_id(rid: str) -> tuple[str, str, str] | None:
    """`(item, kind, n)` of a request id, or None when it is not one."""
    parts = rid.rsplit(":", 2)
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def map_state(state: object) -> FrStatus:
    """R15's mapping; anything else is `unknown`, never a guess."""
    return STATE_MAP.get(str(state), "unknown") if state is not None else "unknown"


@dataclass(frozen=True)
class Listed:
    """A session the agent listed or read (`--statuses`): its id, tags and state. An
    entry keyed by item (or session) id with no session id of its own has `session`
    None: it only ever updates a session already recorded (p5-r5)."""

    session: str | None
    tags: tuple[str, ...]
    state: str | None
    needs_action: str | None

    @property
    def ended(self) -> bool:
        return self.state in ENDED_STATES


def parse_statuses(raw: Any) -> list[Listed]:
    """The agent's statuses file, in any of its three shapes: `{"sessions": [...]}`, a
    bare list of `{id|session, tag|tags, state, needs_action}`, or a mapping keyed by item
    id (or session id) whose value is a state or such an object."""
    if raw is None:
        return []
    entries: list[tuple[str | None, Any]] = []
    if isinstance(raw, Mapping) and "sessions" in raw:
        raw = raw["sessions"]
    if isinstance(raw, list):
        entries = [(None, e) for e in raw]
    elif isinstance(raw, Mapping):
        entries = [(str(k), v) for k, v in raw.items()]
    else:
        raise ValueError("statuses: a list of sessions or a mapping of item id to state")
    out: list[Listed] = []
    for key, value in entries:
        body: Mapping[str, Any] = value if isinstance(value, Mapping) else {"state": value}
        session = body.get("id") or body.get("session")
        if not session and not key:
            raise ValueError(f"statuses: an entry names no session: {value!r}")
        raw_tags = body.get("tags")
        tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
        if body.get("tag"):
            tags.insert(0, str(body["tag"]))
        if key and key not in tags:
            tags.insert(0, key)
        needs = body.get("needs_action")
        state = body.get("state")
        out.append(
            Listed(
                session=str(session) if session else None,
                tags=tuple(dict.fromkeys(tags)),
                state=str(state) if state is not None else None,
                needs_action=str(needs) if needs else None,
            )
        )
    return out


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text())
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError(f"{path}: a mapping")
    return loaded


def _dump(data: Mapping[str, Any]) -> str:
    return yaml.safe_dump(dict(data), sort_keys=False, allow_unicode=True)


def _write(path: Path, text: str) -> None:
    """Write *text* atomically, and only when it differs from what is there."""
    if path.is_file() and path.read_text() == text:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class Mailbox:
    """The requests and sessions of one scope, loaded from (and saved to) *state_dir*;
    with *read_only*, loaded only (p5-r8)."""

    def __init__(
        self, state_dir: Path | None = None, statuses: Any = None, *, read_only: bool = False
    ) -> None:
        self.state_dir = state_dir
        self.read_only = read_only
        self._deferred = False
        requests = _read(state_dir / REQUESTS_FILE) if state_dir else {}
        sessions = _read(state_dir / SESSIONS_FILE) if state_dir else {}
        self.requests: list[dict[str, Any]] = [dict(r) for r in requests.get("requests") or []]
        self.issued: dict[str, int] = {
            str(k): int(v) for k, v in (requests.get("issued") or {}).items()
        }
        self.sessions: list[dict[str, Any]] = [dict(s) for s in sessions.get("sessions") or []]
        self.closed: list[str] = [str(s) for s in sessions.get("closed") or []]
        self.listed = parse_statuses(statuses)
        self._absorb(self.listed)
        self.save()

    # ------------------------------------------------------------------ storage

    def save(self) -> None:
        if self.state_dir is None or self.read_only or self._deferred:
            return
        if self.requests or self.issued or (self.state_dir / REQUESTS_FILE).is_file():
            _write(
                self.state_dir / REQUESTS_FILE,
                _dump({"requests": self.requests, "issued": self.issued}),
            )
        if self.sessions or self.closed or (self.state_dir / SESSIONS_FILE).is_file():
            data: dict[str, Any] = {"sessions": self.sessions}
            if self.closed:
                data["closed"] = self.closed
            _write(self.state_dir / SESSIONS_FILE, _dump(data))

    # ------------------------------------------------------------------ lookups

    def pending(self, item: str, kind: str) -> dict[str, Any] | None:
        return next((r for r in self.requests if r["item"] == item and r["kind"] == kind), None)

    def session_of(self, item: str) -> dict[str, Any] | None:
        return next((s for s in self.sessions if s.get("item") == item), None)

    def _recorded(self, session: str) -> dict[str, Any] | None:
        return next((s for s in self.sessions if s.get("session") == session), None)

    def _live(self) -> list[Listed]:
        """Listed sessions that are ours to find by tag: named, not ended, not closed."""
        return [
            x for x in self.listed if x.session and not x.ended and x.session not in self.closed
        ]

    def listed_for(self, item: str) -> Listed | None:
        """What the agent listed for *item*: its recorded session, matched by id (or a
        session-less entry keyed by the item or that id); with none recorded, a live
        session tagged with the item that no record names (p5-r1)."""
        recorded = self.session_of(item)
        if recorded is not None:
            sid = str(recorded["session"])
            return next(
                (
                    x
                    for x in self.listed
                    if x.session == sid or (x.session is None and {item, sid} & set(x.tags))
                ),
                None,
            )
        return next(
            (x for x in self._live() if item in x.tags and self._recorded(str(x.session)) is None),
            None,
        )

    def session_id(self, item: str) -> str | None:
        recorded = self.session_of(item)
        if recorded is not None:
            return str(recorded["session"])
        listed = self.listed_for(item)
        return listed.session if listed else None

    def held(self, items: Iterable[str]) -> set[str]:
        """Items with a pending dispatch, a recorded session, or a live listed tagged one."""
        tags = {t for x in self._live() for t in x.tags}
        return {
            i
            for i in items
            if self.pending(i, "dispatch") is not None
            or self.session_of(i) is not None
            or i in tags
        }

    def status(self, item: str) -> FrStatus:
        recorded, listed = self.session_of(item), self.listed_for(item)
        if listed is not None and listed.state is not None:
            return map_state(listed.state)
        if recorded is not None:
            return map_state(recorded.get("state"))
        if listed is not None or self.pending(item, "dispatch") is not None:
            return "unknown"
        return "absent"

    def note(self, item: str) -> str | None:
        """A blocked session's `needs_action` text (R15), else None."""
        if self.status(item) != "blocked":
            return None
        listed, recorded = self.listed_for(item), self.session_of(item)
        if listed is not None and listed.needs_action:
            return listed.needs_action
        text = recorded.get("needs_action") if recorded else None
        return str(text) if text else None

    # ------------------------------------------------------------------ requests

    def add(self, item: str, kind: Kind, **fields: Any) -> dict[str, Any]:
        key = f"{item}:{kind}"
        n = self.issued.get(key, 0) + 1
        self.issued[key] = n
        rid = request_id(item, kind, n)
        request = {"id": rid, "kind": kind, "item": item, **fields}
        if kind in CREATING:
            request["request_tag"] = rid
        self.requests.append(request)
        self.save()
        return request

    def outbox(self) -> list[dict[str, Any]]:
        out = [self._annotated(r) for r in self.requests]
        for s in self.sessions:
            item = str(s["item"])
            if self.pending(item, "close") is not None:  # being archived: nothing to ask
                continue
            out.append(
                self._annotated(
                    {
                        "id": request_id(item, "status", 1),
                        "kind": "status",
                        "item": item,
                        "session": s["session"],
                    }  # fmt: skip
                )
            )
        return out

    @staticmethod
    def _annotated(request: Mapping[str, Any]) -> dict[str, Any]:
        row = REQUEST_TABLE[str(request["kind"])]
        return {**request, "execute": row.execute, "record": row.record}

    # ------------------------------------------------------------------ results

    def _request(self, rid: str) -> dict[str, Any] | None:
        return next((r for r in self.requests if r["id"] == rid), None)

    def _validate(self, results: list[dict[str, Any]]) -> None:
        """Refuse a batch with a malformed outcome before anything is applied (p5-r4)."""
        for result in results:
            rid = result.get("id")
            request = self._request(rid) if isinstance(rid, str) else None
            if request is None:
                continue
            allowed = {"close": CLOSE_OUTCOMES, "message": MESSAGE_OUTCOMES}.get(request["kind"])
            if allowed is not None and result.get("outcome") not in allowed:
                raise ValueError(f"{rid}: outcome is one of {sorted(allowed)}")

    def record(self, results: list[dict[str, Any]]) -> list[str]:
        """Apply *results* all or nothing, then save once; the ids applied."""
        if not isinstance(results, list) or not all(isinstance(r, Mapping) for r in results):
            raise ValueError("results: a list of objects, one per request, each with its id")
        self._validate(results)
        closing = set()  # items whose session this record closes (p5-r3)
        for result in results:
            request = self._request(str(result.get("id")))
            if request is not None and request["kind"] == "close":
                if result.get("outcome") in ("closed", "absent"):
                    closing.add(str(request["item"]))
        saved = copy.deepcopy((self.requests, self.issued, self.sessions, self.closed))
        applied: list[str] = []
        self._deferred = True
        try:
            for result in results:
                rid = result.get("id")
                if isinstance(rid, str) and self._apply(rid, result, closing):
                    applied.append(rid)
        except BaseException:
            self.requests, self.issued, self.sessions, self.closed = saved
            raise
        finally:
            self._deferred = False
        self.save()
        return applied

    def _apply(self, rid: str, result: Mapping[str, Any], closing: set[str]) -> bool:
        parts = split_id(rid)
        if parts is not None and parts[1] == "status":
            if parts[0] in closing:  # closed in this same record: nothing left to update
                return True
            recorded = self.session_of(parts[0])
            if recorded is None:
                return False
            self._observe(recorded, result.get("state"), result.get("needs_action"))
            return True
        request = self._request(rid)
        if request is None:
            return False
        kind, item = request["kind"], str(request["item"])
        if kind == "dispatch":
            session = result.get("session")
            if not session:  # a failed create: still pending, asked again next pass
                return True
            self._record_session(request, str(session))
        elif kind == "close":
            outcome = result.get("outcome")
            if outcome not in CLOSE_OUTCOMES:
                raise ValueError(f"{rid}: outcome is one of {sorted(CLOSE_OUTCOMES)}")
            if outcome in ("closed", "absent"):
                for entry in [s for s in self.sessions if s.get("item") == item]:
                    self._end(entry, drop_close=False)  # this close is removed below
        elif kind == "message":
            outcome = result.get("outcome")
            if outcome not in MESSAGE_OUTCOMES:
                raise ValueError(f"{rid}: outcome is one of {sorted(MESSAGE_OUTCOMES)}")
            if outcome == "refused":  # retried next pass, as a new request
                self.requests.remove(request)
                self.message(item, str(request["session"]), str(request["body"]))
                return True
        elif kind == "rehome":
            session = result.get("session")
            if not session:
                return True  # not re-homed yet: asked again next pass
            self._rehomed(request, str(session))
        self.requests.remove(request)
        return True

    def message(self, item: str, session: str, body: str) -> dict[str, Any]:
        """The message request for *body*; a pending one with the same body is reused."""
        for r in self.requests:
            if r["item"] == item and r["kind"] == "message" and r.get("body") == body:
                return r
        n = self.issued.get(f"{item}:message", 0) + 1
        rid = request_id(item, "message", n)
        text = f"[fr request {rid}]\n\n{body}"
        return self.add(item, "message", session=session, text=text, body=body)

    # ------------------------------------------------------------------ sessions

    def _record_session(self, request: Mapping[str, Any], session: str) -> dict[str, Any]:
        item = str(request["item"])
        self.sessions = [s for s in self.sessions if s.get("item") != item]
        entry: dict[str, Any] = {"item": item, "session": session}
        for key in ("repo", "branch"):
            if request.get(key):
                entry[key] = request[key]
        self.sessions.append(entry)
        return entry

    def _rehomed(self, request: Mapping[str, Any], session: str) -> dict[str, Any]:
        """*request*'s item moved to *session*; the old one is closed (its archive is the
        rehome's own last step)."""
        recorded = self.session_of(str(request["item"]))
        if recorded is None:
            return self._record_session(request, session)
        old = str(recorded["session"])
        if old != session and old not in self.closed:
            self.closed.append(old)
        recorded["session"] = session
        recorded.pop("state", None)
        recorded.pop("needs_action", None)
        return recorded

    def _end(self, entry: dict[str, Any], *, drop_close: bool = True) -> None:
        """*entry*'s session is gone: release its item and never close it again (its
        pending close is dropped too, unless the caller is applying that close)."""
        if entry in self.sessions:
            self.sessions.remove(entry)
        sid = str(entry["session"])
        if sid not in self.closed:
            self.closed.append(sid)
        if drop_close:
            self.requests = [
                r
                for r in self.requests
                if not (r["kind"] == "close" and r["item"] == entry["item"] and r["session"] == sid)
            ]

    def _observe(self, entry: dict[str, Any], state: object, needs: object) -> None:
        if state is not None and str(state) in ENDED_STATES:
            self._end(entry)
            return
        if state is not None:
            entry["state"] = str(state)
        if needs:
            entry["needs_action"] = str(needs)
        else:
            entry.pop("needs_action", None)

    def _lost_result(self, x: Listed) -> dict[str, Any] | None:
        """The pending create request *x* is the lost result of: the one whose request
        tag it carries, else a dispatch for an item with no session whose item tag is
        *x*'s only tag (a session created before request tags)."""
        by_tag = next(
            (r for r in self.requests if r["kind"] in CREATING and r["id"] in x.tags), None
        )
        if by_tag is not None:
            return by_tag
        return next(
            (
                r
                for r in self.requests
                if r["kind"] == "dispatch"
                and set(x.tags) == {r["item"]}
                and self.session_of(str(r["item"])) is None
            ),
            None,
        )

    def _absorb(self, listed: list[Listed]) -> None:
        """What the agent listed. A recorded session (matched by its id, or a session-less
        entry by the item or that id) keeps its state beside it, so a later read without
        statuses still knows it, and an archived one ends (p5-r6). A session no record
        names that is a pending create's lost result is recorded, not created a second
        time; any other is left alone (p5-r1, p5-r2, p5-r5)."""
        for x in listed:
            if x.session is None:
                for entry in list(self.sessions):
                    if {str(entry.get("item")), str(entry.get("session"))} & set(x.tags):
                        self._observe(entry, x.state, x.needs_action)
                continue
            recorded = self._recorded(x.session)
            if recorded is not None:
                self._observe(recorded, x.state, x.needs_action)
                continue
            if x.session in self.closed or x.ended:
                continue
            request = self._lost_result(x)
            if request is None:
                continue
            if request["kind"] == "dispatch":
                entry = self._record_session(request, x.session)
            else:
                entry = self._rehomed(request, x.session)
            self.requests.remove(request)
            self._observe(entry, x.state, x.needs_action)
