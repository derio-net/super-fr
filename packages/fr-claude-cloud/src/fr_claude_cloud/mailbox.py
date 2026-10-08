"""The claude-cloud mailbox: pending session requests and recorded sessions, as plain
data over the scope's state directory (cloud-triage R14, R15, §F).

Pure apart from the two files it is handed the directory of, `requests.yaml` and
`sessions.yaml`; both travel in the scope's state ref (`fr.triage.state_ref.REF_FILES`),
so a driver restored on a fresh workspace still holds them. Without a directory (a
runner built by `from_env` and never opened) everything stays in memory.

- A request has a stable id, `<item id>:<kind>:<n>`; *n* counts that item's requests of
  that kind, kept in `requests.yaml`'s `issued`, so a retried request is a new id and a
  re-emitted one the same id.
- A request is pending until a result names it. The agent executes the outbox with its
  session tools (`REQUEST_TABLE`) and records each result with `fr triage drive record`.
- `status` requests are never stored: every pass asks one per recorded session, id
  `<item id>:status:1`, and recording one updates that session's state.
"""

from __future__ import annotations

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

CLOSE_OUTCOMES = frozenset({"closed", "busy", "absent"})
MESSAGE_OUTCOMES = frozenset({"sent", "refused"})


@dataclass(frozen=True)
class Row:
    """One request kind: what the agent executes, and the result it records."""

    execute: str
    record: str


REQUEST_TABLE: Mapping[str, Row] = {
    "dispatch": Row(
        execute="list_sessions and look for one tagged `tag`; when one exists, create "
        "nothing and record its id; otherwise create_session(repo, branch, model, tag, "
        "prompt)",
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
        execute="send_message(session, push and stop); at its next idle, "
        "create_session(repo, branch, model, tag, prompt = the resume brief); then "
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
    """A session the agent listed or read (`--statuses`): its id, tag and state."""

    session: str
    tag: str | None
    state: str | None
    needs_action: str | None


def parse_statuses(raw: Any) -> list[Listed]:
    """The agent's statuses file, in any of its three shapes: `{"sessions": [...]}`, a
    bare list of `{id|session, tag, state, needs_action}`, or a mapping keyed by item id
    (or session id) whose value is a state or such an object."""
    if raw is None:
        return []
    entries: list[tuple[str | None, Any]] = []
    if isinstance(raw, Mapping) and "sessions" in raw:
        raw = raw["sessions"]
    if isinstance(raw, list):
        entries = [(None, e) for e in raw]
    elif isinstance(raw, Mapping):
        entries = list(raw.items())
    else:
        raise ValueError("statuses: a list of sessions or a mapping of item id to state")
    out: list[Listed] = []
    for key, value in entries:
        body: Mapping[str, Any] = value if isinstance(value, Mapping) else {"state": value}
        session = body.get("id") or body.get("session") or key
        if not session:
            raise ValueError(f"statuses: an entry names no session: {value!r}")
        tag = body.get("tag") or key
        needs = body.get("needs_action")
        state = body.get("state")
        out.append(
            Listed(
                session=str(session),
                tag=str(tag) if tag else None,
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
    """The requests and sessions of one scope, loaded from (and saved to) *state_dir*."""

    def __init__(self, state_dir: Path | None = None, statuses: Any = None) -> None:
        self.state_dir = state_dir
        requests = _read(state_dir / REQUESTS_FILE) if state_dir else {}
        sessions = _read(state_dir / SESSIONS_FILE) if state_dir else {}
        self.requests: list[dict[str, Any]] = [dict(r) for r in requests.get("requests") or []]
        self.issued: dict[str, int] = {
            str(k): int(v) for k, v in (requests.get("issued") or {}).items()
        }
        self.sessions: list[dict[str, Any]] = [dict(s) for s in sessions.get("sessions") or []]
        self.listed = parse_statuses(statuses)
        self._absorb(self.listed)
        self.save()

    # ------------------------------------------------------------------ storage

    def save(self) -> None:
        if self.state_dir is None:
            return
        if self.requests or self.issued or (self.state_dir / REQUESTS_FILE).is_file():
            _write(
                self.state_dir / REQUESTS_FILE,
                _dump({"requests": self.requests, "issued": self.issued}),
            )
        if self.sessions or (self.state_dir / SESSIONS_FILE).is_file():
            _write(self.state_dir / SESSIONS_FILE, _dump({"sessions": self.sessions}))

    # ------------------------------------------------------------------ lookups

    def pending(self, item: str, kind: str) -> dict[str, Any] | None:
        return next((r for r in self.requests if r["item"] == item and r["kind"] == kind), None)

    def session_of(self, item: str) -> dict[str, Any] | None:
        return next((s for s in self.sessions if s.get("item") == item), None)

    def listed_for(self, item: str) -> Listed | None:
        """The session the agent listed under *item*'s tag (or as its recorded session)."""
        recorded = self.session_of(item)
        sid = recorded.get("session") if recorded else None
        return next((x for x in self.listed if x.tag == item or (sid and x.session == sid)), None)

    def session_id(self, item: str) -> str | None:
        recorded = self.session_of(item)
        if recorded is not None:
            return str(recorded["session"])
        listed = self.listed_for(item)
        return listed.session if listed else None

    def held(self, items: Iterable[str]) -> set[str]:
        """Items with a pending dispatch, a recorded session, or a listed tagged one."""
        tags = {x.tag for x in self.listed if x.tag}
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
        request = {"id": request_id(item, kind, n), "kind": kind, "item": item, **fields}
        self.requests.append(request)
        self.save()
        return request

    def outbox(self) -> list[dict[str, Any]]:
        out = [self._annotated(r) for r in self.requests]
        for s in self.sessions:
            item = str(s["item"])
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

    def record(self, results: list[dict[str, Any]]) -> list[str]:
        if not isinstance(results, list) or not all(isinstance(r, Mapping) for r in results):
            raise ValueError("results: a list of objects, one per request, each with its id")
        applied: list[str] = []
        for result in results:
            rid = result.get("id")
            if not isinstance(rid, str):
                continue
            if self._apply(rid, result):
                applied.append(rid)
        self.save()
        return applied

    def _apply(self, rid: str, result: Mapping[str, Any]) -> bool:
        parts = split_id(rid)
        if parts is not None and parts[1] == "status":
            recorded = self.session_of(parts[0])
            if recorded is None:
                return False
            self._set_state(recorded, result.get("state"), result.get("needs_action"))
            return True
        request = next((r for r in self.requests if r["id"] == rid), None)
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
                self.sessions = [s for s in self.sessions if s.get("item") != item]
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
            recorded = self.session_of(item)
            if recorded is not None:
                recorded["session"] = str(session)
                recorded.pop("state", None)
                recorded.pop("needs_action", None)
            else:
                self._record_session(request, str(session))
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

    def _record_session(self, request: Mapping[str, Any], session: str) -> None:
        item = str(request["item"])
        self.sessions = [s for s in self.sessions if s.get("item") != item]
        entry: dict[str, Any] = {"item": item, "session": session}
        for key in ("repo", "branch"):
            if request.get(key):
                entry[key] = request[key]
        self.sessions.append(entry)

    @staticmethod
    def _set_state(entry: dict[str, Any], state: object, needs: object) -> None:
        if state is not None:
            entry["state"] = str(state)
        if needs:
            entry["needs_action"] = str(needs)
        else:
            entry.pop("needs_action", None)

    def _absorb(self, listed: list[Listed]) -> None:
        """What the agent listed: a pending dispatch whose tagged session exists is
        recorded, not created a second time (its result was lost); a recorded session's
        state is kept beside it, so a later read without statuses still knows it."""
        for x in listed:
            if x.tag:
                pending = self.pending(x.tag, "dispatch")
                if pending is not None and self.session_of(x.tag) is None:
                    self._record_session(pending, x.session)
                    self.requests.remove(pending)
            for entry in self.sessions:
                if entry.get("session") == x.session or (x.tag and entry.get("item") == x.tag):
                    if x.state is not None:
                        self._set_state(entry, x.state, x.needs_action)
