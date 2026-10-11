# EST — DPL-178 watchdog 僵尸误判竞态修复（t_b42ad0de）

> 评估人: game-engine | 日期: 2026-09-29 | 执行模式: CC-MAX
> 输入: PRD v1.0（t_bff0cf40）+ ARCH v1.0（t_38428931，mem-core main 3630c1c）

## 1. 锚点实勘（devPPL main 3fd46db，实测）

| 锚点 | ARCH 假设 | 实测 | 结论 |
|---|---|---|---|
| notify_check.py 常量区 DISPATCH_RETRY_GRACE_MIN/CARD_AGE_GRACE_MIN | L479-480 | ✓ 在位 | 零漂移 |
| read_zombie_running_cards 签名 hb_threshold_min=30 | L516 | ✓ | 零漂移 |
| run 查询已 SELECT started_at | L541 | ✓ | M1① 零新增列 |
| hb-None 分支无豁免直判僵尸 | L585-587 | ✓ `hb is None → out.append` | 根因①确认 |
| run-None 分支豁免锚点=卡龄 | L551-583 | ✓ | 根因②确认 |
| block_zombie_running_cards 写侧无二次确认 | L606+ | ✓ UPDATE 前无重查 | M2 待加 |
| 既有回归 T113/T114/T115/T116 | test_notify_check.py | ✓ L4318/4379/4453/4506 | 基线在位 |

生产 schema（ARCH 已实测）: tasks.started_at 可空 ✓ / task_runs.started_at NOT NULL ✓——本仓内核未动，直接采信。

## 2. 工作量评估

| 项 | 内容 | 轮次 |
|---|---|---|
| M1 | 常量区 +2（HB_NONE_GRACE_SEC/CLAIM_GRACE_SEC=300）+ hb-None 分支改写 + run-None 分支追加 claim 锚点豁免（ARCH 已给逐行伪代码） | 3-4 |
| M2 | block 写侧 UPDATE 前二次确认（~10 行） | 1-2 |
| T178 | 9 个用例（T178-1~9），~180 行，仿 T113/T114 夹具写法 | 4-6 |
| 门禁 | py_compile + T113/T114/T115/T178* 子集（脚本自跑，单次 <2min）+ 修失败 | 2-3 |
| 实现小计 | | **10-15** |
| 收尾链 | merge 后验证/WIP 笔记/claim 文件/finalize 四步/飞书推送（DPL-136 固定 +8） | 8 |
| 回归 | 子集复跑 + 抽查 | 2-3 |
| **总计** | | **20-26 轮** |

校准说明：历史偏差 K=2.53 全部来自 timed_out=60 的截断值，不反映本卡体量（ARCH 给的是逐行伪代码级规格，翻译成本极低）；且同类先例 t_88bdf002（同体量 DPL-173 EST）实测总估 22-27 轮合理。按口径三项合计取 20-26 轮。

## 3. 拆卡决策

**N=1，不拆卡（serial）**。理由：
- 单文件（notify_check.py + test_notify_check.py）单改动面，无并行切分点
- 总有效估 ~14-18 轮（20-26 × 0.7）< 30 轮拆卡线
- 先例一致（t_88bdf002 N=1 不拆）
- 风险点：唯一风险是 T178-6（写侧二次确认夹具构造 run 竞态状态）可能多花 2-3 轮调试，仍在单卡容量内

## 4. 风险点

- R1: T178-6 需在 block 前手工改 task_runs 状态模拟「复活」，夹具要绕开 block 内部事务——中风险，预留调试轮次
- R2: fail-open 用例 T178-9（缺 started_at 列）需要临时 drop column 的 sqlite 夹具——低风险（T113 夹具已有建库基建）
- R3: 测试脚本非 pytest（自跑 main 函数），子集过滤用函数名单调用而非 -k
