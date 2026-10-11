# 工作量评估 — t_3d6ea880（DPL-198 FIX 触发器隔离：autopilot 每 tick 预检）

评估人: game-engine（工程师）| 日期: 2026-10-03 | 执行模式: CC-MAX（实现经 cc-glm 闭环）

## 1. 输入

- PRD: wiki/projects/devppl/prd/dpl198-fix-trigger-isolation-prd.md（v1.0，A1-A6 六条验收）
- ARCH: wiki/projects/devppl/arch/arch-dpl198-fix-trigger-isolation.md（v1.0，OC Q1 裁定 autopilot 预检案，kernel 零改动）
- 前棒 t_9e1dec15 已交付 T-P1~T-P6 测试映射（A1-A6 一一对应）

## 2. 改动面实锚（2026-10-03 实测）

| # | 改动 | 位置 | 状态 |
|---|------|------|------|
| 1 | `precheck_bumps_before_recompute()` + `_bumps_precheck_scan_sql()` + 3 常量 | pipeline/card_bumps.py（新增 ~90 行，与既有安装函数同构 fail-open 骨架） | 未存在，待建 |
| 2 | autopilot.sh 插桩（card_bumps.off 熔断 if 内、DISCOVERED_TASKS 前，L143-154 区间） | scripts/autopilot.sh（+8 行） | 挂点实测存在（触发器安装段 L143-152、L154 DISCOVERED_TASKS） |
| 3 | 新测试脚本 T-P1~T-P6 | tests/test_dpl198_bumps_precheck.sh（新建 ~220 行，照 test_dpl198_bumps_upgrade.sh 隔离建库套路） | 未存在，待建 |

### 代码级核验点（照写无需猜测）

- 内核跳过挂点: `_has_sticky_block` kanban_db.py:2070-2095 → recompute_ready :2151-2153 sticky 分支先于 counter 检查，实测确认。
- recompute_ready 单 write_txn 循环无 per-row 隔离: :2143-2187 实测确认（毒化核因与 PRD F1 一致）。
- blocked 卡必须补 kind='blocked' 事件（仅改 status 不够）——ARCH §1 补充约束实测成立。
- 扫描 SQL 需 `_bumps_title_exemptions_sql().replace('NEW.','t.')`——豁免 SQL 是触发器内 NEW. 语法，复用须替换前缀（实现时注意点）。
- 事件 payload 镜像 block_task 形态 + source='card-bumps-precheck'（供巡察使区分人/机制 block）。
- 自愈: 补行后 OC kanban_unblock → unblock_task :3330-3374 landing，旧告警不阻塞——A3 闭环无需额外代码。

## 3. 工作量

| 项 | 预计轮次 |
|----|---------|
| 实现（card_bumps.py 函数 + autopilot 插桩） | 8-12 |
| 测试脚本 T-P1~T-P6（bash 隔离 DB，套既有模板） | 4-6 |
| 收尾链固定预算（merge 后验证/WIP 笔记/claim/finalize 四步/飞书） | +8 |
| 回归子集（test_card_bumps.sh + test_dpl198_bumps_upgrade.sh，bash 快测） | 2-4 |
| **总轮次** | **~22-30（中值 26）** |

复杂度: 中。风险点: ① 豁免 SQL NEW.→t. 替换后语义漂移（有 T-P4 用例兜底）；② 事件 payload 形态与 kernel 判定不一致导致 sticky 不生效（T-P1/T-P5 断言兜底）；③ 残余窗口（预检后同 tick 新建坏卡）为 ARCH §2.4 明示不封死项，非实现风险。

## 4. 拆卡决策

总轮次中值 ~26 < 42 拆卡阈值（按 DPL-136 三项合计口径）；改动面单文件函数 + 插桩 + 一个测试脚本，无多交付物；**不拆**。

[SUB-SPLIT] 1 serial
1. DPL-198 FIX 实现 precheck_bumps_before_recompute（card_bumps.py + autopilot.sh 插桩）+ 测试 T-P1~T-P6 + 回归子集 预计 22-30 轮
