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
CWD="$(/bin/pwd -P)" || exit 17
printf 'CWD_OK:%s\n' "$(basename "$CWD")"
printf 'MADW_CLI_OK:%s\n' "$MADW_CLI"
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
start_with_layout_for() { local dir="$1"; shift; (cd "$dir" && MADW_AGENT_CMD="$FAKE" MADW_NO_ATTACH=1 "$MADW" start "$@"); }
stop_for() { local dir="$1"; (cd "$dir" && "$MADW" stop); }

deny_agent_process_probes() {
  kill() {
    if [ "${1:-}" = "-0" ]; then
      case " $MADW_TEST_DENIED_PIDS " in
        *" ${2:-} "*) return 1 ;;
      esac
    fi
    builtin kill "$@"
  }
  export -f kill
}

assert_fake_agent() {
  local pane="$1" output attempt
  for attempt in $(seq 1 50); do
    output="$(tmux capture-pane -p -t "$pane" -S -100)"
    if printf '%s\n' "$output" | grep -Fq 'CWD_OK:codex-project' &&
       printf '%s\n' "$output" | grep -Fq 'MADW_CLI_OK:'; then
      return 0
    fi
    sleep 0.1
  done
  echo "pane $pane did not run the fake Codex executable:" >&2
  printf '%s\n' "$output" >&2
  return 1
}

REPO_A="$TMP/project"
REPO_B="$TMP/other/project"
REPO_C="$TMP/layout-precedence"
REPO_D="$TMP/layout-invalid"
init_repo "$REPO_A"
init_repo "$REPO_B"
init_repo "$REPO_C"
init_repo "$REPO_D"

EMPTY_REPO="$TMP/empty-project"
mkdir -p "$EMPTY_REPO"
git -C "$EMPTY_REPO" init -q
if (cd "$EMPTY_REPO" && MADW_AGENT_CMD="$FAKE" MADW_NO_ATTACH=1 "$MADW" start) >"$TMP/empty-start.log" 2>&1; then
  echo "start accepted a Git repository without a baseline commit" >&2
  exit 1
fi
grep -Fq "no commit yet" "$TMP/empty-start.log"
EMPTY_SESSION="$(cd "$EMPTY_REPO" && "$MADW" id)"
if tmux list-sessions -F '#S' 2>/dev/null | grep -Fqx "$EMPTY_SESSION"; then
  echo "start created tmux panes before checking the Git baseline" >&2
  exit 1
fi
[ ! -e "$EMPTY_REPO/.agent-team" ]

# MADW's Codex command enables network access for tmux socket transport by
# default, while an explicit zero forces the restrictive policy.
mkdir -p "$TMP/bin"
printf '#!/bin/sh\nexit 0\n' > "$TMP/bin/codex"
chmod +x "$TMP/bin/codex"
DOCTOR_OUTPUT="$(cd "$REPO_A" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD= "$MADW" doctor codex)"
printf '%s\n' "$DOCTOR_OUTPUT" | grep -Fq "codex -s workspace-write -c 'sandbox_workspace_write.network_access=true'"
RESTRICTED_DOCTOR="$(cd "$REPO_A" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD= MADW_CODEX_NETWORK_ACCESS=0 "$MADW" doctor codex)"
printf '%s\n' "$RESTRICTED_DOCTOR" | grep -Fq "codex -s workspace-write -c 'sandbox_workspace_write.network_access=false'"
if (cd "$REPO_A" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD= MADW_CODEX_NETWORK_ACCESS=invalid "$MADW" doctor codex) >"$TMP/invalid-codex-policy.log" 2>&1; then
  echo "doctor accepted an unsupported Codex network policy" >&2
  exit 1
fi
grep -Fq 'MADW_CODEX_NETWORK_ACCESS must be 0 or 1' "$TMP/invalid-codex-policy.log"
if (cd "$REPO_A" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD= MADW_CODEX_NETWORK_ACCESS= "$MADW" doctor codex) >"$TMP/empty-codex-policy.log" 2>&1; then
  echo "doctor accepted an empty Codex network policy" >&2
  exit 1
fi
grep -Fq 'MADW_CODEX_NETWORK_ACCESS must be 0 or 1' "$TMP/empty-codex-policy.log"
CUSTOM_DOCTOR="$(cd "$REPO_A" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD="$FAKE" MADW_CODEX_NETWORK_ACCESS=0 "$MADW" doctor codex)"
printf '%s\n' "$CUSTOM_DOCTOR" | grep -Fq "Agent Command:$FAKE"
printf '#!/bin/sh\nexit 0\n' > "$TMP/bin/pi"
chmod +x "$TMP/bin/pi"
PI_DOCTOR="$(cd "$REPO_A" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD= MADW_CODEX_NETWORK_ACCESS=0 "$MADW" doctor pi)"
printf '%s\n' "$PI_DOCTOR" | grep -Fq 'Agent Command:pi'

# A denied socket must not be reported as a missing team.
cat > "$TMP/bin/tmux" <<'EOF'
#!/bin/sh
echo 'error connecting to /private/tmp/tmux-501/default (Operation not permitted)' >&2
exit 1
EOF
chmod +x "$TMP/bin/tmux"
if (cd "$REPO_A" && PATH="$TMP/bin:$PATH" "$MADW" status) >"$TMP/denied-socket.log" 2>&1; then
  echo "status accepted a denied tmux socket" >&2
  exit 1
fi
grep -Fq 'tmux socket access denied by this sandbox' "$TMP/denied-socket.log"

# An unexpected failure after preflight must fail closed. Treating it as "no
# sessions" can make a running Leader create or repair a team and discard its
# current pane context.
export FAKE_TMUX_STATE="$TMP/fake-tmux-state"
export FAKE_TMUX_NEW_SESSION="$TMP/fake-tmux-new-session"
cat > "$TMP/bin/tmux" <<'EOF'
#!/bin/sh
if [ "$1" = "list-sessions" ]; then
  if [ ! -e "$FAKE_TMUX_STATE" ]; then
    : > "$FAKE_TMUX_STATE"
    exit 0
  fi
  echo 'failed to connect to tmux server' >&2
  exit 1
fi
if [ "$1" = "new-session" ]; then
  : > "$FAKE_TMUX_NEW_SESSION"
fi
exit 99
EOF
chmod +x "$TMP/bin/tmux"
if (cd "$REPO_A" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD="$FAKE" MADW_NO_ATTACH=1 "$MADW" start) >"$TMP/unknown-tmux-error.log" 2>&1; then
  echo "start treated an unexpected tmux error as no running team" >&2
  exit 1
fi
grep -Fq 'cannot inspect tmux sessions: failed to connect to tmux server' "$TMP/unknown-tmux-error.log"
[ ! -e "$FAKE_TMUX_NEW_SESSION" ]
rm "$TMP/bin/tmux"

# Exercise the actual Codex command path with a fake interactive executable.
# Reproduce a tmux server started before the caller added Codex to PATH. Its
# panes must use the caller's PATH rather than accidentally run a host Codex.
tmux new-session -d -s madw-path-server 'sleep 120'
tmux set-environment -g PATH /usr/bin:/bin
tmux set-option -g default-shell /bin/bash
cp "$FAKE" "$TMP/bin/codex"
CODEX_REPO="$TMP/codex-project"
init_repo "$CODEX_REPO"
(cd "$CODEX_REPO" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD= MADW_NO_ATTACH=1 "$MADW" start codex) >/dev/null
CODEX_SESSION="$(cd "$CODEX_REPO" && "$MADW" id)"
[ "$(tmux show-options -v -t "$CODEX_SESSION" @madw_agent_cmd)" = "codex -s workspace-write -c 'sandbox_workspace_write.network_access=true'" ]
[ "$(tmux show-options -v -t "$CODEX_SESSION" @madw_agent_path)" = "$TMP/bin:$PATH" ]
[ "$(tmux list-panes -t "$CODEX_SESSION:team" -F '#{pane_id}' | wc -l | tr -d ' ')" = "3" ]
for role in leader impl review; do
  assert_fake_agent "$(tmux show-options -v -t "$CODEX_SESSION" "@madw_pane_$role")"
done
(cd "$CODEX_REPO" && "$MADW" stop) >/dev/null

# An existing team changes its stored policy only on explicit request, and
# running panes adopt it only when restarted.
(cd "$CODEX_REPO" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD= MADW_CODEX_NETWORK_ACCESS=0 MADW_NO_ATTACH=1 "$MADW" start codex) >/dev/null
[ "$(tmux show-options -v -t "$CODEX_SESSION" @madw_agent_cmd)" = "codex -s workspace-write -c 'sandbox_workspace_write.network_access=false'" ]
CODEX_LEAD="$(tmux show-options -v -t "$CODEX_SESSION" @madw_pane_leader)"
OLD_CODEX_PID="$(tmux display-message -p -t "$CODEX_LEAD" '#{pane_pid}')"
(cd "$CODEX_REPO" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD= MADW_NO_ATTACH=1 "$MADW" start codex) >/dev/null
[ "$(tmux show-options -v -t "$CODEX_SESSION" @madw_agent_cmd)" = "codex -s workspace-write -c 'sandbox_workspace_write.network_access=false'" ]
mkdir -p "$CODEX_REPO/.agent-team/tasks/TASK-TEST-TRANSPORT"
printf 'durable evidence\n' > "$CODEX_REPO/.agent-team/tasks/TASK-TEST-TRANSPORT/evidence.txt"
(cd "$CODEX_REPO" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD= MADW_CODEX_NETWORK_ACCESS=1 MADW_NO_ATTACH=1 "$MADW" start codex) >/dev/null
[ "$(tmux show-options -v -t "$CODEX_SESSION" @madw_agent_cmd)" = "codex -s workspace-write -c 'sandbox_workspace_write.network_access=true'" ]
[ "$(tmux display-message -p -t "$CODEX_LEAD" '#{pane_pid}')" = "$OLD_CODEX_PID" ]
[ "$(cat "$CODEX_REPO/.agent-team/tasks/TASK-TEST-TRANSPORT/evidence.txt")" = "durable evidence" ]
CODEX_REVIEW="$(tmux show-options -v -t "$CODEX_SESSION" @madw_pane_review)"
OLD_CODEX_REVIEW_PID="$(tmux display-message -p -t "$CODEX_REVIEW" '#{pane_pid}')"
(cd "$CODEX_REPO" && "$MADW" restart review) >/dev/null
[ "$(tmux display-message -p -t "$CODEX_REVIEW" '#{pane_pid}')" != "$OLD_CODEX_REVIEW_PID" ]
tmux display-message -p -t "$CODEX_REVIEW" '#{pane_start_command}' | grep -Fq 'sandbox_workspace_write.network_access=true'
assert_fake_agent "$CODEX_REVIEW"
(cd "$CODEX_REPO" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD= MADW_CODEX_NETWORK_ACCESS=0 MADW_NO_ATTACH=1 "$MADW" start codex) >/dev/null
[ "$(tmux show-options -v -t "$CODEX_SESSION" @madw_agent_cmd)" = "codex -s workspace-write -c 'sandbox_workspace_write.network_access=false'" ]
# Legacy teams adopt the restart caller's PATH once and reuse it afterwards.
tmux set-option -u -t "$CODEX_SESSION" @madw_agent_path
(cd "$CODEX_REPO" && PATH="$TMP/bin:$PATH" "$MADW" restart review) >/dev/null
assert_fake_agent "$CODEX_REVIEW"
[ "$(tmux show-options -v -t "$CODEX_SESSION" @madw_agent_path)" = "$TMP/bin:$PATH" ]
(cd "$CODEX_REPO" && "$MADW" restart review) >/dev/null
assert_fake_agent "$CODEX_REVIEW"
tmux set-option -t "$CODEX_SESSION" @madw_agent_cmd 'codex --custom-policy'
if (cd "$CODEX_REPO" && PATH="$TMP/bin:$PATH" MADW_AGENT_CMD= MADW_CODEX_NETWORK_ACCESS=1 MADW_NO_ATTACH=1 "$MADW" start codex) >"$TMP/custom-codex-policy.log" 2>&1; then
  echo "start replaced a custom stored Codex command" >&2
  exit 1
fi
grep -Fq 'stored Codex Agent command is custom' "$TMP/custom-codex-policy.log"
[ "$(tmux show-options -v -t "$CODEX_SESSION" @madw_agent_cmd)" = 'codex --custom-policy' ]
(cd "$CODEX_REPO" && "$MADW" stop) >/dev/null

# Default install goes to the shared Agent Skills directory and removes an old
# Codex-specific copy from the discovery path.
INSTALL_HOME="$TMP/install-home"
INSTALL_BIN="$TMP/install-bin"
mkdir -p "$INSTALL_HOME/.codex/skills/multi-agent-development-workflow"
printf 'legacy\n' > "$INSTALL_HOME/.codex/skills/multi-agent-development-workflow/SKILL.md"
HOME="$INSTALL_HOME" MADW_BIN_DIR="$INSTALL_BIN" "$INSTALL" >/dev/null
[ -f "$INSTALL_HOME/.agents/skills/multi-agent-development-workflow/SKILL.md" ]
[ ! -e "$INSTALL_HOME/.codex/skills/multi-agent-development-workflow" ]
[ ! -e "$INSTALL_HOME/.local/share/madw/backups" ]
[ -L "$INSTALL_BIN/madw" ]
[ -L "$INSTALL_BIN/agent-team" ]
(cd "$REPO_A" && MADW_AGENT_CMD="$FAKE" "$INSTALL_BIN/madw" id) >/dev/null
(cd "$REPO_A" && "$INSTALL_BIN/agent-team" --help) >/dev/null

# Exercise a tmux server whose original working directory has been removed.
STALE_CWD="$TMP/stale-server-cwd"
mkdir -p "$STALE_CWD"
(cd "$STALE_CWD" && tmux new-session -d -s madw-stale-server 'sleep 60')
rm -rf "$STALE_CWD"

start_for "$REPO_A"
SESSION_A="$(session_for "$REPO_A")"
[ -d "$REPO_A/.agent-team/tasks" ]
[ -L "$REPO_A/.agent-team/madw" ]
(cd "$REPO_A" && ./.agent-team/madw id) | grep -Fqx "$SESSION_A"
(cd "$REPO_A" && git check-ignore -q .agent-team/)
[ -z "$(git -C "$REPO_A" status --porcelain)" ]
[ "$(tmux list-panes -t "$SESSION_A:team" -F '#{pane_id}' | wc -l | tr -d ' ')" = "3" ]
[ "$(tmux show-options -v -t "$SESSION_A" @madw_runtime)" = "custom" ]
[ "$(tmux show-options -v -t "$SESSION_A" mouse)" = "on" ]
[ "$(tmux show-options -v -t "$SESSION_A" status)" = "5" ]
[ "$(tmux show-options -v -t "$SESSION_A" status-interval)" = "5" ]
tmux show-options -v -t "$SESSION_A" 'status-format[1]' | grep -Fq 'statusline context'
tmux show-options -v -t "$SESSION_A" 'status-format[2]' | grep -Fq 'statusline progress'
tmux show-options -v -t "$SESSION_A" 'status-format[4]' | grep -Fq 'statusline communication'
[ "$(tmux show-options -v -t "$SESSION_A" 'status-format[3]')" = '#[bg=colour235,fill=colour235] ' ]
[ "$(tmux show-options -v -t "$SESSION_A" @madw_task_display)" = "尚未记录当前任务" ]
[ "$(tmux show-options -v -t "$SESSION_A" key-table)" != "root" ]
TEAM_TABLE="$(tmux show-options -v -t "$SESSION_A" key-table)"
tmux list-keys -a | grep -E -- "-T $TEAM_TABLE[[:space:]]+C-c[[:space:]]+kill-session -t $SESSION_A$" >/dev/null
tmux list-keys -a | grep -E -- "-T $TEAM_TABLE[[:space:]]+MouseDown1Pane[[:space:]]+select-pane -t =" >/dev/null
[ "$(tmux show-window-options -v -t "$SESSION_A:team" pane-border-status)" = "bottom" ]
tmux show-window-options -v -t "$SESSION_A:team" pane-border-format | grep -Fq '#[fg=colour51,bold]'
tmux show-window-options -v -t "$SESSION_A:team" pane-border-format | grep -Fq '#[fg=colour82,bold]'
tmux show-window-options -v -t "$SESSION_A:team" pane-border-format | grep -Fq '#[fg=colour213,bold]'

# Reusing an older team repairs its session-local mouse setting.
tmux set-option -t "$SESSION_A" mouse off
start_for "$REPO_A" >/dev/null
[ "$(tmux show-options -v -t "$SESSION_A" mouse)" = "on" ]
[ "$(tmux show-options -v -g mouse)" = "off" ]

LEAD_PANE="$(tmux show-options -v -t "$SESSION_A" @madw_pane_leader)"
IMPL_PANE="$(tmux show-options -v -t "$SESSION_A" @madw_pane_impl)"
REVIEW_PANE="$(tmux show-options -v -t "$SESSION_A" @madw_pane_review)"
[ "$(tmux show-options -p -v -t "$LEAD_PANE" @madw_label)" = "Leader" ]
[ "$(tmux show-options -p -v -t "$IMPL_PANE" @madw_label)" = "Impl" ]
[ "$(tmux show-options -p -v -t "$REVIEW_PANE" @madw_label)" = "Review" ]
LEAD_LEFT="$(tmux display-message -p -t "$LEAD_PANE" '#{pane_left}')"
LEAD_HEIGHT="$(tmux display-message -p -t "$LEAD_PANE" '#{pane_height}')"
IMPL_LEFT="$(tmux display-message -p -t "$IMPL_PANE" '#{pane_left}')"
IMPL_TOP="$(tmux display-message -p -t "$IMPL_PANE" '#{pane_top}')"
IMPL_HEIGHT="$(tmux display-message -p -t "$IMPL_PANE" '#{pane_height}')"
REVIEW_LEFT="$(tmux display-message -p -t "$REVIEW_PANE" '#{pane_left}')"
REVIEW_TOP="$(tmux display-message -p -t "$REVIEW_PANE" '#{pane_top}')"
[ "$LEAD_LEFT" -lt "$IMPL_LEFT" ]
[ "$IMPL_LEFT" -eq "$REVIEW_LEFT" ]
[ "$IMPL_TOP" -lt "$REVIEW_TOP" ]
[ "$LEAD_HEIGHT" -gt "$IMPL_HEIGHT" ]

# A new team can use the explicit three-column layout. Pane positions are
# compared relationally so this remains independent of terminal dimensions.
start_with_layout_for "$REPO_B" --layout columns >/dev/null
SESSION_B="$(session_for "$REPO_B")"
LEAD_B="$(tmux show-options -v -t "$SESSION_B" @madw_pane_leader)"
IMPL_B="$(tmux show-options -v -t "$SESSION_B" @madw_pane_impl)"
REVIEW_B="$(tmux show-options -v -t "$SESSION_B" @madw_pane_review)"
LEAD_B_LEFT="$(tmux display-message -p -t "$LEAD_B" '#{pane_left}')"
IMPL_B_LEFT="$(tmux display-message -p -t "$IMPL_B" '#{pane_left}')"
REVIEW_B_LEFT="$(tmux display-message -p -t "$REVIEW_B" '#{pane_left}')"
[ "$LEAD_B_LEFT" -lt "$IMPL_B_LEFT" ]
[ "$IMPL_B_LEFT" -lt "$REVIEW_B_LEFT" ]
[ "$(tmux show-options -v -t "$SESSION_B" @madw_layout)" = "columns" ]

# A valid CLI choice overrides MADW_LAYOUT. The existing team keeps its
# columns when a later start requests balanced.
(cd "$REPO_C" && MADW_AGENT_CMD="$FAKE" MADW_NO_ATTACH=1 MADW_LAYOUT=columns "$MADW" start --layout balanced) >/dev/null
SESSION_C="$(session_for "$REPO_C")"
LEAD_C="$(tmux show-options -v -t "$SESSION_C" @madw_pane_leader)"
IMPL_C="$(tmux show-options -v -t "$SESSION_C" @madw_pane_impl)"
REVIEW_C="$(tmux show-options -v -t "$SESSION_C" @madw_pane_review)"
LEAD_C_LEFT="$(tmux display-message -p -t "$LEAD_C" '#{pane_left}')"
IMPL_C_LEFT="$(tmux display-message -p -t "$IMPL_C" '#{pane_left}')"
IMPL_C_TOP="$(tmux display-message -p -t "$IMPL_C" '#{pane_top}')"
REVIEW_C_LEFT="$(tmux display-message -p -t "$REVIEW_C" '#{pane_left}')"
REVIEW_C_TOP="$(tmux display-message -p -t "$REVIEW_C" '#{pane_top}')"
[ "$LEAD_C_LEFT" -lt "$IMPL_C_LEFT" ]
[ "$IMPL_C_LEFT" -eq "$REVIEW_C_LEFT" ]
[ "$IMPL_C_TOP" -lt "$REVIEW_C_TOP" ]
[ "$(tmux show-options -v -t "$SESSION_C" @madw_layout)" = "balanced" ]

(cd "$REPO_B" && MADW_AGENT_CMD="$FAKE" MADW_NO_ATTACH=1 "$MADW" start --layout balanced) >/dev/null
[ "$(tmux display-message -p -t "$LEAD_B" '#{pane_left}')" = "$LEAD_B_LEFT" ]
[ "$(tmux display-message -p -t "$IMPL_B" '#{pane_left}')" = "$IMPL_B_LEFT" ]
[ "$(tmux display-message -p -t "$REVIEW_B" '#{pane_left}')" = "$REVIEW_B_LEFT" ]
[ "$(tmux show-options -v -t "$SESSION_B" @madw_layout)" = "columns" ]

# Environment selection applies when no CLI option is present.
ENV_REPO="$TMP/layout-environment"
init_repo "$ENV_REPO"
(cd "$ENV_REPO" && MADW_AGENT_CMD="$FAKE" MADW_NO_ATTACH=1 MADW_LAYOUT=columns "$MADW" start) >/dev/null
ENV_SESSION="$(session_for "$ENV_REPO")"
ENV_LEAD="$(tmux show-options -v -t "$ENV_SESSION" @madw_pane_leader)"
ENV_IMPL="$(tmux show-options -v -t "$ENV_SESSION" @madw_pane_impl)"
ENV_REVIEW="$(tmux show-options -v -t "$ENV_SESSION" @madw_pane_review)"
[ "$(tmux display-message -p -t "$ENV_LEAD" '#{pane_left}')" -lt "$(tmux display-message -p -t "$ENV_IMPL" '#{pane_left}')" ]
[ "$(tmux display-message -p -t "$ENV_IMPL" '#{pane_left}')" -lt "$(tmux display-message -p -t "$ENV_REVIEW" '#{pane_left}')" ]

# Unsupported environment and CLI values fail with a useful error before
# creating a team.
if (cd "$REPO_D" && MADW_AGENT_CMD="$FAKE" MADW_NO_ATTACH=1 MADW_LAYOUT=invalid "$MADW" start) >"$TMP/invalid-env-layout.log" 2>&1; then
  echo "start accepted an unsupported MADW_LAYOUT value" >&2
  exit 1
fi
grep -Fq "unknown layout 'invalid' (choose balanced or columns)" "$TMP/invalid-env-layout.log"
if (cd "$REPO_D" && MADW_AGENT_CMD="$FAKE" MADW_NO_ATTACH=1 "$MADW" start --layout invalid) >"$TMP/invalid-cli-layout.log" 2>&1; then
  echo "start accepted an unsupported --layout value" >&2
  exit 1
fi
grep -Fq "unknown layout 'invalid' (choose balanced or columns)" "$TMP/invalid-cli-layout.log"
[ ! -e "$REPO_D/.agent-team" ]

for _ in 1 2 3 4 5 6 7 8 9 10; do
  if tmux capture-pane -p -t "$LEAD_PANE" -S -100 | grep -Fq '队长，团队已就绪。'; then break; fi
  sleep 0.1
done
tmux capture-pane -p -t "$LEAD_PANE" -S -100 | grep -Fq '队长，团队已就绪。'
tmux capture-pane -p -t "$LEAD_PANE" -S -100 | grep -Fq '【收到开发需求后】'
tmux capture-pane -p -t "$LEAD_PANE" -S -100 | grep -Fq '绝不能解释为“没有团队”'
[ "$(tmux display-message -p -t "$LEAD_PANE" '#{pane_current_path}')" = "$(cd "$REPO_A" && pwd -P)" ]
if tmux capture-pane -p -t "$IMPL_PANE" -S -100 | grep -Fq 'Impl 角色'; then
  echo "Impl received a task before Lead dispatched one" >&2
  exit 1
fi
if tmux capture-pane -p -t "$REVIEW_PANE" -S -100 | grep -Fq 'Review 角色'; then
  echo "Review received a task before Lead dispatched one" >&2
  exit 1
fi
(cd "$REPO_A" && "$MADW" send impl 'TASK-TEST-001: plan the change') >/dev/null
[ "$(tmux show-options -v -t "$SESSION_A" @madw_flow_task)" = 'TASK-TEST-001' ]
tmux show-options -v -t "$SESSION_A" @madw_flow_display | grep -Fq 'Leader → Impl'
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if tmux capture-pane -p -t "$IMPL_PANE" -S -100 | grep -Fq 'TASK-TEST-001: plan the change'; then break; fi
  sleep 0.1
done
tmux capture-pane -p -t "$IMPL_PANE" -S -100 | grep -Fq 'Impl 角色'
tmux capture-pane -p -t "$IMPL_PANE" -S -100 | grep -Fq '【Lead 交接任务】'
tmux capture-pane -p -t "$IMPL_PANE" -S -100 | grep -Fq 'TASK-TEST-001: plan the change'

# A sandbox-denied process probe must not mark live Agents dead or restart
# them. Preserve every PID and the Leader's conversation when reusing a team.
LIVE_LEAD_PID="$(tmux display-message -p -t "$LEAD_PANE" '#{pane_pid}')"
LIVE_IMPL_PID="$(tmux display-message -p -t "$IMPL_PANE" '#{pane_pid}')"
LIVE_REVIEW_PID="$(tmux display-message -p -t "$REVIEW_PANE" '#{pane_pid}')"
export MADW_TEST_DENIED_PIDS="$LIVE_LEAD_PID $LIVE_IMPL_PID $LIVE_REVIEW_PID"
SANDBOX_STATUS="$(
  deny_agent_process_probes
  cd "$REPO_A"
  "$MADW" status
)"
printf '%s\n' "$SANDBOX_STATUS" | grep -E '^leader[[:space:]].*alive' >/dev/null
printf '%s\n' "$SANDBOX_STATUS" | grep -E '^impl[[:space:]].*alive' >/dev/null
printf '%s\n' "$SANDBOX_STATUS" | grep -E '^review[[:space:]].*alive' >/dev/null
(deny_agent_process_probes; start_for "$REPO_A") >/dev/null
[ "$(tmux display-message -p -t "$LEAD_PANE" '#{pane_pid}')" = "$LIVE_LEAD_PID" ]
[ "$(tmux display-message -p -t "$IMPL_PANE" '#{pane_pid}')" = "$LIVE_IMPL_PID" ]
[ "$(tmux display-message -p -t "$REVIEW_PANE" '#{pane_pid}')" = "$LIVE_REVIEW_PID" ]
tmux capture-pane -p -t "$LEAD_PANE" -S -100 | grep -Fq '【收到开发需求后】'

# Re-entering a team repairs a Lead pane that exited without ending the team.
OLD_LEAD_PID="$(tmux display-message -p -t "$LEAD_PANE" '#{pane_pid}')"
tmux respawn-pane -k -t "$LEAD_PANE" 'exit 0'
for _ in 1 2 3 4 5 6 7 8 9 10; do
  [ "$(tmux display-message -p -t "$LEAD_PANE" '#{pane_dead}')" = "1" ] && break
  sleep 0.1
done
start_for "$REPO_A" >/dev/null
[ "$(tmux display-message -p -t "$LEAD_PANE" '#{pane_dead}')" = "0" ]
[ "$(tmux display-message -p -t "$LEAD_PANE" '#{pane_pid}')" != "$OLD_LEAD_PID" ]

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
if tmux capture-pane -p -t "$NEW_REVIEW_PANE" -S -100 | grep -Fq 'Review 角色'; then
  echo "Review received a task immediately after a fresh restart" >&2
  exit 1
fi
(cd "$REPO_A" && "$MADW" send review 'TASK-TEST-001: verify the frozen code') >/dev/null
for _ in $(seq 1 50); do
  if tmux capture-pane -p -t "$NEW_REVIEW_PANE" -S -100 | grep -Fq 'TASK-TEST-001: verify the frozen code'; then break; fi
  sleep 0.1
done
REVIEW_CAPTURE="$(tmux capture-pane -p -t "$NEW_REVIEW_PANE" -S -100)"
if ! printf '%s\n' "$REVIEW_CAPTURE" | grep -Fq 'Review 角色' \
  || ! printf '%s\n' "$REVIEW_CAPTURE" | grep -Fq '【Lead 交接任务】' \
  || ! printf '%s\n' "$REVIEW_CAPTURE" | grep -Fq 'TASK-TEST-001: verify the frozen code'; then
  echo "Review did not display the dispatched task after restart; pane output:" >&2
  printf '%s\n' "$REVIEW_CAPTURE" >&2
  exit 1
fi

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
(deny_agent_process_probes; cd "$REPO_A" && "$MADW" wait impl TASK-TEST-001 001 5) | grep -Fq "PLAN-v001.md"
tmux show-options -v -t "$SESSION_A" @madw_task_display | grep -Fq '【规划中】 TASK-TEST-001'
tmux show-options -v -t "$SESSION_A" @madw_flow_display | grep -Fq 'Impl → Leader'

# A late signal for an older task must not replace the current task's banner.
(cd "$REPO_A" && "$MADW" send impl 'TASK-TEST-002: next task') >/dev/null
(cd "$REPO_A" && "$MADW" signal impl TASK-TEST-001 001) >/dev/null
[ "$(tmux show-options -v -t "$SESSION_A" @madw_flow_task)" = 'TASK-TEST-002' ]

# Completion survives an interrupted/repeated wait and an early signal.
(cd "$REPO_A" && "$MADW" wait impl TASK-TEST-001 001 1) | grep -Fq "PLAN-v001.md"
printf 'early evidence\n' > "$TASK_ROOT/plans/PLAN-v004.md"
(cd "$REPO_A" && "$MADW" signal impl TASK-TEST-001 004) >/dev/null
(cd "$REPO_A" && "$MADW" wait impl TASK-TEST-001 004 1) | grep -Fq "PLAN-v004.md"
printf 'changed evidence\n' > "$TASK_ROOT/plans/PLAN-v004.md"
if (cd "$REPO_A" && "$MADW" wait impl TASK-TEST-001 004 1) >/dev/null 2>&1; then
  echo "wait accepted an artifact changed after completion" >&2
  exit 1
fi
if (cd "$REPO_A" && "$MADW" signal impl TASK-TEST-001 004) >/dev/null 2>&1; then
  echo "signal replaced a previously completed artifact" >&2
  exit 1
fi

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
