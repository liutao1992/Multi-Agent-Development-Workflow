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

然后只在 **Lead** 中输入需求。Lead 自动把 Plan/实现/返工派给 Impl，把固定
Code Head 派给独立 Review，并在 Review FAIL 时形成返工闭环。

### 运行时选择

通常无需指定：

```bash
madw start
```

选择顺序：`MADW_RUNTIME` → 已安装的 `pi` → 已安装的 `codex` → 报错。
也可以显式使用 `madw start pi` 或 `madw start codex`。

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
┌─────────────────────────────────────┐
│ Lead                                │
├──────────────────┬──────────────────┤
│ Impl             │ Review           │
└──────────────────┴──────────────────┘
```

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
死亡检测、失败输出抓取和预期工件检查。

## 启动安全

`madw start` 先检查 Git、Skill、tmux、runtime 和已有项目 team，再创建
pane。不会先创建坏 pane 再发现 runtime 不存在。

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

main 上已有的 correctness 规则继续保留：Lead-only lifecycle、Task Contract
Revision/Hash、Plan Gate、稳定 clean Code Head、独立 Review、返工 RW、PASS
才能验收，以及最终 HEAD 再校验。

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

## 安装

```bash
./install.sh
```

默认：

```text
Skill → ~/.codex/skills/multi-agent-development-workflow
madw  → ~/.local/bin/madw
```

可通过 `MADW_SKILL_DIR`、`MADW_BIN_DIR` 覆盖安装位置。

## 文档

- [Skill 协议](skills/multi-agent-development-workflow/SKILL.md)
- [tmux Adapter](skills/multi-agent-development-workflow/adapters/tmux.md)
- [自动编排说明](skills/multi-agent-development-workflow/automation/orchestrator.md)
- [Lead](skills/multi-agent-development-workflow/roles/lead.md)
- [Impl](skills/multi-agent-development-workflow/roles/impl.md)
- [Review](skills/multi-agent-development-workflow/roles/review.md)
