# 多 Agent 开发工作流

本项目用三个角色完成一个开发任务：**Lead** 定义需求、推进状态并最终验收；**Impl** 制定计划、修改代码和测试；**Review** 基于固定的代码提交独立复核。只有 Lead 能修改任务生命周期状态并宣布 `ACCEPTED`。

> `feature/agent-orchestrator` 分支提供实验性的自动编排；`main` 是稳定的手动交接版本。

## 先选运行方式

| 方式 | 适合场景 | 如何启动 | 能看到什么 |
|---|---|---|---|
| **Native SubAgent** | 日常交互式开发；宿主支持原生子 Agent | 在 Lead 会话中提出任务 | Lead 会话和子 Agent 的最终回报；宿主是否显示子 Agent 过程取决于宿主 |
| **Process** | CI、无人值守、本地单命令执行 | `agent-team --transport process` | CLI 输出及运行日志 |
| **Queue** | 现在就需要 Warp 三面板，分别看到 Impl、Review 工作者 | 两个 `worker` 面板加一个 Lead 面板 | 各工作者进程的实时输出；它们是独立进程，不是 Native SubAgent |
| **手动交接** | 宿主没有自动编排能力，或需要人工控制每次交接 | 分别打开 Lead、Impl、Review 会话 | 各会话的交互过程；需要手动通知下一角色 |

优先使用 Native SubAgent。若宿主不支持原生子 Agent，用 Process；如果需要**当前可用**的三面板实时输出，用 Queue。手动方式是最后的退路。Native 模式的只读三面板观察方案见[设计与使用说明](docs/native-subagent-three-pane-observability.md)：该观察命令尚未实现，不能把设计中的命令当作现有功能。

**并发规则：** 同一个 Git 工作树同一时间只能运行一个自动化 Task。Process/Queue 使用 Code Plane 锁；Native 模式由 Lead 遵守同样约束。要并行开发多个 Task，请为每个 Task 创建独立的 Git worktree。不要自行清除疑似陈旧的锁：仍可能有工作者在改代码。若发生中断或校验失败，先检查 Task 运行目录中的 `pending-validation.json` 并核对状态。

## 安装

可安装的 Skill 是仓库中的 `skills/multi-agent-development-workflow/` 目录，包含 `SKILL.md`、角色、工作流、模板、运行时适配器和 `scripts/agent-team`。

在 Codex 中手动安装此分支：

```bash
git clone -b feature/agent-orchestrator \
  https://github.com/liutao1992/Multi-Agent-Development-Workflow.git
mkdir -p ~/.codex/skills
cp -R Multi-Agent-Development-Workflow/skills/multi-agent-development-workflow \
  ~/.codex/skills/multi-agent-development-workflow
```

如果你的 Skill 安装器支持安装仓库子目录，也可以直接安装 `skills/multi-agent-development-workflow/`。安装后，在**要开发的项目目录**启动 Agent 或运行 CLI，而不是在本仓库中替目标项目执行任务。

`AGENT_TEAM` 只供终端里的 CLI 命令使用。**只在编码 Agent 对话中使用 Native SubAgent 时，不需要设置它。** 使用 Process、Queue，或执行 `doctor`、`status`、`metrics`、`resume` 等 `agent-team` 命令时，先在该终端设置一次路径：

```bash
export AGENT_TEAM="$HOME/.codex/skills/multi-agent-development-workflow/scripts/agent-team"
```

此设置只对当前终端会话及其子进程生效。新开一个 Warp 面板或终端窗口时，需要在那个面板再执行一次；Queue 三个面板都要设置。也可以把这行加入 `~/.zshrc` 或 `~/.bashrc`，让之后启动的终端自动设置。使用 Pi 时，请把路径改为实际安装 Skill 的位置。

**在 Warp 中请使用普通终端输入框执行这些 `bash` 命令。** 如果输入记录前出现 `/agent`，说明命令被送进 Warp AI 对话，随后出现“out of AI credits”是 Warp AI 的额度提示，`agent-team doctor` 并没有运行。此时打开或切换到显示 shell 提示符的终端面板，不要带 `/agent` 前缀；先执行上面的 `export`，再执行 `"$AGENT_TEAM" --runtime codex doctor`。可以先运行 `printf '%s\n' "$AGENT_TEAM"`，确认当前面板已经设置了路径。

## 方式一：Native SubAgent

Native 模式由当前 Lead 会话作为父 Agent。Lead 通常复用同一个 Impl 子 Agent 完成计划、实现和返工；每轮 Review 都新建一个 Review 子 Agent，以保持独立性。Lead 自动执行计划审批、冻结 Review 目标、处理返工和最终验收。

### 新建任务

在目标项目中打开支持原生子 Agent 的编码 Agent，对 Lead 发送：

```text
Use multi-agent-development-workflow.
Role: Lead.
Mode: Automatic.
Transport: native-subagent.

新建任务：增加 iOS 系统词典释义功能。
```

Lead 应创建 `.agent-team/tasks/<TASK-ID>/`，写入 `TASK.md` 与 `STATUS.md`，随后按 `Impl 制定计划 → Lead 审批 → Impl 实现与测试 → 新 Review 复核 → Lead 验收` 推进。Review 失败时，Lead 把确认的返工项交给原 Impl，并在下一轮新建 Review 子 Agent。正常交接无需你去其他面板输入 `继续`。

### 继续任务与处理阻塞

在原 Lead 会话中发送：

```text
Use multi-agent-development-workflow.
Role: Lead.
Mode: Automatic.
Transport: native-subagent.

继续 TASK-YYYYMMDD-NNN-short-name
```

如果 Lead 会话已经绑定且只有一个明确的 Task，直接发送 `继续` 即可。若任务为 `BLOCKED`，把所需产品决策发给 Lead；Lead 记录决策并按 `STATUS.md` 的 Resume State 恢复。丢失 Impl 会话时，Lead 可根据 STATUS 和工件建立替代子 Agent；不能靠旧会话的私有思考重建 Review 依据。

### Native 模式的三面板可见性

目前一个 Lead 面板就能完成编排，但普通 Warp 终端面板**不能自动附着到原生子 Agent 的内部执行流**。想马上看到 Impl、Review 各自的工作者输出，请使用下面的 Queue 模式。

[Native 三面板观察设计](docs/native-subagent-three-pane-observability.md)计划在 Lead 左面板保留交互，在右上、右下面板分别运行 Impl、Review 的只读观察器。没有宿主事件接口时，只能显示结构化进度、工件和结果，不能显示每一次工具调用；有受支持的宿主事件接口时，才可显示更细的实时事件。**观察器尚未实现，当前不能按设计文档直接启动。**

不要运行 `agent-team --transport subagent` 来创建 Native 子 Agent：独立 CLI 无法接入已运行的 Lead 父会话，该参数会被拒绝。

## 方式二：Process 自动运行

Process 模式使用单条 CLI 命令驱动同一套生命周期，分别启动 Codex 或 Pi 工作者进程。它不需要保留三个终端面板。

先检查环境：

```bash
"$AGENT_TEAM" --runtime codex doctor
```

从需求新建任务，命令返回 Task ID：

```bash
"$AGENT_TEAM" --runtime codex --transport process \
  start "增加 iOS 系统词典释义功能"
```

按 Task ID 继续：

```bash
"$AGENT_TEAM" --runtime codex --transport process \
  run TASK-YYYYMMDD-NNN-short-name
```

使用 Pi 时，将 `--runtime codex` 改为 `--runtime pi`：

```bash
"$AGENT_TEAM" --runtime pi --transport process \
  start "增加 iOS 系统词典释义功能"
```

Process 模式会检查工作树是否干净、角色写入边界、计划审批、Review 目标与 Code Head、超时和取消，并在每次 Lead 动作后校验状态转换。Review 不能改代码、Git HEAD 或 STATUS；计划阶段 Impl 不能改代码；实现阶段 Impl 必须留下干净的已提交代码快照。

查看任务状态和运行指标：

```bash
"$AGENT_TEAM" status TASK-YYYYMMDD-NNN-short-name
"$AGENT_TEAM" metrics TASK-YYYYMMDD-NNN-short-name
```

## 方式三：Warp 三面板 Queue

这是**当前已实现**的三面板方案。左侧运行 Lead/Orchestrator，右上运行 Impl worker，右下运行 Review worker。右侧是等待任务的 CLI 工作者进程，不是已经打开的交互式 Codex/Pi 会话；Queue 不会向任意会话注入提示。不要开启 Warp 的同步输入。

```text
┌──────────────────────────────┬──────────────────────────────┐
│ Lead / Orchestrator          │ Impl worker                  │
│ 创建任务、调度、修改 STATUS   │ 接收计划/实现/返工任务         │
│ 审批、最终验收               ├──────────────────────────────┤
│                              │ Review worker                │
│                              │ 接收独立复核任务             │
└──────────────────────────────┴──────────────────────────────┘
```

三个面板都进入同一个目标项目，并在每个面板的普通终端输入框分别执行上文的 `export AGENT_TEAM="..."` 路径设置。启动顺序如下。

**右上 Impl 面板**，运行一次并保持运行：

```bash
"$AGENT_TEAM" --runtime codex worker Impl
```

**右下 Review 面板**，运行一次并保持运行：

```bash
"$AGENT_TEAM" --runtime codex worker Review
```

**左侧 Lead 面板**，新建任务：

```bash
"$AGENT_TEAM" --runtime codex --transport queue \
  start "增加 iOS 系统词典释义功能"
```

继续已有任务：

```bash
"$AGENT_TEAM" --runtime codex --transport queue \
  run TASK-YYYYMMDD-NNN-short-name
```

如果使用 Pi，三个面板都将 `--runtime codex` 改为 `--runtime pi`。Lead 会自动把工作派给右侧面板，等待结果，再继续状态转换、返工或验收；不需要在面板之间手动输入指令。

Queue 的任务按项目隔离。任务经过 `QUEUED → CLAIMED/RUNNING → SUCCEEDED/FAILED/CANCELLED`；如果过期任务的原工作者身份或停止状态无法证实，运行时会隔离该任务并停止新的自动执行，避免旧进程继续改同一个工作树。出现隔离时应先检查工作者进程与运行目录，再恢复任务。

## 方式四：手动交接

当没有可用的自动编排能力时，在目标项目中打开三个交互式 Agent 会话，分别加载 Skill 和对应角色文件：`roles/lead.md`、`roles/impl.md`、`roles/review.md`。Review 每一轮都要使用**全新会话**，不能复用上一轮 Review。

首次绑定可分别发送：

```text
Lead 面板：Use multi-agent-development-workflow. Role: Lead. Mode: Manual.
Impl 面板：Use multi-agent-development-workflow. Role: Impl. Mode: Manual.
Review 面板：Use multi-agent-development-workflow. Role: Review. Mode: Manual.
```

按以下顺序操作：

1. 给 Lead 提需求，由 Lead 建立 TASK 和 STATUS。记下返回的 Task ID。
2. 在 Impl 面板发送 `继续 <TASK-ID>`，让 Impl 读取 STATUS、制定计划；完成后通知 Lead。
3. 在 Lead 面板发送 `继续 <TASK-ID>`，由 Lead 审批计划并推进状态。
4. 再让 Impl `继续 <TASK-ID>`，实现、测试并写入 IMPL 工件。
5. Lead `继续 <TASK-ID>`，冻结确切的 Review 目标和 Code Head。
6. 在**新的** Review 会话发送 `Review <TASK-ID>`；Review 完成后让 Lead `继续 <TASK-ID>`。
7. 如果 Review 失败，Lead 确认返工项，原 Impl 返工，然后重复步骤 5–6 并换新的 Review 会话；通过后由 Lead 验收。

每个角色先读 `STATUS.md`，再读它引用的工件。不要按文件名最大编号猜测当前 Plan、IMPL 或 REVIEW。若会话已绑定唯一任务，后续可使用简短的 `继续`、`Review`、`验收`。手动方式仍遵守角色权限、计划审批、固定代码快照和最终验收规则。

## 查看状态、阻塞恢复与数据位置

下面的 CLI 查询适用于已存在的任务，且不会启动工作者：

```bash
"$AGENT_TEAM" doctor
"$AGENT_TEAM" status TASK-YYYYMMDD-NNN-short-name
"$AGENT_TEAM" metrics TASK-YYYYMMDD-NNN-short-name
```

`doctor` 报告运行时是否可用，不会创建 Control Plane；`status` 为只读查询。`metrics` 统计 Process/Queue 的工作者调用；Native 模式目前没有接入这份统计，返回零不代表子 Agent 没有执行。

Process/Queue 遇到 `BLOCKED` 会停止，获得人工决策后使用显式恢复命令：

```bash
"$AGENT_TEAM" --runtime codex \
  resume TASK-YYYYMMDD-NNN-short-name "采用向后兼容的迁移方式"
```

`resume` 先让 Lead 记录 Blocked Resolution 并校验返回到 STATUS 指定的 Resume State，然后继续自动执行。Native/手动模式则把决策发给 Lead。

默认数据位置：

```text
<project-root>/.agent-team/
├── INDEX.md
├── runtime/                         # 调度日志与运行元数据
└── tasks/<TASK-ID>/
    ├── TASK.md                       # 需求契约
    ├── STATUS.md                     # 唯一生命周期状态
    ├── plans/PLAN-vNNN.md
    ├── implementations/IMPL-NNN.md
    ├── reviews/REVIEW-NNN.md
    └── ACCEPTANCE.md                # Lead 的最终验收
```

项目根目录通过 `git rev-parse --show-toplevel` 识别。`.agent-team/` 是 Control Plane，不能进入代码提交；安装/运行时通常将它写入 `.git/info/exclude`。可用 `git ls-files .agent-team` 确认没有被跟踪。只有显式配置 `AGENT_TEAM_DIR` 才会改用外部 Control Root；多个项目共享时按项目指纹隔离。若自定义根目录仍在工作树内，CLI 会验证它未被 Git 跟踪。

## 生命周期与校验规则

```text
用户需求 → Lead 建任务 → Impl 出 Plan → Lead 审批
         → Impl 提交代码、测试、IMPL → Lead 固定 Review 目标
         → 全新 Review ┬─ FAIL → Lead 确认返工 → 原 Impl → 全新 Review
                       └─ PASS → Lead 写 ACCEPTANCE → ACCEPTED
```

`TASK.md` 是需求来源，记录修订号和 SHA-256 契约哈希；当前 PLAN、IMPL、REVIEW、STATUS、ACCEPTANCE 必须绑定相同版本。Lead 修改产品需求时，须记录变更并重新进入计划流程；Review 返工说明属于单独的 Rework Requirements。Impl 负责 Plan 正文，Lead 只能处理待审批 Plan 的 Approval 区块；决定后该版 Plan 冻结。

`STATUS.md` 是状态来源。Python 校验器在自动执行的 Lead 动作后检查合法状态转换及证据，例如：审批后才能实现；Review 必须针对确切的已提交 Code Head；PASS 才能验收；验收时当前 Git HEAD 仍须等于已复核的 Head。Review 的 FAIL 必须有阻塞问题，目标不匹配须明确记录 `REVIEW_TARGET_MISMATCH`。旧证据不能在需求或代码变更后直接复用。

自动执行遇到以下情况会停止：需要真实的产品决策、`BLOCKED`、工作者失败或消失、没有协议进展、代码工作树不干净、Review 目标无效、角色越权、工作树被另一 Task 占用，或达到编排步数上限。由 Lead 消费问题和证据后再恢复。

## 进一步文档

- [Skill 协议](skills/multi-agent-development-workflow/SKILL.md)
- [Native SubAgent 编排](skills/multi-agent-development-workflow/automation/subagent.md)
- [Native 三面板观察设计与使用说明](docs/native-subagent-three-pane-observability.md)
- [独立 Orchestrator](skills/multi-agent-development-workflow/automation/orchestrator.md)
- [Warp 适配器](skills/multi-agent-development-workflow/adapters/warp.md)
- [Codex 适配器](skills/multi-agent-development-workflow/runtimes/codex.md)
- [Pi 适配器](skills/multi-agent-development-workflow/runtimes/pi.md)
