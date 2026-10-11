# PRD: Watchdog 看板监控

> 作者：许清楚（产品） | 日期：2026-07-09 | 版本：v1.0
> 依据：tasks_watchdog/docs/architecture.md v1.0（高见远）

## 1. 监控范围

**看板**：devPPL 全域所有 kanban board（不限定单 board）。

**事件**：kanban_create（新任务）→ 即时推送；kanban_complete → 归零检测；kanban_block → 阻塞通知；SLA 超时 → 告警升级（BLOCKER 4h / MAJOR 24h 未响应，依 P0-14 §8）。

## 2. 告警条件

- BLOCKER 堆积：连续 2 个 tick 存在未解决 BLOCKER → 告警
- SLA 超时：任务超 P0-14 SLA 时限未推进 → 告警
- 无活跃任务：3 tick 后发送"⚪ 全部完成"→ 静默
- 恢复：新任务创建时 touch 信号文件 → 即时唤醒

## 3. 投递渠道

VA Bot DM 统一通知。orchestrator cron 2min 轮询保底 + 事件钩子零延迟推送，双重保障。
