# QA-EXEC 测试报告 — FIX notify heartbeat 统计范围限定到当前开发链

> 版本：v1.0 | 日期：2026-08-11 | 作者：game-qa（独立测试执行）
>
> 任务卡：t_34901e64 [DEV-QA-EXEC] FIX notify heartbeat 统计范围限定到当前开发链
> D1 测试方案：`docs/qa/fix-notify-heartbeat-chain-scope-test-plan.md`（commit 361ddbf）
> 被测基线：main @ 7889bc6（部署版本，含 F-9 + 5afb7e6 连字符修复 + 6a05fbd merge）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0

---

## 0. 执行摘要

| 项 | 结果 | 说明 |
|---|:---:|---|
| py_compile 静态检查 | ✅ | notify_check.py + test_notify_check.py 编译通过 |
| 基线 test_notify_check.py | ✅ **56/56 PASS** | T1-T19（含 F-9 sleep/wake）无回归 |
| 新增用例 T20（混合源盲区） | 🔴 **FAIL** | QA-D1-01 确认存在 — 活跃0 跑0 堵0 而 pipeline running |
| 新增用例 T21（混合源+blocked） | 🔴 **FAIL** | QA-D1-01 变体 — 堵0 而 pipeline blocked |
| 新增用例 T22（连字符步骤） | ✅ PASS | qa-d1/va-claim 解析正确（5afb7e6 修复生效） |
| 新增用例 T23（blocked 链卡） | ✅ PASS | 堵1 + ACTIVE 正确 |
| 新增用例 T24（归档清理 ADR-7） | ✅ PASS | snapshot 立即清除 |
| 新增用例 T25（真实 board 核对） | ✅ PASS | 活跃2 跑2 堵0 今完15 与 board 一致 |
| 回归 workspace_check.sh | ✅ **27/27 PASS** | B2 无回归 |
| 回归 cmd_channel.sh | ✅ **78/78 PASS** | B3 无回归 |

**总断言数**：56（基线） + 10（新增 PASS） + 2（新增 FAIL） = 68 断言，66 PASS / 2 FAIL

**结论**：

被测 FIX 的**核心路径正确**——真实 board 数字核对一致（活跃2 跑2 堵0 今完15），连字符步骤解析正确，legacy 自动回退/逃生阀/归档退出统计全部生效，存量 T1-T19 无回归，B2/B3 回归全绿。

D1 阶段发现的 **QA-D1-01（MAJOR）混合信号源盲区仍未修复**（T20/T21 FAIL 确认）。该缺陷在链卡全 done-今日 + pipeline 有活跃步骤时导致 heartbeat 报 活跃0 跑0 堵0，与 pipeline 实际状态完全脱节。**当前 board 即将进入该状态**（本任务与 t_5f9f1633 完成后），heartbeat 将立即失真。

---

## 1. 测试环境

| 项 | 配置 |
|---|---|
| Worktree | /workspace/devPPL/.worktrees/t_34901e64（branch wt/t_34901e64） |
| HEAD | 7889bc6（main 部署版本） |
| 执行脚本 | scripts/test_notify_check.py（基线 56 断言）+ scripts/test_notify_exec_qa.py（新增 T20-T25） |
| 隔离策略 | fixture tempfile（pipeline/notify/kanban 三库隔离）；T25 只读生产库 compute_counts |
| 执行时间 | 2026-08-11 18:12-18:15 CST |

---

## 2. 详细结果

### 2.1 基线 56 断言（T1-T19） — 全部 PASS

```
T1:  飞书 token 缓存（验收 1）               3/3 ✓
T2:  heartbeat work-gated（验收 2）           5/5 ✓
T3:  事件推断 + 去重（验收 3）                5/5 ✓
T4:  三路经独立（验收 4）                    3/3 ✓
T5:  fail-open（验收 5）                     4/4 ✓
T6:  7 天清理（验收 6）                      2/2 ✓
T7:  [CMD] ACTIVE + 格式                     3/3 ✓
T8:  dry-run 不污染                          2/2 ✓
T9:  B1-F1 回归 S1                          3/3 ✓
T10: B1-F1 回归 S2                          3/3 ✓
T11: 链卡 running → ACTIVE（AC-1）           2/2 ✓
T12: 多棒在途（AC-2）                        2/2 ✓
T13: archived 排除（AC-4）                   2/2 ✓
T14: 无链卡→legacy 回退（AC-6）              2/2 ✓
T15: stats_scope=legacy 逃生阀               1/1 ✓
T16: 链卡 done→annex（ADR-5）                4/4 ✓
T17: 链 done 非今日→IDLE（AC-5）             2/2 ✓
T18: 缺列 fail-open（AC-7）                  2/2 ✓
T19: F-9 sleep/wake                          6/6 ✓
────────────────────────────────────────────
合计                                        56/56 ✓
```

**无回归**：所有存量用例与 D1 阶段独立复跑结果一致。

### 2.2 新增用例 T20-T25

#### T20: 混合源盲区回归 — 🔴 FAIL（QA-D1-01 确认）

```
前置: 链卡 2 张 done-今日（无在途） + pipeline 1 条 running
输出: [AP 18:15] 活跃0 跑0 堵0 今完2
T20a: ACTIVE 仍成立（推 heartbeat）            ✓
T20b: 修复后活跃N ≥ 1                          ✗ FAIL（活跃0 跑0 堵0）
```

**分析**：chain_relevant=True（done-今日），数字来自链卡 compute_chain_counts → 活跃0 跑0 堵0 今完2。但 pipeline 有 1 条 running，is_active() 看 pipeline 返回 ACTIVE=True → heartbeat 照推但数字完全脱节。**与 D1 测试方案 §3 预测完全一致**。

#### T21: 混合源 + pipeline blocked — 🔴 FAIL（QA-D1-01 变体）

```
前置: 链卡 1 张 done-今日 + pipeline 1 条 blocked
输出: [AP 18:15] 活跃0 跑0 堵0 今完1
T21a: ACTIVE=true                              ✓
T21b: 修复后堵N ≥ 1                            ✗ FAIL（堵0 而 pipeline blocked）
```

**分析**：同 T20，链卡 done-今日导致 chain_relevant=True → 堵0 掩盖 pipeline blocked 步骤。

#### T22: 连字符步骤（qa-d1/va-claim） — ✅ PASS

```
前置: 链卡 qa-d1 running + va-claim ready
输出: [AP 18:15] 活跃2 跑1 堵0 今完0
T22a: read_dev_chain_cards 含 qa-d1 + va-claim 完整步骤名    ✓
T22b: 活跃2 跑1 堵0 今完0                                     ✓
```

**分析**：5afb7e6 的 split('-',2) 修复正确生效。qa-d1/va-claim 不再被静默跳过。QA-D1-02（MINOR）的回归门禁已锁死。

#### T23: blocked 链卡 — ✅ PASS

```
前置: 链卡 dev blocked
输出: [AP 18:15] 活跃0 跑0 堵1 今完0
T23a: ACTIVE=true（推 heartbeat）                ✓
T23b: 数字=活跃0 跑0 堵1 今完0                    ✓
```

**分析**：blocked 链卡正确计入堵N 并触发 ACTIVE。补齐 AC-1 缺测。

#### T24: 归档链卡 snapshot 立即清理（ADR-7） — ✅ PASS

```
前置: 链卡 running → tick → 置 archived → 再 tick
T24-pre: snapshot 含链卡 t_a1                    ✓
T24a: 归档后 pipeline_snapshot 无残留             ✓
```

**分析**：F-8 cleanup 保留集 = steps ids ∪ 非 archived 链卡 ids 生效，归档链卡快照立即删除。

#### T25: 真实 board 数字核对 — ✅ PASS

```
dev 链卡数: 17（board: 17）
board 核对: 活跃2 跑2 堵0 今完15
heartbeat: [AP 18:15] 活跃2 跑2 堵0 今完15
口径: chain
T25a: compute_counts 口径判定正确                ✓
T25b: heartbeat 数字与 board 实况一致             ✓
```

**分析**：当前 board 有 2 张 qa-d1 running（本任务 + MEM-001），17 张 dev 链卡非归档（15 今日完成）。compute_counts 走 chain 口径，数字与 board 完全一致。**注意**：当本任务完成后，board 将进入 T20 描述的盲区状态。

### 2.3 回归测试

| 测试套件 | 结果 | 范围 |
|----------|:----:|------|
| test_workspace_check.sh | ✅ **27/27 PASS** | B2 workspace_check 合规扫描 + 内容注入 |
| test_cmd_channel.sh | ✅ **78/78 PASS** | B3 指令卡通道 + cmd_chain 12 棒完整流程 |

**零改动确认**：本 FIX 不触碰 autopilot/cmd_channel/discover/cmd_chain/constants/workspace_check，回归全部通过。

---

## 3. 发现汇总（与 D1 一致，无新增）

### 发现状态对照

| 发现 | 级别 | D1 状态 | EXEC 验证 | 当前状态 |
|------|:----:|---------|-----------|:--------:|
| QA-D1-01 混合信号源盲区 | **MAJOR** | 实机复现 | T20/T21 FAIL 确认 | **待研发 FIX** |
| QA-D1-02 连字符步骤缺测 | MINOR | 建议补测 | T22 PASS（锁死） | ✅ 已补测 |
| QA-D1-03 PRD/arch 文档未上 main | MINOR | 文档追踪 | — | 待 OC/研发处置 |

### 3.1 QA-D1-01（MAJOR）— EXEC 复现证据

**T20 实测输出**：
```
[AP 18:15] 活跃0 跑0 堵0 今完2
```
链卡全 done-今日（2 张）+ pipeline running（1 条）→ heartbeat 报活跃0 而pipeline 实际在跑。ACTIVE=True（is_active 看 pipeline），但数字来自链卡（chain_relevant=True → 活跃0）。

**T21 实测输出**：
```
[AP 18:15] 活跃0 跑0 堵0 今完1
```
链卡 done-今日 + pipeline blocked → 堵0 掩盖 pipeline blocked。

**判定公式对照（标准 §1.2）**：

| 条件 | 结果 | 说明 |
|------|:----:|------|
| ① 存在缺陷 | ✅ | T20/T21 实测复现 |
| ② 用户可感知 | ✅ | heartbeat 数字与 pipeline 真实状态脱节 |
| ③ 非安全漏洞 | ✅ | — |
| ④ 影响核心功能 | ✅ | heartbeat 信号失真（本 FIX 核心交付物） |
| ⑤ workaround | ✅ | 查 board/autopilot.log |
| **分级** | **MAJOR** | 用户可感知 AND 功能阻断 AND 有 workaround |

**SLA 对照（标准 §8）**：MAJOR → 1 工作日响应 + 2 工作日定位。QA 已提供完整复现（T20/T21 断言 + 实测输出）+ 修复方向（D1 测试方案 §3 方案 A/B）。**待研发评估**。

### 3.2 QA-D1-02（MINOR）— 已关闭

T22 已将连字符步骤解析锁死为回归门禁（qa-d1/va-claim 完整步骤名 + 活跃2 跑1 堵0 今完0 断言通过）。5afb7e6 修复不再有无测试覆盖状态。

---

## 4. 判定公式 / SLA / 发布门禁对照

### 4.1 发布门禁（标准 §10）

> BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉

- BLOCKER = 0 ✅
- MAJOR = 1（QA-D1-01）⚠️ → 未越过门禁，需修复或标注 known issue
- 安全漏洞 = 0 ✅
- 未裁定申诉 = 0 ✅

**门禁判定**：MAJOR=1 ≤ 3，**可发版但需标注 known issue**（标准 §1.1：MAJOR 发版需标注）。建议在发布说明中注明「heartbeat 在链卡全 done-今日 + pipeline 活跃时数字失真，查 board 可获取准确状态」。

### 4.2 SLA 对照（标准 §8）

| 发现 | 级别 | 响应 | 定位 | 方案 | 当前 |
|------|:----:|:----:|:----:|:----:|:----:|
| QA-D1-01 | MAJOR | 1 工作日 | 已完成（T20/T21 复现） | D1 方案 A/B | 待研发评估 |
| QA-D1-02 | MINOR | — | — | T22 已补测 | ✅ 已关闭 |
| QA-D1-03 | MINOR | — | — | merge 合入文档 | 待处置 |

---

## 5. 处置建议

### 5.1 QA-D1-01（MAJOR）— 待 OC 建研发 FIX 卡

QA 不建 FIX 卡（建卡铁律：QA 只测不改）。建议 OC 为 QA-D1-01 建研发 FIX 卡，修复方向（D1 测试方案 §3）：

- **方案 A（推荐）**：chain_relevant() done-今日分支增加 pipeline 活跃检查——链 done-今日 且 pipeline 无 pending/running/blocked 才保持链卡口径；pipeline 有活跃时回退 legacy。
- **方案 B**：compute_counts() 在 chain_relevant=True 但链卡无在途时，将 pipeline 活跃数并入。

修复后 T20/T21 应转为 PASS（活跃N ≥ 1 / 堵N ≥ 1）。

### 5.2 QA-D1-03（MINOR）— 文档合入

PRD（docs/prd/fix-notify-heartbeat-chain-scope-prd.md）和架构文档（docs/arch-fix-notify-heartbeat-chain-scope.md）仅在链分支上存在，main 上不存在。建议 merge 时一并合入。

---

## 6. 测试产物

| 产物 | 路径 |
|------|------|
| D1 测试方案 | docs/qa/fix-notify-heartbeat-chain-scope-test-plan.md（commit 361ddbf, branch wt/t_d3f1e173） |
| **EXEC 测试报告（本文档）** | docs/qa/fix-notify-heartbeat-chain-scope-test-report.md |
| 新增用例脚本 | scripts/test_notify_exec_qa.py（T20-T25 执行脚本） |

---

## 7. 附录：执行命令与输出

### 7.1 基线复跑

```bash
$ python3 scripts/test_notify_check.py
RESULTS: 56 PASS / 0 FAIL
```

### 7.2 新增用例

```bash
$ python3 scripts/test_notify_exec_qa.py
── T20: 混合源盲区 ──
  ✓ T20a: ACTIVE 仍成立
  ✗ T20b: 活跃0 跑0 堵0 今完2 [QA-D1-01 确认]
── T21: 混合源 + blocked ──
  ✓ T21a: ACTIVE=true
  ✗ T21b: 堵0 而 pipeline blocked [QA-D1-01 变体]
── T22: 连字符步骤 ──
  ✓ T22a/T22b: qa-d1/va-claim 完整解析 + 活跃2 跑1 堵0 今完0
── T23: blocked 链卡 ──
  ✓ T23a/T23b: 堵1 + ACTIVE
── T24: 归档清理 ──
  ✓ T24a: snapshot 无残留
── T25: 真实 board 核对 ──
  ✓ T25a/T25b: 活跃2 跑2 堵0 今完15 一致
RESULTS: 10 PASS / 2 FAIL
```

### 7.3 回归

```bash
$ bash scripts/test_workspace_check.sh
PASS=27 FAIL=0  ALL TESTS PASSED

$ bash scripts/test_cmd_channel.sh
PASS=78 FAIL=0  ALL TESTS PASSED
```
