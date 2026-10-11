# B 类 Roundtable R2：OC/autopilot 关系重构方案 — Frank 裁定 + 新需求

**日期**：2026-08-11
**轮次**：R2（R1 已完成，报告见 `2026-08-11-r1-report.md`）

---

## Frank 的裁定（R1 分歧裁决）

### 补充需求（新方向，最重要）：autopilot = 可接受指令的导航器

> 我希望把 autopilot 打造成可接受指令的导航器。比如发起 b 类 roundtable，我告诉 oc，然后 oc 调用 autopilot 这部分功能来推进。目的就是避免啥事都靠 oc 自己，因为 oc 总是试图打破流程。因此，autopilot 应该**可定制化流程、能接收指令、能叫停**。

含义：
- **指令入口**：OC（或 Frank）能向 autopilot 发指令，如"发起 B 类 roundtable"、"暂停"、"恢复"
- **流程可定制**：流程定义不是写死在脚本里，可配置/可编排
- **能叫停**：autopilot 能终止正在跑的任务/流程
- **目的**：OC 只做监督，不做执行——避免 OC 打破流程

### F1：Gap 4 合并进通知 cron（同意 architect），但更新要求

> 同意合并为同一 cron，但更新一点要求：**每个 tick 应该输出一个 heartbeat 到飞书**，比如"当前 x 卡在跑，x 卡已完成"之类的。

含义：通知 cron 除了例外推送 + 里程碑聚合推送外，**每个 tick（每 2 分钟）还要推一条 heartbeat**——报告当前活跃卡数和已完成卡数。

⚠️ 注意与产品红线"不骚扰"的张力：每 2 分钟一条 heartbeat = 720 条/天，需要讨论 heartbeat 内容设计（简短、信息密度高）和是否有静默窗口。

### F2：能接收指令来规划流程（实现路线不限）

> 我不管是开发新的还是用以有技术路线实现，只要能满足我的需求就行，那就是能接收指令来规划流程。

含义：Gap 2（建卡通道）升级为"指令入口"，实现路线开放——新开发 CLI 接口 / 复用 kanban 卡通道 / 文件 IPC 均可，只要满足需求。

### F3：Gap 3 workspace_kind 合规扫描 = P1 解决

> P1 解决

R1 中 product 说 P2，engineer 说 P1（代码安全红线），Frank 裁定 P1。

---

## R2 待讨论议题

### 议题 A：autopilot 导航器架构（新需求核心）
1. 指令通道设计：OC → autopilot 的指令怎么传？
   - 方案 A：OC 建特殊格式 kanban 卡（如 title 前缀 `[CMD]`），autopilot 扫描识别
   - 方案 B：约定文件目录（OC 写指令 JSON 到 `commands/` 目录，autopilot 读取）
   - 方案 C：autopilot 新增 CLI 命令接口（但 autopilot 是 cron 脚本非守护进程，怎么接收？）
2. 指令类型设计：发起 roundtable / 建卡 / 暂停 / 恢复 / 叫停 / 自定义流程
3. 流程定制：流程定义存哪？怎么表达？（如 JSON 流程定义文件）
4. 叫停机制：autopilot 如何终止正在跑的 worker？（kill 进程？标记卡状态？）

### 议题 B：heartbeat 设计（F1 更新）
1. heartbeat 内容：`当前 x 卡在跑，x 卡已完成`——具体格式？
2. 频率：每 2 分钟一条 vs 有变化才推 vs 静默窗口
3. 与"不骚扰"红线的关系：如何平衡？

### 议题 C：指令-流程编排的技术路线（F2）
1. 新开发 vs 复用 kanban 卡通道 vs 文件 IPC——工程判断
2. 与议题 A 的关系：指令入口就是"导航器"的前端

### 议题 D：遗留分歧裁定后确认
1. notify_state.db vs pipeline_events 表（R1 分歧 1，Frank 未明确裁定，需 R2 收敛）
2. Gap 3 = P1（Frank 已裁定），确认实现方案（workspace_check.sh 同级脚本）

---

## R2 参与角色

product → architect → engineer（串行依赖链，纯架构设计跳过 QA）

## 约束
- 不改 Hermes 本体
- autopilot 是 no_agent script cron（无 LLM 调用）
- kanban.db + pipeline_state.db 是唯一的跨 session 状态
- R1 共识：autopilot.sh 704 行不许再膨胀，新功能走独立脚本挂载模式
- R1 共识：通知 cron 读 pipeline_state.db（结构化），绝不读 autopilot.log
