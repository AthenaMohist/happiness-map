# QA 复测报告: P0-15 MINOR x3 [FIX] — A3/A4/A5

**任务**: t_c838e170 — QA RETEST: P0-15 MINOR x3 [FIX] 专项复测 (A3/A4/A5)
**复测日期**: 2026-07-10
**QA 执行**: game-qa
**原始发现**: D2 MINOR 分级陈述 (t_34dadb21) — A3/A4/A5 三项 MINOR
**标准依据**: `docs/standards/qa-finding-classification.md` v1.0, YAML `config/qa-classification.yaml` v1.0.0
**分级陈述**: `docs/qa-reaudits/P0-15-D2-MINOR-reclassification.md`

---

## 1. 复测结论

**PASS** — A3/A4/A5 三项 MINOR 修复全部验证通过，无回归。

| 指标 | 值 |
|------|-----|
| 全量回归 (53 项) | **53 PASS / 0 FAIL / 0 SKIP** |
| A5 Smoke (28 项) | **28 PASS / 0 FAIL** |
| 集成测试 (8 项) | **ALL 8 PASS** |
| Config Loader | **ALL OK** |
| A3 专项 (6 项, §3) | **6 PASS / 0 FAIL** |
| A4 专项 (REG-D2-05) | **PASS** ✓ |
| BLOCKER=0 | ✓ |
| MAJOR | 0 (≤3) |
| 安全漏洞 | 0 |
| 发布门禁评估 | **PASS** |

---

## 2. A3: reinstated 后原始卡片 [CLOSED] comment

### 2.1 原始发现

**位置**: `scripts/product_rule.py` reinstated 分支 (原 L68-L97)
**问题**: 产品裁定 `--verdict reinstated` 后创建新 kanban 卡片，但原始卡片未被标记关闭
**级别**: MINOR（user_visible=YES, no_block, workaround=YES）

### 2.2 修复内容

在 `product_rule.py` L108-109，reinstated 分支新增 [CLOSED] comment：

```python
# Close the original card — reinstated issue lives on in the new card
comment(args.task_id,
        f"\n[CLOSED] 产品裁定 reinstated {new_level} → 新卡片 {new_card_id}\n")
```

### 2.3 验证结果

| 测试 ID | 测试项 | 结果 |
|---------|--------|:---:|
| A3-D2-01 | has_ruling 防重复裁定 (product_rule 调用前检查) | PASS |
| A3-D2-02 | appeal.py 含 has_ruling 二次申诉防护 (红线 3) | PASS |
| A3-D2-03 | product_rule.py 的 reinstated 分支含 create_task 调用 | PASS |
| A3-D2-04 | product_rule.py 的 upheld 分支不调用 create_task | PASS |
| A3-D2-05 | [CLOSED] 状态在 STATE_PREFIXES 中存在 | PASS |
| A3-D2-06 | product_rule.py 的 reinstated 分支含 [CLOSED] comment | PASS |

**判定**: A3 修复已验证。原始卡片在 reinstated 裁定后会收到 [CLOSED] comment，引用新卡片 ID。

---

## 3. A4: assignee 从 YAML 配置读取

### 3.1 原始发现

**位置**: `scripts/product_rule.py` L93 (原 `assignee="game-engine"`)
**问题**: assignee 硬编码为字符串常量，团队重命名后卡片无法分发
**级别**: MINOR（user_visible=NO, system_health_risk, 修复成本极低）

### 3.2 修复内容

三层修改：

1. **YAML 配置** (`config/qa-classification.yaml` L291):
```yaml
product_ruling:
  reinstated_default_assignee: "game-engine"
```

2. **config_loader 访问器** (`scripts/lib/config_loader.py` L209-216):
```python
def get_reinstated_default_assignee() -> str:
    return load_config()["product_ruling"]["reinstated_default_assignee"]
```

3. **product_rule.py 使用** (L29, L103):
```python
from lib.config_loader import get_reinstated_default_assignee
# ...
assignee=get_reinstated_default_assignee(),  # was: assignee="game-engine",
```

### 3.3 验证结果

| 测试 ID | 测试项 | 结果 |
|---------|--------|:---:|
| M1-D2-02 | config_loader 导出 16 个公开访问器（含 get_reinstated_default_assignee） | PASS |
| M2-D2-02 | 所有 YAML 顶级 key 都被 config_loader 覆盖（含 product_ruling） | PASS |
| REG-D2-05 | 无硬编码 assignee 字符串 (A4 已修复) | PASS |
| M1-D2-05 | VALID_LEVELS 全局一致性 (kanban_helpers == config_loader) | PASS |

**判定**: A4 修复已验证。assignee 完全从 YAML 读取，product_rule.py 无遗留硬编码。

---

## 4. A5: 申诉日志 JSON lines 结构化

### 4.1 原始发现

**问题**: 所有 comment 使用自由格式 Markdown，appeal_tracker 仅通过 `startswith("[PREFIX]")` 分类，无法提取结构化字段
**级别**: MINOR（user_visible=NO, maintainability risk）

### 4.2 修复内容

新增 `log_action()` 函数 (`scripts/lib/kanban_helpers.py` L125-142)：
- 写入结构化 JSON lines 到 `logs/appeal_audit.jsonl`
- 每条记录含: `action`, `task_id`, `timestamp` (ISO 8601) + 元数据
- 向后兼容：不影响现有 `comment()` 输出

所有 5 个脚本均已集成 `log_action()` 调用：
- `appeal.py` L97-100: `log_action("appeal", ...)` — 携带 evidence_type, current_level
- `dev_reject.py` L92-96: `log_action("reject", ...)` — 携带 reason, attempts
- `product_rule.py` L68-70 / L87-90: `log_action("ruling", ...)` — 携带 verdict, level
- `downgrade_notify.py` L80-83: `log_action("downgrade", ...)` — 携带 from_level, to_level
- `defer.py` L113-117: `log_action("defer", ...)` — 携带 target_version, frank_confirmed

### 4.3 验证结果

| 测试 ID | 测试项 | 结果 |
|---------|--------|:---:|
| A5-SMOKE-01 | log file created | PASS |
| A5-SMOKE-02 | 3 entries written | PASS |
| A5-SMOKE-03 (×3) | valid JSON | PASS |
| A5-SMOKE-04~07 (×3) | action/task_id/timestamp/ISO 8601 | PASS |
| A5-SMOKE-08 | comment() unchanged and callable (向后兼容) | PASS |
| A5-SMOKE-09 (×5) | all 5 scripts import log_action | PASS |
| A5-SMOKE-10 (×5) | all 5 scripts call log_action() | PASS |

**判定**: A5 修复已验证。JSON lines 格式正确，5 脚本全覆盖，向后兼容。

---

## 5. 全量回归

### 5.1 测试套件一览

| Suite | 测试数 | PASS | FAIL | SKIP |
|-------|:---:|:---:|:---:|:---:|
| test_p0_15_d2.py (§1-8) | 53 | 53 | 0 | 0 |
| test_a5_smoke.py | 28 | 28 | 0 | 0 |
| test_integration.py | 8 | 8 | 0 | 0 |
| test_config_loader.py | — | ALL OK | — | — |
| **合计** | **89+** | **89+** | **0** | **0** |

### 5.2 按 Section 分布 (test_p0_15_d2.py)

| Section | 内容 | PASS | FAIL |
|---------|------|:---:|:---:|
| §1 | A1 whoami 前置验证 | 3 | 0 |
| §2 | A2 STATE_PREFIXES 同步 | 11 | 0 |
| §3 | A3 CLOSED 防护 | 6 | 0 |
| §4 | E2E 全流程集成 | 6 | 0 |
| §5 | Dev Supplements | 7 | 0 |
| §6 | M1/M2 模块覆盖 | 10 | 0 |
| §7 | 回归验证 | 6 | 0 |
| §8 | Schema & Security | 4 | 0 |

---

## 6. 发布门禁

按标准 §10 公式: `BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉`

| 门禁项 | 阈值 | 实测 | 判定 |
|--------|:---:|:---:|:---:|
| BLOCKER | = 0 | **0** | ✅ |
| MAJOR | ≤ 3 | **0** | ✅ |
| 安全漏洞 | = 0 | **0** | ✅ |
| 未裁定申诉 | = 0 | **0** | ✅ |

**发布门禁: PASS** ✅ — 三项 MINOR 修复验证通过，无回归，无阻塞项。

---

## 7. 缺陷状态更新

| 发现 ID | 描述 | 原级别 | 修复状态 | 关联测试 |
|---------|------|:---:|:---:|------|
| A3 | reinstated 后原始卡片未关闭 | MINOR | **FIXED** ✓ | A3-D2-01~06 |
| A4 | assignee 硬编码 | MINOR | **FIXED** ✓ | REG-D2-05, M1-D2-02, M2-D2-02 |
| A5 | 申诉日志无结构化格式 | MINOR | **FIXED** ✓ | A5-SMOKE-01~10 |

## 8. 建议后续动作

1. **A3 后续版本跟进**: 当前修复仅添加 [CLOSED] comment。P0-16 可考虑让 kanban 状态机本身联动（即 CLOSED comment → 自动切换 card status 为 done），无需手动操作。当前 workaround（看板维护者手动标记 done）接受范围内。
2. **A4 运维提醒**: 如未来重命名团队角色，只需修改 `config/qa-classification.yaml` 的 `product_ruling.reinstated_default_assignee`，无需改代码。建议在团队 onboarding 文档中标注此配置项。
3. **A5 数据利用**: `logs/appeal_audit.jsonl` 已就绪。P0-16 可增强 `appeal_tracker.py` 的 `classify_task()`，从 JSON lines 提取结构化字段（evidence_type, level, timestamp），替代当前的纯 text startswith 分类。

---

> 报告版本: v1.0 | 状态: Final
> 关联文档: `docs/qa-reaudits/P0-15-D2-MINOR-reclassification.md`
