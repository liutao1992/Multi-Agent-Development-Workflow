#!/usr/bin/env bash
set -euo pipefail

MADW="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)/scripts/madw"
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

start_for "$REPO_A"
SESSION_A="$(session_for "$REPO_A")"
[ "$(tmux list-panes -t "$SESSION_A:team" -F '#{pane_id}' | wc -l | tr -d ' ')" = "3" ]

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

REVIEW_PANE="$(tmux show-options -v -t "$SESSION_A" @madw_pane_review)"
OLD_PID="$(tmux display-message -p -t "$REVIEW_PANE" '#{pane_pid}')"
(cd "$REPO_A" && "$MADW" restart review)
NEW_REVIEW_PANE="$(tmux show-options -v -t "$SESSION_A" @madw_pane_review)"
NEW_PID="$(tmux display-message -p -t "$NEW_REVIEW_PANE" '#{pane_pid}')"
[ "$REVIEW_PANE" = "$NEW_REVIEW_PANE" ]
[ "$OLD_PID" != "$NEW_PID" ]

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
