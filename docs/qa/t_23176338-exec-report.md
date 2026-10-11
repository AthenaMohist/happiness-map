# QA-EXEC 验收报告 — DPL-218 建卡统一入口收口（库口前移）

任务: t_23176338 | 执行模式: CC-MAX | 日期: 2026-10-07 | 执行: game-qa

## 1. 验收对象

- dev 产物: commit ae6aa8c @ wt/t_97a8333f（只读 checkout 验收，未改动 dev worktree）
- 上游: D1 报告 docs/qa/t_d116f33a-d1-report.md（19 条探针清单）

## 2. 验收执行结果（行为级，独立复跑）

### dev 子集复跑（DPL-137 分层）

- `pytest tests/test_dpl218_bumps_library_gate.py tests/test_dpl145_f3_f5.py tests/test_dpl145_f6_branch_merge.py tests/test_dpl209_s2_wiring.py -q` @ ae6aa8c: **31 passed, 3.18s**，与 dev claim 一致，0 failed 0 error。

### 红探针（旧版桩触发器 WHEN 仅 ready，独立脚本复现）— 3/3 确认旧逻辑缺陷

- R-todo / R-running / R-blocked: 旧库毒卡全部畅通入库 ✓红（探针脚本 cache/scratch/qa218_red_probe.py）

### 绿探针（新逻辑 ae6aa8c，独立装触发器 + INSERT 实测）— 10/10 通过

- G-1~G-4: todo/running/blocked/ready 缺凸点 INSERT → 全部 IntegrityError ABORT ✓
- 终态 done 放行 ✓；三凸点齐备 todo 放行（对照组）✓
- G-5: ABORT 文案含 DPL-218 / [card-bumps-missing] / oc_create_card 指路 ✓
- G-7: 畸形 est id（t_est_x）三凸点齐备正常入库且不派生 est 子卡 ✓
- G-8: 机制自建卡（[DEV-EST] + discover-est-* 幂等前缀 + ready）双豁免不拦截 ✓
- 探针脚本: cache/scratch/qa218_exec_probe_v3.py

### G-6 预检扫描（直接执行 _bumps_precheck_scan_sql 对临时库）

- 缺凸点 todo/blocked 历史卡被扫出 ✓；带凸点卡不误报 ✓

## 3. QA 发现分级（qa-finding-classification §1.2 五步判定）

- **MINOR-1: _bumps_precheck_scan_sql 扫描面泄漏（D3 谓词同源化遗留括号缺失）**
  - 现象: `_EST_LINE_SQL` 展开为 `instr(...) = 0 OR instr(...) = 0` 裸 OR，拼入 AND 链后 OR 优先级低于 AND → 扫描面泄漏。实测（cache/scratch/qa218_exec_probe_g6.py）：status='running' 的 t_par1234567、有未终态 parent 的 t_mno1234567 均被扫出，违反代码注释声明的扫描面语义（status IN ('todo','blocked') + parents 全终态）。
  - 判定: 非用户可感知阻断（预检是 autopilot 告警面，方向 fail-safe——过宽不会漏毒卡，门禁 INSERT/升舱触发器不受影响）；无 workaround 需求；不阻塞发版 → **MINOR**。
  - 注: dev 单测 test_precheck_scan_sql_three_checks_and_scan_scope 只做静态子串断言（`_EST_LINE_SQL.format(e="t.body") in sql`），未对扫描面做行为级断言，故漏网。此为测试设计缺口而非断言错误。
  - 建议处置: 上浮 OC 建 FIX 卡（card_bumps.py:325 将 `{_EST_LINE_SQL...}` 包一层括号即可），并补扫描面行为级单测。**QA 不改代码**。
- **BLOCKER: 0 | MAJOR: 0 | MINOR: 1 | SUGGESTION: 0**
- SLA 对照: MINOR 无 SLA 义务。判定公式对照: 用户不可感知且不阻断功能 → 不构成 MAJOR/BLOCKER。

## 4. 结论

**QA-EXEC 验收 PASS（附 1 MINOR）** — DPL-218 库口前移六刀（D1-D7）行为级验证通过：毒卡四活跃态入库即拒、终态放行、机制自建卡零误伤、est 畸形 id fail-safe、安装链零改动确认。1 MINOR（预检扫描面泄漏）不阻塞发版，建议随下轮修复。

## 5. 交付/commit 产物

- 本报告: docs/qa/t_23176338-exec-report.md @ wt/t_23176338
- 探针留痕: 见 /root/.hermes/profiles/game-qa/cache/scratch/qa218_exec_probe_v3.py、qa218_exec_probe_g6.py、qa218_red_probe.py（repo 外）
- changed_files: ["docs/qa/t_23176338-exec-report.md"]
