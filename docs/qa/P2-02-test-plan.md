# P2-02 HCD Watchdog 心跳路径修复 — QA 测试方案

> 版本：v1.0 | 日期：2026-07-11 | 作者：game-qa
>
> 被测变更：`hermes_hcd_watchdog.sh`
> - L4: `.hcd_heartbeat` → `.hermes_heartbeat`
> - L15: `cat` → `stat -c %Y`（因为 `.hermes_heartbeat` 是 JSON 格式）
>
> 分级依据：`docs/standards/qa-finding-classification.md` v1.0

---

## 被测脚本结构速览

```
 1  #!/bin/bash
 4  readonly HEARTBEAT="/workspace/.hermes_heartbeat"    # ← 变更点 1
 5  readonly STALE_SECONDS=180
10  if [[ ! -f "${HEARTBEAT}" ]]; then                   # 文件缺失 → exit 1
11      echo "[$(date)] HCD Watchdog: 心跳文件不存在" >&2
12      exit 1
15  last=$(stat -c %Y "${HEARTBEAT}")                    # ← 变更点 2: cat → stat
17  age=$((now - last))
19  if [[ ${age} -gt ${STALE_SECONDS} ]]; then           # 过期 → 飞书告警 + exit 1
28      exit 1
30  # silent exit 0                                       # 正常 → 静默退出
```

三种出口：
| 路径 | 条件 | exit code | 副作用 |
|------|------|:---:|------|
| 文件缺失 | `! -f HEARTBEAT` | 1 | stderr 日志 |
| 心跳过期 | `age > 180s` | 1 | 飞书告警 |
| 正常心跳 | 文件存在且新鲜 | 0 | 无（静默） |

---

## 测试用例

### TC-01: 正常心跳 — 静默退出
| 维度 | 内容 |
|------|------|
| **用例编号** | TC-01 |
| **触发条件** | `.hermes_heartbeat` 存在，mtime 距离当前时间 < 180s |
| **前置步骤** | `touch /workspace/.hermes_heartbeat`（确保 mtime 新鲜） |
| **执行命令** | `bash /workspace/hermes_hcd_watchdog.sh` |
| **预期结果** | exit code = 0，stdout/stderr 无输出 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（daemon 监控失效时用户收不到告警）+ 功能阻断（正常路径是整个监控链路的基石）+ 无 workaround（若正常路径失败，整个 watchdog 不可用）。涉及系统健康度退化的「用户可感知」扩展定义。 |
| **环境依赖** | 需要 `.hermes_heartbeat` 文件存在 |

### TC-02: 心跳过期 — 告警触发
| 维度 | 内容 |
|------|------|
| **用例编号** | TC-02 |
| **触发条件** | `.hermes_heartbeat` 存在，但 mtime > 180s 前 |
| **前置步骤** | `touch -d "200 seconds ago" /workspace/.hermes_heartbeat` |
| **执行命令** | `bash /workspace/hermes_hcd_watchdog.sh` |
| **预期结果** | exit code = 1，飞书告警发送成功 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（daemon 挂了但收不到告警）+ 功能阻断（过期检测是最核心的监控能力）+ 无 workaround。若过期检测失效，运维人员无法感知 daemon 停止，属于系统健康度严重退化。 |
| **注意事项** | 飞书 webhook 需要有效的 `FEISHU_*` 环境变量。测试后需 `touch` 恢复心跳文件。 |

### TC-03: 文件缺失 — 错误报告
| 维度 | 内容 |
|------|------|
| **用例编号** | TC-03 |
| **触发条件** | `.hermes_heartbeat` 文件不存在 |
| **前置步骤** | `mv /workspace/.hermes_heartbeat /workspace/.hermes_heartbeat.bak` |
| **执行命令** | `bash /workspace/hermes_hcd_watchdog.sh` |
| **预期结果** | exit code = 1，stderr 输出含 "[日期] HCD Watchdog: 心跳文件不存在" |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（daemon 进程崩溃或文件被误删后无告警）+ 功能阻断（文件缺失检测是 watchdog 的第一道防线）+ 无 workaround。文件不存在意味着 daemon 已停止写入，运维必须立即感知。 |
| **注意事项** | 测试后需 `mv` 恢复心跳文件。 |

### TC-04: crontab 回归 — 定时运行链路
| 维度 | 内容 |
|------|------|
| **用例编号** | TC-04 |
| **触发条件** | crontab 每 5 分钟自动触发 watchdog |
| **前置步骤** | 确认 crontab 条目存在：`*/5 * * * * bash /workspace/hermes_hcd_watchdog.sh >> /workspace/.hcd_watchdog_cron.log 2>&1` |
| **执行命令** | 等待一个 cron 周期（≤ 5 分钟），检查 cron 日志 `tail -3 /workspace/.hcd_watchdog_cron.log` |
| **预期结果** | cron 日志正常追加（心跳新鲜时无输出，过期/缺失时有记录）。无 "command not found"、"Permission denied" 或其他 shell 错误。 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（crontab 不工作则监控链断裂）+ 功能阻断但有 workaround（手动运行 `bash hermes_hcd_watchdog.sh` 仍可工作）。不满足 BLOCKER 条件因为有 workaround，但严重影响自动化监控体验，符合 MAJOR 定义。 |
| **注意事项** | 若 crontab 条目本身不存在 → 升级为 BLOCKER（部署问题，需立即修复）。 |

---

## 边界条件补充（非必须，建议执行）

| 编号 | 场景 | 触发 | 预期 | 级别 |
|------|------|------|------|------|
| TC-E1 | `stat -c %Y` 返回值是有效 epoch | `stat -c %Y .hermes_heartbeat` | 输出 10 位数字，范围在合理 epoch 内 | MAJOR |
| TC-E2 | 心跳文件恰好 180s（边界） | `touch -d "180 seconds ago" ...` | 180 ≤ STALE(180) → 不告警，exit 0 | MAJOR |
| TC-E3 | 心跳文件恰好 181s（边界+1） | `touch -d "181 seconds ago" ...` | 181 > 180 → 告警，exit 1 | MAJOR |
| TC-E4 | 时钟回拨（负 age） | 手动设置系统时间倒退 | age 为负 → 不告警（-N ≤ 180）exit 0 | MINOR |
| TC-E5 | heartbeat 路径含空格/特殊字符 | 临时替换 HEARTBEAT 变量 | 可能因引号不完整而失败 | SUGGESTION |
| TC-E6 | TOCTOU — stat 错误处理验证（新增） | 创建文件后删除，验证 stat || { echo; exit 1; } 模式 | 5 项子测试全部通过 | MAJOR |

> **TC-E7 (非数字输入)** 已删除 — 研发评审确认 stat -c %Y 不可能返回非数字但 exit 0，该用例不合理。

---

## 执行结果 (全量测试)

**执行时间**: 2026-07-11 13:36 CST | **测试脚本**: `tests/test_P2-02_full.py`

| 用例 | 结果 | exit code | 备注 |
|------|:---:|:---:|------|
| TC-01 (正常心跳) | PASS | 0 | 静默退出 |
| TC-02 (心跳过期) | PASS | 1 | 飞书告警 "sent" |
| TC-03 (文件缺失) | PASS | 1 | stderr: "心跳文件不存在" |
| TC-04 (crontab 回归) | PASS | — | crontab entry 确认 + cron log 7 lines |
| TC-E1 (stat epoch) | PASS | 0 | 输出 1783748209（有效 epoch） |
| TC-E2 (180s 边界) | PASS | 0 | 恰好 180s → 不告警 |
| TC-E3 (181s 边界+1) | PASS | 1 | 恰好 181s → 触发告警 |
| TC-E4 (时钟回拨) | PASS | 0 | 负 age → 不告警 |
| TC-E5 (路径引号) | PASS | — | `"${HEARTBEAT}"` 已正确加引号 |
| TC-E6 (TOCTOU/stat) | PASS | — | 5 项子测试全部通过（见下） |

### TC-E6 子测试明细

| 子测试 | 描述 | 结果 |
|:---:|------|:---:|
| 1 | stat 失败时错误处理 (L15 pattern 独立测试) | ✓ exit 1 + "无法读取心跳文件时间戳" |
| 2 | stat 成功时正常路径 | ✓ exit 0 + 有效 epoch |
| 3 | watchdog 文件缺失完整路径 (L10 -f) | ✓ exit 1 + "心跳文件不存在" |
| 4a | watchdog 集成 stat 正常 | ✓ exit 0 |
| 4b | watchdog 集成文件删除 (L10/L15 双防线) | ✓ exit 1 + stderr（L10 先触发） |
| 5 | stat 输出格式验证 | ✓ 10 位纯数字 epoch |

---

## 发布门禁检查

对照标准 §10：

| 门禁条件 | 状态 |
|------|:---:|
| BLOCKER = 0 | ✅ 0 (3/3 PASS) |
| MAJOR ≤ 3 | ✅ 0 (5/5 PASS) |
| 安全漏洞 = 0 | ✅ N/A（非安全类变更） |
| 无未裁定申诉 | ✅ N/A |

**结论：PASS — 可以发布。**

## 变更摘要

| 项目 | 说明 |
|------|------|
| 被测脚本 | `/workspace/hermes_hcd_watchdog.sh` v1.0 |
| 核心变更 | L4: `.hcd_heartbeat` → `.hermes_heartbeat`；L15: `cat` → `stat -c %Y` |
| 修复变更 | L15: 新增 `2>/dev/null) \|\| { echo "..."; exit 1; }` stat 错误处理 |
| 测试脚本 | `tests/test_P2-02_full.py` (354 行, 10 用例) |
| JSON 报告 | `tests/results_P2-02.json` |

---

## 结构化 Claims (claim-schema v1.0)

```json
{
  "schema_version": "1.0",
  "agent": "game-qa",
  "task_id": "t_547104fc",
  "completed_at": "2026-07-11T19:08:00+08:00",
  "claims": [
    {
      "id": "c1",
      "type": "file_modified",
      "target": "/workspace/devPPL/docs/qa/P2-02-test-plan.md",
      "expected": "Test plan file exists with 156+ lines, covering 4 core + 6 edge cases",
      "evidence": "wc -l /workspace/devPPL/docs/qa/P2-02-test-plan.md | awk '{print $1}'"
    },
    {
      "id": "c2",
      "type": "file_created",
      "target": "/workspace/devPPL/tests/test_P2-02_full.py",
      "expected": "Test script exists with 10 test cases covering TC-01~TC-04 and TC-E1~TC-E6",
      "evidence": "stat /workspace/devPPL/tests/test_P2-02_full.py && python3 -c 'import ast; ast.parse(open(\"/workspace/devPPL/tests/test_P2-02_full.py\").read()); print(\"syntax OK\")'",
      "transient": false
    },
    {
      "id": "c3",
      "type": "file_created",
      "target": "/workspace/devPPL/tests/results_P2-02.json",
      "expected": "JSON results file exists with 10 test results (all PASS)",
      "evidence": "python3 -c \"import json; d=json.load(open('/workspace/devPPL/tests/results_P2-02.json')); print(f'{len(d.get(\\\"results\\\",d))} results')\"",
      "transient": false
    },
    {
      "id": "c4",
      "type": "test_passed",
      "target": "bash /workspace/hermes_hcd_watchdog.sh (smoke: TC-01/02/03)",
      "expected": "3 smoke scenarios: fresh heartbeat exit 0, stale heartbeat exit 1 + alert, missing file exit 1 + stderr",
      "evidence": "touch /workspace/.hermes_heartbeat && bash /workspace/hermes_hcd_watchdog.sh; echo exit=$? (expect 0). touch -d '200 seconds ago' /workspace/.hermes_heartbeat && bash /workspace/hermes_hcd_watchdog.sh; echo exit=$? (expect 1). mv /workspace/.hermes_heartbeat /tmp/.hh.bak && bash /workspace/hermes_hcd_watchdog.sh; echo exit=$? (expect 1). mv /tmp/.hh.bak /workspace/.hermes_heartbeat"
    },
    {
      "id": "c5",
      "type": "config_updated",
      "target": "/workspace/hermes_hcd_watchdog.sh",
      "expected": "L4 references .hermes_heartbeat (not .hcd_heartbeat), L15 uses stat -c %Y (not cat)",
      "evidence": "grep -n '.hermes_heartbeat\\|stat -c %Y' /workspace/hermes_hcd_watchdog.sh",
      "value": ".hermes_heartbeat + stat -c %Y"
    }
  ]
}
```
