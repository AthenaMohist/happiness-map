# QA-D1 测试报告 — DPL-158 巡察使（t_3a27734f）

- 日期: 2026-09-11 | QA: game-qa（独立测试方案，未参考 dev 单测断言）
- 真源: wiki/projects/devppl/prd/dpl158-timeout-patrol-prd.md（v1.1）
- 被测: scripts/timeout_patrol.py + scripts/timeout_ledger.py（分支 wt/t_3a27734f，commits 03bc349 基线 + 5d709b4 QA 期间修复）
- 依据: docs/standards/qa-finding-classification.md §1.2 判定公式

## 1. 执行方式

- QA 行为级测试脚本（自建，22 用例）: tests/test_qa_dpl158_patrol.py + tests/test_qa_dpl158_ledger.py
- 独立复跑: `pytest tests/test_qa_dpl158_{patrol,ledger}.py tests/test_dpl158_{patrol,ledger}.py -q` → **57 passed**（commit 79a47ce 时点，本会话亲自复跑验证）
- 真实执行证据（临时构造 kanban.db，非 dev fixture）:
  - `timeout_patrol.py --db <tmp> --dry-run`: timed_out 10 / zombie 1 / repeat 3，t_a cp_round=52 rounds=58、t_b rounds=55（error 提取）、gate 决策 dry-run/skip-done/skip-blocked 三态正确；EXIT=0；DB sha256 扫描前后一致（只读红线 AC8）
  - `--db /nonexistent`: EXIT=1，无 Traceback
  - `timeout_ledger.py --dry-run`: 日报文本含四类计数、F 分类、Top 反复卡、存档铁律执行率；不真推
  - `timeout_ledger.py`（真实写回 wiki）: 台账页生成、发生列追加时间戳、F2 复发标「失效+09-11」、F5:循环型标「生效」

## 2. AC 对照

| AC | 结果 | 证据 |
|---|---|---|
| AC1 日报四类计数+F 分类+Top+铁律率 | PASS（真推通道未验，mock/dry-run 覆盖） | 真跑日报文本 |
| AC2 wiki 表动态列 + CSV 一 run 一行 | PASS（列名编号缺陷见 F-D1-2） | 真跑 + 单测 |
| AC3 预防方案生效情况回填 | PASS | 失效/生效双样例 |
| AC4 ≥3 次 block / done 不 block | PASS | gate 三态 + QA-4 |
| AC5 F1-F5 分类样例 + 空 error 兜底 | PASS | QA-5 |
| AC6 metadata.rounds_used 提取 | PASS | QA-1 |
| AC7 cp_round/timeout_round 双值 | PASS | QA-1 + 真跑 cp_round=52 |
| AC8 只读 + fail-open | PASS | sha256 + exit 语义 |

## 3. QA 发现（按标准 §1.2 判定）

### F-D1-1 [已修复/验证] update_wiki_table 覆盖固定列 — MAJOR（发版前已修）
- 现象: 3 列起步模板首轮真实写回时，发生组从第 0 列起，覆盖「超时原因/预防方案生效情况/说明」列（生产 main() 必触发）。
- 判定: 用户可感知（台账数据错乱）AND 功能阻断（首轮回写即坏）AND 修复前无 workaround → 符合 MAJOR（未到 BLOCKER：写回前有模板可重建，不丢人填数据之外的源数据）。
- 处置: QA 执行期间由 cc 修复（commit 5d709b4，无发生组时从 len(header) 起追加），复跑 57/57 绿 + 真跑复核写回正确。

### F-D1-2 列名「发生N/修复N」跨原因重复编号 — MINOR
- 现象: 多个 cause 各自从 发生1 起编号，同一表头出现 3 个「发生1」（真跑实测 36 列，重复标签集 {发生1×3, 修复1×3, 发生2×2...}）。
- 判定: 用户可感知（阅读歧义）AND 不阻断（列组语义仍可按行读）→ MINOR。FRD D2「行键+动态列」形态成立，但同表列名不唯一违反表语义唯一性直觉。
- 建议: 列名加 cause 前缀（如 F2-发生1）或全局递增编号。

### F-D1-3 cause 不在 CAUSE_KEYS 时产生重复碎行 — MAJOR
- 现象: entry cause 值若非模板 6 行键之一（如裸 'F5'），update_wiki_table 找不到行 → 重建时追加一行 cells 只补到 c2（3 列），造成 `| F5:未分类 |  |  |` 碎行（真跑产物第 22 行实锤）；且 parse 按首个匹配行取 occur_max，二轮写回会写错行。M3 独立复现: 注入 cause='F5' → 输出第 7 行 cols=3。
- 判定: 用户可感知 AND 功能受损（台账行错乱、GAI 双链可读性破坏）AND 有 workaround（人工整理）→ MAJOR（触发条件: 分类器返回值域与模板键集漂移；当前 classify_cause 返回域恰在键集内，故非当日必现，属防御缺失）。
- 建议: 写回前 cause 归一化（不在 CAUSE_KEYS → 'F5:未分类'）或新增行时按模板全列补齐。

### F-D1-4 重复 F5:未分类 行无合并机制 — MINOR（与 F-D1-3 同根，独立列记）
- 现象: 真跑产物中出现两个「F5:未分类」数据行，其中一行 3 列碎行。
- 判定: 不阻断、可人工清理 → MINOR。修复 F-D1-3 后不再产生新碎行，但历史碎行合并逻辑仍缺。

### 观察（不计发现）
- M1 疑点（二轮写回列号错位）经探针验证**不成立**: occur_max 迭代 1→2 正常，列名重复是 F-D1-2 的表现非迭代缺陷。
- 真推飞书通道（AC1 完整态）与 cron 宿主挂载未在本卡范围（部署属 OC）；日报文本/去重/dry-run 已行为级覆盖。

## 4. SLA 与流程对照
- BLOCKER 0 / MAJOR 1（F-D1-3，另 1 项 MAJOR 已在发版前修复闭环）/ MINOR 2。MAJOR 按标准 §8 需研发评估响应；两项 MINOR 不阻塞。
- F-D1-1 修复已经独立复跑 + 真跑双重回归验证，闭环。

## 5. 结论
可交付（附条件）: 0 BLOCKER；建议 F-D1-3 在日报 cron 挂载上线前修复（防分类域漂移时台账损坏），F-D1-2/F-D1-4 可随后续迭代。
