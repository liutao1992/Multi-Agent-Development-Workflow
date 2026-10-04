# Native SubAgent 三面板观察设计

## 目标与边界

保留 Native SubAgent 的编排方式：Lead 是父 Agent，Impl 是同一 Task 中可复用的子 Agent，每轮 Review 都是新的子 Agent。同时用三个面板观察它们：

```text
┌──────────────────────────────┬──────────────────────────────┐
│ Lead：交互和生命周期决策      │ Impl：只读观察               │
│ 创建任务、调度、修改 STATUS   │ 当前阶段、进度、工件、结果    │
│                              ├──────────────────────────────┤
│                              │ Review：只读观察             │
│                              │ 当前轮次、进度、工件、结果    │
└──────────────────────────────┴──────────────────────────────┘
```

只有 Lead 面板接受工作流指令。打开或关闭观察面板不创建、不停止、不修改子 Agent。Impl 和 Review 仍运行在 Lead 所在的原生宿主中。协议要求同一可变工作树上的实现与实质性复核串行执行，因此 Impl 工作时，Review 面板显示“等待”是正常现象。

## 当前如何使用三面板

**此设计尚未实现。** 如果现在需要分别看到 Impl、Review 的实时工作输出，请使用 README 的 [Warp 三面板 Queue 方式](../README.md#方式三warp-三面板-queue)：右上执行 `agent-team --runtime codex worker Impl`，右下执行 `agent-team --runtime codex worker Review`，左侧执行 `agent-team --runtime codex --transport queue start "<需求>"`。Queue 工作者是独立进程，不能称为 Native SubAgent。

目前 Native 模式只需在 Lead 面板发送 `Transport: native-subagent` 的任务指令。普通终端面板无法仅靠打开三个窗口就附着到两个子 Agent 的内部执行流；独立的 `agent-team` CLI 也无法进入已有的 Lead 父会话。

## 实现后如何使用

下列命令是**计划中的接口，现在不能运行**。实现观察器后，使用者将在同一个项目目录打开三个 Warp 面板：

1. 左侧启动支持 Native SubAgent 的 Lead 会话，按 README 的 Native 方式创建或继续 Task，取得 `<TASK-ID>`。
2. 右上执行 `agent-team observe <TASK-ID> --role Impl`，只读查看 Impl 的当前进度和历史轮次。
3. 右下执行 `agent-team observe <TASK-ID> --role Review`，只读查看每轮全新 Review 的进度和结果。
4. 观察面板可稍后加入或重开；使用相同 Task ID 重新连接，不触发重试或重新调度。需要对任务作出决定时，只与 Lead 会话交互。

若某宿主提供**受支持的原生子 Agent 事件订阅接口**，对应适配器可显示工具事件和消息，并明确标记为 `宿主实时事件`。没有该接口时，显示 Lead/子 Agent 主动写出的结构化进度，明确标记为 `进度更新`；它不等于完整执行记录，也不包含每一次工具调用或私有推理。实现前必须针对具体宿主和版本验证事件接口是否存在。不能通过读取无关会话文件或启动第二个 `codex exec` 来冒充原生流。

## 数据与事件契约

观察数据放在目标项目未被 Git 跟踪的 Control Plane 运行目录：

```text
<project-root>/.agent-team/runtime/<TASK-ID>/native-observe/events.jsonl
```

文件每行是一个 UTF-8 JSON 对象：

| 字段 | 含义 |
|---|---|
| `schema` | 事件格式版本，初始为 `1` |
| `time` | ISO 8601 UTC 时间 |
| `task_id` | Task ID |
| `role` | `Lead`、`Impl` 或 `Review` |
| `run_id` | 当前子 Agent 调用或 Lead 动作的唯一 ID |
| `round` | 对应 Plan、实现或 Review 轮次；可为空 |
| `kind` | `started`、`progress`、`artifact`、`completed` 或 `failed` |
| `summary` | 简短、可向用户展示的进度描述 |
| `artifact` | 可选的 Task 相对工件路径 |

Lead 在派发前写 `started`，等待原生子 Agent 返回后写 `completed` 或 `failed`。子 Agent 在有意义的节点写 `progress` 和 `artifact`。观察器按角色和当前 `run_id` 过滤，并从 `STATUS.md` 读取权威生命周期状态。派发前显示“等待”；已派发显示“运行中”；没有终结事件且长时间无更新时显示“最后更新时间，状态未知”，不能擅自判定成功或失败。Review 每轮生成新的 `run_id`，旧轮次保留为历史。

事件必须以完整 JSON 行写入；同一时刻串行写，读取时容忍最后一行不完整。不要记录密钥、原始提示、思维链或 Impl 私有推理。观察事件只是运行元数据，不能作为 Plan/IMPL/REVIEW 证据，也不能授权 STATUS 转换。Review 子 Agent 不从 Impl 的观察日志获取其私有上下文。

## 实施与验收顺序

1. 实现事件写入器及只读 `agent-team observe <TASK-ID> --role Impl|Review` 命令，支持迟到加入、断线重连和不完整 JSON 行；观察器绝不写 STATUS 或派发任务。
2. 在 Native Lead/Impl/Review 指令中约定里程碑事件的写入时机，确保只写 `runtime/`，不进入代码提交或干扰 Control Plane 校验。
3. 仅在宿主确有受支持的原生事件 API 时增加实时事件适配器，并在面板区分 `宿主实时事件` 与 `进度更新`。
4. 验证“计划 → 实现 → 新 Review → 返工 → 新 Review”的三条时间线；确认重开观察面板不影响运行、Review 保持全新上下文、没有私有推理泄漏。
