# FIX cmd_chain 开发链补全 — QA-POST 合并后测试报告

> 版本：v1.0 | 日期：2026-08-12 | 作者：game-qa（QA-POST 合并后独立验证）
>
> 任务卡：t_9c98ce3f [DEV-QA-POST] FIX cmd_chain 开发链补全 — dev 后接 va-claim/QA/VA/merge 完整流程（Frank 2026-08-11 完整流程）
> 被测状态：**合并后** devPPL main @ `292efc3`（dev 卡 t_e8bf805f 产物 9ca1d02，经 merge f347fee 合入主分支 + 后续 7923eff QA-FIX-01 修复 / 87de82c dev-est 13 棒 / 多个相邻合并）
> 前置阶段：PRD t_eaaf5f27 → ARCH t_ae8d172f → DEV t_e8bf805f → VA-CLAIM（9/9 VERIFIED）→ QA-D1 → QA-EXEC t_c36d7426 → QA-D2 t_3fc2eb70（review_pass 附条件）→ VA-QA → MERGE t_79e91534
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0（判定公式/SLA/分级示例对照见 §5）

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| **合并状态核对** | ✅ main @ `292efc3`（feature 9ca1d02 经 merge `f347fee` 已在主分支，工作树干净） |
| 基线复跑 `scripts/test_cmd_channel.sh`（合并后） | ⚠️ **PASS=122 / FAIL=1**（唯一失败 = T22a = QA-FIX-02 已知缺陷） |
| 回归 `scripts/test_workspace_check.sh`（B2） | ✅ **27/27 PASS** |
| QA-FIX-01 合并后复核（7923eff） | ✅ **正确**：T22b（专用标记开头→跳过）PASS；[CHAIN-COMPLETE] LIKE 开头匹配生效 |
| QA-FIX-02 已知缺陷回归（合并后复测） | 🔴 **FAIL 维持**（T22a fixture 缺 `dev-est:done`，advance 先建 dev-est 不建 va-claim） |
| QA-FIX-02 一行修复方向 D2 独立验证 | ✅ **PASS=123 FAIL=0**（L629 补 `dev-est:done` 隔离复跑通过） |
| 新增缺陷（POST 阶段新发现） | **0 新增** — 合并未引入回归 |
| 发布门禁（§10） | BLOCKER=0、MAJOR=1（≤3）、安全=0、申诉=0 → 数字通过，**MAJOR 必须标注 known issue** |

**结论**：合并过程正确（feature 9ca1d02 在 main，无冲突残留，无合并引入的新回归）；QA-FIX-01 修复（7923eff）合并后仍正确；B2 回归 27/27 全绿。**但 QA-FIX-02（MAJOR，T22a fixture 缺 `dev-est:done`）在合并后仍然存在**——根因是 87de82c 把链从 12 棒扩到 13 棒（arch 与 dev 之间插入 dev-est），而 T22a fixture 的 `insert_dev_chain` 仍写 `"prd:done" "arch:done" "dev:done"`（缺 dev-est 棒），advance 发现 dev-est 未 done → 先建 dev-est 而非 va-claim → T22a 断言 va-claim=1 得 0。**board 上从未建过针对 QA-FIX-02 的 FIX 卡**（检索任务表：0 张卡 title 含 QA-FIX-02）。按建卡铁律 QA 不代建研发 FIX 卡，此处再次提请 OC 处置。

---

## 1. 合并状态核对（POST 前置检查）

| 检查项 | 命令 | 结果 |
|---|---|---|
| 主分支 tip | `git log --oneline -1 main` | ✅ `292efc3 Merge branch 'wt/t_620b6ccf'` |
| feature 在 main | `git log --oneline main --grep="开发链\|DEVELOPMENT_CHAIN"` | ✅ `9ca1d02`（feature）+ `f347fee`（merge）+ `7923eff`（QA-FIX-01）+ `87de82c`（dev-est 13 棒） |
| 工作树状态 | `git status --short` | ✅ 干净（测试文件复原后无残留） |
| 改动面核对 | `git show --stat f347fee` | ✅ pipeline/cmd_chain.py +340 / constants.py +22 / cmd_channel.sh +104 / dedup_check.sh +5 / test_cmd_channel.sh +232（与 PRD 改动面一致） |
| 合并后相关 commit | `git log f347fee..main --oneline` | ✅ 含 7923eff（QA-FIX-01）、87de82c（dev-est）、a9e25e0（smart-skip）等相邻演进，均与本 FIX 核心路径一致或正交 |
| 上游链完整 | merge 卡 t_79e91534 已 done | ✅ 链完整 |

---

## 2. 基线复跑结果（合并后，HEAD @ 292efc3）

### 2.1 回归范围（B2/B3 相邻模块）

| 套件 | 结果 | 说明 |
|------|:----:|------|
| `bash scripts/test_workspace_check.sh` | ✅ **27/27** | B2 合规扫描无回归 |
| `bash scripts/test_cmd_channel.sh` | ⚠️ **122/1** | B3 指令卡通道 + 13 棒开发链；唯一失败 = T22a（QA-FIX-02 已知缺陷） |

### 2.2 T22a 失败定位（合并后复测）

```
── T22: [CHAIN-COMPLETE] 误报回归（QA-FIX-01）— 正文提到但非标记 → 不跳过 ──
  ✗ T22a: 正文提到 [CHAIN-COMPLETE]（非标记）→ 链仍推进建 va-claim (got '0' want '1')
── T22b: [CHAIN-COMPLETE] 专用标记（comment 开头）→ 仍跳过（ADR-7 回归）──
  ✓ T22b: 专用标记（comment 开头）→ 整组跳过不建 va-claim
```

- T22b PASS → **QA-FIX-01 修复（7923eff）合并后正确**：专用标记（comment 开头）仍跳过整组，ADR-7 存量链保护未破坏。
- T22a FAIL → **QA-FIX-02 维持**：T22a fixture 的 `insert_dev_chain "$H22" "T22误报回归主题" "prd:done" "arch:done" "dev:done"`（test_cmd_channel.sh L629）缺 `dev-est:done` 棒。

---

## 3. 已知缺陷回归门禁（合并后复测）

> 依据 D2 报告（t_3fc2eb70）：QA-FIX-02 = T22a fixture L629 缺 `dev-est:done`（87de82c 把链从 12 棒扩到 13 棒，arch 与 dev 之间插入 dev-est 棒，fixture 未跟上）。QA-POST 在合并后立即复测——**预期仍 FAIL**（无 FIX 落地），实测符合预期，缺陷维持原判定。

### 3.1 根因代码复核（POST）

- `pipeline/constants.py` L67-90（main @ 292efc3）：`DEVELOPMENT_CHAIN` 已是 13 棒，`dev-est` 位于 arch 与 dev 之间（87de82c 落地）。
- `scripts/test_cmd_channel.sh` L629（main @ 292efc3）：T22a fixture 仍为 `"prd:done" "arch:done" "dev:done"`——**缺 `dev-est:done`**，与 D2 记录完全一致，未被任何后续 commit 修复。

**机制**：advance_sequential_chains 扫描该组，发现 dev-est 棒无 done 记录 → 按 sequential 语义先建 dev-est 卡（而非跳到 va-claim）→ T22a 断言「va-claim=1」得 0。这不是 QA-FIX-01 回归（QA-FIX-01 关注的是 [CHAIN-COMPLETE] 标记匹配，T22b 已证明其正确），而是测试 fixture 与 13 棒链结构脱节。

### 3.2 QA-FIX-02 一行修复方向 D2 独立验证（隔离复跑）

```
$ cp scripts/test_cmd_channel.sh /tmp/tcc_backup.sh
$ sed -i 's|insert_dev_chain "$H22" "T22误报回归主题" "prd:done" "arch:done" "dev:done"|insert_dev_chain "$H22" "T22误报回归主题" "prd:done" "arch:done" "dev-est:done" "dev:done"|' scripts/test_cmd_channel.sh
$ bash scripts/test_cmd_channel.sh
════════ 结果汇总 ════════
PASS=123 FAIL=0
ALL TESTS PASSED
$ cp /tmp/tcc_backup.sh scripts/test_cmd_channel.sh   # 复原，工作树干净
```

✅ **修复方向有效**：L629 补 `dev-est:done` → 123/0 全绿。与 D2（t_3fc2eb70）记录一致。

### 3.3 board 上 QA-FIX-02 FIX 卡核对

```
$ sqlite3 /root/.hermes/kanban.db "SELECT COUNT(*) FROM tasks WHERE title LIKE '%QA-FIX-02%';"
→ 0
```

**流程缺口确认**：D2（t_3fc2eb70）报告明确建议 OC 建 FIX 卡给 game-engine，但 board 上从未创建——管线照常推进 VA-QA → MERGE → QA-POST。QA 按建卡铁律**不代建研发 FIX 卡**，此处再次提请 OC 处置。

### 3.4 回归门禁汇总

| # | 回归用例 | 对应缺陷 | 合并后状态 | 结论 |
|---|---------|---------|:---:|------|
| T22a | 正文提到 [CHAIN-COMPLETE]（非标记）→ 链推进建 va-claim | QA-FIX-02（MAJOR） | 🔴 FAIL | 未修复（fixture 缺 dev-est:done） |
| T22b | 专用标记（comment 开头）→ 整组跳过 | QA-FIX-01（已修复） | ✅ PASS | 7923eff 合并后正确 |

---

## 4. 判定公式 / SLA / 分级示例对照（标准 §6 输出格式要求）

### 4.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| QA-FIX-02（T22a fixture 缺 dev-est:done，维持） | ✅（测试门禁红，CI 可见） | ✅（T22a 回归用例 FAIL，门禁失真） | ✅（1 行 fixture 修复） | 否 | 否 | **MAJOR** |
| QA-FIX-01（[CHAIN-COMPLETE] 误报，已修复） | ❌（7923eff 已生效） | ❌ | — | 否 | 否 | 已关闭 |

### 4.2 SLA 对照（标准 §8）

| 发现 | 级别 | 响应 | 定位（初步判定） | 方案 | 当前状态 |
|------|:---:|:---:|:---:|:---:|:---:|
| QA-FIX-02 | MAJOR | 已超期（D2 报告 2026-08-12 04:42 至今） | ✅ QA 已实机定位（fixture L629 缺 dev-est:done） | ✅ 1 行修复方向已验证（123/0） | **超期未处置**：无 FIX 卡、无研发评估记录 |

### 4.3 分级示例对照（标准 §5 表）

- QA-FIX-02 对照示例（「测试用例与实现脱节导致回归门禁误报」）→ 用户可感知（CI 红）+ 功能阻断（门禁信号失真）+ 有 workaround（1 行修复）→ **MAJOR** 成立；对比 BLOCKER 门槛：无资金/核心数据一致性/OOM/安全漏洞 → 不满足 BLOCKER。

---

## 5. 发布门禁对照（标准 §10）

| 条件 | 当前 | 判定 |
|------|------|------|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 1（QA-FIX-02） | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**结论**：门禁数字上通过（MAJOR=1 ≤ 3），但按标准 §1.1，**MAJOR 发版必须标注 known issue**——test_cmd_channel.sh T22a 在 13 棒链结构下 FAIL（fixture 缺 dev-est:done）。**推荐做法：先由 OC 建 FIX 卡关闭 QA-FIX-02 再发版**（修复面极小，1 行 fixture 补 dev-est:done，D2/POST 均已验证 123/0）；若 Frank 决定带 known issue 发版，需在产品层面确认。

---

## 6. 处置建议（QA 只测不改，不代建 FIX 卡）

1. **OC 建 FIX 卡**（assignee=game-engine，parents=[t_9c98ce3f]）：标题建议「FIX test_cmd_channel.sh T22a fixture — 补 dev-est:done 适配 13 棒链（QA-FIX-02 MAJOR）」，body 附本报告 §3.2 一行修复方向 + 123/0 验证证据。
2. **研发修复**：test_cmd_channel.sh L629 `insert_dev_chain "$H22" "T22误报回归主题" "prd:done" "arch:done" "dev:done"` → 在 `arch:done` 与 `dev:done` 之间补 `"dev-est:done"`。
3. **QA 回归门禁**：FIX 落地后复跑 test_cmd_channel.sh（预期 123/0）+ workspace_check.sh（27/27）→ 全 PASS 后关闭。

---

## 7. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | QA-FIX-02 未修且无 FIX 卡：test_cmd_channel.sh 持续 122/1，T22a 长期红 | CI/门禁信号失真，掩盖后续真回归 | 立即建 FIX 卡；1 行修复已验证 |
| R2 | spec.md（docs/prd/fix-cmd-chain-complete-dev-flow-prd.md）与 arch.md 仅存于 worktree，未上 main | 下游引用断裂（任务卡引用失效） | 建议 merge 时一并合入 main，或任务卡引用改为 commit 链接 |

---

## 附：与本任务相关的既有文档

- PRD：`docs/prd/fix-cmd-chain-complete-dev-flow-prd.md`（worktree t_eaaf5f27，commit 见 dev 卡）
- 架构：`docs/arch-fix-cmd-chain-complete-dev-flow.md`（worktree t_ae8d172f）
- QA 测试方案：`docs/qa/fix-cmd-chain-complete-test-plan.md`
- QA-EXEC 报告：`docs/qa/fix-cmd-chain-complete-test-report.md`
- QA-D2 复测报告：`docs/qa/fix-cmd-chain-complete-d2-review.md`
- 分级标准：`docs/standards/qa-finding-classification.md` v1.0
