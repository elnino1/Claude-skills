#!/usr/bin/env python3
"""Claude Code PreToolUse hook (matcher: Bash) guarding destructive file and git commands.

Decisions:
  deny -> the command can never run (rm on /, ~, $HOME, the project root...)
  ask  -> Claude Code asks the user before running it
  (no output) -> normal permission flow

Input (stdin): {"tool_name": "Bash", "tool_input": {"command": "..."}, "cwd": "...", ...}
The project root is $CLAUDE_PROJECT_DIR (set by Claude Code), else the "cwd" field.
"""

import json
import os
import re
import shlex
import sys

FILE_CMDS = {"rm", "rmdir", "unlink", "shred", "mv", "truncate"}
WRAPPERS = {"sudo", "command", "nice", "nohup", "time", "env", "doas"}
SHELLS = {"bash", "sh", "zsh", "dash"}
OPERATORS = {";", "&&", "||", "|", "&", "(", ")", "\n", "|&"}
GLOB = re.compile(r"[*?\[]")


def decide(decision: str, reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": f"[guard-destructive] {reason}",
        }
    }))
    sys.exit(0)


def split_commands(command: str):
    """Yield the token list of each simple command (split on ; && || | & and newlines)."""
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    current = []
    for tok in lexer:
        if tok in OPERATORS or set(tok) <= set(";&|()"):
            if current:
                yield current
            current = []
        else:
            current.append(tok)
    if current:
        yield current


def strip_prefix(tokens):
    """Drop VAR=value assignments and wrappers like sudo/env/nice."""
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t):
            i += 1
        elif os.path.basename(t) in WRAPPERS:
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):  # wrapper options (sudo -u is rare, ignore its value)
                i += 1
        else:
            break
    return tokens[i:]


def norm(path: str, cwd: str) -> str:
    return os.path.normpath(os.path.join(cwd, os.path.expanduser(path)))


def check_paths(cmd: str, args, project: str, cwd: str, issues: list) -> None:
    paths = [a for a in args if not a.startswith("-") or a == "-"]
    flags = [a for a in args if a.startswith("-") and a != "-"]
    home = os.path.expanduser("~")
    protected = {"/", home, project, os.path.dirname(project)}

    if cmd in {"rm", "rmdir", "shred", "unlink"} and not paths:
        return
    for p in paths:
        if "$" in p or "`" in p:
            issues.append(("ask", f"`{cmd}` on a path built from a variable/substitution: {p}"))
            continue
        if GLOB.search(p):
            issues.append(("ask", f"`{cmd}` with a wildcard: {p}"))
        if not (p.startswith("/") or p.startswith("~")):
            issues.append(("ask", f"`{cmd}` with a relative path (use an absolute path): {p}"))
        target = norm(p, cwd)
        if cmd != "mv" and target in protected:
            issues.append(("deny", f"`{cmd}` on a protected directory: {target}"))
        elif not (target == project or target.startswith(project + os.sep)):
            issues.append(("ask", f"`{cmd}` outside the project ({project}): {target}"))
    if cmd == "rm" and any(re.match(r"^-[a-zA-Z]*[rR]", f) or f == "--recursive" for f in flags):
        issues.append(("ask", f"recursive `rm`: {' '.join([cmd] + args)}"))


def check_git(args, issues: list) -> None:
    # skip global options like -C dir, -c k=v
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in {"-C", "-c"} else 1
    if i >= len(args):
        return
    sub, rest = args[i], args[i + 1:]
    line = "git " + " ".join(args)
    if sub == "clean" and not any(f in rest for f in ("-n", "--dry-run")):
        issues.append(("ask", f"`git clean` deletes untracked files: {line}"))
    elif sub == "reset" and "--hard" in rest:
        issues.append(("ask", f"`git reset --hard` discards local changes: {line}"))
    elif sub == "checkout" and ("--" in rest or "." in rest or "-f" in rest or "--force" in rest):
        issues.append(("ask", f"`git checkout` may discard local changes: {line}"))
    elif sub == "restore" and not ("--staged" in rest and "--worktree" not in rest):
        issues.append(("ask", f"`git restore` discards local changes: {line}"))
    elif sub == "push" and any(f in rest for f in ("-f", "--force", "--force-with-lease", "--mirror", "--delete", "-d")):
        issues.append(("ask", f"destructive `git push`: {line}"))
    elif sub == "push" and any(r.startswith("+") or r.startswith(":") for r in rest if not r.startswith("-")):
        issues.append(("ask", f"destructive `git push` refspec: {line}"))
    elif sub == "branch" and any(f in rest for f in ("-D", "-d", "--delete")):
        issues.append(("ask", f"branch deletion: {line}"))
    elif sub == "stash" and rest[:1] and rest[0] in {"drop", "clear"}:
        issues.append(("ask", f"`git stash {rest[0]}` deletes stashed work: {line}"))


def analyse(command: str, project: str, cwd: str, issues: list, depth: int = 0) -> None:
    try:
        commands = list(split_commands(command))
    except ValueError:
        if re.search(r"\b(rm|mv|shred|git\s+(clean|reset))\b", command):
            issues.append(("ask", "could not parse the command and it contains rm/mv/git destructive words"))
        return
    for tokens in commands:
        tokens = strip_prefix(tokens)
        if not tokens:
            continue
        cmd, args = os.path.basename(tokens[0]), tokens[1:]
        if cmd in SHELLS and "-c" in args and depth < 3:
            idx = args.index("-c")
            if idx + 1 < len(args):
                analyse(args[idx + 1], project, cwd, issues, depth + 1)
        elif cmd == "xargs" and any(os.path.basename(a) in FILE_CMDS for a in args):
            issues.append(("ask", f"`xargs` feeding a delete/move command: {' '.join(tokens)}"))
        elif cmd == "find" and ("-delete" in args or any(a in FILE_CMDS for a in args)):
            issues.append(("ask", f"`find` that deletes/moves files: {' '.join(tokens)}"))
        elif cmd == "rsync" and any(a.startswith("--delete") or a == "--remove-source-files" for a in args):
            issues.append(("ask", f"`rsync` that deletes files: {' '.join(tokens)}"))
        elif cmd in FILE_CMDS:
            check_paths(cmd, args, project, cwd, issues)
        elif cmd == "git":
            check_git(args, issues)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    if data.get("tool_name") != "Bash":
        return
    command = (data.get("tool_input") or {}).get("command") or ""
    cwd = data.get("cwd") or os.getcwd()
    project = os.path.normpath(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)

    issues: list = []
    analyse(command, project, cwd, issues)
    if not issues:
        return
    denies = [r for d, r in issues if d == "deny"]
    if denies:
        decide("deny", "; ".join(dict.fromkeys(denies)))
    decide("ask", "; ".join(dict.fromkeys(r for _, r in issues)))


if __name__ == "__main__":
    main()
