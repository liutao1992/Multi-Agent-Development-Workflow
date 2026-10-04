#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SOURCE="$ROOT/skills/multi-agent-development-workflow"
SKILL_DIR="${MADW_SKILL_DIR:-${CODEX_HOME:-$HOME/.codex}/skills/multi-agent-development-workflow}"
BIN_DIR="${MADW_BIN_DIR:-$HOME/.local/bin}"

[ -f "$SOURCE/SKILL.md" ] || {
  echo "install: Skill source not found: $SOURCE" >&2
  exit 1
}

mkdir -p "$(dirname "$SKILL_DIR")" "$BIN_DIR"
TMP="${SKILL_DIR}.tmp.$$"
rm -rf "$TMP"
mkdir -p "$TMP"
cp -R "$SOURCE/." "$TMP/"

if [ -e "$SKILL_DIR" ]; then
  BACKUP="${SKILL_DIR}.backup.$(date +%Y%m%d%H%M%S)"
  mv "$SKILL_DIR" "$BACKUP"
  echo "Previous Skill moved to: $BACKUP"
fi
mv "$TMP" "$SKILL_DIR"
ln -sfn "$SKILL_DIR/scripts/madw" "$BIN_DIR/madw"

echo "Skill installed: $SKILL_DIR"
echo "madw installed:  $BIN_DIR/madw"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "Add $BIN_DIR to PATH." ;; esac
