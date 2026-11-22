"""Whether an op's `apply` can act at all (gh#1614).

An `apply` that only prints (`echo "docker buildx build --push …"`) exits 0 and
changes nothing, so `fr ops apply` would count the op applied while the real action
never happened. `print_only` is the one predicate `fr plan self-review` (an error) and
`apply_ops` (a manual step, never "applied") both read.

It is a conservative static read of the shell string, never a sandbox, and it errs
toward "acts": a false "acts" leaves the old gap open for one op, a false "only prints"
refuses a real apply. So:

- A quote-aware scan first removes comments, heredoc bodies and every substitution
  (`$(…)`, backticks, `<(…)`, `>(…)`). Anything it cannot balance (an open quote, an
  unclosed heredoc or substitution) is not judged, so it is NOT print-only.
- What is left is print-only when every simple command's first word is a printing
  builtin (`PRINT_ONLY`), after any assignments and shell keywords, and no output
  goes to a file.
- A substitution's body runs, so it is judged too, and more narrowly: every command in
  it must compute a value (`VALUE_ONLY`, `git` only with a read subcommand). An unquoted
  heredoc body expands its substitutions, so they are judged the same way.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable

PRINT_ONLY = frozenset({"echo", "printf", "cat", ":", "true", "false", "printenv", "exit", "set"})
"""First words that write only to stdout/stderr (or nothing) and change no state."""

VALUE_ONLY = PRINT_ONLY | frozenset(
    {"date", "basename", "dirname", "head", "tail", "cut", "tr", "wc", "sort", "uniq",
     "grep", "pwd", "uname", "hostname", "id", "jq", "yq"}
)  # fmt: skip
"""First words a substitution body may use: commands that only compute a value."""

GIT_READ = frozenset({"rev-parse", "describe", "log", "show", "rev-list", "ls-files", "status"})
"""`git` subcommands that only read, allowed inside a substitution."""

_PREFIX = frozenset(
    {"if", "then", "else", "elif", "do", "while", "until", "!", "{", "command", "builtin", "time"}
)
_ALONE = frozenset({"fi", "done", "}"})
_LOOP_HEAD = frozenset({"for", "select"})  # `for x in a b` names words, runs nothing
_PUNCT = frozenset("();<>|&")
_SAFE_FILES = frozenset({"/dev/stdout", "/dev/stderr", "/dev/null"})
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_DELIM = re.compile(r"-?[ \t]*(?:'([^'\n]+)'|\"([^\"\n]+)\"|\\?([A-Za-z_][A-Za-z0-9_]*))")
_SUB = "_"
"""What a removed substitution leaves in the outer text: one inert word."""


class _UnbalancedError(ValueError):
    """The scan could not balance a quote, a substitution or a heredoc."""


def _close_paren(text: str, i: int) -> int:
    """Index just past the `)` matching the `(` before `i`, skipping quoted text."""
    depth = 1
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            j = text.find("'", i + 1)
            if j < 0:
                raise _UnbalancedError
            i = j + 1
            continue
        if c == '"':
            i = _close_quote(text, i + 1)
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise _UnbalancedError


def _close_quote(text: str, i: int) -> int:
    """Index just past the `"` closing a double-quoted string that starts at `i`."""
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
        elif c == '"':
            return i + 1
        elif text.startswith("$(", i):
            i = _close_paren(text, i + 2)
        elif c == "`":
            j = text.find("`", i + 1)
            if j < 0:
                raise _UnbalancedError
            i = j + 1
        else:
            i += 1
    raise _UnbalancedError


def _substitution(text: str, i: int, bodies: list[str]) -> int | None:
    """At `i`, a `$((…))` (skipped), `$(…)` or backtick substitution: collect its body
    and return the index after it; `None` when none starts here."""
    if text.startswith("$((", i):
        end = _close_paren(text, i + 3)  # past the inner `)`; the outer one must follow
        if end >= len(text) or text[end] != ")":
            raise _UnbalancedError
        _bodies_of(text[i + 3 : end - 1], bodies)  # `$(( $(cmd) ))` still runs cmd
        return end + 1
    if text.startswith("$(", i):
        end = _close_paren(text, i + 2)
        bodies.append(text[i + 2 : end - 1])
        return end
    if text[i] == "`":
        j = text.find("`", i + 1)
        if j < 0:
            raise _UnbalancedError
        bodies.append(text[i + 1 : j])
        return j + 1
    return None


def _bodies_of(text: str, bodies: list[str]) -> None:
    """Collect the substitutions in `text` read as one double-quoted string (a heredoc
    body, an arithmetic expression)."""
    i = 0
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        nxt = _substitution(text, i, bodies)
        i = nxt if nxt is not None else i + 1


def _scan(text: str) -> tuple[str, list[str]]:
    """`(outer, bodies)`: `text` with comments, heredoc bodies and substitutions removed
    (each substitution leaves one inert word), and the removed substitution bodies."""
    out: list[str] = []
    bodies: list[str] = []
    heredocs: list[tuple[str, bool, bool]] = []  # (delimiter, quoted, strip tabs)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            out.append(text[i : i + 2])
            i += 2
        elif c == "'":
            j = text.find("'", i + 1)
            if j < 0:
                raise _UnbalancedError
            out.append(text[i : j + 1])
            i = j + 1
        elif c == '"':
            j = _close_quote(text, i + 1)
            _bodies_of(text[i + 1 : j - 1], bodies)
            out.append(text[i:j])
            i = j
        elif c == "#" and (i == 0 or text[i - 1] in " \t\n;&|()"):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif c in "<>" and text.startswith("(", i + 1):
            end = _close_paren(text, i + 2)
            bodies.append(text[i + 2 : end - 1])
            out.append(_SUB)
            i = end
        elif text.startswith("<<<", i):
            out.append(" <<< ")
            i += 3
        elif text.startswith("<<", i):
            m = _DELIM.match(text, i + 2)
            if m is None:
                raise _UnbalancedError
            delim = m.group(1) or m.group(2) or m.group(3)
            quoted = m.group(3) is None or text[m.start(3) - 1] == "\\"
            heredocs.append((delim, quoted, text[i + 2] == "-"))
            out.append(" ")
            i = m.end()
        elif c == "\n" and heredocs:
            out.append("\n")
            i += 1
            for delim, quoted, dash in heredocs:
                start = i
                while True:
                    if i >= n:
                        raise _UnbalancedError  # a heredoc that never closes
                    j = text.find("\n", i)
                    line = text[i : n if j < 0 else j]
                    i = n if j < 0 else j + 1
                    if (line.lstrip("\t") if dash else line) == delim:
                        break
                if not quoted:
                    _bodies_of(text[start:i], bodies)
            heredocs = []
        else:
            nxt = _substitution(text, i, bodies)
            if nxt is not None:
                out.append(_SUB)
                i = nxt
            else:
                out.append(c)
                i += 1
    if heredocs:
        raise _UnbalancedError
    return "".join(out), bodies


def _word(token: str) -> str:
    """A command word, with a `/bin/` or `/usr/bin/` path dropped."""
    for prefix in ("/usr/bin/", "/bin/"):
        if token.startswith(prefix):
            return token[len(prefix) :]
    return token


def _acts(text: str, allowed: Callable[[str, str | None], bool]) -> bool:
    """Whether `text` may change state: a command `allowed` refuses, an output redirect
    to a file, or a substitution whose own body may. Unparseable text acts."""
    try:
        outer, bodies = _scan(text)
        lexer = shlex.shlex(outer.replace("\n", " ; "), posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = ""  # `_scan` already removed the comments
        tokens = list(lexer)
    except ValueError:  # `_UnbalancedError`, or shlex's "No closing quotation"
        return True
    if any(_acts(body, _value_only) for body in bodies):
        return True
    expect_word, in_loop_head, i = True, False, 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if set(tok) <= _PUNCT:
            if ">" in tok:
                target_ok = nxt.isdigit() or nxt == "-" if tok.endswith("&") else nxt in _SAFE_FILES
                if not target_ok:
                    return True  # writes (or opens for writing) a file
                i += 1
            elif "<" in tok:
                i += 1  # the operand: a file read, or a here-string
            else:
                expect_word, in_loop_head = True, False
        elif in_loop_head or not expect_word:
            pass
        elif tok in _LOOP_HEAD:
            in_loop_head = True
        elif tok in _PREFIX or _ASSIGNMENT.match(tok):
            pass
        elif tok in _ALONE:
            expect_word = False
        elif allowed(_word(tok), nxt):
            expect_word = False
        else:
            return True
        i += 1
    return False


def _value_only(word: str, nxt: str | None) -> bool:
    return word in VALUE_ONLY or (word == "git" and nxt in GIT_READ)


def _printing(word: str, nxt: str | None) -> bool:
    return word in PRINT_ONLY


def print_only(command: str) -> bool:
    """Whether `command` (an op's `apply`) only prints, so running it changes nothing."""
    if not command.strip() or _acts(command, _printing):
        return False
    try:
        outer, _ = _scan(command)
    except ValueError:
        return False
    # Something must be there: a printing command, or at least an assignment.
    words = outer.replace(";", " ").split()
    return any(w in PRINT_ONLY or _ASSIGNMENT.match(w) for w in map(_word, words))
