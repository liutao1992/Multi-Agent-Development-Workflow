#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SOURCE="$ROOT/skills/multi-agent-development-workflow"
SKILL_DIR="${MADW_SKILL_DIR:-$HOME/.agents/skills/multi-agent-development-workflow}"
BIN_DIR="${MADW_BIN_DIR:-$HOME/.local/bin}"
BACKUP_DIR="${MADW_BACKUP_DIR:-$HOME/.local/share/madw/backups}"

[ -f "$SOURCE/SKILL.md" ] || {
  echo "install: Skill source not found: $SOURCE" >&2
  exit 1
}

backup_existing() {
  local path="$1" label="$2" target
  [ -e "$path" ] || [ -L "$path" ] || return 0
  mkdir -p "$BACKUP_DIR"
  target="$BACKUP_DIR/${label}-$(date +%Y%m%d%H%M%S)-$$"
  mv "$path" "$target"
  echo "Previous install moved to: $target"
}

# ~/.agents/skills is shared by Pi and Codex. With the default install path,
# move old runtime-specific copies out of discovery paths to avoid duplicates.
if [ -z "${MADW_SKILL_DIR:-}" ]; then
  backup_existing "${CODEX_HOME:-$HOME/.codex}/skills/multi-agent-development-workflow" "codex-skill"
  backup_existing "$HOME/.pi/agent/skills/multi-agent-development-workflow" "pi-skill"
fi

backup_existing "$SKILL_DIR" "shared-skill"

mkdir -p "$(dirname "$SKILL_DIR")" "$BIN_DIR"
TMP="${SKILL_DIR}.tmp.$$"
rm -rf "$TMP"
mkdir -p "$TMP"
cp -R "$SOURCE/." "$TMP/"
mv "$TMP" "$SKILL_DIR"

ln -sfn "$SKILL_DIR/scripts/madw" "$BIN_DIR/madw"
ln -sfn "$SKILL_DIR/scripts/agent-team" "$BIN_DIR/agent-team"

echo "Skill installed: $SKILL_DIR"
echo "madw installed:  $BIN_DIR/madw"
echo "agent-team installed: $BIN_DIR/agent-team"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Add $BIN_DIR to PATH." ;;
esac
