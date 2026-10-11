# Roundtable B: 管线工具评估 — R2 架构师发言

> 发言人: 高见远（架构师） | 日期: 2026-07-30 | 版本: v2.0
> 关联: Product R2 发言 (t_349b1013), R1 架构师发言 (t_5b17ec48), Engineer 发言

---

## 0. R1 → R2 转折点

R1 我拒绝了 OpenSpec——因为它是「Claude Code 生态的东西」，而我们跑在 Hermes 上。

**R2 我收回这个判断。** OC 的新事实改变了评估：

> OpenSpec `supported-tools.md` 官方列出 Hermes Agent，skill 路径 `.hermes/skills/openspec-/SKILL.md`

这不是社区 hack 或偶然兼容——是 OpenSpec 的一等公民支持。Product 的转向基于硬事实，我同意。

但有一个 **工程硬约束** Product 没提：

---

## 1. OpenSpec 的技术代价

### 1.1 硬依赖链

```
OpenSpec CLI (@fission-ai/openspec v1.7.0)
  ├── requires: Node >= 20.19.0   ← 我们当前 v18.19.1，不满足
  ├── install: npm install -g @fission-ai/openspec
  ├── deps: commander, chalk, zod, yaml, inquirer, ...
  └── telemetry: 默认开启（需 export OPENSPEC_TELEMETRY=0 关闭）
```

**当前环境**：`node v18.19.1`。OpenSpec 的 `engines` 字段要求 `>=20.19.0`。`npm install` 在 `engine-strict=false` 时不会阻止安装——但运行期可能遇到 v20-only 的 API（如 `import.meta.resolve` 等）。**风险可控但存在**：多数 v1.7 CLI 工具在 Node 18 下 work，但官方不保证。

### 1.2 推荐操作

```bash
# 方案 A（推荐）：升级 Node
nvm install 20.19.0  # 或 22.x LTS

# 方案 B（临时）：用现有 Node 18 试，遇到问题再升
npm install -g @fission-ai/openspec@latest --engine-strict=false
```

**架构判断**：Node 20.19 vs 18.19 的跨度不大（都是 LTS 线），升级风险低。**建议方案 A**——不要在新工具链的第一个依赖上就开始欠技术债。

### 1.3 OpenSpec 本身的架构质量

| 维度 | 评估 | 说明 |
|------|:---:|------|
| 规范格式 | ✅ Markdown | 纯文本，可 Git diff、可 grep、可 LLM 阅读 |
| 验证能力 | ✅ `openspec validate --strict --json` | 确定性校验，脚本可消费 JSON 输出 |
| 生命周期 | ✅ propose→apply→archive | 完整，archive 防止 specs 腐化 |
| 生态 | ✅ 20+ agent 支持 | Hermes 是一等公民，不是 afterthought |
| 侵入性 | ⚠️ 中等 | 需要 init→update 生成 `.hermes/skills/openspec-*/` |
| 许可证 | ✅ MIT | 可自由 fork |

**结论**：OpenSpec 不是另一个「更重的 Jira」。它是 Markdown + CLI 校验的组合——恰好卡在「灵活足够让 LLM 读」和「严格足够让脚本验」的甜点区。

---

## 2. 与现有管线的集成点

### 2.1 OpenSpec ↔ autopilot ↔ checkpoint 数据流

Product 把 OpenSpec 放在 autopilot 前面。从技术集成顺序看：

```
┌─────────────────────────────────────────────────────┐
│                  OpenSpec Layer                       │
│  .hermes/skills/openspec-propose/SKILL.md            │
│  .hermes/skills/openspec-apply/SKILL.md              │
│  .hermes/skills/openspec-archive/SKILL.md            │
│                                                      │
│  产出: openspec/changes/{task-id}/                    │
│        ├── spec.md          ← 人类可读规范            │
│        ├── tasks.md         ← 分解的任务清单           │
│        └── design.md        ← 技术设计（如有）         │
└──────────────┬──────────────────────────────────────┘
               │ spec.md 写入完成
               ▼
┌─────────────────────────────────────────────────────┐
│                Autopilot Layer (P0-2)                │
│  autopilot.sh: cron 轮询 kanban → 检测状态变更       │
│                                                      │
│  读: kanban task body (含 OpenSpec ref)              │
│  读: pipeline_state.db (checkpoint)                  │
│  写: kanban comment [AUTOPILOT: ...]                 │
└──────────────┬──────────────────────────────────────┘
               │ 步骤状态变更
               ▼
┌─────────────────────────────────────────────────────┐
│              Checkpoint Layer (P0-3)                 │
│  pipeline_state.db (SQLite WAL)                      │
│                                                      │
│  记录: task_id → step_name → status → artifacts      │
│  提供: 断点恢复、超时检测、产物追踪                    │
└─────────────────────────────────────────────────────┘
```

### 2.2 集成顺序分析：Product 说 OpenSpec 在 autopilot 前面——技术上对吗？

**对，但有一个前置条件。**

OpenSpec 是规范层——它定义「要做什么」。Autopilot 是执行层——它根据规范驱动步骤。没有规范，autopilot 只能读 kanban body 里的 NL 自由文本，这就是 Frank 不信任管线的根源。

**但前置条件是**：autopilot 需要能「读 OpenSpec 的 spec.md 并据此执行」。如果 autopilot 做了但 OpenSpec 还没引入，autopilot 读的是非结构化的 kanban body；如果 OpenSpec 引入了但 autopilot 还没做，规范写了没人执行。**两者必须协同到位。**

**建议的顺序**：

```
Step 0: npm install -g @fission-ai/openspec + openspec init  [0.2h]
        → 生成 .hermes/skills/openspec-*/ 和 openspec/ 目录

Step 1: 写 1-2 个 devPPL 的 pilot spec 验证流程           [0.3h]
        → openspec propose "管线步骤合约引擎"
        → 验证 openspec validate --strict --json 通过

Step 2: P0-2 checkpoint (Engineer 建议的先做)              [1.0h]
        → pipeline_state.db + checkpoint.py

Step 3: P0-1 步骤合约引擎                                  [2.5h]
        → state.py + JSONL 合约

Step 4: 将 OpenSpec 集成到 autopilot 的读取路径            [0.5h]
        → autopilot 从 kanban body 提取 OpenSpec ref
        → 读 openspec/changes/{id}/spec.md → 解析 requires/produces
```

**总工期增量**：Step 0 + Step 1 + Step 4 = ~1.0h OpenSpec 集成成本。加上 Engineer 评估的 ~9.6h 全栈 = **~10.6h ≈ 2 个工作日**。

---

## 3. LangGraph 模式借鉴——哪些值得抄，哪些不合适

### 3.1 值得抄的

| LangGraph 概念 | 我们的等价物 | 抄什么 |
|:---|:---|:---|
| **Checkpointer** (持久化图状态) | P0-2 `pipeline_state.db` | **checkpoint 粒度**：LangGraph 在每个 super-step 后自动 checkpoint。我们不需要真正的图执行——但「步骤完成后自动写 checkpoint」的模式值得抄。`autopilot.sh` 每检测到 kanban status 变更 → 自动写 pipeline_state.db |
| **Interrupt** (暂停等待人工输入) | kanban `blocked` + roundtable D 类 | **中断语义**：LangGraph 的 `interrupt()` 是一个显式的「暂停点」。我们 kanban block 后没有「恢复时自动从断点继续」的机制——目前靠 cron 重新轮询。P2-2 的中断接口可以参考这个模式 |
| **Resume** (从 checkpoint 恢复) | P0-3 resume.sh (P19-03) | **恢复机制**：LangGraph 的 `graph.stream(resume_from=checkpoint)` 是 API 级的恢复。我们的 resume 需要：读 pipeline_state.db → 找到最后完成的 step → 派发下一个 step。这个接口设计可以借 LangGraph 的模式 |
| **State update** (状态更新不可变) | SQLite INSERT (append-only) | LangGraph 的状态更新是 reducer-based（新状态 = reducer(旧状态, 更新)）。我们不需要 reducer——但「状态不可变 + 追加」的模式确保审计可追溯 |

### 3.2 不合适的

| LangGraph 概念 | 为什么不合适 |
|:---|:---|
| **图编译 (StateGraph.compile)** | 我们的「图」是 cron+kanban 的松散耦合——不是编译期确定的 DAG。步骤之间通过 kanban status 隐式连接，不是显式边 |
| **Streaming / 事件循环** | LangGraph 假设一个长生命周期的 runtime（graph.stream() 持续输出事件）。我们是 cron job——每次运行是一次性的，不持有 runtime |
| **Node 内 LLM 调用** | LangGraph 的 node 内部通常放 LLM call（tool-calling agent）。我们的 node（steps）本身就是跨 agent 会话的——不能假设一个 node 内是同步 LLM call |
| **条件边 (conditional edges)** | LangGraph 的条件边是 `Callable[[State], str]`——在运行时根据状态决定下一节点。我们的条件路由（P1-1）可以用 YAML 替代——不需要运行时 Python 函数 |

### 3.3 borrow 不 fork

Product 说「框架级不 fork」——完全同意。LangGraph 是一个 runtime 框架，fork 它意味着维护一个 Python 图执行引擎。我们的 cron+kanban 架构不需要图引擎——只需要借鉴它的 **checkpoint/interrupt/resume 数据模型**。这三者加起来的数据模型大约 3 个 SQL 表 + ~20 行 Python，不构成 fork。

---

## 4. DPL-009 webhook——实测方案

### 4.1 核心问题

> Hermes webhook 能否订阅 kanban 事件？

### 4.2 实测方案（端到端，~0.5h）

```bash
# Step 1: 查 Hermes webhook 的事件类型支持
hermes webhook list --json 2>/dev/null || echo "webhook 子系统可能未安装"

# Step 2: 如果有 webhook，查它是否暴露 kanban 事件
# 看文档或源码中 webhook 的 event_types 列表
grep -r "kanban" ~/.hermes/plugins/webhook*/ 2>/dev/null || echo "webhook plugin 可能未加载"

# Step 3: 创建一个测试 webhook 订阅
# 如果有 webhook 子系统：
hermes webhook create \
  --events "kanban.status_change" \
  --url "http://localhost:9999/test" \
  --json

# Step 4: 触发一个 kanban 事件
# 手动改一个 task 的状态
python3 -c "
from scripts.lib.kanban_helpers import get_task, update_task_status
# 读当前 task → 检查 webhook 是否触发
"

# Step 5: 验证
# 看 webhook receiver 是否收到事件
# 如果没收到 → 说明 Hermes webhook 不订阅 kanban → 回退到 cron polling
```

### 4.3 架构判断

**大概率 Hermes webhook 不支持 kanban 事件订阅。** 理由：

1. Hermes webhook 的设计初衷是「Gateway 层接收外部消息」（Telegram/Slack webhook），不是「内部事件总线」
2. Kanban dispatcher 是基于 SQLite polling 的（`kanban.db`），不是事件驱动的
3. 如果 webhook 能订阅 kanban，Engineer 的 autopilot 方案就不需要 cron polling 了

**但这不代表 DPL-009 死了。** 即使 webhook 不支持 kanban，我们仍有两条路径：

| 路径 | 机制 | 延迟 | 适用场景 |
|:---|:---|:---:|:---|
| A: autopilot cron polling | 每 2min 轮询 kanban 状态变更 | ~2min | 常规步骤推进 |
| B: 自定义事件钩子 | state.py 写 checkpoint 时 curl webhook URL | ~0s | 紧急告警（超时、合约失败） |

**推荐：A + B 组合。** cron polling 是主路径（覆盖 95% 场景），自定义 webhook 是快速路径（覆盖超时告警等 5%）。

---

## 5. 架构风险全景

### 5.1 新识别风险

| 风险 | 级别 | 触发条件 | 缓释 |
|:---|:---:|:---|:---|
| **Node 版本不兼容** | MINOR | Node 18 下 OpenSpec 运行期遇到 v20-only API | 升级到 Node 20.19+（方案 A）。如暂不升级，试运行 pilot spec 看结果 |
| **OpenSpec telemetry 隐私** | LOW | 默认开启，发送命令名和版本到 PostHog | `export OPENSPEC_TELEMETRY=0` 或 `DO_NOT_TRACK=1` |
| **OpenSpec skill 与 SOUL.md 冲突** | MEDIUM | OpenSpec 的 SKILL.md 指令可能与 SOUL.md 的铁律冲突（如「OpenSpec 要求 LLM 输出 spec」vs SOUL.md「不代替 Frank 做决定」） | 审查 OpenSpec skill 内容后再 merge。如冲突，本地 patch skill |
| **close.sh 幽灵依赖** | MAJOR | Engineer 发现 GAI 标注 done 但 repo 中无 close.sh。如果 close.sh 不存在，P0 管线缺了闭环最后一步 | P0 执行前做一次 5 分钟管线健康检查：`find / -name close.sh 2>/dev/null` |
| **pipeline_state.db 跨 workspace 共享** | MEDIUM | 如果 InfoManager 已有 `pipeline_state.db`，devPPL 再用一个独立 DB → 两个 DB schema 可能不一致 | devPPL 独立维护自己的 `pipeline_state.db`（`/workspace/devPPL/pipeline_state.db`），不跨 workspace 共享 |
| **OpenSpec specs 腐化** | MEDIUM | specs 写了但不维护 → 变成新的 GAI（过时但标记 done） | 用 `openspec validate --strict` 做 CI-style 检查；`openspec archive` 清理过时 specs |

### 5.2 R1 已识别、R2 仍有效的风险

| 风险 | R1 状态 | R2 更新 |
|:---|:---|:---|
| 全节点 JSON Schema 不可行 | ✅ 共识 | OpenSpec 的 Markdown 格式恰好绕过了这个坑——不需要 JSON Schema |
| 钻石拓扑 fan-out→fan-in | ✅ 共识 | kanban parents 支持树形依赖——够用 |
| DB 级事务长持锁 | ✅ 共识 | SQLite WAL + busy_timeout + 短事务，问题可控 |

### 5.3 风险缓解路线

```
Week 1 先做 P0-2 checkpoint            [1.0h] ← 最低风险，最高价值
         + 管线健康检查                  [0.3h] ← 确认 close.sh 位置
         + Node 升级到 20.19+           [0.2h] ← 消除 OpenSpec 前置条件

Week 2 P0-1 步骤合约引擎                [2.5h]
         + OpenSpec init + pilot spec   [0.5h] ← 验证 OpenSpec→autopilot 链路

Week 3 P0-3 CLI dashboard              [0.5h]
         + autopilot OpenSpec 集成      [0.5h]
         + P1-1 条件路由                [1.2h]

Week 4 P2-1/2 fan-out + 中断           [1.2h]
         + DPL-009 webhook 方案确定     [0.3h]
```

---

## 6. 对 Product 新优先级栈的架构评价

```
P0-1: OpenSpec 引入          ← ✅ 同意。但需要 Node ≥20.19 前置
P0-2: autopilot.sh + state.py ← ⚠️ 建议调整顺序：先 P0-3 checkpoint，再合约引擎
P0-3: 轻量 checkpoint         ← ✅ 同意。建议放在 autopilot 前面做
P1-1: 条件路由                ← ✅ 同意。YAML 方案沿用现有 config_loader 模式
P1-2: 可视化面板              ← ✅ 同意。先 CLI 原型
P1-3: DPL-009 webhook         ← ⚠️ 实测后可能降为 P2（取决于 Hermes webhook 能力）
P2-1: fan-out 并行            ← ✅ 同意
P2-2: DPL-011 P1+P2           ← ✅ 同意
```

**关键修正**：P0-2 和 P0-3 的执行顺序应该交换。Checkpoint 是数据基座——合约引擎的入口校验需要知道「上一步产出了什么」。没有 checkpoint，合约引擎只能做文件存在性检查而非产物溯源。**先做 checkpoint，再做合约引擎。**

---

## 7. 总体评价

### 同意 Product 的核心转向

> 「OpenSpec 直接解决 Frank '不信任管线' 的根源——Markdown 可审查、可验证、可 Git 追踪」

**同意。** R1 我因为平台兼容性拒绝了它，R2 新的技术事实（官方 Hermes 支持）推翻了那个判断。OpenSpec 的 Markdown + CLI 验证组合恰好落在「灵活 vs 严格」的甜点区。

### 同意 Engineer 的工期修正

> 「6.8h → ~9.6h 全栈，含集成调试」

**同意。** 加上 OpenSpec 集成（~1.0h），全栈 ~10.6h ≈ **2 个工作日**。

### 补充：架构健康度检查

我建议在动手写代码之前做一次 5 分钟的「管线健康检查」：

1. `which openspec` 或 `npm list -g @fission-ai/openspec` — 确认 OpenSpec 是否已安装
2. `node --version` — 确认 ≥20.19
3. `find / -name close.sh 2>/dev/null | head -5` — 确认 close.sh 位置
4. `ls /workspace/devPPL/scripts/lib/kanban_helpers.py` — 确认集成点可用

这 5 分钟能避免 5 小时的返工。

### 不做的事（再次确认）

- ❌ 不 fork LangGraph——借鉴模式（checkpoint/interrupt/resume）不引入框架
- ❌ 不修改 Hermes 引擎层——管线在脚本层实现
- ❌ 不引入 Superpowers/gstack——受限于 Claude Code 平台，学 workflow 不引入工具
- ❌ 不支持 DPL-009 全量 webhook 替代 cron——在实测 webhook 不支持 kanban 后，回退到 cron polling + 自定义事件钩子

---

> 我是地基。OpenSpec 的 Node 20.19 依赖是我们需要过的第一道门。过了这道门，接下来的 checkpoint → 合约引擎 → 可视化 的推进顺序是稳固的。先做管线健康检查，不要在「close.sh 到底在哪」这种问题上浪费 5h。
