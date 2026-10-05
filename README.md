# Multi-Agent Development Workflow

使用三个长期角色形成一个可观察的开发闭环：

```text
用户
 ↓
Lead
 ├─ tmux → Impl   → Plan / Code / Tests / IMPL
 └─ tmux → Review → PASS / FAIL
                   │
             FAIL ─┘→ Lead → Impl → fresh Review
 ↓
ACCEPTED
```

当前设计只保留四个核心概念：

```text
Skill       → 定义协议
tmux        → 运行 + 通信 + 同步 + 观察
.agent-team → 状态 + 证据
Git         → 代码快照身份
```

交互式 Agent 之间不再使用项目自定义 Queue / mailbox / heartbeat / lease。

## 快速开始

安装后，在目标 Git 项目中：

```bash
cd my-project
madw start
```

项目须先有至少一个提交，Lead 才能记录 Task Baseline SHA。仅执行
`git init` 的空仓库会在创建面板前得到明确错误；先提交项目初始文件，再运行
`madw start`。启动器会创建项目内的 `.agent-team/tasks/`，并将
`.agent-team/` 加入当前仓库的 Git 本地排除规则，使控制面不进入代码提交。
Agent 在项目内通过 `./.agent-team/madw` 调用 CLI，无需依赖终端环境变量。

`madw start` 默认创建一个 tmux session，并将其分成 Lead、Impl、Review
三个并排的 pane。进入各 pane 后运行 `madw launch pi` 或
`madw launch codex`，可以混用。
`launch` 会自动给 Lead 发送角色说明，并记住每个角色选择的 Agent，供 Review
刷新或意外退出后恢复。然后在 Lead 中输入开发需求。`madw send` 会等待目标 Agent 的全屏
界面就绪；尚未启动 Agent 时会报错，不会把任务粘贴进 shell。

```bash
madw attach impl       # 聚焦 Impl pane，在里面启动 Agent
madw attach review     # 聚焦 Review pane，在里面启动 Agent
madw attach leader     # 聚焦 Lead pane，在里面启动 Agent
```

也可以显式使用 `madw start pi` 或 `madw start codex`，沿用自动启动的三 pane
模式。设置 `MADW_RUNTIME` 或 `MADW_AGENT_CMD` 也会选择自动启动模式。
直接在对应 pane 输入 `pi` 或 `codex` 也可用；此时需从另一终端运行
`madw bootstrap leader`，且 Review 重置后需手动重启 Agent。

下面的沙箱设置只适用于 MADW 启动的 Codex 团队。

MADW 启动的 Codex 团队默认使用 `workspace-write` 沙箱并启用网络访问，
使 `madw send`、`wait` 和 `signal` 可连接 macOS 上的 tmux socket。
这也允许该团队 Agent 执行的命令访问外部网络；不会修改全局 Codex 配置。
如果希望保持网络限制，可在创建团队时显式选择：

```bash
MADW_CODEX_NETWORK_ACCESS=0 madw start codex
```

升级已有 Codex 团队时，代码通过评审后，先在项目仓库运行 `./install.sh`
更新已安装的 Skill，然后在普通终端执行：

```bash
MADW_CODEX_NETWORK_ACCESS=1 MADW_NO_ATTACH=1 madw start codex
```

这只更新团队保存的启动命令；运行中的 Agent 不会被打断，任务证据和面板排列
也会保留。待各角色完成当前交接后，分别运行 `madw restart review`、
`madw restart impl`，再从安全的外部终端重启 `leader`。重启后的角色才会使用
新策略。若选用了限制模式或其他策略仍阻止连接，只对失败的 `madw` 命令申请
提升权限并重试；socket 拒绝不表示团队已退出。若需自定义 Codex 启动命令，
可设置 `MADW_AGENT_CMD`。

## 一个 tmux session，三个角色 pane

默认拓扑按项目 Git 根目录命名：

```text
madw-<repo>-<path-hash>          Lead | Impl | Review
```

`madw start` 创建三个并排的角色 shell pane，不替你选择 Agent。
`madw attach <role>` 聚焦对应 pane；`madw watch` 聚焦 Lead。
在 tmux 内可用鼠标或 `Ctrl+b` 加方向键切换 pane。边框显示角色名，状态栏提示
`madw launch pi|codex` 命令。
`madw status` 查看三位角色当前运行的命令。每个 pane 只放一个角色，
派单和完成信号仍使用 `madw send`、`wait`、`signal`。

默认布局为三列；`--layout balanced` 可改为 Lead 在左、Impl/Review 在右上下排列。
如需旧的三个独立 session，可运行 `madw start --sessions`。
自动启动模式仍支持 `madw start pi|codex`。
手动模式中，若 Review 使用 `madw launch` 选过 Agent，
`madw restart review` 会以同一种 Agent 刷新上下文；直接输入 `pi` 或
`codex` 的 Review session 会重置为 shell，需手动重新启动。
`madw stop` 结束整个团队。

如果旧 session 报 `getcwd` 错误，请从能正常进入项目目录的终端运行
`cd <项目目录> && madw stop && madw start`。新版启动器会在每个角色 shell
启动前显式进入项目目录，避免复用 tmux server 已失效的工作目录。

每个角色的终端输出会追加保存到
`.agent-team/runtime/logs/<role>.log`。排查 Agent 异常时运行
`madw logs review 200` 查看 Review 最近 200 行；省略行数时默认显示 120 行。
当前团队默认开启 Debug 日志；之后可用 `madw debug off` 停止记录，
需要时运行 `madw debug on` 继续追加。日志保存在本机 Control Plane，
不会进入 Git 代码快照。

## 常用命令

```bash
madw start [pi|codex]
madw launch pi|codex
madw bootstrap leader
madw status
madw watch
madw attach leader
madw attach impl
madw attach review
madw restart review
madw logs review 200
madw debug off
madw stop
madw doctor
madw id
```

Lead 可使用：

```bash
madw send impl "<handoff>"
madw wait impl TASK-... 001

madw restart review
madw send review "<handoff>"
madw wait review TASK-... 001
```

Worker 在工件写完后使用 `madw signal ...`。等待封装增加 timeout、Agent
死亡检测、失败输出抓取和预期工件检查。完成记录保存在 tmux session 内，并
绑定工件内容哈希；Lead 中断后再次执行同一条 `madw wait` 可以核对已完成
的交接，工件被修改则会报错。

## 启动与派单安全

`madw start` 在创建 session 前检查 Git 基线、Skill 和 tmux。手动模式
不要求预先安装 Pi 或 Codex；三个 shell pane 都从当前项目目录启动。
自动模式还检查所选 Agent 命令。`madw send` 和 `madw bootstrap leader`
等待目标进入全屏 UI，最多等待 `MADW_TUI_TIMEOUT` 秒（默认 10 秒）；
超时会失败且不派单。

## Review 独立性

每轮正式评审需要新上下文。手动模式中通过 `madw launch` 启动的 Review
会按该角色记录的运行时自动刷新；直接启动的 Review 则会重置为 shell，
需要用户重新启动。自动三 pane 模式按团队运行时刷新 Review。

## 状态与证据

tmux 只负责传输和观察。生命周期仍在：

```text
<project-root>/.agent-team/tasks/<TASK-ID>/
├── TASK.md
├── STATUS.md
├── plans/
├── implementations/
├── reviews/
└── ACCEPTANCE.md
```

原有的正确性规则继续保留：Lead-only lifecycle、Task Contract
Revision/Hash、Plan Gate、稳定 clean Code Head、独立 Review、返工 RW、PASS
才能验收，以及最终 HEAD 再校验。

**验证边界：**tmux 模式的 `madw wait` 只核对完成信号、工件是否存在及其
内容哈希，并检查 worker 进程是否存活。Plan 审批、角色写入边界、Git HEAD
与 Review/Acceptance 证据的语义校验仍由 Lead 按 Skill 执行；tmux 不会
自动运行 Python 编排器的逐步校验。需要机器强制执行这些检查时，使用下述
Process 模式。同一工作树同一时间只能有一个可修改代码的任务；并行任务
请使用不同的 Git worktree。tmux 团队目前不与 Process 模式共用自动锁，
因此不要在同一工作树同时运行 `madw` 团队任务和 `agent-team run/start`。

代码身份闭环：

```text
Implementation Head
=
Review Declared Head
=
Review Observed Head
=
STATUS Code Head
=
Accepted Head
```

## Process fallback

CI/无人值守场景仍可使用：

```bash
agent-team --runtime codex --transport process run <TASK-ID>
agent-team --runtime pi --transport process run <TASK-ID>
```

它不是交互式 tmux 团队的通信层。旧 filesystem Queue transport 和
`agent-team worker Impl/Review` 已移除。

安装脚本会同时把 `madw` 和 `agent-team` 链接到 `~/.local/bin`。如果该目录
不在 `PATH`，可以直接运行安装目录中的脚本，或在**要执行 Process 命令的
终端**设置：

```bash
export AGENT_TEAM="$HOME/.agents/skills/multi-agent-development-workflow/scripts/agent-team"
"$AGENT_TEAM" --runtime codex --transport process run <TASK-ID>
```

`AGENT_TEAM` 只用于 `agent-team` CLI；仅使用 `madw start` 的 tmux 模式
不需要设置。每个新终端面板都有独立的 shell 环境，若使用该变量，需要在
那个面板重新设置，或写入 shell 启动配置。请在普通 shell 输入命令；Warp
Agent 输入框会把命令交给 Warp AI，而不会执行本地脚本。

## 安装

```bash
./install.sh
```

默认：

```text
Skill → ~/.agents/skills/multi-agent-development-workflow
madw  → ~/.local/bin/madw
agent-team → ~/.local/bin/agent-team
```

`~/.agents/skills` 作为共享用户级 Skill 目录，可同时服务 Pi 和 Codex，
因此 Pi 和 Codex 可共用同一份 Skill，不需要为两个 runtime 复制两份。

升级旧版本时，安装器会删除旧的 `~/.codex/skills/...` 或
`~/.pi/agent/skills/...` 同名 Skill，再安装共享目录中的新版本，避免重复发现。

可通过 `MADW_SKILL_DIR`、`MADW_BIN_DIR` 覆盖路径。

默认手动模式允许 Lead、Impl、Review 选择不同 Agent。自动启动模式
`madw start pi|codex` 仍使用同一种运行时；切换自动模式的团队运行时需先
`madw stop`，再启动新团队。

## 文档

- [Skill 协议](skills/multi-agent-development-workflow/SKILL.md)
- [tmux Adapter](skills/multi-agent-development-workflow/adapters/tmux.md)
- [自动编排说明](skills/multi-agent-development-workflow/automation/orchestrator.md)
- [Lead](skills/multi-agent-development-workflow/roles/lead.md)
- [Impl](skills/multi-agent-development-workflow/roles/impl.md)
- [Review](skills/multi-agent-development-workflow/roles/review.md)
