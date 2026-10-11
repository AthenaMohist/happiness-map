# 估算报告 — DPL-200 典型坑收录扫坑口径扩充（DEV-EST t_1398bd74）

> 评估人: game-engine（寇豆码）| 日期: 2026-10-03 | 依据: PRD v1.0（t_1b5b77cc）+ ARCH v1.0（t_e1e8100e, mem-core e0c4207）

## 1. 改动面实锚（全部读过源码确认）

| 项 | 锚点 | 状态 |
|---|---|---|
| A1 坑行 | wiki/actions/lessons-daily.md:1742（含 [[pits/issuer-verifier-same-source-self-cert-loop]] 双链 + dpl200sameloop 标记） | 人工回写已完成，DEV 复核 signal_hash 兼容 |
| A2 详情页 | wiki/pits/issuer-verifier-same-source-self-cert-loop.md（56 行） | 已交付，复核双链可解析 |
| A3 S1/S2 | chain_review.py:74 `_COMMENT_PATTERNS` +2 行；:60 PIT_CAUSE 两键 → F6:编号 | 待实现 |
| A3 S3 | chain_review.py:55 CHAIN_CODE_RE + 新纯函数 find_dup_numbers；void 经 `python3 -m memcore.registry_gate state`（禁本地正则）；TST- 豁免；开关 DUP_REPORT_DOWNGRADED=False | 待实现 |
| A3 F6 | mechanisms/F6 label 页（pit_type_label 模板既有, chain_review.py:520；taxonomy :1023） | 待建 |
| A4 | scripts/registry_prose_drift.py（新建 ~60 行，只读，exit 0/1 语义） | 待实现 |
| A6 | tests/test_chain_review.py（现 1736 行）TC1-4 + 新 test_registry_prose_drift.py 3 例 | 待实现 |
| 明确不动 | timeout_patrol.classify_cause 级联（ARCH §1.4 冻结）；seq.py/registry_gate.py/gate_code_4q.sh/机读块格式 | — |

## 2. 轮次估算（三口径合计，DPL-136）

| 口径 | 轮次 |
|---|---|
| 实现（A3 复用层 ~2 + S3 ~4 + A4 脚本 ~3 + F6 页/文档 ~2 + 测试 7 例先红后绿 ~5） | ~16 |
| 收尾链固定预算（merge 后验证/WIP/claim/finalize/飞书） | +8 |
| 回归（pytest -k "chain_review or prose_drift" 子集，~60-75s/遍 × 3 遍 ≈） | +4 |
| **合计（预算口径）** | **~28 轮** |
| 历史校准 K=2.53 后有效轮参考 | 基线 ~11 × K ≈ 28（与上自洽） |

## 3. 拆卡裁决

- 预算口径 ~28 轮 < 42（拆卡阈值），ARCH §5 亦明示「单卡可承载，无需拆分」。
- 交付物单链（同一文件族 chain_review.py + 1 新脚本 + 测试），无并行收益。
- **裁决: [SUB-SPLIT] 1 serial，不拆。**

风险点（不阻塞）：
1. 撞号降级（R3）Frank 未追认 → 开关常量 False 保原口径，追认后一行翻转。
2. lessons L1742 坑行无 signal_hash 注入（人工回写）→ chain_review 增量去重需验证不重复追加（A1 验收点，列入测试）。
