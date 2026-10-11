# P2-02 HCD Watchdog 全量测试 — QA 报告

> 版本：v1.0 | 日期：2026-07-11 13:36 CST | 测试者：game-qa
>
> 分级依据：`docs/standards/qa-finding-classification.md` v1.0 + `config/qa-classification.yaml` v1.0.0

---

## 1. 执行概要

| 指标 | 值 |
|------|-----|
| 被测脚本 | `/workspace/hermes_hcd_watchdog.sh` |
| 测试脚本 | `tests/test_P2-02_full.py` (354 行) |
| 总用例数 | 10 |
| PASS | **10** |
| FAIL | 0 |
| ERROR | 0 |
| SKIP | 0 |
| 执行时间 | 2026-07-11 13:36 CST |

---

## 2. 分级结果汇总

### BLOCKER (3/3 PASS) — 发布门禁核心

| 用例 | 结果 | 分级依据 (§1.2) |
|------|:---:|------|
| TC-01 正常心跳 — 静默退出 | PASS | 用户可感知 + 功能阻断 + 无 workaround |
| TC-02 心跳过期 — 告警触发 | PASS | 用户可感知 + 功能阻断 + 无 workaround |
| TC-03 文件缺失 — 错误报告 | PASS | 用户可感知 + 功能阻断 + 无 workaround |

### MAJOR (5/5 PASS)

| 用例 | 结果 | 分级依据 (§1.2) |
|------|:---:|------|
| TC-04 crontab 回归 | PASS | 有 workaround（手动运行） |
| TC-E1 stat epoch 验证 | PASS | 系统健康度退化（stat 格式异常则监控链断裂） |
| TC-E2 180s 边界 | PASS | 用户体验退化（边界误告警） |
| TC-E3 181s 边界+1 | PASS | 用户体验退化（边界漏报） |
| TC-E6 TOCTOU stat 错误处理 | PASS | 系统健康度退化（stat 失败未处理则监控失效） |

### MINOR (1/1 PASS)

| 用例 | 结果 | 分级依据 (§1.2) |
|------|:---:|------|
| TC-E4 时钟回拨 | PASS | 用户可感知 + 不影响核心任务完成 |

### SUGGESTION (1/1 PASS)

| 用例 | 结果 | 分级依据 (§1.2) |
|------|:---:|------|
| TC-E5 路径引号 | PASS | 用户不可感知 + 纯代码层面 |

---

## 3. TC-E6 TOCTOU 详细结果（新增用例）

**目的**: 独立验证 D1 裁决中架构师发现的 MAJOR 问题（stat 错误处理缺失）的修复效果。

| # | 子测试 | 预期 | 实际 | 结果 |
|:-:|------|------|------|:---:|
| 1 | stat 失败 → 错误处理 | exit 1 + "无法读取心跳文件时间戳" | exit=1 stderr 符合 | PASS |
| 2 | stat 正常路径 | exit 0 + 有效 epoch | exit=0 epoch=1783748213 | PASS |
| 3 | watchdog 文件缺失 (L10) | exit 1 + "心跳文件不存在" | exit=1 stderr 符合 | PASS |
| 4a | watchdog 集成 stat 正常 | exit 0 | exit=0 | PASS |
| 4b | watchdog 集成文件删除 | exit 1 + stderr（L10/L15 双防线） | exit=1 stderr 符合（L10 触发） | PASS |
| 5 | stat 输出格式 | 10 位纯数字 epoch | "1783748213" | PASS |

**结论**: stat 错误处理修复（L15: `2>/dev/null) || { echo "..."; exit 1; }`）验证通过。L10（-f 检查）和 L15（stat || handler）构成双防线，任一触发均可正确报告错误。

---

## 4. 发布门禁 (§10)

对照标准 §10：`BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉`

| 门禁条件 | 状态 | 说明 |
|------|:---:|------|
| BLOCKER = 0 | ✅ PASS | 3/3 BLOCKER 全部通过 |
| MAJOR ≤ 3 | ✅ PASS | 0 FAIL（5/5 全部通过） |
| 安全漏洞 = 0 | ✅ N/A | 非安全类变更 |
| 无未裁定申诉 | ✅ N/A | 无申诉 |

**门禁判定: PASS — 可以发布。**

---

## 5. 发现与建议

### 无新增 BLOCKER/MAJOR

全量 10 用例全部 PASS，未发现新问题。

### SUGGESTION

| # | 描述 | 级别 | 依据 |
|:-:|------|:---:|------|
| S1 | TC-E4 时钟回拨场景依赖系统时间准确性。当前 `age < 0` 时 exit 0（不告警），这在 NTP 同步后的短暂回拨中是安全的。但若 NTP 故障导致持续回拨，watchdog 会静默失效。建议后续版本增加 `age < -3600` 时的异常告警。 | SUGGESTION | 用户不可感知 + 极端场景 + 有替代防护（NTP 自身监控） |

---

## 6. 测试产物

| 文件 | 路径 |
|------|------|
| 测试脚本 | `/workspace/devPPL/tests/test_P2-02_full.py` |
| JSON 报告 | `/workspace/devPPL/tests/results_P2-02.json` |
| 测试方案 (更新) | `/workspace/devPPL/docs/qa/P2-02-test-plan.md` |
| QA 报告 | `/workspace/devPPL/docs/qa/P2-02-qa-report.md` (本文件) |

---

## 7. 判定公式对照 (合规声明)

本报告所有用例分级均严格对照标准 §1.2 五步判定公式：

```
前置检查 → 正式判定(BLOCKER/MAJOR/MINOR/SUGGESTION)
           → 安全漏洞独立判定(§2)
           → 数据敏感度加权(§4)
```

无模糊定级、无主观降级、无绕过公式。TC-01 原始定级 BLOCKER 经产品裁决降为 MAJOR（有条件通过）的记录已在 D1 裁定汇总中体现，本次全量测试的 BLOCKER=0 门禁基于修复后的代码执行结果。

---

*报告结束。2026-07-11 13:36 CST · game-qa*

---

## 8. 结构化 Claims (claim-schema v1.0)

```json
{
  "schema_version": "1.0",
  "agent": "game-qa",
  "task_id": "t_10229569",
  "completed_at": "2026-07-11T19:12:00+08:00",
  "claims": [
    {
      "id": "c1",
      "type": "file_modified",
      "target": "/workspace/devPPL/docs/qa/P2-02-qa-report.md",
      "expected": "QA report exists with 8 sections, covering 10/10 PASS results and release gate",
      "evidence": "grep -c '^## ' /workspace/devPPL/docs/qa/P2-02-qa-report.md",
      "transient": false
    },
    {
      "id": "c2",
      "type": "test_passed",
      "target": "python3 /workspace/devPPL/tests/test_P2-02_full.py",
      "expected": "10/10 test cases pass: 3 BLOCKER + 5 MAJOR + 1 MINOR + 1 SUGGESTION, exit code 0",
      "evidence": "cd /workspace/devPPL && python3 tests/test_P2-02_full.py 2>&1 | tail -5",
      "transient": false
    },
    {
      "id": "c3",
      "type": "file_created",
      "target": "/workspace/devPPL/tests/results_P2-02.json",
      "expected": "JSON results file with 10 results (all PASS), summary shows gate_pass: true",
      "evidence": "python3 -c \"import json; d=json.load(open('/workspace/devPPL/tests/results_P2-02.json')); print(f'passed={d[\\\"summary\\\"][\\\"passed\\\"]} gate_pass={d[\\\"summary\\\"][\\\"gate_pass\\\"]}')\"",
      "transient": false
    },
    {
      "id": "c4",
      "type": "test_passed",
      "target": "bash /workspace/hermes_hcd_watchdog.sh (smoke: fresh heartbeat → exit 0)",
      "expected": "Fresh heartbeat file produces exit 0 (silent, no output)",
      "evidence": "touch /workspace/.hermes_heartbeat && bash /workspace/hermes_hcd_watchdog.sh; echo exit=$? | grep 'exit=0'",
      "transient": false
    },
    {
      "id": "c5",
      "type": "config_updated",
      "target": "/workspace/hermes_hcd_watchdog.sh",
      "expected": "L15 contains 2>/dev/null || { echo stderr; exit 1; } stat error handling pattern",
      "evidence": "grep -c '2>/dev/null) || { echo.*无法读取心跳文件时间戳.*exit 1' /workspace/hermes_hcd_watchdog.sh",
      "value": "stat error handling fix",
      "transient": false
    }
  ]
}
```
