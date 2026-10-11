# FIX cmd_chain 开发链补全 — QA 测试执行报告（test_report.md）

> 版本：v1.0 | 日期：2026-08-12 | 作者：game-qa（独立测试执行，非研发自测）
>
> 任务卡：t_c36d7426 [DEV-QA-EXEC] FIX cmd_chain 开发链补全 — dev 后接 va-claim/QA/VA/merge 完整流程
> 被测基线：main @ 292efc3（含 9ca1d02 12 棒补全 + 7923eff QA-FIX-01 修复 + 87de82c estimate-split）
> 测试方案：`docs/qa/fix-cmd-chain-complete-test-plan.md`（v1.0，t_50c4ead1）
> 上游文档：
> - PRD：`docs/prd/fix-cmd-chain-complete-dev-flow-prd.md`（t_eaaf5f27）
> - 架构：`docs/arch-fix-cmd-chain-complete-dev-flow.md`（t_ae8d172f）
> - 分级标准：`docs/standards/qa-finding-classification.md` v1.0

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| 静态检查（bash -n × 3 + py_compile × 2） | ✅ 全部通过 |
| 基线复跑 `scripts/test_cmd_channel.sh`（main @ 292efc3） | ⚠️ PASS=122 FAIL=1（T22a） |
| 回归复跑 `scripts/test_workspace_check.sh` | ✅ PASS=27 FAIL=0 |
| QA-FIX-01（[CHAIN-COMPLETE] 误报）修复验证 | ✅ 生产代码修复正确（隔离复现 A/B/C + 真实板核对） |
| 测试方案新增用例覆盖（T22-T28） | ⚠️ T22a/T22b 已入脚本；T22a 因 fixture 过时 FAIL（见 §3）；T23-T28 未入脚本，T24/T25 手工验证通过，T28 真实板核对通过 |
| **本次执行发现** | **MAJOR × 1（QA-FIX-02：T22a 回归门禁 fixture 过时）** |

**结论**：
1. **QA-FIX-01 修复（7923eff）生产代码正确**——`cmd_chain.py` L826 已收紧为 `LIKE '[CHAIN-COMPLETE]%'`（标记独占 comment 开头）；隔离复现 Scenario B（正文提到非标记 → 链仍推进建 va-claim）✅、Scenario C（专用标记 → 整组跳过）✅；真实板 dev-b9cb8c1763 链持续推进（qa-exec 本卡 running）✅。
2. **新发现 QA-FIX-02（MAJOR，测试套件缺陷）**：QA-FIX-01 的回归门禁 T22a 在 main 上 FAIL——estimate-split 提交 87de82c 在 DEVELOPMENT_CHAIN 中 arch 与 dev 之间插入 `dev-est` 棒，同步更新了 T7/T13/T14/T17/T18b/T24/T26-30 的 fixture，**唯独漏掉 T22a**（test_cmd_channel.sh L629 仍为 `prd:done arch:done dev:done`，缺 `dev-est:done`）。生产代码行为正确（advance 先建 dev-est 再续棒），是测试 fixture 未跟上 13 棒链结构。T22a 修复方向：fixture 补 `dev-est:done`（1 行）。
3. **发布门禁（标准 §10）**：BLOCKER=0，MAJOR=1（QA-FIX-02）≤3，安全漏洞=0，无未裁定申诉 → 未越过门禁，但 QA-FIX-02 需在测试门禁转绿前由研发修复 fixture（建议 OC 建 FIX 卡，参照 QA-FIX-01 闭环流程）。

---

## 1. 执行环境与方法

与测试方案 §2 一致（隔离，不触碰真实 board 写入）：

| 项 | 配置 |
|---|---|
| 隔离 kanban.db | 复制真实 schema → 清空 → 插入受控行（`/tmp/qaexec-*/kanban.db`） |
| 隔离 pipeline_state.db | `/tmp/qaexec-*/pipe.db`（CheckpointDB ensure_schema + backup_script → /bin/true 封闭 merge） |
| 隔离 git 仓库 | `/tmp/qaexec-*/gitrepo`：main + `wt/t_<dev卡id>` + 无关分支（merge/close 执行靶） |
| 环境变量 | `HERMES_KANBAN_DB` / `PIPELINE_STATE_DB` 指向 temp；`PYTHONPATH=$REPO_ROOT` |
| 执行命令 | `bash scripts/test_cmd_channel.sh`（TEST_TMPT 按任务隔离）+ `bash scripts/test_workspace_check.sh` + 独立 Python 复现脚本 |

**执行前置全部通过**：
1. `bash -n scripts/cmd_channel.sh scripts/test_cmd_channel.sh scripts/dedup_check.sh` ✅
2. `python3 -m py_compile pipeline/cmd_chain.py pipeline/constants.py` ✅
3. 基线复跑 ✅（见下）

---

## 2. 测试结果明细

### 2.1 test_cmd_channel.sh（main @ 292efc3，独立复跑）

```
PASS=122 FAIL=1
SOME TESTS FAILED
```

| 需求域 | 用例 | 结果 |
|--------|------|:---:|
| [CMD] 消费/建链/幂等/控制面/容错/滞留（B3 存量） | T1-T12 | ✅ 全绿 |
| 12 棒推进（AC-1/2/4） | T13/T14 | ✅ 全绿 |
| merge/close 自消费（AC-3/3b/7） | T15/T15b/T16/T16b/T21 | ✅ 全绿 |
| 产物追溯注入（AC-6） | T17 | ✅ 全绿 |
| [CHAIN-COMPLETE] 真标记跳过（AC-8） | T18a/T18b | ✅ 全绿 |
| 解析修复（AC-4/5） | T19 | ✅ 全绿 |
| dedup 排除回归（ADR-8） | T20 | ✅ 全绿 |
| **QA-FIX-01 误报回归（门禁）** | **T22a** | **❌ FAIL（got '0' want '1'）** |
| QA-FIX-01 真标记回归（ADR-7） | T22b | ✅ 全绿 |
| 智能跳步（smart-skip，后续特性） | T22-T25（新编号） | ✅ 全绿 |
| 评估拆卡（estimate-split，后续特性） | T26-T31 | ✅ 全绿 |
| B2 回归（discover 排除） | R1-R3 | ✅ 全绿 |

### 2.2 test_workspace_check.sh（回归范围，独立复跑）

```
PASS=27 FAIL=0
ALL TESTS PASSED
```

### 2.3 独立隔离复现（QA 新增证据，非研发脚本内）

| 场景 | 输入 | 结果 | 结论 |
|------|------|------|------|
| A：T22a 现 fixture（prd/arch/dev done，无 dev-est，正文提到 [CHAIN-COMPLETE]） | advance 一次 | va_claim=0，**dev_est=1** | 生产 advance 先建 dev-est（13 棒链的正常续棒）；**非误报跳过** |
| B：修正 fixture（prd/arch/dev-est/dev done，正文提到非标记） | advance 一次 | **va_claim=1** | ✅ QA-FIX-01 修复正确：正文提到不再误判跳过 |
| C：真标记 + dev-est 齐全（comment 以 [CHAIN-COMPLETE] 开头） | advance 一次 | va_claim=0 | ✅ T22b 回归：真标记仍跳过（ADR-7 不破坏） |
| D1：merge 卡分支不存在（测试方案 T24） | exec_chain_merge | action=failed，detail 含"分支 wt/t_xxx 不存在" | ✅ merge 失败路径正确（ADR-4/F-9） |
| D2：当前分支非 main（测试方案 T25） | exec_chain_merge | action=failed，detail 含"不是 main/master，拒绝合并" | ✅ 非 main 拒绝合并（AC-3b） |
| D3：main 上正常 merge | exec_chain_merge | action=done，git log 含 autopilot merge commit | ✅ 正常路径不受影响 |

### 2.4 真实板只读核对（测试方案 T28）

| 核对项 | 结果 |
|--------|:---:|
| dev-b9cb8c1763 链卡齐全（prd→arch→dev→va-claim→qa-d1→dev-est→qa-exec） | ✅ |
| 链上无滞留 [DEV-MERGE]/[DEV-CLOSE]（ready >3 tick） | ✅ 0 张 |
| 存量链 af032394f6 / fc7aca36db 已全链闭环（close done） | ✅ |
| 真实板 b9cb8c1763 有 retroactive [DEV-EST]（t_10fef705 done） | ✅ 与隔离复现 A 行为一致 |

---

## 3. ⚠️ 本次执行发现

### QA-FIX-02（MAJOR）：QA-FIX-01 回归门禁 T22a 在 main 上 FAIL —— 测试 fixture 未跟上 13 棒链结构

**位置**：`scripts/test_cmd_channel.sh` L629（T22a fixture），对比 L580（T18b fixture，87de82c 已更新）

**缺陷描述**：
- estimate-split 提交 87de82c 在 DEVELOPMENT_CHAIN 中 arch 与 dev 之间插入 `dev-est` 棒（constants.py L74-77，链 12→13 棒）
- 该提交同步更新了 T7/T13/T14/T17/T18b/T24/T26-30 的 fixture（均补 `dev-est:done`），**唯独漏掉 T22a**（L629 仍为 `"prd:done" "arch:done" "dev:done"`）
- 结果：advance 对 T22a 链的正确行为是**先建 dev-est 卡**（`dev_est=1`），不会一步到 va-claim → 断言 `va_claim==1` FAIL

**关键区分（非生产代码缺陷）**：
- 生产代码 `cmd_chain.py` L826 的 `LIKE '[CHAIN-COMPLETE]%'` 修复**正确且生效**——Scenario B 证明正文提到非标记时链正常推进建 va-claim（va_claim=1）
- 真实板 b9cb8c1763 链持续推进（dev-est 自动补建并 done → qa-exec 本卡 running），说明生产 advance 无回归
- 缺陷在测试套件 fixture 本身：T22a 的目标断言场景（正文提到 → 建 va-claim）需要链到达 va-claim 前棒，而当前 fixture 少了 dev-est 棒

**分级判定（对照标准 §1.2 五步公式）**：
- ① 存在缺陷 ✅（main 上测试套件 FAIL=1，回归门禁失效）
- ② 用户可感知 ✅（CI/测试门禁红，开发链 QA 门禁无法通过；标准 §1.3「系统健康度退化」）
- ③ 非安全漏洞 ✅
- ④ 影响核心功能 ✅（QA-FIX-01 的回归保护失效：T22a 无法区分「修复正确但 fixture 过时」与「修复被回退」——两者都 FAIL，门禁失去信息量）
- ⑤ 分级：用户可感知 AND 功能阻断（门禁失效）但有 workaround（隔离复现 B 手工验证修复正确 + 1 行 fixture 修复）→ **MAJOR**（非 BLOCKER）

**SLA 对照（标准 §8）**：MAJOR 8h 定位（QA 已实机复现 + 根因定位到 87de82c 漏改 L629）+ 24h 方案（本报告 §3 给出修复方向）→ 需研发评估。

**修复方向（供研发评估，QA 不代修）**：
- 1 行修复：`scripts/test_cmd_channel.sh` L629 改为
  `insert_dev_chain "$H22" "T22误报回归主题" "prd:done" "arch:done" "dev-est:done" "dev:done"`
- 修复后 T22a 断言 `va_claim==1` 恢复为有效门禁（与 T18b 同构）
- 建议同时核对 T22b fixture（当前因真标记整组跳过不暴露问题，但语义上同样应补 `dev-est:done` 保持 fixture 与 13 棒链一致）

**影响面评估**：仅测试套件受影响；生产代码无缺陷。当前 main 上任何 CI 运行 `test_cmd_channel.sh` 都会报 FAIL=1，会污染后续所有 QA/VA 门禁判断，需尽快修复。

**处理建议**：按标准 §6 论证流程——QA 报告 → 研发评估（通过/驳回/暂缓）→ 建议 OC 建 FIX 卡给 game-engine（参照 QA-FIX-01 闭环：t_620b6ccf 模式），修复后 QA 复测 T22a/T22b 转绿。

---

## 4. 测试方案新增用例覆盖对照

| 方案用例 | 状态 | 说明 |
|---------|:---:|------|
| T22（误报回归，门禁） | ⚠️ 已入脚本但 FAIL | 根因 QA-FIX-02（fixture 过时）；生产修复本身正确 |
| T22b（真标记回归） | ✅ 已入脚本 PASS | L636-642 |
| T23（ADR-9 workspace_kind 断言） | ⚠️ 未入脚本 | 生产代码 L396 merge/close 不传 workspace 已静态核对（S6），建议后续补断言 |
| T24（merge 分支缺失失败路径） | ⚠️ 未入脚本，**QA 手工验证 PASS** | 隔离复现 D1：failed + 正确 detail |
| T25（merge 非 main 拒绝） | ⚠️ 未入脚本，**QA 手工验证 PASS** | 隔离复现 D2：failed + 拒绝合并；D3 正常路径不受影响 |
| T26（两链并行） | ⚠️ 部分覆盖 | 脚本 T6c 覆盖两链各建 PRD；完整 A→qa-d1/B→arch 断言未入脚本 |
| T27（archived 卡幂等） | ⚠️ 部分覆盖 | 脚本 T21 覆盖消费幂等；advance 扫 archived 幂等未单独断言 |
| T28（真实板核对） | ✅ 本报告 §2.4 完成 | 只读查询，无写入 |

> 注：测试方案编号 T23-T28 与后续特性（smart-skip T22-T25、estimate-split T26-T31）存在编号复用，方案原编号 T23-T28 中除 T22/T22b 外均未按原编号并入脚本。建议研发在修复 QA-FIX-02 时一并将 T23-T25 断言补入（可并入既有 T15/T16 区域）。

---

## 5. 判定公式 / SLA / 分级示例对照（标准 §6 输出格式要求）

### 5.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| QA-FIX-01（[CHAIN-COMPLETE] 误报） | ✅（链停推进） | ✅（自动续棒失效） | ✅（OC 手动建卡） | 否 | 否 | **MAJOR**（已修复验证） |
| QA-FIX-02（T22a 门禁 fixture 过时） | ✅（测试门禁红） | ✅（回归保护失效） | ✅（隔离复现 B + 1 行 fixture 修复） | 否 | 否 | **MAJOR** |

### 5.2 SLA 对照（标准 §8）

| 发现 | 级别 | 响应 | 定位（初步判定） | 方案 | 当前状态 |
|------|:---:|:---:|:---:|:---:|:---:|
| QA-FIX-01 | MAJOR | 4h 内 | 8h 内（QA 已实机复现 + 证据链完整） | 24h 内（方案 A） | ✅ 已修复（7923eff）+ QA 复测 |
| QA-FIX-02 | MAJOR | 4h 内 | 8h 内（QA 已实机复现 + 根因定位 87de82c 漏改 L629） | 24h 内（本报告 §3 修复方向） | ⚠️ 待研发评估/修复 |

### 5.3 分级示例对照（标准 §5 表）

- QA-FIX-02 对照示例 16（"日志持续报 ERROR 但功能正常"→ 关键路径静默失败 → MAJOR）：T22a 是 QA-FIX-01 的**关键回归门禁**，其失效使修复保护静默失效 → 同构，**MAJOR** 成立
- 对比 BLOCKER 门槛：无资金/核心数据一致性、无 OOM、无安全漏洞、无概率性核心 bug → 不满足 BLOCKER
- 对比 MINOR（"用户能忍"）：测试门禁红导致后续所有 QA/VA 运行被污染，且门禁失去信息量（修复正确与否不可区分），非"能忍"级别

---

## 6. 发布门禁对照（标准 §10）

| 门禁项 | 要求 | 当前 | 结果 |
|--------|------|------|:---:|
| BLOCKER | =0 | 0 | ✅ |
| MAJOR | ≤3 | 1（QA-FIX-02） | ✅ |
| 安全漏洞 | =0 | 0 | ✅ |
| 未裁定申诉 | =0 | 0 | ✅ |

**结论**：门禁数字上未越过，但 QA-FIX-02 需修复（建议 OC 建 FIX 卡）使 T22a 回归门禁转绿后再算链级门禁闭环。

---

## 7. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | T22a 长期红 → 团队习惯性忽略测试 FAIL | 真实回归被掩盖 | 尽快修复 fixture（1 行）；QA 复测转绿 |
| R2 | T22b fixture 未同步补 dev-est（当前被真标记跳过掩盖） | 后续链结构调整时 T22b 也可能红 | 建议修复时一并对齐 |
| R3 | T23-T28 方案用例未入脚本 | 覆盖缺口 | 建议修复 QA-FIX-02 时补 T23-T25 断言 |
| R4 | 生产代码无缺陷但门禁红 → 误判 QA-FIX-01 复发 | 错误回滚 | 本报告 §2.3 复现证据（Scenario B）作为对照基线 |

---

## 附：QA 侧交付物

| 交付物 | 路径 | 状态 |
|--------|------|:---:|
| 本测试报告 | `docs/qa/fix-cmd-chain-complete-test-report.md` | ✅ 本次产出 |
| 测试方案（前棒） | `docs/qa/fix-cmd-chain-complete-test-plan.md` | ✅ t_50c4ead1 |
