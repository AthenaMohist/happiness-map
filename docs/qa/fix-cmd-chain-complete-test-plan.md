# FIX cmd_chain 开发链补全 — QA D1 测试方案（test_plan.md）

> 版本：v1.0 | 日期：2026-08-11 | 作者：game-qa（独立测试方案，非研发自测）
>
> 任务卡：t_50c4ead1 [DEV-QA-D1] FIX cmd_chain 开发链补全 — dev 后接 va-claim/QA/VA/merge 完整流程
> 被测提交：9ca1d02（已 merge 到 main f347fee；VA 验证 9/9 VERIFIED t_39bd7664）
> 上游文档：
> - PRD：`docs/prd/fix-cmd-chain-complete-dev-flow-prd.md`（v1.0，commit 5b45e05，t_eaaf5f27）
> - 架构：`docs/arch-fix-cmd-chain-complete-dev-flow.md`（v1.0，commit a8f7b53，t_ae8d172f）
> - 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> - 基线测试：`scripts/test_cmd_channel.sh`（78 断言，T1-T21 + R1-R3）

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| 基线复跑 `scripts/test_cmd_channel.sh` | ✅ 78/78 PASS（QA 独立复跑，2026-08-11） |
| 静态核对（12 棒定义 / 解析修复 / 消费段 / dedup 排除） | ✅ 与 arch v1.0 一致（详见 §4.2） |
| 真实板核对（b9cb8c1763 链推进） | ⚠️ 见 D1 前置发现（§3） |
| **D1 发现** | **MAJOR × 1**（QA-FIX-01：`[CHAIN-COMPLETE]` 跳过误报） |

**结论**：被测提交的 12 棒推进 / merge/close 自消费 / [CHAIN-COMPLETE] 跳过逻辑主体实现正确、基线 78 断言全绿。但 D1 测试设计阶段发现 1 个 **MAJOR**（`[CHAIN-COMPLETE]` 标记误报，已在真实板复现——本链自身 qa-d1 因此被跳过、需手动补建），修复（FIX 卡 t_8aa9fbeb）未落地，需在测试执行前/执行中关闭。本方案将误报场景纳入新增用例 T22（回归门禁）。

---

## 1. 测试范围概览

```
被测模块                           PRD AC 覆盖       arch ADR        新增/扩展
──────────────────────────────────────────────────────────────────────────────
pipeline/constants.py (147行)     AC-1/AC-2/AC-3     ADR-1           12 棒 + SELF_CONSUMED_STEPS
pipeline/cmd_chain.py (714行)     AC-1~AC-8           ADR-2~7,9,10    +_parse_dev_key/_topic_from_title/
                                                      _chain_context/exec_chain_merge/exec_chain_close
scripts/cmd_channel.sh (455行)    AC-3/AC-3b         ADR-3/4         +链卡消费段（第 5 段）
scripts/dedup_check.sh (252行)    AC-8               ADR-8           +[DEV- 排除（1 行）
scripts/test_cmd_channel.sh       AC-1~AC-8          §5.2            T13-T21（78 断言）+ 本方案 T22+
```

**零改动确认（回归范围）**：autopilot.sh / discover.py / notify_check.py / workspace_check.sh / stuck_check.sh / state.py / backup.py / contracts.jsonl —— 本 FIX 不触碰，需回归验证不破坏。

### 1.1 验收标准映射（PRD §5.2）

| AC | 验收要点 | 测试用例 | 状态 |
|----|---------|---------|:---:|
| AC-1 | dev done → 自动建 [DEV-VA-CLAIM]（assignee=verifier） | T13a-c | ✅ 已有 |
| AC-2 | 全链 12 棒顺序、每棒仅 1 卡（幂等） | T14a-b | ✅ 已有 |
| AC-3 | merge 被消费执行 → done → 建 qa-post | T15a-f | ✅ 已有 |
| AC-3b | merge 合并 wt/t_<dev卡> 分支，不合并无关分支 | T15b/T15d-e | ✅ 已有 |
| AC-4 | 连字符步骤解析（va-claim 不被跳过） | T13a/T19b | ✅ 已有 |
| AC-5 | 标题提取（不回退 spec_hash） | T19a | ✅ 已有 |
| AC-6 | 产物追溯注入（qa-exec body 含 test_plan/dev/spec） | T17a-d | ✅ 已有 |
| AC-7 | 失败卡可见（blocked + [cmd-chain] comment） | T16b1-b2 | ✅ 已有 |
| AC-8 | [CHAIN-COMPLETE] 存量链跳过 | T18a-b | ⚠️ 仅真标记方向；**误报方向缺测（T22 新增）** |

---

## 2. 测试环境与方法

与既有基线一致（隔离，不触碰真实 board）：

| 项 | 配置 |
|---|---|
| 隔离 kanban.db | 复制真实 schema → 清空 → 插入受控行（`/tmp/cmdchan-test/kanban.db`） |
| 隔离 pipeline_state.db | `/tmp/cmdchan-test/pipe.db`（CheckpointDB ensure_schema） |
| 隔离 git 仓库 | `/tmp/cmdchan-test/gitrepo`：main + `wt/t_<dev卡id>` + 无关分支（merge/close 执行靶） |
| 环境变量 | `HERMES_KANBAN_DB` / `PIPELINE_STATE_DB` 指向 temp；`PYTHONPATH=$REPO_ROOT` |
| 执行命令 | `bash scripts/test_cmd_channel.sh`（78 断言基线）+ 新增 T22+ 断言 |

**执行前置**：
1. `bash -n scripts/cmd_channel.sh scripts/test_cmd_channel.sh scripts/dedup_check.sh` 语法检查
2. `python3 -m py_compile pipeline/cmd_chain.py pipeline/constants.py`
3. 基线复跑 78 断言全绿后，再执行新增用例

---

## 3. ⚠️ D1 前置发现（测试设计阶段）

### QA-FIX-01（MAJOR）：`[CHAIN-COMPLETE]` 跳过逻辑误报——comment 正文提到该词即误判整组跳过

**位置**：`pipeline/cmd_chain.py` L368-378（advance_sequential_chains 的 marked 检查）

**缺陷描述**：
```python
marked = conn.execute(
    "SELECT 1 FROM task_comments WHERE task_id IN (...) AND body LIKE '%%[CHAIN-COMPLETE]%%' LIMIT 1"
)
```
`LIKE '%[CHAIN-COMPLETE]%'` 是**任意位置子串匹配**——只要组内任一卡的任何 comment **提到**了 "[CHAIN-COMPLETE]" 这个词（哪怕在解释文档、说明文字、正文里），整组就被误判为"已标记跳过"，链不再推进。

**真实板复现（不可辩驳的证据）**：本 FIX 自己的开发链 dev-b9cb8c1763——

| 卡 | comment 作者 | comment 正文含该词的上下文 |
|---|---|---|
| t_eaaf5f27（PRD） | game-director #928 | "5. 存量 2 条旧链处置：PRD §7 D1 待 Frank 裁决，默认建议 **[CHAIN-COMPLETE]** 标记跳过" |
| t_ae8d172f（ARCH） | game-architect #929 | "D1 存量链：机制已实现（**[CHAIN-COMPLETE]** comment 跳过）" |
| t_e8bf805f（DEV） | game-engine #930 | "advance_sequential_chains 改 5 点（…**[CHAIN-COMPLETE]** 组跳过…）" |
| t_39bd7664（VA-CLAIM） | verifier #933 | "advance_sequential_chains 5 改点（**[CHAIN-COMPLETE]** 组跳过…）" |

QA 用真实库复现 advance 的 marked 查询：**Skip triggered = True**（整组被跳过）。
实际后果：dev 链 5 棒全 done 后，advance 本应在下一 tick 自动建 `[DEV-QA-D1]`（本任务 t_50c4ead1），**因误报被跳过 → OC 手动补建**（本任务来源注明"手动补建 qa-d1——advance 因 [CHAIN-COMPLETE] 误报未自动建"）。

**FIX 卡处置状态**：t_8aa9fbeb（`[CMD] create dev FIX [CHAIN-COMPLETE] 标记误报`）已消费归档，但 **无修复落地**：
- 代码仍为 `LIKE '%[CHAIN-COMPLETE]%'`（cmd_chain.py L373 未变）
- 无对应 FIX 开发链（无 [DEV-PRD] 卡、无修复 commit）
- 该 FIX 指令卡消费后无回执 comment（cmd_channel 建链失败静默）

**分级判定（对照标准 §1.2 五步公式）**：
- ① 存在缺陷 ✅（真实板复现：Skip triggered=True，qa-d1 被迫手动补建）
- ② 用户可感知 ✅（链卡停推进、下游卡不自动创建，OC/Frank 查板可见断链）
- ③ 非安全漏洞 ✅
- ④ 影响核心功能 ✅（开发链自动推进 = 本 FIX 核心能力；误报使"自动续棒"失效）
- ⑤ 分级：用户可感知 AND 功能阻断（自动续棒失效）AND 有 workaround（OC 手动建卡）→ **MAJOR**（非 BLOCKER，因为存在手动补建 workaround）

**SLA 对照（标准 §8）**：MAJOR 8h 定位（QA 已实机复现）+ 24h 方案（建议修复方向见下）→ 需研发评估并给出修复方案。

**建议修复方向（供研发评估，QA 不代修）**：
- marked 检查应只匹配**专用标记**而非任意正文提到：
  - 方案 A（推荐）：`body LIKE '[CHAIN-COMPLETE]%'`（仅匹配以标记开头的 comment，如 OC 标记格式 `[CHAIN-COMPLETE] 存量链已完成…`）
  - 方案 B：匹配 `[CHAIN-COMPLETE]` 后跟换行/结尾（`%[CHAIN-COMPLETE]\n%` 或 `%[CHAIN-COMPLETE]%` 收紧为 `LIKE '[CHAIN-COMPLETE]%' OR LIKE '%\n[CHAIN-COMPLETE]%'`，防误伤正文行内提到）
  - 无论哪种：**新增回归测试 T22**（见 §4.3）锁死误报场景。

**影响面评估**：当前真实板仅 dev-b9cb8c1763 受影响（其 4 张卡的交付 comment 均含该词）；dev-af032394f6 / dev-fc7aca36db 两条存量链的 dev 卡有**真实** [CHAIN-COMPLETE] 标记（worker 发的专用标记，body 以 `[CHAIN-COMPLETE]` 开头）——方案 A 下仍正确跳过（不受影响）；新链（后续创建的普通开发链）在交付 comment 中不提及该词，不会误触发。

---

## 4. 测试用例设计

### 4.1 基线 78 断言（研发已有，QA 独立复跑确认）——按需求域归类

| 需求域 | 用例 | 断言数 | 说明 |
|--------|------|:---:|------|
| 12 棒推进 | T13（dev done → va-claim）、T14（全链 12 棒顺序） | 5 | AC-1/AC-2/AC-4 |
| merge/close 自消费 | T15（merge 消费→done→qa-post）、T15b（分支正确）、T16（close 消费→done→链结束）、T16b（S6' 失败→blocked）、T21（消费幂等） | 13 | AC-3/AC-3b/AC-7 |
| 产物追溯注入 | T17（qa-exec body 含 qa-d1/test_plan/dev/spec） | 4 | AC-6 |
| [CHAIN-COMPLETE] 跳过 | T18a（真标记→跳过）、T18b（新链不受影响） | 2 | AC-8（真标记方向） |
| 解析修复 | T19（连字符步骤标题提取 + split('-',2) 幂等键） | 2 | AC-4/AC-5 |
| dedup 排除回归 | T20（两条 [DEV-MERGE] 共存不被归档） | 2 | ADR-8 |
| 回归 | R1-R3（discover 不注册 [ROUNDTABLE-/DEV-，普通卡仍发现） | 3 | B2 回归 |
| 存量 B3 回归 | T1-T12（[CMD] 消费/建链/幂等/控制面/容错/滞留） | 47 | B3 回归 |

### 4.2 静态核对清单（QA 独立代码核对）

| # | 核对项 | 依据 | 结果 |
|---|--------|------|:---:|
| S1 | DEVELOPMENT_CHAIN = 12 棒，顺序 prd→…→close，与 contracts.jsonl STEP_NAMES 对齐 | constants.py L70-83 | ✅ |
| S2 | SELF_CONSUMED_STEPS = {merge, close}，assignee=autopilot | constants.py L86 | ✅ |
| S3 | _parse_dev_key split('-',2) 支持连字符步骤 | cmd_chain.py L193-206 | ✅ |
| S4 | _topic_from_title 正则 `[DEV-[^\]]+]` 兼容 12 种标题 | cmd_chain.py L209-216 | ✅ |
| S5 | advance 每 tick 每链最多推进 1 棒（break） | cmd_chain.py L410 | ✅ |
| S6 | merge/close 卡不传 workspace（ADR-9） | cmd_chain.py L396 | ✅ |
| S7 | cmd_channel.sh 链卡消费 CAS ready→running→done/blocked（终态 done 非 archived） | cmd_channel.sh L338-430 | ✅ |
| S8 | dedup_check 排除 `[DEV-` 前缀 | dedup_check.sh L87 | ✅ |
| S9 | merge 分支双路径（body 'dev 卡:' → 幂等键反查）+ rev-parse 校验 | cmd_chain.py L421-448, L475-480 | ✅ |
| S10 | close S6' 检测源 = kanban 链卡（非 pipeline_steps），11 棒全 done | cmd_chain.py L541-555 | ✅ |
| S11 | [CHAIN-COMPLETE] 跳过检查 | cmd_chain.py L368-378 | ⚠️ **误报（QA-FIX-01）** |

### 4.3 新增用例（本方案扩展，测试执行时并入 test_cmd_channel.sh）

| # | 场景 | 前置 | 断言 | 对应缺陷/ADR |
|---|------|------|------|-------------|
| **T22** | **[CHAIN-COMPLETE] 误报回归（关键）**：组内卡 comment 正文提到该词（非专用标记）→ 链**仍推进** | 建链 prd/arch/dev done；对 dev 卡发 comment "D1 处置建议 **[CHAIN-COMPLETE]** 标记跳过"（正文中间提到，非以标记开头） | T22a: 下一 tick 仍建 va-claim（count=1） | **QA-FIX-01** |
| T22b | [CHAIN-COMPLETE] 专用标记仍跳过（防修复过度） | 对 dev 卡发 comment 以 `[CHAIN-COMPLETE]` 开头 | T22b: 不建 va-claim（count=0） | ADR-7 回归 |
| T23 | merge/close 卡 workspace_kind = scratch（ADR-9 实测断言） | T15 同 fixture | T23a: merge 卡 workspace_kind=scratch；T23b: close 卡 workspace_kind=scratch；T23c: va-claim/qa-d1 等 worker 卡 workspace_kind=worktree | ADR-9 |
| T24 | merge 失败路径：分支不存在 → blocked + [cmd-chain] comment | merge:ready，dev 卡分支 wt/t_<id> 不存在 | T24a: status=blocked；T24b: comment 含 [cmd-chain] | ADR-4/F-9 |
| T25 | merge 失败路径：当前分支非 main/master → 拒绝合并 | 隔离 git repo 检出 wt/t_unrelated 后执行 | T25a: status=blocked；T25b: git log 无 merge commit | ADR-4 AC-3b |
| T26 | 两链并行互不干扰 | 链 A 推进到 va-claim done；链 B 仅 prd done | T26a: A 建 qa-d1；T26b: B 不提前建 arch | ADR-1 幂等 |
| T27 | advance 扫描含 archived 卡防重（幂等第二道） | 链卡含一张 archived 的 va-claim + dev done | T27a: 不重复建 va-claim；T27b: 正常推进下一棒 | ADR-10 |
| T28 | 真实板核对：b9cb8c1763 链卡齐全 + 无 [DEV- 异常残留 | 真实 /root/.hermes/kanban.db 只读查询 | T28a: 链卡 prd→qa-d1 齐全；T28b: 无活跃 [DEV-MERGE]/[DEV-CLOSE] 卡滞留 ready>3tick | 环境核对 |

**门禁判定**：T22a 在修复前必然 FAIL（误报存在）——T22 作为回归用例必须在 FIX 卡（t_8aa9fbeb 重建的修复链）交付后通过；其余新增用例（T23-T28）当前基线可直接执行验证。

---

## 5. 判定公式 / SLA / 分级示例对照（标准 §6 输出格式要求）

### 5.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| QA-FIX-01（[CHAIN-COMPLETE] 误报） | ✅（链停推进） | ✅（自动续棒失效） | ✅（OC 手动建卡） | 否 | 否 | **MAJOR** |

### 5.2 SLA 对照（标准 §8）

| 发现 | 级别 | 响应 | 定位（初步判定） | 方案 | 当前状态 |
|------|:---:|:---:|:---:|:---:|:---:|
| QA-FIX-01 | MAJOR | 4h 内 | 8h 内（QA 已实机复现 + 证据链完整） | 24h 内（本方案 §3 给出修复方向） | 待研发评估 |

### 5.3 分级示例对照（标准 §5 表）

- QA-FIX-01 对照示例 17（"列表页偶发白屏，刷新后恢复"= MAJOR：用户可感知 + 功能阻断 + 有 workaround）→ 同构，**MAJOR** 成立
- 对比 BLOCKER 门槛：无资金/核心数据一致性、无 OOM、无安全漏洞、无概率性核心 bug → 不满足 BLOCKER

---

## 6. 测试执行与交付

### 6.1 执行步骤（qa-exec 阶段）

```bash
cd /workspace/devPPL

# 1. 静态检查
bash -n scripts/cmd_channel.sh scripts/test_cmd_channel.sh scripts/dedup_check.sh
python3 -m py_compile pipeline/cmd_chain.py pipeline/constants.py

# 2. 基线复跑（78 断言）
bash scripts/test_cmd_channel.sh          # 期望 PASS=78 FAIL=0

# 3. 新增用例（T22 需 FIX 落地后；T23-T28 可直接执行）
#    —— 并入 test_cmd_channel.sh 或独立扩展脚本

# 4. 回归范围
bash scripts/test_workspace_check.sh      # 期望 PASS=27 FAIL=0
```

### 6.2 交付物

| 交付物 | 路径 |
|--------|------|
| 本测试方案 | `docs/qa/fix-cmd-chain-complete-test-plan.md` |
| （qa-exec 产出）测试报告 | `docs/qa/fix-cmd-chain-complete-test-report.md` |

### 6.3 发布门禁对照（标准 §10）

- BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉
- 当前：BLOCKER=0，**MAJOR=1**（QA-FIX-01）→ 未越过门禁，但 MAJOR 需在发布前修复或标注 known issue（标准 §1.1）

---

## 7. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | FIX 卡 t_8aa9fbeb 消费但修复未落地，后续链继续被误跳 | 开发链自动推进持续失效 | 测试执行前由 OC 重建 FIX 卡给研发；T22 作为回归门禁 |
| R2 | merge/close 测试误触真实主仓库 git merge | 污染 main | 全部测试走隔离 git 仓库（`/tmp/cmdchan-test/gitrepo`）；生产路径 REPO_ROOT 显式传入 |
| R3 | 新增用例 T22 在修复前 FAIL，基线从 78 变 79 | 误读为回归 | T22 标注"FIX 前置"，门禁判定按 §4.3 |
| R4 | 真实板核对（T28）依赖只读查询 | 无写入风险 | 仅 SELECT；不触碰真实库写入 |

---

## 附：与本方案相关的既有文档

- B3 指令卡通道验证：`docs/qa/cmd-channel-verification.md`、`docs/qa/retest-b3-cmd-channel.md`
- 10 步管线 v2：`config/contracts.jsonl` + `pipeline/constants.py` STEP_NAMES
- notify heartbeat 链卡口径：`scripts/notify_check.py` read_cmd_cards
