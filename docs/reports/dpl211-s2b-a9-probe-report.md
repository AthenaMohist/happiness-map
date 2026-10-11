# DPL-211 S2-B R3 上浮报告 — A9 行为级探针 [chain-zombie]

- 卡号: t_3f563622
- Commit: 3747f6a（scripts/probe_a9_chain_zombie.py 实跑验证）
- 上游: S2-A t_fd9675eb（5c4a245，watchdog [chain-zombie] 体检段）；S1 t_86734a4b（7653aab / d23df90 / 61473e2，deep_open_cards 递归终态判定 + D5 祖先豁免）

## 1. 目的与范围

A9 为行为级端到端验证探针，验证 watchdog [chain-zombie] 体检段在接近真实调用路径下能正确发现「僵尸链」（链根 done 但链内仍有活跃深卡），并与既有单元测试（tests/test_chain_zombie_scan.py、tests/test_deep_open_cards.py）互补：单测覆盖函数级语义，探针覆盖 DB → 扫描 → 渲染的整链行为。

不在范围：生产 kanban.db 实测、性能评估、非 chain-zombie 体检项。

## 2. 方法

- fixture DB 构造：探针自建临时 SQLite 库，仅含 `tasks` / `task_links` 两表：
  - 僵尸链 `t_root0001`(done) → mid(done) → `deep0001`(blocked)：根与中间卡均 done，深卡 blocked 仍活跃。
  - 对照干净链：全部 done，无活跃深卡。
- 调用链：`scan_chain_zombies` → 内部经 `deep_open_cards` 递归终态判定 → 结果经 `format_heartbeat` 渲染输出。
- 探针断言：僵尸链产生且仅产生 1 行 chain-zombie 告警；干净链产生 0 行；渲染输出包含 [chain-zombie] 行。

## 3. 实跑证据

- 告警行原文：

  ```
  [chain-zombie] 链 t_root0001 根 done 但活跃深卡 1 张: deep0001(blocked)
  ```

- 渲染路径：format_heartbeat 输出片段含 [chain-zombie] 告警行（僵尸链场景），干净全 done 链 0 行。
- PASS 摘要：探针实跑 PASS（1 告警 + 0 误报 + 渲染含告警行）。
- 回归：`tests/test_chain_zombie_scan.py` + `tests/test_deep_open_cards.py` = **21 passed**。
- Commit: 3747f6a。

## 4. 结论

watchdog [chain-zombie] 体检段行为级验证通过：僵尸链检出、干净链无误报、告警行可经 format_heartbeat 渲染可见。无需额外上浮。

## 5. 观察项 / 需 Frank 裁定边界

1. **format_heartbeat 空链不渲染可视化（既有行为，非缺陷）**：notify_check.py ~L3329 分支在 chains/standalone/done_today 全空时不渲染可视化。chain-zombie 告警行依赖链数据传入，空链场景下告警不出现。是否需要 chain-zombie 告警独立于可视化常显，留给 Frank 裁定。本次探针未改动该逻辑，改为传链列表走完整渲染路径验证。
2. **fixture schema 简化**：探针 fixture 仅含 `tasks` / `task_links` 两表，与真实 kanban.db schema 存在简化；生产库行为由单测 + 渲染接线点保证，探针结论不直接外推到生产库全 schema。

## 6. 上浮判定

无 BLOCKER / MAJOR 发现 → **无需额外上浮**。
