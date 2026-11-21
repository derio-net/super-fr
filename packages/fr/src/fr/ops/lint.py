"""Whether an op's `apply` can act at all (gh#1614).

An `apply` that only prints (`echo "docker buildx build --push …"`) exits 0 and
changes nothing, so `fr ops apply` would count the op applied while the real action
never happened. `print_only` is the one predicate `fr plan self-review` (an error) and
`apply_ops` (a manual step, never "applied") both read.

It is a conservative static read of the shell string, never a sandbox. A command is
print-only when every simple command in it is a printing builtin (`PRINT_ONLY`), a
bare assignment, or a shell keyword, and no output is redirected to a file. Heredoc
bodies, comments and the inside of a command substitution (`TAG="$(git rev-parse
HEAD)"`, a value computed for the print) are not commands of their own. Anything it
cannot parse, or any other first word (a script, `docker`, `bash`), is NOT print-only:
a false "acts" costs nothing, a false "only prints" refuses a real apply.
"""

from __future__ import annotations

import re
import shlex

PRINT_ONLY = frozenset({"echo", "printf", "cat", ":", "true", "false", "printenv", "exit", "set"})
"""First words that write only to stdout/stderr (or nothing) and change no state."""

_KEYWORD_PREFIX = frozenset({"if", "then", "else", "elif", "do", "while", "until", "!", "{"})
_KEYWORD_ALONE = frozenset({"fi", "done", "}", "esac"})
_SEPARATORS = frozenset({";", ";;", "&", "&&", "|", "||", "|&", "(", ")"})
_OUT_REDIRECTS = frozenset({">", ">>", ">|", "&>", "&>>", ">&"})
_HARMLESS_TARGETS = frozenset({"/dev/stdout", "/dev/stderr", "/dev/null", "1", "2", "-"})
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_HEREDOC = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")


def _without_heredoc_bodies(command: str) -> str:
    """The command with every heredoc body removed; the `<<` line stays."""
    out: list[str] = []
    pending: list[tuple[str, bool]] = []  # (delimiter, strip leading tabs)
    for line in command.splitlines():
        if pending:
            delim, dash = pending[0]
            if (line.lstrip("\t") if dash else line) == delim:
                pending.pop(0)
            continue
        out.append(line)
        pending.extend((m.group(3), bool(m.group(1))) for m in _HEREDOC.finditer(line))
    return "\n".join(out)


def _tokens(command: str) -> list[str] | None:
    # The `;` goes AFTER the newline: a comment runs to the newline, so a separator
    # before it would be swallowed and the next line read as the comment line's args.
    text = _without_heredoc_bodies(command).replace("\\\n", " ").replace("\n", "\n ; ")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def print_only(command: str) -> bool:
    """Whether `command` (an op's `apply`) only prints, so running it changes nothing."""
    tokens = _tokens(command)
    if not tokens:
        return False
    saw_command = False
    expect_word = True  # at the start of a simple command
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "(" and i > 0 and (tokens[i - 1].endswith("$") or tokens[i - 1] in "<>"):
            depth, i = 1, i + 1  # a command or process substitution: a value, not a command
            while i < len(tokens) and depth:
                depth += {"(": 1, ")": -1}.get(tokens[i], 0)
                i += 1
            continue
        if tok in _SEPARATORS:
            expect_word = True
        elif tok in _OUT_REDIRECTS:
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            if target not in _HARMLESS_TARGETS:
                return False  # writes a file
            i += 1
        elif tok in ("<", "<<", "<<-", "<<<"):
            i += 1  # its operand (a file read, a heredoc delimiter, a string)
        elif expect_word:
            if tok in _KEYWORD_PREFIX or _ASSIGNMENT.match(tok):
                pass
            elif tok in _KEYWORD_ALONE:
                expect_word = False
            elif tok in PRINT_ONLY:
                saw_command, expect_word = True, False
            else:
                return False
        i += 1
    return saw_command or any(_ASSIGNMENT.match(t) for t in tokens)
