# 占位 blocked 规约（wip-placeholder）

> 来源: DPL-198 R3（t_f2b27e9c）| 状态: 生效 | 日期: 2026-10-05
>
> 面向: 所有领卡 worker（QA/VA/DEV 全角色）。

## 规约（一行版）

领卡并发占位置 blocked 时必须同时带 `block_kind='wip-placeholder'`；语义阻塞一律走 kanban_block（带真实 kind），禁止用占位 blocked 表达真阻塞；占位不落 task_events。

## 说明

- **占位 blocked**（防双领的瞬态标记）与**语义 blocked** 共用 `status='blocked'`，
  唯一区分是 `block_kind`：占位 = `wip-placeholder`；语义 = 走 `kanban_block`
  通道的 4 合法 kind（dependency / needs_input / capability / transient）。
- **占位不落 task_events**：无事件 → `_has_sticky_block` 不成立 →
  recompute_ready 可正常 promote，占位语义才正确（落事件会造出 sticky 占位）。
- **超时兜底**: card-audit 对 `wip-placeholder` 卡检查最近动态，
  超 2h（`placeholder_stale_h`，config/card_audit.yaml 可调）无动态 →
  产出 `[card-audit:PLACEHOLDER-STALE]` 真告警，真僵尸不隐身。
- **防御性副闸**: 无 kind 的近窗 blocked 卡会被 card-audit 自动 heal 补
  `wip-placeholder`（BLOCKED-NO-KIND 规则，action=auto-heal），
  但 worker 不应依赖该兜底——写路径直接带 kind。
