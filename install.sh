#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SOURCE="$ROOT/skills/multi-agent-development-workflow"
SKILL_DIR="${MADW_SKILL_DIR:-$HOME/.agents/skills/multi-agent-development-workflow}"
BIN_DIR="${MADW_BIN_DIR:-$HOME/.local/bin}"

[ -f "$SOURCE/SKILL.md" ] || {
  echo "install: Skill source not found: $SOURCE" >&2
  exit 1
}

remove_existing() {
  local path="$1"
  case "$path" in
    */multi-agent-development-workflow) ;;
    *) echo "install: refusing to remove unexpected Skill path: $path" >&2; exit 1 ;;
  esac
  [ -e "$path" ] || [ -L "$path" ] || return 0
  rm -rf -- "$path"
  echo "Previous install removed: $path"
}

mkdir -p "$(dirname "$SKILL_DIR")" "$BIN_DIR"
TMP="${SKILL_DIR}.tmp.$$"
rm -rf "$TMP"
mkdir -p "$TMP"
cp -R "$SOURCE/." "$TMP/"

# ~/.agents/skills is shared by Pi and Codex. With the default install path,
# remove old runtime-specific copies to avoid duplicates.
if [ -z "${MADW_SKILL_DIR:-}" ]; then
  remove_existing "${CODEX_HOME:-$HOME/.codex}/skills/multi-agent-development-workflow"
  remove_existing "$HOME/.pi/agent/skills/multi-agent-development-workflow"
fi

remove_existing "$SKILL_DIR"
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
