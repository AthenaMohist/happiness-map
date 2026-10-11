# 工作量评估 — t_d202f9a3（WIKI_POINTER_BODY_LINE 卡 body 注入知识锚点行）

评估卡: t_est_d202f9a3 · 评估人: game-engine · 2026-09-06

## 1. 需求摘要

pipeline 建卡时在卡 body 注入一行固定「知识锚点」，告诉 worker：建卡规范/编号选码/
备份方法/链归属拿不准时先查 mem-core wiki（kanban-card-format.md /
project-codes-backup.md）或 `memctl query`，不确定写卡 comment 上浮 OC，禁凭印象造。
解决「规范都在 wiki、派发上下文零链接」的最后一公里。

## 2. 改动清单（已实地核对注入点）

| # | 文件 | 改动 | 复杂度 |
|---|------|------|--------|
| 1 | pipeline/constants.py | 新增 `WIKI_POINTER_BODY_LINE` 常量（一行文案，需求已给出全文） | 极低 |
| 2 | pipeline/cmd_chain.py `_dev_card_body`（~L955-960 尾部注入块） | 在 `TEST_GATE_BODY_LINE` 之前 append 锚点行 | 低 |
| 3 | pipeline/cmd_chain.py 子卡 body 组装（~L1170-1174） | 同上，位置在 TEST_GATE 之前 | 低 |
| 4 | pipeline/discover.py `_create_est_card` est_body（~L270-272） | 同上（est 卡 body 组装，CHECKPOINT 行之后） | 低 |
| 5 | tests/（对齐 T59e 风格） | ① constants 存在性/内容断言 ② 三处组装函数产出的 body 含 `[知识锚点]` 且位于 TEST_GATE 行之前 | 低 |

关键约束：
- 位置红线：锚点行必须在 `TEST_GATE_BODY_LINE` 之前（需求明示）。
- 增量-only：不改任何既有行，纯 append；存量卡不回填（天然满足）。
- 凡建卡路径都带上：cmd_chain 两处 + discover est block 三处全覆盖。

## 3. 风险点

- **低风险**：纯文案注入，无逻辑分支、无 schema 改动、无 DB 写路径变化。
- T59e 既有断言多数检查「行存在」，少数可能断言 body 尾部行序（WIP 末行）——
  锚点插在 TEST_GATE 前不动 WIP 末行，预计零回归；若有行序敏感断言需微调测试。
- discover.py 的 SQL trigger 路径（L410-432 内联 SQL 建 est 卡 body）与 Python 路径
  是双实现——锚点行如只在 Python 路径注入，trigger 路径建出的卡会缺失。验收
  「凡建卡路径都带上」要求两处都注入（trigger 的 SQL 文本里 append 常量即可）。

## 4. 工作量结论

- 预计轮数：**10-16 轮（中位 13）**；有效轮数 ×0.7 ≈ 9-11
- 复杂度：低（常量 + 4 处注入 + 2-3 个测试断言）
- 风险：低

## 5. 拆分决策

总轮数 ≤20 → **不拆**。
