#!/usr/bin/env bash
set -euo pipefail

TEST_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SKILL_ROOT="$(CDPATH= cd -- "$TEST_DIR/.." && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SKILL_ROOT/../.." && pwd)"
MADW="$SKILL_ROOT/scripts/madw"
INSTALL="$REPO_ROOT/install.sh"

TMP="$(mktemp -d)"
export TMUX_TMPDIR="$TMP/tmux"
mkdir -p "$TMUX_TMPDIR"

cleanup() {
  tmux kill-server >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

FAKE="$TMP/fake-agent.sh"
cat >"$FAKE" <<'EOF'
#!/usr/bin/env bash
trap 'exit 0' TERM INT
while IFS= read -r line; do
  printf 'FAKE:%s\n' "$line"
done
EOF
chmod +x "$FAKE"

init_repo() {
  local dir="$1"
  mkdir -p "$dir"
  git -C "$dir" init -q
  git -C "$dir" config user.email test@example.com
  git -C "$dir" config user.name Test
  printf 'base\n' > "$dir/README.md"
  git -C "$dir" add README.md
  git -C "$dir" commit -qm init
}

session_for() { local dir="$1"; (cd "$dir" && MADW_AGENT_CMD="$FAKE" "$MADW" id); }
start_for() { local dir="$1"; (cd "$dir" && MADW_AGENT_CMD="$FAKE" MADW_NO_ATTACH=1 "$MADW" start); }
stop_for() { local dir="$1"; (cd "$dir" && "$MADW" stop); }

REPO_A="$TMP/project"
REPO_B="$TMP/other/project"
init_repo "$REPO_A"
init_repo "$REPO_B"

# Default install goes to the shared Agent Skills directory and migrates an old
# Codex-specific copy out of the discovery path.
INSTALL_HOME="$TMP/install-home"
INSTALL_BIN="$TMP/install-bin"
mkdir -p "$INSTALL_HOME/.codex/skills/multi-agent-development-workflow"
printf 'legacy\n' > "$INSTALL_HOME/.codex/skills/multi-agent-development-workflow/SKILL.md"
HOME="$INSTALL_HOME" MADW_BIN_DIR="$INSTALL_BIN" "$INSTALL" >/dev/null
[ -f "$INSTALL_HOME/.agents/skills/multi-agent-development-workflow/SKILL.md" ]
[ ! -e "$INSTALL_HOME/.codex/skills/multi-agent-development-workflow" ]
find "$INSTALL_HOME/.local/share/madw/backups" -maxdepth 1 -type d -name 'codex-skill-*' | grep -q .
[ -L "$INSTALL_BIN/madw" ]
(cd "$REPO_A" && MADW_AGENT_CMD="$FAKE" "$INSTALL_BIN/madw" id) >/dev/null

start_for "$REPO_A"
SESSION_A="$(session_for "$REPO_A")"
[ "$(tmux list-panes -t "$SESSION_A:team" -F '#{pane_id}' | wc -l | tr -d ' ')" = "3" ]
[ "$(tmux show-options -v -t "$SESSION_A" @madw_runtime)" = "custom" ]

LEAD_PANE="$(tmux show-options -v -t "$SESSION_A" @madw_pane_leader)"
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if tmux capture-pane -p -t "$LEAD_PANE" -S -100 | grep -q 'Role: Lead'; then break; fi
  sleep 0.1
done
tmux capture-pane -p -t "$LEAD_PANE" -S -100 | grep -q 'Role: Lead'

start_for "$REPO_B"
SESSION_B="$(session_for "$REPO_B")"
[ "$SESSION_A" != "$SESSION_B" ]
tmux list-sessions -F '#S' | grep -Fqx "$SESSION_A"
tmux list-sessions -F '#S' | grep -Fqx "$SESSION_B"

# Per-role runtime overrides are rejected; team metadata must stay coherent.
if (cd "$REPO_A" && "$MADW" restart review codex) >/dev/null 2>&1; then
  echo "restart unexpectedly accepted a per-role runtime override" >&2
  exit 1
fi
[ "$(tmux show-options -v -t "$SESSION_A" @madw_runtime)" = "custom" ]

REVIEW_PANE="$(tmux show-options -v -t "$SESSION_A" @madw_pane_review)"
OLD_PID="$(tmux display-message -p -t "$REVIEW_PANE" '#{pane_pid}')"
(cd "$REPO_A" && "$MADW" restart review)
NEW_REVIEW_PANE="$(tmux show-options -v -t "$SESSION_A" @madw_pane_review)"
NEW_PID="$(tmux display-message -p -t "$NEW_REVIEW_PANE" '#{pane_pid}')"
[ "$REVIEW_PANE" = "$NEW_REVIEW_PANE" ]
[ "$OLD_PID" != "$NEW_PID" ]
[ "$(tmux show-options -v -t "$SESSION_A" @madw_runtime)" = "custom" ]

TASK_ROOT="$REPO_A/.agent-team/tasks/TASK-TEST-001"
mkdir -p "$TASK_ROOT/plans"
cat >"$TASK_ROOT/STATUS.md" <<'EOF'
# Task Status

## Current State

PLANNING

## Current Implementation

Artifact: N/A
Code Head SHA: N/A

## Current Review

Artifact: N/A
EOF

# Successful wait/signal and artifact validation.
(
  sleep 0.3
  printf 'plan evidence\n' > "$TASK_ROOT/plans/PLAN-v001.md"
  cd "$REPO_A"
  "$MADW" signal impl TASK-TEST-001 001 >/dev/null
) &
(cd "$REPO_A" && "$MADW" wait impl TASK-TEST-001 001 5) | grep -Fq "PLAN-v001.md"

# Timeout must fail closed instead of blocking forever.
set +e
TIMEOUT_OUTPUT="$(cd "$REPO_A" && "$MADW" wait impl TASK-TEST-001 002 1 2>&1)"
TIMEOUT_RC=$?
set -e
[ "$TIMEOUT_RC" -eq 124 ]
printf '%s\n' "$TIMEOUT_OUTPUT" | grep -Fq "timeout waiting"

# Dead pane/Agent must be detected while waiting.
IMPL_PANE="$(tmux show-options -v -t "$SESSION_A" @madw_pane_impl)"
tmux respawn-pane -k -t "$IMPL_PANE" "exit 7"
for _ in 1 2 3 4 5 6 7 8 9 10; do
  [ "$(tmux display-message -p -t "$IMPL_PANE" '#{pane_dead}')" = "1" ] && break
  sleep 0.1
done
set +e
DEAD_OUTPUT="$(cd "$REPO_A" && "$MADW" wait impl TASK-TEST-001 003 5 2>&1)"
DEAD_RC=$?
set -e
[ "$DEAD_RC" -eq 2 ]
printf '%s\n' "$DEAD_OUTPUT" | grep -Fq "Agent exited"
(cd "$REPO_A" && "$MADW" restart impl) >/dev/null

STATUS_OUTPUT="$(cd "$REPO_A" && "$MADW" status)"
printf '%s\n' "$STATUS_OUTPUT" | grep -Fq "Team:    $SESSION_A"
printf '%s\n' "$STATUS_OUTPUT" | grep -Fq "leader"
printf '%s\n' "$STATUS_OUTPUT" | grep -Fq "impl"
printf '%s\n' "$STATUS_OUTPUT" | grep -Fq "review"

stop_for "$REPO_A"
if tmux list-sessions -F '#S' 2>/dev/null | grep -Fqx "$SESSION_A"; then
  echo "project A session survived stop" >&2
  exit 1
fi
tmux list-sessions -F '#S' | grep -Fqx "$SESSION_B"

if (cd "$REPO_A" && MADW_AGENT_CMD= MADW_NO_ATTACH=1 "$MADW" start unsupported-runtime) >/dev/null 2>&1; then
  echo "unsupported runtime unexpectedly succeeded" >&2
  exit 1
fi

stop_for "$REPO_B"
echo "tmux integration: PASS"
