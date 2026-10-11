# 工作量评估 — t_b0ffef61（DPL-169 修补链：FIX_GATE「原链已终态拒修补」误伤 · 方括号坑修复）

评估人: game-engine (寇豆码) | 日期: 2026-09-30 | 执行模式: CC-MAX
输入: PRD dpl169-fixgate-bracket-prd.md + ARCH arch-dpl169-fixgate-bracket.md v1.0（前棒 t_77e3dec3）

## 1. 改动面实勘（已核对本仓 main@46bc109 同构代码）

| 改动 | 位置 | 规模 |
|---|---|---|
| 新建 pipeline/parents_parse.py（parse_parents + parents_exist，ARCH D2 契约照抄） | pipeline/ | ~50 行，零新依赖 |
| 门限 a heredoc（:495-514）改 import 调用 | scripts/cmd_channel.sh | ~15 行替换，语义逐字节等价 |
| FIX_GATE heredoc（:538-550）同调 parse_parents，首 id 语义注释固化 | scripts/cmd_channel.sh | ~10 行替换 |
| G6FIX 五用例子组（G6 组末尾 :3074 后，复用既有桩） | test_cmd_channel.sh | ~80-100 行 |
| pytest 单元直测 2 用例（附带防线，不入门禁） | tests/ 或同构位置 | ~20 行 |
| 两处调用点互指注释（R1 防漂移） | cmd_channel.sh | 2 行 |

## 2. 复杂度 / 风险

- 复杂度: 低。ARCH 已把接口契约、正则、调用点语义、执行路径（sys.path DEVPLP_DIR）全部定死，DEV 照抄。
- 风险点:
  - R2 门限 a 回归 → 用例 2/4 + G6 既有断言兜底（架构已备）
  - R3 sys.path cron 环境 → 既有 T37 先例，跑 G6 子集确认
  - A5 验收升级为 grep 无内联正则残留（结构性保证，省 diff 工作）
- 明确不动: 门限 b/c、classify_chain、close 流程、全量套件不重跑。

## 3. 轮次估算（DPL-136 三项合计口径）

- 实现轮次: parents_parse.py 2 + cmd_channel.sh 两处改造 3 + G6FIX 用例 3 + pytest 直测 1 ≈ 9 轮
- 回归测试轮次: G6+G6FIX 子集（test_cmd_channel.sh 定向执行，估 2-4 轮含调试）
- 收尾链固定预算: +8 轮（merge 后验证 / WIP 笔记 / claim / finalize / 飞书推送）
- 基线合计 ≈ 20 轮；按历史偏差校准 K=2.53 名义上限超出，但本卡与 t_3cb55dfc（同 shape，估 17-22，实际按时完成）同构，偏差主因是多模块/多交付物卡；本卡单模块三文件小改，取 18-24 轮。

## 4. 决策

有效轮次预估 18-24（<30 阈值），交付物 2 个（代码+测试），**不拆卡**。

[SUB-SPLIT] 1 serial
1. DPL-169 方括号坑修复: pipeline/parents_parse.py 抽取 + cmd_channel.sh 门限a/FIX_GATE 改造 + G6FIX 五用例 + pytest 直测，预计 18-24 轮
