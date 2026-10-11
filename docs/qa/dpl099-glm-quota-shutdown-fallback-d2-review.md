> **[历史评审归档]** 本报告为 DPL-099 QA-D2 历史评审（t_00e0d32d，2026-09-04）。
> F1/F4/T58 MAJOR 发现已由 DPL-099 二次复发 FIX（t_d1351aa3 链）在 main 闭环；
> 报告中的代码行号/结论以评审时点为准，仅作验收证据归档，不代表 main 现状。

# DPL-099 QA-D2 结果严重度评审报告

> 版本：v1.0 | 日期：2026-09-01 | 作者：game-qa
>
> 任务卡：t_00e0d32d [DEV-QA-D2] GLM 额度耗尽自动停机 + 备用模型强制收尾存档（DPL-099）
> 被测对象：**devPPL main @ 8d1b468 + 7472b3b（DPL-103/104 漂移纳入）**
> 测试方案：`docs/qa/dpl099-glm-quota-shutdown-fallback-test-plan.md`（v1.0，D1 交付）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> 上游报告：`docs/qa/dpl099-glm-quota-shutdown-fallback-qa-exec-report.md`（QA-EXEC t_f08b2488）

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| 被测代码状态 | **main 含 DPL-099/103/104 全部产物**（7472b3b = main 8d1b468 同步进 worktree；`git branch -a --contains ee3dc58` 含 `wt/t_00e0d32d`） |
| 静态核查 | **S1-S12 全过（12/12）**（行号因 DPL-103/104 漂移微调，见 §3 对照表） |
| 新测试套件 | test_glm_quota_probe.sh **PASS=75 FAIL=0**（T5b PASS，佐证 F1 非污染） |
| 回归套件 | watchdog 28/0 ✅ / idle 19/0 ✅ / **drift 28/3 ❌（F4）** / **cmd_channel 390/8 ❌（F1+T58）** |
| devPPL pytest | **281 passed / 8 failed / 1 error** —— **零新增**（基线与 VA 一致） |
| D2 漏报探针 | **A-H 18/18 全过**（含 DPL-104 适配：G-2 双作业 pause / D-3 限频断言） |
| 新发现 | **F1-MAJOR**（stale .glm_shutdown 抑制 oc_wake_check）+ **F2-MINOR**（/tmp ts 文件硬编码）+ **F3-MINOR**（双出口告警）+ **F4-MAJOR**（drift 清单 6 项测试种子 5）+ **T58 新回归 6 断言**（chain env 回滚状态机） |
| 发布门禁 | **未通过**（BLOCKER=0 AND MAJOR=2>F1+F4 AND 安全漏洞=0）→ **需研发评估 F1/F4/T58** |

**结论**：DPL-099 核心逻辑四段函数完整 + A1-A7 验收成立 + pytest 零新增。**但 DPL-103/104 引入 F1+F4 两处 MAJOR 缺陷，以及 T58 env 重试状态机 6 断言新回归**，均需在发版前由研发裁定处置。**发布门禁未通过，暂不推荐发版**。

---

## 1. 前置检查

| # | 检查 | 结果 |
|---|---|---|
| 1 | 被测 commit 为 main 祖先 | ✅ `7472b3b` = main `8d1b468` 同步，`ee3dc58` 为 worktree 分支提交 |
| 2 | 5 文件 sha256 对照 | ✅ glm_quota_probe.sh = a811f675...（QA-EXEC 一致）；test_glm_quota_probe.sh = 2c3027f3...（一致） |
| 3 | bash -n ×7 | ✅ 全过（glm_quota_probe / test_glm_quota_probe / oc_wake_check / deploy_drift_check / test_deploy_drift / test_watchdog_unify / test_idle_check） |
| 4 | DPL-103/104 merge 范围 | ✅ `git diff 8864e51..main --stat` 仅 1 脚本（glm_quota_probe.sh L516+ 新增限频段） |
| 5 | QA-EXEC 报告可达性 | ⚠️ 报告在 dangling commit `668c13e`，未并入 main（OBS-B 继承） |

---

## 2. 测试执行结果

### 2.1 新测试套件 test_glm_quota_probe.sh（T1-T16，75 断言）

**PASS=75 FAIL=0**（TMPT 全量 env 打桩，GLM_FINALIZE_WORKSPACES=fixture REPO）

| 段 | 覆盖 | 结果 |
|---|---|---|
| T1a-T1e | 探针四态（A1） | ✅ 全过 |
| T2a-T2c | 连续 2 次熔断五维（A2） | ✅ 全过 |
| T3a-T3c | 机械收尾 + R5（A3） | ✅ 全过 |
| T4a-T4d | 分级恢复（A4） | ✅ 全过 |
| T5a-T5e | 真实环境零污染（A5） | ✅ 全过含 T5b（本次 tick md5 稳定） |
| T6a-T6c | 源 L 停机感知（A6） | ✅ 全过（fixture 内隔离，不受 stale 标记影响） |
| T7a-T7b | R7 登记（A7） | ✅ 全过 |

> **T5b 复核结论**：本次 PASS，佐证 F1（QA-EXEC 继承 flaky）为调度器 churn 而非产品缺陷。维持 SUGGESTION 改进方向不变。

### 2.2 回归套件（对 main@8d1b468+7472b3b）

| 测试 | 断言数 | 本卡实测 | 结果 |
|---|:---:|:---:|:---:|
| test_glm_quota_probe.sh | 75 | PASS=75 FAIL=0 | ✅ |
| test_deploy_drift.sh（含 T8 must-sync） | 31 | **PASS=28 FAIL=3** | ⚠️ **F4** |
| test_watchdog_unify.sh | 28 | PASS=28 FAIL=0 | ✅ |
| test_idle_check.sh | 19 | PASS=19 FAIL=0 | ✅ |
| test_cmd_channel.sh | 398 | **PASS=390 FAIL=8** | ⚠️ **F1 + T58** |

### 2.3 devPPL pytest 基线

```
HOME=/root python3 -m pytest tests/ -q
→ 281 passed / 8 failed / 1 error（479.36s）
```

- 失败集：`test_memory_middleware_qa` ×3（tc19/tc20/tc23）+ `test_slice2_d1_qa` ×5（TC14/TC09×3/BE01）+ `ERROR test_P2-02_full` ×1
- 与 VA 记录基线 **逐项一致，零新增**
- 零新增证据：`git diff 8864e51..main -- tests/test_memory_middleware_qa.py tests/test_slice2_d1_qa.py tests/test_P2-02_full.py` 为空

---

## 3. 静态核查（S1-S12，与 QA-EXEC 报告 §3 对照）

DPL-103/104 漂移导致行号微调，独立读码验证全部 12 项：

| # | 核查点 | QA-EXEC 行号 | 本卡实测行号 | 结果 |
|---|---|---|---|:---:|
| S1 | 四段函数存在 | probe L147 / shutdown L404 / finalize_mech L431 / recover L623 | probe **L148** / shutdown **L411** / finalize_mech **L438** / recover **L643** | ✅ |
| S2 | --inject 优先于网络请求 | L151-162 | L154-167 | ✅ |
| S3 | parse_reset_at 双格式 | L129-140 | L130-140 | ✅ |
| S4 | pause 双调度源 + D9 CLI 降级 | L233-287 | L239-293（含 HERMES_CMD 分支） | ✅ |
| S5 | D15 活跃卡 A∪B∪C 三 SQL | L293-359 | L312-378（段号漂移 +19） | ✅ |
| S6 | .glm_shutdown 原子写（tmp+mv） | L366-381 | L374-392 | ✅ |
| S7 | finalize N+2 工作区 + 失败清单不阻塞 + push 独立 try | L431-499 | L438-506 | ✅ |
| S8 | recover 时间闸门 + 窗口型三件套 / 无窗口只通知 + D7 + --force | L553-700 | L545-692（段号漂移 -8） | ✅ |
| S9 | R5 agnes 派发 D17 | L513-547 | L520-554（含 limit 判断新增） | ✅ |
| S10 | 探针绝不 pause 自己 | L59 | L59（未变） | ✅ |
| S11 | oc_wake_check 源 L 位置 + glm_tail + 跳过名单 | L698-777 | L698-777（未变） | ✅ |
| S12 | deploy_drift DEFAULT_SYNC_LIST 恰 6 项（DPL-103 加第 6 项） | L42: 5 项 | L45: **6 项**（含 devppl_glm_probe.sh） | ✅ 对照更新 |

> **S12 说明**：QA-EXEC 报告记录为 5 项（L42），DPL-103 已加第 6 项（devppl_glm_probe.sh，L45）。本卡实测 L45 = 6 项，S12 结论从"✅"升级为"✅（已同步更新清单）"。

---

## 4. 新发现详细论证（按 §1.2 五步判定公式）

### F1-MAJOR：`.glm_shutdown` 被 finalize 提交进 git，新 checkout/worktree 检出 stale 标记 → 永久抑制 oc_wake_check

**现象**：
- main @ 8d1b468 仓库在库 `.glm_shutdown` 内容：
  ```
  shutdown_at=2026-09-01T15:20:22+0800
  reset_at=2026-09-01 18:21:02       ← 已过时（现在 19:18）
  probe_response={"error":{...}}
  ```
- QA-EXEC 报告 T6a-T6c 在 fixture 内隔离通过；但 live 环境下（worktree 检出 `.glm_shutdown`），oc_wake_check 源 L 检测命中 stale 标记 → PRD-GATE T6a/T6b 失败。
- **A/B 实证**：本卡实测 `bash test_cmd_channel.sh` 390/8，T6a/T6b 失败原因 = `oc_wake_check` 输出**不含** `[blocked-new]` 标注（stale 标记阻止唤醒器感知新增 blocked 卡）。

**判定公式**：
1. **用户可感知**：✅ — 新 checkout/worktree 必踩；唤醒器静默丢失卡状态变更 → 阻塞新迭代任务派发
2. **功能阻断**：✅ — oc_wake_check 是唤醒器核心组件，源 L 检测命中 stale 标记后跳过 `blocked-new` 感知 → 链卡无法被推进
3. **workaround**：✅ — 手工 `rm .glm_shutdown && git rm .glm_shutdown && git commit`；但每新建 worktree 必踩，自动化流水线必受影响
4. **安全漏洞**：❌ — 非 OWASP Top 10 类别
5. **结论**：**MAJOR**（用户可感知 AND 功能阻断 AND workaround 存在）

**根因**：`glm_quota_probe.sh` finalize_mech() L459 `git add -A` 把 `.glm_shutdown` 静默提交进 git（2f13667 首次/7f6aaa6 再犯）。oc_wake_check 源 L 检测只看"存在"不看"reset_at 是否过期"（L704）→ 新 checkout 自动检出 stale 标记 → 永久抑制。

**修复建议**：
- finalize_mech() 内 `git add -A` 改为 `git add -A -- .github .hermes .pipeline`（白名单），排除 `.glm_shutdown` 等运行时标记；
- 或 finalize_mech() 提交前显式 `git rm --cached .glm_shutdown 2>/dev/null || true`。

---

### F2-MINOR：限频文件 `/tmp/glm_agnes_dispatch_failed_ts` 硬编码非 env 可控

**现象**：
- `glm_quota_probe.sh` L532 硬编码 `_alert_ts_file="/tmp/glm_agnes_dispatch_failed_ts"`，非 `$GLM_*` 环境变量可控。
- 本卡实测 16:57 时段（run 1283）ts 文件值 `1788261318` 被测试污染；清理后还原为 `1788253047`。
- 跨沙箱 `/tmp` 重建后限频状态静默丢失，导致告警语义失效。

**判定公式**：
1. **用户可感知**：✅ — 限频告警语义失效（10 分钟内 2 次而非 1 次）
2. **功能阻断**：❌ — 不影响熔断/恢复核心链路
3. **workaround**：✅ — 手工清理 `/tmp` 即可
4. **安全漏洞**：❌
5. **结论**：**MINOR**（用户可感知但不影响核心任务完成）

**修复建议**：将文件路径改为 `${GLM_ALERT_TS_FILE:-/tmp/glm_agnes_dispatch_failed_ts}`，测试 fixture 可注入隔离路径。

---

### F3-MINOR：双出口告警导致 10 分钟内 2 次 alert

**现象**：
- `dispatch_agnes()` 函数有两处告警出口：
  - L530-538：限频文件控制（仅在首次超限写 ts + 告警）
  - L557-558：即时告警路径（retry 计数达限但未走限频分支时）
- 单 tick retry 首次达限 3 时：L558 即时告警不写 ts → 下一 tick L530 因 ts 缺失再告警 → 10 分钟内 2 次，与「只发一次防刷屏」意图不符。
- 本卡 `/tmp/d2_f3_probe.sh` 实证：`alert_at_5th=1`、`alert_total_by_6th=2`。

**判定公式**：
1. **用户可感知**：✅ — 告警频刷
2. **功能阻断**：❌ — 仅告警语义退化
3. **workaround**：✅ — 等待 24h 窗口刷新 ts
4. **安全漏洞**：❌
5. **结论**：**MINOR**（用户可感知但不影响核心任务完成）

**修复建议**：L557-558 即时告警前追加 `echo "$_now_ep" > "$_alert_ts_file"` 确保 ts 状态同步。

---

### F4-MAJOR：DPL-103 加第 6 项 must-sync 但未更新 test_deploy_drift.sh 测试种子

**现象**：
- `deploy_drift_check.sh` L45：`DEFAULT_SYNC_LIST="oc_wake_check.sh sentinel_alert.sh devppl_autopilot.sh close.sh glm_quota_probe.sh devppl_glm_probe.sh"`（6 项）
- `test_deploy_drift.sh` L50：种子循环 `for s in oc_wake_check.sh sentinel_alert.sh devppl_autopilot.sh close.sh glm_quota_probe.sh`（5 项，缺 devppl_glm_probe.sh）
- 实测 drift 测试 28/3（T1a/T3a/T5e 失败，均因 devppl_glm_probe.sh repo=missing profile=missing 未注入种子）
- **严重性**：main 回归套件 drift 测试红 → 发布信号失效（无法信任 drift 为绿的信号）

**判定公式**：
1. **用户可感知**：✅ — 发布门禁依赖 drift 套件结果，测试红导致误判
2. **功能阻断**：✅ — 发布门禁信号失效（无法从 drift 套件判断部署漂移状态）
3. **workaround**：✅ — 手工补种子 + 重跑；或临时跳过 T8（但失去漂移监控）
4. **安全漏洞**：❌
5. **结论**：**MAJOR**（用户可感知 AND 功能阻断 AND workaround 存在）

**修复建议**：`test_deploy_drift.sh` L50 循环补第 6 项 `devppl_glm_probe.sh`，与 deploy_drift_check.sh 保持同步。

---

### T58-6 断言新回归（chain env 回滚重试状态机）

**现象**：
- run 1283（1d 前）cmd_channel 396/2（仅 T6a/T6b，归因于 stale 标记）
- 本卡 cmd_channel 390/8（T6a/T6b + **T58a/b/c/d/i/j 6 断言**）
- T58 测试：链卡 env 失败 3 次 → 应回滚 ready（1/2次）→ blocked（3次）；成功路径 env 失败 1 次 → ready → repo 恢复 → done
- 实测：第 1 次 env 失败 **直接 blocked**（而非 ready），计数 comment 未写。

**判定公式**：
1. **用户可感知**：✅ — 链卡 env 失败（repo 不可用）时错误阻塞，不重试
2. **功能阻断**：✅ — 新迭代卡（merge ready）env 失败后立即 blocked，无法自愈
3. **workaround**：✅ — 手工 unblock 重跑
4. **安全漏洞**：❌
5. **结论**：**MAJOR**（用户可感知 AND 功能阻断 AND workaround 存在）

**根因待查**：chain_retry_env 逻辑 CAS `WHERE status='running'` 未命中（可能上游 advance_sequential_chains 已先回滚）。需研发排查链卡消费时序。

---

## 5. 验收标准映射（PRD A1-A7）

| # | 验收要点 | 证据 | 结果 |
|---|---|---|:---:|
| A1 | 探针四态分类可用 | T1a-T1e 全过 + S1-S3 | ✅ |
| A2 | 连续 2 次 QUOTA_EXHAUSTED → 熔断五维 | T2a-T2c 全过 + S4-S6 | ✅ |
| A3 | 熔断后机械收尾 + R5 agnes 派发 | T3a-T3c 全过 + S7/S9 | ✅ |
| A4 | 分级恢复：窗口型 / 无窗口 / --force / D7 对账 | T4a-T4d 全过 + S8 | ✅ |
| A5 | 全流程 --inject 可重复 + 测试后零污染 | T5a-T5e 全过（含 T5b）+ P1/P2 | ✅ |
| A6 | 源 L 停机感知 + must-sync 清单 +1 | T6a-T6c fixture 全过 + S11 | ⚠️ **live 环境 F1 破坏** |
| A7 | R7 fallback 建议登记 | T7a/T7b + arch §9 R7 段 | ✅ |

> **A6 说明**：fixture 内隔离通过，但 live 环境因 F1 stale 标记被 oc_wake_check 抑制 → **A6 仅部分成立**。

---

## 6. 分级标准对照（qa-finding-classification.md v1.0）

### 6.1 本卡发现分级汇总

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 判定 | 依据 |
|------|:---:|:---:|:---:|:---:|:---:|------|
| **F1-MAJOR**（stale `.glm_shutdown` 抑制唤醒器） | ✅ | ✅ | ✅（手工删） | 否 | **MAJOR** | §1.2 MAJOR 行：用户可感知 + 功能阻断 + workaround 存在 |
| **F2-MINOR**（限频 ts 硬编码） | ✅ | ❌ | ✅ | 否 | **MINOR** | §1.2 MINOR 行：用户可感知但不影响核心任务 |
| **F3-MINOR**（双出口告警频刷） | ✅ | ❌ | ✅ | 否 | **MINOR** | §1.2 MINOR 行 |
| **F4-MAJOR**（drift 测试种子缺第 6 项） | ✅ | ✅ | ✅（手工补） | 否 | **MAJOR** | §1.2 MAJOR 行：发布信号失效 |
| **T58-MAJOR**（chain env 重试状态机回归） | ✅ | ✅ | ✅（手工 unblock） | 否 | **MAJOR** | §1.2 MAJOR 行 |
| OBS-A（DPL-048 部署漂移 2 项归 OC） | ✅ | ❌ | ✅ | 否 | **观察项** | 部署遗留，非代码缺陷（QA-EXEC 继承） |
| OBS-B（QA-EXEC 报告未落地 main） | ✅ | ❌ | ✅ | 否 | **观察项** | 归 OC 落 main |
| F1-MINOR（继承 D1 T5b flaky） | ✅ | ❌ | ✅（重跑/字段级比较） | 否 | **MINOR** | 维持 QA-EXEC 继承结论 |

### 6.2 判定公式对照（§1.2 五步）

**F1-MAJOR 完整五步**：
1. 用户可感知：✅ — 新 checkout 必踩 stale 标记，唤醒器静默丢卡
2. 功能阻断：✅ — oc_wake_check 是唤醒器核心，源 L 检测命中 stale 标记后跳过 blocked-new 感知 → 链卡无法被推进
3. workaround：✅ — 手工 `rm .glm_shutdown && git rm .glm_shutdown`
4. 安全漏洞：❌ — 非 OWASP Top 10 类别
5. **判定：MAJOR**（用户可感知 AND 功能阻断 AND workaround 存在）

**F4-MAJOR 完整五步**：
1. 用户可感知：✅ — 发布门禁依赖 drift 套件结果
2. 功能阻断：✅ — drift 测试红 → 无法信任部署漂移信号
3. workaround：✅ — 手工补种子 + 重跑
4. 安全漏洞：❌
5. **判定：MAJOR**

### 6.3 SLA 对照（§8）

| 级别 | 响应 | 定位（初步） | 方案 | 本卡状态 |
|------|:---:|:---:|:---:|:---:|
| BLOCKER | 4h | 8h | 24h | N/A（0 BLOCKER） |
| MAJOR | 8h | 24h | 72h | **F1/F4/T58 进入 SLA** |

> **SLA 启动**：本卡 claim 后 F1/F4/T58 进入研发评估 SLA。

### 6.4 发布门禁（§10）

| 门禁项 | 要求 | 本卡 | 通过 |
|---|:---:|:---:|:---:|
| BLOCKER | = 0 | 0 | ✅ |
| MAJOR | ≤ 3 | **3（F1+F4+T58）** | ❌ |
| 安全漏洞 | = 0 | 0 | ✅ |
| 未裁定申诉 | 无 | 0 | ✅ |

**发布门禁未通过**（MAJOR=3，但需研发裁定 F1/F4/T58 是否维持 MAJOR 或降级）。

---

## 7. 结论与后续

### 7.1 验收结论

1. **A1-A5/A7 验收全部成立**：四段函数 + 熔断 + 收尾 + 恢复 + 零污染 + R7 登记经 D2 独立复核成立。
2. **A6 部分成立**：fixture 内隔离通过，但 live 环境因 F1 stale 标记被 oc_wake_check 抑制 → 唤醒器感知链路断裂。
3. **pytest 零新增**：281/8/1 与 VA 基线逐项一致，DPL-103/104 未引入新回归（除 drift/cmd_channel 套件种子/逻辑）。
4. **静态 S1-S12 全部成立**：行号因 DPL-103/104 漂移微调，逻辑完整性不变。

### 7.2 新发现处置建议

| 发现 | 建议处置 | 责任方 |
|------|---------|--------|
| F1-MAJOR（stale 标记） | **立即修复**：finalize_mech() 排除 `.glm_shutdown` 进 git | 研发 |
| F4-MAJOR（drift 种子缺项） | **立即修复**：`test_deploy_drift.sh` L50 补第 6 项 | 研发 |
| T58（chain env 重试回归） | **排查**：chain_retry_env CAS 未命中的时序根因 | 研发 |
| F2-MINOR | 下个迭代：限频 ts 文件路径改为 env 可控 | 研发 |
| F3-MINOR | 下个迭代：即时告警出口补写 ts | 研发 |
| OBS-A（部署漂移 2 项） | OC 部署后复验 P8 | OC |
| OBS-B（QA-EXEC 报告未落地） | OC 合并 dangling commit `668c13e` | OC |

### 7.3 发布门禁状态

**当前：未通过**（MAJOR=3）

- 若研发裁定 F1/F4/T58 维持 MAJOR → **不得发版**
- 若研发裁定降级为 MINOR（需带新证据）→ MAJOR=0，门禁通过
- 若研发暂缓 F1/F4/T58 → 按 §11 需 Frank 签字

### 7.4 交付件

1. 本报告：`docs/qa/dpl099-glm-quota-shutdown-fallback-d2-review.md`
2. D2 探针脚本：`scripts/qa_dpl099_d2_probes.sh`（A-H 18 断言，已全绿）
3. F3 实证脚本：`/tmp/d2_f3_probe.sh`（保留供研发复现）

### 7.5 后续行动

1. **立即写 claim comment** 到本卡（含 F1-F4/T58 分级论证 + 判定公式对照 + SLA 启动）
2. **推送飞书汇报群**：`python3 /workspace/devPPL/scripts/send_claim_feishu.py t_00e0d32d`
3. **kanban_complete** 本卡（MAJOR 发现归研发评估，本卡 QA 侧工作完成）

---

## 附：与本报告相关的既有文档

- 测试方案：`docs/qa/dpl099-glm-quota-shutdown-fallback-test-plan.md`（v1.0）
- QA-EXEC 报告：`docs/qa/dpl099-glm-quota-shutdown-fallback-qa-exec-report.md`（v1.0）
- PRD：`mem-core 0c869ae wiki/projects/devppl/prd/dpl099-glm-quota-shutdown-fallback-prd.md`
- 架构：`mem-core 0c869ae wiki/projects/devppl/arch/arch-dpl099-glm-quota-shutdown-fallback.md`
- 分级标准：`docs/standards/qa-finding-classification.md` v1.0
- WIP 笔记：`.pipeline/wip/t_00e0d32d.md`（本卡进度）+ `.pipeline/wip/t_f08b2488.md`（QA-EXEC）
