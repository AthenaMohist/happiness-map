# QA-D1 测试方案 — INF-021（DPL-170）chain_review 扫描窗参数化

> 卡: t_33bde193 | 作者: game-qa | 依据: PRD inf021 v1.0 + ARCH M16/M17（D1 裁决）| 独立产出，非追认研发脚本

## 1. 测试对象与范围

- 对象: `scripts/chain_review.py`（S1: parse_cutoff / scan_chains(cutoff) / --day-cutoff+env / scan window 审计行）、`scripts/dpl162_daily.sh`（S2 M17）。
- 范围: PRD AC1-AC5。只跑 `tests/test_chain_review.py` 域内子集（DPL-137）。不改研发代码。
- 参考优先级: PRD 第一（AC 口径）→ ARCH 第二（D1 legacy 裁决、D5 快照锚点语义）。

## 2. 测试矩阵（每条含通过标准）

| # | 用例 | 行为级验证点 | 通过标准 |
|---|------|------------|---------|
| T1 | AC1 边界表（cutoff=23:00） | 独立构造 DB：链在 D-1 23:30 / D 00:00 / D 12:00 / D-1 22:59 完成 | 前 3 条链被扫出，第 4 条不出现；区间语义 = (win_start, win_end] 半开半闭 |
| T2 | AC1 legacy 回退（cutoff=00:00） | 同一 DB 分别以 cutoff=00:00 与 cutoff=None 调 scan_chains | 两者输出完全相等（ARCH D1 构造性回退），且 = 旧自然日语义 |
| T3 | AC2 链成员快照锚点 | 窗口末（D 23:00）后 created_at 的成员卡 | 该卡被剔除出链成员、不追溯破坏已完成链（win_end 锚点） |
| T4 | AC2 fail-open | completed_at=NULL 卡 + 全 NULL 链 | 不崩；NULL 卡不计入 closed；窗内有卡的全 NULL 链不计入 |
| T5 | AC3 CLI 注入 | `--day-cutoff 06:00` 实跑 main | 审计行含 `(cutoff=06:00 BJT)`，退出码 0 |
| T6 | AC3 env 注入 | `CHAIN_REVIEW_DAY_CUTOFF=06:00` | 同 T5；env 优先于缺省 23:00，CLI 优先于 env |
| T7 | AC3 非法值 | `--day-cutoff 25:00` / env `25:00` / `24:00` / `abc` | 退出码 2（配置错误不 fail-open，PRD R1） |
| T8 | AC4 审计行 + 幂等 | 真实 kanban.db 只读 dry-run 连跑两遍 | 输出含 `scan window: 2026-09-25 23:00 -> 2026-09-26 23:00 (cutoff=23:00 BJT)`；两遍 diff 为空 |
| T9 | AC4 legacy 格式 | `--day-cutoff 00:00` dry-run | 含 `(cutoff=00:00 BJT, legacy)`，仍可 grep `scan window:` |
| T10 | AC5 域回归 | `pytest tests/test_chain_review.py -q` | 全绿（研发基线 134 passed；QA 独立复跑为准） |
| T11 | M17 包装器 | dpl162_daily.sh 语法 + 调用方式 | bash -n 通过；裸调用不传参（吃缺省 23:00）；cron 06:30 未动 |
| T12 | M16.5 不改清单（反证） | grep signal_hash/_scan_*/count_pit_occurrences/lessons 标签段 | S1 diff (7429f66) 中零触碰 |

## 3. 分级预期

- 预期 0 BLOCKER / 0 MAJOR。任何 T1-T9 失败 = BLOCKER（功能主路径）；T10-T12 失败按标准 §1.2 判定（回归破坏 → MAJOR 起评）。

## 4. 执行与工作量评估

- 独立行为级探针脚本: `tests/qa_inf021_probe.py`（QA 自有，直接驱动 scan_chains + main，不 import 研发新测试）。
- 预计执行 ≤10 轮 → 不拆执行子卡。
