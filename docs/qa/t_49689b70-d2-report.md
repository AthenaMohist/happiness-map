# QA-D2 复核报告 — DPL-218 建卡统一入口收口（库口前移）

任务: t_49689b70 | 日期: 2026-10-07 | 执行: game-qa（TL2 抽测复核）

## 1. 复核对象

- 前棒: t_23176338 QA-EXEC 报告 docs/qa/t_23176338-exec-report.md @ wt/t_23176338 (d2741a1)
- dev 产物: ae6aa8c @ wt/t_97a8333f
- D2 范围: 报告逻辑检查 + 随机抽 2-3 条 EXEC 断言独立复跑（test-execution-layering-spec TL2，不跑全量）

## 2. 抽测结果（独立复跑，非采信 EXEC 结论）

### 抽测-1: dev 子集 pytest 复跑 — 与报告一致 ✓

- 环境: 独立只读 worktree（ae6aa8c detached checkout，scratch 目录）
- `pytest tests/test_dpl218_bumps_library_gate.py tests/test_dpl145_f3_f5.py tests/test_dpl145_f6_branch_merge.py tests/test_dpl209_s2_wiring.py -q`
- 实测: **31 passed, 13.53s**，与 EXEC 报告「31 passed, 3.18s」断言一致（通过数一致；耗时差异属环境噪声）。

### 抽测-2: MINOR-1 扫描面泄漏 — 行为级复现确认 ✓

- 方法: 独立构建临时库（含 kanban_assignee_whitelist），直接执行 `_bumps_precheck_scan_sql()`（probe_g6.py）
- 实测:
  - `t_par1234567`（status=running, 无凸点）→ **被扫出**，违反声明的扫描面语义（status IN ('todo','blocked')）
  - `t_mno1234567`（todo, 有未终态 parent）→ **被扫出**，违反「parents 全终态」约束
  - 对照组 `t_abc1234567`（缺凸点 todo + 全终态）正确扫出 ✓
- 结论: EXEC 报告 MINOR-1 现象、根因（`_EST_LINE_SQL` 裸 OR 拼入 AND 链，OR 优先级泄漏扫描面）、定位（card_bumps.py:325 附近）全部复核成立。

### 报告逻辑检查 ✓

- 分级判定符合 qa-finding-classification §1.2（非用户可感知阻断、fail-safe 方向不漏毒卡 → MINOR）
- SLA 对照、判定公式对照齐备；changed_files 段齐备（DPL-060）
- "QA 不改代码、上浮 OC 建 FIX 卡"处置路径正确

## 3. 复核结论

**QA-D2 复核 PASS** — 抽测 2/2 独立复现一致，报告结论（0 BLOCKER / 0 MAJOR / 1 MINOR）维持不变。无新发现。

MINOR-1 建议处置不变: OC 建 FIX 卡（`{_EST_LINE_SQL...}` 包一层括号 + 补扫描面行为级单测）。

## 4. 交付/commit 产物

- 本报告: docs/qa/t_49689b70-d2-report.md @ wt/t_49689b70
- 抽测探针: /root/.hermes/profiles/game-qa/cache/scratch/d218d2/probe_g6.py（repo 外）
- changed_files: ["docs/qa/t_49689b70-d2-report.md"]
