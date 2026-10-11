---
created: 2026-10-03
id: t_0b144374-estimate
type: entity
project: "[[entities/devppl.md|devPPL]]"
status: active
updated: 2026-10-03
---

# DEV-EST — DPL-199 巡察使日报三段判断模板 工作量评估（t_0b144374）

> 评估人: game-engine | 口径: 基线轮次 × K(2.53) + 收尾链 +8 + 回归

## 1. 改动面清单（实锚验证）

| # | 改动 | 文件 | 实锚证据（本 worktree 实勘 2026-10-03） |
|---|---|---|---|
| C1 | 五段模板重写为三段判断 + `--legacy-format` | scripts/timeout_ledger.py | `format_daily_report` :408（签名 :409-412 与 ARCH §2.3 一致）；铁律执行率算式 :445-450（`ARCHIVE_SLACK=15` :57）；`_load_fix_cards` :688 |
| C2 | 三判断函数 judge_recurrence / judge_new_pits / judge_disposition | scripts/timeout_ledger.py（新增） | 落位于 format_daily_report 同文件；派修输入源 `_load_fix_cards` :688 已存在可复用 |
| C3 | 新模块 patrol_pit_index.py（build_pit_index + match_pits） | scripts/patrol_pit_index.py（新建，worktree 尚不存在） | 归一化规则源 `timeout_patrol.py:256 normalize_signal`；hash 空间分歧实锚：`timeout_ledger.py:147 _signal_hash` vs `chain_review.py:108 signal_hash`（ARCH A2 成立，必须走降级指纹） |
| C4 | lessons 台账解析（多行 cell 容错） | wiki/actions/lessons-daily.md | 实测 1741 行，`grep -c 待修复` = **909**（P3 数据成立）；表行格式 `|描述|F分类|双链|修复状态|`，无 signal_hash 列（A3 成立） |
| C5 | timeout 台账双源读取 | wiki/actions/timeout-forensics.md + logs/timeout_ledger.csv | wiki 表 18 列含「预防方案生效情况」:20、复发写回规则 :9（A4 成立）；CSV 在本 worktree 不存在（logs 为运行时产物）→ fail-open 路径是**必经**而非边角 |
| C6 | lessons_seen fail-open | logs/lessons_seen.json | `chain_review.py:50 DEFAULT_SEEN_PATH` 实锚；本 worktree 文件不存在，A6 成立 |
| C7 | 派修活性检测输入 | scripts/patrol_fix_agenda.py + logs/patrol_fix_agenda.log / patrol_fix_cards.json | `pending_pits` :10-31，v2 过滤器只认 `[[oc-pitfall-log-` :20、`DAILY_CAP=3` :8/:31（P3 失灵根因实锚）；日志/JSON 本 worktree 不存在（运行时产物，judge_disposition 需容缺） |
| C8 | repeat+done 口径（AC4，零采集改动） | scripts/timeout_patrol.py | scan 产物含 task_status（A7；本卡不动 :256 采集/classify） |
| C9 | 新测试文件 | tests/test_dpl199_report.py（新建） | 现有回归基线实锚：tests/test_dpl158_ledger.py、tests/test_dpl158_patrol.py 均存在 |

改动面结论：1 新模块 + 1 新测试文件 + timeout_ledger.py 单文件改动（不动 timeout_patrol.py / chain_review.py / patrol_fix_agenda.py），纯报告层，与 PRD「定位」一致。

## 2. 复杂度与风险点

- **lessons 多行 cell 解析**（R-高）: 909 行待修复、描述 cell 含 CC-PLAN 散文，降级指纹取首语义段有误配风险；ARCH §1.2 已定口径，<2 源 [待定性] 兜底。解析器是本卡最大不确定量。
- **双 hash 空间**（R-中）: ledger `_signal_hash`(:147) 与 chain_review `signal_hash`(:108) 不可 join，辅键比对须严格走 `_signal_hash(e._error)==csv.signal_hash` 同空间路径。
- **AC8 快照锁**（R-中）: legacy 输出逐字符一致，需先固化改造前快照 fixture，重构时不能碰旧函数文本路径。
- **运行时日志缺失是常态**（R-低）: agenda log / fix_cards.json / CSV / seen 全部可能缺失，fail-open 分支每个源都要单测（AC9）。
- **测试量**（R-中）: 9 个 AC × 多分支（复发/未复发/待定性/矛盾/零事件/legacy），纯函数可测性好，抵消部分量。

## 3. 轮次估算

| 模块 | 基线轮 |
|---|---|
| patrol_pit_index.py（PitRecord + build_pit_index 三源解析 + match_pits + 单测） | 4 |
| 三判断函数 + pending/AC4 路由 + 单测 | 2.5 |
| format_daily_report 重写 + legacy 快照锁 + 零事件日 | 2.5 |
| test_dpl199_report.py AC1-AC9 全分支 + 回归门禁跑绿 | 2 |
| **基线合计** | **11** |

- 校准实现轮 = 11 × 2.53 ≈ **27.8 → 28 轮**
- 收尾链固定 +8 轮
- 回归测试 = 2 × 2.53 ≈ **5 轮**（dpl158 子集 + 新卡子集 + AC8 快照比对）
- **三口径合计 ≈ 41 轮**
- 有效轮 = 迭代预算 × 0.7；41 / 0.7 ≈ 58.6 预算 → 需求预算 ≈ **59 轮 > 42**，**必须拆卡**。

## 4. 拆卡建议：2 serial

1. **卡 1【DEV·DPL-199a】坑指纹索引与判断函数**: 新建 scripts/patrol_pit_index.py（§2.1 接口、降级指纹口径 §1.2、三源 fail-open）+ timeout_ledger.py 三判断函数（§2.2 签名冻结）+ 对应单测（AC2/AC3/AC4/AC5/AC9 纯函数侧）。预计 **16-20 轮**（校准口径：基线 6.5-8 × 2.53）。
2. **卡 2【DEV·DPL-199b】日报文本重写与验收**（依赖卡 1）: format_daily_report 三段重写（§1.1 文本形态冻结）+ `--legacy-format` 快照锁（AC8）+ 零事件日（R4）+ test_dpl199_report.py 集成断言（AC1/AC6/AC7）+ dpl158 回归门禁。预计 **18-22 轮**（基线 7-8.5 × 2.53 + 回归 5）。

两卡合计 34-42 轮，各卡预算 ≤42 有效轮约束内（卡 2 含收尾链 8 轮分摊于上式）。

## 5. 结论摘要

- 改动面 9 项（2 新文件 + 1 文件改 + 6 数据源实锚），全部验证通过，与 ARCH A1-A7 一致；本 worktree 运行时日志缺失进一步坐实 fail-open 为必经路径。
- 总轮次 ≈ 41（实现 28 + 收尾 8 + 回归 5），预算需求 ≈ 59 > 42 → 拆 2 serial 卡。
