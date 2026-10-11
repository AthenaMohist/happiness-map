# FIX notify heartbeat 统计范围限定到当前开发链 — QA-POST 合并后测试报告

> 版本：v1.0 | 日期：2026-08-11 | 作者：game-qa（QA-POST 合并后独立验证）
>
> 任务卡：t_ce68b383 [DEV-QA-POST] FIX notify heartbeat 统计范围限定到当前开发链（不统计全局历史）
> 被测状态：**合并后** devPPL main @ `1eb4b3f`（dev 卡 t_e72e6cc1 产物 ddc64e2，经 merge 6a05fbd 合入主分支 + 后续 5afb7e6/7889bc6/1eb4b3f）
> 前置阶段：PRD t_f86c3398 → ARCH t_0c41ef06 → DEV t_e72e6cc1 → VA-CLAIM t_294750f0 → QA-D1 t_d3f1e173 → QA-EXEC t_34901e64 → QA-D2 t_114271f2 → VA-QA t_2b6e91dd → MERGE t_2a8898d5
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0（判定公式/SLA/分级示例对照见 §5）

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| **合并状态核对** | ✅ main @ `1eb4b3f`（feature ddc64e2 已在主分支，工作树干净） |
| 基线复跑 `scripts/test_notify_check.py`（合并后） | ✅ **56/56 PASS**（T1-T19，含 F-9 sleep/wake 6/6） |
| QA 独立执行用例 T20-T25（合并后） | ⚠️ **10 PASS / 2 FAIL**（T20b + T21b = QA-D1-01 混合信号源盲区，根因函数未改） |
| 回归 workspace_check（B2） | ✅ **27/27 PASS** |
| 回归 cmd_channel（B3） | ✅ **78/78 PASS** |
| 真实 board dry-run 数字核对（T25，只读） | ✅ `[AP 19:50] 活跃1 跑1 堵0 今完24` — 与 board 实况逐项一致 |
| 新增缺陷（POST 阶段新发现） | **0 新增** — 合并未引入回归 |
| 已知缺陷维持 | **QA-D1-01（MAJOR）仍未修复**（无 FIX 卡落地，根因 `chain_relevant()` L411-424 与 D1/D2 记录一致）；QA-D1-02（MINOR）已由 5afb7e6 修复；QA-D1-03（MINOR）文档仍未上 main |

**结论**：合并过程正确（feature ddc64e2 已在 main，无冲突残留、无合并引入的新回归），合并后基线 56/56、回归 27+78 全绿，真实 board 数字一致，**FIX 核心路径（链卡口径统计、连字符步骤、归档清理、legacy 回退）全部正确**。**但 QA-D1-01（MAJOR，混合信号源盲区）在合并后仍然存在**——合并前没有任何 FIX 落地（`chain_relevant()` L411-424 / `compute_counts()` L454-465 与 D1 记录完全一致），且 **board 上从未建过针对 QA-D1-01 的 FIX 卡**（检索任务表：仅 t_620b6ccf 是另一问题 cmd_chain 误报，非本缺陷）。**发布门禁：BLOCKER=0、MAJOR=1（≤3）、安全漏洞=0、无未裁定申诉 → 数字上可发版但 MAJOR 必须标注 known issue**；建议 OC 建 FIX 卡给研发，QA 在 FIX 交付后执行 T20/T21 回归门禁关闭。

---

## 1. 合并状态核对（POST 前置检查）

| 检查项 | 命令 | 结果 |
|---|---|---|
| 主分支 tip | `git log --oneline -1` | ✅ `1eb4b3f fix(cmd_chain): merge 分支名 wt/t_ 双前缀` |
| feature 在 main | `git log --oneline main --grep=heartbeat` | ✅ `ddc64e2`（feature commit）+ `6a05fbd`（merge）+ `5afb7e6`（split 修复）+ `7889bc6`（F-9） |
| 工作树状态 | `git status --short` | ✅ 干净 |
| 改动面核对 | `git show --stat 6a05fbd` | ✅ 仅 config/notify.json + scripts/notify_check.py + scripts/test_notify_check.py（与 PRD 改动面一致） |
| 合并后新 commit | `git log 7889bc6..HEAD` | ✅ 仅 1eb4b3f（cmd_chain merge 分支名修复，与 notify 无关，零影响） |
| 上游链完整 | merge 卡 t_2a8898d5 已 done | ✅ 链完整 |

---

## 2. 基线复跑结果（合并后，HEAD @ 1eb4b3f）

### 2.1 静态检查

```
$ python3 -m py_compile scripts/notify_check.py scripts/test_notify_check.py
✅ 通过
```

### 2.2 基线 56/56 PASS

```
$ python3 scripts/test_notify_check.py
RESULTS: 56 PASS / 0 FAIL
```

✅ T1-T19 全绿，含 T19（F-9 sleep/wake）6/6 断言——与 D1（56/56）/ EXEC（56/56）/ D2（56/56）一致，**合并后无回归**。

### 2.3 回归范围（B2/B3 相邻模块）

| 套件 | 结果 | 说明 |
|------|:----:|------|
| `bash scripts/test_workspace_check.sh` | ✅ 27/27 | B2 合规扫描无回归 |
| `bash scripts/test_cmd_channel.sh` | ✅ 78/78 | B3 指令卡通道 + 12 棒开发链无回归 |

---

## 3. 已知缺陷回归门禁（合并后复测）

> 依据 D2 报告 §9：QA-D1-01 修复方向（方案 A/B）由研发评估，T20/T21 作为回归门禁，FIX 落地后必须全 PASS 才关闭。
> QA-POST 在合并后立即复测——**预期仍 FAIL**（无 FIX 落地），实测符合预期，缺陷维持原判定。

### 3.1 QA 独立用例 T20-T25 复跑（合并后 HEAD）

执行方式：从 QA-EXEC 分支（356921f）取回 `scripts/test_notify_exec_qa.py`（该文件未合入 main，POST 阶段从 commit 提取复跑），隔离 fixture 环境。

```
── T20: 混合源盲区 — 链卡全 done-今日 + pipeline running ──
  ✓ T20a: ACTIVE 仍成立（推 heartbeat）
  ✗ T20b: 修复后活跃N ≥ 1（当前: [AP 19:37] 活跃0 跑0 堵0 今完2）   ← QA-D1-01
── T21: 混合源 — 链卡全 done-今日 + pipeline blocked ──
  ✓ T21a: ACTIVE=true
  ✗ T21b: 修复后堵N ≥ 1（当前: [AP 19:37] 活跃0 跑0 堵0 今完1）     ← QA-D1-01
── T22: 连字符步骤 (qa-d1/va-claim) → 正确统计 ──
  ✓ T22a: read_dev_chain_cards 含 qa-d1 + va-claim 完整步骤名        ← QA-D1-02 已修复
  ✓ T22b: 活跃2 跑1 堵0 今完0
── T23: blocked 链卡 → 堵N + ACTIVE ──
  ✓ T23a: ACTIVE=true
  ✓ T23b: 数字=活跃0 跑0 堵1 今完0
── T24: 归档链卡 snapshot 立即清理（ADR-7）──
  ✓ T24-pre: snapshot 含链卡 t_a1
  ✓ T24a: 归档后 pipeline_snapshot 无该 task_id 残留
── T25: 真实 board 数字核对（compute_counts 直接验证）──
  ✓ T25a: compute_counts 口径判定正确
  ✓ T25b: heartbeat 数字与 board 实况一致
  [dev 链卡数] 25（board: 25）
  [board 核对] 活跃2 跑2 堵0 今完23   → 随后另一链 qa-post 完成，复跑得 活跃1 跑1 堵0 今完24 | t_02577c95 qa-post done
  [口径] chain

RESULTS: 10 PASS / 2 FAIL
```

### 3.2 回归门禁汇总

| # | 回归用例 | 对应缺陷 | 合并后状态 | 结论 |
|---|---------|---------|:---:|------|
| T20b | 链卡 done-今日 + pipeline running → 活跃N≥1 | QA-D1-01（MAJOR） | 🔴 FAIL | 未修复 |
| T21b | 链卡 done-今日 + pipeline blocked → 堵N≥1 | QA-D1-01（MAJOR 变体） | 🔴 FAIL | 未修复 |
| T22a/b | 连字符步骤完整解析 | QA-D1-02（MINOR） | ✅ PASS | 5afb7e6 已修复 |
| T23a/b | blocked 链卡 → 堵N + ACTIVE | 补 AC-1 | ✅ PASS | 正确 |
| T24a | 归档链卡 snapshot 立即清理 | ADR-7 | ✅ PASS | 正确 |
| T25a/b | 真实 board 数字一致 | 环境核对 | ✅ PASS | 正确 |

### 3.3 根因代码复核（POST）

```
$ git diff ddc64e2 HEAD -- scripts/notify_check.py | wc -l → 101 行（仅 5afb7e6 split + 7889bc6 F-9，均不触及盲区）
$ grep -n "def chain_relevant" -A 14 scripts/notify_check.py  → L411-424 与 D1 记录完全一致
```

**确认**：`chain_relevant()` 的 done-今日分支（L420-423）仍只检查链卡 completed_at，不看 pipeline 活跃；`compute_counts()` 仍按 `chain_relevant` 结果二选一，无合并逻辑——QA-D1-01 根因未变。

### 3.4 board 上 QA-D1-01 FIX 卡核对

```
$ sqlite3 /root/.hermes/kanban.db "SELECT id,title,status FROM tasks WHERE title LIKE '%盲区%' OR title LIKE '%QA-D1-01%' OR title LIKE '%混合%';"
→ 仅 t_6d3046d0（历史 autopilot 发现盲区，done，非本缺陷）
→ 无针对 QA-D1-01 的 FIX 卡
```

**流程缺口确认**：D1（t_d3f1e173）/ EXEC（t_34901e64）/ D2（t_114271f2）三轮报告均明确建议 OC 建 FIX 卡，但 board 上从未创建——管线照常推进 VA-QA → MERGE → QA-POST。QA 按建卡铁律**不代建研发 FIX 卡**，此处再次提请 OC 处置。

---

## 4. 真实 board 数字核对（只读 dry-run，POST 阶段）

生产库副本（`cp /root/.hermes/kanban.db /tmp/qa-post/` + pipeline_state.db + notify_state.db），`--dry-run` 不写生产：

```
$ python3 scripts/notify_check.py --dry-run --state-db /tmp/qa-post/pipeline_state.db \
    --notify-db /tmp/qa-post/notify_state.db --kanban-db /tmp/qa-post/kanban.db
[DRY-RUN] 将推送: [AP 19:50] 活跃1 跑1 堵0 今完24 | t_02577c95 qa-post done
```

SQL 独立核对（kanban tasks 表）：
- 在途链卡（ready/running/blocked，dev-%） = 1（t_ce68b383 本卡 running） ✅
- running = 1 ✅
- blocked = 0 ✅
- done 今日 = 24 ✅

**口径**：chain（链卡有在途）。与 heartbeat 输出逐项一致。当前 board 不在盲区（本卡 running 在途），但一旦本卡完成进入下一棒 dev/qa 卡，且旧链卡 done-今日仍在窗口内，盲区将再次显现——**QA-D1-01 是持续性风险，不是一次性状态**。

---

## 5. 判定公式 / SLA / 分级示例对照（标准 §6 输出格式要求）

### 5.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| QA-D1-01（混合信号源盲区，维持） | ✅（heartbeat 报 活跃0 而 pipeline 在跑） | ✅（信号失真，pipeline 活跃被掩盖） | ✅（查 board/log 可发现） | 否 | 否 | **MAJOR** |
| QA-D1-02（连字符缺测，已修复） | ❌（修复已生效，回归已补） | ❌ | — | 否 | 否 | 已关闭 |
| QA-D1-03（文档未上 main，维持） | ✅（下游引用断裂） | ❌ | ✅（查 commit） | 否 | 否 | **MINOR** |

### 5.2 SLA 对照（标准 §8）

| 发现 | 级别 | 响应 | 定位（初步判定） | 方案 | 当前状态 |
|------|:---:|:---:|:---:|:---:|:---:|
| QA-D1-01 | MAJOR | 1 工作日 | 2 工作日（QA 已实机复现 sim1 + 证据链完整） | 当前版本窗口（D1 方案 §3 方案 A/B） | **超期未处置**：自 D1（18:10）报告至今 1.5h+，无 FIX 卡、无研发评估记录 |
| QA-D1-03 | MINOR | 2 工作日 | — | merge 时合入文档 | 维持（merge 6a05fbd 未含文档） |

### 5.3 分级示例对照（标准 §5 表）

- QA-D1-01 对照示例 8（「缓存不一致导致部分用户看到过期数据」= MAJOR）与示例 16（「关键路径静默失败」）→ 同构，**MAJOR** 成立；对比 BLOCKER 门槛：无资金/核心数据一致性、无 OOM、无安全漏洞 → 不满足 BLOCKER。
- QA-D1-03 对照示例 15（代码层面）→ 用户不可感知/低影响 → **MINOR** 成立。

---

## 6. 发布门禁对照（标准 §10）

| 条件 | 当前 | 判定 |
|------|------|------|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 1（QA-D1-01） | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**结论**：门禁数字上通过（MAJOR=1 ≤ 3），但按标准 §1.1，**MAJOR 发版必须标注 known issue**——heartbeat 在「链卡全 done-今日 + pipeline 活跃」状态下数字失真（报 活跃0 跑0 堵0）。**推荐做法：先由 OC 建 FIX 卡关闭 QA-D1-01 再发版**（修复面小，D1 方案已给出方向，T20/T21 门禁已就绪）；若 Frank 决定带 known issue 发版，需在产品层面确认。

---

## 7. 处置建议（QA 只测不改，不代建 FIX 卡）

1. **OC 建 FIX 卡**（assignee=game-engine，parents=[t_ce68b383]）：标题建议「FIX notify heartbeat 混合信号源盲区 — 链卡 done-今日 + pipeline 活跃时数字失真（QA-D1-01 MAJOR）」，body 附 D1 测试方案 §3 复现 + 方案 A/B。
2. **研发修复**：方案 A（chain_relevant done-今日分支加 pipeline 活跃检查 → 回退 legacy 或合并计数）或方案 B（compute_counts 合并 pipeline 数字），任一满足 T20b/T21b。
3. **QA 回归门禁**：FIX 落地后复跑 T20/T21（+ 基线 56 断言 + 回归 27+78）→ 全 PASS 后关闭。
4. **QA-D1-03（MINOR）**：merge 时把 `docs/prd/fix-notify-heartbeat-chain-scope-prd.md` + `docs/arch-fix-notify-heartbeat-chain-scope.md` + 本链 QA 文档一并合入 main，或任务卡引用改为 commit 链接。

---

## 8. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | QA-D1-01 未修且无 FIX 卡：每轮链卡 done-今日 + pipeline 活跃即触发盲区 | Frank 对系统状态错误认知（本 FIX 核心目标在边界态失效） | 立即建 FIX 卡；T20/T21 门禁 |
| R2 | 测试脚本 test_notify_exec_qa.py 未合入 main（仅存于 QA-EXEC/D2 分支） | 回归门禁用例丢失，后续无法自动复跑 | 建议 merge 时并入 scripts/ |
| R3 | QA 文档（D1 方案/EXEC 报告/D2 报告/本报告）未上 main | 下游引用断裂（QA-D1-03 延续） | merge 时一并合入 |

---

## 附：与本任务相关的既有文档

- D1 测试方案：`docs/qa/fix-notify-heartbeat-chain-scope-test-plan.md`（分支 wt/t_d3f1e173，commit 361ddbf）
- QA-EXEC 报告：`docs/qa/fix-notify-heartbeat-chain-scope-test-report.md`（分支 wt/t_34901e64，commit 356921f）
- QA-D2 复测报告：`docs/qa/fix-notify-heartbeat-chain-scope-d2-report.md`（分支 wt/t_114271f2，commit 3031732）
- 执行脚本：`scripts/test_notify_exec_qa.py`、`scripts/d2_board_probe.py`（同上分支）
- PRD：`docs/prd/fix-notify-heartbeat-chain-scope-prd.md`（commit 6f7abcb，未上 main）
- 架构：`docs/arch-fix-notify-heartbeat-chain-scope.md`（commit 2c57d81，未上 main）
- 分级标准：`docs/standards/qa-finding-classification.md` v1.0
