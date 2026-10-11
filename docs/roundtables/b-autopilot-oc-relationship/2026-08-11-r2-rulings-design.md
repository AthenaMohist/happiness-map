# R2 裁定落地设计：heartbeat 工作状态门控 + 类型化建链策略

**日期**：2026-08-11
**来源**：Frank 对 R2 报告 3 个裁定点的裁决（1 修正 heartbeat 语义 / 2 修正建链策略 / 3 批准实施）

---

## 裁定 1：heartbeat 按工作状态门控（work-gated heartbeat）

### Frank 的语义

> 更关心 autopilot 是否有明确的开启和关闭条件。开启状态下 heartbeat 一直提示（让我知道它活着）；任务做完了，应该随 autopilot 自动停止，不需要一直运行。

### 落地设计

**heartbeat 不再是"无条件每 tick 推"，而是"有活干的时候每 tick 推，没活干自动静默"。**

```
每个 tick（notify cron）:
  1. 聚合活跃任务: pipeline_steps WHERE status IN ('pending','running','blocked')
                   + kanban 未归档的 [CMD] 指令卡
  2. 判定工作状态:
     - ACTIVE（存在活跃任务）→ 推 heartbeat（每 tick 1 条）
     - IDLE（无活跃任务）→ 不推 heartbeat（静默）
  3. 状态迁移时发边界消息:
     - IDLE→ACTIVE: 推一条 "autopilot 开工: 活跃N 跑N"（里程碑）
     - ACTIVE→IDLE: 推一条 "autopilot 空闲: 全部任务完成（今日完N）"（里程碑）
```

- **开启条件**：存在活跃任务（pipeline pending/running/blocked 或未消费 [CMD] 卡）
- **关闭条件**：活跃任务清零 → heartbeat 自动停（不再每 tick 推）
- **边界消息保证**：Frank 能区分"静默 = 没事做"和"静默 = 死了"——ACTIVE→IDLE 边界有一条明确的"空闲"消息，之后静默是正常态
- **silent_window 保留但默认关闭**（`heartbeat.silent_window: null`）：Frank 明确"开启状态下希望一直提示"，所以不做时间窗口静默；配置项保留供将来按需开启
- 逃生阀保留：`heartbeat.enabled` 一键总开关

### 与 R2 差异

| 项 | R2 方案 | 裁定后 |
|----|---------|--------|
| 触发条件 | 每 tick 无条件推 | 仅 ACTIVE 状态推（work-gated） |
| 停止条件 | silent_window 时间窗口 | 活跃任务清零自动停 |
| silent_window | 默认开 22:00-08:00 | 默认关（null），Frank 要求一直提示 |
| 边界消息 | 无 | IDLE→ACTIVE / ACTIVE→IDLE 各推一条里程碑 |

---

## 裁定 2：类型化建链策略（chain strategy）

### Frank 的语义

> B 类可以一次建全链；开发类必须先有 PRD，再有架构图，再有代码，这个依赖关系没法打破。请根据不同类型的 roundtable 来定义顺序。

### 落地设计

**发言链（A/B/C roundtable）vs 开发链（D/开发任务）采用不同建卡策略：**

| 类型 | 含义 | 建链策略 | 原因 |
|------|------|---------|------|
| B | brainstorm 头脑风暴 | **all_at_once 一次建全链**（product→architect→engineer，parents 门控保序） | 发言内容无物理产物依赖，parents 依赖自动保证"先听后说" |
| A | vote 表决 | all_at_once（同 B，parents 门控） | 发言类，无物理产物 |
| C | risk_matrix 风险矩阵 | all_at_once（同 B） | 发言类，无物理产物 |
| **D/开发** | 开发任务（PRD→架构→代码） | **sequential 逐棒建卡**（前卡 done 才建后卡） | 物理产物依赖：PRD 是架构输入、架构是代码输入，无法提前建卡（body 无法引用不存在的产物） |

### constants.py 新增定义

```python
# Roundtable 建链策略（Frank 裁定 2026-08-11）
# all_at_once: 一次建全链（parents 门控保序）
# sequential:  逐棒建卡（前卡 done 才建后卡，物理产物依赖）
ROUNDTABLE_CHAIN_STRATEGY = {
    "A": "all_at_once",
    "B": "all_at_once",
    "C": "all_at_once",
    "D": "sequential",
}

# 开发链（sequential）的棒次与产物映射
DEVELOPMENT_CHAIN = [
    {"step": "prd",      "assignee": "game-director",  "produces": "PRD/spec.md"},
    {"step": "arch",     "assignee": "game-architect", "produces": "架构设计/arch.md"},
    {"step": "dev",      "assignee": "game-engine",    "produces": "代码实现"},
]
```

### cmd_channel roundtable handler 路由逻辑

```
[CMD] roundtable B <议题>
  → strategy = all_at_once
  → 一次建 3 张卡: product(t_parent) → architect(parents=[product]) → engineer(parents=[architect])
  → 全部落库后 parent 卡 ready，门控自动逐棒

[CMD] create dev <需求描述>
  → strategy = sequential（D 类）
  → 只建第 1 张: PRD 卡(game-director, body=需求描述)
  → PRD done 后（同一 cmd_channel 或 advance 钩子）再建架构卡，body 注入 PRD 产物路径
  → 架构 done 后再建 dev 卡，body 注入架构产物路径
```

**sequential 的落地方式**：cmd_channel 每 tick 检查"上一棒是否 done + 本棒是否已建"（幂等键 `dev-<spec_hash>-<step>`），前卡 done 才建下一张，body 注入前置产物路径。产物路径从卡的附件/comment 提取（PRD 卡 comment `[PRODUCES] spec.md` 或附件）。

### 与 R2 差异

| 项 | R2 方案 | 裁定后 |
|----|---------|--------|
| 建链策略 | 统一"一次性建全链" | 按类型分：A/B/C all_at_once，D/开发 sequential |
| 开发类 | 未覆盖 | 新增 sequential 逐棒（PRD→架构→代码） |
| 产物注入 | 未覆盖 | sequential 链后棒 body 注入前棒产物路径 |

---

## 裁定 3：批准实施

- 同意 R2 建议 → 按 3 批拆卡实施（通知 cron 6.5h → workspace_check+注入 3h → 指令卡通道 6h）
- 本设计文档为三批任务卡的验收基准之一

## 待拆卡清单（3 批）

| 批次 | 卡 | assignee | 预估 |
|------|-----|---------|------|
| 1 | 通知 cron：notify_state.db + 事件推断 + work-gated heartbeat + 飞书 token 缓存 | game-engine | 6.5h |
| 2a | workspace_check.sh（Gap3） | game-engine | 1.5h |
| 2b | 建卡内容注入 + SOP 文档（Gap2+5） | game-engine | 1.5h |
| 3 | 指令卡通道：cmd_channel.sh + task_control + 排除集 + 类型化建链 | game-engine | 6h |
