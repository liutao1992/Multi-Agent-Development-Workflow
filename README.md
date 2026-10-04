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

启动后，左侧 **Lead** 会提示你输入开发需求。点击左侧输入框，直接描述任务并
按 `Enter`；右上 Impl 和右下 Review 启动后保持待命，无须手动输入初始化指令。
Lead 收到你的需求后，把 Plan/实现/返工派给 Impl，把固定 Code Head 派给
独立 Review，并在 Review FAIL 时形成返工闭环。

如果左侧显示 `Pane is dead`，在项目的普通终端重新运行 `madw start codex`
（或 `madw start pi`）；它会恢复退出的 Agent，并保留现有团队和任务状态。

### 运行时选择

通常无需指定：

```bash
madw start
```

选择顺序：`MADW_RUNTIME` → 已安装的 `pi` → 已安装的 `codex` → 报错。
也可以显式使用 `madw start pi` 或 `madw start codex`。

截图中手动建立的三个 session 使用 Pi Agent；`madw start pi` 同样使用 Pi。
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

## 一个项目一个 tmux session

默认拓扑：

```text
madw-<repo-name>-<git-root-hash>
└── team
    ├── Lead
    ├── Impl
    └── Review
```

不同项目不会再复用全局 `leader/impl/review` session；同名 repo 也通过
Git 根目录短 hash 隔离。

`madw start` 默认进入三 pane UI：

```text
┌──────────────────┬──────────────────┐
│                  │ Impl             │
│ Lead             ├──────────────────┤
│                  │ Review           │
└──────────────────┴──────────────────┘
```

也可以启动为三列布局，Lead、Impl、Review 各占一列。以下命令可分别选择默认布局、
显式选择 `balanced` 或 `columns`，也可设置环境默认值：

```bash
madw start
madw start --layout balanced
madw start --layout columns
MADW_LAYOUT=balanced madw start
MADW_LAYOUT=columns madw start
```

`MADW_LAYOUT` 支持 `balanced` 和 `columns`，未设置时默认为 `balanced`；显式
`--layout` 参数优先于环境变量。布局选择仅在创建新团队时应用；已有团队保留其当前
面板排列。

像截图中的 tmux session 名一样，每个 pane 的底部分隔线上固定显示
青色 `[Leader]`、绿色 `[Impl]`、紫色 `[Review]`。Agent 自己更新终端标题时，
这些角色标识也不会被覆盖。界面上的 Leader 对应流程中的 Lead 角色。

底部消息栏用深色背景、内边距和空白行分隔内容，留出阅读空间。它分别显示
**工作目录与当前 Git 分支**、**任务进度**和**Agent 通信**。任务进度用中文
突出显示当前阶段和任务编号；通信行用 `Leader → Impl`、
`Impl → Leader`、`Leader → Review` 等箭头显示
**谁正与谁交接、当前在等待谁、哪一轮已完成**。这些提示由 `madw send`、
`wait` 和 `signal` 更新。状态栏每 5 秒读取当前任务的 `STATUS.md`，因此
任务进入 `ACCEPTED` 后会自动显示“已验收”和“等待新需求”，不必等待下一条
交接命令。所有提示都在 tmux 状态栏中，不会写入 Agent 的对话或增加模型
上下文；它显示协议状态，不显示 Agent 的内部思考。

在 tmux 面板内点击 Lead、Impl 或 Review，即可将键盘焦点切到对应 Agent；
再按 `Enter` 可确认该 Agent 当前的提示（例如 Codex 的目录信任确认）。
`madw start` 和 `madw watch` 会为当前团队启用鼠标操作，不修改其他 tmux 会话。

在三面板界面按 **Ctrl+C** 会结束整个当前项目团队：三个 Agent 进程、三个
pane 和对应的 tmux session 都会退出。它不会结束其他项目或手动创建的 tmux
session。若只想暂时离开界面、让团队继续运行，按 **Ctrl+b，然后按 d**；
之后在项目目录执行 `madw watch` 可重新进入。也可以在普通终端执行
`madw stop` 结束团队。此快捷键适用于通过 `madw start`、`watch` 或
`attach` 进入的团队界面；直接使用 `tmux send-keys` 向 Agent 发送 Ctrl+C
仍只会中断该 Agent。

## 常用命令

```bash
madw start [pi|codex]
madw status
madw watch
madw attach leader
madw attach impl
madw attach review
madw restart review
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

## 启动安全

`madw start` 先检查 Git、Skill、tmux、runtime 和已有项目 team，再创建
pane。不会先创建坏 pane 再发现 runtime 不存在。

每个 Agent pane 启动或重启时都会显式进入当前项目路径，避免长期运行的
tmux server 仍指向已删除的旧目录，导致 Codex/Pi 报 `No such file or directory`
或 `uv_cwd ENOENT`。

当前启动检查确认的是 **Agent 进程已经存活**，不是 runtime-specific 的
“交互界面已经 Ready”。Pi/Codex 的 PTY 通常会保留提前输入；如果后续实测
出现启动 prompt 被吞的问题，再在各 runtime adapter 中增加专门的 readiness
探测，不在通用 tmux 层猜测 UI 状态。

启动不依赖固定 `sleep 1`：

```bash
madw start --boot-timeout 20
MADW_BOOT_TIMEOUT=20 madw start
```

## Review 独立性

Review pane 地址稳定，但每轮 substantive Review 必须刷新上下文：

```bash
madw restart review
```

内部使用 `tmux respawn-pane -k`，保留 session/layout/pane ID，替换 Review
Agent context。

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
因此 `./install.sh` 与 `madw start` 的 runtime 自动选择保持一致，不需要
为两个 runtime 复制两份 Skill。

升级旧版本时，安装器会删除旧的 `~/.codex/skills/...` 或
`~/.pi/agent/skills/...` 同名 Skill，再安装共享目录中的新版本，避免重复发现。

可通过 `MADW_SKILL_DIR`、`MADW_BIN_DIR` 覆盖路径。

一个 MADW team 只使用一个 runtime。角色重启只允许：

```bash
madw restart leader
madw restart impl
madw restart review
```

如果要从 Codex 切换到 Pi（或反向），使用：

```bash
madw stop
madw start pi
```

## 文档

- [Skill 协议](skills/multi-agent-development-workflow/SKILL.md)
- [tmux Adapter](skills/multi-agent-development-workflow/adapters/tmux.md)
- [自动编排说明](skills/multi-agent-development-workflow/automation/orchestrator.md)
- [Lead](skills/multi-agent-development-workflow/roles/lead.md)
- [Impl](skills/multi-agent-development-workflow/roles/impl.md)
- [Review](skills/multi-agent-development-workflow/roles/review.md)
