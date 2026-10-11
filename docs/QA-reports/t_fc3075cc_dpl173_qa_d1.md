# QA-D1 报告 — DPL-173 oc_wake L4 强制输出根治（t_fc3075cc）

评审对象: dev 卡 t_3692069a，commit 3c2734c @ wt/t_3692069a（已 merge 本分支 3fd46db）
日期: 2026-09-29 | 评审人: game-qa（D1，execution lens）

## 1. 验证结果

### 1.1 子集复跑（DPL-137 QA-D1 只跑本卡子集）
- pytest tests/test_dpl173_oc_wake_blocked_still.py -q → **8 passed**（T1-T8）
- bash -n scripts/oc_wake_check.sh → 通过
- 变更相关回归 pytest -k "oc_wake or dpl172 or gate_audit" → **39 passed**

### 1.2 行为级独立探针（沙箱实跑 oc_wake_check.sh，非测试夹具复用）
| 探针 | 断言 | 结果 |
|------|------|------|
| N1 | blocked 2 张 → 两 tick `[blocked-still] N=2 ts=… tids=t_x1,t_y2`，ts nonce 每 tick 必变；无 NO_ANOMALY；不写 seen 键 | PASS |
| N2 | glm 停机窗口内 `[monitor-nonce]`/`[blocked-still]` 均抑制且 `[glm-shutdown]` 打印；窗口清除后 nonce 恢复 | PASS |
| N3 | 25 张 blocked 卡 → `N=25` 真实总数（独立 COUNT），tids LIMIT 20 防刷屏 | PASS |

### 1.3 diff 吸合审阅（git show 3c2734c 对照 ARCH v1.0）
- D1/D2: C2 独立 SELECT（LIMIT20 + COUNT(*)），输出行带 ts=now nonce，守卫 `not glm_tail`（停机期抑制，对齐 DPL-103）✓
- D3: `[monitor-nonce] epoch` 内聚主脚本，仅 `state=paused` 且非停机窗口时打印 ✓
- D4: seen 跳过名单 +2 tag（blocked-still / monitor-nonce），双保险 ✓
- D5: oc_wake_monitor.sh 全删；rg 全仓仅剩 wiki 存证/注释/测试存证引用，无活引用（scripts/jobs.json 零残留）✓

### 1.4 与上游核对
- VA 抽查 t_9aa02aff 5/5 VERIFIED、0 FALSIFIED — 与本报告独立结果一致。
- claim 声明 8 passed / 39 passed / bash -n — 均独立复现成功。

## 2. §1.2 判定公式对照（qa-finding-classification.md）

逐项用户可感知/功能阻断/workaround 判定: 未发现任何缺陷项。
- BLOCKER = 0（无功能阻断、无安全项）
- MAJOR = 0
- MINOR = 0
- SUGGESTION = 0
边界确认: 停机窗口抑制为设计语义（DA3，对齐 DPL-103 窗口语义），非缺陷。

## 3. SLA 对照

无 BLOCKER/MAJOR 发现 → 无 SLA 时钟启动，不适用。

## 4. 发布门禁对照（§10）

BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉 → **门禁 PASS**。
全量 pytest 留待合并后 main 节点（DPL-137），本卡不跑全量。

## 5. Verdict

PASS — 实现符合 PRD/ARCH，行为级与测试级双重验证全绿，建议合并。
