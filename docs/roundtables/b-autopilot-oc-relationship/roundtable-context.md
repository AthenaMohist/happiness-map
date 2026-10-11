# B 类 Roundtable：OC/autopilot 关系重构方案

## 背景

Frank 裁定的新规则：
> 理想状态是 autopilot 自动走流程并汇报，OC 作为监管，保证 ppl 流程健康。如果流程进行正常，OC 不应做任何多余的事。**OC 不再建卡**，但可以删卡或归档卡。OC 建卡应通过 autopilot 进行。

## 当前 autopilot 能力（实锤）

### ✅ 已有能力（13 项）
1. 任务发现 — 扫描 kanban.db 自动注册未注册任务
2. 状态推进 — 调用 advance_pipeline() 决定下一步
3. 建卡（10 步全链） — dev/qa-d1/qa-exec/qa-d2/va-claim/va-qa/qa-post/va-post/merge/close
4. dev 卡强制 worktree — 仅限 autopilot 自己建的卡
5. fanout 检测 — dev done → 自动启动 qa-d1
6. merge 执行 — git merge + 前后备份
7. close 子流程（7 步） — S6→kanban→GAI→manifest→备份→通知→归档
8. gate_roundtable — MAJOR 缺陷 → D 类 roundtable + block
9. rollback — 回退到指定步骤
10. retry — 超时/失败 → 重建同步骤卡
11. block / await_confirm — 阻塞 + 等待决策
12. dedup_check — 重复卡检测
13. stuck_check — 超时卡检测

### ❌ 确认的缺口（5 项）

| # | 缺口 | 严重性 | 说明 |
|---|------|--------|------|
| 1 | **autopilot 无飞书汇报通道** | 🔴 高 | deliver=local，管线里程碑只能写日志，Frank 看不到 |
| 2 | **autopilot 不能接受"建卡"指令** | 🔴 高 | OC 不建卡了，但 autopilot 没有外部触发建卡的入口 |
| 3 | **workspace_kind 合规扫描缺失** | 🟡 中 | OC 手动建 dir 卡无人拦截 |
| 4 | **管线健康度报告缺失** | 🟡 中 | 无"哪些任务卡住/超时/整体进度"输出 |
| 5 | **手动建卡内容注入缺失** | 🟢 低 | autopilot 建卡自动注入 claim/wiki/超轮次提醒，手动卡无此能力 |

## 确认的事实：autopilot 不依赖 OC session

- autopilot = 独立 cron（每 2 分钟），deliver=local
- gateway = 独立守护进程（PID 3227325），OC session 活不活不影响
- dispatcher = gateway 内部组件，拾取 ready 卡 → spawn worker
- worker = dispatcher spawn 的独立 session
- kanban-notifier = gateway 内部组件，tails task_events → 推送飞书（通过 kanban_notify_subs 表）

**OC 停了后**：autopilot ✅继续跑 | worker ✅继续被 dispatch | worker 完成通知 ✅到飞书 | autopilot 主动汇报 ❌无法到飞书

## 需要讨论的方案方向

1. **autopilot 飞书汇报通道**：如何让管线关键节点（步骤完成/错误/阻塞）自动推送到飞书？
   - 方案 A：autopilot deliver 从 local 改为 feishu
   - 方案 B：autopilot 内部直接调 feishu API 发消息
   - 方案 C：新增独立通知 cron

2. **OC 建卡通道**：OC 不直接建卡，但需要触发建卡——接口怎么设计？
   - 方案 A：OC 写文件到约定路径，autopilot 发现后建卡
   - 方案 B：OC 直接调 `hermes kanban create`，autopilot 自动发现注册
   - 方案 C：autopilot 新增 "manual" 命令接口

3. **workspace_kind 合规扫描**：类似 dedup_check，每轮扫描违规卡 → block + 告警

4. **管线健康度报告**：autopilot 定期输出进度摘要（多少任务在跑/卡住/完成）

## 约束
- 不改 Hermes 本体（放弃后续升级的代价太大）
- autopilot 是 no_agent script cron（无 LLM 调用）
- kanban.db + pipeline_state.db 是唯一的跨 session 状态
