#!/usr/bin/env bash
# Expose the host's Claude config (bind-mounted read-only under /opt) to Claude Code in the container.
# Run by postStartCommand on every container start.
set -u

SKILLS_SRC="${SKILLS_SRC:-/opt/claude-skills}"    # host Claude-skills repo
HOST_CLAUDE="${HOST_CLAUDE:-/opt/host-claude}"    # selected files from host ~/.claude
GUARD="${GUARD:-/opt/claude-skills/devcontainer/guard-destructive.py}"  # read-only mount: Claude cannot alter it
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

mkdir -p "$DEST/skills"

# Skills: one symlink per folder containing a SKILL.md
for d in "$SKILLS_SRC"/*/; do
  [ -f "$d/SKILL.md" ] || continue
  name=$(basename "$d")
  target="$DEST/skills/$name"
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "[link-host-claude] skip skill '$name': a local copy already exists in $target" >&2
    continue
  fi
  ln -sfn "${d%/}" "$target"
done

# Drop links to skills removed from the repo
for l in "$DEST"/skills/*; do
  [ -L "$l" ] && [ ! -e "$l" ] && rm -f "$l"
done

# Global instructions and other read-only items, if mounted
for item in CLAUDE.md agents commands; do
  src="$HOST_CLAUDE/$item"
  [ -e "$src" ] || continue
  if [ -e "$DEST/$item" ] && [ ! -L "$DEST/$item" ]; then
    echo "[link-host-claude] skip '$item': a local one already exists in $DEST" >&2
    continue
  fi
  ln -sfn "$src" "$DEST/$item"
done

# Guard hook for destructive commands: register it in the container's user settings (idempotent)
if [ -f "$GUARD" ]; then
  python3 - "$DEST/settings.json" "$GUARD" <<'PY'
import json, os, sys
path, guard = sys.argv[1], sys.argv[2]
cmd = f"python3 {guard}"
settings = json.load(open(path)) if os.path.exists(path) else {}
pre = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
if not any(h.get("command") == cmd for entry in pre for h in entry.get("hooks", [])):
    pre.append({"matcher": "Bash", "hooks": [{"type": "command", "command": cmd, "timeout": 10}]})
    with open(path, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"[link-host-claude] guard hook registered in {path}", file=sys.stderr)
PY
fi
exit 0
