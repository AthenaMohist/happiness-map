# 工作量评估 — t_4a9c5fa8（DPL-169 watchdog IDLE done-today 后门）

评估人: game-engine (寇豆码) @ t_est_4a9c5fa8 · 2026-09-30

## 1. 源需求实勘

- 后门位置确认: `scripts/notify_check.py:3859-3878`
  - `active=False and hb_enabled` 时读当天完成链/独立卡
  - sleep 态 → 走 `done_digest_sent_at` 水位，日结一次（t_40f0697a F1 已封）
  - **IDLE 态（else 分支 L3877-3878）→ 无条件 `done_today_visual=True`，无任何冷却** → 每 2min tick 重推 ✅✅ 摘要，铁证与 OC 实勘一致
- 发送侧 L3895-3921: `done_today_visual` 时复用 dt_chains 渲染并发飞书；sleep 有水位推进，IDLE 无
- 现有测试: tests/ 下 notify 相关用例（含 t_40f0697a F1 回归）已覆盖 sleep 分支

## 2. 两个方案的工作量

### 方案 A（最小改，对齐 F1）
IDLE 态也走 `done_digest_sent_at` 日结一次水位（复用 kv 键，删除 else 直通分支）。
- 改动: notify_check.py ~10 行（else 分支加水位判断 + 发送后推进）
- 测试: 新增 2 个用例（IDLE 首推 1 条 / 同 tick 重推被水位拦）+ 回归现有 notify 子集
- 预计 8-12 轮

### 方案 B（源卡推荐，Frank 已批模板）
`active=False` 时 heartbeat 完全不走 done_today 分支；今完摘要归 23:30 巡察使日报①段
（timeout_ledger.py 五段模板已由 t_97265638 落地，有现成渲染函数可复用）。
- 改动:
  - notify_check.py: 删 IDLE done-today 分支（L3877-3878 + L3895 条件收窄 + L3919-3921 日志）~15 行
  - timeout_ledger.py: 日报①段接入「今完 m 链 n 卡」聚合（复用 done_today_chain_entries）~20 行
  - 保留 sleep 日结一次语义（F1 不回归）
- 测试: T1 无活跃+今有完成 → 0 条 heartbeat；T2 有活跃照常；T3 sleep 不回归；T4 造 05:26 形态用例必须 0 推；T5 现有 notify 子集全绿；日报①段断言
- 预计 14-20 轮

## 3. 复杂度 / 风险

- 复杂度: 低-中。单文件为主（方案 B 跨两个文件），逻辑是布尔门 + 水位键复用，无 schema 变更
- 风险点:
  1. `done_digest_sent_at` 若 A/B 两态混用需明确语义（B 方案 IDLE 不再推则该键仅剩 sleep 语义，最干净）
  2. 23:30 日报若当天 tick 缺失会漏日结（B 方案需在日报段兜底读当天完成，不依赖 heartbeat 水位）
  3. 现有 sleep F1 回归用例必须保持绿（T3）

## 4. 决策

- 预计轮数（取方案 B 目标态）: raw ≈ 15 轮，× K=1.3 ≈ 18-20 轮，**≤20 → 不拆**
- [SUB-SPLIT] 1 serial — 源卡 t_4a9c5fa8 直接跑，按方案 B 实现
- 建议实现卡 body 附带: 上述风险点 2 的兜底要求 + T1-T5 验收清单
