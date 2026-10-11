# QA-SUB-2 复核报告 — T22 门禁 + 真实板验证 + 回归（QA-FIX-01 [CHAIN-COMPLETE] 误报修复）

> 版本：v1.0 | 日期：2026-08-12 | 作者：game-qa（QA-SUB-2，拆卡 2/2）
> 来源卡：t_ba42f2dc（6 次超时拆卡）；parent：t_620b6ccf（研发修复卡）
> 被测修复：commit `7923eff` on branch `wt/t_620b6ccf`（未 merge）
> 测试方案：docs/qa/fix-cmd-chain-complete-test-plan.md（T22 门禁 §4.3）
> 分级标准：docs/standards/qa-finding-classification.md v1.0

---

## 1. 结论（TL;DR）

| 验证项 | 结果 | 证据 |
|---|---|---|
| **T22 门禁**（误报场景 FAIL→修复后 PASS） | ✅ **PASS** | T22a/T22b 全绿（修复分支 80/80；合并树 99/99） |
| **真实板验证**（b9cb8c1763 不再误跳） | ✅ **PASS** | OLD_skip=True → NEW_skip=**False**（5 条正文提及不再触发） |
| **真实板验证**（af032394f6/fc7aca36db 仍正确跳过） | ⚠️ **claim 不可复现，但无功能影响** | 板上 0 条正式标记；两链均 13/13 全 done，advance 无事可做 |
| **回归**（合并树全量） | ✅ **PASS** | 99 + 27 + 156 全绿；merge 干净无冲突 |

**复核结论：修复可放行 merge 回 main。** 附带 2 条非阻塞发现（MINOR × 1、SUGGESTION × 1）。

---

## 2. T22 门禁执行结果（PASS）

方案 §4.3 T22 场景（误报回归）在**修复分支**独立执行：

```
bash scripts/test_cmd_channel.sh   # 在 /workspace/devPPL/.worktrees/t_620b6ccf（7923eff）
→ PASS=80 FAIL=0
  ✓ T22a: 正文提到 [CHAIN-COMPLETE]（非标记）→ 链仍推进建 va-claim   [count=1]
  ✓ T22b: 专用标记（comment 开头）→ 整组跳过不建 va-claim            [count=0]
```

- T22a 前置：prd/arch/dev 三棒 done；对 dev 卡发 comment `"D1 处置建议：默认建议 [CHAIN-COMPLETE] 标记跳过（此处仅为文档说明，非专用标记）"`（正文中间提到，非标记开头）→ 下一 tick **仍建 va-claim** ✅
- T22b 前置：对 dev 卡发 comment `"[CHAIN-COMPLETE] 存量链代码已通过其他路径合入 main，跳过续棒"`（标记独占开头）→ **不建 va-claim** ✅
- 门禁判定（方案 §4.3）：T22a 修复前必然 FAIL（误报存在）、修复后 PASS —— **符合预期，门禁通过**

---

## 3. 真实板验证（只读查询 /root/.hermes/kanban.db）

### 3.1 三条链 skip 状态对照

| 链 | 卡数/状态 | OLD_skip（`%[CHAIN-COMPLETE]%`） | NEW_skip（`[CHAIN-COMPLETE]%`） | 结论 |
|---|---|---|---|---|
| dev-b9cb8c1763（误报链） | 5/5 done（prd/arch/dev/va-claim/qa-d1） | **True**（5 条 comment 正文提及） | **False**（0 条以标记开头） | ✅ 不再误跳，可自动续棒 |
| dev-af032394f6 | 13/13 done（全链含 close） | False（0 条提及） | False（0 条标记） | ⚠️ 见 3.2 |
| dev-fc7aca36db | 13/13 done（全链含 close） | False（0 条提及） | False（0 条标记） | ⚠️ 见 3.2 |

关键数据（只读 SQL 实查）：
- 全库 `task_comments` 中 `LIKE '[CHAIN-COMPLETE]%'`（正式标记）= **0 条**
- 全库 `LIKE '%[CHAIN-COMPLETE]%'`（任意提及）= 7 条，全部落在 b9cb8c1763 链的交付 comment 正文（t_eaaf5f27/t_ae8d172f/t_e8bf805f/t_39bd7664/t_50c4ead1），外加修复卡 t_620b6ccf 和复核卡 t_ba42f2dc 自身

### 3.2 ⚠️ 发现 QA-SUB2-01（MINOR）：研发 claim #2/#3 不可复现

研发声明（t_620b6ccf comment）称：`af032394f6（正式标记）→ True（保持跳过）`、`fc7aca36db（正式标记）→ True（保持跳过）`，并标注为"真实板验证"。

**实测**：真实板上这两条链 **不存在任何 [CHAIN-COMPLETE] comment**（0 条正式标记、0 条任意提及）。`OLD_skip=False → NEW_skip=False`，与研发声明不符。

**功能影响评估**：无。两条链均已 13/13 全 done（含 close 终态），advance 对它们无可建后棒——即使 skip=False，也不会产生任何新卡。修复对这两条链无行为改变，**无回归**。

**分级判定（对照标准 §1.2）**：
- ① 存在缺陷？→ 代码无缺陷（修复本身正确）；缺陷在**验证声明不实**（证据与真实板不符）
- ② 用户可感知？→ 否（链已完结，无任何功能差异）
- ③ 非安全漏洞 ✅
- ④ 影响核心功能？→ 否
- ⑤ 判定：**MINOR**（不影响功能；但声明不实影响 VA 复验，需更正证据口径）

**建议**：研发更新修复声明，将 #2/#3 更正为"两条链无标记、已全链完结，修复不影响"；或补充说明该验证基于假设标记存在的模拟场景。VA 复验时以本报告 3.1 表为准。

---

## 4. 回归（合并树全量）

### 4.1 merge 兼容性
- `git merge-tree --write-tree main wt/t_620b6ccf` → **无冲突**（Auto-merging pipeline/cmd_chain.py + scripts/test_cmd_channel.sh）
- 实际 merge（HEAD + wt/t_620b6ccf，隔离 worktree）→ **干净合并**，仅 2 文件 +23/-3

### 4.2 合并树测试全量（独立执行）

| 测试 | 结果 | 说明 |
|---|---|---|
| test_cmd_channel.sh | **PASS=99 FAIL=0** | main 基线 97（含 smart-skip T22-T25）+ 修复 T22/T22b 2 条 |
| test_workspace_check.sh | **PASS=27 FAIL=0** | 回归范围 |
| test_notify_check.py | **PASS=156 FAIL=0** | notify 全量 |

### 4.3 其他误判路径排查（复核要求 #1 补全）
- 全库 grep `CHAIN-COMPLETE`：仅 cmd_chain.py 的 marked 查询使用 LIKE；notify_check.py 中仅为 FIX 卡标题展示（非跳过逻辑）→ **无第二处误判路径**
- 换行锚定：`LIKE '[CHAIN-COMPLETE]%'` 对 `"## 说明\n[CHAIN-COMPLETE] ..."` 不匹配 —— 这是方案 A（QA 推荐）的预期收紧；OC 标记格式以 comment 开头为准（T22b 锁定），如未来出现换行内嵌标记需再评估（SUGGESTION，见 §5）

### 4.4 其他链/普通管线任务
- 真实板现存 dev-* 链仅 3 条（b9cb8c1763 / af032394f6 / fc7aca36db），无其他活跃开发链受影响
- [CMD]/[ROUNDTABLE]/普通管线卡：R1-R3 全绿（discover 不注册 [DEV-，普通卡仍发现）

---

## 5. 发现清单

| ID | 级别 | 描述 | 处置建议 |
|---|---|---|---|
| QA-SUB2-01 | MINOR | 研发 claim #2/#3（af032394f6/fc7aca36db 正式标记→skip=True）真实板不可复现；板上 0 条标记，两链已完结无影响 | 更正声明证据口径；VA 以本报告 3.1 为准 |
| QA-SUB2-02 | SUGGESTION | 合并后 test_cmd_channel.sh 存在 T22 编号冲突：修复的 T22（误报回归）与 main smart-skip 的 T22-T25 同名（合并文件 L607 与 L627 均为 "T22"），当前 99/99 通过但测试日志同名易混淆 | merge 时可将修复 T22/T22b 重编号（如 T22f/T22g 或 T18c/T18d） |

---

## 6. SLA / 判定公式 / 分级示例对照（标准 §6 输出格式）

### 6.1 判定公式对照（标准 §1.2）
- QA-FIX-01 修复后：误报场景 T22a 从 FAIL→PASS（门禁验证通过）；无新增 BLOCKER/MAJOR
- QA-SUB2-01（MINOR）：用户可感知=否 → 不进入功能阻断公式；按"声明不实"定级 MINOR

### 6.2 SLA 对照（标准 §8）
- MAJOR QA-FIX-01：响应/定位（QA 实机复现）/方案均已在 SLA 内完成；修复 7923eff 于 2026-08-11 17:20 落地，本复核 2026-08-12 完成 ✅

### 6.3 分级示例对照（标准 §5）
- QA-SUB2-01 对照示例（低影响证据/文档类）= MINOR：用户能忍、不阻塞发版
- 对比 BLOCKER 门槛：无安全漏洞、无资金/数据一致性、无核心功能阻断 → 不满足

### 6.4 发布门禁对照（标准 §10）
- BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉
- 当前：BLOCKER=0，MAJOR=0（QA-FIX-01 已修复验证），MINOR=1，SUGGESTION=1 → **满足门禁，放行 merge**

---

## 7. 交付物
- 本报告：docs/qa/fix-cmd-chain-complete-qa-sub2-report.md
- 复核结论：**PASS，放行 merge 回 main**（研发或 OC 执行 merge）
- 复核脚本（只读查询）：/tmp/qa_sub2_realboard.py、/tmp/qa_sub2_verify2.py、/tmp/qa_sub2_markers.py
