# 评估报告 — [FIX] 测试 sys.path 硬编码污染根治 — 全量 pytest 恢复为可用验收门禁（DPL-057）

> 评估人：寇豆码（game-engine） | 日期：2026-08-15 | 评估卡：t_est_f8d25717
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：t_f8d25717（[FIX] 测试 sys.path 硬编码污染根治 — 全量 pytest 恢复为可用验收门禁，DPL-057）
> 来源：DPL-056 SUB-3（t_49ce4679）超时根因根治，OC 2026-08-15 建卡
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**不拆（[SUB-SPLIT] 1），单卡可完成，预计 6-12 轮 ≤ 20 轮阈值。**

本卡**代码修复已完成并进 main**（OC 直接处置：12eb90a 改名 + cee5d6b 5 文件 `__file__` 相对化 + 9daa839 merge），
待办只剩三类收尾工作，全部是**文档 + 验证**性质，零新代码：

1. **规范落文档**：把「测试禁止硬编码绝对路径、必须 `__file__` 相对；脚本式测试（模块级 exit）禁止 `test_` 前缀」写成正式标准
2. **扫描确认**：两条 grep 命令验证 0 残留（本次评估已实测通过）
3. **全量 pytest 验收门禁**：完整跑一遍确认无 INTERNALERROR、无新增回归（本次评估实测收集 290 tests 正常）

无设计决策、无新代码、无新测试编写——本质是「写一份规范 + 跑一遍验证」的轻量收尾卡。

## 2. 工作量评估（读码结论 + 本次实测，非假设）

### 2.1 现状基线（评估期间实测）

| 检查项 | 命令 | 实测结果 |
|--------|------|---------|
| 硬编码绝对路径残留 | `grep -rn 'sys.path.insert(0, "/workspace/devPPL")' tests/` | **0 残留**（exit=1 无匹配）✅ |
| 模块级 exit 的 test_ 文件 | `grep -rn '^exit(' tests/ --include='test_*.py'` | **0 残留** ✅ |
| 全量 sys.path.insert 现状 | `grep -rn 'sys.path.insert' tests/` | 14 处，全部为 `__file__` 相对 / `_REPO_ROOT`(基于 __file__) / `Path(__file__).resolve().parent` 等 worktree-portable 形式 ✅ |
| pytest 收集门禁 | `python3 -m pytest tests/ --collect-only -q` | **290 tests collected in 0.20s，无 INTERNALERROR** ✅（验收 3 前置已恢复）|
| 全量 pytest 基线 | OC 记录（main，599s） | 275 passed / 14 failed / 1 error（14 failed 均为存量，与 DPL-056 无关）|

**结论：验收 2 已达成（两条扫描 0 残留）；验收 3 的收集门禁已恢复（290 collected 无 INTERNALERROR），完整跑一遍仅剩确认动作。**

### 2.2 改动清单（逐项轮数）

| # | 项 | 内容 | 预估轮数 |
|---|----|------|:---:|
| ① | 规范落文档 | 新建 devPPL 测试规范标准文档（见 §3 R1 落位建议）：测试禁止硬编码绝对路径 → 必须 `__file__` 相对（附 worktree-portable 范例）；脚本式测试（模块级执行 + exit）禁止 `test_` 前缀命名（pytest 收集守卫），附正反例 + 扫描命令。参照 docs/standards/qa-finding-classification.md 的既有标准格式 | 2-4 |
| ② | 扫描确认 | 复跑两条 grep 命令 + sys.path.insert 全量审视，把结果写进 claim | 1 |
| ③ | 全量 pytest | `python3 -m pytest tests/ -q` 完整跑（~10 min 等待）+ 对照 275/14 基线确认无新增回归 | 2-3 |
| ④ | 收尾 | [PRODUCES]/[CLAIM] comment + 飞书推送（send_claim_feishu.py）+ complete | 1-2 |

**预计总轮数（基准）：6-12 轮（中位 9）。**

### 2.3 DPL-018 校准

- 本卡为**文档 + 验证收尾型**（非功能开发型）：无新代码、无设计决策、无测试编写。
  参照同型先例 t_est_1ecadb5f（集成/落地型 K=1.0）与 t_est_0f418cf6 S1 半（纯落地 6-10 轮轻卡），
  校准系数取 **K=1.0**（基准即校准；唯一不确定点是文档落位，见 R1，属小决策不放大轮数量级）。
- **校准后：6-12 轮 ≤ 20 轮阈值 → 不拆（[SUB-SPLIT] 1）。**

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **规范文档落位（唯一决策点）** | 低 | 源卡写「`wiki/concepts/patterns/` 或 devPPL 测试规范」，但 **repo 现无 wiki/ 目录**（本次实测 find 无结果）。devPPL 既有标准全在 `docs/standards/`（qa-finding-classification.md 是唯一标准文档）。建议落位 `docs/standards/devppl-test-spec.md`（或 test-path-hygiene.md），沿用 .hermes.md「核心标准文档」引用模式；若坚持 wiki 结构需先建目录，+1 轮。**评估建议：docs/standards/，理由是与现有标准文档同构、QA/研发都能在 docs 下找到，且 docs 有 lint 惯例** |
| R2 全量 pytest 存量失败 | 低 | 基线 275/14/1 已由 OC 记录，14 failed 均为存量（test_notify_exec_qa.py 14/1 等与 DPL-056 无关，前置失败先例）。本卡只须确认**无新增回归**，不修存量失败（源卡未要求） |
| R3 全量跑时长 | 低 | OC 实测 599s ≈ 10 min。跑批在后台执行（notify_on_complete），等待不占轮数；若中途超时拆段跑，+1 轮兜底 |
| R4 文档质量门禁 | 低 | 规范要可执行：每条约带「正例/反例 + 扫描命令」，让后续 QA/研发能自查。参照 qa-finding-classification.md 的论证式结构。文档本身也要过 repo 的 docs lint（若有） |
| R5 与 .hermes.md 联动 | 低 | .hermes.md 已含「QA 必须」规则；测试规范落地后建议在 .hermes.md 加一行引用（若源卡允许，属可选，不影响验收） |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | 6-12 轮 ≤ 20 轮阈值 → **不拆** |
| 模块依赖 | ①②③ 弱依赖（扫描结果写进文档 claim、全量 pytest 是最终验收），但任一环节 3-4 轮内可完成，无跨会话必要 |
| 并行收益 | 无——文档 + 验证天然单线程；拆卡反而引入 worktree 切换与 merge 开销 |
| 兜底 | 即使全量 pytest 意外暴露新问题（R2/R3 兜底），42 有效轮内足够；真出现超预算情况，②③ 可独立交付（验证结论写 comment 即算部分完成） |

**决策：不拆（[SUB-SPLIT] 1），单卡直接完成。** 量级参照：t_est_1ecadb5f（落地型 8-15 轮不拆）、t_est_0f418cf6 S1（纯落地 6-10 轮轻卡）。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 1
1. [FIX] 测试 sys.path 硬编码污染根治 — 全量 pytest 恢复为可用验收门禁（game-engine，单卡 = 源卡 t_f8d25717）：
   a. 落规范文档 docs/standards/devppl-test-spec.md（建议落位，见 R1）：
      - 禁令 1：测试禁止硬编码绝对路径（sys.path.insert(0, '/workspace/devPPL') 等），
        必须 __file__ 相对（Path(__file__).resolve().parent / os.path.join(_REPO_ROOT, ...) 基于 __file__），
        附 worktree-portable 正例 + 硬编码反例 + 扫描命令
        grep -rn 'sys.path.insert(0, "/workspace/devPPL")' tests/
      - 禁令 2：脚本式测试（模块级执行 + exit）禁止 test_ 前缀命名（pytest 收集阶段被脚本 exit 杀死
        → INTERNALERROR 全量瘫痪），必须改名非 test_ 前缀（如 staleness_guard_check.py）或加收集守卫，
        附扫描命令 grep -rn '^exit(' tests/ --include='test_*.py'
      - 每条禁令带「现象（DPL-056 病例）/正例/反例/扫描命令」，参照 qa-finding-classification.md 格式
   b. 扫描确认：复跑两条 grep 命令，0 残留写入 claim
   c. 全量 pytest：python3 -m pytest tests/ -q（后台跑 ~10min），对照基线 275 passed / 14 failed / 1 error
      确认无新增回归（14 failed 为存量，不修）
   d. 收尾：[PRODUCES]/[CLAIM] comment + 飞书推送 + complete
      预计 6-12 轮
```

- SPLIT: no（count=1，校准后 6-12 轮 ≤ 20 阈值）
- MODE: serial（单卡）
- ROUNDS_EST（校准后）: 9（基准 6-12 中位 × K=1.0）
- FILES: 新建 docs/standards/devppl-test-spec.md（~80-120 行）；零代码改动（修复已进 main）
- STATUS: not_started（本评估卡待 complete，autopilot 解析后建 1 张 [DEV-DEV]/直接派源卡）
- TESTS: 全量 pytest 275/14/1 基线对照（无新增回归）；两条 grep 扫描 0 残留
- RISK: R1 文档落位（建议 docs/standards/，wiki/ 不存在）；R2 存量失败不修；R3 全量跑 ~10min 后台化
- ACTION: build_one_dev_card（assignee=game-engine，单卡 = 源卡 t_f8d25717）

## 6. 备注

- **代码修复已完成是本卡轻量的核心原因**：OC 已在建卡前直接处置（12eb90a rename + cee5d6b 5 文件
  `__file__` 相对化 + 9daa839 merge 进 main），且污染复现验证（dpl026 前置 → dpl056 16/16 全绿）已闭环。
  本卡实质是「把教训固化成规范 + 把验收门禁跑通」，不是开发卡。
- **wiki/ 目录不存在是评估期间新发现**：源卡建议落位 `wiki/concepts/patterns/`，但 repo 无该目录。
  若产品/架构坚持 wiki 结构，需先建目录（+1 轮）；否则 docs/standards/ 是更顺的落位。
- 本评估卡自身产物（本文件）需随源卡 merge 进 main，不能悬空（不能犯它评估的错——est 文档
  NOT in main 正是 DPL-056 类问题，见 t_est_0f418cf6 第三实例教训）。
- 全量 pytest 存量 14 failed 基线（test_notify_exec_qa.py 14/1 等）已有先例记录（t_e7d69f20、
  t_est_0f418cf6），本卡不修，只做回归对照。
